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
- `stellar.html` (linked from the dashboard header) walks a viewer through the anchor in six
  steps for the demo video: a flag and its captured order line, their canonical JSON and SHA-256
  hashes, the batch digest, the live Horizon transaction side by side with the local digest, an
  in-browser price edit that turns the row "Alterado", and the account's full anchor history
  fetched from Horizon (4 flags at ledger 5111255, 2 at ledger 5111652). Hashing now lives in
  `frontend/shared.js`, loaded by both pages, so a deploy must ship `shared.js` with `app.js`.
  `tests/js/stellar.mjs` runs the page in a vm with a stubbed DOM and Horizon. Not deployed yet.
- Deployed to osint-mercado.cl over scp (no rsync on the dev machine); the previous live files
  are kept on the server in `domains/osint-mercado.cl/backup-pre-stellar/`.
  `published/flags.json` was republished with `source_sha256`, so the refresh cron (ADR 0016)
  serves the anchored set.
- **Finding:** every published flag's official link (ADR 0007) now opens Mercado Público's
  "No Tiene los Permiso suficientes para visualizar la ficha" dialog for a reader who is not
  logged in (checked on all 4 published orders). The provenance link no longer lets the public
  verify anything on its own. A mirror of the API record is proposed (ADR 0028, 0029), not decided; nothing from it is deployed.
- After the fair-price study (`docs/research/fair-price-comparison.md`), San Bernardo
  (corchetera, a Convenio Marco order at catalogue price against a smaller-stapler baseline) and
  Pirque (huincha, mixed-grade baseline) were withdrawn through the ledger. Live set: Buin and
  El Bosque, re-anchored at ledger 5111652 and verified on the live files. Open from the study:
  reword Buin to the Convenio Marco comparison, confirm a Piwen 1 kg retail price for El Bosque,
  confirm whether the Alcaplus pendrive price includes IVA, and refresh seed prices observed
  12-13 July before they pass the 90-day limit.
- **Mirror direction (Felipe):** mirror the official order PDF, not only the API record. Order of
  work per order: download the PDF, hash the exact downloaded bytes immediately (that hash is what
  gets anchored), then OCR it and save the text. Open check before building: whether the PDF can
  be fetched without a session, given the login wall on the order pages. ADR 0028/0029 stay
  Proposed until this is settled with Felipe.
- Published per ADR 0031: 2 reviewed flags plus 3,893 lead rows (3,876 in review, 17 decided),
  sealed with the review-queue digest (ADR 0030) at ledger 5112074. Data-quality items now
  public: about 71 leads with no comuna and about 102 with codes or symbols in the comuna field,
  shown as "Comuna sin identificar"; name variants such as "Calera De Tango" and "Til Til".
- **Open for Felipe:** leads 90f5cb11bca6ecd9 (Conchali, escobillones) and a311ef975d16cf90
  (Vitacura, escobillon) are "confirm" in the ledger but not in `confirmed_flags.json`. They are
  published as "En revision" with no estimate until he decides.
- **Rule:** every change to the published set needs `osint-anchor publish` and a redeploy of
  `anchors.json`, or the new rows show as not anchored.
- Backfill of purchase orders from 13 July 2026 onwards runs with `scripts/ingest_range.sh`
  (the GitHub Actions ingest was removed), newest-first and as a single process; new anomalies
  still go through the curation gate.
- **API quota (official, chilecompra.cl/api):** 10,000 requests per day per ticket, not
  modifiable; one ticket per person; IP monitoring; abuse can mean suspension or a permanent
  block; large downloads recommended between 22:00 and 07:00. One day of RM data costs at least
  ~400 requests (52 listings plus one detail per listed order; median 340 municipal orders kept
  per day over 27 captured days), so the quota covers roughly 16-25 days of data per calendar
  day. Never run two ingests in parallel on one ticket: simultaneous requests already drew a 429
  (ADR 0008), and two processes can exceed the daily cap in about three hours.
- **API client gaps (found against published rate-limit practice):** no persisted daily request
  counter or stop before the 10,000 cap; no circuit breaker (after 4 retries an order is skipped
  and the run keeps firing); no retry on 5xx or timeouts; a day with skipped orders is still
  written and then skipped forever by `ingest_range.sh`, with the gaps unrecorded; no response
  cache, so a killed or restarted day re-fetches everything (four mid-day kills on 2026-10-09
  spent quota for nothing); no jitter. Already right: Retry-After honoured, exponential backoff,
  session reuse, User-Agent, 60 s timeout, 0.25 s pacing. Fixed by `fetcher.py` (cache, rolling
  24 h log stopping at 9,000, jittered retries on 429/5xx/timeouts, breaker after 5 consecutive
  failures, every retry logged) and per-day `oc_items_<fecha>.gaps.json`.
- **Measured 429 behaviour (single process, 90 s windows):** at 0.25 s pacing, 88 requests gave
  54 orders with 28 retries (32%, all HTTP 429, no Retry-After header); at 1.0 s, 58 requests
  gave 42 orders with 14 retries (24%). The limit is not plain spacing and is undocumented.
  1.0 s is the default (`PACE` overrides): about 2,300 requests per hour stays under the 9,000
  stop for three hours. Stop runs with `scripts/stop_ingest.ps1`, never a command-line match that
  can kill its own shell.
- **Hostinger caches static assets for 7 days** (`Cache-Control: public, max-age=604800` on css and
  js; html has no cache header). After the redesign deploy, browsers that had seen the old site
  kept the old stylesheets and the new pages rendered unstyled. The build now appends
  `?v=<sha256 prefix>` to every local css, js and svg link (`fingerprint_assets`), so each deploy
  loads fresh files. Data files are fetched with `cache: "no-store"`.

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
