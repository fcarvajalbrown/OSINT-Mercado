from osint_mercado import solotodo


def test_offer_prices_extracts_active_offers_only():
    entities = [
        {"active_registry": {"offer_price": "71281.00", "normal_price": "71281.00"}},
        {"active_registry": {"offer_price": None, "normal_price": None}},  # out of stock
        {"active_registry": {"offer_price": "89900"}},
        {"active_registry": {}},
    ]
    assert solotodo.offer_prices(entities) == [71281.0, 89900.0]


def test_name_matches_requires_all_distinctive_tokens():
    assert solotodo.name_matches("HP Toner (Negro) [CF283A]", ["cf283a"])
    assert solotodo.name_matches("HP 83A Negro CF283A", ["hp", "cf283a"])
    # a different toner must NOT match a CF283A anchor
    assert not solotodo.name_matches("HP Toner CE285A", ["cf283a"])
    # empty tokens never match (avoid anchoring to a broad category)
    assert not solotodo.name_matches("Toner generico", [])


def test_retail_stats_is_robust():
    s = solotodo.retail_stats([100.0, 90.0, 110.0])
    assert s["median_clp"] == 100.0
    assert s["min_clp"] == 90.0
    assert s["n_offers"] == 3
    assert solotodo.retail_stats([]) is None
