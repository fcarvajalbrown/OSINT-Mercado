# 0018 - Peer-price comparison engine (market as its own baseline)

Status: Accepted
Date: 2026-07-13
Deciders: Felipe Carvajal Brown

## Context

The controlled-basket engine (ADR 0005/0013) compares each purchase to a hand-researched
retail baseline. Two structural limits follow: it only covers commodities someone has
baselined (~21% of RM line-items), and those are the *low-value* commodities. The large
public-money waste - construction, professional services, equipment, events, health services -
has no retail price and is therefore invisible. Hand-curating baselines does not scale to the
whole catalogue.

A second signal is available for free inside the data itself: **what every other public buyer
paid for the same catalogued product**. Mercado Publico line-items carry a UNSPSC product code,
and most codes are bought by many organisms. The market can be its own baseline.

## Decision

Add a parallel **peer-price** engine (`peers.py` + `osint-peer-score`) that runs alongside, not
instead of, the basket engine:

1. Normalize every captured line to CLP gross (IVA-aligned, currency-converted), reusing the
   basket engine's `fx` + `gross_up`.
2. Group by UNSPSC product code; for each code with at least `MIN_PEERS` (5) observations compute
   the **median** and **MAD** (median absolute deviation - robust to the very outliers we hunt).
3. Flag a line only when it is BOTH statistically extreme (robust z = 0.6745*(x-median)/MAD >=
   `Z_THRESHOLD` 3.5) AND materially above the median (`ratio` >= `MIN_RATIO` 1.5). Cheaper-than-
   peers is never flagged. When MAD is 0 (identical peers) the robust-z test is skipped and only
   the ratio applies.
4. **Plausibility cap** (`RATIO_CAP` 12x): above it the line is almost never a real overprice but
   a scope/unit artifact - a whole contract or a bulk total recorded under a per-unit product code
   (e.g. a $30M printing contract sharing "Impresion de papeleria" with $170 per-form jobs). Those
   are routed out rather than published.
5. Emit `data/peer_pending.json` with provenance and stable ids, ready for the same curation gate.

## Consequences

- Coverage jumps from the basket's ~21% of line-items to the whole catalogue, and specifically to
  the high-value spend that matters. On six RM days the engine produced ~99 capped leads across 31
  communes (vs ~51 commodity candidates), including construction (n=95 peers), training and event
  contracts, hardware and toner - none reachable by the basket.
- **Peer flags are investigative leads, not proof.** Scope heterogeneity within a product code (a
  larger project priced under the same code as a smaller one) survives the cap, so a peer flag means
  "priced well above peers for the same code - worth investigating", and every one must pass human
  review (ADR 0006) before publication. The engine writes to its own queue and does not yet feed the
  published site; curation/site integration is a later, reviewed step.
- The approach scales to national coverage with no extra baseline research: more buyers only sharpen
  the peer medians.
- Robust statistics (median/MAD) rather than mean/stddev keep a few extreme lines from moving the
  baseline, which the raw data (contracts sharing codes with unit jobs) makes essential.

## Alternatives considered

- **Mean + standard deviation.** Rejected: non-robust; the contract-vs-unit outliers that motivate
  the engine would inflate the mean and hide real overprices.
- **No plausibility cap, lean on curation.** Rejected: the uncapped output was dominated by
  100000x scope artifacts, drowning the credible 1.5-12x band and making the queue unreviewable.
- **Only peer comparison, retire the basket.** Rejected: the basket is precision-first and
  publish-ready for its commodities; peer flags need heavier review. They are complementary.
- **Per-unit normalization inside peer groups (ADR 0017 style).** Deferred: services/contracts have
  no parseable pack/size, so normalization cannot resolve scope heterogeneity here; the cap plus
  robust stats plus mandatory review is the v1 guard.
