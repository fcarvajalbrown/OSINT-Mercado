from dataclasses import dataclass
from datetime import date

from osint_mercado.basket import PriceObservation

FRESHNESS_DAYS = 90
SPREAD_HIGH_MAX = 0.25


@dataclass(frozen=True)
class Baseline:
    sku_id: str
    reference_price_clp: float
    confidence: str
    n_observations: int
    freshest_observed_at: str
    spread_ratio: float


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def compute_reference(
    sku_id: str, observations: list[PriceObservation], as_of: date
) -> Baseline:
    if not observations:
        return Baseline(sku_id, 0.0, "insufficient", 0, "", 0.0)

    prices = [o.price_clp for o in observations]
    reference_price = _median(prices)
    freshest = max(observations, key=lambda o: o.observed_at)
    freshest_age_days = (as_of - date.fromisoformat(freshest.observed_at)).days
    spread_ratio = (
        (max(prices) - min(prices)) / reference_price if len(prices) >= 2 else 0.0
    )

    if freshest_age_days > FRESHNESS_DAYS:
        confidence = "insufficient"
    elif len(observations) >= 2 and spread_ratio <= SPREAD_HIGH_MAX:
        confidence = "high"
    else:
        confidence = "medium"

    return Baseline(
        sku_id=sku_id,
        reference_price_clp=reference_price,
        confidence=confidence,
        n_observations=len(observations),
        freshest_observed_at=freshest.observed_at,
        spread_ratio=spread_ratio,
    )
