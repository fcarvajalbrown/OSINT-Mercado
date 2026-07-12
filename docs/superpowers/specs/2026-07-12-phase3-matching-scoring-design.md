# Phase 3 — Matching & anomaly scoring (design spec)

**Date:** 2026-07-12
**Status:** Approved, ready for implementation plan
**Shaped by:** ADR 0002, 0005, 0006, 0007, 0009; new ADRs 0011, 0012, 0013 (written during this phase)

## Goal

Turn the normalized per-line-item dataset (Phase 1/1.5) and the retail baselines
(Phase 2) into CLP-comparable, IVA-aligned overprice flags for the controlled basket,
emitted as `pending` anomalies with provenance, ready for the Phase 4 human curation gate.

Two prerequisites (deferred by ADR 0009) must land before any price comparison is valid:
(1) CLP conversion via `mindicador.cl` with a date-keyed rate cache, and (2) net-vs-gross
(IVA) alignment. Only then: the controlled-basket classifier, per-unit guardrails,
overprice ratio + severity, and the pending-anomaly output.

## Verified external facts (not guessed)

- **mindicador.cl** — `GET https://mindicador.cl/api/{indicador}/{dd-mm-yyyy}` returns
  `{version, autor, codigo, nombre, unidad_medida, serie: [{fecha, valor}]}`. `fecha` is
  ISO-8601; `valor` is the CLP value of one unit of the indicator on that date. Indicators
  needed: `uf` (UF/CLF, daily), `utm` (monthly-constant), `dolar` (USD, business-day),
  `euro` (EUR, business-day). Key-free, no secret required. (Verified live 2026-07-12.)
- **Order payload** — `EspecificacionProveedor`, `EspecificacionComprador`, `Unidad`,
  `Correlativo` are all present per line item in `tests/fixtures/oc_detail_sample.json`,
  but the parser does not currently extract them. `Producto` is only the generic UNSPSC
  label; the real product identity is in the `Especificacion*` fields.
- **IVA** — verified on the fixture: order `TotalNeto` 452976 x 1.19 (`PorcentajeIva` 19) =
  `Total` 539041. IVA is applied at order level; item `TotalImpuestos` is 0.

## Open verification gate (resolve during implementation, before hardcoding)

- Exact `Moneda`/`TipoMoneda` code strings for the five currencies. Read
  `docs/research/2026-07-12-parser-improvement.md` first; if it does not state the literal
  codes (e.g. is it `"CLF"` or `"UF"`, `"USD"` or `"DOLAR"`), capture a real non-CLP order
  from the live API rather than guess. The fixture only contains `"CLP"`.

## Design decisions (all confirmed with the user)

1. **Matcher inputs:** extend the parser to capture `EspecificacionProveedor`,
   `EspecificacionComprador`, `Unidad`, `Correlativo`; match keywords over a normalized
   concatenation of `Producto + EspecificacionProveedor + EspecificacionComprador +
   Categoria`. Re-ingest to refresh the dataset.
2. **Labeled sample:** bounded live capture across RM municipalities, hand-labeled
   (positives + hard negatives), committed as a test fixture. Confirm date/size with the
   user before running the capture.
3. **IVA alignment:** gross-up the order net unit price by `(1 + porcentaje_iva/100)` using
   the order-level `PorcentajeIva`, compare to the gross retail baseline. Exempt orders
   (`porcentaje_iva == 0`) → net == gross.
4. **Rate cache:** committed date-keyed `data/fx_rates.json` (`"indicator:YYYY-MM-DD" ->
   valor`), for re-run stability, deterministic offline tests, and an audit trail.
5. **Severity tiers:** PRD defaults as module constants — `WATCH = 1.5`, `HIGH = 2.0`,
   `SEVERE = 3.0`.
6. **Anomaly output:** diff-friendly `data/pending_anomalies.json`, sorted deterministically,
   each record carrying a stable id = hash(`oc_id`, `correlativo`, `sku_id`) so re-runs are
   identical and Phase 4 can confirm/dismiss by id.
7. **Unit guardrail:** compare at the SKU's canonical unit; bracket the ratio with a
   plausibility band (`RATIO_FLOOR ~= 0.3`, `RATIO_CAP ~= 20`). Out-of-band ratios are routed
   to `unit_ambiguous` (needs review) instead of auto-flagged. Curator sees raw quantity +
   unit/spec text. Pack hints in keywords help the matcher confirm same-pack.

## Modules and contracts

### `mindicador_schema.py` (new)
Single source of truth for mindicador.cl field-name strings and the currency map. Mirrors
the role of `schema.py`. Constants: API base URL, indicator names, response field keys
(`serie`, `fecha`, `valor`, ...), and `CURRENCY_TO_INDICATOR` mapping order currency codes
to indicators (`CLP -> None`). Nothing else hardcodes these strings.

