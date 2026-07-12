# 0006 — Human curation gate before publishing flags

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

Published flags are effectively public accusations of overpricing against named communes. A
purely automated pipeline will produce false positives (bad matches, stale baselines, unit
mismatches). Publishing those unreviewed would damage the tool's credibility and could harm
real people. The auditor is willing to review flags a few times per week.

## Decision

Statistically flagged anomalies land in a **`pending`** state. A human **confirms or
dismisses** each flag (with an optional note) before it is published. Only **confirmed** flags
appear on the public dashboard; **dismissed** flags are archived with a reason.

## Consequences

- The public dataset carries only human-reviewed claims — credibility protected.
- Adds a manual step a few times per week, which the auditor accepted as a feature, not a
  cost.
- Requires a simple, low-friction review artifact (e.g. a pending-flags file or minimal review
  view). Exact mechanism is a Phase 4 detail.
- Dismissals with reasons become useful training/QA signal for improving the matcher and
  baselines over time.

## Alternatives considered

- **Auto-publish everything above threshold.** Rejected: false positives become public
  accusations.
- **Confidence-based auto-publish (publish only very-high-confidence flags).** Deferred: a
  reasonable later optimization once the matcher's precision is measured, but v1 keeps a human
  in the loop for every published flag.
