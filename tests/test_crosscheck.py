from osint_mercado import crosscheck


def _b(oc, cor, sku, sev, ratio):
    return {"id": f"{oc}-{cor}-{sku}", "oc_id": oc, "correlativo": cor, "sku_id": sku,
            "status": "pending", "severity": sev, "overprice_ratio": ratio,
            "comuna": "X", "unit_price_clp_gross": 1000.0, "reference_price_clp": 100.0,
            "oc_url": "http://x"}


def _p(oc, cor, sev, ratio, n=20):
    return {"oc_id": oc, "correlativo": cor, "severity": sev, "overprice_ratio": ratio,
            "n_peers": n, "peer_median_clp": 90.0}


def test_only_lines_flagged_by_both_engines_are_confirmed():
    basket = [_b("1", 1, "harina_1kg", "severe", 8.0), _b("2", 1, "cloro", "severe", 5.0)]
    peer = [_p("1", 1, "severe", 6.0)]  # only line 1 is a peer outlier
    out = crosscheck.cross_confirmed(basket, peer)
    assert [c["id"] for c in out] == ["1-1-harina_1kg"]
    assert out[0]["retail_ratio"] == 8.0
    assert out[0]["peer_ratio"] == 6.0
    assert out[0]["n_peers"] == 20


def test_requires_severe_in_both_by_default():
    basket = [_b("1", 1, "s", "severe", 8.0)]
    peer = [_p("1", 1, "high", 2.2)]  # peer only high -> not published
    assert crosscheck.cross_confirmed(basket, peer) == []


def test_non_pending_basket_lines_ignored():
    basket = [{**_b("1", 1, "s", "severe", 8.0), "status": "unit_ambiguous"}]
    peer = [_p("1", 1, "severe", 6.0)]
    assert crosscheck.cross_confirmed(basket, peer) == []


def test_min_peers_guard():
    basket = [_b("1", 1, "s", "severe", 8.0)]
    peer = [_p("1", 1, "severe", 6.0, n=3)]  # too few peers to trust the median
    assert crosscheck.cross_confirmed(basket, peer, min_peers=5) == []
