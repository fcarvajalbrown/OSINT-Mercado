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

## Phase 1.5 — Parser enrichment
**Status:** Done

From `docs/research/2026-07-12-parser-improvement.md`: the parser extracts only ~4 of ~26
order fields and 3 of 14 item fields already present in the real payload — most of these are
"extract what is already there", not new API calls.

- Extract order `CodigoEstado` / `CodigoTipo` and **drop cancelled/rejected orders**
  (correctness: cancelled orders are currently counted as real purchases with real prices).
- Extract `Moneda` / `TipoMoneda` + `PorcentajeIva`; normalize amounts to CLP
  (UTM / UF / USD / EUR) and align net-vs-gross before any price comparison.
- Extract `CodigoCategoria` / `CodigoProducto` (UNSPSC) as a strong join key for basket
  matching — reusable by the mining data product.
- Before adding `schema.py` constants, open the official OC data-dictionary PDF manually to
  confirm exact field names.

_Shaped by: ADR 0005; parser-improvement research (2026-07-12)._

## Phase 2 — Basket & retail baseline engine
**Status:** Done

- Defined the v1 controlled basket of 19 commoditized SKUs with canonical
  keywords/model identifiers and units (`data/basket.json`).
- Curated manual-seed price list (versioned) as guaranteed baseline fallback
  (`data/seed_prices.json`) — 30 real retailer observations gathered via live
  web lookups, covering all 19 SKUs.
- Aggregator source integration deferred (no source chosen/verified yet); the
  engine is pluggable for one later, per ADR 0010.
- Reference price = median across available sources, anchored by the seed. Baseline-confidence
  flag (high/medium/insufficient) per SKU, computed by `build_baselines.py` into
  `data/baselines.json`.

_Shaped by: ADR 0002, 0004, 0010._

## Phase 3 — Matching & anomaly scoring
**Status:** Done

- CLP conversion (`mindicador.cl`, date-keyed committed `data/fx_rates.json`, business-day
  fallback) + net-vs-gross IVA gross-up landed first, per ADR 0009's deferral (ADR 0011).
- Controlled-basket classifier (`matcher.py`): per-SKU keyword rules over the item-identity
  fields, rapidfuzz only to disambiguate, developed test-first against a hand-labeled real RM
  sample (precision 1.0, documented recall) (ADR 0012).
- Overprice ratio + severity tiers (Watch >=1.5x, High >=2x, Severe >=3x) with a per-unit
  plausibility band routing unit mismatches to `unit_ambiguous`; matched lines with an
  insufficient baseline emit `needs_baseline` rather than a flag (ADR 0013).
- `osint-score` CLI emits a deterministic `data/pending_anomalies.json` with provenance
  (oc id, url, captured_at) and stable ids for the curation gate. Validated end-to-end on a
  real bounded RM capture.

_Shaped by: ADR 0002, 0005, 0006, 0007, 0009; new ADR 0011, 0012, 0013._

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
- Deploy over **SSH**: `rsync` the built static site to `public_html`, authenticating with the
  Hostinger SSH password (`SSH_HOSTINGER` in `.env` locally / a GitHub Actions secret in CI,
  non-interactive via `sshpass`). Needs the SSH host, port, and username (not secret) at build
  time. This replaces the native-Git-integration transport; write a superseding ADR then.
  (Consider migrating to SSH key auth later — more secure and cleaner to automate than a password.)

_Shaped by: ADR 0003 (deploy transport to be superseded at Phase 5)._

## Later phases (toward the PDF's grand vision)
**Status:** Not Started

- **Broaden the basket** progressively toward national / broad product categories.
- **Robust statistics** (MAD / IQR) in the anomaly core.
- **Cryptographic provenance** hashing of source data for tamper-evident reports suitable for
  oversight bodies (Contraloría).
- **Historical trends**: price-over-time views per SKU and per commune.

_Shaped by: ADR 0004, 0005, 0007._
