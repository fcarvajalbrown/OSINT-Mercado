"""Auto-SKU catalog (ADR 0019).

The controlled basket (ADR 0005) hand-curates a few dozen commoditized SKUs with
researched retail baselines - precision-first, but only ~13% of line-items match.
This module inverts that for coverage: every distinct product a public buyer
purchases becomes an SKU automatically, keyed by its UNSPSC product code (or, when
a line carries no code, by its normalized product name). No manual review, no retail
research - the market itself baselines these codes via the peer engine (ADR 0018).

The catalog is a versioned, monotonically-growing lookup: a code seen once is an
SKU forever. Deterministic, no network.
"""

import argparse
import glob
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from osint_mercado.matcher import normalize


@dataclass(frozen=True)
class CatalogEntry:
    sku: str            # catalog key: the product code, or "name:<normalized>"
    code: str           # UNSPSC product code when present, else ""
    name: str           # most common product name seen for this SKU
    unit: str           # most common unidad
    n_orders: int
    n_communes: int
    first_seen: str


def _key(code, name) -> tuple[str, str]:
    code = str(code or "").strip()
    if code and code != "0":
        return code, code
    return "name:" + normalize(name), ""


def build_catalog(rows) -> dict[str, CatalogEntry]:
    """rows: dicts with product_code / product / unidad / comuna / fecha."""
    agg: dict[str, dict] = defaultdict(
        lambda: {"code": "", "names": Counter(), "units": Counter(),
                 "communes": set(), "n": 0, "first": ""}
    )
    for r in rows:
        key, code = _key(r.get("product_code"), r.get("product") or "")
        a = agg[key]
        a["code"] = code
        a["names"][(r.get("product") or "").strip()] += 1
        a["units"][r.get("unidad") or ""] += 1
        a["communes"].add(r.get("comuna"))
        a["n"] += 1
        f = str(r.get("fecha") or "")[:10]
        if f and (not a["first"] or f < a["first"]):
            a["first"] = f
    out: dict[str, CatalogEntry] = {}
    for key, a in agg.items():
        name = a["names"].most_common(1)[0][0] if a["names"] else ""
        unit = a["units"].most_common(1)[0][0] if a["units"] else ""
        out[key] = CatalogEntry(key, a["code"], name, unit, a["n"],
                                len(a["communes"]), a["first"])
    return out


def merge(*catalogs: dict[str, CatalogEntry]) -> dict[str, CatalogEntry]:
    """Union catalogs, summing counts and keeping the earliest first_seen.

    The catalog never shrinks: an SKU seen in any input survives.
    """
    acc: dict[str, CatalogEntry] = {}
    for cat in catalogs:
        for key, e in cat.items():
            if key not in acc:
                acc[key] = e
                continue
            prev = acc[key]
            acc[key] = CatalogEntry(
                sku=key, code=e.code or prev.code,
                name=prev.name if prev.n_orders >= e.n_orders else e.name,
                unit=prev.unit if prev.n_orders >= e.n_orders else e.unit,
                n_orders=prev.n_orders + e.n_orders,
                n_communes=max(prev.n_communes, e.n_communes),
                first_seen=min(x for x in (prev.first_seen, e.first_seen) if x) or "",
            )
    return acc


def load_catalog(path) -> dict[str, CatalogEntry]:
    p = Path(path)
    if not p.exists():
        return {}
    return {
        row["sku"]: CatalogEntry(**row)
        for row in json.loads(p.read_text(encoding="utf-8"))
    }


def save_catalog(cat: dict[str, CatalogEntry], path) -> None:
    rows = [asdict(cat[k]) for k in sorted(cat, key=lambda k: -cat[k].n_orders)]
    Path(path).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def _resolve(items: str) -> list[str]:
    p = Path(items)
    if p.is_dir():
        return sorted(glob.glob(str(p / "oc_items_*.parquet")))
    return sorted(glob.glob(items)) or [items]


def main() -> None:
    import polars as pl

    ap = argparse.ArgumentParser(description="Auto-build the product SKU catalog from captures")
    ap.add_argument("--items", required=True, help="parquet file, glob, or directory")
    ap.add_argument("--out", default="data/product_catalog.json")
    args = ap.parse_args()

    existing = load_catalog(args.out)
    built = [existing] if existing else []
    for f in _resolve(args.items):
        df = pl.read_parquet(f)
        built.append(build_catalog(df.iter_rows(named=True)))
    cat = merge(*built) if built else {}
    save_catalog(cat, args.out)
    print(f"catalog: {len(cat)} auto-SKUs -> {args.out}")


if __name__ == "__main__":
    main()
