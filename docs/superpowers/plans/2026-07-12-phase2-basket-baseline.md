# Phase 2 — Basket & Retail Baseline Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the v1 controlled basket of 19 commoditized SKUs and build the engine
that turns curated manual-seed retail price observations into a reference price and
confidence tier per SKU, ready for Phase 3's anomaly scoring to consume.

**Architecture:** Two pure library modules (`basket.py` for data model + loaders,
`baseline.py` for the median/confidence computation), two versioned JSON data files
(`data/basket.json`, `data/seed_prices.json`) populated with real retailer observations
gathered via live web lookups, and a small CLI (`build_baselines.py`) that materializes
`data/baselines.json` for Phase 3 to read directly.

**Tech Stack:** Python 3.11+, stdlib `json`/`dataclasses`/`datetime`/`argparse` only — no
new third-party dependency needed for this phase (manual-seed only, no aggregator client).

## Global Constraints

- Python 3.11+ (dev machine: 3.14). Run via `.venv/Scripts/python`.
- TDD: write the failing test first, confirm it fails, implement, confirm it passes.
- Run `.venv/Scripts/python -m pytest -q` and
  `.venv/Scripts/python -m ruff check src tests scripts` after every task; both must be
  green/clean before committing.
- Conventional Commits (`feat:`, `test:`, `docs:`, etc.). Commit after each task; push to
  `origin` right after each commit — do not batch commits.
- No emojis anywhere. No AI attribution (no `Co-Authored-By`, no "Generated with" lines).
- Never open a pull request. Work directly on `master`.
- Never invent facts/numbers: every price observation in `data/seed_prices.json` must
  come from a real, currently-live retailer page found via WebSearch/WebFetch, with its
  real URL and the date it was actually checked.
