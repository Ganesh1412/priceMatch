import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover - defensive fallback
    Anthropic = None

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

    if not os.getenv("ANTHROPIC_API_KEY") or Anthropic is None:
        reply = (
            f"Demo mode: I would verify the price for {payload.product} at {payload.customer_price} "
            f"against the Google Sheet and Target API. Set ANTHROPIC_API_KEY to enable live Anthropic responses."
        )
        return {"reply": reply, "mode": "demo"}

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = (
        "You are a pricing verification assistant for a retail customer experience. "
        f"The customer asked about product '{payload.product}' and provided a price of {payload.customer_price}. "
        f"Verify the price against a Google Sheet and Target API context. "
        "Return a concise, customer-friendly answer with a clear verdict such as 'competitive', 'above market', or 'below market'. "
        "Mention the data sources used and keep the response brief."
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=300,
            system=(
                "You are a pricing verification assistant. Compare a customer-provided price against market data "
                "from a Google Sheet and a Target API. Return a concise, friendly response that explains whether the price "
                "is competitive."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
    except Exception as exc:  # pragma: no cover - runtime safeguard
        raise HTTPException(status_code=502, detail=f"Anthropic request failed: {exc}") from exc

    return {"reply": text, "mode": "anthropic"}
