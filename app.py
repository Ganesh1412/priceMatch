import json
import os
import re
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

PARSE_BOT_URL = (
    "https://api.parse.bot/scraper/9a5779d1-6006-4cff-8af0-2f31ec742428/search_products"
)
PARSE_BOT_API_KEY = os.getenv("PARSE_BOT_API_KEY")


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
    pct_from_average = (customer_value - average) / average if average else 0
    if pct_from_average < -0.10:
        verdict = "below market"
    elif pct_from_average > 0.10:
        verdict = "above market"
    else:
        verdict = "competitive"
    return (
        f"Local price check for '{product}': the customer price is {verdict}.\n"
        f"Market range: ${low:.2f}-$" f"{high:.2f} (average ${average:.2f}).\n"
        f"Customer price: ${customer_value:.2f}."
    )


def relevant_market_products(product: str, market_products: list[dict]) -> list[dict]:
    """Filter out scraper fallback listings that don't relate to the requested product."""
    tokens = {t for t in re.findall(r"[a-z0-9]+", product.lower()) if len(t) >= 3}
    if not tokens:
        return market_products
    relevant = []
    for item in market_products:
        name = str(item.get("title") or item.get("name") or "").lower()
        if any(token in name for token in tokens):
            relevant.append(item)
    return relevant


LIMITATIONS = [
    "Listings are keyword matches, not confirmed identical products.",
    "Shipping, tax, and promotions are not normalized across listings.",
]


def build_verdict_data(product: str, customer_price: str, market_products: list[dict]) -> dict:
    """Build the structured verdict/comparison/confidence/listings payload."""
    listings = []
    usable_prices = []
    for item in relevant_market_products(product, market_products)[:5]:
        name = item.get("title") or item.get("name") or "Unknown"
        source = item.get("store") or item.get("retailer") or item.get("brand") or "Unknown source"
        price = parse_price(item.get("price") or item.get("current_price"))
        listings.append(
            {
                "name": name,
                "price": price,
                "source": source,
                "matchStatus": "keyword_match",
            }
        )
        if price is not None:
            usable_prices.append(price)

    customer_value = parse_price(customer_price)

    if len(usable_prices) < 2:
        return {
            "verdict": {
                "code": "insufficient_evidence",
                "label": "Not enough evidence",
                "explanation": (
                    f"We found fewer than two comparable listings for '{product}', "
                    "so we can't confidently verify this price."
                ),
            },
            "comparison": {
                "customerPrice": customer_value,
                "marketAverage": None,
                "comparableRange": {"low": None, "high": None},
                "lowestComparable": {"price": None, "difference": None, "percentageDifference": None},
            },
            "confidence": {
                "level": "low",
                "productMatch": "unknown",
                "reasons": ["Fewer than two usable comparable listings were found."],
            },
            "listings": listings,
            "limitations": LIMITATIONS,
        }

    low, high = min(usable_prices), max(usable_prices)
    average = sum(usable_prices) / len(usable_prices)
    lowest_price = low
    difference = None
    percentage_difference = None
    if customer_value is not None:
        difference = round(customer_value - lowest_price, 2)
        percentage_difference = round((difference / lowest_price) * 100, 2) if lowest_price else None

    if customer_value is None:
        code, label, explanation = (
            "insufficient_evidence",
            "Not enough evidence",
            "We couldn't read a valid customer price to compare against the market.",
        )
        confidence_level = "low"
    else:
        pct_from_average = (customer_value - average) / average if average else 0
        if abs(pct_from_average) <= 0.10:
            code, label = "competitive", "Competitive"
            explanation = f"The customer's price is within 10% of the market average of ${average:.2f}."
        elif pct_from_average < -0.10:
            code, label = "lower", "Below market"
            explanation = f"The customer's price is more than 10% below the market average of ${average:.2f}."
        else:
            code, label = "higher", "Above market"
            explanation = f"The customer's price is more than 10% above the market average of ${average:.2f}."
        confidence_level = "moderate"

    return {
        "verdict": {"code": code, "label": label, "explanation": explanation},
        "comparison": {
            "customerPrice": customer_value,
            "marketAverage": round(average, 2),
            "comparableRange": {"low": round(low, 2), "high": round(high, 2)},
            "lowestComparable": {
                "price": round(lowest_price, 2),
                "difference": difference,
                "percentageDifference": percentage_difference,
            },
        },
        "confidence": {
            "level": confidence_level,
            "productMatch": "keyword_match",
            "reasons": [
                "Listings matched by product keyword search, not by confirmed SKU/model.",
                f"{len(usable_prices)} usable comparable listing(s) found.",
            ],
        },
        "listings": listings,
        "limitations": LIMITATIONS,
    }


