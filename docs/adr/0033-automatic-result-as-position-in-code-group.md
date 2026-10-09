# 0033 — Publish the automatic result as a position against its code group

**Status:** Accepted (amends ADR 0032)
**Date:** 2026-10-09
**Deciders:** Felipe Carvajal Brown

## Context

ADR 0032's formula, run on 3,893 leads, gave 1,079 estimates whose top "overprice" cases were
format mismatches (San Pedro +75,903% for a print job). A pack and size parser plus the CGU
homogeneity test cut that to 143, and none of the top 12 was a clean comparison: bundled orders,
a wrong product code, a broom width read as a length, packs the parser missed, product tiers.
After fixing three parser gaps ("x N" boxes, sachets), 150 estimates remain: 73 normal, 41 high,
35 out of range, 1 data error. The method measures a price's position in its product-code group;
on this data that is not proof of overprice.

## Decision

- Comparables as ADR 0032, priced per base unit (unit, gram, millilitre or metre) from the pack
  and size parser, grouped by product code, unit and dimension.
- An estimate is published only when the group passes the CGU homogeneity test (coefficient of
  variation 25% or less after the two trims); the reference is then the mean. Dispersed groups
  get no estimate.
- Levels: "normal" up to Q3, "alto" up to the Tukey fence, "fuera de rango" above it,
  "error de datos" above 100 times the fence.
- The page shows the reference and the % "sobre la referencia automática" for every level, and
  above the fence says "Fuera de rango para su código: puede ser formato, paquete o sobreprecio".
  The word sobreprecio is never a label of the automatic result.
- No per-case human step. Felipe's review, when it happens, replaces the automatic result with
  "Revisado".

## Consequences

- 150 of 3,893 leads get an automatic result; the rest stay "En revisión".
- No municipality is labelled with an overprice the method cannot show.
- The "alto" level can still reflect format (instant coffee sticks against jars per gram); the
  page text says so.
- Runs in the local build in about 8 s; the server has no Python.

## Alternatives considered

- **Publish ADR 0032's "sobreprecio" label after the parser fixes.** Four-digit percentages for
  bundles and wrong codes would remain.
- **Drop the automatic estimate (back to ADR 0031).** Leads keep waiting.
