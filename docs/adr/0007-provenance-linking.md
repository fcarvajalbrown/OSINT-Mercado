# 0007 — Provenance linking (verifiable flags) in v1

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

The original PRD placed verifiable, provenance-backed reports in its *future* roadmap
(cryptographic hashing for submissions to Contraloría). But a watchdog that makes public
claims needs those claims to be checkable from day one; unverifiable flags are worthless and
dangerous. Full cryptographic provenance is heavier than v1 needs, but basic source-linking is
not optional.

## Decision

In v1, every flag **stores and displays** its provenance: the official source order id, a
direct link back to the order on Mercado Público, and a capture timestamp. The dashboard
surfaces the source link on every row so any reader can verify a flag against the official
record.

## Consequences

- Every published claim is independently verifiable — the credibility floor for a watchdog.
- Provenance fields become part of the core data model and the published schema.
- Cryptographic hashing of source payloads (tamper-evident provenance for formal oversight
  submissions) remains a **later phase**, building on these fields rather than replacing them.

## Alternatives considered

- **Defer all provenance to a later phase (as in the original PRD).** Rejected: publishing
  unverifiable accusations is unacceptable even in v1.
- **Full cryptographic hashing now.** Rejected for v1 as heavier than needed; scheduled as a
  later phase on top of the v1 provenance fields.
