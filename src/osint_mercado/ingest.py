import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from osint_mercado import api_client, municipal, parser, schema, store
from osint_mercado.api_client import ApiError
from osint_mercado.config import load_ticket

logger = logging.getLogger(__name__)


def run(fecha, out_dir, ticket, codes_path, session=None, max_per_organism=None,
        pace_seconds=0.0, sleep=time.sleep) -> Path:
    session = session or api_client.make_session()
    entries = json.loads(Path(codes_path).read_text(encoding="utf-8"))
    org_codes = [e["codigo_organismo"] for e in entries if e.get("codigo_organismo")]

    order_codes = []
    failures = 0
    for org in org_codes:
        try:
            listing = api_client.fetch_json(api_client.build_by_organism_url(fecha, org, ticket), session)
        except ApiError:
            failures += 1
            logger.warning("listing failed for organism %s; skipping", org)
            continue
        codes = [row.get(schema.OC_CODIGO) for row in (listing.get(schema.LIST_LISTADO) or [])]
        codes = [c for c in codes if c]
        if max_per_organism is not None:
            codes = codes[:max_per_organism]
        order_codes.extend(codes)
        if pace_seconds:
            sleep(pace_seconds)

    orders = []
    for codigo in order_codes:
        try:
            detail = api_client.fetch_json(api_client.build_detail_url(codigo, ticket), session)
        except ApiError:
            failures += 1
            logger.warning("detail failed for order %s; skipping", codigo)
            continue
        orders.extend(parser.parse_detail(detail))
        if pace_seconds:
            sleep(pace_seconds)

    municipals = municipal.filter_municipal(orders)
    captured_at = datetime.now(timezone.utc).isoformat()
    df = store.orders_to_items_df(municipals, captured_at=captured_at)
    out_path = Path(out_dir) / f"oc_items_{fecha}.parquet"
    store.write_parquet(df, out_path)
    if failures:
        logger.warning("%d API request(s) failed and were skipped", failures)
    return out_path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Ingest RM municipal purchase orders for a date")
    ap.add_argument("--fecha", required=True, help="date ddmmaaaa, e.g. 09072026")
    ap.add_argument("--out", default="data", help="output directory")
    ap.add_argument("--codes", default="data/rm_municipal_codes.json", help="RM organism codes file")
    ap.add_argument("--max-per-organism", type=int, default=None,
                    help="cap orders fetched per municipality (fair across all comunas)")
    ap.add_argument("--pace", type=float, default=0.0, help="seconds to sleep between API calls")
    args = ap.parse_args()
    path = run(fecha=args.fecha, out_dir=args.out, ticket=load_ticket(),
               codes_path=args.codes, max_per_organism=args.max_per_organism,
               pace_seconds=args.pace)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
