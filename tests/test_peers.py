from osint_mercado import peers


def test_median_and_mad():
    assert peers.median([1, 2, 3, 4, 5]) == 3
    assert peers.median([1, 2, 3, 4]) == 2.5
    # MAD of [1,2,3,4,5] = median(|x-3|) = median([2,1,0,1,2]) = 1
    assert peers.mad([1, 2, 3, 4, 5]) == 1.0


def test_robust_z_scales_by_mad():
    # robust z = 0.6745 * (x - median) / mad
    assert peers.robust_z(10, 4, 2) == 0.6745 * 6 / 2


def test_peer_stat_requires_minimum_peers():
    # Fewer than MIN_PEERS distinct observations -> no stat (can't trust a peer median).
    assert peers.build_peer_stats(
        [("101", "Cemento", 1000.0)] * 3
    ) == {}


def test_peer_stat_computed_for_populated_group():
    rows = [("101", "Cemento", p) for p in [1000, 1050, 980, 1020, 1010, 1000]]
    stats = peers.build_peer_stats(rows)
    assert "101" in stats
    s = stats["101"]
    assert s.n == 6
    assert s.median_clp == 1005.0
    assert s.product_name == "Cemento"


def test_clear_outlier_is_flagged_above_peers():
    rows = [("101", "Cemento", p) for p in [1000, 1050, 980, 1020, 1010, 5000]]
    stats = peers.build_peer_stats(rows)
    hit = peers.classify(5000.0, stats["101"])
    assert hit is not None
    assert hit.ratio > 3
    assert hit.severity == "severe"


def test_in_band_price_not_flagged():
    rows = [("101", "Cemento", p) for p in [1000, 1050, 980, 1020, 1010, 1005]]
    stats = peers.build_peer_stats(rows)
    assert peers.classify(1010.0, stats["101"]) is None


def test_cheaper_than_peers_never_flagged():
    rows = [("101", "Cemento", p) for p in [1000, 1050, 980, 1020, 1010, 300]]
    stats = peers.build_peer_stats(rows)
    assert peers.classify(300.0, stats["101"]) is None


def test_implausible_ratio_is_capped_out():
    # A whole-contract line ($30M) under a per-unit product code is a scope artifact,
    # not a 100000x overprice; it must not be flagged.
    rows = [("101", "Impresion", p) for p in [170, 180, 160, 175, 165, 170]]
    stats = peers.build_peer_stats(rows)
    assert peers.classify(30_000_000.0, stats["101"]) is None


def test_identical_peers_flag_only_on_ratio():
    # MAD == 0 (all peers identical): fall back to a ratio test, don't divide by zero.
    rows = [("101", "Cemento", 1000.0) for _ in range(6)]
    stats = peers.build_peer_stats(rows)
    assert peers.classify(1000.0, stats["101"]) is None
    hit = peers.classify(2500.0, stats["101"])
    assert hit is not None and hit.ratio == 2.5
