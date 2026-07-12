# Phase 3 — Matching & anomaly scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the normalized per-line-item dataset + retail baselines into CLP-comparable, IVA-aligned overprice flags for the controlled basket, emitted as `pending` anomalies with provenance for the Phase 4 curation gate.

**Architecture:** Extend the parser to capture the rich product-identity fields; add a `mindicador.cl`-backed CLP conversion layer with a committed date-keyed rate cache; add a keyword+fuzzy controlled-basket matcher; add a scoring core that grosses-up net prices, computes overprice ratio + severity with a unit-plausibility guardrail, and emits deterministic pending anomalies via a new CLI.

**Tech Stack:** Python 3.11+ (dev 3.14), Polars, requests + truststore, rapidfuzz (new), pytest + responses, ruff.

## Global Constraints

- Python `>=3.11`; run tools via `.venv/Scripts/python`.
- TDD: failing test first, confirm fail, implement, confirm pass. `pytest -q` and `ruff check src tests scripts` stay green/clean before every commit.
- Field-name string literals live only in `schema.py` (Mercado Publico) and `mindicador_schema.py` (mindicador). Nothing else hardcodes them.
- Never guess field names / currency codes / API shapes — verify against a real fixture or official docs first.
- New network dep (mindicador) verifies TLS via `truststore.inject_into_ssl()`; never disable verification. mindicador needs no secret.
- Conventional Commits, scoped. Commit + push per task. No feature branches. No AI attribution. No emojis. No PR unless explicitly asked.
- Each significant decision gets a MADR-lite ADR (0011, 0012, 0013).

---

### Task 1: Extend parser for rich product-identity fields

**Files:**
- Modify: `src/osint_mercado/schema.py` (add 4 item field constants)
- Modify: `src/osint_mercado/models.py` (`LineItem`: 4 new fields)
- Modify: `src/osint_mercado/parser.py` (`_parse_items`)
- Modify: `src/osint_mercado/store.py` (`ITEM_COLUMNS`, row dict)
- Test: `tests/test_parser.py`, `tests/test_store.py`

**Interfaces:**
- Produces: `LineItem.correlativo: int`, `LineItem.unidad: str`, `LineItem.espec_comprador: str`, `LineItem.espec_proveedor: str`; store columns `correlativo, unidad, espec_comprador, espec_proveedor`.

- [ ] **Step 1:** Add a failing test in `tests/test_parser.py` asserting the first fixture line item parses `correlativo == 1`, `espec_proveedor` contains `"BOTIN PANAMA JACK"`, `espec_comprador` contains `"RES X"`, and `unidad == ""` (fixture `Unidad` is null → default).
- [ ] **Step 2:** Run `.venv/Scripts/python -m pytest tests/test_parser.py -q` → FAIL.
- [ ] **Step 3:** Implement:
  - `schema.py`: `ITEM_CORRELATIVO = "Correlativo"`, `ITEM_UNIDAD = "Unidad"`, `ITEM_ESPEC_COMPRADOR = "EspecificacionComprador"`, `ITEM_ESPEC_PROVEEDOR = "EspecificacionProveedor"`.
  - `models.LineItem`: add `correlativo: int = 0`, `unidad: str = ""`, `espec_comprador: str = ""`, `espec_proveedor: str = ""`.
  - `parser._parse_items`: extract with `_to_int` / `str(... or "")` (guard `None`).
- [ ] **Step 4:** Run test → PASS.
- [ ] **Step 5:** Add columns to `store.ITEM_COLUMNS` and the row dict; update `tests/test_store.py` to assert the new columns exist and carry the values. Run `pytest -q` → PASS.
- [ ] **Step 6:** Re-ingest to refresh the committed Parquet (bounded live run — see Task 4 note; may be regenerated together with Task 4). `ruff check src tests` clean.
- [ ] **Step 7:** Commit `feat(parser): capture especificacion/unidad/correlativo line-item fields`.

---

### Task 2: mindicador schema module + currency-code verification

