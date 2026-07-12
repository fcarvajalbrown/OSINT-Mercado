import json
from datetime import date

from osint_mercado.build_baselines import build, write_baselines


def _write(path, rows):
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_build_computes_one_baseline_row_per_sku(tmp_path):
    basket_path = tmp_path / "basket.json"
    seed_path = tmp_path / "seed_prices.json"
    _write(basket_path, [
        {"sku_id": "sku_a", "canonical_name": "SKU A", "keywords": ["a"], "unit": "unidad"},
        {"sku_id": "sku_b", "canonical_name": "SKU B", "keywords": ["b"], "unit": "unidad"},
    ])
    _write(seed_path, [
        {"sku_id": "sku_a", "retailer": "R1", "price_clp": 1000.0,
         "observed_at": "2026-07-01", "url": "https://example.cl/a"},
        {"sku_id": "sku_a", "retailer": "R2", "price_clp": 1100.0,
         "observed_at": "2026-07-05", "url": "https://example.cl/a2"},
    ])

    rows = build(basket_path, seed_path, date(2026, 7, 12))

    assert len(rows) == 2
    row_a = next(r for r in rows if r["sku_id"] == "sku_a")
    row_b = next(r for r in rows if r["sku_id"] == "sku_b")
    assert row_a["reference_price_clp"] == 1050.0
    assert row_a["confidence"] == "high"
    assert row_b["confidence"] == "insufficient"
    assert row_b["n_observations"] == 0


def test_write_baselines_roundtrip(tmp_path):
    out = tmp_path / "baselines.json"
    write_baselines([{"sku_id": "sku_a", "reference_price_clp": 1050.0}], out)

    assert out.exists()
    assert json.loads(out.read_text(encoding="utf-8")) == [
        {"sku_id": "sku_a", "reference_price_clp": 1050.0}
    ]
