from pathlib import Path

import polars as pl

from osint_mercado.models import PurchaseOrder

# PROVISIONAL: verify the real mercadopublico.cl order deep-link before the frontend/publishing
# phase (Phase 5). The provenance requirement (ADR 0007) needs a correct link; this format is a
# placeholder confirmed only to be structurally reasonable (ends with the order code).
OC_PUBLIC_URL = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idOC="

ITEM_COLUMNS = [
    "oc_id", "buyer_name", "buyer_code", "comuna", "region", "fecha",
    "product", "quantity", "unit_price", "oc_url", "captured_at",
]


def orders_to_items_df(orders: list[PurchaseOrder], captured_at: str) -> pl.DataFrame:
    rows = [
        {
            "oc_id": o.codigo,
            "buyer_name": o.buyer.name,
            "buyer_code": o.buyer.code,
            "comuna": o.buyer.comuna,
            "region": o.buyer.region,
            "fecha": o.fecha,
            "product": item.product,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "oc_url": f"{OC_PUBLIC_URL}{o.codigo}",
            "captured_at": captured_at,
        }
        for o in orders
        for item in o.items
    ]
    return pl.DataFrame(rows, schema=ITEM_COLUMNS)


def write_parquet(df: pl.DataFrame, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
