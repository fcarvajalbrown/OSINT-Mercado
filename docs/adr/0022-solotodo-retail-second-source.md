# 0022 - SoloTodo as the independent retail second source (goods)

Status: Accepted
Date: 2026-07-14
Deciders: Felipe Carvajal Brown

## Context

The auto-catalog (ADR 0019) covers ~2,654 products but baselines them only by the
commune-vs-commune peer median - single-source and self-referential, so peer flags are
investigative leads, not publish-grade (ADR 0018/0020). Only the ~82 hand-curated SKUs have an
independent retail anchor. The deciders asked for a real external second source, found via web
research, kept commune-vs-commune wherever possible but with a genuine independent goods anchor -
explicitly *not* an aggregator that fabricates prices, and with rigorous math so results are sane.

A discovery pass verified **SoloTodo (`api.solotodo.com`)**: a public, no-auth JSON API with
per-store Chilean retail prices across 70 goods categories, scraping private retail (Falabella,
Paris, PC Factory, DGA, ...). It is independent of Mercado Publico and carries a provenance URL per
store. It has no services and is an undocumented private backend.

## Decision

Wire SoloTodo as an independent retail anchor for **goods**, via `solotodo.py`:

- `retail_quote(query, must_tokens)` searches SoloTodo, keeps only products whose name contains
  **all** distinctive `must_tokens`, and returns the robust price stats (median + min across every
  matching store offer) with a provenance URL - or `None` when nothing confidently matches.
- **Precision guard (the "not crazy" rule):** a quote is used only on a token match. A part-number
  or model match ("CF283A") is exact; a broad-category query ("Toner") never anchors, because a
  category median is meaningless. On a miss the item stays peer-only rather than getting a wrong
  anchor.
- Robust statistics (median/min across stores), never a mean, matching the rest of the pipeline.

A flag is only publish-grade when an independent source agrees; SoloTodo supplies that agreement for
the goods it covers, extending the cross-confirmation gate (ADR 0020) beyond the 82-SKU basket.

## Consequences

- Verified live: `toner CF283A` returns a real anchor of median $89,900 across 17 store offers
  (min $63,990), matching a hand-researched price - independent confirmation of the mechanism.
- **Partial coverage, honestly bounded.** SoloTodo reliably anchors *identifiable* goods (toner and
  cartridges by part number, electronics/appliances by model, some grocery brands). It does not
  cover services, and generic/broad-category catalog entries often get no confident token match. So
  it grows publishable goods coverage beyond 82 toward the hundreds - not a full-catalogue baseline.
- Politeness/stability: undocumented backend, no published rate limits - cache results, low request
  rate, and pin field access behind this module (as with `schema.py`).
- ChileCompra Convenio Marco reference-price CSV remains a candidate official secondary anchor
  (goods and some services) once its client-side download URL is captured; deferred.

## Alternatives considered

- **Baseline every catalog code from a SoloTodo *category* median.** Rejected as "crazy": a category
  average conflates different models and would manufacture false overprices - exactly what the
  precision guard prevents.
- **Mercado Libre API.** Rejected: requires OAuth app registration; anonymous calls 403.
- **Blend SoloTodo into the hand seed prices.** Rejected for the cross-check: kept as a *distinct*
  source so agreement between methods stays independent.
