"""osint-peer-score: flag purchases priced far above peer public buyers (ADR 0018).

Reads one or more per-line-item Parquet captures, normalizes every unit price to
CLP gross (IVA-aligned, currency-converted), builds a peer median + MAD per product
code across all buyers, and emits the outliers to a deterministic JSON queue with
provenance and stable ids for the same curation gate the basket flags use.
"""

import argparse
import glob
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import polars as pl

from osint_mercado import api_client, fx, peers, scoring


@dataclass(frozen=True)
class PeerAnomaly:
    id: str
    oc_id: str
    correlativo: int
    comuna: str
    product_code: str
    product: str
    quantity: float
    moneda: str
    unit_price: float
    unit_price_clp_gross: float
    peer_median_clp: float
    mad_clp: float
    n_peers: int
    robust_z: float
    overprice_ratio: float
    severity: str
    status: str
    oc_url: str
    captured_at: str


def _row_date(row: dict) -> date:
    for value in (row.get("fecha"), row.get("captured_at")):
        if value:
            try:
                return date.fromisoformat(str(value)[:10])
            except ValueError:
                continue
    raise ValueError(f"line item {row.get('oc_id')} has no parseable date")


def _resolve_items(items: str) -> list[str]:
    p = Path(items)
    if p.is_dir():
        return sorted(glob.glob(str(p / "oc_items_*.parquet")))
    return sorted(glob.glob(items)) or [items]


def _peer_id(oc_id: str, correlativo: int, product_code: str) -> str:
    raw = f"peer|{oc_id}|{correlativo}|{product_code}".encode()
    return hashlib.sha1(raw).hexdigest()[:16]


def run(items, baselines_path, out_path, fx_cache_path, *, session=None) -> Path:
    files = _resolve_items(items)
    fx_cache = fx.load_fx_cache(fx_cache_path)
    session = session or api_client.make_session()

    df = pl.concat([pl.read_parquet(f) for f in files], how="diagonal_relaxed")

    # First pass: normalize every line to CLP gross and collect peer observations.
    priced: list[dict] = []
    peer_rows: list[tuple[str, str, float]] = []
    for row in df.iter_rows(named=True):
        code = str(row.get("product_code") or "").strip()
        if not code or code == "0":
            continue
        try:
            unit_clp = fx.to_clp(
                float(row["unit_price"]), row["moneda"], _row_date(row),
                fx_cache, session,
            )
        except Exception:
            continue
        gross = round(scoring.gross_up(unit_clp, float(row.get("porcentaje_iva") or 0.0)), 2)
        if gross <= 0:
            continue
        rec = {"row": row, "code": code, "gross": gross}
        priced.append(rec)
        peer_rows.append((code, row.get("product") or "", gross))

    stats = peers.build_peer_stats(peer_rows)

    anomalies: list[PeerAnomaly] = []
    seen: set[str] = set()
    for rec in priced:
        stat = stats.get(rec["code"])
        if stat is None:
            continue
        hit = peers.classify(rec["gross"], stat)
        if hit is None:
            continue
        row = rec["row"]
        aid = _peer_id(row["oc_id"], int(row["correlativo"]), rec["code"])
        if aid in seen:
            continue
        seen.add(aid)
        anomalies.append(PeerAnomaly(
            id=aid, oc_id=row["oc_id"], correlativo=int(row["correlativo"]),
            comuna=row["comuna"], product_code=rec["code"],
            product=row.get("product") or "", quantity=float(row.get("quantity") or 0.0),
            moneda=row["moneda"], unit_price=float(row["unit_price"]),
            unit_price_clp_gross=rec["gross"], peer_median_clp=stat.median_clp,
            mad_clp=stat.mad_clp, n_peers=stat.n, robust_z=hit.robust_z,
            overprice_ratio=hit.ratio, severity=hit.severity, status="peer_pending",
            oc_url=row.get("oc_url") or "", captured_at=row.get("captured_at") or "",
        ))

    anomalies.sort(key=lambda a: (-a.overprice_ratio, a.comuna, a.product_code))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps([asdict(a) for a in anomalies], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    fx.save_fx_cache(fx_cache, fx_cache_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Flag purchases priced far above peer public buyers")
    ap.add_argument("--items", required=True, help="parquet file, glob, or directory of oc_items_*.parquet")
    ap.add_argument("--baselines", default="data/baselines.json")
    ap.add_argument("--out", default="data/peer_pending.json")
    ap.add_argument("--fx-cache", default="data/fx_rates.json")
    args = ap.parse_args()
    out = run(args.items, args.baselines, args.out, args.fx_cache)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
