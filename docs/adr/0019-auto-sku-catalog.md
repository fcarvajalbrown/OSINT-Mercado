# 0019 - Auto-SKU catalog (data-derived, not hand-curated)

Status: Accepted
Date: 2026-07-13
Deciders: Felipe Carvajal Brown

## Context

The controlled basket (ADR 0005) hand-curates a few dozen commoditized SKUs with
researched retail baselines. It is precision-first but only ~13% of RM line-items match
it, and growing it means a human researching retail prices SKU by SKU - it does not scale
to the whole catalogue. A purchase we cannot match is coverage lost, and hand-reviewing
~1,700 unmatched codes to decide which to add is not viable.

## Decision

Invert the model for coverage: **every distinct product a public buyer purchases becomes an
SKU automatically.** `catalog.py` (`osint-catalog`) scans the captures and builds a versioned
`data/product_catalog.json`, keyed by UNSPSC product code (or, when a line carries no code,
by its normalized product name). No manual review, no retail research. The catalog is
monotonically growing (a code seen once is an SKU forever) and merges across days.

The auto-SKUs are baselined by the **market itself** via the peer engine (ADR 0018): the
reference price for a code is the median of what other communes paid for it. The hand-curated
basket is retained for the commodities where an external retail baseline exists and matters.

## Consequences

- On 13 RM days the catalog holds **2,654 auto-SKUs** (1,754 with a UNSPSC code, 900 name-only).
  368 have >=5 orders and are peer-baseline-able, covering **61% of all line-items** vs the
  basket's ~13% - with zero manual curation.
- **Single-source limitation (deliberate, and to be mitigated).** An auto-SKU's baseline is the
  peer median on Mercado Publico alone: it is self-referential and cannot catch market-wide
  overpricing (if every commune overpays, the median looks normal). This is the price of
  coverage-without-research. Mitigation is a follow-up: cross-check against the retail basket
  where they overlap, and add a second commune-vs-commune reference (best-price benchmark +
  same-supplier price discrimination) - kept internal to Mercado Publico rather than an external
  aggregator, per the deciders' preference.
- Auto-SKUs never publish on their own: peer flags are investigative leads that pass the human
  curation gate (ADR 0006) before any publication.

## Alternatives considered

- **Hand-review the ~1,700 unmatched codes.** Rejected by the deciders: does not scale and defeats
  the point; "one purchase order without an SKU = an SKU added automatically".
- **Only the controlled basket.** Rejected: caps coverage at ~13% and at low-value commodities.
- **Name-only keying for everything.** Rejected: the UNSPSC code is a stronger, language-stable
  join key; name-keying is the fallback only for code-less lines.
