"""SoloTodo retail price source: an independent second anchor for goods (ADR 0022).

The auto-catalog (ADR 0019) covers ~2,654 products but baselines them only by the
commune-vs-commune peer median - single-source. SoloTodo (`api.solotodo.com`) is a
public, no-auth Chilean price aggregator that scrapes private retail (Falabella,
Paris, PC Factory, DGA, etc.). Querying it gives a real cross-retailer price
distribution, independent of Mercado Publico, with a provenance URL per store.

Precision guard (so it never anchors to the wrong product): a quote is only
returned when the caller's distinctive tokens all appear in the SoloTodo product
name. A broad category median ("Toner") is meaningless; a part-number/model match
("CF283A") is exact. Goods only - SoloTodo carries no services.
"""

import unicodedata

from osint_mercado import peers

BASE = "https://api.solotodo.com"


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def offer_prices(entities: list[dict]) -> list[float]:
    """Extract active per-store offer prices (CLP) from an /entities/ payload."""
    out: list[float] = []
    for e in entities:
        reg = e.get("active_registry") or {}
        price = reg.get("offer_price") or reg.get("normal_price")
        if price in (None, "", 0):
            continue
        try:
            out.append(float(price))
        except (TypeError, ValueError):
            continue
    return out


def name_matches(product_name: str, must_tokens) -> bool:
    """True only if every distinctive token appears in the product name."""
    nm = _norm(product_name)
    toks = [_norm(t) for t in must_tokens if t]
    return bool(toks) and all(t in nm for t in toks)


def retail_stats(prices: list[float]) -> dict | None:
    if not prices:
        return None
    return {
        "median_clp": peers.median(prices),
        "min_clp": min(prices),
        "n_offers": len(prices),
    }


# --- network (thin; parsing above is what tests cover) -----------------------

def search_products(session, query: str, page_size: int = 8) -> list[dict]:
    r = session.get(f"{BASE}/products/", params={"search": query, "page_size": page_size}, timeout=25)
    r.raise_for_status()
    return r.json().get("results", [])


def product_entities(session, product_id) -> list[dict]:
    r = session.get(f"{BASE}/products/{product_id}/entities/", timeout=25)
    r.raise_for_status()
    return r.json()


def retail_quote(session, query: str, must_tokens=()) -> dict | None:
    """Robust retail price for the SoloTodo product(s) matching `must_tokens`.

    Returns None when nothing confidently matches - the caller then simply has no
    SoloTodo anchor for that item (peer-only), rather than a wrong one.
    """
    prices: list[float] = []
    matched_name = sample_url = None
    for p in search_products(session, query):
        if must_tokens and not name_matches(p.get("name", ""), must_tokens):
            continue
        ents = product_entities(session, p["id"])
        pr = offer_prices(ents)
        if not pr:
            continue
        prices.extend(pr)
        matched_name = matched_name or p.get("name")
        if sample_url is None:
            sample_url = next((e.get("external_url") for e in ents if e.get("external_url")), None)
    stats = retail_stats(prices)
    if stats is None:
        return None
    stats.update(product=matched_name, url=sample_url, query=query, source="solotodo")
    return stats
