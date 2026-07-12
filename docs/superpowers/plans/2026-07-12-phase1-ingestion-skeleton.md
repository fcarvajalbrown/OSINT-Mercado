# Phase 1 — Ingestion Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reproducible pipeline that fetches municipal purchase orders from the Mercado Público órdenes de compra API for a given date and persists a normalized per-line-item dataset, runnable locally and on a scheduled GitHub Actions workflow.

**Architecture:** A small Python package. An HTTP client fetches the OC list-by-date and per-order detail from the ChileCompra API. A parser turns detail JSON into typed records; a municipal filter keeps only municipal buyers; a normalizer writes one row per line item to Parquet via Polars. A CLI ties it together; a GitHub Actions workflow runs it on a schedule using the ticket secret.

**Tech Stack:** Python 3.11+ (dev machine has 3.14), `requests` + `truststore` (HTTP with OS-truststore TLS), `polars` (dataframe/Parquet), `python-dotenv` (local env), `pytest` + `responses` (tests with mocked HTTP). Lint: `ruff`. Build metadata: `pyproject.toml` (PEP 621).

## Global Constraints

Every task implicitly includes these. Copied from the project's rules and spec.

- **No emojis anywhere** — code, comments, commits, docs, output.
- **No AI attribution anywhere** — no `Co-Authored-By`, no "Generated with …" lines in commits, code, or docs.
- **No pull requests unless explicitly requested** — commit directly to the working branch; do not run `gh pr create` on your own initiative.
- **Never guess or invent facts** — API field names, params, and quotas are verified against the real captured fixture (Task 1) or official docs before code depends on them. Use `context7` for library docs.
- **Not a lawyer / no legal advice** — scraping-ToS or licensing questions are deferred to a qualified lawyer, never answered in code or docs.
- **The API ticket is a secret** — it lives only in a gitignored `.env` (local) and a GitHub Actions secret named `CHILECOMPRA_API_TICKET`. Never commit it, never print it, never include it in a fixture or a logged URL.
- **TLS is always verified** — never disable certificate verification. Use `truststore` to trust the OS certificate store (the dev machine intercepts TLS with a self-signed corporate/AV cert).
- **Technical constraints from the spec/ADRs:** Python + Polars (no Rust/PyO3, ADR 0002); versioned data files as the store (ADR 0004); provenance fields (`oc_id`, `oc_url`, `captured_at`) on every persisted item (ADR 0007). v1 covers national **municipal** buyers only.

## Verified API facts (from this session's research)