PRICE_PROXIMITY_WINDOW = 40.0

# Recognizable brand/product-line tokens; product names lacking any of these
# are treated as "generic" for the tier-ambiguous check below.
BRAND_TOKENS = {
    "apple", "airpods", "garmin", "fitbit", "samsung", "sony", "google", "pixel",
    "microsoft", "amazon", "lg", "bose", "jbl", "beats", "nike", "adidas", "dell",
    "hp", "lenovo", "asus", "acer", "canon", "nikon", "whirlpool", "kitchenaid",
    "dyson", "ninja", "keurig", "casio", "seiko", "timex", "oneplus", "xiaomi",
    "huawei", "motorola", "nokia", "logitech", "razer",
}

TIER_LABELS = ["Budget", "Mid-range", "Premium"]

# Wide-spread threshold for generic-name tier detection.
TIER_PRICE_RATIO_THRESHOLD = 3.0


def has_brand_token(product: str) -> bool:
    """Return True if the product name contains a recognizable brand/product-line keyword."""
    tokens = set(re.findall(r"[a-z0-9]+", product.lower()))
    return bool(tokens & BRAND_TOKENS)


def build_price_tiers(usable: list[dict]) -> list[dict]:
    """Bucket listings into low/mid/high terciles by price rank (not fixed dollar amounts)."""
    sorted_listings = sorted(usable, key=lambda item: item["price"])
    n = len(sorted_listings)
    b1, b2 = round(n / 3), round(2 * n / 3)
    groups = [sorted_listings[:b1], sorted_listings[b1:b2], sorted_listings[b2:]]
    tiers = []
    for label, group in zip(TIER_LABELS, groups):
        if not group:
            continue
        tiers.append(
            {
                "label": label,
                "low": group[0]["price"],
                "high": group[-1]["price"],
                "examples": [item["name"] for item in group],
            }
        )
    return tiers


def build_disambiguation(
    product: str,
    customer_price: str,
    market_products: list[dict],
    selected_listing_index: Optional[int],
) -> dict:
    """Build the disambiguation object: confirmed/estimated/ambiguous/inconclusive verdict."""
    usable: list[dict] = []
    for item in relevant_market_products(product, market_products):
        name = item.get("title") or item.get("name") or "Unknown"
        source = item.get("store") or item.get("retailer") or item.get("brand") or "Unknown source"
        price = parse_price(item.get("price") or item.get("current_price"))
        if price is not None:
            usable.append({"name": name, "price": round(price, 2), "source": source})
    for i, listing in enumerate(usable):
        listing["index"] = i

    customer_value = parse_price(customer_price)

    if not usable:
        return {
            "status": "inconclusive",
            "confidence": "Inconclusive",
            "matched_listing": None,
            "candidates": [],
            "verdict_text": (
                f"We couldn't find any usable market listings for '{product}', so we can't verify this price."
            ),
        }

    def verdict_text_for(matched: dict) -> str:
        if customer_value is None:
            return (
                f"We found a matching listing for '{product}' at ${matched['price']:.2f}, "
                "but couldn't read a valid customer price to compare."
            )
        delta = round(customer_value - matched["price"], 2)
        if abs(delta) < 0.01:
            return f"Your price of ${customer_value:.2f} matches {matched['name']} ({matched['source']}) exactly."
        direction = "higher" if delta > 0 else "lower"
        return (
            f"Your price of ${customer_value:.2f} is ${abs(delta):.2f} {direction} than "
            f"{matched['name']} ({matched['source']}) at ${matched['price']:.2f}."
        )

    if selected_listing_index is not None and 0 <= selected_listing_index < len(usable):
        matched = usable[selected_listing_index]
        return {
            "status": "confirmed",
            "confidence": "Confirmed",
            "matched_listing": matched,
            "candidates": [],
            "verdict_text": verdict_text_for(matched),
        }

    within_window = (
        [u for u in usable if abs(u["price"] - customer_value) <= PRICE_PROXIMITY_WINDOW]
        if customer_value is not None
        else []
    )

    if len(within_window) == 1:
        matched = within_window[0]
        return {
            "status": "confirmed",
            "confidence": "Confirmed",
            "matched_listing": matched,
            "candidates": [],
            "verdict_text": verdict_text_for(matched),
        }

    prices = [u["price"] for u in usable]
    wide_spread = (
        len(usable) >= 3 and min(prices) > 0 and (max(prices) / min(prices)) > TIER_PRICE_RATIO_THRESHOLD
    )

    if not has_brand_token(product) and wide_spread:
        return {
            "status": "tier_ambiguous",
            "confidence": "Estimated",
            "matched_listing": None,
            "candidates": usable,
            "tiers": build_price_tiers(usable),
            "verdict_text": (
                f"'{product}' doesn't name a specific brand or model, and prices for it range widely — "
                "pick the tier (or exact listing) that matches what you have so we can confirm the price."
            ),
        }

    return {
        "status": "ambiguous",
        "confidence": "Estimated",
        "matched_listing": None,
        "candidates": usable,
        "verdict_text": (
            f"We found multiple possible listings for '{product}' — pick the one that matches "
            "what you have so we can confirm the price."
        ),
    }


