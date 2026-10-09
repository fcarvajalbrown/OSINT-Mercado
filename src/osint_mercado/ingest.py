import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from osint_mercado import api_client, municipal, order_status, parser, schema, store
from osint_mercado.api_client import ApiError
from osint_mercado.config import load_ticket
from osint_mercado.fetcher import CircuitOpen, Fetcher, QuotaExhausted, UsageLog

CACHE_DIR = "data/cache"
USAGE_LOG = "data/api_usage.log"
DAILY_LIMIT = 9000
STOP_EXIT_CODE = 3

logger = logging.getLogger(__name__)


def run(fecha, out_dir, ticket, codes_path, session=None, max_per_organism=None,
        pace_seconds=0.0, sleep=time.sleep, fetcher=None) -> Path:
    session = session or (None if fetcher else api_client.make_session())
    entries = json.loads(Path(codes_path).read_text(encoding="utf-8"))
    org_codes = [e["codigo_organismo"] for e in entries if e.get("codigo_organismo")]

    def get_listing(org):
        if fetcher:
            return fetcher.get_listing(fecha, org)
        return api_client.fetch_json(api_client.build_by_organism_url(fecha, org, ticket), session)

    def get_detail(codigo):
        if fetcher:
            return fetcher.get_detail(codigo)
        return api_client.fetch_json(api_client.build_detail_url(codigo, ticket), session)

    order_codes = []
    gaps = []
    for org in org_codes:
        try:
            listing = get_listing(org)
        except ApiError:
            gaps.append({"kind": "listing", "organism": org})
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
            detail = get_detail(codigo)
        except ApiError:
            gaps.append({"kind": "detail", "codigo": codigo})
            logger.warning("detail failed for order %s; skipping", codigo)
            continue
        orders.extend(parser.parse_detail(detail))
        if pace_seconds:
            sleep(pace_seconds)

    active = order_status.drop_cancelled(orders)
    municipals = municipal.filter_municipal(active)
    captured_at = datetime.now(timezone.utc).isoformat()
    df = store.orders_to_items_df(municipals, captured_at=captured_at)
    out_path = Path(out_dir) / f"oc_items_{fecha}.parquet"
    store.write_parquet(df, out_path)
    gaps_path = Path(out_dir) / f"oc_items_{fecha}.gaps.json"
    if gaps:
        gaps_path.write_text(json.dumps(gaps, indent=2), encoding="utf-8")
        logger.warning("%d API request(s) failed and were skipped; listed in %s", len(gaps), gaps_path)
    elif gaps_path.exists():
        gaps_path.unlink()
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
    ap.add_argument("--cache", default=CACHE_DIR, help="response cache directory")
    ap.add_argument("--usage-log", default=USAGE_LOG, help="rolling 24 h request log")
    ap.add_argument("--daily-limit", type=int, default=DAILY_LIMIT,
                    help="stop before this many requests in 24 h (official cap is 10,000)")
    args = ap.parse_args()
    ticket = load_ticket()
    fetcher = Fetcher(api_client.make_session(), ticket, args.cache,
                      UsageLog(args.usage_log, args.daily_limit), pace_seconds=args.pace)
    try:
        path = run(fecha=args.fecha, out_dir=args.out, ticket=ticket, codes_path=args.codes,
                   max_per_organism=args.max_per_organism, fetcher=fetcher)
    except (QuotaExhausted, CircuitOpen) as exc:
        print(f"STOPPED {args.fecha}: {exc}")
        sys.exit(STOP_EXIT_CODE)
    print(f"wrote {path} ({fetcher.usage.count()} requests in the last 24 h)")


if __name__ == "__main__":
    main()
