from app import build_disambiguation, relevant_market_products

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
