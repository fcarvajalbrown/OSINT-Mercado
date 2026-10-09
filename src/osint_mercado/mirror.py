import argparse
import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from osint_mercado import api_client, config
from osint_mercado.integrity import leaf

MIRROR_DIR = "data/mirror"
SOURCE = f"{api_client.BASE_URL}?codigo=<oc_id>"
CONTACT_FIELDS = ("NombreContacto", "CargoContacto", "FonoContacto", "MailContacto")
PARTIES = ("Comprador", "Proveedor")


FREE_TEXT_FIELDS = ("Descripcion",)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\d/])(?:\+?56[\s-]?)?(?:\(?\d{1,2}\)?[\s-]?)?\d{4}[\s-]?\d{4}(?![\d/])")


def _mask(value):
    if isinstance(value, str):
        return PHONE.sub("[fono omitido]", EMAIL.sub("[correo omitido]", value))
    if isinstance(value, dict):
        return {k: _mask(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask(v) for v in value]
    return value


def redact(raw: dict) -> dict:
    out = copy.deepcopy(raw)
    for order in out.get("Listado") or []:
        for party in PARTIES:
            block = order.get(party)
            if isinstance(block, dict):
                for field in CONTACT_FIELDS:
                    if field in block:
                        block[field] = None
        for field in FREE_TEXT_FIELDS:
            if field in order:
                order[field] = None
    return _mask(out)


def public_copy(oc_id: str, raw: dict, fetched_at: str) -> dict:
    return {
        "oc_id": oc_id,
        "fetched_at": fetched_at,
        "source": SOURCE,
        "raw_sha256": leaf(raw),
        "redacted_fields": [f"{p}.{f}" for p in PARTIES for f in CONTACT_FIELDS] + list(FREE_TEXT_FIELDS),
        "masked": "emails and phone numbers in every other text field",
        "record": redact(raw),
    }


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def mirror_orders(oc_ids, fetch, out_dir, now) -> list[str]:
    out_dir = Path(out_dir)
    written = []
    for oc_id in oc_ids:
        raw_path = out_dir / "raw" / f"{oc_id}.json"
        if raw_path.exists():
            continue
        raw = fetch(oc_id)
        _write(raw_path, raw)
        _write(out_dir / "public" / f"{oc_id}.json", public_copy(oc_id, raw, now()))
        written.append(oc_id)
    return written


def rebuild_public(out_dir) -> list[str]:
    out_dir = Path(out_dir)
    rebuilt = []
    for raw_path in sorted((out_dir / "raw").glob("*.json")):
        oc_id = raw_path.stem
        public_path = out_dir / "public" / f"{oc_id}.json"
        old = json.loads(public_path.read_text(encoding="utf-8")) if public_path.exists() else {}
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        _write(public_path, public_copy(oc_id, raw, old.get("fetched_at")))
        rebuilt.append(oc_id)
    return rebuilt


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> None:
    ap = argparse.ArgumentParser(description="Mirror the official API record of every confirmed order")
    ap.add_argument("--confirmed", default="data/confirmed_flags.json")
    ap.add_argument("--out", default=MIRROR_DIR)
    ap.add_argument("--rebuild-public", action="store_true",
                    help="regenerate public copies from the stored raw records, keeping capture times")
    args = ap.parse_args()

    if args.rebuild_public:
        rebuilt = rebuild_public(args.out)
        print(f"rebuilt {len(rebuilt)} public copies: {', '.join(rebuilt) or 'none'}")
        return

    confirmed = json.loads(Path(args.confirmed).read_text(encoding="utf-8"))
    oc_ids = sorted({row["oc_id"] for row in confirmed if row.get("oc_id")})
    ticket = config.load_ticket()
    session = api_client.make_session()

    def fetch(oc_id):
        return api_client.fetch_json(api_client.build_detail_url(oc_id, ticket), session)

    written = mirror_orders(oc_ids, fetch, args.out, _utc_now)
    print(f"mirrored {len(written)} new of {len(oc_ids)} orders: {', '.join(written) or 'none'}")


if __name__ == "__main__":
    main()
