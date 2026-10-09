import hashlib
import json
import math

import polars as pl
from stellar_sdk import Account, Keypair

from osint_mercado import anchor, integrity

FLAG = {"id": "a1", "comuna": "Ñuñoa", "oc_id": "1-1", "correlativo": 8,
        "unit_price_clp_gross": 9282.0, "overprice_ratio": 2.7559, "curation_note": None}

ITEM = {"oc_id": "1-1", "correlativo": 8, "unit_price": 7800.0, "quantity": 12.0,
        "estado": "Aceptada", "captured_at": "2026-07-13T18:33:03.168923+00:00",
        "descuentos": math.nan}


def test_canonical_sorts_keys_compacts_and_keeps_utf8():
    assert integrity.canonical(FLAG) == (
        '{"comuna":"Ñuñoa","correlativo":8,"curation_note":null,"id":"a1","oc_id":"1-1",'
        '"overprice_ratio":2.7559,"unit_price_clp_gross":9282}'
    )


def test_canonical_writes_integral_floats_as_integers_like_javascript():
    assert integrity.canonical({"x": 3368.0, "y": [1.0, 1.5]}) == '{"x":3368,"y":[1,1.5]}'


def test_canonical_writes_nan_as_null():
    assert integrity.canonical({"x": math.nan}) == '{"x":null}'


def test_leaf_is_sha256_of_canonical_utf8_bytes():
    expected = hashlib.sha256(integrity.canonical(FLAG).encode("utf-8")).hexdigest()
    assert integrity.leaf(FLAG) == expected


def test_digest_is_order_independent_sha256_of_sorted_raw_leaves():
    leaves = [integrity.leaf({"id": "b"}), integrity.leaf({"id": "a"})]
    raw = b"".join(bytes.fromhex(h) for h in sorted(leaves))
    assert integrity.digest(leaves) == hashlib.sha256(raw).hexdigest()
    assert integrity.digest(leaves) == integrity.digest(list(reversed(leaves)))


def test_attach_sources_hashes_the_matching_line_into_the_flag():
    items = pl.DataFrame([ITEM, {**ITEM, "correlativo": 9, "unit_price": 1.0}])
    flags, sources = integrity.attach_sources([FLAG], items)
    snapshot = sources["a1"]
    assert snapshot["unit_price"] == 7800.0
    assert snapshot["descuentos"] is None
    assert flags[0]["source_sha256"] == integrity.leaf(snapshot)
    assert "source_sha256" not in FLAG


def test_attach_sources_leaves_unmatched_flag_without_source():
    items = pl.DataFrame([{**ITEM, "oc_id": "other"}])
    flags, sources = integrity.attach_sources([FLAG], items)
    assert "source_sha256" not in flags[0]
    assert sources == {}


def test_record_lists_ids_leaves_and_digest():
    flags = [FLAG, {"id": "b2", "comuna": "Buin"}]
    rec = integrity.record(flags)
    assert rec["flag_ids"] == ["a1", "b2"]
    assert rec["leaves"] == [integrity.leaf(f) for f in flags]
    assert rec["digest"] == integrity.digest(rec["leaves"])
    assert rec["network"] == "testnet"


def test_anchor_submits_digest_and_writes_record(monkeypatch, tmp_path):
    sent = {}

    def fake_submit(secret, digest_hex):
        sent.update(secret=secret, digest=digest_hex)
        return {"hash": "tx123", "ledger": 42, "created_at": "2026-10-09T22:00:00Z"}

    monkeypatch.setattr(anchor, "submit_digest", fake_submit)
    out = tmp_path / "anchors.json"
    rec = anchor.anchor([FLAG], "SSECRET", out)
    assert sent == {"secret": "SSECRET", "digest": rec["digest"]}
    assert (rec["tx_hash"], rec["ledger"]) == ("tx123", 42)
    assert rec["anchored_at"] == "2026-10-09T22:00:00Z"
    assert json.loads(out.read_text(encoding="utf-8")) == rec


def test_build_transaction_carries_digest_in_memo_and_data():
    kp = Keypair.random()
    digest_hex = integrity.digest([integrity.leaf(FLAG)])
    tx = anchor.build_transaction(Account(kp.public_key, 1), kp, digest_hex)
    body = tx.transaction
    assert body.memo.memo_hash == bytes.fromhex(digest_hex)
    op = body.operations[0]
    assert op.data_name == anchor.DATA_NAME
    assert op.data_value == bytes.fromhex(digest_hex)
    assert tx.signatures


def test_queue_record_hashes_undecided_leads_and_counts_them():
    queues = {
        "anomalias": [{"id": "a", "comuna": "Buin", "severity": "high"},
                      {"id": "b", "comuna": "Buin", "severity": None}],
        "convenio_marco": [{"id": "c", "comuna": "Pirque", "severity": "severe"}],
    }
    rec = integrity.queue_record(queues, decided={"b"})
    assert rec["total"] == 2
    assert rec["lead_hashes"] == sorted([integrity.leaf(queues["anomalias"][0]),
                                         integrity.leaf(queues["convenio_marco"][0])])
    assert rec["digest"] == integrity.digest(rec["lead_hashes"])
    assert rec["counts"]["by_engine"] == {"anomalias": 1, "convenio_marco": 1}
    assert rec["counts"]["by_comuna"] == {"Buin": 1, "Pirque": 1}
    assert rec["counts"]["by_severity"] == {"high": 1, "severe": 1}


def test_queue_record_labels_missing_severity():
    rec = integrity.queue_record({"x": [{"id": "a", "comuna": "Buin"}]}, decided=set())
    assert rec["counts"]["by_severity"] == {"sin_clasificar": 1}


def test_build_transaction_adds_queue_digest_entry_when_given():
    kp = Keypair.random()
    digest_hex = integrity.digest([integrity.leaf(FLAG)])
    queue_hex = integrity.digest([integrity.leaf({"id": "q"})])
    tx = anchor.build_transaction(Account(kp.public_key, 1), kp, digest_hex, queue_hex)
    ops = tx.transaction.operations
    assert [o.data_name for o in ops] == [anchor.DATA_NAME, anchor.QUEUE_DATA_NAME]
    assert ops[1].data_value == bytes.fromhex(queue_hex)
    assert tx.transaction.memo.memo_hash == bytes.fromhex(digest_hex)


def test_anchor_records_queue_digest(monkeypatch, tmp_path):
    sent = {}

    def fake_submit(secret, digest_hex, queue_hex=None):
        sent["queue"] = queue_hex
        return {"hash": "tx9", "ledger": 7, "created_at": "2026-10-09T23:00:00Z"}

    monkeypatch.setattr(anchor, "submit_digest", fake_submit)
    queue = integrity.queue_record({"x": [{"id": "q", "comuna": "Buin"}]}, decided=set())
    rec = anchor.anchor([FLAG], "S", tmp_path / "a.json", queue=queue)
    assert sent["queue"] == queue["digest"]
    assert rec["queue_digest"] == queue["digest"]
    assert rec["queue_total"] == 1
