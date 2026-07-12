# Idea: ChileCompra Data Product (short PRD / concept capture)

> **Status:** Concept only. Captured 2026-07-12. Not committed, not started. This is a
> separate, potentially commercial product from OSINT-Mercado (which is a non-commercial
> watchdog). Parked here so the idea isn't lost; validate everything below before acting.

## One line

A value-added data product on top of Chile's public procurement data (ChileCompra /
Mercado Público): a clean API and/or dashboard that serves the *usable* information the
official channels bury.

## The opportunity (grounded in what we verified building OSINT-Mercado)

Chile's procurement data is nominally "open" but practically painful to use — a real gap
between "available" and "usable":

- The órdenes de compra **list** endpoint returns only `Codigo`, `Nombre`, `CodigoEstado` —
  no buyer, no comuna, no items, no prices. Any price needs a **detail call per order**.
- A single national day is ~16,600 orders, and the listing doesn't say who bought, so naive
  national ingestion means fetching every detail just to learn the buyer. Strict **rate
  limits** (observed HTTP 429) make that hostile.
- The **bulk open-data** dumps are **tenders-only** and stale, excluding Compra Ágil,
  Convenio Marco, and direct purchase orders — exactly where most day-to-day buying lives.

Net: getting clean, queryable, item-level procurement data with buyers and prices is real
engineering work. That work is the product. Felipe's observation: companies already monetize
this (their own API / dashboards over the real info) — treat that as a hypothesis to confirm,
including who the existing players are and how they differentiate.

## Product concept (options, not yet chosen)

- **A. Clean API.** Ingest, normalize, enrich, and serve procurement data via a fast
  REST/GraphQL API with the fields the official API buries (buyer, comuna, region, item-level
  product/quantity/unit price, category, method), no rate-limit pain for consumers.
- **B. Dashboard / analytics.** A hosted product for specific audiences to explore and
  benchmark procurement (search, alerts, price benchmarks, supplier/buyer profiles).
- **C. Both.** API as the backend, dashboard as its first consumer.

## Why this could reuse OSINT-Mercado

OSINT-Mercado already builds the hard part: ingestion, schema normalization, provenance
linking, and (soon) retail price baselines and anomaly scoring. A commercial data product
could share that ingestion/normalization core while staying a separate codebase and business.

## Candidate customers to validate (hypotheses, not facts)

Suppliers bidding to the State; investigative journalists (e.g. CIPER-type work); NGOs and
oversight bodies; academics/researchers; municipalities benchmarking their own spend. None
confirmed — each needs a real conversation before it counts.

## Open questions before this is more than an idea

- **Licensing / terms of reuse and resale of public procurement data.** This is a legal
  question — consult a qualified lawyer. Not addressed here.
- Which purchase methods (Ágil, Convenio Marco, direct OCs) are actually obtainable and at
  what freshness, given the API's constraints.
- Infra cost and rate-limit strategy for full national, continuous ingestion at scale.
- Who the existing players are and what would differentiate this.
- Pricing/business model, and whether A, B, or C is the wedge.

## Relationship to OSINT-Mercado

Keep them separate: OSINT-Mercado is the non-commercial municipal-overpricing watchdog
(`PRD.md`, `docs/adr/`). This product is commercial and broader. Shared ingestion core,
separate repos, separate PRDs.
