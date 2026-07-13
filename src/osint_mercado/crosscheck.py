"""Cross-confirmation publish gate (ADR 0020).

A flag is publishable only when two independent methods agree it is a severe
overprice: the retail-baseline engine (real store prices, ADR 0013/0017) AND the
commune-vs-commune peer engine (ADR 0018). Retail is an external anchor; peers are
the internal market. Agreement between them is the automated stand-in for human
review when publishing without a per-flag look.

Pure and deterministic: takes the two queues, returns the cross-confirmed set with
both engines' evidence attached.
"""


def cross_confirmed(basket, peer, *, require_severe=True, min_peers=5) -> list[dict]:
    """Lines flagged by BOTH engines. `basket` = pending anomalies, `peer` = peer flags."""
    peer_by_line = {(x["oc_id"], x["correlativo"]): x for x in peer}
    out = []
    for b in basket:
        if b.get("status") != "pending":
            continue
        p = peer_by_line.get((b["oc_id"], b["correlativo"]))
        if p is None:
            continue
        if p.get("n_peers", 0) < min_peers:
            continue
        if require_severe and not (
            b.get("severity") == "severe" and p.get("severity") == "severe"
        ):
            continue
        out.append({
            "id": b["id"], "oc_id": b["oc_id"], "correlativo": b["correlativo"],
            "comuna": b["comuna"], "sku_id": b["sku_id"],
            "retail_ratio": b.get("overprice_ratio"), "peer_ratio": p.get("overprice_ratio"),
            "n_peers": p.get("n_peers"), "peer_median_clp": p.get("peer_median_clp"),
            "retail_ref": b.get("reference_price_clp"),
            "paid": b.get("unit_price_clp_gross"), "oc_url": b.get("oc_url"),
        })
    out.sort(key=lambda c: -(c["retail_ratio"] or 0))
    return out
