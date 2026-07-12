"""osint-score: match ingested line-items against the basket and emit anomalies.

Reads the per-line-item Parquet, the retail baselines, and the basket; matches
each line to a SKU; scores matched lines (CLP conversion + IVA gross-up +
overprice ratio + severity, per scoring.py); and writes a deterministic
data/pending_anomalies.json for the Phase 4 curation gate. Every emitted
anomaly carries a `status` (pending / unit_ambiguous / needs_baseline).
"""

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

import polars as pl

from osint_mercado import api_client, fx, matcher, scoring
from osint_mercado.baseline import Baseline
from osint_mercado.basket import load_basket


def load_baselines(path) -> dict[str, Baseline]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        row["sku_id"]: Baseline(
            sku_id=row["sku_id"],
            reference_price_clp=float(row["reference_price_clp"]),
            confidence=row["confidence"],
            n_observations=int(row["n_observations"]),
            freshest_observed_at=row["freshest_observed_at"],
            spread_ratio=float(row["spread_ratio"]),
        )
        for row in rows
    }


def _row_date(row: dict) -> date:
    # Prefer the order's own date; fall back to the capture timestamp.
    for value in (row.get("fecha"), row.get("captured_at")):
        if value:
            try:
                return date.fromisoformat(str(value)[:10])
            except ValueError:
                continue
    raise ValueError(f"line item {row.get('oc_id')} has no parseable date")


def run(items_path, baselines_path, basket_path, fx_cache_path, out_path,
        *, session=None) -> Path:
    skus = load_basket(basket_path)
    baselines = load_baselines(baselines_path)
    fx_cache = fx.load_fx_cache(fx_cache_path)
    session = session or api_client.make_session()

    df = pl.read_parquet(items_path)
    anomalies = []
    for row in df.iter_rows(named=True):
        result = matcher.match(
            row["product"], row["espec_proveedor"], row["espec_comprador"], skus
        )
        if result.sku_id is None:
            continue
        anomaly = scoring.score_line_item(
            oc_id=row["oc_id"], correlativo=int(row["correlativo"]),
            comuna=row["comuna"], producto=row["product"],
            quantity=float(row["quantity"]), moneda=row["moneda"],
            unit_price=float(row["unit_price"]),
            porcentaje_iva=float(row["porcentaje_iva"]),
            on_date=_row_date(row), oc_url=row["oc_url"],
            captured_at=row["captured_at"], match=result,
            baseline=baselines.get(result.sku_id), fx_cache=fx_cache,
            session=session,
        )
        if anomaly is not None:
            anomalies.append(anomaly)

    anomalies.sort(key=lambda a: (a.comuna, a.sku_id, a.oc_id, a.correlativo))
    rows_out = [asdict(a) for a in anomalies]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(rows_out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    fx.save_fx_cache(fx_cache, fx_cache_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Score ingested line-items into pending anomalies")
    ap.add_argument("--items", required=True, help="per-line-item Parquet from ingest")
    ap.add_argument("--baselines", default="data/baselines.json")
    ap.add_argument("--basket", default="data/basket.json")
    ap.add_argument("--fx-cache", default="data/fx_rates.json")
    ap.add_argument("--out", default="data/pending_anomalies.json")
    args = ap.parse_args()
    out = run(args.items, args.baselines, args.basket, args.fx_cache, args.out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
