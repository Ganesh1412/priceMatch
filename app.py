import os
import re
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover - defensive fallback
    Anthropic = None

PARSE_BOT_URL = (
    "https://api.parse.bot/scraper/9a5779d1-6006-4cff-8af0-2f31ec742428/search_products"
)
PARSE_BOT_API_KEY = os.getenv("PARSE_BOT_API_KEY", "pmx_20f1381acba5ef3610a782c7fc0d057c")


def parse_price(value: object) -> float | None:
    """Extract a numeric price from scraper or form values."""
    match = re.search(r"\d+(?:,\d{3})*(?:\.\d{1,2})?", str(value))
    return float(match.group(0).replace(",", "")) if match else None


def build_local_verdict(product: str, customer_price: str, market_products: list[dict]) -> str:
    market_prices = [
        price
        for item in market_products
        if (price := parse_price(item.get("price") or item.get("current_price"))) is not None
    ]
    customer_value = parse_price(customer_price)
    if not market_prices or customer_value is None:
        return (
            f"Market data for '{product}' is available, but I could not compare the prices reliably.\n"
            f"Customer price provided: {customer_price}."
        )

    low, high = min(market_prices), max(market_prices)
    average = sum(market_prices) / len(market_prices)
    if customer_value < low:
        verdict = "below market"
    elif customer_value > high:
        verdict = "above market"
    else:
        verdict = "competitive"
    return (
        f"Local price check for '{product}': the customer price is {verdict}.\n"
        f"Market range: ${low:.2f}-$" f"{high:.2f} (average ${average:.2f}).\n"
        f"Customer price: ${customer_value:.2f}."
    )


async def fetch_market_prices(keyword: str, zipcode: str, count: int = 5) -> list[dict]:
    """Fetch product listings from the Parse Bot scraper API."""
    params = {
        "zip": zipcode,
        "count": count,
        "offset": 0,
        "keyword": keyword,
        "sort_by": "relevance",
    }
    headers = {"X-API-Key": PARSE_BOT_API_KEY}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(PARSE_BOT_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    # Response shape: {"status": "success", "data": {"products": [...], ...}}
    if isinstance(data, list):
        return data
    if "data" in data and isinstance(data["data"], dict):
        return data["data"].get("products", [])
    return data.get("products", data.get("results", []))

app = FastAPI(title="Price Match Customer Assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")


class PriceRequest(BaseModel):
    product: str
    customer_price: str
    zipcode: str = "10001"


@app.get("/", response_class=FileResponse)
async def index():
    return FileResponse("templates/index.html")


@app.get("/health")

async def health():
    return {"status": "ok"}


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.svg")


@app.post("/api/verify-price")
async def verify_price(payload: PriceRequest):
    if not payload.product.strip():
        raise HTTPException(status_code=400, detail="Product name is required.")
    if not payload.customer_price.strip():
        raise HTTPException(status_code=400, detail="Customer price is required.")

    # Fetch live market prices from Parse Bot scraper
    try:
        market_products = await fetch_market_prices(payload.product.strip(), payload.zipcode)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Price scraper error: {exc.response.status_code}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch market prices: {exc}") from exc

    # Build a readable summary of scraped results for the prompt / demo response
    if market_products:
        lines = []
        for p in market_products[:5]:
            name = p.get("title") or p.get("name", "Unknown")
            price = p.get("price") or p.get("current_price", "N/A")
            store = p.get("store") or p.get("retailer", "")
            lines.append(f"- {name}: {price}" + (f" ({store})" if store else ""))
        market_summary = "\n".join(lines)
    else:
        market_summary = "No market listings found."

    if not os.getenv("ANTHROPIC_API_KEY") or Anthropic is None:
        reply = build_local_verdict(payload.product, payload.customer_price, market_products)
        return {"reply": reply, "mode": "demo", "market_products": market_products}

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = (
        f"The customer is asking about '{payload.product}' and says they saw it priced at {payload.customer_price}. "
        f"Here are the current market listings we fetched (zip code {payload.zipcode}):\n{market_summary}\n\n"
        "Based on this data, give a concise, customer-friendly verdict: is the customer's price competitive, "
        "above market, or below market? Include the price range found and a brief recommendation."
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            system=(
                "You are a helpful retail pricing assistant. You receive live product listings and a customer-provided price. "
                "Give a brief, friendly verdict on whether the customer's price is competitive. Be specific about numbers."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Anthropic request failed: {exc}") from exc

    return {"reply": text, "mode": "anthropic", "market_products": market_products}
