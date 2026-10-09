import json

from osint_mercado import leads

ANOMALY = {
    "id": "a1", "comuna": "Buin", "product": "Pendrive 16GB", "quantity": 12.0,
    "unit_price_clp_gross": 9282.0, "oc_id": "1-1", "correlativo": 8, "oc_url": "http://x/1",
    "captured_at": "2026-07-13T18:33:03+00:00", "overprice_ratio": 2.76, "severity": "high",
    "reference_price_clp": 3368.0, "baseline_confidence": "medium", "normalized_unit_price_clp": 9282.0,
    "matched_rule": "kw", "unit_divisor": 1, "unit_price": 7800.0, "moneda": "CLP", "status": "pending",
    "sku_id": "pendrive_usb_16gb",
}
CM = {
    "id": "c1", "comuna": "317", "oc_text": "Corchetera 30 hojas", "unit_price_clp_net": 8275.0,
    "oc_id": "2-2", "correlativo": 5, "oc_url": "http://x/2", "captured_at": "2026-07-13T18:53:58+00:00",
    "ratio": 7.2, "severity": "severe", "cm_reference_per_unit": 1149.0, "cm_sample_producto": "x",
    "clean": True, "clean_reason": "", "cm_region": "RM", "dimension": "hojas", "n_refs": 66,
    "oc_per_unit": 8275.0, "product_code": 44121615, "status": "pending",
}
PEER = {
    "id": "p1", "comuna": "", "product": "Nueces 1kg", "quantity": 3.0, "unit_price_clp_gross": 23664.0,
    "oc_id": "3-3", "correlativo": 40, "oc_url": "http://x/3", "captured_at": "2026-07-13T18:33:03+00:00",
    "overprice_ratio": 3.46, "severity": "high", "peer_median_clp": 6800.0, "mad_clp": 900.0,
    "robust_z": 5.1, "n_peers": 19, "moneda": "CLP", "product_code": 50101716, "status": "pending",
    "unit_price": 19886.0,
}
ESTIMATE_KEYS = {
    "overprice_ratio", "ratio", "severity", "reference_price_clp", "cm_reference_per_unit",
    "peer_median_clp", "mad_clp", "robust_z", "overprice_pct", "baseline_confidence",
    "cm_sample_producto", "n_refs", "n_peers", "normalized_unit_price_clp", "clean_reason",
}


def build(decisions=None, confirmed=()):
    queues = {"anomalias": [ANOMALY], "convenio_marco": [CM], "precio_pares": [PEER]}
    return leads.public_leads(queues, decisions or {}, set(confirmed))


def test_unreviewed_rows_carry_order_data_and_no_estimate():
    rows = {r["id"]: r for r in build()}
    assert set(rows) == {"a1", "c1", "p1"}
    for row in rows.values():
        assert not ESTIMATE_KEYS & set(row)
        assert row["status"] == "en_revision"
        assert "ratio" not in json.dumps(row)
    a = rows["a1"]
    assert (a["engine"], a["product"], a["quantity"], a["price_paid_clp"], a["price_basis"]) == (
        "anomalias", "Pendrive 16GB", 12.0, 9282.0, "bruto")
    assert (a["oc_id"], a["correlativo"], a["oc_url"]) == ("1-1", 8, "http://x/1")


def test_convenio_marco_rows_state_net_price_and_use_order_text():
    row = next(r for r in build() if r["id"] == "c1")
    assert (row["product"], row["price_paid_clp"], row["price_basis"], row["quantity"]) == (
        "Corchetera 30 hojas", 8275.0, "neto", None)


def test_unusable_comuna_is_published_as_unidentified():
    rows = {r["id"]: r for r in build()}
    assert rows["c1"]["comuna"] == leads.UNKNOWN_COMUNA
    assert rows["p1"]["comuna"] == leads.UNKNOWN_COMUNA
    assert rows["a1"]["comuna"] == "Buin"


def test_dismissed_lead_keeps_order_data_and_shows_reason():
    decisions = {"a1": {"decision": "dismiss", "note": "Pack ambiguo", "reviewed_at": "2026-07-14"}}
    row = next(r for r in build(decisions) if r["id"] == "a1")
    assert row["status"] == "descartado"
    assert row["review_note"] == "Pack ambiguo"
    assert row["reviewed_at"] == "2026-07-14"
    assert not ESTIMATE_KEYS & set(row)


def test_confirmed_leads_are_left_to_the_published_flags():
    ids = {r["id"] for r in build(confirmed={"a1"})}
    assert ids == {"c1", "p1"}


def test_rows_are_in_a_stable_order():
    assert [r["id"] for r in build()] == [r["id"] for r in build()]


def test_automatic_estimate_is_attached_to_open_leads_only():
    queues = {"anomalias": [ANOMALY], "convenio_marco": [CM], "precio_pares": [PEER]}
    auto = {("1-1", 8): {"reference_clp": 3000.0, "level": "sobreprecio"},
            ("2-2", 5): {"reference_clp": 1000.0, "level": "alto"}}
    decisions = {"c1": {"decision": "dismiss", "note": "CM", "reviewed_at": "2026-10-09"}}
    rows = {r["id"]: r for r in leads.public_leads(queues, decisions, set(), auto)}
    assert rows["a1"]["auto_estimate"]["level"] == "sobreprecio"
    assert "auto_estimate" not in rows["c1"]
    assert "auto_estimate" not in rows["p1"]
    assert not ESTIMATE_KEYS & set(rows["a1"])
