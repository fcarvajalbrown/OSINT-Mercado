"""Human curation gate (ADR 0006), git-native.

The auditor's confirm/dismiss decisions live in a versioned ledger
(data/curation_decisions.json) keyed by anomaly id. Applying the ledger to the
pending anomalies is a pure, deterministic function: confirmed flags become the
published dataset, dismissed flags are archived with a reason, and anything with
no decision stays undecided. Only reviewable statuses (pending, unit_ambiguous)
are subject to curation; needs_baseline is a baseline gap, not an accusation.
"""

import json
from dataclasses import dataclass
from pathlib import Path

REVIEWABLE = {"pending", "unit_ambiguous"}


@dataclass(frozen=True)
class Decision:
    decision: str
    note: str
    reviewed_at: str


@dataclass(frozen=True)
class CurationResult:
    confirmed: list[dict]
    dismissed: list[dict]
    undecided: list[dict]


def load_pending(path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_decisions(path) -> dict[str, Decision]:
    p = Path(path)
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {
        k: Decision(v["decision"], v.get("note", ""), v["reviewed_at"])
        for k, v in raw.items()
    }


def save_decisions(decisions: dict[str, Decision], path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    obj = {
        k: {"decision": d.decision, "note": d.note, "reviewed_at": d.reviewed_at}
        for k, d in sorted(decisions.items())
    }
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def set_decision(decisions: dict[str, Decision], anomaly_id: str, decision: str,
                 note: str, reviewed_at: str) -> dict[str, Decision]:
    """Return a new ledger with `anomaly_id` set; does not mutate the input."""
    updated = dict(decisions)
    updated[anomaly_id] = Decision(decision, note, reviewed_at)
    return updated


def _sort_key(item: dict):
    return (item.get("comuna", ""), item.get("sku_id", ""),
            item.get("oc_id", ""), item.get("correlativo", 0))


def apply_decisions(pending: list[dict], decisions: dict[str, Decision]) -> CurationResult:
    confirmed, dismissed, undecided = [], [], []
    for item in pending:
        if item.get("status") not in REVIEWABLE:
            continue
        decision = decisions.get(item["id"])
        if decision is None:
            undecided.append(item)
        elif decision.decision == "confirm":
            confirmed.append({**item, "status": "confirmed",
                              "curation_note": decision.note,
                              "reviewed_at": decision.reviewed_at})
        elif decision.decision == "dismiss":
            dismissed.append({**item, "status": "dismissed",
                              "dismiss_reason": decision.note,
                              "reviewed_at": decision.reviewed_at})
        else:
            undecided.append(item)

    confirmed.sort(key=_sort_key)
    dismissed.sort(key=_sort_key)
    undecided.sort(key=_sort_key)
    return CurationResult(confirmed, dismissed, undecided)
