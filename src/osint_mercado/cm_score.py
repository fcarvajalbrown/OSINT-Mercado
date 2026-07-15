"""osint-cm-score: raise Convenio Marco overprice leads from OC captures.

Reads the per-line-item captures and the cached CM catalog; for each line under a
CM-covered UNSPSC code, converts the net unit price to CLP, scores it against the
size/pack-normalized median CM price for the same product (cm_scoring), tags the
lead clean-or-not (cm_verify), and writes a deterministic data/cm_pending.json for
the human curation gate (ADR 0006/0024). CM leads are never auto-published; each
carries the order's provenance and the matched CM product/price/region as evidence.
"""

import argparse
import glob
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from osint_mercado import api_client, cm_catalog, cm_scoring, cm_verify, fx, matcher


def _resolve(items: str) -> list[str]:
    items = str(items)
    p = Path(items)
    if p.is_dir():
        return sorted(glob.glob(str(p / "oc_items_*.parquet")))
    return sorted(glob.glob(items)) or [items]


def _row_date(row: dict) -> date:
    for value in (row.get("fecha"), row.get("captured_at")):
        if value:
            try:
                return date.fromisoformat(str(value)[:10])
            except ValueError:
                continue
    raise ValueError(f"line item {row.get('oc_id')} has no parseable date")


def _oc_text(row: dict) -> str:
    """The item-identity text for matching and size-parsing.

    Espec-first (falls back to the `product` label only when both especificacion
    fields are empty), so the broad UNSPSC category label never drives a match -
    a category like "Papas fritas o galletas tostadas" would otherwise match an
    unrelated CM product a "Snack de Todito" espec never should (ADR 0021).
    """
    return matcher.build_match_text(
        row.get("product") or "", row.get("espec_proveedor") or "",
        row.get("espec_comprador") or "",
    )


def _code(row: dict) -> str | None:
    raw = row.get("product_code")
    if raw is None:
        return None
    code = str(int(raw)) if isinstance(raw, (int, float)) else str(raw).strip()
    return code if code and code != "0" and len(code) == 8 and code.isdigit() else None


def run(items_path, cm_catalog_path, fx_cache_path, out_path, *, session=None,
        min_refs: int = cm_scoring.MIN_REFS, accumulate: bool = True):
    import polars as pl

    cm_by_code = cm_scoring.enrich_catalog(cm_catalog.load_catalog(cm_catalog_path))
    fx_cache = fx.load_fx_cache(fx_cache_path)
    session = session or api_client.make_session()

    report = {"lines": 0, "under_cm_code": 0, "leads": 0, "clean_leads": 0,
              "fx_skipped": 0, "severe": 0, "high": 0, "watch": 0}
    leads: list[dict] = []
    for f in _resolve(items_path):
        df = pl.read_parquet(f)
        for row in df.iter_rows(named=True):
            report["lines"] += 1
            code = _code(row)
            if code is None or code not in cm_by_code:
                continue
            report["under_cm_code"] += 1
            try:
                unit_clp = fx.to_clp(
                    float(row["unit_price"]), row["moneda"], _row_date(row),
                    fx_cache, session
                )
            except (api_client.ApiError, ValueError):
                # An unconvertible currency (unknown code, or a rate lookup that
                # failed) means we cannot compare like-for-like; drop this one line
                # rather than abort the batch. These are a negligible minority.
                report["fx_skipped"] += 1
                continue
            lead = cm_scoring.score_cm(
                oc_id=row["oc_id"], correlativo=int(row["correlativo"]),
                comuna=row["comuna"], product_code=code, oc_text=_oc_text(row),
                unit_price_clp_net=unit_clp, oc_url=row["oc_url"],
                captured_at=row["captured_at"], cm_rows=cm_by_code[code],
                min_refs=min_refs,
            )
            if lead is None:
                continue
            clean, reason = cm_verify.assess_lead(lead.oc_text, lead.cm_sample_producto)
            record = asdict(lead)
            record["clean"] = clean
            record["clean_reason"] = reason
            leads.append(record)
            report["leads"] += 1
            report["clean_leads"] += int(clean)
            report[lead.severity] += 1

    out_path = Path(out_path)
    merged: dict[str, dict] = {}
    if accumulate and out_path.exists():
        for row in json.loads(out_path.read_text(encoding="utf-8")):
            merged[row["id"]] = row
    for r in leads:
        merged[r["id"]] = r
    rows_out = sorted(
        merged.values(),
        key=lambda r: (-(r["ratio"] or 0), r["comuna"], r["product_code"], r["oc_id"]),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(rows_out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    fx.save_fx_cache(fx_cache, fx_cache_path)
    return out_path, report


def main() -> None:
    ap = argparse.ArgumentParser(description="Raise Convenio Marco overprice leads from captures")
    ap.add_argument("--items", required=True, help="parquet file, glob, or directory of captures")
    ap.add_argument("--cm-catalog", default="data/cm_catalog.parquet")
    ap.add_argument("--fx-cache", default="data/fx_rates.json")
    ap.add_argument("--out", default="data/cm_pending.json")
    ap.add_argument("--min-refs", type=int, default=cm_scoring.MIN_REFS)
    args = ap.parse_args()
    out, report = run(args.items, args.cm_catalog, args.fx_cache, args.out,
                      min_refs=args.min_refs)
    print(f"wrote {out}")
    print(f"  lines={report['lines']} under_cm_code={report['under_cm_code']} "
          f"leads={report['leads']} clean={report['clean_leads']} "
          f"(severe={report['severe']} high={report['high']} watch={report['watch']})")


if __name__ == "__main__":
    main()