- OC endpoint: `https://api.mercadopublico.cl/servicios/v1/publico/ordenesdecompra.json`
- Auth: `ticket` query param. Date: `fecha` query param in `ddmmaaaa` format (e.g. `09072026`). Formats: json/xml.
- Query variants: by order `codigo`, by `fecha` (all orders of a day), by organism code, by provider code.
- Response envelope: top-level `Cantidad` (int) and `Listado` (array). Exact per-order field names are locked from the real fixture in Task 1 — do not hard-code assumed names elsewhere; import them from `schema.py`.
- Sources: [ChileCompra API](https://www.chilecompra.cl/api/), [Utilización](https://api.mercadopublico.cl/modules/api.aspx).

## REVISION 2 (2026-07-12) — by-organism acquisition, Región Metropolitana scope (ADR 0008)

Implementation of Task 1 proved the by-date approach infeasible (list endpoint has no buyer or
prices; ~16,600 national orders/day; HTTP 429). This section **overrides** the tasks below
where they conflict; where they conflict, this section governs.

- **Scope:** v1 covers the **52 Región Metropolitana municipalities**, queried **by-organism** —
  not national by-date.
- **Task 2 (HTTP client):** additionally provide
  `build_by_organism_url(fecha, codigo_organismo, ticket)` →
  `…ordenesdecompra.json?fecha=…&CodigoOrganismo=…&ticket=…`; and add **retry-with-backoff on
  HTTP 429** in `fetch_json` (bounded retries, exponential backoff, honor `Retry-After` if
  present). Tests: assert the by-organism URL carries both params; mock a 429-then-200 sequence
  and assert it retries then succeeds.
- **NEW Task 5b (RM municipal codes):** build a versioned `data/rm_municipal_codes.json`
  mapping `comuna → CodigoOrganismo` for the 52 RM municipalities, each code **verified against a
  real API response** (query by-organism, confirm `NombreOrganismo`/comuna). Provide a discovery
  script; do NOT hard-code guessed codes. Full coverage may require sampling several dates; the
  list is expandable. Depends on Task 2.
- **Task 3 (parser):** the order creation date is **nested** — read
  `order[schema.OC_FECHAS][schema.OC_FECHA]` (schema.py already defines `OC_FECHAS = "Fechas"`),
  not `order.get(schema.OC_FECHA)`. Guard when `Fechas` is absent.
- **Task 6 (CLI):** replace the by-date loop with: load the RM codes; for each code, query
  by-organism for the date; collect order codes; fetch detail per order (throttled, backoff);
  parse; keep the municipal filter as a safety check; store. Add `--codes <path>` (RM codes
  file); keep `--max-orders` as a per-run safety cap.
- **Task 7 (workflow):** unchanged except the run command passes `--codes data/rm_municipal_codes.json`.

## File structure

- `pyproject.toml` — package metadata, dependencies, `ruff`/`pytest` config, console script.
- `src/osint_mercado/__init__.py` — package marker, version.
- `src/osint_mercado/config.py` — load the ticket from env (`.env` locally).
- `src/osint_mercado/schema.py` — centralized API field-name constants (source of truth, reconciled with the fixture).
- `src/osint_mercado/api_client.py` — URL building + `fetch_json` with `truststore` TLS.
- `src/osint_mercado/models.py` — typed records: `Buyer`, `LineItem`, `PurchaseOrder`.
- `src/osint_mercado/parser.py` — detail JSON → `PurchaseOrder`.
- `src/osint_mercado/municipal.py` — municipal-buyer predicate + filter.
- `src/osint_mercado/store.py` — orders → Polars DataFrame of line items → Parquet.
- `src/osint_mercado/ingest.py` — CLI entrypoint tying the pipeline together.
- `scripts/capture_fixtures.py` — one-off real-response capture (Task 1).
- `docs/api/ordenes-de-compra-schema.md` — observed real schema notes.
- `tests/fixtures/oc_list_sample.json`, `tests/fixtures/oc_detail_sample.json` — real captured fixtures (ticket stripped).
- `tests/test_*.py` — one test module per source module.
- `.github/workflows/ingest.yml` — scheduled + manual pipeline run.

---

### Task 1: Scaffolding, config loader, and live schema capture

**Files:**
- Create: `pyproject.toml`, `src/osint_mercado/__init__.py`, `src/osint_mercado/config.py`, `src/osint_mercado/schema.py`, `scripts/capture_fixtures.py`, `docs/api/ordenes-de-compra-schema.md`
- Test: `tests/test_config.py`, `tests/test_fixture_shape.py`
- Produce (by running the capture): `tests/fixtures/oc_list_sample.json`, `tests/fixtures/oc_detail_sample.json`

**Interfaces:**
- Produces: `config.load_ticket() -> str` (raises `RuntimeError` if unset); `schema.LIST_CANTIDAD`, `schema.LIST_LISTADO`, `schema.OC_CODIGO`, `schema.OC_COMPRADOR`, `schema.COMPRADOR_NOMBRE`, `schema.COMPRADOR_COMUNA`, `schema.OC_ITEMS`, `schema.ITEMS_LISTADO`, `schema.ITEM_PRODUCTO`, `schema.ITEM_CANTIDAD`, `schema.ITEM_PRECIO` (str constants, reconciled with the fixture).

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "osint-mercado"
version = "0.1.0"
description = "Audit Chilean municipal procurement for overpricing"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.32",
    "truststore>=0.9",
    "polars>=1.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "responses>=0.25", "ruff>=0.6"]

[project.scripts]
osint-ingest = "osint_mercado.ingest:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Create the package marker**

`src/osint_mercado/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Install the package (dev) into a venv**

Run:
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```
Expected: installs `requests`, `truststore`, `polars`, `python-dotenv`, `pytest`, `responses`, `ruff` without error.

- [ ] **Step 4: Write the failing test for the config loader**

`tests/test_config.py`:
```python
import pytest
from osint_mercado import config


def test_load_ticket_reads_env(monkeypatch):
    monkeypatch.setenv("CHILECOMPRA_API_TICKET", "TICKET-123")
    assert config.load_ticket() == "TICKET-123"


def test_load_ticket_missing_raises(monkeypatch):
    monkeypatch.delenv("CHILECOMPRA_API_TICKET", raising=False)
    with pytest.raises(RuntimeError, match="CHILECOMPRA_API_TICKET"):
        config.load_ticket()
```

- [ ] **Step 5: Run it and confirm it fails**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: osint_mercado.config` (module not yet created).

- [ ] **Step 6: Implement the config loader**

`src/osint_mercado/config.py`:
```python
import os
from dotenv import load_dotenv

TICKET_ENV = "CHILECOMPRA_API_TICKET"


def load_ticket() -> str:
    """Return the Mercado Publico API ticket from the environment (.env locally)."""
    load_dotenv()  # no-op if there is no .env (e.g. CI, where the secret is a real env var)
    ticket = os.getenv(TICKET_ENV)
    if not ticket:
        raise RuntimeError(f"{TICKET_ENV} is not set (put it in .env locally or a CI secret)")
    return ticket
```

- [ ] **Step 7: Run the test and confirm it passes**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 8: Create the schema constants with documented (to-be-reconciled) names**

`src/osint_mercado/schema.py`. These are the documented Mercado Público field names; Step 11 reconciles each against the real fixture and corrects any that differ.
```python
"""Single source of truth for Mercado Publico OC field names.

Values below are the documented names. After capturing the real fixture
(this task), verify each against tests/fixtures/oc_detail_sample.json and
correct any that differ. Nothing else in the codebase may hard-code these
strings; import from here.
"""

# List-by-date envelope
LIST_CANTIDAD = "Cantidad"
LIST_LISTADO = "Listado"

# Order (detail) fields
OC_CODIGO = "Codigo"
OC_NOMBRE = "Nombre"
OC_FECHA = "FechaCreacion"
OC_COMPRADOR = "Comprador"

# Buyer (Comprador) fields
COMPRADOR_NOMBRE = "NombreOrganismo"
COMPRADOR_CODIGO = "CodigoOrganismo"
COMPRADOR_COMUNA = "ComunaUnidad"
COMPRADOR_REGION = "RegionUnidad"

# Items container and line-item fields
OC_ITEMS = "Items"
ITEMS_LISTADO = "Listado"
ITEM_PRODUCTO = "Producto"
ITEM_CANTIDAD = "Cantidad"
ITEM_PRECIO = "PrecioNeto"
```

- [ ] **Step 9: Write the capture script**

`scripts/capture_fixtures.py`. Uses `truststore` (real TLS verification), strips the ticket from anything written, and refuses to save if the ticket string appears in the payload.
```python
"""Capture one real list-by-date and one detail response as test fixtures.

Run locally with a valid ticket in .env. TLS is verified via the OS trust
store (truststore), so the dev machine's intercepting cert is trusted
without weakening verification.
"""
import json
import sys
from pathlib import Path

import requests
import truststore

from osint_mercado.config import load_ticket

truststore.inject_into_ssl()

BASE = "https://api.mercadopublico.cl/servicios/v1/publico/ordenesdecompra.json"
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def get(params: dict) -> dict:
    resp = requests.get(BASE, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def save(name: str, payload: dict, ticket: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if ticket in text:
        raise SystemExit(f"Refusing to save {name}: ticket present in payload")
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / name).write_text(text, encoding="utf-8")
    print(f"wrote {name} ({len(text)} bytes)")


def main() -> None:
    ticket = load_ticket()
    fecha = sys.argv[1] if len(sys.argv) > 1 else "09072026"
    listing = get({"fecha": fecha, "ticket": ticket})
    save("oc_list_sample.json", listing, ticket)
    first = (listing.get("Listado") or [None])[0]
    if not first:
        raise SystemExit(f"No orders returned for fecha={fecha}; try another date")
    codigo = first["Codigo"]
    detail = get({"codigo": codigo, "ticket": ticket})
    save("oc_detail_sample.json", detail, ticket)


if __name__ == "__main__":
    main()
```

- [ ] **Step 10: Run the capture (real network + ticket)**

Run: `.venv/Scripts/python scripts/capture_fixtures.py 09072026`
Expected: writes `tests/fixtures/oc_list_sample.json` and `oc_detail_sample.json`. If the date has no orders, retry with a recent weekday in `ddmmaaaa` format. If TLS still fails, confirm the intercepting CA is in the Windows certificate store.

- [ ] **Step 11: Reconcile `schema.py` and document the real schema**

Open `tests/fixtures/oc_detail_sample.json`. For each constant in `schema.py`, confirm the real key name and correct it if it differs (the docs and the live payload occasionally diverge — this is the "don't guess" gate). Record the observed top-level and nested field names, and whether the **list** response already contains buyer/items (if it does, the detail fetch is redundant and Task 6's CLI can parse list items directly), in `docs/api/ordenes-de-compra-schema.md`.

- [ ] **Step 12: Write a fixture shape test**

`tests/test_fixture_shape.py`:
```python
import json
from pathlib import Path

from osint_mercado import schema

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_list_fixture_has_envelope():
    data = _load("oc_list_sample.json")
    assert schema.LIST_LISTADO in data
    assert isinstance(data[schema.LIST_LISTADO], list) and data[schema.LIST_LISTADO]


def test_detail_fixture_has_order_fields():
    data = _load("oc_detail_sample.json")
    order = data[schema.LIST_LISTADO][0]
    assert order[schema.OC_CODIGO]
    assert schema.OC_COMPRADOR in order
    assert schema.OC_ITEMS in order
```

- [ ] **Step 13: Run the shape test and confirm it passes**

Run: `.venv/Scripts/python -m pytest tests/test_fixture_shape.py -v`
Expected: PASS. If it fails on a key name, the reconciliation in Step 11 is incomplete — fix `schema.py`, not the test.

- [ ] **Step 14: Confirm fixtures contain no ticket, then commit**

Run: `grep -ri "ticket" tests/fixtures/ || echo "clean"`
Expected: no ticket value present.
```bash
git add pyproject.toml src/osint_mercado/__init__.py src/osint_mercado/config.py \
  src/osint_mercado/schema.py scripts/capture_fixtures.py \
  docs/api/ordenes-de-compra-schema.md tests/test_config.py \
  tests/test_fixture_shape.py tests/fixtures/oc_list_sample.json \
  tests/fixtures/oc_detail_sample.json
git commit -m "Phase 1: scaffolding, config loader, and captured OC schema fixtures"
```

---

### Task 2: HTTP client (URL building + fetch)

**Files:**
- Create: `src/osint_mercado/api_client.py`
- Test: `tests/test_api_client.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `api_client.BASE_URL: str`; `api_client.build_list_url(fecha, ticket) -> str`; `api_client.build_detail_url(codigo, ticket) -> str`; `api_client.make_session() -> requests.Session`; `api_client.fetch_json(url, session) -> dict` (raises `ApiError` on HTTP/network failure).

- [ ] **Step 1: Write failing tests with mocked HTTP**

`tests/test_api_client.py`:
```python
import pytest
import responses
from osint_mercado import api_client


def test_build_list_url_has_fecha_and_ticket():
    url = api_client.build_list_url("09072026", "T-1")
    assert url.startswith(api_client.BASE_URL)
    assert "fecha=09072026" in url
    assert "ticket=T-1" in url


def test_build_detail_url_has_codigo_and_ticket():
    url = api_client.build_detail_url("1234-5-SE20", "T-1")
    assert "codigo=1234-5-SE20" in url
    assert "ticket=T-1" in url


@responses.activate
def test_fetch_json_returns_payload():
    responses.add(responses.GET, api_client.BASE_URL, json={"Cantidad": 0, "Listado": []}, status=200)
    session = api_client.make_session()
    out = api_client.fetch_json(api_client.build_list_url("09072026", "T-1"), session)
    assert out["Cantidad"] == 0


@responses.activate
def test_fetch_json_raises_on_http_error():
    responses.add(responses.GET, api_client.BASE_URL, status=500)
    session = api_client.make_session()
    with pytest.raises(api_client.ApiError):
        api_client.fetch_json(api_client.build_list_url("09072026", "T-1"), session)
```

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/Scripts/python -m pytest tests/test_api_client.py -v`
Expected: FAIL with `ModuleNotFoundError: osint_mercado.api_client`.

- [ ] **Step 3: Implement the client**

`src/osint_mercado/api_client.py`:
```python
from urllib.parse import urlencode

import requests
import truststore

truststore.inject_into_ssl()  # verify TLS against the OS trust store

BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico/ordenesdecompra.json"


class ApiError(RuntimeError):
    """Raised when the OC API request fails."""


def build_list_url(fecha: str, ticket: str) -> str:
    return f"{BASE_URL}?{urlencode({'fecha': fecha, 'ticket': ticket})}"


def build_detail_url(codigo: str, ticket: str) -> str:
    return f"{BASE_URL}?{urlencode({'codigo': codigo, 'ticket': ticket})}"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "osint-mercado/0.1"})
    return session


