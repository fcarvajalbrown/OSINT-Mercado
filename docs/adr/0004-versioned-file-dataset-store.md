# 0004 — Versioned file dataset as store; DuckDB build-time only

**Status:** Accepted (Supersedes/revises ADR 003 of `docs/OSINT_Mercado_PRD.pdf`)
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

The original PRD chose **DuckDB** as an in-process embedded analytical backend for a desktop
daemon. In the split architecture (ADR 0001) there is no long-running host process: the
pipeline runs in CI and the host serves static files. A runtime database on Hostinger is both
unavailable (no root/servers) and unnecessary.

There is also a provenance requirement (ADR 0007): flags must be verifiable and the dataset's
history auditable.

## Decision

Use **versioned data files (Parquet and/or JSON) committed to the repo** as the store. Git
history is the audit trail — every change to the dataset is a diff with a timestamp and
author. Use **DuckDB at build time** inside the pipeline to query/aggregate/shape the data
that gets published; it is a build tool, not a runtime dependency.

## Consequences

- Free, tamper-evident-ish provenance and reproducibility via git history.
- No database server anywhere; the published artifact is just files the static site reads.
- DuckDB's OLAP strengths are still used where they help (build-time aggregation), keeping
  that part of the original design alive honestly.
- Large raw data is not committed wholesale; the repo holds curated/published datasets and
  the inputs needed to reproduce them. Retention/size policy is a Phase 1–2 detail.

## Alternatives considered

- **DuckDB file as the shipped runtime store.** Rejected: the browser reads JSON in v1;
  shipping a DuckDB file only matters if we adopt DuckDB-WASM (a possible later showcase, not
  needed now).
- **Hostinger MySQL as the store.** Rejected for v1 (see ADR 0003): getting CI data into
  shared-hosting MySQL is the fiddly part, and server-side query isn't needed yet.
