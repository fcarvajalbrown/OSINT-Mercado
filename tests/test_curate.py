import datetime as dt
import json

from osint_mercado import curate

TODAY = dt.date(2026, 7, 12)
PENDING = [
    {"id": "a1", "status": "pending", "comuna": "Nunoa", "sku_id": "mouse_usb",
     "oc_id": "1-1", "correlativo": 1, "overprice_ratio": 3.3},
    {"id": "a2", "status": "unit_ambiguous", "comuna": "Maipu", "sku_id": "alcohol_gel_1l",
     "oc_id": "2-1", "correlativo": 1, "overprice_ratio": 0.18},
]


def _setup(tmp_path):
    pending = tmp_path / "pending.json"
    pending.write_text(json.dumps(PENDING), encoding="utf-8")
    return (pending, tmp_path / "decisions.json",
            tmp_path / "confirmed.json", tmp_path / "dismissed.json")


def test_confirm_then_promote_publishes_flag(tmp_path):
    pending, decisions, confirmed, dismissed = _setup(tmp_path)
    curate.record("a1", "confirm", "real overprice", decisions, TODAY)
    curate.promote(pending, decisions, confirmed, dismissed)
    rows = json.loads(confirmed.read_text(encoding="utf-8"))
    assert [r["id"] for r in rows] == ["a1"]
    assert rows[0]["status"] == "confirmed"
    assert rows[0]["reviewed_at"] == "2026-07-12"
    assert json.loads(dismissed.read_text(encoding="utf-8")) == []


def test_dismiss_then_promote_archives_flag(tmp_path):
    pending, decisions, confirmed, dismissed = _setup(tmp_path)
    curate.record("a2", "dismiss", "sachet vs 1L, unit mismatch", decisions, TODAY)
    curate.promote(pending, decisions, confirmed, dismissed)
    arch = json.loads(dismissed.read_text(encoding="utf-8"))
    assert [r["id"] for r in arch] == ["a2"]
    assert arch[0]["dismiss_reason"] == "sachet vs 1L, unit mismatch"
    assert json.loads(confirmed.read_text(encoding="utf-8")) == []


def test_status_counts(tmp_path):
    pending, decisions, confirmed, dismissed = _setup(tmp_path)
    curate.record("a1", "confirm", "", decisions, TODAY)
    s = curate.status(pending, decisions)
    assert s["confirmed"] == 1
    assert s["undecided"] == 1
    assert s["undecided_ids"] == ["a2"]


def test_promote_is_deterministic(tmp_path):
    pending, decisions, confirmed, dismissed = _setup(tmp_path)
    curate.record("a1", "confirm", "x", decisions, TODAY)
    curate.promote(pending, decisions, confirmed, dismissed)
    first = confirmed.read_bytes()
    curate.promote(pending, decisions, confirmed, dismissed)
    assert confirmed.read_bytes() == first