### `fx.py` (new)
- `load_fx_cache(path) -> dict`, `save_fx_cache(cache, path)` for `data/fx_rates.json`.
- `get_rate(indicator, on_date, cache, session, *, sleep) -> float` — cache-first; on miss,
  fetch from mindicador; if `serie` is empty for the date (weekend/holiday), walk back up to
  N calendar days to the nearest prior published value. Writes the resolved value into the
  cache keyed by the *requested* date.
- `to_clp(amount, currency_code, on_date, cache, session) -> float` — `CLP` passes through;
  otherwise `amount * get_rate(indicator, on_date, ...)`. Unknown currency raises.
- Calls `truststore.inject_into_ssl()` at import (idempotent), like `api_client.py`. Never
  disables TLS verification.

### schema / models / parser / store (extend)
- `schema.py`: add `ITEM_ESPEC_COMPRADOR`, `ITEM_ESPEC_PROVEEDOR`, `ITEM_UNIDAD`,
  `ITEM_CORRELATIVO`, verified against the fixture.
- `models.LineItem`: add `correlativo: int`, `unidad: str`, `espec_comprador: str`,
  `espec_proveedor: str` (defaulted, frozen dataclass convention).
- `parser.py`: extract the four new fields.
- `store.py`: add the four columns to `ITEM_COLUMNS` and the row dict.
- Re-ingest to regenerate the committed Parquet.

### `matcher.py` (new)
- `normalize(text) -> str`: lowercase, strip accents, collapse whitespace/punctuation.
- `build_match_text(item) -> str`: normalized `Producto + EspecificacionProveedor +
  EspecificacionComprador + Categoria`.
- `match(item, basket) -> MatchResult(sku_id | None, rule, score)`: keyword substring hit
  first; if several SKUs collide, disambiguate with `rapidfuzz.fuzz.token_set_ratio`; a fuzzy
  fallback threshold catches near-misses. Deterministic; no randomness.
- New dependency: `rapidfuzz`.
- Developed test-first against the labeled sample; report precision/recall in the tests.

### `scoring.py` (new)
- Constants: `WATCH = 1.5`, `HIGH = 2.0`, `SEVERE = 3.0`, `RATIO_FLOOR = 0.3`,
  `RATIO_CAP = 20.0`, `SCORABLE_CONFIDENCE = {"medium", "high"}`.
- `gross_up(net_price, porcentaje_iva) -> float`.
- `severity(ratio) -> str | None` (None below `WATCH`).
- `score_line_item(item, match, baseline, fx_ctx) -> Anomaly | None`:
  - insufficient baseline confidence -> `Anomaly(status="needs_baseline")` (not an overprice
    flag).
  - convert unit price to CLP, gross-up, `ratio = gross_unit_clp / reference_price_clp`.
  - ratio outside `[RATIO_FLOOR, RATIO_CAP]` -> `status="unit_ambiguous"`.
  - ratio in band and `>= WATCH` -> `status="pending"`, with severity.
  - ratio in band and `< WATCH` -> `None` (not emitted).
- `Anomaly` fields: `id`, `oc_id`, `correlativo`, `comuna`, `sku_id`, `matched_rule`,
  `product`, `quantity`, `moneda`, `unit_price` (raw), `unit_price_clp_gross`,
  `reference_price_clp`, `baseline_confidence`, `overprice_ratio`, `severity`, `status`,
  `oc_url`, `captured_at`.

### `score.py` CLI (new, entry point `osint-score`)
Reads the items Parquet + `data/baselines.json` + `data/basket.json` + `data/fx_rates.json`;
runs matcher + scorer over all line items; refreshes the fx cache for any new
`(currency, date)`; writes sorted, deterministic `data/pending_anomalies.json`. Follows the
`ingest.py` / `build_baselines.py` CLI conventions.

## Data files
- `data/fx_rates.json` — committed rate cache.
- `data/pending_anomalies.json` — committed pending anomalies (Phase 4 input).
- `tests/fixtures/labeled_line_items.json` — hand-labeled real sample.

## Testing (TDD throughout)
- `fx`: cache hit/miss, business-day walk-back fallback, conversion math, unknown-currency
  error; network mocked with `responses` (existing dev dep).
- parser: the four new fields extracted from the fixture.
- matcher: precision/recall on the labeled sample, plus targeted positive and hard-negative
  cases.
- scoring: gross-up math, ratio, severity boundaries (exactly 1.5/2.0/3.0), plausibility band,
  `needs_baseline`, `unit_ambiguous`, and determinism (same input -> identical ids and order).
- CLI: end-to-end on a small fixture producing a stable `pending_anomalies.json`.

## ADRs to write this phase
- **0011** — Currency & IVA normalization to CLP (implements ADR 0009's deferred work).
- **0012** — Controlled-basket matcher implementation (extends ADR 0005).
- **0013** — Anomaly scoring & pending-anomaly output.

## Out of scope (Phase 3)
Curation UI/workflow (Phase 4), dashboard/deploy (Phase 5), robust statistics (MAD/IQR),
aggregator price sources, cryptographic provenance — all later phases per ROADMAP.
