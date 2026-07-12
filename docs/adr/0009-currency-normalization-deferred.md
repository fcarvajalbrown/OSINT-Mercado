# 0009 — Currency and tax fields captured raw; CLP normalization deferred

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

Phase 1.5 parser-enrichment research (`docs/research/2026-07-12-parser-improvement.md`,
section 2.1-2.2) found that Mercado Público purchase orders can be denominated in five
currency types (CLP, CLF/UF, USD, UTM, EUR) and are usually net-of-IVA. Comparing
`PrecioNeto` across orders without accounting for `Moneda`/`TipoMoneda` and
`PorcentajeIva` would silently mix incompatible values once a non-CLP order appears in
the dataset, and would understate OC prices ~19% relative to a gross retail baseline.

Converting UTM/UF/USD/EUR amounts to CLP needs an external, date-anchored rate source.
The research identifies `mindicador.cl` (a free, no-key REST mirror of Banco Central de
Chile's daily indicators) as the practical option, plus a local cache keyed by
currency+date to avoid a network call per order at parse/ingest time.

No price comparison exists yet in this codebase — that's Phase 2 (basket/baseline) and
Phase 3 (matching/anomaly scoring) work. Building the conversion module now would mean
designing rate-caching and staleness handling before either consumer exists to validate
the design against.

## Decision

Phase 1.5 extracts and stores the raw currency/tax fields losslessly (`Moneda`,
`TipoMoneda`, `PorcentajeIva`, `PrecioNeto`, `Total`, `TotalNeto`, `Impuestos`,
`Cargos`, `Descuentos`, and their item-level equivalents) without converting anything
to CLP. `parser.py` makes no network calls and stays a pure function, matching its
current convention.

CLP normalization (the `mindicador.cl`-backed conversion utility, its rate cache, and
the net-vs-gross alignment logic) is deferred to whichever of Phase 2 or Phase 3 first
needs CLP-comparable prices for anomaly scoring. All the raw values needed to convert
later are captured now, so no re-parsing of historical data will be required when that
module is built.

## Consequences

- No non-CLP or net/gross-price comparison is possible yet — by construction, since no
  comparison logic exists yet either. This ADR does not block Phase 1.5's ingestion or
  storage work.
- The eventual conversion module is unblocked: currency code, tax rate, and both net
  and gross totals are already on every stored order/item.
- Whoever builds Phase 2/3 must implement the `mindicador.cl` integration (or an
  alternative) and a rate cache before doing any cross-currency price comparison —
  tracked as a prerequisite in `ROADMAP.md`'s Phase 2/3 sections, not a surprise gap.
- If a non-CLP order shows up in the dataset before conversion is built, any naive
  price-comparison code written against `unit_price`/`total` without checking
  `moneda`/`tipo_moneda` first would silently produce wrong results — this is a known,
  documented risk for whoever implements Phase 2/3, not an oversight.

## Alternatives considered

- **Convert to CLP inline during Phase 1.5 ingestion.** Rejected for now: requires
  building the `mindicador.cl` client, a date-keyed rate cache, and net/gross alignment
  logic before either downstream consumer (Phase 2 baseline, Phase 3 scoring) exists to
  validate the design against. Also couples the ingest pipeline to a new external
  dependency (`mindicador.cl` availability) on every daily run before that dependency is
  load-bearing.
- **Convert inside `parser.py` itself.** Rejected regardless of timing: would require
  network I/O inside what is currently a pure, easily-unit-tested function, breaking the
  existing convention that parsing has no side effects.
