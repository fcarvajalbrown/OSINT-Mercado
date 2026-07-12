# 0010 — Basket & retail baseline: seed-only v1, pluggable multi-source design

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

Phase 2 needs a retail baseline engine for the v1 controlled basket (PRD section 4).
The PRD calls for "a hybrid of sources — price aggregators where coverage exists,
targeted per-product scrapes otherwise, and a curated manual-seed price as guaranteed
fallback," with the reference price as the median across sources, anchored by the seed.
No aggregator or scrape source has been chosen or verified against a real response yet
(per CLAUDE.md's never-guess rule, we do not build a client against an unverified API
shape), so building that integration now would mean guessing at a data format.

## Decision

Ship Phase 2 with the manual-seed source only. Every price observation is a real,
currently-live retailer listing found via web search/fetch and recorded with its
retailer name, price, observation date, and source URL — no invented numbers.

The engine is designed so an aggregator/scraper source can be added later without
changing its core logic: `compute_reference` takes a flat list of `PriceObservation`
regardless of which source produced them. Adding a new source means writing a loader
that emits the same shape and concatenating its output with the seed observations before
computing the reference price; that loader is a future ADR once a concrete source is
chosen and its data format verified against a real response.

Storage is split into two versioned JSON files: `data/basket.json` (the basket
definition: SKU id, canonical name, keywords, unit) and `data/seed_prices.json` (price
observations, keyed by `sku_id`). Splitting keeps git diffs clean per ADR 0004 — a price
refresh does not touch basket definitions, and vice versa. A third file,
`data/baselines.json`, is a materialized snapshot produced by `build_baselines.py` from
the other two — the median reference price and confidence tier per SKU, ready for Phase 3
to read directly without recomputing.

Confidence is a three-tier signal computed from observation count, freshness, and price
spread, not a binary "has a seed price or doesn't":

- `high` — >=2 observations, freshest <=90 days old, spread ratio <=0.25
- `medium` — >=1 observation, freshest <=90 days old (below the `high` bar)
- `insufficient` — 0 observations, or all observations >90 days old

`reference_price_clp` is the median across all observations for a SKU. For v1 (seed-only)
this is the median of seed observations; once other sources exist, seed observations
continue to participate directly in that median rather than being a mere fallback — this
is what "anchored by the seed" means going forward.

Two data-quality judgment calls came up while curating `data/seed_prices.json` and are
recorded here since they shape how the committed baseline should be read:

- Out-of-stock retailer listings (price displayed on a live page, but the item not
  currently purchasable) are included as valid observations — the price is still a real,
  currently-displayed market reference point.
- A price observation for `extintor_pqs_6kg` from a retailer selling a 75%-concentration
  PQS fill (rather than the standard full-charge product the other listings describe) was
  excluded as not a comparable commodity, even though it was a real, confirmed price.

## Consequences

- No new external network dependency or secret in this phase (no aggregator API key, no
  scraper). Lower risk, faster to ship correctly.
- Some basket SKUs ended up with only 1 observation (several: papel resma, pilas AA,
  pendrive, guantes, and all 4 limpieza SKUs), computing to `confidence == "medium"`.
  Two SKUs (`zapatos_seguridad_puntera_acero`, `mascarillas_quirurgicas_caja50`) have 2
  observations but a wide price spread between retailers, also landing at `"medium"`
  rather than `"high"` — an honest signal, not a gap papered over.
- Phase 3 must treat `"insufficient"` baselines as "needs baseline", not score them, per
  the PRD's baseline-confidence guardrail. No SKU in the v1 basket landed at
  `"insufficient"` — every SKU has at least one real observation.
- Adding an aggregator/scrape source later is additive: a new loader function plus
  concatenation, no change to `compute_reference` or the confidence formula.
- Four SKUs' seed observations (`cloro_lavandina_4l`, `alcohol_gel_1l`, `escoba_fibra`,
  `basurero_plastico_60l`) cite a retailer category-listing page URL rather than an
  individual product-detail page, since the product pages themselves blocked automated
  fetching. The price was still confirmed live on the cited page; the provenance link is
  just less precise than the other SKUs'. Acceptable for a v1 baseline input (not itself a
  published public-facing flag citation — that stricter standard applies to Phase 3/4
  order provenance per ADR 0007, not to baseline sourcing).

## Alternatives considered

- **Build an aggregator/scraper integration now.** Rejected: no concrete source has been
  chosen or verified against a real response; building against a guessed API shape
  violates the project's never-guess convention.
- **Single price per SKU, binary confidence.** Rejected: loses the freshness/spread
  signal for no implementation savings, and would need rework the moment a second
  source (or a second seed observation) exists.
- **One combined JSON file for basket definition + price observations.** Rejected: a
  price refresh would touch the same file as basket-definition edits, muddying git diffs
  that are supposed to serve as an audit trail (ADR 0004).