def fetch_json(url: str, session: requests.Session) -> dict:
    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        # Do not include the URL (it carries the ticket) in the message.
        raise ApiError(f"OC API request failed: {type(exc).__name__}") from exc
```

- [ ] **Step 4: Run and confirm pass**

Run: `.venv/Scripts/python -m pytest tests/test_api_client.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/osint_mercado/api_client.py tests/test_api_client.py
git commit -m "Phase 1: OC API HTTP client with OS-truststore TLS"
```

---

### Task 3: Parse detail JSON into typed records

**Files:**
- Create: `src/osint_mercado/models.py`, `src/osint_mercado/parser.py`
- Test: `tests/test_parser.py`

**Interfaces:**
- Consumes: `schema.*` constants (Task 1); the committed `oc_detail_sample.json`.
- Produces: dataclasses `Buyer(name: str, code: str, comuna: str, region: str)`, `LineItem(product: str, quantity: float, unit_price: float)`, `PurchaseOrder(codigo: str, name: str, fecha: str, buyer: Buyer, items: list[LineItem])`; `parser.parse_detail(payload: dict) -> list[PurchaseOrder]`.

- [ ] **Step 1: Write failing tests against the real fixture**

Tests assert invariants (types, non-empty, positive), not guessed literal values.

`tests/test_parser.py`:
```python
import json
from pathlib import Path

