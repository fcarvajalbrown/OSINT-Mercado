# 0031 — Publish every lead; the overprice estimate waits for human review

**Status:** Accepted (supersedes the "only confirmed flags appear" part of ADR 0006; builds on
ADR 0026 and 0030)
**Date:** 2026-10-09
**Deciders:** Felipe Carvajal Brown

## Context

Under ADR 0006 only confirmed flags reach the public site, which on 2026-10-09 meant 2 rows while
3,876 leads waited in review (3,229 undecided anomalies, 346 Convenio Marco leads, 301 peer-price
leads). ADR 0030 gave that count as 3,895; that figure included 19 anomalies the ledger had
already decided, and 3,876 is the undecided number. The purchase-order data behind every lead is
public on Mercado Público. What ADR 0006 protects against is an unreviewed overprice claim against
a named municipality, not the order data itself.

## Decision

- Every lead from the three engines is published with its order data: comuna, buying unit,
  product, quantity, price paid (stating whether it is gross or net of IVA), order number and
  official link, and capture time.
- For a lead that Felipe has not reviewed, the overprice estimate, the severity and the reference
  price are not published at all; the row shows "En revisión" in their place. The reference price
  is withheld too, because the price paid next to the reference is the ratio.
- When Felipe confirms a lead, its estimate, severity, reference and his review note appear.
  Dismissed leads keep their order data and show the dismissal reason.
- Every published row, reviewed or not, is part of the Stellar seal (ADR 0026), so a later edit to
  any row is visible. The review-queue seal of ADR 0030 continues.
- Leads whose comuna field is blank, numeric or otherwise unusable are published as "Comuna sin
  identificar" until the data is fixed, never dropped.

## Consequences

- The public sees all leads, but no overprice claim against a municipality appears before human
  review; the review step remains the only thing that turns a lead into a claim.
- The published dataset grows from 2 rows to about 3,900; the dashboard needs filtering and
  paging, and the browser hashes every row on verification.
- The data-quality gaps found on 2026-10-09 become visible (about 71 leads with no comuna, about
  102 with codes or symbols in the comuna field, and name variants such as "Calera De Tango" and
  "Til Til"), which is a reason to fix them at the source.

## Alternatives considered

- **Keep ADR 0006 as is and show only counts (ADR 0030 alone).** Rejected by Felipe: two rows are
  not a presentable public record.
- **Publish leads with the reference price but without ratio and severity.** Rejected: the ratio
  can be read off the page before review.
- **Publish everything including unreviewed estimates, labelled.** Rejected: an unreviewed
  estimate is still an accusation against a named municipality.
