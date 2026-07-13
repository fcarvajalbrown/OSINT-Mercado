from osint_mercado import catalog


def test_every_product_code_becomes_a_sku_automatically():
    rows = [
        {"product_code": "44103103", "product": "Toner", "unidad": "un", "comuna": "A", "fecha": "2026-07-02"},
        {"product_code": "44103103", "product": "Toner HP", "unidad": "un", "comuna": "B", "fecha": "2026-07-01"},
        {"product_code": "56101504", "product": "Sillas", "unidad": "un", "comuna": "A", "fecha": "2026-07-03"},
    ]
    cat = catalog.build_catalog(rows)
    assert set(cat) == {"44103103", "56101504"}
    e = cat["44103103"]
    assert e.n_orders == 2
    assert e.n_communes == 2
    assert e.name == "Toner"          # most common name for the code
    assert e.first_seen == "2026-07-01"


def test_codeless_line_still_gets_a_sku_by_name():
    rows = [{"product_code": "0", "product": "Cosa Rara", "unidad": "", "comuna": "A", "fecha": "2026-07-01"}]
    cat = catalog.build_catalog(rows)
    assert len(cat) == 1
    (key,) = cat
    assert key.startswith("name:")
    assert cat[key].name == "Cosa Rara"


def test_merge_grows_catalog_and_never_shrinks():
    day1 = catalog.build_catalog(
        [{"product_code": "101", "product": "A", "unidad": "", "comuna": "X", "fecha": "2026-07-01"}]
    )
    day2 = catalog.build_catalog(
        [{"product_code": "202", "product": "B", "unidad": "", "comuna": "Y", "fecha": "2026-07-02"}]
    )
    merged = catalog.merge(day1, day2)
    assert set(merged) == {"101", "202"}
