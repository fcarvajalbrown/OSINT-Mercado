# Phase 2 — Basket & Retail Baseline Engine: Design

> Brainstormed 2026-07-12. Implements ROADMAP.md's Phase 2. Feeds Phase 3 (matching/scoring).

## Context

Phase 1/1.5 produce a normalized per-line-item dataset with raw currency/tax fields and
UNSPSC codes, but no retail reference prices exist yet. Phase 2 must define the v1
controlled basket (~15-25 commoditized SKUs) and build the engine that produces a
reference price and a confidence signal per SKU, so Phase 3 can compute an overprice
ratio against real order line-items.

## Goals

- Define a v1 basket of commoditized SKUs with canonical keywords/units (consumed later
  by the Phase 3 matcher, per ADR 0005).
- Build a versioned, curated manual-seed price list from real retail observations (no
  invented numbers).
- Compute a reference price (median of observations) and a per-SKU confidence tier.
- Design the observation-collection step so a future aggregator/scrape source can be
  added without changing the reference-price/confidence logic.

## Non-goals (deferred)

- Any aggregator API or scraper integration — no such source has been chosen/verified
  yet. The interface is designed to accept one later; none is built now.
- The basket-matcher itself (turning a messy order line-item into a `sku_id`) — that is
  Phase 3, per ADR 0005.
- CLP currency conversion / net-vs-gross alignment — Phase 3 prerequisite, per ADR 0009.
- Deciding the minimum confidence tier required to score a flag — Phase 3 decision;
  Phase 2 only computes and exposes the tier.

## Architecture

Two new flat modules, matching the existing `src/osint_mercado/` style:

- **`basket.py`** — dataclasses `Sku` and `PriceObservation`; loaders
  `load_basket(path) -> list[Sku]` and `load_seed_observations(path) -> list[PriceObservation]`.
  Pure I/O + parsing, no computation, mirroring `parser.py`'s "load raw structure" role.
- **`baseline.py`** — `compute_reference(observations: list[PriceObservation], as_of: date) -> Baseline`.
  Pure function: given all observations for one SKU and a reference date, returns the
  median reference price and a confidence tier. No I/O, so it is trivially unit-testable
  with synthetic observations. `as_of` is passed in by the caller (the pipeline entry
  point), following the same injectable-time convention `ingest.py` already uses for
  `captured_at` — never `datetime.now()` called inside the pure function itself.

**Pluggability.** `compute_reference` takes a flat `list[PriceObservation]` regardless of
origin. For v1, the only producer is `basket.load_seed_observations`. A future
aggregator/scraper source is just another function that returns the same
`PriceObservation` shape; its output gets concatenated with the seed observations before
calling `compute_reference`. No change to the median/confidence logic when that source is
added — it gets its own ADR at that time (per CLAUDE.md, once a concrete source is chosen
and its data format verified against a real response).

This decision (seed-only v1, storage split, confidence formula) gets its own ADR —
`docs/adr/0010-basket-baseline-seed-only-v1.md` — written during implementation.

## Data model

```python
@dataclass(frozen=True)
class Sku:
    sku_id: str
    canonical_name: str
    keywords: list[str]
    unit: str
    unspsc_category_code: int = 0
    unspsc_product_code: int = 0

@dataclass(frozen=True)
class PriceObservation:
    sku_id: str
    retailer: str
    price_clp: float
    observed_at: str  # ISO date, e.g. "2026-07-10"
    url: str

@dataclass(frozen=True)
class Baseline:
    sku_id: str
    reference_price_clp: float
    confidence: str  # "high" | "medium" | "insufficient"
    n_observations: int
    freshest_observed_at: str
    spread_ratio: float  # (max - min) / median; 0.0 if <2 observations
```

## Storage: two versioned JSON files

- **`data/basket.json`** — list of `Sku` records. Stable; rarely changes once curated.
- **`data/seed_prices.json`** — list of `PriceObservation` records, keyed by `sku_id`.
  Refreshed periodically as prices are re-checked.

