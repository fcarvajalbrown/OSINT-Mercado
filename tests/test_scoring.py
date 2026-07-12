import datetime as dt

import pytest

from osint_mercado import scoring
from osint_mercado.baseline import Baseline
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
