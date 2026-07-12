# OSINT-Mercado — Design Spec (v1)

**Date:** 2026-07-12
**Author:** Felipe Carvajal Brown
**Status:** Approved design; ready for implementation planning.

This is the design record produced during brainstorming. It supersedes the local-daemon
design in `docs/OSINT_Mercado_PRD.pdf`. Durable decisions are captured in `docs/adr/`; scope
and phasing in `PRD.md` and `ROADMAP.md`.

## 1. What we're building

A public-interest **webapp** that audits Chilean **municipal** procurement for overpricing.
The pipeline ingests public purchase orders from the Mercado Público / ChileCompra API,
compares each against a curated retail baseline for a **tight controlled basket** of
commoditized goods, flags deviations beyond a configurable threshold, routes flags through a
human curation gate, and publishes confirmed flags on a static dashboard where each one links
back to its official source order.

**Goal:** a genuinely shippable watchdog tool that also stands as a defensible engineering
showcase.

## 2. Locked decisions (from brainstorming)

| Decision | Choice | ADR |
|---|---|---|
| Deployment target | Hostinger **Business shared** hosting (domain + plan bought) | 0001, 0003 |
| Where heavy compute runs | **External** — GitHub Actions (Python not runnable on shared host) | 0001, 0002 |
| Pipeline language | Python + Polars; **no Rust/PyO3** in v1 | 0002 |
| Store | Versioned data files (Parquet/JSON) in repo; DuckDB build-time only | 0004 |
| v1 coverage | **National** municipal buyers, **tight controlled basket** (~15–25 SKUs) | — |
| Long-term goal | National + broad product categories (widen the basket over phases) | — |
| Baseline source | Hybrid: aggregator + targeted scrape + **curated manual seed** fallback | 0002, 0004 |
| Matching | **Controlled-basket classifier** (per-SKU rules + fuzzy fallback), not general fuzzy | 0005 |
| Publish gate | **Human curation** — pending → confirmed/dismissed; review 1–3×/week | 0006 |
| Trust | **Provenance link** on every flag (source id + url + captured_at) | 0007 |
| Frontend | Static HTML/CSS/JS, client-side filtering | 0003 |
| Deploy | Build in CI → commit static output → Hostinger **native Git integration** to `public_html` | 0003 |

## 3. Verified platform facts (checked, not assumed)

- **Python is not supported on Hostinger shared hosting** (needs root). → external pipeline is
  a requirement, not a preference.
- **Cron jobs and (limited, non-root) SSH** are available on shared plans.
- **Native Git integration** deploys a GitHub branch to `public_html` and auto-redeploys on
  push; works for static HTML/JS on Premium and Business.
- The **"Deploy Web App" (Node.js)** tile is Business/Cloud only. The account is Business, so
  it exists — but we deliberately do not depend on it (deploy stays pre-built static).

Sources consulted: Hostinger support docs on Node.js hosting options and Git-repository
deployment; third-party confirmations on Python-on-shared and Node-on-shared availability.

## 4. Architecture — three planes

### Pipeline plane (GitHub Actions, Python)
Scheduled (daily). Stages:
1. **Ingest** — Mercado Público OC API, ticket-authenticated, filtered to municipal buyer
   codes over a date window. Persist raw responses. (Phase 1 confirms exact endpoint/params
   and rate limits from official API docs.)
2. **Baseline refresh** — per basket SKU, gather prices from aggregator(s) + targeted
   scrapes, fall back to the manual seed. Reference = median across available sources,
   anchored by the seed. Record a per-SKU baseline-confidence.
3. **Match** — controlled-basket classifier maps line-items to SKUs (per-SKU keyword/model
   rules + fuzzy fallback). Attach unit price paid.
