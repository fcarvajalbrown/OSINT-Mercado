# Phase 4 — Curation workflow (design spec)

**Date:** 2026-07-12
**Status:** Approved (design ratification deferred to end-of-run question batch), ready for implementation
**Shaped by:** ADR 0006 (human curation gate), 0007 (provenance), 0004 (versioned files); new ADR 0014

## Goal

Implement the human curation gate (ADR 0006). Turn `data/pending_anomalies.json` into a
reviewed, published dataset: an auditor confirms or dismisses each reviewable flag (with a
note/reason); confirmed flags promote into a published `data/confirmed_flags.json` (the Phase 5
dashboard's input); dismissed flags archive into `data/dismissed_flags.json` with the reason.
Re-runs are stable: the same pending + decisions always produce identical outputs.

## Mechanism: git-native decisions ledger

There is no server (static hosting, ADR 0001/0003) and git history is the audit trail
(ADR 0004). So curation is a versioned **decisions ledger** the auditor edits via a CLI, not
an interactive app or database.

- `data/curation_decisions.json` — object keyed by anomaly `id`:
  `{ "<id>": {"decision": "confirm"|"dismiss", "note": "...", "reviewed_at": "YYYY-MM-DD"} }`.
  Each decision is a small, reviewable git diff.

## Reviewable set

Reviewable = emitted anomalies with `status ∈ {pending, unit_ambiguous}`. `needs_baseline`
items are baseline gaps, not accusations, and are excluded from the review queue. A confirmed
`unit_ambiguous` means the auditor verified a real overprice after resolving the unit
question; it publishes like a confirmed `pending`.

## Modules and contracts

### `curation.py` (pure, no clock, no network)
- `Decision` dataclass: `decision: str`, `note: str`, `reviewed_at: str`.
- `load_pending(path) -> list[dict]`, `load_decisions(path) -> dict[str, Decision]`,
  `save_decisions(decisions, path)`.
- `REVIEWABLE = {"pending", "unit_ambiguous"}`.
- `apply_decisions(pending, decisions) -> CurationResult` with fields `confirmed`,
  `dismissed`, `undecided` (all `list[dict]`), where:
  - confirmed = reviewable items whose decision is `confirm`, each enriched with
    `curation_note`, `reviewed_at`, and `status="confirmed"`.
  - dismissed = reviewable items whose decision is `dismiss`, enriched with
    `dismiss_reason`, `reviewed_at`, `status="dismissed"`.
  - undecided = reviewable items with no ledger entry.
  - deterministic ordering by `(comuna, sku_id, oc_id, correlativo)`.
- `set_decision(decisions, anomaly_id, decision, note, reviewed_at) -> dict` (pure ledger
  update, returns a new dict).

### `curate.py` CLI (`osint-curate`)
Subcommands (the clock lives here, injected as `today` for tests):
- `status` — counts of reviewable / confirmed / dismissed / undecided; lists undecided ids.
- `confirm <id> [--note ...]` — write a `confirm` decision (reviewed_at = today).
- `dismiss <id> --reason ...` — write a `dismiss` decision (reason stored as note).
- `promote` — read pending + ledger; write `confirmed_flags.json` and `dismissed_flags.json`
  deterministically.

## Data files
- `data/curation_decisions.json` — the ledger (auditor-edited via CLI).
- `data/confirmed_flags.json` — published dataset (Phase 5 input); only confirmed flags.
- `data/dismissed_flags.json` — archive with reasons.

## Testing (TDD)
- `apply_decisions`: confirm routes to confirmed with note/reviewed_at/status; dismiss routes
  to dismissed with reason; no-decision stays undecided; `needs_baseline` never appears;
  stable ordering.
- `set_decision`: pure update, overwrite existing, does not mutate input.
- determinism: two `promote` runs on the same inputs are byte-identical.
- CLI: `confirm` then `promote` yields the flag in `confirmed_flags.json`; `dismiss` archives
  it; `status` counts are correct.

## Out of scope
Dashboard/deploy (Phase 5). No auto-publish above a confidence threshold (ADR 0006 keeps a
human in the loop for every published flag).
