# 0008 — By-organism API acquisition, scoped to the Región Metropolitana

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

Implementation of Phase 1 surfaced that the órdenes de compra API is far thinner than the
original plan assumed:

- The **list-by-date** endpoint (`ordenesdecompra.json?fecha=…`) returns only `Codigo`,
  `Nombre`, and `CodigoEstado` — **no buyer, no comuna, no items, no prices**. Getting any
  price requires a **detail call per order** (`?codigo=…`).
- A single national day returned **16,664 orders**, and the listing does not identify the
  buyer, so filtering to municipalities would require fetching detail for *every* order just
  to discover which are municipal. A live **HTTP 429** was hit almost immediately. National
  by-date + detail is not feasible against this rate-limited API.
- The **bulk open-data** shortcut does not rescue us: Chile's OCDS bulk dataset is
  tenders-only and its public mirror is stale (Dec 2018–Apr 2022), explicitly **excluding
  Compra Ágil, Convenio Marco, and direct purchase orders** — the exact methods municipal
  commodity purchases use.

However, the API **does** support filtering by buyer:
`ordenesdecompra.json?fecha=…&CodigoOrganismo=…&ticket=…` returns only that organism's
orders for the date.

## Decision

Acquire OC data via **by-organism queries**: for a curated list of municipal organism codes,
query `fecha + CodigoOrganismo` to get that municipality's order codes for the day, then fetch
detail per order (throttled, with backoff on 429). This pre-filters to municipal buyers and
bounds the request volume.

**v1 scope is the 52 municipalities of the Región Metropolitana.** Maintain a versioned
`comuna → CodigoOrganismo` list, each code verified against a real API response. Expand to
other regions and eventually national coverage in later phases.

This supersedes the by-date + detail ingestion approach in the Phase 1 plan and refines the
"national municipal buyers" wording of the v1 spec (`PRD.md`, the design spec) to the Región
Metropolitana for v1. National coverage remains the long-term goal.

## Consequences

- Feasible, bounded acquisition, pre-filtered to municipal, and it covers the commodity-OC
  methods the bulk dumps exclude.
- Introduces a maintained artifact: the RM municipal organism-code list (one-time build,
  verified, expandable). Building it is a Phase 1 task.
- Still N+1 (detail per order) but bounded per municipality; the HTTP client must throttle and
  back off on 429.
- Freshness is daily.

## Alternatives considered

- **By-date + detail, national.** Rejected: infeasible (volume, no pre-filter to municipal,
  rate limits).
- **Bulk open-data (OCDS / descargas CSV).** Rejected for v1: OCDS is tenders-only and stale
  and excludes our purchase methods. The ChileCompra "descargas" CSVs may cover more but their
  item-level granularity is unconfirmed; revisit as a possible later national source via a
  dedicated spike.
- **Hybrid bulk + API now.** Deferred: no usable bulk source for our methods today, so no
  benefit yet.
