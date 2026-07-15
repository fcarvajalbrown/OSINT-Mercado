"""Convenio Marco (CM) overprice scoring core (ADR 0024).

The normative comparison: could the organism have bought this cheaper under the
framework agreement it was bound to consider? For one OC line-item we look up the
CM rows sharing its UNSPSC code, keep only those that name the *same product*
(token overlap - the code alone is not a match, since broad ONU codes and buyer
misclassification put "pala de aseo" and "mesa plegable" under one code), normalize
both sides by size or pack so we compare per gram / ml / m / each, and measure the
paid price against the *median* matched CM price (median, not min - a one-off
per-pack artifact must not become the reference).

Net-to-net: CM "PRECIO EN TIENDA" is shown net of IVA, same basis as an OC line's
PrecioNeto, so neither side is grossed up (confirmed against ChileCompra store docs
and an empirical near-parity cross-check; ADR 0024). Deterministic, no network:
currency conversion to CLP happens upstream in the CLI, as with the peer engine.
"""

import hashlib
from dataclasses import dataclass

from osint_mercado import cm_catalog, units
from osint_mercado.matcher import _STOPWORDS, normalize
from osint_mercado.peers import median
from osint_mercado.scoring import severity

# A matched CM reference median needs at least this many token-matched, size-parseable
# offers before it is trustworthy enough to raise a lead (ADR 0024).
MIN_REFS = 3

# Two distinctive tokens (>= this length) must be shared between the OC item and a
# CM row for it to count as the same product within a shared code.
MIN_SHARED_TOKENS = 2
MIN_TOKEN_LEN = 4

# Plausibility band. Below the floor it is not an overprice; above the cap it is
# almost always a scope/unit artifact (a whole contract under one product code),
# routed out rather than raised as an implausible accusation.
MIN_RATIO = 1.5
MAX_RATIO = 15.0

# Generic words that carry no product identity - excluded from token matching so
# overlap reflects the actual item, not shared boilerplate.
_GENERIC = {
    "unidad", "unidades", "caja", "cajas", "pack", "juego", "bolsa", "bolsas",
    "color", "colores", "marca", "modelo", "tipo", "region", "metropolitana",
    "nacional", "precio", "tienda", "producto", "aproximado", "equivalente",
}


@dataclass(frozen=True)
class CMComparison:
    dimension: str          # "g" / "ml" / "m" / "unit"
    ratio: float
    severity: str
    oc_per_unit: float
    cm_reference_per_unit: float
    n_refs: int
    cm_sample_producto: str
    cm_region: str


@dataclass(frozen=True)
class CMLead:
    id: str
    oc_id: str
    correlativo: int
    comuna: str
    product_code: str
    oc_text: str
    unit_price_clp_net: float
    dimension: str
    oc_per_unit: float
    cm_reference_per_unit: float
    ratio: float
    severity: str
    n_refs: int
    cm_sample_producto: str
    cm_region: str
    status: str
    oc_url: str
    captured_at: str


def distinctive_tokens(text: str) -> set[str]:
    """Identity-bearing tokens of a product text: long enough, not stop/generic."""
    out = set()
    for tok in normalize(text).split():
        if len(tok) < MIN_TOKEN_LEN or tok.isdigit():
            continue
        if tok in _STOPWORDS or tok in _GENERIC:
            continue
        out.add(tok)
    return out


def _matched_rows(oc_tokens: set[str], cm_rows: list[dict]) -> list[dict]:
    matched = []
    for row in cm_rows:
        shared = oc_tokens & distinctive_tokens(cm_catalog.descriptive_text(row))
        if len(shared) >= MIN_SHARED_TOKENS:
            matched.append(row)
    return matched


