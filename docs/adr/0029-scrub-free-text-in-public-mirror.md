# 0029 — Scrub personal data from free text in the public mirror (refines ADR 0028)

**Status:** Accepted (refines ADR 0028)
**Date:** 2026-10-09
**Deciders:** Felipe Carvajal Brown (under his standing instruction to proceed with the
recommended approach while away; open to revision)

## Context

ADR 0028 publishes a copy of each official order record with the named contact fields of
`Comprador` and `Proveedor` set to `null`. A scan of the first four public copies before deploy
found two officials' full names, their work email addresses, a phone number and an invoicing
mailbox inside the free-text `Descripcion` of order 1736-668-SE26. Blanking the structured contact
fields is not enough: free text can carry the same data, and names in free text cannot be
removed reliably by pattern.

## Decision

- The public copy sets `Descripcion` (the order's free-text description) to `null`.
- Every other text field in the public copy has email addresses replaced by `[correo omitido]`
  and phone numbers by `[fono omitido]`.
- The public copy lists what was removed (`redacted_fields`, `masked`).
- The raw record stays untouched in the private repository, and its hash (`raw_sha256`) is still
  part of the public copy, so the anchor commits to the full original.
- `osint-mirror --rebuild-public` regenerates the public copies from the raw records, keeping
  each capture time, whenever these rules change.
- Every deploy of mirrors is preceded by a scan of the public copies for email addresses.

## Consequences

- No named individual's contact data is republished from the free text.
- The public copy loses the order description, which can hold relevant terms (delivery
  milestones, delivery place, invoicing rules). Those terms remain in the private raw copy and
  can be cited by hand in a curation note.
- The phone pattern targets Chilean 8- and 9-digit numbers with optional +56 and area code; it
  skips digit runs joined by "/" so document numbers such as "600/00155/2026" stay intact.

## Alternatives considered

- **Mask emails and phones in `Descripcion` but keep the text.** Rejected: officials' names would
  remain, and names cannot be stripped reliably by pattern.
- **Publish no mirror until a manual review of each record.** Rejected for now: it would leave
  the provenance links broken (ADR 0028) with no public alternative.
