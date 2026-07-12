# OSINT-Mercado — Roadmap

Phase-based, not calendar-dated. Status per phase: `Not Started` / `In Progress` /
`Blocked` / `Done`. Each phase links back to the ADRs that shaped it. Vision and scope live
in `PRD.md`; decisions in `docs/adr/`.

---

## Phase 0 — Project setup & design docs
**Status:** In Progress

- PRD, ROADMAP, and ADRs written and committed.
- Brainstorming spec at `docs/superpowers/specs/2026-07-12-osint-mercado-webapp-design.md`.
- `git init` and initial commit.
- Repo scaffolding decided (pipeline package, data dir, frontend dir).

_Shaped by: ADR 0001, 0002, 0003, 0004, 0005, 0006, 0007._

## Phase 1 — Data ingestion skeleton
**Status:** In Progress

- Register a ChileCompra / Mercado Público API ticket (free); store as a CI secret. (Done)
- Confirm the exact OC endpoint, params, and response schema from a real captured fixture.
  (Done — see `docs/api/ordenes-de-compra-schema.md`.)
- Build a versioned `comuna → CodigoOrganismo` list for the 52 Región Metropolitana
  municipalities, each code verified against a real API response (ADR 0008).
- Ingest by-organism: for each RM municipal code, query `fecha + CodigoOrganismo`, fetch
  detail per order (throttled, backoff on 429), parse items and prices, persist normalized
  per-line-item data with provenance.
- First GitHub Actions scheduled workflow (daily) running ingestion end-to-end.

_Shaped by: ADR 0001, 0002, 0004, 0008._

## Phase 2 — Basket & retail baseline engine
**Status:** Not Started

- Define the v1 controlled basket (~15–25 commoditized SKUs) with canonical
  keywords/model identifiers and units.
- Curated manual-seed price list (versioned) as guaranteed baseline fallback.
- Aggregator source integration where coverage exists; targeted per-product scrapes for the
  rest.
- Reference price = median across available sources, anchored by the seed. Baseline-confidence
  flag per SKU.

_Shaped by: ADR 0002, 0004._

## Phase 3 — Matching & anomaly scoring
**Status:** Not Started

- Controlled-basket classifier: per-SKU keyword/model rules + fuzzy fallback, developed
  test-first against a labeled sample.
- Per-unit normalization (not per-pack).
- Overprice ratio + severity tiers (configurable). Only score when baseline confidence is
  sufficient; otherwise mark "needs baseline" rather than flag.
- Emit `pending` anomalies with provenance fields (source id, url, captured_at).

_Shaped by: ADR 0002, 0005, 0006, 0007._

## Phase 4 — Curation workflow
**Status:** Not Started

- Review artifact listing pending flags for confirm/dismiss with an optional note.
- Confirmed flags promote into the published dataset; dismissed archived with reason.
- Re-run stability: same inputs → same flags.

_Shaped by: ADR 0006, 0007._

## Phase 5 — Static dashboard & deploy
**Status:** Not Started

- Static frontend: filter confirmed flags by commune / category / severity; each row shows
  unit-paid vs baseline, overprice %, severity, and the official source link.
- Build in GitHub Actions; emit static output.
- Hostinger native Git integration auto-deploys to `public_html` on push (Business shared).

_Shaped by: ADR 0003._

## Later phases (toward the PDF's grand vision)
**Status:** Not Started

- **Broaden the basket** progressively toward national / broad product categories.
- **Robust statistics** (MAD / IQR) in the anomaly core.
- **Cryptographic provenance** hashing of source data for tamper-evident reports suitable for
  oversight bodies (Contraloría).
- **Historical trends**: price-over-time views per SKU and per commune.

_Shaped by: ADR 0004, 0005, 0007._