async def fetch_market_prices(keyword: str, zipcode: str, count: int = 5) -> list[dict]:
    """Fetch product listings from the Parse Bot scraper API."""
    if not PARSE_BOT_API_KEY:
        raise HTTPException(status_code=500, detail="PARSE_BOT_API_KEY is not configured.")
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
    selected_listing_index: Optional[int] = None


def build_researcher_output(payload: PriceRequest, market_products: list[dict]) -> dict:
    """Return the evidence that is handed from the researcher to the designer."""
    listings = [
        {
            "name": item.get("title") or item.get("name") or "Unknown",
            "price": item.get("price") or item.get("current_price"),
            "source": item.get("store") or item.get("retailer") or item.get("brand") or "Unknown source",
        }
        for item in market_products[:5]
    ]
    return {
        "agent": "researcher",
        "title": "Market Researcher",
        "summary": f"Found {len(listings)} market listing(s) for '{payload.product}'.",
        "input": {
            "product": payload.product,
            "customer_price": payload.customer_price,
            "zipcode": payload.zipcode,
        },
        "listings": listings,
    }


def build_solution_designer_output(
    payload: PriceRequest,
    researcher_output: dict,
    verdict_data: dict,
    disambiguation: dict,
) -> dict:
    """Turn researcher evidence into the structured experience data."""
    return {
        "agent": "solution-designer",
        "title": "Solution Designer",
        "summary": verdict_data["verdict"]["explanation"],
        "input": researcher_output,
        "verdict": verdict_data["verdict"],
        "comparison": verdict_data["comparison"],
        "confidence": verdict_data["confidence"],
        "disambiguation": disambiguation,
    }


def build_prototyper_output(payload: PriceRequest, designer_output: dict, market_products: list[dict]) -> dict:
    """Format the designer's decision as the customer-facing assistant response."""
    return {
        "agent": "prototyper",
        "title": "Customer Assistant",
        "summary": build_local_verdict(payload.product, payload.customer_price, market_products),
        "input": designer_output,
    }


def build_communicator_output(
    payload: PriceRequest, designer_output: dict, disambiguation: dict
) -> dict:
    """Translate the verified result into evidence-bound customer messaging."""
    verdict = designer_output["verdict"]
    limitations = [
        "Market listings are keyword matches and are not confirmed identical products.",
        "A human should make the final price-match decision.",
    ]
    if disambiguation.get("status") != "confirmed":
        limitations.insert(0, disambiguation["verdict_text"])
    return {
        "agent": "communicator",
        "title": "Evidence Communicator",
        "summary": f"{verdict['label']}: {verdict['explanation']}",
        "input": designer_output,
        "message": verdict["explanation"],
        "limitations": limitations,
    }