**Files:**
- Create: `src/osint_mercado/mindicador_schema.py`
- Test: `tests/test_mindicador_schema.py`

**Interfaces:**
- Produces: `API_BASE`, indicator constants `IND_UF/IND_UTM/IND_DOLAR/IND_EURO`, response keys `RESP_SERIE="serie"`, `SERIE_FECHA="fecha"`, `SERIE_VALOR="valor"`, and `CURRENCY_TO_INDICATOR: dict[str, str | None]`.

- [ ] **Step 1:** Verify currency codes: read `docs/research/2026-07-12-parser-improvement.md` for the literal `Moneda`/`TipoMoneda` code strings. If not stated literally, capture one real non-CLP order via the live API and record the codes. Document the confirmed codes in a comment.
- [ ] **Step 2:** Write `tests/test_mindicador_schema.py` asserting `CURRENCY_TO_INDICATOR["CLP"] is None` and that each non-CLP code maps to the right indicator string; assert `API_BASE` and response keys are the verified literals.
- [ ] **Step 3:** Run → FAIL (module missing).
- [ ] **Step 4:** Implement the module with the verified constants and map. `API_BASE = "https://mindicador.cl/api"`.
- [ ] **Step 5:** Run → PASS; ruff clean.
- [ ] **Step 6:** Commit `feat(fx): add verified mindicador.cl field-name/currency-code module`.

---

### Task 3: CLP conversion layer with committed date-keyed rate cache

**Files:**
- Create: `src/osint_mercado/fx.py`
- Test: `tests/test_fx.py`
- Data: `data/fx_rates.json` (created/committed by the CLI in Task 7; a seed empty `[]`/`{}` may be committed here)

**Interfaces:**
- Consumes: `mindicador_schema` constants; `api_client`-style session.
- Produces:
  - `load_fx_cache(path) -> dict[str, float]`, `save_fx_cache(cache, path) -> None`
  - `get_rate(indicator: str, on_date: date, cache: dict, session, *, sleep=time.sleep, max_backfill_days=7) -> float`
  - `to_clp(amount: float, currency_code: str, on_date: date, cache: dict, session) -> float`
  - `cache_key(indicator, on_date) -> str` = `f"{indicator}:{on_date.isoformat()}"`

- [ ] **Step 1:** Write `tests/test_fx.py` with (network mocked via `responses`):
  - cache hit returns cached value without a request;
  - cache miss fetches, returns `serie[0].valor`, and stores under the requested date key;
  - business-day fallback: date with empty `serie` triggers walk-back to a prior date that has a value (assert final value + that it is cached under the originally-requested key);
  - `to_clp("CLP")` returns the amount unchanged and makes no request;
  - `to_clp` for a UF amount multiplies by the rate;
  - unknown currency raises `ValueError`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `fx.py`:
  - `truststore.inject_into_ssl()` at import.
  - URL builder `f"{API_BASE}/{indicator}/{dd-mm-yyyy}"`.
  - `get_rate`: cache-first; on miss loop back up to `max_backfill_days`, fetching each date until `serie` non-empty; cache and return the first `valor`; raise `RuntimeError` if none found.
  - `to_clp`: map `currency_code` via `CURRENCY_TO_INDICATOR`; `None` → return amount; missing key → `ValueError`.
- [ ] **Step 4:** Run → PASS; ruff clean.
- [ ] **Step 5:** Commit `feat(fx): add CLP conversion with date-keyed mindicador rate cache`.

---

### Task 4: Capture + hand-label a real line-item sample

**Files:**
- Create: `tests/fixtures/labeled_line_items.json`
- Possibly refresh: `data/oc_items_<fecha>.parquet` (re-ingest with the Task 1 parser)

**Interfaces:**
- Produces: a JSON array of `{producto, espec_proveedor, espec_comprador, categoria, category_code, product_code, expected_sku_id | null, note}` — real line-items, hand-labeled positives + hard negatives spanning the basket.