- Ruff line-length limit is 100 (`pyproject.toml`'s `[tool.ruff]`).

---

### Task 1: Basket data model and loaders

**Files:**
- Create: `src/osint_mercado/basket.py`
- Test: `tests/test_basket.py`

**Interfaces:**
- Produces: `Sku` dataclass (sku_id: str, canonical_name: str, keywords: list[str],
  unit: str, unspsc_category_code: int = 0, unspsc_product_code: int = 0).
  `PriceObservation` dataclass (sku_id: str, retailer: str, price_clp: float,
  observed_at: str, url: str). `load_basket(path) -> list[Sku]`.
  `load_seed_observations(path) -> list[PriceObservation]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_basket.py
import json

from osint_mercado.basket import Sku, PriceObservation, load_basket, load_seed_observations


def test_load_basket_parses_sku_records(tmp_path):
    path = tmp_path / "basket.json"
    path.write_text(json.dumps([
        {
            "sku_id": "toner_hp_cf283a",
            "canonical_name": "Toner HP CF283A",
            "keywords": ["toner", "cf283a", "83a"],
            "unit": "unidad",
            "unspsc_category_code": 0,
            "unspsc_product_code": 0,
        }
    ]), encoding="utf-8")

    skus = load_basket(path)

    assert skus == [Sku(
        sku_id="toner_hp_cf283a",
        canonical_name="Toner HP CF283A",
        keywords=["toner", "cf283a", "83a"],
        unit="unidad",
        unspsc_category_code=0,
        unspsc_product_code=0,
    )]


def test_load_basket_defaults_missing_unspsc_codes(tmp_path):
    path = tmp_path / "basket.json"
    path.write_text(json.dumps([
        {"sku_id": "escoba_fibra", "canonical_name": "Escoba de fibra",
         "keywords": ["escoba"], "unit": "unidad"}
    ]), encoding="utf-8")

    skus = load_basket(path)

    assert skus[0].unspsc_category_code == 0
    assert skus[0].unspsc_product_code == 0


def test_load_seed_observations_parses_price_records(tmp_path):
    path = tmp_path / "seed_prices.json"
    path.write_text(json.dumps([
        {
            "sku_id": "toner_hp_cf283a",
            "retailer": "Sodimac",
            "price_clp": 45990.0,
            "observed_at": "2026-07-10",
            "url": "https://www.sodimac.cl/sodimac-cl/product/123",
        }
    ]), encoding="utf-8")

    observations = load_seed_observations(path)

    assert observations == [PriceObservation(
        sku_id="toner_hp_cf283a",
        retailer="Sodimac",
        price_clp=45990.0,
        observed_at="2026-07-10",
        url="https://www.sodimac.cl/sodimac-cl/product/123",
    )]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_basket.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'osint_mercado.basket'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/osint_mercado/basket.py
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Sku:
    sku_id: str
    canonical_name: str
    keywords: list[str] = field(default_factory=list)
    unit: str = ""
    unspsc_category_code: int = 0
    unspsc_product_code: int = 0


@dataclass(frozen=True)
class PriceObservation:
    sku_id: str
    retailer: str
    price_clp: float
    observed_at: str
    url: str


def load_basket(path) -> list[Sku]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Sku(
            sku_id=row["sku_id"],
            canonical_name=row["canonical_name"],
            keywords=list(row.get("keywords") or []),
            unit=row.get("unit", ""),
            unspsc_category_code=int(row.get("unspsc_category_code") or 0),
            unspsc_product_code=int(row.get("unspsc_product_code") or 0),
        )
        for row in rows
    ]


def load_seed_observations(path) -> list[PriceObservation]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        PriceObservation(
            sku_id=row["sku_id"],
            retailer=row["retailer"],
            price_clp=float(row["price_clp"]),
            observed_at=row["observed_at"],
            url=row["url"],
        )
        for row in rows
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_basket.py -v`
Expected: 3 passed

- [ ] **Step 5: Lint and commit**

```bash
.venv/Scripts/python -m ruff check src tests scripts
git add src/osint_mercado/basket.py tests/test_basket.py
git commit -m "feat(basket): add Sku/PriceObservation data model and loaders"
git push
```

---

### Task 2: Reference-price and confidence engine

**Files:**
- Create: `src/osint_mercado/baseline.py`
- Test: `tests/test_baseline.py`

**Interfaces:**
- Consumes: `osint_mercado.basket.PriceObservation` (from Task 1).
- Produces: `Baseline` dataclass (sku_id: str, reference_price_clp: float,
  confidence: str, n_observations: int, freshest_observed_at: str, spread_ratio: float).
  `compute_reference(sku_id: str, observations: list[PriceObservation], as_of: date) -> Baseline`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_baseline.py
from datetime import date

from osint_mercado.basket import PriceObservation
from osint_mercado.baseline import compute_reference


def _obs(price, observed_at, retailer="Retailer"):
    return PriceObservation(
        sku_id="sku1", retailer=retailer, price_clp=price,
        observed_at=observed_at, url="https://example.cl",
    )


def test_no_observations_is_insufficient():
    baseline = compute_reference("sku1", [], date(2026, 7, 12))
    assert baseline.confidence == "insufficient"
    assert baseline.reference_price_clp == 0.0
    assert baseline.n_observations == 0
    assert baseline.spread_ratio == 0.0


def test_two_close_recent_observations_is_high_confidence():
    obs = [_obs(10000, "2026-07-01"), _obs(11000, "2026-06-15")]
    baseline = compute_reference("sku1", obs, date(2026, 7, 12))
    assert baseline.confidence == "high"
    assert baseline.reference_price_clp == 10500.0
    assert baseline.n_observations == 2
    assert baseline.freshest_observed_at == "2026-07-01"


def test_single_recent_observation_is_medium_confidence():
    obs = [_obs(10000, "2026-07-01")]
    baseline = compute_reference("sku1", obs, date(2026, 7, 12))
    assert baseline.confidence == "medium"
    assert baseline.spread_ratio == 0.0


def test_wide_spread_two_observations_is_medium_confidence():
    obs = [_obs(10000, "2026-07-01"), _obs(20000, "2026-06-15")]
    baseline = compute_reference("sku1", obs, date(2026, 7, 12))
    assert baseline.confidence == "medium"
    assert baseline.spread_ratio > 0.25


def test_all_stale_observations_is_insufficient():
    obs = [_obs(10000, "2025-01-01"), _obs(11000, "2025-02-01")]
    baseline = compute_reference("sku1", obs, date(2026, 7, 12))
    assert baseline.confidence == "insufficient"


def test_median_of_three_observations():
    obs = [_obs(9000, "2026-07-01"), _obs(10000, "2026-07-02"), _obs(20000, "2026-07-03")]
    baseline = compute_reference("sku1", obs, date(2026, 7, 12))
    assert baseline.reference_price_clp == 10000.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_baseline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'osint_mercado.baseline'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/osint_mercado/baseline.py
from dataclasses import dataclass
from datetime import date

from osint_mercado.basket import PriceObservation

FRESHNESS_DAYS = 90
SPREAD_HIGH_MAX = 0.25


@dataclass(frozen=True)
class Baseline:
    sku_id: str
    reference_price_clp: float
    confidence: str
    n_observations: int
    freshest_observed_at: str
    spread_ratio: float


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def compute_reference(
    sku_id: str, observations: list[PriceObservation], as_of: date
) -> Baseline:
    if not observations:
        return Baseline(sku_id, 0.0, "insufficient", 0, "", 0.0)

    prices = [o.price_clp for o in observations]
    reference_price = _median(prices)
    freshest = max(observations, key=lambda o: o.observed_at)
    freshest_age_days = (as_of - date.fromisoformat(freshest.observed_at)).days
    spread_ratio = (
        (max(prices) - min(prices)) / reference_price if len(prices) >= 2 else 0.0
    )

    if freshest_age_days > FRESHNESS_DAYS:
        confidence = "insufficient"
    elif len(observations) >= 2 and spread_ratio <= SPREAD_HIGH_MAX:
        confidence = "high"
    else:
        confidence = "medium"

    return Baseline(
        sku_id=sku_id,
        reference_price_clp=reference_price,
        confidence=confidence,
        n_observations=len(observations),
        freshest_observed_at=freshest.observed_at,
        spread_ratio=spread_ratio,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_baseline.py -v`
Expected: 6 passed

- [ ] **Step 5: Lint and commit**

```bash
.venv/Scripts/python -m ruff check src tests scripts
git add src/osint_mercado/baseline.py tests/test_baseline.py
git commit -m "feat(baseline): compute reference price and confidence tier from observations"
git push
```

---

### Task 3: Curate the v1 basket definition (19 SKUs)

**Files:**
- Create: `data/basket.json`
- Test: `tests/test_basket_data.py`

**Interfaces:**
- Consumes: `osint_mercado.basket.load_basket` (Task 1).
- Produces: the real, committed basket dataset Phase 3 will match order line-items
  against. `unspsc_category_code`/`unspsc_product_code` are left at `0` for every SKU in
  v1 — no real captured order confirms the exact UNSPSC commodity code for e.g. "safety
  boots with steel toe" specifically (the one real fixture we have is plain "Zapatos de
  hombre", a different commodity), so per CLAUDE.md's never-guess rule these are left
  unset rather than assigned a plausible-looking code. Phase 3's matcher (keyword +
  fuzzy, per ADR 0005) does not depend on them being populated.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_basket_data.py
from pathlib import Path

from osint_mercado.basket import load_basket

BASKET_PATH = Path(__file__).parent.parent / "data" / "basket.json"


def test_v1_basket_has_nineteen_unique_skus():
    skus = load_basket(BASKET_PATH)
    assert len(skus) == 19
    assert len({s.sku_id for s in skus}) == 19


def test_every_sku_has_canonical_name_unit_and_keywords():
    skus = load_basket(BASKET_PATH)
    for sku in skus:
        assert sku.canonical_name
        assert sku.unit
        assert sku.keywords
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_basket_data.py -v`
Expected: FAIL with `FileNotFoundError` (data/basket.json does not exist yet)

- [ ] **Step 3: Write the basket data file**

```json
[
  {"sku_id": "toner_hp_cf283a", "canonical_name": "Toner HP CF283A (LaserJet Pro M125/M225)",
   "keywords": ["toner", "toner cf283a", "83a", "hp 83a", "laserjet pro m125", "laserjet pro m225"],
   "unit": "unidad", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "toner_hp_ce285a", "canonical_name": "Toner HP CE285A (LaserJet P1102)",
   "keywords": ["toner", "toner ce285a", "85a", "hp 85a", "laserjet p1102"],
   "unit": "unidad", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "papel_resma_carta_75g", "canonical_name": "Papel resma carta 75g",
   "keywords": ["resma", "papel carta", "papel bond carta", "resma carta 75 gr"],
   "unit": "resma (500 hojas)", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "papel_resma_oficio_75g", "canonical_name": "Papel resma oficio 75g",
   "keywords": ["resma", "papel oficio", "papel bond oficio", "resma oficio 75 gr"],
   "unit": "resma (500 hojas)", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "pilas_aa_blister4", "canonical_name": "Pilas alcalinas AA (blister x4)",
   "keywords": ["pilas aa", "pilas alcalinas aa", "baterias aa"],
   "unit": "blister", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "pilas_aaa_blister4", "canonical_name": "Pilas alcalinas AAA (blister x4)",
   "keywords": ["pilas aaa", "pilas alcalinas aaa", "baterias aaa"],
   "unit": "blister", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "pendrive_usb_16gb", "canonical_name": "Pendrive USB 16GB",
   "keywords": ["pendrive", "pen drive", "memoria usb", "usb 16gb", "unidad flash"],
   "unit": "unidad", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "mouse_usb", "canonical_name": "Mouse óptico USB",
   "keywords": ["mouse", "mouse usb", "mouse optico", "raton usb"],
   "unit": "unidad", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "teclado_usb", "canonical_name": "Teclado USB estándar",
   "keywords": ["teclado", "teclado usb"],
   "unit": "unidad", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "cartucho_tinta_hp_664_negro", "canonical_name": "Cartucho de tinta HP 664 negro",
   "keywords": ["cartucho de tinta", "hp 664", "tinta hp 664 negro"],
   "unit": "unidad", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "zapatos_seguridad_puntera_acero", "canonical_name": "Zapatos de seguridad con puntera de acero",
   "keywords": ["zapatos de seguridad", "calzado de seguridad", "puntera de acero", "zapato industrial"],
   "unit": "par", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "chaleco_reflectante_seguridad", "canonical_name": "Chaleco reflectante de seguridad",
   "keywords": ["chaleco reflectante", "chaleco de seguridad", "chaleco alta visibilidad"],
   "unit": "unidad", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "guantes_nitrilo_caja100", "canonical_name": "Guantes de nitrilo desechables (caja x100)",
   "keywords": ["guantes de nitrilo", "guantes de latex", "guantes desechables", "caja 100"],
   "unit": "caja", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "mascarillas_quirurgicas_caja50", "canonical_name": "Mascarillas quirúrgicas desechables (caja x50)",
   "keywords": ["mascarillas quirurgicas", "mascarilla desechable", "caja 50"],
   "unit": "caja", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "extintor_pqs_6kg", "canonical_name": "Extintor PQS 6kg",
   "keywords": ["extintor", "extintor pqs", "extintor 6 kilos", "extintor polvo quimico seco"],
   "unit": "unidad", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "cloro_lavandina_4l", "canonical_name": "Cloro/lavandina genérico (botella 4L)",
   "keywords": ["cloro", "lavandina", "cloro 4 litros"],
   "unit": "botella", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "alcohol_gel_1l", "canonical_name": "Alcohol gel 1L",
   "keywords": ["alcohol gel", "alcohol en gel", "gel antibacterial"],
   "unit": "botella", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "escoba_fibra", "canonical_name": "Escoba de fibra",
   "keywords": ["escoba", "escoba de fibra", "escoba plastica"],
   "unit": "unidad", "unspsc_category_code": 0, "unspsc_product_code": 0},
  {"sku_id": "basurero_plastico_60l", "canonical_name": "Basurero plástico 60L",
   "keywords": ["basurero", "papelero", "basurero plastico 60 litros", "contenedor de basura"],
   "unit": "unidad", "unspsc_category_code": 0, "unspsc_product_code": 0}
]
```

Save this as `data/basket.json` (UTF-8, preserve the Spanish accents as literal characters,
not escape sequences).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_basket_data.py -v`
Expected: 2 passed

- [ ] **Step 5: Lint and commit**

```bash
.venv/Scripts/python -m ruff check src tests scripts
git add data/basket.json tests/test_basket_data.py
git commit -m "feat(basket): curate v1 controlled basket of 19 SKUs"
git push
```

---

### Task 4: Populate seed prices — office/print consumables (SKUs 1-10)

**Files:**
- Modify: `data/seed_prices.json` (create if absent; append to a JSON array)

**Interfaces:**
- Consumes: `sku_id`s from `data/basket.json` (Task 3):
  `toner_hp_cf283a`, `toner_hp_ce285a`, `papel_resma_carta_75g`, `papel_resma_oficio_75g`,
  `pilas_aa_blister4`, `pilas_aaa_blister4`, `pendrive_usb_16gb`, `mouse_usb`,
  `teclado_usb`, `cartucho_tinta_hp_664_negro`.
- Produces: `PriceObservation` records (Task 1's shape) for each of the 10 SKUs above.

This is a data-curation task, not code — there is no failing test to write first. The
validation step is the existing loader test plus a fresh sanity check.

- [ ] **Step 1: For each of the 10 SKUs above, gather 2-3 real observations**

For each `sku_id`, use WebSearch to find current listings at real Chilean retailers
(e.g. Sodimac, PC Factory, Lider, Falabella — whichever actually stock that SKU), then
WebFetch the specific product page to confirm the exact current price and URL. Do not
invent or estimate a price — every entry must come from a page you actually fetched.
Record each as:

```json
{"sku_id": "<sku_id>", "retailer": "<real retailer name>", "price_clp": <float>,
 "observed_at": "<YYYY-MM-DD, today's real date>", "url": "<the exact product page URL>"}
```

If a SKU genuinely yields only 1 credible observation after a reasonable search effort,
record that 1 — do not pad with fabricated retailers.

- [ ] **Step 2: Write/append all observations to `data/seed_prices.json`**

If the file does not exist yet, create it as a JSON array containing all observations
gathered in Step 1. If it exists (from a prior task run), load it, append the new
records, and write back the merged array.

- [ ] **Step 3: Verify the file parses**

Run: `.venv/Scripts/python -c "from osint_mercado.basket import load_seed_observations; obs = load_seed_observations('data/seed_prices.json'); print(len(obs))"`
Expected: prints a count >= 10 (at least one observation per SKU in this batch), no
exception.

- [ ] **Step 4: Lint and commit**

```bash
.venv/Scripts/python -m ruff check src tests scripts
git add data/seed_prices.json
git commit -m "data(basket): seed retail prices for office/print consumables"
git push
```

---

### Task 5: Populate seed prices — PPE / seguridad (SKUs 11-15)

**Files:**
- Modify: `data/seed_prices.json`

**Interfaces:**
- Consumes: `sku_id`s `zapatos_seguridad_puntera_acero`, `chaleco_reflectante_seguridad`,
  `guantes_nitrilo_caja100`, `mascarillas_quirurgicas_caja50`, `extintor_pqs_6kg`.
- Produces: `PriceObservation` records for these 5 SKUs.

Same process as Task 4, applied to this batch of 5 SKUs. Target retailers likely to stock
PPE/safety supplies: Sodimac, industrial-supply sites, EPP-specific Chilean retailers
found via the search itself — do not assume a specific site in advance, verify via
WebSearch which retailers actually carry each item.

- [ ] **Step 1: Gather 2-3 real observations per SKU via WebSearch + WebFetch**

Same recording format as Task 4, Step 1.

- [ ] **Step 2: Append all observations to `data/seed_prices.json`**

Load the existing array (from Task 4), append this batch's records, write back the
merged array.

- [ ] **Step 3: Verify the file parses**

Run: `.venv/Scripts/python -c "from osint_mercado.basket import load_seed_observations; obs = load_seed_observations('data/seed_prices.json'); print(len(obs))"`
Expected: prints a count >= 15 (Task 4's + this batch's), no exception.

- [ ] **Step 4: Lint and commit**

```bash
.venv/Scripts/python -m ruff check src tests scripts
git add data/seed_prices.json
git commit -m "data(basket): seed retail prices for PPE/seguridad SKUs"
git push
```

---

### Task 6: Populate seed prices — limpieza/insumos básicos (SKUs 16-19)

**Files:**
- Modify: `data/seed_prices.json`

**Interfaces:**
- Consumes: `sku_id`s `cloro_lavandina_4l`, `alcohol_gel_1l`, `escoba_fibra`,
  `basurero_plastico_60l`.
- Produces: `PriceObservation` records for these 4 SKUs.

Same process as Task 4/5, applied to this final batch of 4 SKUs.

- [ ] **Step 1: Gather 2-3 real observations per SKU via WebSearch + WebFetch**

Same recording format as Task 4, Step 1.

- [ ] **Step 2: Append all observations to `data/seed_prices.json`**

Load the existing array (from Tasks 4-5), append this batch's records, write back the
merged array. The file should now contain observations for all 19 SKUs.

- [ ] **Step 3: Verify the file parses and covers all 19 SKUs**

Run:
```bash
.venv/Scripts/python -c "
from osint_mercado.basket import load_basket, load_seed_observations
skus = {s.sku_id for s in load_basket('data/basket.json')}
obs = load_seed_observations('data/seed_prices.json')
covered = {o.sku_id for o in obs}
print('total observations:', len(obs))
print('skus without any observation:', skus - covered)
"
```
Expected: no exception; review the "skus without any observation" list — ideally empty,
but a handful of SKUs with genuinely no findable retail listing is acceptable (they will
compute to `confidence == "insufficient"`, which is the correct, honest signal).

- [ ] **Step 4: Lint and commit**

```bash
.venv/Scripts/python -m ruff check src tests scripts
git add data/seed_prices.json
git commit -m "data(basket): seed retail prices for limpieza/insumos basicos SKUs"
git push
```

---

### Task 7: Build-baselines CLI

**Files:**
- Create: `src/osint_mercado/build_baselines.py`
- Test: `tests/test_build_baselines.py`
- Modify: `pyproject.toml` (add script entry point)

**Interfaces:**
- Consumes: `osint_mercado.basket.load_basket`, `load_seed_observations` (Task 1);
  `osint_mercado.baseline.compute_reference` (Task 2).
- Produces: `build(basket_path, seed_prices_path, as_of: date) -> list[dict]` and
  `write_baselines(rows: list[dict], path) -> None`, plus a `main()` CLI entry point
  writing `data/baselines.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_baselines.py
import json
from datetime import date

from osint_mercado.build_baselines import build, write_baselines


def _write(path, rows):
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_build_computes_one_baseline_row_per_sku(tmp_path):
    basket_path = tmp_path / "basket.json"
    seed_path = tmp_path / "seed_prices.json"
    _write(basket_path, [
        {"sku_id": "sku_a", "canonical_name": "SKU A", "keywords": ["a"], "unit": "unidad"},
        {"sku_id": "sku_b", "canonical_name": "SKU B", "keywords": ["b"], "unit": "unidad"},
    ])
    _write(seed_path, [
        {"sku_id": "sku_a", "retailer": "R1", "price_clp": 1000.0,
         "observed_at": "2026-07-01", "url": "https://example.cl/a"},
        {"sku_id": "sku_a", "retailer": "R2", "price_clp": 1100.0,
         "observed_at": "2026-07-05", "url": "https://example.cl/a2"},
    ])

    rows = build(basket_path, seed_path, date(2026, 7, 12))

    assert len(rows) == 2
    row_a = next(r for r in rows if r["sku_id"] == "sku_a")
    row_b = next(r for r in rows if r["sku_id"] == "sku_b")
    assert row_a["reference_price_clp"] == 1050.0
    assert row_a["confidence"] == "high"
    assert row_b["confidence"] == "insufficient"
    assert row_b["n_observations"] == 0


def test_write_baselines_roundtrip(tmp_path):
    out = tmp_path / "baselines.json"
    write_baselines([{"sku_id": "sku_a", "reference_price_clp": 1050.0}], out)

    assert out.exists()
    assert json.loads(out.read_text(encoding="utf-8")) == [
        {"sku_id": "sku_a", "reference_price_clp": 1050.0}
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_build_baselines.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'osint_mercado.build_baselines'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/osint_mercado/build_baselines.py
import argparse
import json
from datetime import date
from pathlib import Path

from osint_mercado.basket import load_basket, load_seed_observations
from osint_mercado.baseline import compute_reference


def build(basket_path, seed_prices_path, as_of: date) -> list[dict]:
    skus = load_basket(basket_path)
    observations = load_seed_observations(seed_prices_path)

    by_sku: dict[str, list] = {}
    for obs in observations:
        by_sku.setdefault(obs.sku_id, []).append(obs)

    baselines = [
        compute_reference(sku.sku_id, by_sku.get(sku.sku_id, []), as_of)
        for sku in skus
    ]
    return [
        {
            "sku_id": b.sku_id,
            "reference_price_clp": b.reference_price_clp,
            "confidence": b.confidence,
            "n_observations": b.n_observations,
            "freshest_observed_at": b.freshest_observed_at,
            "spread_ratio": b.spread_ratio,
        }
        for b in baselines
    ]


def write_baselines(rows: list[dict], path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute retail baselines for the controlled basket")
    ap.add_argument("--basket", default="data/basket.json")
    ap.add_argument("--seed-prices", default="data/seed_prices.json")
    ap.add_argument("--out", default="data/baselines.json")
    args = ap.parse_args()
    rows = build(args.basket, args.seed_prices, date.today())
    write_baselines(rows, args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_build_baselines.py -v`
Expected: 2 passed

- [ ] **Step 5: Register the CLI entry point**

In `pyproject.toml`, under `[project.scripts]`, add a line after the existing
`osint-ingest` entry:

```toml
[project.scripts]
osint-ingest = "osint_mercado.ingest:main"
osint-build-baselines = "osint_mercado.build_baselines:main"
```

Reinstall so the new console script is registered:

```bash
.venv/Scripts/python -m pip install -e ".[dev]"
```

- [ ] **Step 6: Run against the real curated data and commit the resulting baselines**

```bash
.venv/Scripts/python -m osint_mercado.build_baselines
```

Expected: prints `wrote data/baselines.json`. Inspect `data/baselines.json` — it should
have exactly 19 rows (one per basket SKU), matching sku_ids from `data/basket.json`.

```bash
.venv/Scripts/python -m ruff check src tests scripts
.venv/Scripts/python -m pytest -q
git add src/osint_mercado/build_baselines.py tests/test_build_baselines.py pyproject.toml data/baselines.json
git commit -m "feat(baseline): add build-baselines CLI and commit initial baselines snapshot"
git push
```

---

### Task 8: ADR 0010 — basket & baseline architecture

**Files:**
- Create: `docs/adr/0010-basket-baseline-seed-only-v1.md`
- Modify: `docs/adr/README.md`

**Interfaces:**
- None (documentation only).

- [ ] **Step 1: Write the ADR**

```markdown
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
refresh does not touch basket definitions, and vice versa.

Confidence is a three-tier signal computed from observation count, freshness, and price
spread, not a binary "has a seed price or doesn't":

- `high` — >=2 observations, freshest <=90 days old, spread ratio <=0.25
- `medium` — >=1 observation, freshest <=90 days old (below the `high` bar)
- `insufficient` — 0 observations, or all observations >90 days old

`reference_price_clp` is the median across all observations for a SKU. For v1 (seed-only)
this is the median of seed observations; once other sources exist, seed observations
continue to participate directly in that median rather than being a mere fallback — this
is what "anchored by the seed" means going forward.

## Consequences

- No new external network dependency or secret in this phase (no aggregator API key, no
  scraper). Lower risk, faster to ship correctly.
- Some basket SKUs may end up with only 1 observation or none, since real search results
  vary by product. Those compute to `confidence == "medium"` or `"insufficient"`
  respectively — an honest signal, not a gap papered over.
- Phase 3 must treat `"insufficient"` baselines as "needs baseline", not score them, per
  the PRD's baseline-confidence guardrail.
- Adding an aggregator/scrape source later is additive: a new loader function plus
  concatenation, no change to `compute_reference` or the confidence formula.

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
```

- [ ] **Step 2: Add the ADR to the index**

Read `docs/adr/README.md` first to match its existing table row format exactly, then add
a row for `0010` with title "Basket & retail baseline: seed-only v1, pluggable
multi-source design" and status "Accepted".

- [ ] **Step 3: Commit**

```bash
git add docs/adr/0010-basket-baseline-seed-only-v1.md docs/adr/README.md
git commit -m "docs: add ADR 0010 for basket/baseline architecture"
git push
```

---

### Task 9: Update ROADMAP and README status

**Files:**
- Modify: `ROADMAP.md`
- Modify: `README.md`

**Interfaces:**
- None (documentation only).

- [ ] **Step 1: Update ROADMAP.md's Phase 2 section**

Change the Phase 2 heading's `**Status:** Not Started` to `**Status:** Done`, and append
a line noting the shaping ADR:

```markdown
_Shaped by: ADR 0002, 0004, 0010._
```

(replacing the existing `_Shaped by: ADR 0002, 0004._` line for Phase 2.)

- [ ] **Step 2: Update README.md's Status section**

Change:

```markdown
- **Phase 2 (basket/baseline), 3 (matching/scoring), 4 (curation), 5
  (dashboard/deploy): Not started.**
```

to:

```markdown
- **Phase 2 — Basket & retail baseline engine: Done.** Curated a 19-SKU controlled
  basket with canonical keywords/units, seeded real retail price observations per SKU,
  and computes a median reference price with a high/medium/insufficient confidence tier.
- **Phase 3 (matching/scoring), 4 (curation), 5 (dashboard/deploy): Not started.**
```

- [ ] **Step 3: Commit**

```bash
git add ROADMAP.md README.md
git commit -m "docs: mark Phase 2 done in ROADMAP and README"
git push
```
