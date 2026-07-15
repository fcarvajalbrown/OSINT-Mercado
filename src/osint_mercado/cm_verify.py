"""CM lead quality gate (ADR 0024), reusing the verify.py philosophy.

Every CM lead already cleared the scoring core (same-product match within the code,
size/pack-normalized, median reference, plausibility band). This gate adds the
second-order checks the manual review taught us on the retail engine (ADR 0023),
adapted for CM: is the priced line a *clean single-product* purchase, or a bundle /
red-context / unresolved-pack line whose price is not attributable to one unit?

CM leads are never auto-published (ADR 0006/0024) - they all go to the human gate.
This gate does not gate publishing; it tags each lead `clean` or not, with a reason,
so the reviewer sees which leads are the cleanest and which need a closer look. The
two live false positives a reviewer surfaced (a colored pen SET, a multi-flavor
juice line) are the regression cases this encodes.
"""

import re

from osint_mercado import verify
from osint_mercado.matcher import normalize

# Bundle / assortment signals: the priced line is several items, not one unit.
_BUNDLE_WORDS = ("set", "kit", "combo", "surtido", "juego", "pack")

# Container/pack words whose multiplier is not a clean per-unit price. Their
# presence means the priced unit is uncertain (a box of N vs one), so hold for
# review rather than accuse - the "unnormalized pack/box multiplier" failure mode.
_PACK_WORDS = ("caja", "cajas", "resma", "resmas", "paquete", "paquetes",
               "estuche", "display", "blister", "docena", "bandeja")

# A verbose or enumerated line (multiple items listed) is a bundle, not one product.
_MAX_CLEAN_LEN = 180


def _has_word(word: str, text: str) -> bool:
    return re.search(r"\b" + re.escape(word) + r"(?:es|s)?\b", text) is not None


def looks_like_bundle(oc_text: str) -> bool:
    """A single clean line names one product; a bundle sets/enumerates/is verbose."""
    text = normalize(oc_text)
    if any(_has_word(w, text) for w in _BUNDLE_WORDS):
        return True
    # an assorted "N colores" set (e.g. a 12-colour tempera box), N >= 2
    if re.search(r"\b([2-9]|\d{2,})\s*colores\b", text):
        return True
    if oc_text.count("\n") >= 2:  # enumerated flavors / variants
        return True
    if len(text) > _MAX_CLEAN_LEN:
        return True
    return False


def has_pack_ambiguity(oc_text: str) -> bool:
    """The line carries a box/pack multiplier that is not a clean per-unit price."""
    text = normalize(oc_text)
    if any(_has_word(w, text) for w in _PACK_WORDS):
        return True
    # a bare "x 10" / "x10" multiplier
    return re.search(r"\bx\s*\d{2,}\b", text) is not None


def assess(oc_text: str) -> tuple[bool, str]:
    """Is this OC line a clean single-product purchase? Returns (clean, reason)."""
    if verify.has_red_context(oc_text):
        return False, "red context (dispenser/kit/quote/container/appliance/service)"
    if looks_like_bundle(oc_text):
        return False, "bundle / set / multi-item line"
    if has_pack_ambiguity(oc_text):
        return False, "unresolved pack/box multiplier"
    return True, "clean single-product line"


def assess_lead(oc_text: str, cm_reference_text: str) -> tuple[bool, str]:
    """Clean only if BOTH the OC line and the matched CM reference are single items.

    The scorer matches on shared tokens, so a single-product OC line can land on a
    CM reference that is itself a set/multi-pack (e.g. a 12-colour tempera box):
    the per-unit comparison is then apples-to-oranges. Screening the CM reference
    for the same bundle signals catches that class of false positive.
    """
    clean, reason = assess(oc_text)
    if not clean:
        return False, reason
    if looks_like_bundle(cm_reference_text):
        return False, "CM reference is a bundle / set / multi-pack"
    return True, "clean single-product line"
