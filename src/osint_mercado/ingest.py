import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from osint_mercado import api_client, municipal, parser, schema, store
from osint_mercado.config import load_ticket


def run(fecha, out_dir, ticket, codes_path, session=None, max_orders=None) -> Path:
    session = session or api_client.make_session()
    entries = json.loads(Path(codes_path).read_text(encoding="utf-8"))
    org_codes = [e["codigo_organismo"] for e in entries if e.get("codigo_organismo")]

    order_codes = []
    for org in org_codes:
        listing = api_client.fetch_json(api_client.build_by_organism_url(fecha, org, ticket), session)
        for row in (listing.get(schema.LIST_LISTADO) or []):
            code = row.get(schema.OC_CODIGO)
            if code:
                order_codes.append(code)
    if max_orders is not None:
        order_codes = order_codes[:max_orders]

    orders = []
    for codigo in order_codes:
        detail = api_client.fetch_json(api_client.build_detail_url(codigo, ticket), session)
        orders.extend(parser.parse_detail(detail))

    municipals = municipal.filter_municipal(orders)
    captured_at = datetime.now(timezone.utc).isoformat()
    df = store.orders_to_items_df(municipals, captured_at=captured_at)
    out_path = Path(out_dir) / f"oc_items_{fecha}.parquet"
    store.write_parquet(df, out_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest RM municipal purchase orders for a date")
    ap.add_argument("--fecha", required=True, help="date ddmmaaaa, e.g. 09072026")
    ap.add_argument("--out", default="data", help="output directory")
    ap.add_argument("--codes", default="data/rm_municipal_codes.json", help="RM organism codes file")
    ap.add_argument("--max-orders", type=int, default=None, help="per-run cap on orders fetched")
    args = ap.parse_args()
    path = run(fecha=args.fecha, out_dir=args.out, ticket=load_ticket(),
               codes_path=args.codes, max_orders=args.max_orders)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