from osint_mercado import parser
from osint_mercado.models import PurchaseOrder

FIX = Path(__file__).parent / "fixtures"


def _detail():
    return json.loads((FIX / "oc_detail_sample.json").read_text(encoding="utf-8"))


def test_parse_detail_returns_orders():
    orders = parser.parse_detail(_detail())
    assert orders and isinstance(orders[0], PurchaseOrder)


def test_parsed_order_has_core_fields():
    order = parser.parse_detail(_detail())[0]
    assert order.codigo
    assert order.buyer.name
    assert order.items
    assert order.items[0].unit_price > 0
    assert order.items[0].quantity > 0
```

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/Scripts/python -m pytest tests/test_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: osint_mercado.parser`.

- [ ] **Step 3: Implement the models**

`src/osint_mercado/models.py`:
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Buyer:
    name: str
    code: str
    comuna: str
    region: str


@dataclass(frozen=True)
class LineItem:
    product: str
    quantity: float
    unit_price: float


@dataclass(frozen=True)
class PurchaseOrder:
    codigo: str
    name: str
    fecha: str
    buyer: Buyer
    items: list[LineItem]
```

- [ ] **Step 4: Implement the parser**

`src/osint_mercado/parser.py`. Uses only `schema.*` names, so a reconciliation fix in Task 1 flows through here automatically.
```python
from osint_mercado import schema
from osint_mercado.models import Buyer, LineItem, PurchaseOrder


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_buyer(order: dict) -> Buyer:
    comprador = order.get(schema.OC_COMPRADOR) or {}
    return Buyer(
        name=str(comprador.get(schema.COMPRADOR_NOMBRE, "")),
        code=str(comprador.get(schema.COMPRADOR_CODIGO, "")),
        comuna=str(comprador.get(schema.COMPRADOR_COMUNA, "")),
        region=str(comprador.get(schema.COMPRADOR_REGION, "")),
    )


