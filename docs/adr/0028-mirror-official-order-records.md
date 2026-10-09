# 0028 — Mirror the official record of every published order

**Status:** Accepted (refines ADR 0007; builds on ADR 0026 and 0027)
**Date:** 2026-10-09
**Deciders:** Felipe Carvajal Brown

## Context

ADR 0007 makes every published flag carry a link to its official purchase order on
mercadopublico.cl so any reader can verify it independently. On 2026-10-09 every one of the
four published orders' links opened Mercado Público's dialog "No Tiene los Permiso suficientes
para visualizar la ficha" for a reader who is not logged in (checked with an anonymous request
against all four). The public link no longer lets a reader verify anything, and the project
cannot assume an order page will stay reachable.

The public API (`ordenesdecompra.json?codigo=...`, with the project's ticket) still returns the
full order record, and its body does not contain the ticket. The record includes, for both the
buying unit and the supplier, a named contact person with position, phone and email
(`NombreContacto`, `CargoContacto`, `FonoContacto`, `MailContacto`).

Felipe asked for the official documents to be mirrored so they survive removal or a login wall,
and approved the recommended approach below.

## Decision

- **Mirror on capture.** A new `osint-mirror` CLI fetches the API record of every order behind a
  confirmed flag and stores it, unchanged, in `data/mirror/raw/<oc_id>.json` in the repository
  (private). A mirror is a snapshot: an existing file is never overwritten, so the first capture
  is what stays.
- **Public copy without personal contact data.** `data/mirror/public/<oc_id>.json` holds the same
  record with the four contact fields of `Comprador` and `Proveedor` set to `null`, plus
  `fetched_at`, the API endpoint (without the ticket) and `raw_sha256`, the canonical hash of the
  untouched record. Organisation names, RUTs, addresses, items, prices and dates are kept.
- **Anchored.** Each published flag carries `mirror_sha256`, the canonical hash of its public
  copy, so the Stellar digest (ADR 0026) commits to the flag, its source line (ADR 0027) and the
  mirrored record, and through `raw_sha256` to the full original.
- **Served and verified.** `osint-build-site` publishes the public copies under
  `data/mirror/`, the dashboard links each row to its copy next to the official link, and the
  browser verifier checks the copy's hash like the other two.

## Consequences

- A reader can see what the official record said when it was captured even when the official
  page is behind a login or gone, and can check that copy against the Stellar anchor.
- The mirror is only as old as its capture: orders flagged in the past are mirrored now, so their
  copy shows today's state of the record, not the state at ingest time. The capture time is shown.
- The full records, contact data included, stay in the private repository. Whether the contact
  fields may be published is not decided here; it is kept out by default and can be revisited in
  a new ADR.
- Mirroring adds one API call per published order, run by hand or alongside publishing.

## Alternatives considered

- **Scrape the order page or PDF with a logged-in session.** Rejected: it needs an account
  session the project should not automate, and the API already returns the structured record.
- **Publish the full record including contact data.** Rejected as the default: it republishes
  named individuals' phone numbers and emails, which the audit does not need.
- **Link to a third-party archive (e.g. the Wayback Machine).** Rejected: the archived page would
  show the same permission dialog, and the project would not control the copy.
