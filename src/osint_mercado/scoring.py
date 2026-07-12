"""Anomaly scoring core (ADR 0013).

Converts a matched line-item to a CLP-comparable, IVA-aligned overprice ratio
and assigns a severity, with a per-unit plausibility guardrail. Deterministic:
the same inputs always produce the same anomaly (including a stable id), which
the Phase 4 curation gate and re-run reproducibility both rely on.
"""

import hashlib
from dataclasses import dataclass

from osint_mercado import fx
from osint_mercado.baseline import Baseline
from osint_mercado.matcher import MatchResult

# Severity tiers (PRD defaults). Configurable here, in one place.
WATCH = 1.5
HIGH = 2.0
SEVERE = 3.0

# Per-unit plausibility band. A ratio outside this range almost always means the
# order priced a different unit than the baseline (per-item vs per-pack), so it
# is routed to review rather than published as an overprice flag.
RATIO_FLOOR = 0.3
RATIO_CAP = 20.0

# Only score against a baseline the retail engine considers trustworthy.
SCORABLE_CONFIDENCE = {"medium", "high"}


@dataclass(frozen=True)
class Anomaly:
    id: str
    oc_id: str
    correlativo: int
    comuna: str
    sku_id: str
    matched_rule: str
    product: str
    quantity: float
    moneda: str
    unit_price: float
    unit_price_clp_gross: float
    reference_price_clp: float | None
    baseline_confidence: str
    overprice_ratio: float | None
    severity: str | None
    status: str
    oc_url: str
    captured_at: str


def gross_up(net_price: float, porcentaje_iva: float) -> float:
    """Bring a net-of-tax price to gross, to compare against gross retail baselines."""
    return net_price * (1 + porcentaje_iva / 100)


def severity(ratio: float) -> str | None:
    if ratio >= SEVERE:
        return "severe"
    if ratio >= HIGH:
        return "high"
    if ratio >= WATCH:
        return "watch"
    return None


def make_anomaly_id(oc_id: str, correlativo: int, sku_id: str) -> str:
    raw = f"{oc_id}|{correlativo}|{sku_id}".encode()
    return hashlib.sha1(raw).hexdigest()[:16]


def score_line_item(*, oc_id, correlativo, comuna, producto, quantity, moneda,
                    unit_price, porcentaje_iva, on_date, oc_url, captured_at,
                    match: MatchResult, baseline: Baseline | None,
                    fx_cache, session) -> Anomaly | None:
    """Score one matched line-item.

    Returns None when the line is matched, in-band, and below the Watch
    threshold (i.e. not an anomaly). Otherwise returns an Anomaly whose
    `status` is one of: pending, unit_ambiguous, needs_baseline.
    """
    if match.sku_id is None:
        return None

    unit_clp = fx.to_clp(unit_price, moneda, on_date, fx_cache, session)
    gross = round(gross_up(unit_clp, porcentaje_iva), 2)

    def _anomaly(*, reference, confidence, ratio, sev, status):
        return Anomaly(
            id=make_anomaly_id(oc_id, correlativo, match.sku_id),
            oc_id=oc_id, correlativo=correlativo, comuna=comuna,
            sku_id=match.sku_id, matched_rule=match.rule, product=producto,
            quantity=quantity, moneda=moneda, unit_price=unit_price,
            unit_price_clp_gross=gross, reference_price_clp=reference,
            baseline_confidence=confidence, overprice_ratio=ratio,
            severity=sev, status=status, oc_url=oc_url, captured_at=captured_at,
        )

    if baseline is None or baseline.confidence not in SCORABLE_CONFIDENCE:
        return _anomaly(
            reference=(baseline.reference_price_clp if baseline else None),
            confidence=(baseline.confidence if baseline else "insufficient"),
            ratio=None, sev=None, status="needs_baseline",
        )

    ratio = round(gross / baseline.reference_price_clp, 4)

    if ratio < RATIO_FLOOR or ratio > RATIO_CAP:
        return _anomaly(reference=baseline.reference_price_clp,
                        confidence=baseline.confidence, ratio=ratio, sev=None,
                        status="unit_ambiguous")

    sev = severity(ratio)
    if sev is None:
        return None

    return _anomaly(reference=baseline.reference_price_clp,
                    confidence=baseline.confidence, ratio=ratio, sev=sev,
                    status="pending")
