# 0023 - Conservative publish-verification filter (two-gate autonomous publishing)

Status: Accepted
Date: 2026-07-14
Deciders: Felipe Carvajal Brown

## Context

The cross-confirmation gate (ADR 0020) was necessary but not sufficient: on a live autonomous
batch, bundles (a trophy kit read as a pendrive), dispensers (a soap dispenser read as soap),
bigger containers (a 4-gal tineta read as a gallon), and quote-request lines still passed "both
engines agree" and produced false accusations that had to be reverted (ADR 0021). The deciders
nonetheless want the site to keep filling *unattended* ("upload checked products immediately as
feasible"), so the automated stand-in for a human's final look must encode the actual failure modes.

## Decision

Add `verify.py`, a strict second gate applied after cross-confirmation, with two levels:

- `is_publishable` - a flag qualifies only if it is a `pending` severe/high overprice with a
  sane ratio, an independent method (the peer engine) also flagged it, the SKU's own keyword
  actually appears in the item's especificacion, AND the espec carries none of the learned
  **red-context** signals (dispenser, kit/bundle, tineta/multi-gallon container, quote-request,
  industrial/appliance variant). It rejects on any doubt.
- `is_auto_publishable` - for UNATTENDED publishing, additionally requires the SKU to be in a
  **tier-stable** allowlist (papel resma, pendrive, huincha, corchetera, cartulina, opalina,
  nueces, toner, ...). Tier-variable SKUs (flavored vs plain te, industrial vs consumer escoba,
  premium vs basic cafe/pens, appliances, footwear, paint) can pass `is_publishable` yet still be
  a legitimately-pricier variant, so they are never auto-published - only surfaced for human review.

Autonomous publishing therefore runs three gates in series: retail baseline overprice -> peer
agreement -> `is_auto_publishable`. Tier-variable and red-context flags accumulate in the review
queue for a human pass.

## Consequences

- On the 13-day capture the filter passes 5 of 157 pending and rejects 152 - and of the 5, only the
  tier-stable ones auto-publish; the tier-variable te/escoba are correctly held. Recall is
  sacrificed hard for precision, which is the right trade for public accusations.
- The tier-stable allowlist is a maintained judgement list, not an inferred property; new SKUs
  default to *not* auto-publishable until explicitly added, which fails safe.
- Human review is not eliminated, it is *targeted*: the queue a person sees is the tier-variable and
  red-context residue, already stripped of the clearly-clean and the clearly-false.

## Alternatives considered

- **Publish everything that cross-confirms.** Rejected: that is exactly what produced the reverted
  false accusations.
- **Infer tier-stability automatically.** Deferred: unreliable (a "te" keyword can't tell flavored
  from plain); an explicit allowlist that fails safe is more honest than a heuristic that fails open.