def _parse_items(order: dict) -> list[LineItem]:
    container = order.get(schema.OC_ITEMS) or {}
    rows = container.get(schema.ITEMS_LISTADO) or []
    return [
        LineItem(
            product=str(row.get(schema.ITEM_PRODUCTO, "")),
            quantity=_to_float(row.get(schema.ITEM_CANTIDAD)),
            unit_price=_to_float(row.get(schema.ITEM_PRECIO)),
        )
        for row in rows
    ]


def parse_detail(payload: dict) -> list[PurchaseOrder]:
    orders = payload.get(schema.LIST_LISTADO) or []
    return [
        PurchaseOrder(
            codigo=str(order.get(schema.OC_CODIGO, "")),
            name=str(order.get(schema.OC_NOMBRE, "")),
            fecha=str(order.get(schema.OC_FECHA, "")),
            buyer=_parse_buyer(order),
            items=_parse_items(order),
        )
        for order in orders
    ]
```

- [ ] **Step 5: Run and confirm pass**

Run: `.venv/Scripts/python -m pytest tests/test_parser.py -v`
Expected: PASS (2 passed). A failure here means a `schema.py` name still does not match the fixture — fix the constant, not the parser.

- [ ] **Step 6: Commit**

```bash
git add src/osint_mercado/models.py src/osint_mercado/parser.py tests/test_parser.py
git commit -m "Phase 1: parse OC detail JSON into typed records"
```

---

### Task 4: Municipal-buyer filter

**Files:**
- Create: `src/osint_mercado/municipal.py`
- Test: `tests/test_municipal.py`

**Interfaces:**
- Consumes: `models.PurchaseOrder`, `models.Buyer` (Task 3).
- Produces: `municipal.is_municipal(buyer_name: str) -> bool`; `municipal.filter_municipal(orders: list[PurchaseOrder]) -> list[PurchaseOrder]`.

- [ ] **Step 1: Write failing tests**

`tests/test_municipal.py`:
```python
from osint_mercado import municipal
from osint_mercado.models import Buyer, PurchaseOrder


def _order(buyer_name):
    return PurchaseOrder("C1", "n", "01012026", Buyer(buyer_name, "1", "X", "Y"), [])


def test_is_municipal_matches_municipalidad():
    assert municipal.is_municipal("I. MUNICIPALIDAD DE NUNOA")
    assert municipal.is_municipal("Municipalidad de Santiago")
    assert municipal.is_municipal("CORPORACION MUNICIPAL DE VALPARAISO")


