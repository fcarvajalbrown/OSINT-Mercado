"""osint-build-site: render the static dashboard from confirmed flags.

Copies the self-contained frontend assets to the output directory and writes
`data/flags.json` (the confirmed flags, enriched with canonical name, category,
and overprice %). No network, no external runtime dependencies; the result is a
plain static site deployable to any host.
"""

import argparse
import json
import shutil
from pathlib import Path

from osint_mercado.basket import Sku, load_basket

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


def build(confirmed_path, basket_path, frontend_dir, out_dir) -> Path:
    out_dir = Path(out_dir)
    frontend_dir = Path(frontend_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(frontend_dir, out_dir)

    confirmed = json.loads(Path(confirmed_path).read_text(encoding="utf-8"))
    skus = load_basket(basket_path)
    flags = build_flags(confirmed, skus)

    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "flags.json").write_text(
        json.dumps(flags, indent=2, ensure_ascii=False), encoding="utf-8"
    )
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