- [ ] **Step 1:** Run a bounded live ingest (default choice, no blocking: one recent business date, `--max-per-organism 5`) to pull real line-items across RM municipalities. Use `.venv/Scripts/python -m osint_mercado.ingest`.
- [ ] **Step 2:** Inspect the Parquet; select a spread of line-items (aim ~40-80): clear positives for as many basket SKUs as appear, plus hard negatives (near-miss text that must NOT match). Hand-label `expected_sku_id` (or `null`).
- [ ] **Step 3:** Write `tests/fixtures/labeled_line_items.json`. Commit `test(matcher): add hand-labeled real line-item sample`.

---

### Task 5: Controlled-basket matcher

**Files:**
- Create: `src/osint_mercado/matcher.py`
- Modify: `pyproject.toml` (add `rapidfuzz` to dependencies)
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `basket.load_basket`, `basket.Sku`; labeled fixture.
- Produces:
  - `normalize(text: str) -> str`
  - `build_match_text(producto, espec_proveedor, espec_comprador, categoria) -> str`
  - `MatchResult` dataclass: `sku_id: str | None`, `rule: str`, `score: float`
  - `match(producto, espec_proveedor, espec_comprador, categoria, skus, *, fuzzy_threshold=88) -> MatchResult`

- [ ] **Step 1:** Write `tests/test_matcher.py`:
  - `normalize("Tóner  HP")` → `"toner hp"` (accents stripped, whitespace collapsed, lowercased);
  - a positive: the fixture chaleco line matches `chaleco_reflectante_seguridad` — NOTE if the fixture's chaleco doesn't match on current keywords, this drives a keyword refinement in basket.json (record it);
  - a hard negative returns `sku_id is None`;
  - a data-driven test iterating `labeled_line_items.json` computing precision/recall and asserting precision `>=` an agreed floor (start strict, e.g. precision `== 1.0` on labeled positives it does match; recall reported).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `matcher.py`:
  - `normalize`: `unicodedata.normalize("NFKD", ...)` drop combining marks, lowercase, regex `\s+`→space, strip.
  - keyword pass: for each SKU, if any normalized keyword is a substring of the normalized match text → candidate (rule `"keyword"`, score 100). Multiple candidates → pick highest `token_set_ratio` (rule `"keyword+fuzzy"`).
  - fallback: if no keyword hit, best `token_set_ratio` over each SKU's `canonical_name + keywords`; accept only if `>= fuzzy_threshold` (rule `"fuzzy"`).
  - else `MatchResult(None, "none", best_score)`.
