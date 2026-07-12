# 0005 — Controlled-basket classifier over general fuzzy matching

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

Matching messy municipal order line-items to real retail prices is the hardest, riskiest part
of the system, and the original PRD hand-waved it as "intensive fuzzy matching" (its stated
reason for needing Rust). General-purpose fuzzy matching across all products is both hard and
error-prone, and false positives in a watchdog tool are reputationally costly.

v1 restricts scope to a **tight controlled basket** (~15–25 SKUs). The difficulty of matching
is bounded by the basket, not by the number of communes.

## Decision

Implement matching as a **curated per-SKU classifier**, not general fuzzy matching. For each
basket SKU, define canonical keywords/model identifiers and matching rules; apply a fuzzy
**fallback** only to disambiguate. The question the matcher answers is narrow: "does this
line-item refer to one of my known basket SKUs?"

Develop the matcher **test-first** against a labeled sample of real line-items.

## Consequences

- Higher precision and explainability: every match traces to a specific rule, which matters
  when a flag is challenged.
- Removes the stated justification for Rust/PyO3 (see ADR 0002).
- Requires curation effort per SKU, which is acceptable at basket scale and aligns with the
  human-in-the-loop posture (ADR 0006).
- Scaling toward broad categories (later phases) will require revisiting this — likely a
  hybrid of curated rules and a learned/embedding matcher, as its own future ADR.

## Alternatives considered

- **General fuzzy matching (RapidFuzz/token-set over everything).** Rejected for v1: lower
  precision, harder to explain, and unnecessary given the controlled basket.
- **LLM/embedding classifier.** Rejected for v1: adds cost/dependency and non-determinism to
  a pipeline that benefits from being reproducible. A candidate for the broad-category phase.
