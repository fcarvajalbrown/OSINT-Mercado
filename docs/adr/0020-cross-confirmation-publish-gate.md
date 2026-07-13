# 0020 - Cross-confirmation publish gate (two independent methods must agree)

Status: Accepted
Date: 2026-07-13
Deciders: Felipe Carvajal Brown

## Context

Publishing a flag names a commune as having overpaid. The human curation gate (ADR 0006)
is the safeguard, but the deciders authorized publishing a first batch *without a per-flag
human look*, to reach a live, growing set faster. That requires an automated stand-in for
review strong enough to protect against false accusations.

Two independent price references now exist: the retail-baseline engine (real store prices,
two sources per SKU where possible; ADR 0013/0017) and the commune-vs-commune peer engine
(ADR 0018). They fail in different ways - retail can be stale or wrong-variant; peers can be
scope-heterogeneous - so their *agreement* is a much stronger signal than either alone. This
also answers the deciders' concern that a single source is not enough.

## Decision

`crosscheck.py` publishes a flag automatically only when **both engines independently rate the
same line-item a severe overprice**, with guards:

- The line is `pending` in the retail engine (severe, unit-normalized) AND appears in the peer
  queue as `severe`.
- The peer median rests on at least `min_peers` (5) buyers.
- Cheaper-than-peers or high-only tiers do not qualify.

Survivors are confirmed through the existing ledger (`osint-curate`) with an evidence note
recording both ratios and the peer count, then promoted to `confirmed_flags.json` and published.
Every published flag keeps its source-order link, so any reader can verify it.

Flags that only one engine sees stay in the review queues as leads - notably the big-ticket
peer-only leads (construction/services), which have no retail cross-check and are scope-risky.

## Consequences

- The first autonomous batch is small and defensible: on the 13-day RM capture, 9 line-items are
  cross-confirmed severe by both engines (e.g. Recoleta harina retail 11x / peer 7.6x on n=13;
  El Bosque te retail 7.4x / peer 6.2x on n=218). Added to the 6 human-reviewed flags -> 15 live.
- Recall is deliberately sacrificed: the gate can only confirm lines the retail basket covers, so
  it is bounded by basket breadth. Growing the retail basket toward strong peer-only leads widens
  the publishable set - the intended next loop, not a reason to lower the bar.
- The same-supplier price-discrimination signal is not yet available: the parser does not extract
  a supplier identity (only `estado_proveedor`). Deferred until supplier extraction lands.
- Autonomous publishing remains reversible: confirmations live in the git-versioned ledger and can
  be dismissed and re-promoted.

## Alternatives considered

- **Publish every severe flag from either engine.** Rejected: single-source severe flags are
  frequently unit/scope artifacts; this is precisely what the cross-check filters.
- **Wait for per-flag human review.** Rejected by the deciders for the first batch (explicit
  "skip review" go-ahead); the two-method agreement is the substitute, and the human gate remains
  available for the rest.
- **Lower to `high` in both engines.** Deferred: start at the most defensible bar (severe+severe);
  can be revisited once the published set is validated in the field.
