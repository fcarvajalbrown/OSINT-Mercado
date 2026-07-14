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
    # tier / wrong-product signals surfaced by review: heavy-duty vs consumer,
    # chargers vs batteries, tablets/aerosol vs the liquid SKU, lockers, etc.
    "industrial", "municipal", "jumbo", "isofit", "locker", "cargador",
    "recargable", "pastilla", "aerosol", "profesional", "aguarras",
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


def matched_sku_ids(espec: str, skus) -> set:
    """Which basket SKUs the espec matches (same rule as the matcher)."""
    text = matcher.normalize(espec)
    out = set()
    for s in skus:
        if any(matcher._keyword_matches(kw, text) for kw in s.keywords) and not any(
            matcher._keyword_matches(x, text) for x in s.exclude
        ):
            out.add(s.sku_id)
    return out


def looks_like_bundle(espec: str, skus) -> bool:
    """A single clean purchase line names one product; a bundle/multi-item line
    matches several SKUs, enumerates, or is verbose. Reject those - the priced
    total is not attributable to the one SKU our keyword happened to hit."""
    if len(matched_sku_ids(espec, skus)) > 1:
        return True
    if espec.count("\n") >= 2:
        return True
    if len(matcher.normalize(espec)) > 220:
        return True
    return False


def is_publishable_volume(flag: dict, espec: str, sku: Sku, skus) -> tuple[bool, str]:
    """Volume gate: like is_publishable_medium but replaces the peer requirement
    with a direct bundle/multi-item detector, so clean single-product retail flags
    publish without needing peer agreement. Keeps right-product, red-context and
    ratio guards."""
    ok, why = is_publishable_medium(flag, espec, sku)
    if not ok:
        return False, why
    if looks_like_bundle(espec, skus):
        return False, "bundle / multi-item line"
    # heavy-duty stapler capacity (100+ hojas) is a different tier from the desktop
    # baseline; "hojas" alone is fine (a paper ream is 500 hojas).
    if sku.sku_id == "corchetera_metalica" and re.search(r"\b[1-9]\d\d\s*hojas", matcher.normalize(espec)):
        return False, "heavy-duty capacity tier"
    # packaging language we did NOT normalize (divisor stayed 1) means the unit is
    # uncertain - a box of 10 reams priced against one ream reads as a fake 11x.
    if (flag.get("unit_divisor") or 1) == 1 and re.search(
        r"\b(cajas|pack|paquetes|estuche|resmas|block|display|x\s*\d+|\d+\s*cajas)\b",
        matcher.normalize(espec),
    ):
        return False, "unnormalized pack/box multiplier"
    return True, "clean (volume)"


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


def is_publishable_medium(flag: dict, espec: str, sku: Sku) -> tuple[bool, str]:
    """Medium-conservative gate for autonomous publishing.

    Keeps the checks that prevent *false* accusations - a `pending` overprice at
    watch tier or above, in a sane ratio band, whose SKU keyword actually appears
    in the item's especificacion, with no red-context (bundle / dispenser /
    quote-request / multi-gallon-or-tineta container / appliance). Drops the
    stricter peer-agreement and tier-stable requirements, so tier-variable and
    single-source flags publish too. Each still carries its source-order link.
    """
    if flag.get("status") != "pending":
        return False, "not pending"
    ratio = flag.get("overprice_ratio") or 0
    if flag.get("severity") not in ("severe", "high", "watch"):
        return False, "below watch tier"
    if not (MIN_RATIO <= ratio <= MAX_RATIO):
        return False, "ratio outside sane band"
    text = matcher.normalize(espec)
    if not any(matcher._keyword_matches(kw, text) for kw in sku.keywords):
        return False, "SKU keyword absent from espec"
    if has_red_context(espec):
        return False, "red context (bundle/dispenser/container/quote/appliance)"
    return True, "clean (medium)"


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
