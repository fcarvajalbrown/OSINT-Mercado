"""Controlled-basket classifier (ADR 0005).

Answers the narrow question "does this line-item refer to one of my known
basket SKUs?" via curated per-SKU keyword rules, with a rapidfuzz fallback
used only to disambiguate. Deterministic: no randomness, no network.

Matching is over the item-identity fields (Producto + EspecificacionProveedor +
EspecificacionComprador) only. The UNSPSC `Categoria` label is deliberately
excluded: it is a broad bucket ("Escobas, trapeadores...") that over-generalizes
and leaks false positives (a dustpan matching "escoba"). Precision matters more
than recall here because every published flag is a public accusation (ADR 0006).

A keyword matches when every one of its meaningful tokens appears as a substring
of the normalized text. Per-token substring (rather than whole-phrase substring)
survives inserted words like "TAMANO", and substring (rather than exact token)
survives plurals ("escobillon" in "escobillones").
"""

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

from osint_mercado.basket import Sku

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_STOPWORDS = {"de", "la", "el", "los", "las", "y", "con", "para", "a", "x", "en", "del"}


def normalize(text: str) -> str:
    """Lowercase, strip accents, and collapse non-alphanumerics to single spaces."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = without_marks.lower()
    return _NON_ALNUM.sub(" ", lowered).strip()


def build_match_text(producto: str, espec_proveedor: str, espec_comprador: str) -> str:
    """Normalized concatenation of the fields carrying product identity."""
    return normalize(" ".join([producto, espec_proveedor, espec_comprador]))


def _keyword_tokens(keyword: str) -> list[str]:
    return [t for t in normalize(keyword).split() if t and t not in _STOPWORDS]


def _keyword_matches(keyword: str, text: str) -> bool:
    tokens = _keyword_tokens(keyword)
    return bool(tokens) and all(t in text for t in tokens)


@dataclass(frozen=True)
class MatchResult:
    sku_id: str | None
    rule: str
    score: float


def _sku_blob(sku: Sku) -> str:
    return normalize(" ".join([sku.canonical_name, *sku.keywords]))


def match(producto: str, espec_proveedor: str, espec_comprador: str,
          skus: list[Sku]) -> MatchResult:
    """Classify a line-item against the basket.

    A SKU is a candidate only if one of its curated keywords fires. With a
    single candidate that is the match; with several, rapidfuzz token_set_ratio
    picks the closest (the only role of fuzzy matching, per ADR 0005). No
    keyword, no match: recall is bounded by keyword coverage, which keeps
    precision high for a public-accusation tool.
    """
    text = build_match_text(producto, espec_proveedor, espec_comprador)
    if not text:
        return MatchResult(None, "none", 0.0)

    candidates = [
        sku for sku in skus
        if any(_keyword_matches(kw, text) for kw in sku.keywords)
    ]

    if not candidates:
        return MatchResult(None, "none", 0.0)

    if len(candidates) == 1:
        return MatchResult(candidates[0].sku_id, "keyword", 100.0)

    best = max(candidates, key=lambda s: fuzz.token_set_ratio(text, _sku_blob(s)))
    best_score = fuzz.token_set_ratio(text, _sku_blob(best))
    return MatchResult(best.sku_id, "keyword+fuzzy", best_score)