4. **Score** — per-unit normalization; overprice ratio = unit_paid ÷ reference; severity tier;
   emit `pending` anomalies only when baseline confidence is sufficient (else "needs
   baseline").

### Curation plane (human-in-the-loop)
The auditor reviews pending flags 1–3×/week, confirming or dismissing each with an optional
note. Confirmed → published dataset; dismissed → archived with reason.

### Presentation plane (Hostinger static)
A static dashboard filters confirmed flags by commune / category / severity. Each row shows
unit-paid vs baseline, overprice %, severity, and the **official source link**. Built in CI,
deployed via native Git integration.

### Data flow
```
[Mercado Público API] ┐
                      ├─► GitHub Actions: ingest → baseline → match → score
[Retail baselines]    ┘             │
                                    ▼
                          pending anomalies ──► human curation (confirm/dismiss)
                                    │                    │
                                    ▼                    ▼
                        versioned data files ──► published JSON + static site build
                                                          │  native Git deploy on push
                                                          ▼
                                                   Hostinger public_html
```

## 5. Data model (core entities)

- **basket_sku** — id, name, category, canonical keywords / model identifiers, unit,
  manual_seed_price.
- **baseline_price** — sku_id, source, price, captured_at.
- **purchase_order_item** — oc_id, buyer_code, commune, date, raw_description, matched_sku_id,
  unit_price, qty, oc_url.
- **anomaly** — id, oc_item_id, sku_id, unit_paid, baseline_ref, overprice_ratio, severity,
  status (`pending` / `confirmed` / `dismissed`), reviewer_note, provenance (oc_id, oc_url,
  captured_at), published_at.

## 6. Anomaly method (v1)

- Reference price per SKU = median of available baseline sources, anchored by the seed.
- Overprice ratio = unit_paid ÷ reference.
- Severity tiers (configurable): **Watch ≥1.5×**, **High ≥2×**, **Severe ≥3×**.
- Guardrails: normalize to per-unit (not per-pack); require minimum baseline confidence before
  scoring; otherwise mark "needs baseline" rather than flag.
- Robust statistics (MAD / IQR) is a later enhancement, not v1.

## 7. Risks & mitigations

- **Retail scraping fragility / anti-bot.** → hybrid sources with a curated manual-seed
  fallback so a broken scrape never leaves a SKU without a baseline (ADR 0004). Human review
  catches stale baselines (ADR 0006).
- **False-positive matches → unfair public accusations.** → controlled-basket classifier for
  precision (ADR 0005) + mandatory human curation gate (ADR 0006) + provenance link so every
  claim is checkable (ADR 0007).
- **Mercado Público API specifics/limits unknown.** → Phase 1 explicitly confirms endpoint,
  params, and rate limits from official docs before building on them; a free ticket is
  required.
- **CI ↔ host coupling.** → pre-built static output + native Git deploy keeps the boundary
  simple and reproducible (ADR 0003).
- **Legal/ToS gray areas of scraping.** Flagged as a real consideration; not legal advice.
  Mitigated by preferring aggregator sources and low-volume targeted fetches, and by relying
  on official APIs for the procurement side.

## 8. Success criteria (v1)

- Pipeline ingests municipal OCs nationally and matches against the basket with documented,
  testable accuracy on a labeled sample.
- Reproducible flags: same inputs → same flags.
- Every published flag verifiable via its source link.
- Dashboard loads and filters the confirmed dataset entirely client-side on Hostinger.

## 9. Out of scope for v1

Complex service contracts, public works, specialized consulting; real-time telemetry; broad
product categories (long-term goal); Rust/PyO3; cryptographic provenance hashing; historical
trend views; server-side search.

## 10. Superpowers workflow for build-out

Design (this spec) → `superpowers:writing-plans` → `using-git-worktrees` →
`test-driven-development` (matcher + scorer) → `subagent-driven-development` /
`executing-plans` → `systematic-debugging` → `verification-before-completion` →
`requesting-code-review` → `finishing-a-development-branch`. `dispatching-parallel-agents`
for independent scrapers; `security-review` for scraper + API-key handling; `context7` for
live library docs.