def test_is_municipal_rejects_non_municipal():
    assert not municipal.is_municipal("SERVICIO DE SALUD METROPOLITANO")
    assert not municipal.is_municipal("MINISTERIO DE OBRAS PUBLICAS")


def test_filter_municipal_keeps_only_municipal():
    orders = [_order("Municipalidad de Maipu"), _order("Ministerio de Salud")]
    kept = municipal.filter_municipal(orders)
    assert len(kept) == 1
    assert kept[0].buyer.name == "Municipalidad de Maipu"
```

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/Scripts/python -m pytest tests/test_municipal.py -v`
Expected: FAIL with `ModuleNotFoundError: osint_mercado.municipal`.

- [ ] **Step 3: Implement the filter**

`src/osint_mercado/municipal.py`. The `MUNICIPAL` substring (case-insensitive, accent-insensitive) catches "Municipalidad", "I. Municipalidad", and "Corporación Municipal". Task 1's schema notes confirm buyer names look like this; refine to an official municipal-organism code list in a later phase.
```python
import unicodedata

from osint_mercado.models import PurchaseOrder


def _normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    return "".join(c for c in stripped if not unicodedata.combining(c)).upper()


def is_municipal(buyer_name: str) -> bool:
    return "MUNICIPAL" in _normalize(buyer_name)


def filter_municipal(orders: list[PurchaseOrder]) -> list[PurchaseOrder]:
    return [o for o in orders if is_municipal(o.buyer.name)]
```

- [ ] **Step 4: Run and confirm pass**

Run: `.venv/Scripts/python -m pytest tests/test_municipal.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/osint_mercado/municipal.py tests/test_municipal.py
git commit -m "Phase 1: municipal-buyer filter"
```

---

### Task 5: Normalize to Polars DataFrame and write Parquet

**Files:**
- Create: `src/osint_mercado/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `models.PurchaseOrder` (Task 3).
- Produces: `store.ITEM_COLUMNS: list[str]`; `store.orders_to_items_df(orders, captured_at) -> polars.DataFrame` (one row per line item, with provenance columns); `store.write_parquet(df, path) -> None`.

- [ ] **Step 1: Write failing tests**

`tests/test_store.py`:
```python
from osint_mercado import store
from osint_mercado.models import Buyer, LineItem, PurchaseOrder


def _orders():
    buyer = Buyer("Municipalidad de Nunoa", "1", "Nunoa", "RM")
    items = [LineItem("Toner HP 85A", 2.0, 45000.0)]
    return [PurchaseOrder("1234-5-SE26", "compra", "01072026", buyer, items)]


def test_orders_to_items_df_one_row_per_item():
    df = store.orders_to_items_df(_orders(), captured_at="2026-07-12T00:00:00Z")
    assert df.height == 1
    assert set(store.ITEM_COLUMNS).issubset(set(df.columns))
    row = df.row(0, named=True)
    assert row["oc_id"] == "1234-5-SE26"
    assert row["unit_price"] == 45000.0
    assert row["oc_url"].endswith("1234-5-SE26")
    assert row["captured_at"] == "2026-07-12T00:00:00Z"


def test_write_parquet_roundtrip(tmp_path):
    import polars as pl

    df = store.orders_to_items_df(_orders(), captured_at="2026-07-12T00:00:00Z")
    out = tmp_path / "items.parquet"
    store.write_parquet(df, out)
    assert out.exists()
    assert pl.read_parquet(out).height == 1
```

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/Scripts/python -m pytest tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: osint_mercado.store`.

- [ ] **Step 3: Implement the store**

`src/osint_mercado/store.py`. `oc_url` is the provenance link (ADR 0007).
```python
from pathlib import Path

import polars as pl

from osint_mercado.models import PurchaseOrder

OC_PUBLIC_URL = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idOC="

ITEM_COLUMNS = [
    "oc_id", "buyer_name", "buyer_code", "comuna", "region", "fecha",
    "product", "quantity", "unit_price", "oc_url", "captured_at",
]


def orders_to_items_df(orders: list[PurchaseOrder], captured_at: str) -> pl.DataFrame:
    rows = [
        {
            "oc_id": o.codigo,
            "buyer_name": o.buyer.name,
            "buyer_code": o.buyer.code,
            "comuna": o.buyer.comuna,
            "region": o.buyer.region,
            "fecha": o.fecha,
            "product": item.product,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "oc_url": f"{OC_PUBLIC_URL}{o.codigo}",
            "captured_at": captured_at,
        }
        for o in orders
        for item in o.items
    ]
    return pl.DataFrame(rows, schema=ITEM_COLUMNS)


def write_parquet(df: pl.DataFrame, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
```

Note: confirm in Task 1's schema notes that the public OC URL parameter (`idOC=` above) matches how mercadopublico.cl links to an order; if the real deep-link differs, update `OC_PUBLIC_URL` and the `test_write_parquet_roundtrip` assertion accordingly.

