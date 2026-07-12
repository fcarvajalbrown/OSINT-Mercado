# 0013 — Anomaly scoring, severity tiers, unit guardrail, and pending output

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

With CLP/IVA normalization (ADR 0011) and the matcher (ADR 0012) in place, Phase 3 needs to
turn a matched, CLP-comparable line-item into an overprice flag, decide its severity, guard
against a specific false-positive class, and emit the result for the Phase 4 human curation
gate (ADR 0006) with provenance (ADR 0007). Two hazards shape the design: the order's
`Unidad` field is null/unreliable in real data, so a line can be priced per-single-unit while
the baseline is per-pack (or vice versa), producing absurd ratios; and re-runs must be
reproducible (a PRD success criterion).

## Decision

- **Overprice ratio:** `ratio = gross_unit_price_clp / reference_price_clp`, where the numerator
  is the order price after CLP conversion and IVA gross-up (ADR 0011) and the denominator is
  the retail baseline (ADR 0010).
- **Severity tiers** (PRD defaults, as named module constants): `Watch ≥ 1.5×`, `High ≥ 2×`,
  `Severe ≥ 3×`.
- **Baseline confidence guardrail:** only score against a `medium`/`high` baseline. A matched
  line with a missing or `insufficient` baseline is emitted with status `needs_baseline`, not
  scored as an overprice.
- **Per-unit plausibility band:** a ratio outside `[0.3×, 20×]` is treated as a probable
  unit mismatch (per-item vs per-pack) and emitted with status `unit_ambiguous` for human
  review, rather than published as an overprice. Validated on real data: a 75 ml alcohol-gel
  sachet against the 1 L baseline scored 0.18× and was correctly routed to review, not flagged.
- **Emitted outcomes:** matched lines produce an `Anomaly` with `status ∈ {pending,
  unit_ambiguous, needs_baseline}`; a matched line that is in-band and below Watch is not
  emitted at all. All emitted anomalies are written to a single diff-friendly
  `data/pending_anomalies.json`, sorted deterministically by `(comuna, sku_id, oc_id,
  correlativo)`; Phase 4 filters the review queue by `status`.
- **Determinism / provenance:** each anomaly carries a stable
  `id = sha1(oc_id | correlativo | sku_id)[:16]` and the ADR 0007 provenance fields
  (`oc_id`, `oc_url`, `captured_at`). The same inputs always produce byte-identical output.

## Consequences

- The curation gate receives a stable, human-readable queue; `status` separates real overprice
  candidates (`pending`) from items needing a unit check (`unit_ambiguous`) or a better
  baseline (`needs_baseline`).
- Re-running the scorer on the same inputs yields identical flags and ids, satisfying the
  reproducibility criterion and letting Phase 4 confirm/dismiss by id.
- The plausibility band trades a little recall (a genuine >20× overprice would be held for
  review rather than auto-flagged) for protection against the most common false-positive
  class. Acceptable for a public-accusation tool with a human in the loop.
- Thresholds and the band live in one module as constants; tuning them is a one-line change.

## Alternatives considered

- **Parse pack size from spec text and normalize to a true per-single-unit price.** Rejected
  for v1: pack-size parsing from messy free-text is itself error-prone; the plausibility band
  plus the human gate is simpler and safe.
- **Auto-flag every ratio ≥ Watch with no band.** Rejected: unit mismatches would publish
  absurd flags straight into the queue.
- **Separate files per status.** Rejected for v1: one file with a `status` field keeps the
  store simple (ADR 0004) and is enough at basket + RM scale.
