# 0027 — Anchor the source order line behind each flag (extends ADR 0026)

**Status:** Accepted (extends ADR 0026)
**Date:** 2026-10-09
**Deciders:** Felipe Carvajal Brown

## Context

ADR 0026 anchors the published flags, which proves the project did not change its own findings
after publication. It says nothing about the government data the finding rests on. Each flag
points to a purchase order line on Mercado Público (ADR 0007), and that page is controlled by
the State: if the order is later edited, cancelled or taken down, the link no longer shows what
the flag was judged against. The pipeline already stores every ingested line with its
`captured_at` timestamp in `data/oc_items_*.parquet`.

## Decision

Extend the anchor to the source line behind each flag.

- **Source snapshot.** For each published flag, the matching ingested row (`oc_id` +
  `correlativo`) is taken from the stored order items, with every `ITEM_COLUMNS` field as
  captured, including `captured_at`. Missing values become `null`.
- **Source hash inside the flag.** The source row's canonical SHA-256 (same canonical form as
  ADR 0026) is written into the published flag as `source_sha256`, so the flag's leaf, and
  therefore the on-chain digest, commits to both the finding and its source.
- **Published snapshots.** The source rows are published as `data/sources.json`, keyed by flag
  id. They are already public on Mercado Público; publishing them exposes nothing new.
- **Browser check.** The verifier recomputes each source hash from `sources.json`, checks it
  against the flag's `source_sha256`, then checks the flag leaf against the anchored digest.
  The dashboard shows the capture time in Chile local time with UTC in parentheses.
- A flag whose source row cannot be found is published without `source_sha256` and the
  dashboard says so; it is never given an invented snapshot.

## Consequences

- The project can show what an order line said when it was captured, independent of the
  current state of Mercado Público, within the testnet limits of ADR 0026.
- `osint-build-site` and `osint-anchor` now need the ingested parquet files that hold the
  flagged lines; those files are gitignored, so anchoring runs where they exist.
- This is a demonstration of an integrity layer, not legal evidence, and the project makes no
  claim that orders are in fact altered after publication.

## Alternatives considered

- **Hash the whole order as returned by the API.** Rejected for now: the pipeline keeps the
  normalised line items, not the raw JSON responses, so an exact raw snapshot does not exist
  for past captures.
- **Anchor every ingested line, not only flagged ones.** Rejected for now: far more data than
  the dashboard can verify in a browser, and not what the hackathon demo needs. Candidate for
  a later ADR together with Merkle proofs.