- [ ] **Step 4: Run and confirm pass**

Run: `.venv/Scripts/python -m pytest tests/test_store.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/osint_mercado/store.py tests/test_store.py
git commit -m "Phase 1: normalize orders to Parquet line-item dataset with provenance"
```

---

### Task 6: CLI entrypoint (end-to-end pipeline)

**Files:**
- Create: `src/osint_mercado/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `config`, `api_client`, `parser`, `municipal`, `store` (all prior tasks).
- Produces: `ingest.run(fecha, out_dir, ticket, session=None, max_orders=None) -> Path` (returns the written parquet path); `ingest.main()` (argparse CLI).

- [ ] **Step 1: Write a failing end-to-end test with mocked HTTP**

`tests/test_ingest.py`. Mocks the list call and one detail call; asserts the output keeps municipal buyers only.
```python
import json
from pathlib import Path

import polars as pl
import responses

from osint_mercado import api_client, ingest, schema

FIX = Path(__file__).parent / "fixtures"


def _detail_payload():
    return json.loads((FIX / "oc_detail_sample.json").read_text(encoding="utf-8"))


@responses.activate
def test_run_writes_municipal_items(tmp_path, monkeypatch):
    detail = _detail_payload()
    codigo = detail[schema.LIST_LISTADO][0][schema.OC_CODIGO]
    # Force the parsed buyer to be municipal so the row survives the filter.
    detail[schema.LIST_LISTADO][0][schema.OC_COMPRADOR][schema.COMPRADOR_NOMBRE] = "Municipalidad de Test"
    listing = {schema.LIST_CANTIDAD: 1, schema.LIST_LISTADO: [{schema.OC_CODIGO: codigo}]}

    responses.add(responses.GET, api_client.BASE_URL, json=listing, status=200)
    responses.add(responses.GET, api_client.BASE_URL, json=detail, status=200)

    out = ingest.run(fecha="09072026", out_dir=tmp_path, ticket="T-1",
                     session=api_client.make_session())
    df = pl.read_parquet(out)
    assert df.height >= 1
    assert df.select(pl.col("buyer_name")).row(0)[0].startswith("Municipalidad")
```

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/Scripts/python -m pytest tests/test_ingest.py -v`
Expected: FAIL with `ModuleNotFoundError: osint_mercado.ingest`.

- [ ] **Step 3: Implement the CLI/pipeline**

`src/osint_mercado/ingest.py`. `captured_at` is passed in / defaulted at call time (not hard-coded) for provenance.
```python
import argparse
from datetime import datetime, timezone
from pathlib import Path

from osint_mercado import api_client, municipal, parser, store, schema
from osint_mercado.config import load_ticket


def run(fecha: str, out_dir, ticket: str, session=None, max_orders=None) -> Path:
    session = session or api_client.make_session()
    listing = api_client.fetch_json(api_client.build_list_url(fecha, ticket), session)
    codes = [row.get(schema.OC_CODIGO) for row in (listing.get(schema.LIST_LISTADO) or [])]
    codes = [c for c in codes if c]
    if max_orders is not None:
        codes = codes[:max_orders]

    orders = []
    for codigo in codes:
        detail = api_client.fetch_json(api_client.build_detail_url(codigo, ticket), session)
        orders.extend(parser.parse_detail(detail))

    municipals = municipal.filter_municipal(orders)
    captured_at = datetime.now(timezone.utc).isoformat()
    df = store.orders_to_items_df(municipals, captured_at=captured_at)

    out_path = Path(out_dir) / f"oc_items_{fecha}.parquet"
    store.write_parquet(df, out_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest municipal purchase orders for a date")
    ap.add_argument("--fecha", required=True, help="date in ddmmaaaa format, e.g. 09072026")
    ap.add_argument("--out", default="data", help="output directory")
    ap.add_argument("--max-orders", type=int, default=None, help="cap orders fetched (skeleton)")
    args = ap.parse_args()
    path = run(fecha=args.fecha, out_dir=args.out, ticket=load_ticket(), max_orders=args.max_orders)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run and confirm pass**

Run: `.venv/Scripts/python -m pytest tests/test_ingest.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run the full test suite and lint**

Run: `.venv/Scripts/python -m pytest -q && .venv/Scripts/python -m ruff check src tests`
Expected: all tests pass; ruff reports no errors.

- [ ] **Step 6: Smoke-test end-to-end against the live API (bounded)**

Run: `.venv/Scripts/python -m osint_mercado.ingest --fecha 09072026 --out data --max-orders 25`
Expected: prints `wrote data/oc_items_09072026.parquet`. Inspect it:
`.venv/Scripts/python -c "import polars as pl; print(pl.read_parquet('data/oc_items_09072026.parquet').head())"`
Expected: municipal line items with prices and `oc_url` links.

