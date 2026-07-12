# 0011 — Currency conversion to CLP and net-vs-gross (IVA) alignment

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

ADR 0009 captured the raw currency/tax fields (`Moneda`/`TipoMoneda`, `PorcentajeIva`,
`PrecioNeto`, `Total`/`TotalNeto`, ...) losslessly and deferred CLP normalization to
whichever of Phase 2 or Phase 3 first needed CLP-comparable prices. Phase 3 (matching &
anomaly scoring) is that consumer: no overprice ratio is valid until every order unit price
is expressed in the same currency (CLP) and on the same tax basis as the gross retail
baseline.

Two independent corrections are required. (1) Mercado Público orders can be denominated in
five currencies — CLP, CLF (UF), USD, UTM, EUR (confirmed from the official ChileCompra API
page, per `docs/research/2026-07-12-parser-improvement.md` §2.1). (2) `PrecioNeto` is
net-of-tax while Chilean retail sticker prices are gross (IVA included); comparing the two
directly understates OC prices by ~19%.

## Decision

**Currency.** Convert non-CLP amounts to CLP with a `mindicador.cl`-backed rate, keyed by
the order's own date. The endpoint shape was verified live (2026-07-12):
`GET https://mindicador.cl/api/{indicador}/{dd-mm-yyyy}` returns
`{..., serie: [{fecha, valor}]}` where `valor` is the CLP value of one unit of the indicator
that day. Indicator mapping (verified): `CLF/UF → uf`, `USD → dolar`, `UTM → utm`,
`EUR → euro`, `CLP → no conversion`. mindicador field names and the currency map live in a
dedicated `mindicador_schema.py` (the single source of truth, mirroring `schema.py`); no
other module hard-codes them. mindicador is key-free — no new secret.

Rates are cached in a committed, date-keyed `data/fx_rates.json` (`"indicator:YYYY-MM-DD" →
valor`). USD/EUR/UF have no published value on weekends/holidays, so a cache miss walks back
up to 7 days to the nearest prior business day and caches the result under the originally
requested date (re-run stability). TLS is verified against the OS trust store (the `fx`
module reaches the network only through `api_client`, which calls
`truststore.inject_into_ssl()`); verification is never disabled.

**IVA.** Align net-to-gross by grossing **up** the order price:
`gross = net × (1 + PorcentajeIva/100)`, using the order-level `PorcentajeIva`. Exempt
orders (`PorcentajeIva == 0`) yield `gross == net`. Verified against the real fixture:
`TotalNeto 452976 × 1.19 = Total 539041`. Grossing up the OC price (rather than netting down
the baseline) keeps the published baseline equal to the real retail sticker price a reader
can independently verify.

## Consequences

- Cross-currency and net/gross comparisons are now valid; the USD and IVA-exempt orders seen
  in a real RM capture are handled correctly.
- One network call per new `(indicator, date)` pair, not per order; the committed cache makes
  CI runs and re-runs deterministic and provides an audit trail of exactly which rate was
  used.
- `parser.py` remains a pure, network-free function (ADR 0009); conversion happens later, in
  the scoring stage.
- If mindicador is unreachable for a needed non-CLP date, that line cannot be scored until
  the rate is available — an explicit failure, not a silent mis-comparison.

## Alternatives considered

- **Net down the baseline instead of grossing up the OC price.** Rejected: the published
  baseline would no longer match the retailer's sticker price, weakening verifiability.
- **Fixed/hardcoded rates or a non-dated rate.** Rejected: UF compounds daily and USD/EUR
  move daily; a non-dated rate silently mis-converts.
- **Convert at ingest time.** Rejected (already by ADR 0009): couples the daily ingest to an
  external dependency before it is load-bearing and breaks the pure-parser convention.
