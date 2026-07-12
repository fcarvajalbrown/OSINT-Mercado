# 0002 — Python + Polars pipeline; Rust/PyO3 deferred

**Status:** Accepted (Supersedes ADR 001 of `docs/OSINT_Mercado_PRD.pdf`)
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

The original PRD specified Python + Polars with heavy fuzzy-matching logic dropped down to
Rust via PyO3, justified by "cross-referencing thousands of unstandardized purchase strings
against retail strings in real-time." That justification assumed general-purpose fuzzy
matching across all products.

v1 restricts scope to a **tight controlled basket** (~15–25 SKUs), which turns matching into
a curated per-SKU classification problem (ADR 0005), not a high-volume general fuzzy-matching
problem. There is also no real-time requirement — the pipeline is a scheduled batch job.

## Decision

Build the pipeline in **Python with Polars**. **Do not** introduce Rust/PyO3 in v1. Revisit
only if profiling on real data shows a specific, measured bottleneck that Polars/Python
cannot meet.

## Consequences

- Far simpler build and CI: no cross-compilation, no manylinux wheel juggling, no PyO3
  toolchain.
- Polars still provides multi-threaded dataframe performance, which is more than enough at
  basket scale on GitHub Actions.
- The "milliseconds via Rust" claim is dropped as premature optimization (YAGNI). If the
  basket grows toward broad categories (later phases) and a real bottleneck appears, Rust
  becomes a future ADR with evidence behind it.

## Alternatives considered

- **Keep Rust/PyO3 as specified.** Rejected: large build/complexity cost for a benefit the
  v1 scope does not need. Optimization without a measured bottleneck.
- **Pure pandas.** Rejected: Polars is a strictly better fit for the columnar work and
  integrates cleanly with the DuckDB build-time step (ADR 0004).