- [ ] **Step 7: Commit (do not commit the live-run data file yet)**

Ensure `data/` output is not staged (retention policy is a later phase; the CI artifact is the deliverable).
```bash
echo "data/" >> .gitignore
git add src/osint_mercado/ingest.py tests/test_ingest.py .gitignore
git commit -m "Phase 1: end-to-end ingestion CLI"
```

---

### Task 7: Scheduled GitHub Actions workflow

**Files:**
- Create: `.github/workflows/ingest.yml`

**Interfaces:**
- Consumes: the `osint-ingest` console script / `osint_mercado.ingest` module; the `CHILECOMPRA_API_TICKET` repository secret.
- Produces: a daily + manually-dispatchable workflow that runs ingestion and uploads the dataset as an artifact.

Note: this task requires a GitHub **remote** and the repository secret, which are Felipe's to set up (the repo is local-only per project rules, and creating a remote is a deliberate step). Write and commit the workflow file now; the actual CI run is verified once the remote and secret exist.

- [ ] **Step 1: Write the workflow**

`.github/workflows/ingest.yml`:
```yaml
name: ingest

on:
  schedule:
    - cron: "0 12 * * *"  # daily 12:00 UTC (about 08:00 Chile time)
  workflow_dispatch:
    inputs:
      fecha:
        description: "date ddmmaaaa (default: yesterday)"
        required: false

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install
        run: pip install -e ".[dev]"
      - name: Compute fecha
        id: d
        run: |
          if [ -n "${{ github.event.inputs.fecha }}" ]; then
            echo "fecha=${{ github.event.inputs.fecha }}" >> "$GITHUB_OUTPUT"
          else
            echo "fecha=$(date -u -d yesterday +%d%m%Y)" >> "$GITHUB_OUTPUT"
          fi
      - name: Run ingestion
        env:
          CHILECOMPRA_API_TICKET: ${{ secrets.CHILECOMPRA_API_TICKET }}
        run: osint-ingest --fecha "${{ steps.d.outputs.fecha }}" --out data --max-orders 200
      - name: Upload dataset
        uses: actions/upload-artifact@v4
        with:
          name: oc-items-${{ steps.d.outputs.fecha }}
          path: data/*.parquet
          if-no-files-found: warn
```

- [ ] **Step 2: Validate the YAML locally**

Run: `.venv/Scripts/python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ingest.yml')); print('valid yaml')"`
Expected: `valid yaml` (install `pyyaml` if missing: `.venv/Scripts/python -m pip install pyyaml`).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ingest.yml
git commit -m "Phase 1: scheduled GitHub Actions ingestion workflow"
```

- [ ] **Step 4: Setup steps for Felipe (documented, run when ready — not automated)**

1. Create a GitHub remote and push (`git remote add origin …` then `git push -u origin master`).
2. In the repo: Settings → Secrets and variables → Actions → New repository secret → name `CHILECOMPRA_API_TICKET`, value = your ticket.
3. Actions tab → `ingest` → Run workflow (manual dispatch) → confirm the artifact uploads.

---

## Self-Review

**Spec coverage (Phase 1 rows of ROADMAP):**
- Register/confirm API ticket + endpoint/params → Task 1 (verified facts + capture), Task 2 (client). ✓
- Fetch municipal-buyer OCs for a date window → Task 6 (CLI), Task 4 (municipal filter). ✓
- Persist responses / normalized data → Task 5 (Parquet store, ADR 0004), fixtures in Task 1. ✓
- First scheduled GitHub Actions workflow → Task 7. ✓
- Provenance fields on every item (ADR 0007) → Task 5 (`oc_url`, `captured_at`). ✓
- Python + Polars, no Rust (ADR 0002) → stack + Task 5. ✓

**Placeholder scan:** No "TBD/TODO"; every code step has complete code. The two conditional notes (list-vs-detail shape, exact deep-link param) are explicit reconciliation instructions tied to the real fixture, not deferred work.

**Type consistency:** `PurchaseOrder`/`Buyer`/`LineItem` field names are used identically in `parser.py`, `municipal.py`, `store.py`, `ingest.py`, and tests. `schema.*` constants are the single source for API field names. `ITEM_COLUMNS` names match the dict keys built in `orders_to_items_df` and the assertions in `test_store.py`/`test_ingest.py`.

**Known-uncertainty handling:** API field names and the OC deep-link are pinned to the real captured fixture (Task 1) before dependent code runs — honoring "never guess." Municipal identification uses a name heuristic in v1, with an official-organism-code list flagged as a later-phase refinement.
