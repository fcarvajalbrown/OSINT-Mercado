"""osint-build-site: render the static dashboard from confirmed flags.

Copies the self-contained frontend assets to the output directory and writes
`data/flags.json` (the confirmed flags, enriched with canonical name, category,
and overprice %). No network, no external runtime dependencies; the result is a
plain static site deployable to any host.
"""

import argparse
import glob
import json
import shutil
from pathlib import Path

import polars as pl

from osint_mercado.basket import Sku, load_basket
from osint_mercado.integrity import attach_sources
from osint_mercado.store import ITEM_COLUMNS

ITEMS_GLOB = "data/oc_items_*.parquet"

# Fields carried through to the published dashboard dataset.
_PUBLIC_FIELDS = (
    "id", "comuna", "sku_id", "oc_id", "correlativo", "unit_price_clp_gross",
    "reference_price_clp", "overprice_ratio", "severity", "oc_url",
    "reviewed_at", "curation_note",
)


def build_flags(confirmed: list[dict], skus: list[Sku]) -> list[dict]:
    by_id = {s.sku_id: s for s in skus}
    flags = []
    for row in confirmed:
        sku = by_id.get(row.get("sku_id"))
        ratio = row.get("overprice_ratio")
        flag = {k: row.get(k) for k in _PUBLIC_FIELDS}
        flag["canonical_name"] = sku.canonical_name if sku else row.get("sku_id", "")
        flag["category"] = sku.category if sku else ""
        flag["overprice_pct"] = round((ratio - 1) * 100) if isinstance(ratio, (int, float)) else None
        flags.append(flag)
    flags.sort(key=lambda f: (f.get("comuna") or "", f.get("sku_id") or "",
                              f.get("oc_id") or "", f.get("correlativo") or 0))
    return flags


def load_items(items_glob: str = ITEMS_GLOB) -> pl.DataFrame:
    files = sorted(glob.glob(items_glob))
    if not files:
        return pl.DataFrame(schema={"oc_id": pl.String, "correlativo": pl.Int64})
    frames = [pl.read_parquet(f) for f in files]
    items = pl.concat(frames, how="diagonal_relaxed")
    missing = [c for c in ITEM_COLUMNS if c not in items.columns]
    items = items.with_columns([pl.lit(None).alias(c) for c in missing])
    return items.select(ITEM_COLUMNS)


def public_dataset(confirmed_path, basket_path, items_glob=ITEMS_GLOB) -> tuple[list[dict], dict]:
    confirmed = json.loads(Path(confirmed_path).read_text(encoding="utf-8"))
    flags = build_flags(confirmed, load_basket(basket_path))
    return attach_sources(flags, load_items(items_glob))


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def build(confirmed_path, basket_path, frontend_dir, out_dir,
          items_glob=ITEMS_GLOB, anchors_path="data/anchors.json") -> Path:
    out_dir = Path(out_dir)
    frontend_dir = Path(frontend_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(frontend_dir, out_dir)

    flags, sources = public_dataset(confirmed_path, basket_path, items_glob)

    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_json(data_dir / "flags.json", flags)
    _write_json(data_dir / "sources.json", sources)
    if Path(anchors_path).exists():
        shutil.copyfile(anchors_path, data_dir / "anchors.json")
    return out_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the static dashboard from confirmed flags")
    ap.add_argument("--confirmed", default="data/confirmed_flags.json")
    ap.add_argument("--basket", default="data/basket.json")
    ap.add_argument("--frontend", default="frontend")
    ap.add_argument("--out", default="dist")
    args = ap.parse_args()
    out = build(args.confirmed, args.basket, args.frontend, args.out)
    print(f"built site at {out}")


if __name__ == "__main__":
    main()
