import hashlib
import json
import math

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


def record(flags: list[dict]) -> dict:
    leaves = [leaf(f) for f in flags]
    return {
        "network": NETWORK,
        "flag_ids": [f["id"] for f in flags],
        "leaves": leaves,
        "digest": digest(leaves),
    }
