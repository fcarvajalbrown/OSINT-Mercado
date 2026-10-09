# 0032 — Automatic overprice estimate from a published auditor method

**Status:** Accepted (supersedes the part of ADR 0031 that holds the overprice estimate until
human review)
**Date:** 2026-10-09
**Deciders:** Felipe Carvajal Brown

## Context

ADR 0031 publishes every lead but withholds the overprice estimate, severity and reference until
Felipe reviews each one; 3,876 leads wait. `docs/research/deterministic-overprice-methods.md`
found published deterministic methods: the CGU's ALICE-Sobrepreço reference price (2025) and
UFMG's Tukey price levels (Silva et al. 2024). Both leave one step to people or to text grouping:
deciding which purchases are comparable. On 2026-10-09, 72.9% of the 25,150 CLP order lines sat
in product-code + unit groups of 10 or more prices.

## Decision

- Comparables: same 8-digit ChileCompra product code, same normalised unit, Región Metropolitana,
  the 12 months before the order date. Fewer than 10 prices: no estimate, the row stays
  "En revisión".
- Reference (CGU): drop prices outside mean ± 1 standard deviation, twice; then the mean if the
  coefficient of variation is 25% or less (TCU Acórdão 9603/2023), otherwise the median.
- Level (UFMG): normal up to Q3; high up to Q3 + 1.5 IQR; overprice above it; above
  100 x (Q3 + 1.5 IQR) is treated as a probable data error and not published as overprice.
- Published with no per-case review as "Estimación automática", with the reference, the % above
  it, the level, the group size and the formula. Felipe's review, when it happens, replaces it
  with "Revisado".
- Every automatic estimate is part of the Stellar seal (ADR 0026).

## Consequences

- Most leads get an estimate without waiting for review.
- A product code covers a commodity class, not a model; a dearer variant inside the same code
  reads as overprice. The label and the visible comparables are the safeguard; the study's
  spec-mismatch finding still applies.
- The method's output is an alert, as all three sources describe theirs, and the page says so.

## Alternatives considered

- **Keep per-case review (ADR 0031 as is).** Too slow for 3,876 leads.
- **UFMG levels only.** No reference or percentage, less informative.
- **CGU reference only.** Any price above the reference counts.
