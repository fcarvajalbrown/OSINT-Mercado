from osint_mercado import curation

PENDING = [
    {"id": "a1", "status": "pending", "comuna": "Nunoa", "sku_id": "mouse_usb",
     "oc_id": "1-1", "correlativo": 1},
    {"id": "a2", "status": "unit_ambiguous", "comuna": "Maipu", "sku_id": "alcohol_gel_1l",
     "oc_id": "2-1", "correlativo": 1},
    {"id": "a3", "status": "needs_baseline", "comuna": "Buin", "sku_id": "x",
     "oc_id": "3-1", "correlativo": 1},
]


def test_set_decision_is_pure_and_overwrites():
    d = {}
    d2 = curation.set_decision(d, "a1", "confirm", "looks real", "2026-07-12")
    assert d == {}
    assert d2["a1"].decision == "confirm"
    d3 = curation.set_decision(d2, "a1", "dismiss", "actually fine", "2026-07-13")
    assert d3["a1"].decision == "dismiss"
    assert d2["a1"].decision == "confirm"


def test_apply_confirm_routes_to_confirmed():
    decisions = {"a1": curation.Decision("confirm", "real overprice", "2026-07-12")}
    res = curation.apply_decisions(PENDING, decisions)
    assert len(res.confirmed) == 1
    c = res.confirmed[0]
    assert c["id"] == "a1"
    assert c["status"] == "confirmed"
    assert c["curation_note"] == "real overprice"
    assert c["reviewed_at"] == "2026-07-12"
    assert [u["id"] for u in res.undecided] == ["a2"]
    assert res.dismissed == []


def test_apply_dismiss_routes_to_dismissed():
    decisions = {"a2": curation.Decision("dismiss", "unit mismatch", "2026-07-12")}
    res = curation.apply_decisions(PENDING, decisions)
    assert [d["id"] for d in res.dismissed] == ["a2"]
    assert res.dismissed[0]["dismiss_reason"] == "unit mismatch"
    assert res.dismissed[0]["status"] == "dismissed"
    assert [u["id"] for u in res.undecided] == ["a1"]


def test_needs_baseline_is_never_reviewable():
    decisions = {"a3": curation.Decision("confirm", "x", "2026-07-12")}
    res = curation.apply_decisions(PENDING, decisions)
    assert res.confirmed == []
    assert [u["id"] for u in res.undecided] == ["a2", "a1"]  # sorted: Maipu, Nunoa


def test_apply_is_deterministically_ordered():
    decisions = {
        "a1": curation.Decision("confirm", "", "2026-07-12"),
        "a2": curation.Decision("confirm", "", "2026-07-12"),
    }
    res = curation.apply_decisions(PENDING, decisions)
    assert [c["comuna"] for c in res.confirmed] == ["Maipu", "Nunoa"]


def test_decisions_roundtrip(tmp_path):
    p = tmp_path / "curation_decisions.json"
    decisions = curation.set_decision({}, "a1", "confirm", "note", "2026-07-12")
    curation.save_decisions(decisions, p)
    loaded = curation.load_decisions(p)
    assert loaded["a1"] == curation.Decision("confirm", "note", "2026-07-12")


def test_load_missing_decisions_returns_empty(tmp_path):
    assert curation.load_decisions(tmp_path / "nope.json") == {}
