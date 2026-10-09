"""osint-build-site: render the static dashboard from confirmed flags.

Copies the self-contained frontend assets to the output directory and writes
`data/flags.json` (the confirmed flags, enriched with canonical name, category,
and overprice %). No network, no external runtime dependencies; the result is a
plain static site deployable to any host.
"""

import argparse
import glob
import hashlib
import json
import re
import shutil
from pathlib import Path

import polars as pl

from osint_mercado.basket import Sku, load_basket
from osint_mercado.integrity import attach_mirrors, attach_sources, queue_record
from osint_mercado.auto_estimate import estimates_for
from osint_mercado.leads import lead_key, public_leads
from osint_mercado.store import ITEM_COLUMNS

ITEMS_GLOB = "data/oc_items_*.parquet"
MIRROR_PUBLIC_DIR = "data/mirror/public"
QUEUE_FILES = {
    "anomalias": "data/pending_anomalies.json",
    "convenio_marco": "data/cm_pending.json",
    "precio_pares": "data/peer_pending.json",
}
DECISIONS_PATH = "data/curation_decisions.json"
ASSET_REF = re.compile(r'(href|src)="\./([^"?#]+\.(?:css|js|svg))"')

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


def public_dataset(confirmed_path, basket_path, items_glob=ITEMS_GLOB,
                   mirror_dir=MIRROR_PUBLIC_DIR) -> tuple[list[dict], dict, dict]:
    confirmed = json.loads(Path(confirmed_path).read_text(encoding="utf-8"))
    flags = build_flags(confirmed, load_basket(basket_path))
    flags, sources = attach_sources(flags, load_items(items_glob))
    flags, mirrors = attach_mirrors(flags, mirror_dir)
    return flags, sources, mirrors


def public_queue(queue_files=None, decisions_path=DECISIONS_PATH) -> dict:
    queue_files = QUEUE_FILES if queue_files is None else queue_files
    queues = {
        engine: json.loads(Path(path).read_text(encoding="utf-8"))
        for engine, path in queue_files.items() if Path(path).exists()
    }
    decisions_file = Path(decisions_path)
    decided = set(json.loads(decisions_file.read_text(encoding="utf-8"))) if decisions_file.exists() else set()
    return queue_record(queues, decided)


def public_lead_rows(confirmed_path, queue_files=None, decisions_path=DECISIONS_PATH,
                     items_glob=ITEMS_GLOB) -> list[dict]:
    queue_files = QUEUE_FILES if queue_files is None else queue_files
    queues = {
        engine: json.loads(Path(path).read_text(encoding="utf-8"))
        for engine, path in queue_files.items() if Path(path).exists()
    }
    decisions_file = Path(decisions_path)
    decisions = json.loads(decisions_file.read_text(encoding="utf-8")) if decisions_file.exists() else {}
    confirmed = json.loads(Path(confirmed_path).read_text(encoding="utf-8"))
    keys = {lead_key(lead) for items in queues.values() for lead in items}
    auto = estimates_for(load_items(items_glob), keys)
    return public_leads(queues, decisions, {row["id"] for row in confirmed}, auto)


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def fingerprint_assets(site_dir: Path) -> None:
    def versioned(match: re.Match) -> str:
        attr, rel = match.groups()
        asset = site_dir / rel
        if not asset.is_file():
            return match.group(0)
        version = hashlib.sha256(asset.read_bytes()).hexdigest()[:10]
        return f'{attr}="./{rel}?v={version}"'

    for page in site_dir.glob("*.html"):
        page.write_text(ASSET_REF.sub(versioned, page.read_text(encoding="utf-8")), encoding="utf-8")


def build(confirmed_path, basket_path, frontend_dir, out_dir,
          items_glob=ITEMS_GLOB, anchors_path="data/anchors.json",
          mirror_dir=MIRROR_PUBLIC_DIR, queue_files=None, decisions_path=DECISIONS_PATH) -> Path:
    out_dir = Path(out_dir)
    frontend_dir = Path(frontend_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(frontend_dir, out_dir)

    flags, sources, mirrors = public_dataset(confirmed_path, basket_path, items_glob, mirror_dir)

    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_json(data_dir / "flags.json", flags)
    _write_json(data_dir / "sources.json", sources)
    _write_json(data_dir / "queue.json", public_queue(queue_files, decisions_path))
    _write_json(data_dir / "leads.json", public_lead_rows(confirmed_path, queue_files, decisions_path, items_glob))
    (data_dir / "mirror").mkdir(exist_ok=True)
    for oc_id, doc in mirrors.items():
        _write_json(data_dir / "mirror" / f"{oc_id}.json", doc)
    if Path(anchors_path).exists():
        shutil.copyfile(anchors_path, data_dir / "anchors.json")
    fingerprint_assets(out_dir)
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
