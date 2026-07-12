# OSINT-Mercado

Public-interest web application that audits Chilean municipal procurement for
structural overpricing. A Python pipeline ingests purchase orders (órdenes de
compra) from the Mercado Público / ChileCompra API, cross-references them
against a curated retail price baseline for a controlled basket of commoditized
goods, and flags purchases that deviate from the retail reference beyond a
configurable threshold. Every published flag links back to its official
source order so any claim can be independently verified.

## Status

- **Phase 1 — Data ingestion skeleton: Done.** Ingests purchase orders for the
  52 municipalities of the Región Metropolitana via the Mercado Público
  by-organism API and writes a normalized per-line-item Parquet dataset.
- **Phase 1.5 — Parser enrichment: Done.** Extracts order status/type (dropping
  cancelled orders), raw currency/tax fields, and UNSPSC product-classification
  codes.
- **Phase 2 — Basket & retail baseline engine: Done.** Curated a 19-SKU controlled
  basket with canonical keywords/units, seeded real retail price observations per SKU,
  and computes a median reference price with a high/medium/insufficient confidence tier.
- **Phase 3 (matching/scoring), 4 (curation), 5 (dashboard/deploy): Not started.**

See `ROADMAP.md` for phase-by-phase status and `PRD.md` for the stable product
vision. Every significant architectural decision is recorded in `docs/adr/`.

## Architecture

Split across three planes (`docs/adr/0001`):

- **Pipeline (external compute).** Python + Polars, runs on GitHub Actions on a
  schedule (`.github/workflows/ingest.yml`). Python does not run on the target
  Hostinger shared host, so external compute is a hard requirement.
- **Store (versioned files).** The dataset lives as versioned Parquet/JSON
  files committed to the repo; git history is the audit trail (`docs/adr/0004`).
- **Presentation (static site, Phase 5).** A static dashboard deployed to
  Hostinger, not yet built.

## Repo layout

```
src/osint_mercado/   Pipeline package (ingest, parse, filter, store)
tests/               Test suite, including real captured API fixtures
scripts/             One-off/maintenance scripts (fixture capture, RM code discovery)
data/                Versioned output datasets and reference lists
docs/adr/            Architecture decision records (source of truth for decisions)
docs/api/            Reconciled Mercado Público API schema notes
docs/research/       Research reports backing specific phases
docs/superpowers/    Design specs and implementation plans
PRD.md               Stable product vision (rarely changes)
ROADMAP.md           Phase-based status (not calendar-dated)
```

## Development setup

Requires Python 3.11+ (dev machine runs 3.14).

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

Copy `.env.example` (if present) or create a `.env` with a free ChileCompra API
ticket:

```
CHILECOMPRA_API_TICKET=your-ticket-here
```

Run the test suite and linter:

```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check src tests scripts
```

Run ingestion for a given date:

```bash
.venv/Scripts/python -m osint_mercado.ingest --fecha 09072026 --out data
```

## Contributing conventions

Development conventions (commit style, TDD, secrets handling, TLS interception
on this dev machine, never guessing API field names) are documented in
`CLAUDE.md`.
