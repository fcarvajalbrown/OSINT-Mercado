"""osint-curate: the auditor's confirm/dismiss CLI over pending anomalies.

Records decisions into the versioned ledger (data/curation_decisions.json) and
promotes them into the published data/confirmed_flags.json and archived
data/dismissed_flags.json. Every decision is a small git diff (the audit trail).
"""

import argparse
import json
from datetime import date
from pathlib import Path

from osint_mercado import curation


def _write(path, rows) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def record(anomaly_id, decision, note, decisions_path, today: date) -> None:
    decisions = curation.load_decisions(decisions_path)
    decisions = curation.set_decision(decisions, anomaly_id, decision, note, today.isoformat())
    curation.save_decisions(decisions, decisions_path)


def promote(pending_path, decisions_path, confirmed_path, dismissed_path) -> curation.CurationResult:
    pending = curation.load_pending(pending_path)
    decisions = curation.load_decisions(decisions_path)
    result = curation.apply_decisions(pending, decisions)
    _write(confirmed_path, result.confirmed)
    _write(dismissed_path, result.dismissed)
    return result


def status(pending_path, decisions_path) -> dict:
    pending = curation.load_pending(pending_path)
    decisions = curation.load_decisions(decisions_path)
    result = curation.apply_decisions(pending, decisions)
    return {
        "confirmed": len(result.confirmed),
        "dismissed": len(result.dismissed),
        "undecided": len(result.undecided),
        "undecided_ids": [u["id"] for u in result.undecided],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Curate pending anomalies (confirm/dismiss/promote)")
    ap.add_argument("--pending", default="data/pending_anomalies.json")
    ap.add_argument("--decisions", default="data/curation_decisions.json")
    ap.add_argument("--confirmed", default="data/confirmed_flags.json")
    ap.add_argument("--dismissed", default="data/dismissed_flags.json")
    sub = ap.add_subparsers(dest="command", required=True)

    p_confirm = sub.add_parser("confirm", help="confirm a flag by anomaly id")
    p_confirm.add_argument("id")
    p_confirm.add_argument("--note", default="")

    p_dismiss = sub.add_parser("dismiss", help="dismiss a flag by anomaly id")
    p_dismiss.add_argument("id")
    p_dismiss.add_argument("--reason", required=True)

    sub.add_parser("promote", help="write confirmed_flags.json and dismissed_flags.json")
    sub.add_parser("status", help="print counts and undecided ids")

    args = ap.parse_args()

    if args.command == "confirm":
        record(args.id, "confirm", args.note, args.decisions, date.today())
        print(f"confirmed {args.id}")
    elif args.command == "dismiss":
        record(args.id, "dismiss", args.reason, args.decisions, date.today())
        print(f"dismissed {args.id}")
    elif args.command == "promote":
        result = promote(args.pending, args.decisions, args.confirmed, args.dismissed)
        print(f"confirmed={len(result.confirmed)} dismissed={len(result.dismissed)} "
              f"undecided={len(result.undecided)}")
    elif args.command == "status":
        print(json.dumps(status(args.pending, args.decisions), ensure_ascii=False))


if __name__ == "__main__":
    main()