- [ ] **Step 4:** Run → PASS (refine basket keywords / threshold as the labeled sample demands; keep changes in `basket.json`, re-run `build_baselines` if SKUs change — they won't for keyword-only edits).
- [ ] **Step 5:** `ruff check`, `pip install -e ".[dev]"` to pull rapidfuzz. Commit `feat(matcher): add controlled-basket keyword+fuzzy classifier`.

---

### Task 6: Anomaly scoring core

**Files:**
- Create: `src/osint_mercado/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `baseline.Baseline`, `matcher.MatchResult`, `fx.to_clp`.
- Produces:
  - constants `WATCH=1.5`, `HIGH=2.0`, `SEVERE=3.0`, `RATIO_FLOOR=0.3`, `RATIO_CAP=20.0`, `SCORABLE_CONFIDENCE={"medium","high"}`
  - `gross_up(net_price: float, porcentaje_iva: float) -> float`
  - `severity(ratio: float) -> str | None`
  - `Anomaly` dataclass (fields per spec)
  - `make_anomaly_id(oc_id, correlativo, sku_id) -> str`
  - `score_line_item(*, oc_id, correlativo, comuna, producto, quantity, moneda, unit_price, porcentaje_iva, on_date, oc_url, captured_at, match, baseline, fx_cache, session) -> Anomaly | None`

- [ ] **Step 1:** Write `tests/test_scoring.py`:
  - `gross_up(100, 19) == 119`; `gross_up(100, 0) == 100`;
  - `severity`: `1.49 → None`, `1.5 → "watch"`, `2.0 → "high"`, `3.0 → "severe"`;
  - `make_anomaly_id` deterministic + stable for same inputs, differs on different inputs;
  - `score_line_item`: insufficient baseline → `status == "needs_baseline"`; ratio in band ≥ WATCH → `status == "pending"` with right severity and `unit_price_clp_gross`; ratio `< WATCH` in band → `None`; ratio `> RATIO_CAP` → `status == "unit_ambiguous"`; a non-CLP moneda converts via a mocked fx cache.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `scoring.py` with the branch logic from the spec. `make_anomaly_id`: `hashlib.sha1(f"{oc_id}|{correlativo}|{sku_id}".encode()).hexdigest()[:16]`.
- [ ] **Step 4:** Run → PASS; ruff clean.
- [ ] **Step 5:** Commit `feat(scoring): add IVA-aligned overprice scoring with unit guardrail`.

---

### Task 7: `osint-score` CLI + pending anomalies output

**Files:**
- Create: `src/osint_mercado/score.py`
- Modify: `pyproject.toml` (`[project.scripts] osint-score = "osint_mercado.score:main"`)
- Data: `data/pending_anomalies.json`, `data/fx_rates.json`
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: everything above; reads items Parquet + `data/baselines.json` + `data/basket.json` + `data/fx_rates.json`.
- Produces: `run(items_path, baselines_path, basket_path, fx_cache_path, out_path, *, session, on_date_source) -> Path`; `main()`.

- [ ] **Step 1:** Write `tests/test_score.py`: build a tiny Parquet (via `store.orders_to_items_df`) with one overpriced matchable CLP line and one below-threshold line; run `run(...)` with a pre-seeded fx cache (no network); assert `pending_anomalies.json` contains exactly the pending record, is sorted deterministically, and a second `run` produces byte-identical output.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `score.py`: read Parquet rows, for each row `match` → if matched, look up baseline → `score_line_item` (using the row's `fecha` date for fx) → collect non-None anomalies; sort by `(comuna, sku_id, oc_id, correlativo)`; write `pending_anomalies.json` (indent=2, ensure_ascii=False); `save_fx_cache`. CLI flags mirror `build_baselines.py`.
- [ ] **Step 4:** Run → PASS; ruff clean.
- [ ] **Step 5:** Run the real CLI over the refreshed dataset to produce the committed `data/pending_anomalies.json` + `data/fx_rates.json`. Commit `feat(score): add osint-score CLI emitting pending anomalies`.

---

### Task 8: ADRs + ROADMAP

**Files:**
- Create: `docs/adr/0011-currency-iva-normalization.md`, `docs/adr/0012-matcher-implementation.md`, `docs/adr/0013-anomaly-scoring-pending-output.md`
- Modify: `docs/adr/README.md` (index), `ROADMAP.md` (Phase 3 → Done)

- [ ] **Step 1:** Write the three MADR-lite ADRs (Status Accepted, Date 2026-07-12, Deciders: Felipe Carvajal Brown; Context/Decision/Consequences/Alternatives). 0011 references and builds on 0009; 0012 extends 0005; 0013 references 0006/0007.
- [ ] **Step 2:** Update the ADR README index table and set ROADMAP Phase 3 to `Done`.
- [ ] **Step 3:** `pytest -q` + `ruff check src tests` green/clean. Commit `docs(adr): add ADRs 0011-0013 and mark Phase 3 done`.

## Self-Review notes
- Spec coverage: fx (T2/T3), IVA gross-up (T6), matcher rich-text (T1/T5), labeled sample (T4), severity (T6), pending output + determinism (T6/T7), unit guardrail (T6), ADRs (T8). All covered.
- Open verification gate (currency codes) is Task 2 Step 1, before any hardcoding.
- Live-capture scope defaulted (one date, `--max-per-organism 5`) rather than blocking, per the momentum directive.
