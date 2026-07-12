# OSINT-Mercado — Product Requirements Document (PRD)

> Status: Stable vision doc. Rarely edited. Architecture and scope decisions live in
> `docs/adr/`; phased execution lives in `ROADMAP.md`.
>
> This markdown PRD supersedes the original `docs/OSINT_Mercado_PRD.pdf`, which
> described a local-first desktop daemon. That premise was invalidated by the actual
> deployment target (a webapp on Hostinger **Business shared** hosting). The PDF is
> retained only as a historical artifact. See `docs/adr/` for the superseding decisions.

## 1. Executive summary

OSINT-Mercado is a public-interest **web application** that systematically audits and
exposes structural overpricing in Chilean municipal procurement. It ingests public
purchase orders (órdenes de compra) from the Mercado Público / ChileCompra API,
cross-references them against a curated retail price baseline for a controlled basket of
commoditized goods, and flags purchases that deviate from the retail reference beyond a
configurable threshold.

Every published flag links back to its official source order so any claim can be
independently verified. It requires no community input or volunteer sourcing; it operates
as a standalone watchdog.

## 2. Problem statement & scope

**The gap.** State procurement data is transparent and available via API, but dense and
unparsed. Extreme administrative waste or minor corruption at the municipal level — e.g.
buying standard electronics or office supplies at a large markup over retail — goes
largely unnoticed without dedicated auditing.

**Primary objective.** Automate anomaly detection for localized municipal acquisitions of
standard, commoditized goods, and present the findings on a public, verifiable dashboard.

**In scope (v1).** Municipal buyers nationally, restricted to a **tight controlled basket**
(~15–25 hand-picked commoditized SKUs with clean retail baselines).

**Out of scope.** Complex service contracts, public works (Obras Públicas), and specialized
consulting where pricing lacks a standardized retail baseline. Real-time telemetry (a
procurement watchdog is a batch problem; freshness of a day or a few days is ample).

## 3. Users

- **The auditor (primary).** Runs the pipeline, reviews flagged anomalies a few times a
  week, confirms or dismisses them before they publish.
- **The public (secondary).** Reads the published dashboard, filters flags, and follows the
  source link to verify each one against the official record.

## 4. Core functional requirements

- **State data ingestion.** Scheduled fetching from the Mercado Público OC API, filtered to
  municipal buyer codes. Ticket-authenticated (a free ChileCompra API key).
- **Retail baseline engine.** For each basket SKU, gather current retail prices from a
  hybrid of sources — price aggregators where coverage exists, targeted per-product scrapes
  otherwise, and a curated manual-seed price as guaranteed fallback. Reference price = the
  median across available sources, anchored by the seed.
- **Controlled-basket matcher.** Decide whether a municipal order line-item refers to one of
  the known basket SKUs, using per-SKU keyword/model rules plus a fuzzy fallback. This is a
  curated classifier over a small basket, not general-purpose fuzzy matching across all
  products.
- **Anomaly detection.** Overprice ratio = unit price paid ÷ baseline reference. Flags are
  assigned a severity tier (configurable; default Watch ≥1.5×, High ≥2×, Severe ≥3×), with
  guardrails: per-unit normalization and a minimum baseline confidence before a line-item is
  scored at all.
- **Human curation gate.** Statistically flagged anomalies land in a `pending` state. The
  auditor confirms or dismisses each (with an optional note) before it is published. Only
  confirmed flags appear on the public dashboard.
- **Provenance.** Every flag stores and displays its official source order id, a link back to
  Mercado Público, and a capture timestamp — so no accusation is unverifiable.
- **Dashboard.** A static web dashboard filtering confirmed flags by commune, product
  category, and severity, each row showing unit-paid vs baseline, overprice %, and the
  source link.

## 5. Architecture (summary)

A **split** system across three planes. Full rationale in `docs/adr/`.

- **Pipeline plane (external compute).** Python + Polars runs on GitHub Actions on a
  schedule: ingest → baseline refresh → match → score → emit pending anomalies. Python is
  **not runnable on Hostinger shared hosting** (no root), so external compute is a hard
  requirement, not a preference (ADR 0001, ADR 0002).
- **Store plane (versioned files).** The dataset lives as versioned data files
  (Parquet / JSON) committed to the repo. Git history gives a free provenance and audit
  trail. DuckDB is used at build time to shape/aggregate the published data, not as a runtime
  dependency (ADR 0004).
- **Presentation plane (Hostinger static).** A static HTML/CSS/JS dashboard with client-side
  filtering. Built in GitHub Actions and auto-deployed to Hostinger via its native Git
  integration (ADR 0003). Plan: Hostinger **Business shared** hosting.

```
[Mercado Público API] ┐
                      ├─► (GitHub Actions: ingest → baseline → match → score)
[Retail baselines]    ┘            │
                                   ▼
                       pending anomalies ──► (human curation gate)
                                   │                  │ confirm/dismiss
                                   ▼                  ▼
                       versioned data files ──► published JSON + static site
                                                        │  (native Git deploy)
                                                        ▼
                                                 Hostinger (public_html)
```

## 6. Success criteria (v1)

- The pipeline ingests municipal OCs nationally and matches them against the controlled
  basket with a documented, testable accuracy on a labeled sample.
- Flagged anomalies are reproducible: re-running the pipeline on the same inputs yields the
  same flags.
- Every published flag is independently verifiable via its source link.
- The dashboard loads and filters the confirmed dataset entirely client-side on Hostinger.

## 7. Non-goals / guardrails

- No unverified public accusations: the curation gate and provenance link are mandatory.
- No reliance on Hostinger's build environment: the frontend is pre-built and deployed as
  static output (works on Premium or Business).
- No premature optimization: no Rust/PyO3 until a measured need appears (ADR 0002).

## 8. Long-term direction

The standing goal beyond v1 is national coverage across **broad product categories** (the
original PDF's grand vision), reached by progressively widening the basket. Later phases also
include robust statistics (MAD/IQR) for the anomaly core, cryptographic hashing of source
data for tamper-evident provenance, and historical price-trend views. These are tracked in
`ROADMAP.md`.
