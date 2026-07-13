# 0021 - Match on the especificacion, not the UNSPSC category label

Status: Accepted
Date: 2026-07-13
Deciders: Felipe Carvajal Brown

## Context

ADR 0012 matched over `Producto + EspecificacionProveedor + EspecificacionComprador`. In the real
API data the `Producto` field is almost always the broad **UNSPSC product-category label**
("Nueces o frutos secos", "Brochas", "Harina de trigo", "Jugos y nectar concentrados"), not the
specific item. A basket keyword that appears in the category name therefore fired regardless of
what was actually bought. Verifying an autonomously published batch exposed this concretely: a line
whose item was **almond flour** matched `harina_1kg` via the category "Harina de trigo"; **hazelnuts**
and **quinoa** matched `nueces_1kg`; a **paint roller** matched `brocha_pintura`; **highlighters**
matched `plumon_pizarra`; **frozen berries / passion-fruit pulp** matched `jugo_nectar_15l`.

Worse, this defeated the cross-confirmation publish gate (ADR 0020): the peer engine groups by the
same UNSPSC product code, so both engines "agreed" for the *same* wrong reason - the agreement was
not independent, and false accusations reached the public site before being caught and reverted.

## Decision

Match on the **especificacion fields** (`EspecificacionProveedor` + `EspecificacionComprador`), which
carry the specific item description. Fall back to the `Producto` category label only when both
especificacion fields are empty. A category label alone can no longer trigger a match when the
espec describes a different product.

Complementary hardening from the same verification pass: per-SKU excludes for tier/format/bundle
mismatches surfaced (tineta vs galon, adjustable basketball *system* vs rim, kit/trofeo bundles vs a
single pendrive, toallitas/wipes vs liquid disinfectant, almond flour vs wheat), and `parse_count`
learned "N corchetes/grapas" so bulk-count boxes normalize instead of misfiring.

## Consequences

- On the 13-day RM capture the cross-confirmed set fell from 17 (mostly category-pollution false
  positives) to 3 genuine right-product candidates - and even those carry tier/quantity uncertainty a
  human must resolve on the source order. This is the intended precision-first behaviour.
- Recall drops for lines where the real item name lived only in the `Producto` field and the espec was
  boilerplate ("segun cotizacion adjunta"). Acceptable: a missed match is a non-event; a false match is
  a false public accusation.
- **The key operational finding:** the automated gate is a strong *filter* (853 reviewable -> ~3
  candidates) but not a safe *substitute for human verification*. Bundles, unparsed units, and
  format/tier mismatches still pass "both engines agree". Autonomous publishing is therefore retired in
  favour of automation-assisted human confirmation (the cross-check pre-ranks; a person confirms each).
- Supersedes the matching-scope portion of ADR 0012.

## Alternatives considered

- **Enumerate excludes for every contradicting product.** Rejected: unbounded and always one new
  product behind; espec-primary matching fixes the class, not the instance.
- **Keep matching the category label, lean on the cross-check.** Rejected: the cross-check is not
  independent of the category, so it inherits the same error - the exact failure that reached production.
