"""Conservative publish-verification filter (ADR 0023).

The cross-confirmation gate (ADR 0020) proved necessary but not sufficient: bundles,
dispensers, bigger containers, and quote-request lines still slipped past "both
engines agree" and produced false accusations. This filter is the second gate,
encoding the failure modes the manual commune-by-commune review exposed. It is
deliberately strict - it rejects on any doubt - because a missed publish is a
non-event while a false one is a public accusation.

A flag is publishable only if ALL hold:
  - it is a `pending` severe/high overprice, ratio in a sane band;
  - an independent method (the peer engine) also flagged it;
  - the SKU's own keyword actually appears in the item's especificacion; and
  - the espec carries none of the red-context signals (a dispenser OF the
    consumable, a kit/bundle, a multi-gallon/tineta container, a quote-request
    with no fixed quantity, an industrial/appliance variant).
"""

import re

from osint_mercado import matcher
from osint_mercado.basket import Sku

# Espec substrings that mean "this is not a clean, comparable purchase of the SKU".
RED_CONTEXT = (
    "dispensador", "kit ", "cotizacion", "ee.tt", "eett", "adjunt", "tineta",
    "granel", "ajustable", "calefon", "estufa", "batidora", "semi industrial",
    "juego de mesa", "oftalmoscopio", "pedestal", "segun eett", "por metro",
    "arriendo", "instalacion",
)

MIN_RATIO = 1.5
MAX_RATIO = 15.0

# SKUs whose quality tier barely varies, so a keyword match at a standard unit is
# reliably the same product - safe to publish autonomously. Tier-variable SKUs
# (te flavored vs plain, escoba industrial vs consumer, cafe/pens premium vs basic,
# appliances, footwear, paint) are deliberately excluded and held for human review.
TIER_STABLE = frozenset({
    "papel_resma_carta_75g", "papel_resma_oficio_75g", "pendrive_usb_16gb",
    "huincha_medir", "corchetera_metalica", "corchetes_caja", "cartulina_espanola",
    "opalina_resma", "nueces_1kg", "clips_metalicos_caja", "sobre_oficio",
    "cinta_embalaje", "mouse_usb", "teclado_usb", "toner_hp_cf283a",
    "toner_hp_ce285a", "cartucho_tinta_hp_664_negro", "regla_plastica",
})


def has_red_context(espec: str) -> bool:
    e = matcher.normalize(espec)
    if any(w.strip() in e for w in RED_CONTEXT):
        return True
    # multi-gallon container ("4 gl", "5 gl") priced against a single-gallon baseline
    if re.search(r"\b[2-9]\s*gl\b", e):
        return True
    return False


def is_publishable(flag: dict, espec: str, sku: Sku, *, peer_confirmed: bool) -> tuple[bool, str]:
    if flag.get("status") != "pending":
        return False, "not pending"
    if not peer_confirmed:
        return False, "not peer-confirmed (single source)"
    if flag.get("severity") not in ("severe", "high"):
        return False, "below high tier"
    ratio = flag.get("overprice_ratio") or 0
    if not (MIN_RATIO <= ratio <= MAX_RATIO):
        return False, "ratio outside sane band"
    text = matcher.normalize(espec)
    if not any(matcher._keyword_matches(kw, text) for kw in sku.keywords):
        return False, "SKU keyword absent from espec"
    if has_red_context(espec):
        return False, "red context (bundle/dispenser/container/quote/appliance)"
    return True, "clean"


def is_auto_publishable(flag: dict, espec: str, sku: Sku, *, peer_confirmed: bool) -> tuple[bool, str]:
    """Stricter gate for UNATTENDED publishing: is_publishable AND a tier-stable SKU.

    Tier-variable SKUs can pass is_publishable and still be a pricier-but-legitimate
    variant, so they are never auto-published - only surfaced for human review.
    """
    ok, why = is_publishable(flag, espec, sku, peer_confirmed=peer_confirmed)
    if not ok:
        return False, why
    if sku.sku_id not in TIER_STABLE:
        return False, "tier-variable SKU (hold for human review)"
    return True, "clean (tier-stable)"