def build_manager_output(
    payload: PriceRequest, designer_output: dict, disambiguation: dict
) -> dict:
    """Provide the final operating recommendation without automating approval."""
    confirmed = disambiguation.get("status") == "confirmed"
    verdict = designer_output.get("verdict", {})
    comparison = designer_output.get("comparison", {})
    confidence = designer_output.get("confidence", {})
    status = disambiguation.get("status", "unknown")

    if confirmed:
        decision = "proceed_with_conditions"
        decision_label = "proceed with conditions"
        summary = (
            "Proceed with conditions: the match is confirmed enough for human review, "
            "but the exact product and customer context still need a final operator check."
        )
        why_now = (
            "The current evidence identifies a single relevant comparable listing that is close enough "
            "to the customer price to merit a human review decision."
        )
        value_created = (
            "This reduces the search space for a human reviewer and turns raw market listings into an "
            "explainable price comparison."
        )
        evidence_basis = (
            "A single matched listing was identified, the customer price was compared against the market "
            "range and average, and the confidence level was explicit about the remaining ambiguity."
        )
        critical_condition = "No automated approval: a human must confirm the exact product match before any final price decision."
        pilot_readiness = "Ready for a limited human-review pilot if the exact-match workflow is documented and staffed."
        launch_readiness = "Not ready for broad launch without operator training and a product-match confirmation step."
    else:
        decision = "hold_for_validation"
        decision_label = "hold for validation"
        summary = (
            "Hold the price-match decision until the product or tier is confirmed. The current market "
            "evidence is not specific enough for a trustworthy approval step."
        )
        why_now = (
            "The product match is ambiguous or the evidence set is too weak to support a defensible price "
            "comparison without additional confirmation."
        )
        value_created = (
            "The prototype still provides a clear decision boundary: it stops when evidence is weak and "
            "prevents overconfident automation."
        )
        evidence_basis = (
            "The current output shows an ambiguous or insufficient match, which means the customer price cannot "
            "be responsibly compared to a single product listing."
        )
        critical_condition = "The workflow must wait for an exact product match or a human-selected listing before it can be trusted."
        pilot_readiness = "Not yet ready for pilot use in a decision-support role without a confirmed matching step."
        launch_readiness = "Not ready for launch; the app should remain in validation until the matching quality is materially improved."

    operational_plan = [
        {
            "priority": 1,
            "action": "Confirm the exact product match workflow before any customer-facing price decision.",
            "owner_role": "Product + operator lead",
            "dependency": "Research and disambiguation results",
            "completion_signal": "One explicit product-match confirmation flow is documented and tested for the top failure modes.",
            "intended_decision": "Proceed or hold based on the confirmed match quality.",
        },
        {
            "priority": 2,
            "action": "Tighten the trust model by surfacing market-range, source quality, and uncertainty in every result.",
            "owner_role": "Engineering",
            "dependency": "Verified listing data and UI contract",
            "completion_signal": "The result screen shows evidence, confidence, and limitations for every verdict without hiding ambiguity.",
            "intended_decision": "Improve confidence before pilot scaling.",
        },
        {
            "priority": 3,
            "action": "Run a small pilot with human review on a limited set of product searches and track result quality.",
            "owner_role": "Customer operations",
            "dependency": "Confirmed product-match workflow",
            "completion_signal": "Pilot logs show operator override rate and false-positive/false-negative review outcomes for a defined sample.",
            "intended_decision": "Validate whether the tool materially reduces decision time without raising trust risk.",
        },
    ]

    return {
        "agent": "manager",
        "title": "Manager Oversight",
        "summary": summary,
        "input": designer_output,
        "decision": decision,
        "human_review_required": True,
        "reason": disambiguation.get("verdict_text", "No verified match was established."),
        "executive_summary": {
            "Decision": decision_label,
            "Why now": why_now,
            "Value created": value_created,
            "Evidence basis": evidence_basis,
            "Critical condition or constraint": critical_condition,
        },
        "alignment_review": {
            "Customer problem and target user": (
                "The intended user is a customer or operator who needs a quick, evidence-based answer on whether a price is competitive or requires a human decision."
            ),
            "Research-to-design fit": (
                "The research is clear enough to support a comparison flow, but it only supports human review when the product match is not exact."
            ),
            "Design-to-build fit": (
                "The prototype implements a defensible comparison and disambiguation flow that reflects the evidence rather than overclaiming certainty."
            ),
            "Build-to-message fit": (
                "The app's messaging should emphasize evidence and human review, not automated approval or guaranteed savings."
            ),
            "Contradictions or gaps": (
                "The core risk is that a generic product name can still produce weak or ambiguous matches; the message must not imply exact product identity when only a keyword match is available."
            ),
        },
        "delivery_and_readiness": {
            "Shipped and verified": (
                "The app can fetch listings, normalize prices, compare them to the customer price, and surface disambiguation or ambiguity states."
            ),
            "Deferred or unverified": (
                "The product does not yet support broad trust claims, retailer integrations, or autonomous pricing decisions."
            ),
            "Pilot readiness": pilot_readiness,
            "Launch readiness": launch_readiness,
            "Human decisions required": (
                "A human must confirm the exact product and approve any final price-match recommendation when there is not a single high-confidence comparable listing."
            ),
        },
        "risks_and_safeguards": {
            "Highest-priority risks": [
                "Keyword match ambiguity can produce false confidence when the product is not uniquely identified.",
                "Price normalization may hide shipping, taxes, or promotions that change the true comparable value.",
                "Any launch message that implies automation or guaranteed savings would overstate the product's evidence."
            ],
            "Trust and compliance safeguards": [
                "Keep the default posture as human decision support rather than automated approval.",
                "Demonstrate the evidence, not just the verdict, and expose match quality in the UI and messages.",
                "Treat product match uncertainty as a blocking condition for any broader launch claim."
            ],
            "Escalation triggers": [
                "A product match remains ambiguous after the user selects a candidate listing.",
                "The market data source becomes stale, incomplete, or inconsistent across listings.",
                "The customer price falls outside the supported market comparison range or the product is not a standard retail item."
            ],
        },
        "operational_plan": operational_plan,
        "measurement_and_cadence": {
            "Core metrics": [
                "rate of confirmed product matches",
                "human override rate",
                "share of searches with incomplete or ambiguous evidence",
                "average time to operator decision"
            ],
            "Review cadence": "Weekly review of match quality, operator overrides, and data quality flags during pilot validation.",
            "Decision gates": [
                "Only proceed to a wider pilot when the exact-match flow is stable and ambiguity is below an agreed threshold.",
                "Hold the launch if the error rate or evidence gaps increase relative to the pilot baseline."
            ],
        },
        "leadership_recommendation": {
            "Recommended next move": (
                "Run a small human-review pilot with the confirmed-match path and track the rate of ambiguity, override, and acceptability before scaling."
            ),
            "Smallest validating experiment": (
                "Test a handful of searches across common product names, then review whether operators can reliably confirm the exact match and price comparison from the current evidence."
            ),
            "What would change this recommendation": (
                "This recommendation changes only if product matching becomes consistently exact, the quality of listings improves materially, and a defined operator process proves the solution reduces decision time without trust erosion."
            ),
        },
    }


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

    verdict_data = build_verdict_data(payload.product, payload.customer_price, market_products)
    disambiguation = build_disambiguation(
        payload.product, payload.customer_price, market_products, payload.selected_listing_index
    )
    if disambiguation.get("status") == "tier_ambiguous":
        verdict_data["limitations"] = [
            *verdict_data["limitations"],
            "Tier was picked by category price range, not by exact brand/model match.",
        ]

    reply = build_local_verdict(payload.product, payload.customer_price, market_products)
    return {
        "reply": reply,
        "mode": "local",
        "market_products": market_products,
        **verdict_data,
        "disambiguation": disambiguation,
    }


