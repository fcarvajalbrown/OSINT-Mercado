# OSINT-Mercado — Roadmap

Phase-based, not calendar-dated. Status per phase: `Not Started` / `In Progress` /
`Blocked` / `Done`. Each phase links back to the ADRs that shaped it. Vision and scope live
in `PRD.md`; decisions in `docs/adr/`.

---

Finished phases live in `docs/ROADMAP-HISTORY.md`.

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
- **Automatic estimate (ADR 0032) on real data, not yet published.** Of 3,893 lead rows, 1,079
  have 10 or more comparables: 689 normal, 189 high, 192 overprice, 9 probable data errors. The
  top overprice cases are format mismatches, not prices: a San Pedro promotional print job at
  $587,500 against a $773 reference (+75,903%), a 72-colour marker set against single markers.
  997 of the 1,079 fall back to the median because the group CV is above 25%, which by the CGU
  rule means the group is not homogeneous. Of the 82 homogeneous ones, the overprice cases still
  include likely pack-versus-unit lines (copy paper, water). The CV test checks the comparables,
  not the lead line's own format. Not sealed or deployed until a format gate exists.
- **Format gate on the automatic estimate (pack/size parser + CGU 25% CV), measured.** 8.3 s for
  3,893 leads on the local PC. Estimates drop from 1,079 to 143: 69 normal, 36 high, 37 overprice,
  1 data error. None of the top 12 overprice cases is a clean comparison: bundled orders priced as
  one unit (Talagante rollers, "solicitud completa adjunta"), a wrong product code (Talagante
  vehicle service under electrical systems), a broom width read as a length (Peñalolén 45 cm),
  packs the parser misses ("cajas de resma x 10", "96 sachet"), and tier mismatches (10 m kitchen
  roll against 250 m jumbo rolls, opalina against plain reams). With the misses fixed by hand the
  copy paper cases come to about +9% and +31%, not +992% and +555%. The method detects prices out
  of range of their code group; on this data that is not the same as overprice. Runs locally;
  the server has no Python.
- **Automatic result live (ADR 0033).** After the parser fixes ("x N" boxes, sachets), 150 of
  3,893 leads carry an automatic result: 73 normal, 41 alto, 35 fuera de rango, 1 error de datos.
  Sealed at testnet ledger 5112586 (digest b7c74471...), deployed, live files pass both parity
  checks. The "alto" level still reflects format in places (instant coffee sticks against jars
  per gram).

_Shaped by: ADR 0007, 0016; new ADR 0026, 0027, 0028, 0030, 0031, 0032, 0033._

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
- **Rayen (APS clinical software), non-commodity audit pilot.** Asked for by a presidential
  advisor, who wants automated procurement audits extended to non-commodity purchases. A search
  of the ingested orders for "rayen" finds six real purchases in five municipalities: Vitacura
  1480067-79-TD26 (100 Rayen APS licences, 15 months, 660 UF net, trato directo), Paine
  2790-100-TD26 (DWH fed by Rayen data, 371.28 UF net, trato directo), La Pintana 2274-339-SE25
  (queue system with Rayen integration, $72,366,108), Maipú 2583-592-SE24 (electronic medical
  leave integrated with Rayen, $5,462,185), Padre Hurtado 3827-361/413/448/501-SE26 (call centre
  with Rayen, $2,254,740 a month), La Pintana 2274-125-AG26 (Rayen-compatible printers,
  $1,820,000). Matches for "Trayenta" (a drug) and other text are false positives.
- **Rayen coverage gaps.** Municipal corporations and the Servicios de Salud are not ingested,
  so these figures are a floor. The dataset has no supplier name or RUT column, so total Rayen
  billing cannot be measured until order detail with the supplier is stored.
- **Rayen pilot (Felipe's proposal, guide sent to the advisor):** measure all Rayen spend with
  the supplier identified by RUT, read the bases (chilecompracl), build a replacement in one
  comuna or Servicio de Salud, compare cost against the contract, then reuse the method. Guide
  PDF and source: felipe_skill_voice `misc/2026-10-21_guia-rayen-chilecompra/`.

_Shaped by: ADR 0004, 0005, 0007._
