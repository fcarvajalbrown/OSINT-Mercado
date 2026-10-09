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
**Status:** Done (basket subsequently grown to 75 SKUs)

- Defined the controlled basket of commoditized SKUs with canonical
  keywords/exclude rules and units (`data/basket.json`). Started at 19 SKUs;
  grown to **75 SKUs across five categories** (Oficina y computación, Seguridad
  y EPP, Limpieza, Ferretería y herramientas, Alimentos y abarrotes),
  data-driven from real RM line-item frequency. This lifted match coverage on
  the 2026-07-09 capture from 1.9% to 21.1% of line-items.
- Curated manual-seed price list (versioned) as guaranteed baseline fallback
  (`data/seed_prices.json`) — **123 real, web-verified retailer observations**
  (each with a source URL), giving scorable baselines for 74 of 75 SKUs. No
  prices invented; unverifiable retailers omitted rather than guessed.
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
**Status:** Done

- Git-native decisions ledger (`data/curation_decisions.json`) keyed by stable anomaly id,
  driven by the `osint-curate` CLI (`status` / `confirm` / `dismiss` / `promote`) (ADR 0014).
- Confirmed flags promote into the published `data/confirmed_flags.json` (Phase 5 input);
  dismissed archived with reason into `data/dismissed_flags.json`. Only reviewable statuses
  (`pending`, `unit_ambiguous`) are curatable; `needs_baseline` is excluded.
- Pure `apply_decisions` is deterministic: same pending + ledger -> identical published output.

_Shaped by: ADR 0006, 0007; new ADR 0014._

## Phase 5 — Static dashboard & deploy
**Status:** Done (deploy automation built; first live push pending the SSH credential + go-ahead)

- Self-contained static frontend (`frontend/`, no external deps): filters confirmed flags by
  commune / category / severity; each row shows unit-paid (gross CLP) vs baseline, overprice %,
  severity, and the official Mercado Público source link. Empty-state until curation confirms.
- `osint-build-site` builds `dist/` from `data/confirmed_flags.json` + basket (adds
  canonical name, category, overprice %). Built in CI (`.github/workflows/build-deploy.yml`).
- Deploy over SSH: `scripts/deploy.sh` mirrors `dist/` to `public_html` with
  `rsync -az --delete`, authenticating with an SSH private key (`SSH_KEY` secret; host/port/
  user/path as non-secret CI variables). `workflow_dispatch`-only + `--dry-run`; env validated
  before any network call. Transport supersedes ADR 0003 (ADR 0015); key auth per ADR 0025.
- **Pending:** the user's explicit go-ahead before the first live publish to the public site.

_Shaped by: ADR 0003 (transport superseded), 0004, 0007; new ADR 0015._

## Phase 6 — Convenio Marco normative engine
**Status:** Done (engine + lead queue; leads pending human curation)

The most defensible comparison: could the organism have bought this cheaper under the framework
agreement it was bound to consider? (ADR 0024.)

- `cm_catalog.py` fetches the weekly CM index, reads every inner CSV (incl. the multi-CSV zips),
  keeps METROPOLITANA + NACIONAL rows with a valid 8-digit UNSPSC + positive net price, dedups, and
  caches a committed `data/cm_catalog.parquet` (434,782 rows, 471 codes).
- `cm_scoring.py` matches same-product rows by >=2 distinctive-token overlap within the shared code
  (never the code alone; espec-only, not the category label, per ADR 0021), normalizes both sides
  per g/ml/m/each (`units.parse_any_size`), and measures the paid price against the median matched
  CM price. Net-to-net (CM PRECIO EN TIENDA confirmed net of IVA). Band [1.5x, 15x], min 3 refs.
- `cm_verify.py` tags each lead clean-or-not (bundle / red-context / pack-ambiguity, screening the
  CM reference too). `osint-cm-score` emits `data/cm_pending.json` with provenance + CM evidence.
- Over 27 RM captures: 4,529 line-items under a CM code -> 356 size-normalized region-matched
  same-product leads -> 151 clean first-pass. Investigative leads for the human gate (ADR 0006),
  never auto-published.

_Shaped by: ADR 0005, 0006, 0013, 0017, 0018, 0021, 0022; new ADR 0024._

## Phase 7 — Integrity layer on Stellar (Find Your Way hackathon)
**Status:** In Progress

- `osint-anchor` anchors the published flags on the Stellar testnet: one transaction per
  publication carries the SHA-256 digest of every flag as a hash memo and a `manage_data` entry
  (ADR 0026). Each flag also commits to the hash of its source order line as captured (ADR 0027).
  First anchor: ledger 5111255, 18:04 Chile time (21:04 UTC), transaction
  `ad864ba7a7a7afd3c70092b176eb0fc6e5d5694da18f698f99884ecabab95e8f`, 4 flags, 4 source lines.
- The dashboard recomputes every hash in the browser and checks it against Horizon testnet; a
  changed value turns its row "Alterado". `tests/js/parity.mjs` proves Python and browser hashes
  agree byte for byte and that a changed price is caught; it runs inside pytest.
- Deployed to osint-mercado.cl over scp (no rsync on the dev machine); the previous live files
  are kept on the server in `domains/osint-mercado.cl/backup-pre-stellar/`.
  `published/flags.json` was republished with `source_sha256`, so the refresh cron (ADR 0016)
  serves the anchored set.
- **Finding:** every published flag's official link (ADR 0007) now opens Mercado Público's
  "No Tiene los Permiso suficientes para visualizar la ficha" dialog for a reader who is not
  logged in (checked on all 4 published orders). The provenance link no longer lets the public
  verify anything on its own. Addressed by mirroring the API record (ADR 0028).
- **Rule:** every change to the published set needs `osint-anchor publish` and a redeploy of
  `anchors.json`, or the new rows show as not anchored.
- Backfill of purchase orders from 13 July 2026 onwards runs with `scripts/ingest_range.sh`
  (the GitHub Actions ingest was removed); new anomalies still go through the curation gate.

_Shaped by: ADR 0007, 0016; new ADR 0026, 0027, 0028._

## Later phases (toward the PDF's grand vision)
**Status:** Not Started

- **Broaden the basket** progressively toward national / broad product categories.
  (In progress: grown from 19 to 75 SKUs across five categories; next steps are
  a second-source retail aggregator for baseline robustness, filling the single
  remaining `needs_baseline` SKU, and adding more single-observation SKUs' second
  sources so more baselines reach `high` confidence.)
- **Archive the source order in our own store** (not just a link out). Each published flag
  must stay verifiable even when the official Mercado Público page is unreachable or a reader
  cannot access it. Snapshot the relevant order payload (or a rendered copy) into the versioned
  store / site data so the evidence travels with the flag. Extends ADR 0007 (provenance is
  currently a link + capture timestamp only). **Priority: high** — a watchdog claim that can't
  be checked because the source link is down is unacceptable.
- **Robust statistics** (MAD / IQR) in the anomaly core.
- **Cryptographic provenance** hashing of source data for tamper-evident reports suitable for
  oversight bodies (Contraloría), building on the archived payload above.
- **Historical trends**: price-over-time views per SKU and per commune.

_Shaped by: ADR 0004, 0005, 0007._
