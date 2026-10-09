# Architecture Decision Records

MADR-lite records of significant decisions. Once **Accepted**, an ADR is immutable; a change
of course is a new ADR that sets its Status to "Supersedes 00XX" and edits the old record's
Status to "Superseded by 00YY".

These ADRs supersede the decisions in the original `docs/OSINT_Mercado_PRD.pdf`, which
assumed a local-first desktop daemon (Rust/PyO3, Dear PyGui, DuckDB runtime). That premise
did not survive the actual deployment target — a webapp on Hostinger Business shared hosting.

| #    | Title                                                                 | Status   |
|------|-----------------------------------------------------------------------|----------|
| 0001 | Split-compute architecture: external pipeline + static Hostinger site | Accepted |
| 0002 | Python + Polars pipeline; Rust/PyO3 deferred                          | Accepted |
| 0003 | Static web frontend + native Git deploy; Dear PyGui dropped            | Accepted (transport superseded by 0015) |
| 0004 | Versioned file dataset as store; DuckDB build-time only                | Accepted |
| 0005 | Controlled-basket classifier over general fuzzy matching              | Accepted |
| 0006 | Human curation gate before publishing flags                           | Accepted |
| 0007 | Provenance linking (verifiable flags) in v1                           | Accepted |
| 0008 | By-organism API acquisition, scoped to the Región Metropolitana        | Accepted |
| 0009 | Currency and tax fields captured raw; CLP normalization deferred       | Accepted |
| 0010 | Basket & retail baseline: seed-only v1, pluggable multi-source design  | Accepted |
| 0011 | Currency conversion to CLP and net-vs-gross (IVA) alignment            | Accepted |
| 0012 | Controlled-basket matcher: implementation                             | Accepted |
| 0013 | Anomaly scoring, severity tiers, unit guardrail, and pending output    | Accepted |
| 0014 | Curation workflow: git-native decisions ledger + osint-curate CLI     | Accepted |
| 0015 | Deploy transport: SSH + rsync (supersedes the transport of ADR 0003)  | Accepted |
| 0016 | Pull-based data publishing via Hostinger cron (refines ADR 0015)      | Accepted |
| 0017 | Unit normalization before overprice scoring (extends ADR 0013)        | Accepted |
| 0018 | Peer-price comparison engine (market as its own baseline)             | Accepted |
| 0019 | Auto-SKU catalog (data-derived, not hand-curated)                     | Accepted |
| 0020 | Cross-confirmation publish gate (two methods must agree)              | Accepted |
| 0021 | Match on the especificacion, not the UNSPSC category label            | Accepted |
| 0022 | SoloTodo as the independent retail second source (goods)              | Accepted |
| 0023 | Conservative publish-verification filter (autonomous publishing)      | Accepted |
| 0024 | Convenio Marco size-normalized comparison engine                      | Accepted |
| 0025 | SSH key auth for deploy (refines ADR 0015)                            | Accepted |
| 0026 | Anchor published flags on the Stellar ledger                         | Accepted |
| 0027 | Anchor the source order line behind each flag (extends ADR 0026)      | Accepted |
| 0028 | Mirror the official record of every published order                  | Proposed |
| 0029 | Scrub personal data from free text in the public mirror               | Proposed |
| 0030 | Seal the review queue alongside the published set                     | Accepted |
