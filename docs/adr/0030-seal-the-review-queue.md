# 0030 — Seal the review queue alongside the published set

**Status:** Accepted (builds on ADR 0006 and 0026)
**Date:** 2026-10-09
**Deciders:** Felipe Carvajal Brown

## Context

Only human-reviewed leads are published (ADR 0006). On 2026-10-09 the public site showed 2 flags
while 3,895 leads waited in review: 3,248 in `pending_anomalies.json`, 346 Convenio Marco leads in
`cm_pending.json` and 301 peer-price leads in `peer_pending.json`. A reader cannot tell whether
inconvenient leads are being quietly dropped from that queue. Publishing the unreviewed rows is
ruled out by ADR 0006, and the same night two of the four reviewed flags failed a fair-price
review and were withdrawn.

## Decision

- Each queued lead gets a canonical SHA-256, the same canonical form as ADR 0026.
- The sorted lead hashes combine into one queue digest.
- The anchor transaction that already carries the published digest (hash memo and `manage_data`
  `osint-mercado`) also carries the queue digest in a second `manage_data` entry,
  `osint-mercado-queue`. One transaction per publication, as before.
- The site publishes `data/queue.json` with the lead hashes, none of their content, plus counts
  by comuna and severity. Municipality names appear only in those counts.
- The browser recomputes the queue digest from `queue.json` and checks it against the on-chain
  entry.
- Later, a lead's content can be revealed and checked against its hash, proving it was in the
  queue on that date. If a lead disappears between two sealed queues, the drop in the count is
  visible to anyone.

## Consequences

- The public sees the size and spread of the review queue without any individual unreviewed lead
  being published, and removing leads from the queue becomes visible.
- Every anchor from now on commits to two digests. The anchor at ledger 5111652 has only the
  first; the next publication produces the first queue seal.
- The testnet caveats of ADR 0026 apply.

## Alternatives considered

- **Publish the unreviewed rows.** Rejected: ADR 0006, and the withdrawals of 2026-10-09.
- **A separate transaction for the queue.** Rejected: one transaction keeps both digests tied to
  the same moment.
