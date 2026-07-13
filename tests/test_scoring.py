import datetime as dt

import pytest

from osint_mercado import scoring
from osint_mercado.baseline import Baseline
from osint_mercado.basket import Sku
from osint_mercado.matcher import MatchResult

D = dt.date(2026, 7, 9)


def _bl(price, conf="high"):
    return Baseline("mouse_usb", price, conf, 2, "2026-07-12", 0.1)


def _score(*, unit_price=10000.0, moneda="CLP", porcentaje_iva=19.0,
           baseline=None, fx_cache=None, rule="keyword"):
    m = MatchResult("mouse_usb", rule, 100.0)
    return scoring.score_line_item(
        oc_id="1-1-SE26", correlativo=1, comuna="Nunoa", producto="Mouse",
        quantity=1.0, moneda=moneda, unit_price=unit_price,
        porcentaje_iva=porcentaje_iva, on_date=D, oc_url="http://x/1",
        captured_at="2026-07-12T00:00:00Z", match=m, baseline=baseline,
        fx_cache=({} if fx_cache is None else fx_cache), session=None,
    )


def test_gross_up():
    assert scoring.gross_up(100.0, 19.0) == 119.0
    assert scoring.gross_up(100.0, 0.0) == 100.0


def test_severity_boundaries():
    assert scoring.severity(1.49) is None
    assert scoring.severity(1.5) == "watch"
    assert scoring.severity(1.99) == "watch"
    assert scoring.severity(2.0) == "high"
    assert scoring.severity(2.99) == "high"
    assert scoring.severity(3.0) == "severe"


def test_make_anomaly_id_stable_and_distinct():
    a = scoring.make_anomaly_id("1-1-SE26", 1, "mouse_usb")
    b = scoring.make_anomaly_id("1-1-SE26", 1, "mouse_usb")
    c = scoring.make_anomaly_id("1-1-SE26", 2, "mouse_usb")
    assert a == b
    assert a != c


def test_pending_flag_for_overpriced_clp_line():
    a = _score(unit_price=10000.0, baseline=_bl(3651.0))
    assert a.status == "pending"
    assert a.severity == "severe"
    assert a.unit_price_clp_gross == 11900.0
    assert a.overprice_ratio > 3
    assert a.matched_rule == "keyword"
    assert a.oc_url == "http://x/1"
    assert a.id == scoring.make_anomaly_id("1-1-SE26", 1, "mouse_usb")


def test_below_threshold_returns_none():
    assert _score(unit_price=10000.0, baseline=_bl(10000.0)) is None


def test_insufficient_baseline_marks_needs_baseline():
    a = _score(unit_price=10000.0, baseline=_bl(3651.0, "insufficient"))
    assert a.status == "needs_baseline"
    assert a.severity is None
    assert a.overprice_ratio is None


def test_missing_baseline_marks_needs_baseline():
    a = _score(unit_price=10000.0, baseline=None)
    assert a.status == "needs_baseline"
    assert a.baseline_confidence == "insufficient"


def test_extreme_ratio_marks_unit_ambiguous():
    a = _score(unit_price=10000.0, baseline=_bl(100.0))
    assert a.status == "unit_ambiguous"
    assert a.severity is None
    assert a.overprice_ratio is not None


def test_tiny_ratio_marks_unit_ambiguous():
    a = _score(unit_price=10000.0, baseline=_bl(1_000_000.0))
    assert a.status == "unit_ambiguous"


def test_non_clp_line_converts_via_fx_cache():
    a = _score(unit_price=100.0, moneda="USD", baseline=_bl(20000.0),
               fx_cache={"dolar:2026-07-09": 950.0})
    assert a.status == "pending"
    assert a.unit_price_clp_gross == pytest.approx(113050.0)
    assert a.severity == "severe"


# ---- unit normalization (pack count / size) --------------------------------

def _score_norm(*, unit_price, baseline, spec_text, sku, porcentaje_iva=0.0):
    m = MatchResult(sku.sku_id, "keyword", 100.0)
    return scoring.score_line_item(
        oc_id="1-1-SE26", correlativo=1, comuna="Nunoa", producto="x",
        quantity=1.0, moneda="CLP", unit_price=unit_price,
        porcentaje_iva=porcentaje_iva, on_date=D, oc_url="http://x/1",
        captured_at="2026-07-12T00:00:00Z", match=m,
        baseline=Baseline(sku.sku_id, baseline, "high", 2, "2026-07-12", 0.1),
        fx_cache={}, session=None, spec_text=spec_text, sku=sku,
    )


def test_pack_of_four_is_divided_before_scoring():
    # A pack of 4 markers at $2963 is ~$741/unit vs a $717 baseline: not an
    # overprice once normalized. Raw ratio would have been ~4x (a false flag).
    sku = Sku("destacador_fluor", "Destacador", ["destacador"], base_count=1)
    a = _score_norm(unit_price=2963.0, baseline=717.0,
                    spec_text="PACK DE 4 UNIDADES DESTACADORES", sku=sku)
    assert a is None or a.severity is None
    if a is not None:
        assert a.unit_divisor == 4.0
        assert a.normalized_unit_price_clp == pytest.approx(740.75)


def test_bigger_box_relative_to_baseline_count():
    # Baseline is a box of 5000 corchetes; a 1000-count box priced at $191 is
    # ~$958 per 5000, in line with the $840 baseline, not a 0.2x "bargain".
    sku = Sku("corchetes_caja", "Corchetes", ["corchetes"], base_count=5000)
    a = _score_norm(unit_price=191.59, baseline=840.5,
                    spec_text="CORCHETE 26/6 1000 UNIDADES", sku=sku)
    assert a is None  # normalized ratio ~1.14, below the Watch threshold


def test_size_based_longer_tape_normalized_per_metre():
    # A 200 m roll at $2975 vs a 40 m baseline: per-metre it is cheaper, so the
    # raw 3.5x flag must dissolve after size normalization.
    sku = Sku("cinta_embalaje", "Cinta", ["cinta embalaje"], base_size=40.0, base_dim="m")
    a = _score_norm(unit_price=2975.0, baseline=837.5,
                    spec_text="CINTA DE EMBALAJE ROLLO 5 CM X 200 MTS", sku=sku)
    assert a is None
    # 2975 / (200/40) = 595 per 40 m vs 837 baseline -> ratio < 1


def test_small_format_scaled_up_routes_to_review_not_flag():
    # A 75 ml sachet is dearer per litre than a 1 L bottle; scaling it up must not
    # manufacture an overprice flag. It routes to unit_ambiguous for human review.
    sku = Sku("alcohol_gel_1l", "Alcohol gel", ["alcohol gel"], base_size=1000.0, base_dim="ml")
    a = _score_norm(unit_price=1047.0, baseline=5790.0,
                    spec_text="ALCOHOL GEL SIMONDS 75 ML", sku=sku)
    assert a.status == "unit_ambiguous"
    assert a.severity is None


def test_real_overprice_survives_normalization():
    # Same unit, genuinely 4x over baseline: normalization must NOT erase it.
    sku = Sku("mouse_usb", "Mouse", ["mouse usb"], base_count=1)
    a = _score_norm(unit_price=16000.0, baseline=4000.0,
                    spec_text="Mouse USB optico", sku=sku)
    assert a.status == "pending"
    assert a.unit_divisor == 1.0
    assert a.severity == "severe"
