# 0014 — Curation workflow: git-native decisions ledger + osint-curate CLI

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

ADR 0006 established the human curation gate — statistically flagged anomalies land in
`pending`, and a human confirms or dismisses each (with a note) before publishing — but left
the exact review mechanism as a Phase 4 decision. The system has no server (static hosting,
ADR 0001/0003) and treats git history as the audit trail (ADR 0004). The auditor reviews a
few times per week. Whatever the mechanism, it must be reproducible: the same pending set and
the same decisions must always yield the same published dataset (a PRD success criterion).

## Decision

Curation is a versioned **decisions ledger** the auditor drives through a CLI, not an
interactive app or a database.

- `data/curation_decisions.json` — an object keyed by anomaly `id`:
  `{"<id>": {"decision": "confirm"|"dismiss", "note": "...", "reviewed_at": "YYYY-MM-DD"}}`.
  Each decision is a small, self-explaining git diff.
- `curation.py` is pure (no clock, no network): `apply_decisions(pending, decisions)` routes
  each **reviewable** anomaly to `confirmed`, `dismissed`, or `undecided`, deterministically
  ordered. Reviewable = `status ∈ {pending, unit_ambiguous}`; `needs_baseline` is a baseline
  gap, not an accusation, and is excluded from the queue. A confirmed `unit_ambiguous`
  publishes like a confirmed `pending` (the auditor resolved the unit question).
- `osint-curate` CLI: `status` (counts + undecided ids), `confirm <id> [--note]`,
  `dismiss <id> --reason`, and `promote` (writes `data/confirmed_flags.json` and
  `data/dismissed_flags.json`). The clock lives only in the CLI (injectable in tests).
- `data/confirmed_flags.json` is the sole published dataset and the Phase 5 dashboard's input;
  it contains only human-confirmed flags. `data/dismissed_flags.json` archives dismissals with
  their reason.

## Consequences

- Only human-reviewed claims are ever published — the credibility floor a watchdog needs.
- The full review history is in git: who decided what, when, and why (the note/reason), with
  no extra infrastructure.
- Re-running `promote` on the same ledger + pending is byte-identical, satisfying
  reproducibility and letting decisions accrete safely over time.
- Dismissals with reasons become QA signal for improving the matcher and baselines
  (ADR 0006's intent).
- The ledger is keyed by the stable anomaly id (ADR 0013), so a decision survives re-scoring
  as long as the underlying (oc_id, correlativo, sku_id) persists.

## Alternatives considered

- **Interactive review CLI/TUI that prompts per flag.** Rejected: harder to test, no diffable
  audit trail, and re-run state is implicit.
- **A small database (SQLite) of decisions.** Rejected: a runtime dependency and a binary
  store that breaks the versioned-file audit trail (ADR 0004).
- **Generated HTML review page writing back decisions.** Rejected for v1: needs a write path
  the static host does not provide; the CLI + ledger is simpler and fully git-native.
