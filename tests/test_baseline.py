from datetime import date

from osint_mercado.basket import PriceObservation
from osint_mercado.baseline import compute_reference


def _obs(price, observed_at, retailer="Retailer"):
    return PriceObservation(
        sku_id="sku1", retailer=retailer, price_clp=price,
        observed_at=observed_at, url="https://example.cl",
    )


def test_no_observations_is_insufficient():
    baseline = compute_reference("sku1", [], date(2026, 7, 12))
    assert baseline.confidence == "insufficient"
    assert baseline.reference_price_clp == 0.0
    assert baseline.n_observations == 0
    assert baseline.spread_ratio == 0.0


def test_two_close_recent_observations_is_high_confidence():
    obs = [_obs(10000, "2026-07-01"), _obs(11000, "2026-06-15")]
    baseline = compute_reference("sku1", obs, date(2026, 7, 12))
    assert baseline.confidence == "high"
    assert baseline.reference_price_clp == 10500.0
    assert baseline.n_observations == 2
    assert baseline.freshest_observed_at == "2026-07-01"


def test_single_recent_observation_is_medium_confidence():
    obs = [_obs(10000, "2026-07-01")]
    baseline = compute_reference("sku1", obs, date(2026, 7, 12))
    assert baseline.confidence == "medium"
    assert baseline.spread_ratio == 0.0


def test_wide_spread_two_observations_is_medium_confidence():
    obs = [_obs(10000, "2026-07-01"), _obs(20000, "2026-06-15")]
    baseline = compute_reference("sku1", obs, date(2026, 7, 12))
    assert baseline.confidence == "medium"
    assert baseline.spread_ratio > 0.25


def test_all_stale_observations_is_insufficient():
    obs = [_obs(10000, "2025-01-01"), _obs(11000, "2025-02-01")]
    baseline = compute_reference("sku1", obs, date(2026, 7, 12))
    assert baseline.confidence == "insufficient"


def test_median_of_three_observations():
    obs = [_obs(9000, "2026-07-01"), _obs(10000, "2026-07-02"), _obs(20000, "2026-07-03")]
    baseline = compute_reference("sku1", obs, date(2026, 7, 12))
    assert baseline.reference_price_clp == 10000.0
