from app import tools


def setup_function():
    tools.LEADS.clear()


def test_search_finds_in_stock_and_out_of_stock_products_with_flag():
    names = {p["name"]: p for p in tools.search_products("running shoe")["products"]}
    assert names["Road Racer Shoe"]["in_stock"] is False
    assert names["Trail Runner Shoe"]["in_stock"] is True


def test_search_respects_max_price():
    results = tools.search_products("jacket", max_price=100)["products"]
    assert all(p["price"] <= 100 for p in results)


def test_recommend_skips_out_of_stock_items():
    picks = tools.recommend_products(category="accessories")["products"]
    assert all(p["in_stock"] for p in picks)
    assert "Merino Wool Beanie" not in [p["name"] for p in picks]


def test_order_status_returned_when_order_and_email_match():
    result = tools.get_order_status("nw-1001", "Amara.Test@example.com")
    assert result["verified"] is True
    assert result["status"] == "shipped"


def test_order_status_hidden_when_email_does_not_match():
    result = tools.get_order_status("NW-1001", "someone.else@example.com")
    assert result["verified"] is False
    assert "status" not in result


def test_order_status_hidden_for_unknown_order():
    result = tools.get_order_status("NW-9999", "amara.test@example.com")
    assert result["verified"] is False


def test_promotions_exclude_expired_offers():
    codes = [p["code"] for p in tools.get_promotions(today="2026-11-09")["promotions"]]
    assert "WINTER15" in codes
    assert "OCT10" not in codes


def test_lead_not_saved_without_consent():
    result = tools.save_lead("Ana", "ana@example.com", "running shoes", consent=False)
    assert result["saved"] is False
    assert tools.LEADS == []


def test_lead_saved_with_consent_and_normalized():
    result = tools.save_lead("Ana", "Ana@Example.com ", "running shoes", consent=True)
    assert result["saved"] is True
    assert tools.LEADS == [{"name": "Ana", "email": "ana@example.com", "interest": "running shoes"}]


def test_lead_rejects_invalid_email():
    result = tools.save_lead("Ana", "not-an-email", "running shoes", consent=True)
    assert result["saved"] is False
    assert tools.LEADS == []
