from datetime import datetime

import polars as pl
import pytest

from osint_mercado import auto_estimate as ae


def test_cgu_worked_example_is_reproduced():
    ref = ae.cgu_reference([10, 12, 13, 15, 16, 18, 20, 50, 90])
    assert ref["kept"] == 7
    assert ref["rule"] == "media"
    assert ref["reference"] == pytest.approx(14.86, abs=0.005)
    assert 100 * ref["cv"] == pytest.approx(21.71, abs=0.005)


def test_dispersed_sample_uses_the_median():
    ref = ae.cgu_reference([10] * 5 + [30] * 5)
    assert ref["cv"] > ae.CV_LIMIT
    assert ref["rule"] == "mediana"
    assert ref["reference"] == 20


def test_levels_follow_the_tukey_fence():
    prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
    q1, q3, fence = ae.tukey_fence(prices)
    assert (q1, q3) == (12.25, 16.75)
    assert fence == pytest.approx(16.75 + 1.5 * 4.5)
    assert ae.level(15, q3, fence) == "normal"
    assert ae.level(17, q3, fence) == "alto"
    assert ae.level(30, q3, fence) == "sobreprecio"
    assert ae.level(fence * 101, q3, fence) == "error_de_datos"


def test_fewer_than_ten_comparables_gives_no_estimate():
    assert ae.estimate_line(100.0, datetime(2026, 9, 1), [10.0] * 9) is None


def _items(rows):
    return pl.DataFrame(rows, schema={
        "oc_id": pl.String, "correlativo": pl.Int64, "fecha": pl.String, "product_code": pl.Int64,
        "unidad": pl.String, "unit_price": pl.Float64, "moneda": pl.String, "region": pl.String,
    }, orient="row")


def test_estimates_use_only_earlier_same_code_same_unit_rm_clp_lines_within_a_year():
    rm = ae.RM_REGION
    rows = [(f"c{i}", 1, f"2026-08-{i + 1:02d}T10:00:00", 111, "Unidad", 100.0 + i, "CLP", rm) for i in range(10)]
    rows += [
        ("late", 1, "2026-09-20T10:00:00", 111, "unidad", 999.0, "CLP", rm),
        ("old", 1, "2024-01-01T10:00:00", 111, "unidad", 1.0, "CLP", rm),
        ("other_code", 1, "2026-08-02T10:00:00", 222, "unidad", 1.0, "CLP", rm),
        ("other_unit", 1, "2026-08-02T10:00:00", 111, "caja", 1.0, "CLP", rm),
        ("usd", 1, "2026-08-02T10:00:00", 111, "unidad", 1.0, "USD", rm),
        ("lead", 7, "2026-09-10T10:00:00", 111, " UNIDAD ", 300.0, "CLP", rm),
    ]
    est = ae.estimates_for(_items(rows), {("lead", 7), ("c0", 1)})
    assert set(est) == {("lead", 7)}
    e = est[("lead", 7)]
    assert e["n_comparables"] == 10
    assert e["reference_clp"] == 104.5
    assert e["reference_rule"] == "media"
    assert e["level"] == "sobreprecio"
    assert e["overprice_pct"] == round(100 * (300 - 104.5) / 104.5, 2)
    assert (e["window_from"], e["window_to"]) == ("2025-09-10", "2026-09-10")
    assert e["method"] == ae.METHOD