async def pipeline_events(payload: PriceRequest):
    """Yield each agent result in order so the UI can render the handoffs live."""
    try:
        market_products = await fetch_market_prices(payload.product.strip(), payload.zipcode)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Price scraper error: {exc.response.status_code}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch market prices: {exc}") from exc

    researcher_output = build_researcher_output(payload, market_products)
    yield {"type": "agent", "stage": researcher_output}

    verdict_data = build_verdict_data(payload.product, payload.customer_price, market_products)
    disambiguation = build_disambiguation(
        payload.product, payload.customer_price, market_products, payload.selected_listing_index
    )
    if disambiguation.get("status") == "tier_ambiguous":
        verdict_data["limitations"] = [
            *verdict_data["limitations"],
            "Tier was picked by category price range, not by exact brand/model match.",
        ]
    designer_output = build_solution_designer_output(
        payload, researcher_output, verdict_data, disambiguation
    )
    yield {"type": "agent", "stage": designer_output}

    prototyper_output = build_prototyper_output(payload, designer_output, market_products)
    yield {"type": "agent", "stage": prototyper_output}
    communicator_output = build_communicator_output(payload, designer_output, disambiguation)
    yield {"type": "agent", "stage": communicator_output}
    manager_output = build_manager_output(payload, designer_output, disambiguation)
    yield {"type": "agent", "stage": manager_output}
    yield {
        "type": "complete",
        "result": {
            "reply": prototyper_output["summary"],
            "mode": "pipeline",
            "market_products": market_products,
            **verdict_data,
            "disambiguation": disambiguation,
        },
    }


@app.post("/api/verify-price/stream")
async def verify_price_stream(payload: PriceRequest):
    if not payload.product.strip():
        raise HTTPException(status_code=400, detail="Product name is required.")
    if not payload.customer_price.strip():
        raise HTTPException(status_code=400, detail="Customer price is required.")

    async def stream():
        try:
            async for event in pipeline_events(payload):
                yield json.dumps(event) + "\n"
        except HTTPException as exc:
            yield json.dumps({"type": "error", "message": exc.detail}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")
