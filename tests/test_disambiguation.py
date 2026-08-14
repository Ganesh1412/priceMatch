from app import build_disambiguation, build_local_verdict, relevant_market_products

AIRPODS_LISTINGS = [
    {"title": "Apple AirPods Max 2 - Midnight", "brand": "Apple", "price": "$449.99"},
    {"title": "Apple AirPods 4 Wireless Earbuds", "brand": "Apple", "price": "$99.99"},
    {"title": "Apple AirPods Pro 3 Wireless Earbuds", "brand": "Apple", "price": "$189.99"},
]

IRRELEVANT_LISTINGS = [
    {"title": "Hello Kitty 25ct Puffy Stickers", "brand": "Hello Kitty", "price": "$2.00"},
    {"title": "Generic Phone Case", "brand": "Acme", "price": "$9.99"},
]


def test_relevant_market_products_filters_unrelated_listings():
    result = relevant_market_products("airpods", AIRPODS_LISTINGS + IRRELEVANT_LISTINGS)
    assert result == AIRPODS_LISTINGS


def test_local_verdict_explains_market_evidence_and_limitations():
    result = build_local_verdict("airpods", "150", AIRPODS_LISTINGS)

    assert "appears below market" in result
    assert "3 available market listing(s)" in result
    assert "range from $99.99 to $449.99" in result
    assert "$50.01 higher" in result
    assert "not an automatic price-match approval" in result


def test_local_verdict_explains_when_a_comparison_cannot_be_made():
    result = build_local_verdict("airpods", "not a price", AIRPODS_LISTINGS)

    assert "could not complete a reliable price comparison" in result
    assert "exact product name or model" in result
    assert "exact product match" in result


def test_inconclusive_when_no_relevant_listings():
    result = build_disambiguation("xyzzynonexistentwidget123", "15", IRRELEVANT_LISTINGS, None)
    assert result["status"] == "inconclusive"
    assert result["confidence"] == "Inconclusive"
    assert result["matched_listing"] is None


def test_confirmed_single_match_within_window():
    result = build_disambiguation("airpods", "150", AIRPODS_LISTINGS, None)
    assert result["status"] == "confirmed"
    assert result["matched_listing"]["price"] == 189.99


def test_ambiguous_when_no_single_window_match():
    result = build_disambiguation("airpods", "145", AIRPODS_LISTINGS, None)
    assert result["status"] == "ambiguous"
    assert len(result["candidates"]) == 3


def test_confirmed_via_selected_listing_index():
    result = build_disambiguation("airpods", "145", AIRPODS_LISTINGS, 1)
    assert result["status"] == "confirmed"
    assert result["matched_listing"]["name"] == "Apple AirPods 4 Wireless Earbuds"


def test_selected_listing_index_out_of_range_falls_back_to_ambiguous():
    result = build_disambiguation("airpods", "145", AIRPODS_LISTINGS, 99)
    assert result["status"] == "ambiguous"


def test_manager_recommends_human_review_for_confirmed_match():
    from app import build_manager_output

    designer_output = {
        "verdict": {"label": "Below market", "explanation": "Customer price is below the market average."},
        "comparison": {"customerPrice": 150.0, "marketAverage": 180.0},
        "confidence": {"level": "moderate"},
    }
    disambiguation = {"status": "confirmed", "verdict_text": "Your price matches the Apple AirPods Pro 3 listing."}

    result = build_manager_output(None, designer_output, disambiguation)
    assert result["decision"] == "proceed_with_conditions"
    assert result["human_review_required"] is True
    assert result["executive_summary"]["Decision"] == "proceed with conditions"


def test_manager_holds_when_match_is_not_confirmed():
    from app import build_manager_output

    designer_output = {
        "verdict": {"label": "Not enough evidence", "explanation": "We found fewer than two comparable listings."},
        "comparison": {"customerPrice": 150.0, "marketAverage": None},
        "confidence": {"level": "low"},
    }
    disambiguation = {"status": "ambiguous", "verdict_text": "We found multiple possible listings for the product."}

    result = build_manager_output(None, designer_output, disambiguation)
    assert result["decision"] == "hold_for_validation"
    assert result["leadership_recommendation"]["Recommended next move"]
    assert "operational_plan" in result
