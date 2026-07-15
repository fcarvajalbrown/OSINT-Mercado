import json

import polars as pl

from osint_mercado import cm_score


def _oc_parquet(tmp_path):
    rows = [
        # café: 170 g at $13,600 net vs CM 50 g at $2,000 -> $80/g vs $40/g -> 2.0x
        {"oc_id": "700-1-SE26", "correlativo": 3, "comuna": "Buin",
         "product": "Cafe", "espec_comprador": "CAFE INSTANTANEO GOLD TARRO 170 G",
         "espec_proveedor": "", "unit_price": 13600.0, "moneda": "CLP",
         "product_code": 50201709, "fecha": "2026-07-10", "captured_at": "2026-07-10T00:00:00Z",
         "oc_url": "https://mp/700-1-SE26"},
        # a code with no CM coverage -> skipped
        {"oc_id": "701-1-SE26", "correlativo": 1, "comuna": "Maipu",
         "product": "Cosa", "espec_comprador": "PRODUCTO SIN CONVENIO 1 UNIDAD",
         "espec_proveedor": "", "unit_price": 9999.0, "moneda": "CLP",
         "product_code": 99999999, "fecha": "2026-07-10", "captured_at": "2026-07-10T00:00:00Z",
         "oc_url": "https://mp/701-1-SE26"},
    ]
    p = tmp_path / "oc_items.parquet"
    pl.DataFrame(rows).write_parquet(p)
    return p


def _cm_parquet(tmp_path):
    rows = [
        {"code": "50201709", "region": "METROPOLITANA", "producto": "CAFE INSTANTANEO GOLD",
         "marca": "NESCAFE", "modelo": "TARRO", "medida": "50 G", "proveedor": "P",
         "rut": "1-9", "precio_neto": 2000.0}
        for _ in range(3)
    ]
    p = tmp_path / "cm_catalog.parquet"
    pl.DataFrame(rows).write_parquet(p)
    return p


def test_run_emits_cm_lead_with_evidence(tmp_path):
    items = _oc_parquet(tmp_path)
    cat = _cm_parquet(tmp_path)
    out = tmp_path / "cm_pending.json"
    fxc = tmp_path / "fx_rates.json"
    _, report = cm_score.run(items, cat, fxc, out, session=None)

    rows = json.loads(out.read_text(encoding="utf-8"))
    assert len(rows) == 1
    lead = rows[0]
    assert lead["oc_id"] == "700-1-SE26"
    assert lead["product_code"] == "50201709"
    assert lead["ratio"] == 2.0
    assert lead["severity"] == "high"
    assert lead["dimension"] == "g"
    assert lead["cm_reference_per_unit"] == 40.0
    assert lead["oc_url"] == "https://mp/700-1-SE26"
    assert lead["clean"] is True
    assert report["leads"] == 1
    assert report["under_cm_code"] == 1  # only the café line shares a CM code


def test_run_skips_unconvertible_currency_line(tmp_path):
    # A line under a CM code but in a currency we cannot convert must be skipped
    # (counted), not crash the whole batch.
    items = tmp_path / "oc_items.parquet"
    pl.DataFrame([{
        "oc_id": "702-1-SE26", "correlativo": 1, "comuna": "Buin", "product": "Cafe",
        "espec_comprador": "CAFE INSTANTANEO GOLD TARRO 170 G", "espec_proveedor": "",
        "unit_price": 100.0, "moneda": "XYZ", "product_code": 50201709,
        "fecha": "2026-07-10", "captured_at": "2026-07-10T00:00:00Z",
        "oc_url": "https://mp/702-1-SE26"},
    ]).write_parquet(items)
    cat = _cm_parquet(tmp_path)
    out = tmp_path / "cm_pending.json"
    fxc = tmp_path / "fx_rates.json"
    _, report = cm_score.run(items, cat, fxc, out, session=None)
    assert report["leads"] == 0
    assert report["fx_skipped"] == 1
    assert json.loads(out.read_text(encoding="utf-8")) == []


def test_run_is_deterministic(tmp_path):
    items = _oc_parquet(tmp_path)
    cat = _cm_parquet(tmp_path)
    out = tmp_path / "cm_pending.json"
    fxc = tmp_path / "fx_rates.json"
    cm_score.run(items, cat, fxc, out, session=None)
    first = out.read_bytes()
    cm_score.run(items, cat, fxc, out, session=None)
    assert out.read_bytes() == first