def _dominant_dimension(oc_text: str, matched: list[dict]) -> str:
    """The size dimension most matched CM rows carry, or 'unit' if none do.

    Determining the dimension from the matched set (not guessed per code) keeps OC
    and CM on the same footing: a mis-detected dimension yields no comparison rather
    than a wrong one.
    """
    counts = {"g": 0, "ml": 0, "m": 0}
    for row in matched:
        parsed = units.parse_any_size(cm_catalog.descriptive_text(row))
        if parsed is not None:
            counts[parsed[0]] += 1
    best_dim, best_n = max(counts.items(), key=lambda kv: kv[1])
    if best_n == 0 or units.parse_any_size(oc_text) is None:
        return "unit"
    return best_dim


def _per_unit(text: str, price: float, dim: str) -> float | None:
    """Price per base unit (per g/ml/m, or per each) after pack normalization."""
    pack = units.parse_count(text) or 1
    if dim == "unit":
        return price / pack
    size = units.parse_size_in_dim(text, dim)
    if size is None or size <= 0:
        return None
    return price / (size * pack)


def compare(oc_text: str, unit_price_clp_net: float, cm_rows: list[dict],
            *, min_refs: int = MIN_REFS) -> CMComparison | None:
    """Size/pack-normalized, product-matched CM comparison for one OC line, or None.

    None whenever the line cannot be compared defensibly: no CM coverage, no
    same-product match within the code, too few references for a trustworthy
    median, an unnormalizable size, or a ratio outside the plausibility band.
    """
    if not cm_rows or unit_price_clp_net <= 0:
        return None
    oc_tokens = distinctive_tokens(oc_text)
    matched = _matched_rows(oc_tokens, cm_rows)
    if len(matched) < min_refs:
        return None

    dim = _dominant_dimension(oc_text, matched)
    oc_per_unit = _per_unit(oc_text, unit_price_clp_net, dim)
    if oc_per_unit is None:
        return None

    refs = []
    sample = None
    for row in matched:
        cm_pu = _per_unit(cm_catalog.descriptive_text(row), row["precio_neto"], dim)
        if cm_pu is not None and cm_pu > 0:
            refs.append(cm_pu)
            if sample is None:
                sample = row
    if len(refs) < min_refs:
        return None

    reference = median(refs)
    if reference <= 0:
        return None
    ratio = round(oc_per_unit / reference, 4)
    if ratio < MIN_RATIO or ratio > MAX_RATIO:
        return None
    sev = severity(ratio)
    if sev is None:
        return None

    return CMComparison(
        dimension=dim, ratio=ratio, severity=sev,
        oc_per_unit=round(oc_per_unit, 2),
        cm_reference_per_unit=round(reference, 2), n_refs=len(refs),
        cm_sample_producto=sample["producto"], cm_region=sample["region"],
    )


def make_lead_id(oc_id: str, correlativo: int, product_code: str) -> str:
    raw = f"cm|{oc_id}|{correlativo}|{product_code}".encode()
    return hashlib.sha1(raw).hexdigest()[:16]


def score_cm(*, oc_id, correlativo, comuna, product_code, oc_text,
             unit_price_clp_net, oc_url, captured_at, cm_rows,
             min_refs: int = MIN_REFS) -> CMLead | None:
    """Score one OC line against its CM code and return a lead, or None.

    Every returned lead is investigative (goes to the human curation gate, never
    auto-published; ADR 0006/0024), carrying the matched CM evidence and the
    order's provenance so a reviewer can check it against the official source.
    """
    cmp = compare(oc_text, unit_price_clp_net, cm_rows, min_refs=min_refs)
    if cmp is None:
        return None
    return CMLead(
        id=make_lead_id(oc_id, correlativo, product_code),
        oc_id=oc_id, correlativo=correlativo, comuna=comuna,
        product_code=product_code, oc_text=oc_text,
        unit_price_clp_net=round(unit_price_clp_net, 2),
        dimension=cmp.dimension, oc_per_unit=cmp.oc_per_unit,
        cm_reference_per_unit=cmp.cm_reference_per_unit, ratio=cmp.ratio,
        severity=cmp.severity, n_refs=cmp.n_refs,
        cm_sample_producto=cmp.cm_sample_producto, cm_region=cmp.cm_region,
        status="pending", oc_url=oc_url, captured_at=captured_at,
    )
