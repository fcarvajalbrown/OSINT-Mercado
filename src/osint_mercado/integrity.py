import hashlib
import json
import math
from pathlib import Path

import polars as pl

NETWORK = "testnet"


def _normalise(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    return value


def canonical(obj) -> str:
    return json.dumps(_normalise(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def leaf(obj) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def digest(leaves: list[str]) -> str:
    return hashlib.sha256(b"".join(bytes.fromhex(h) for h in sorted(leaves))).hexdigest()


def attach_sources(flags: list[dict], items: pl.DataFrame) -> tuple[list[dict], dict]:
    sources = {}
    out = []
    if "captured_at" in items.columns:
        items = items.sort("captured_at")
    for flag in flags:
        match = items.filter(
            (pl.col("oc_id") == flag.get("oc_id"))
            & (pl.col("correlativo") == flag.get("correlativo"))
        )
        flag = dict(flag)
        if match.height:
            snapshot = _normalise(match.row(0, named=True))
            sources[flag["id"]] = snapshot
            flag["source_sha256"] = leaf(snapshot)
        out.append(flag)
    return out, sources


def attach_mirrors(flags: list[dict], public_dir) -> tuple[list[dict], dict]:
    public_dir = Path(public_dir)
    mirrors = {}
    out = []
    for flag in flags:
        flag = dict(flag)
        oc_id = flag.get("oc_id")
        path = public_dir / f"{oc_id}.json"
        if oc_id and path.exists():
            doc = mirrors.get(oc_id) or json.loads(path.read_text(encoding="utf-8"))
            mirrors[oc_id] = doc
            flag["mirror_sha256"] = leaf(doc)
        out.append(flag)
    return out, mirrors


def queue_record(queues: dict[str, list[dict]], decided: set[str]) -> dict:
    by_engine: dict[str, int] = {}
    by_comuna: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    hashes = []
    for engine, leads in queues.items():
        for lead in leads:
            if lead.get("id") in decided:
                continue
            hashes.append(leaf(lead))
            by_engine[engine] = by_engine.get(engine, 0) + 1
            comuna = lead.get("comuna") or "sin_comuna"
            by_comuna[comuna] = by_comuna.get(comuna, 0) + 1
            severity = lead.get("severity") or "sin_clasificar"
            by_severity[severity] = by_severity.get(severity, 0) + 1
    hashes.sort()
    return {
        "network": NETWORK,
        "total": len(hashes),
        "lead_hashes": hashes,
        "digest": digest(hashes),
        "counts": {
            "by_engine": by_engine,
            "by_comuna": dict(sorted(by_comuna.items())),
            "by_severity": by_severity,
        },
    }


def record(flags: list[dict]) -> dict:
    leaves = [leaf(f) for f in flags]
    return {
        "network": NETWORK,
        "flag_ids": [f["id"] for f in flags],
        "leaves": leaves,
        "digest": digest(leaves),
    }