Splitting these keeps git diffs clean per ADR 0004 (a price refresh doesn't touch basket
definitions, and vice versa). Field names are the dataclass field names directly (JSON
keys = snake_case field names) — this is our own internal format, fully controlled, so it
does not need a `schema.py`-style external-field-name constants module (that pattern
exists specifically for unstable third-party API field names we must verify against real
fixtures, per CLAUDE.md).

## Confidence formula

Computed in `compute_reference`, using the freshest observation's age (from `as_of`) and
the price spread across observations:

- **`high`** — >=2 observations, freshest <=90 days old, spread ratio <=0.25
- **`medium`** — >=1 observation, freshest <=90 days old (doesn't clear the `high` bar)
- **`insufficient`** — 0 observations, or all observations >90 days old

`reference_price_clp` = median of all observation prices (seed observations directly
participate in the median, not merely a fallback — this is what "anchored by the seed"
means once other sources exist; for v1, seed is the only source so the median equals the
median of seed prices).

## v1 basket (19 SKUs)

Informed by: PRD examples (toner, paper, PPE), the real captured fixture (safety boots,
reflective vests), and a news/Contraloría/ChileCompra web search confirming (a) no
existing public tool does a standing, per-order, source-linked audit of municipal
commoditized-goods purchases — CIPER/Contraloría coverage is almost entirely land-deal
and pandemic-era shell-company stories, and ChileCompra's own Observatorio reports are
aggregate self-monitoring, not per-transaction public disclosure — and (b) ChileCompra's
own 2026 Observatorio flags *computadores* and *insumos de oficina* as its
worst/deteriorating overspend categories nationally, which shaped adding basic computer
peripherals to the basket.

**Office/print consumables**
1. Toner HP CF283A (LaserJet Pro M125/M225 series) — unidad
2. Toner HP CE285A (LaserJet P1102 series) — unidad
3. Papel resma carta 75g — resma (500 hojas)
4. Papel resma oficio 75g — resma (500 hojas)
5. Pilas alcalinas AA (blister x4) — blister
6. Pilas alcalinas AAA (blister x4) — blister
7. Pendrive USB 16GB — unidad
8. Mouse óptico USB — unidad
9. Teclado USB estándar — unidad
10. Cartucho de tinta HP 664 negro — unidad

**PPE / seguridad**
11. Zapatos de seguridad con puntera de acero — par
12. Chaleco reflectante de seguridad — unidad
13. Guantes de látex/nitrilo desechables (caja x100) — caja
14. Mascarillas quirúrgicas desechables (caja x50) — caja
15. Extintor PQS 6kg — unidad

**Limpieza / insumos básicos**
16. Cloro/lavandina genérico (botella 4L) — botella
17. Alcohol gel 1L — botella
18. Escoba de fibra — unidad
19. Basurero plástico 60L — unidad

(Dropped the earlier-flagged near-duplicate "resma A4" candidate, since carta + oficio
already cover the paper category without redundancy.)

## Seed price population

For each of the 19 SKUs, real observations (retailer, price, URL, date) will be gathered
via live WebSearch/WebFetch against real Chilean retailer listings during implementation
— never invented. Target 2-3 observations per SKU where available (some SKUs, e.g.
generic PPE, may only yield 1). The resulting `seed_prices.json` is reviewed before
commit.

## Testing approach (TDD, per CLAUDE.md)

- `tests/test_basket.py` — loading `basket.json`/`seed_prices.json` fixtures into
  dataclasses; malformed/missing-field handling.
- `tests/test_baseline.py` — `compute_reference` against synthetic observation sets
  covering all three confidence tiers, the median calculation (even/odd counts), and the
  spread-ratio edge case of a single observation (spread_ratio = 0.0).
- Real `data/basket.json` + `data/seed_prices.json` committed as the actual v1 dataset,
  not just test fixtures — Phase 3 consumes these directly.

## Open items resolved during this brainstorm

- Retail sources: manual-seed only for v1; pluggable interface for later (user decision).
- Basket definition: I propose, user approves (done above).
- Confidence basis: observation count + freshness + spread, not binary (user decision).
- Seed data entry: live WebSearch/WebFetch lookups against real retailers, reviewed
  before commit (user decision).
