from pathlib import Path

import polars as pl

from osint_mercado.models import PurchaseOrder

# PROVISIONAL: verify the real mercadopublico.cl order deep-link before the frontend/publishing
# phase (Phase 5). The provenance requirement (ADR 0007) needs a correct link; this format is a
# placeholder confirmed only to be structurally reasonable (ends with the order code).
OC_PUBLIC_URL = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idOC="

ITEM_COLUMNS = [
    "oc_id", "buyer_name", "buyer_code", "comuna", "region", "fecha",
    "codigo_estado", "estado", "codigo_tipo", "tipo",
    "codigo_estado_proveedor", "estado_proveedor",
    "tipo_moneda", "porcentaje_iva", "order_total", "order_total_neto",
    "impuestos", "cargos", "descuentos",
    "product", "quantity", "unit_price",
    "moneda", "total", "total_cargos", "total_descuentos", "total_impuestos",
    "category", "category_code", "product_code",
    "oc_url", "captured_at",
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
            "codigo_estado": o.codigo_estado,
            "estado": o.estado,
            "codigo_tipo": o.codigo_tipo,
            "tipo": o.tipo,
            "codigo_estado_proveedor": o.codigo_estado_proveedor,
            "estado_proveedor": o.estado_proveedor,
            "tipo_moneda": o.tipo_moneda,
            "porcentaje_iva": o.porcentaje_iva,
            "order_total": o.total,
            "order_total_neto": o.total_neto,
            "impuestos": o.impuestos,
            "cargos": o.cargos,
            "descuentos": o.descuentos,
            "product": item.product,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "moneda": item.moneda,
            "total": item.total,
            "total_cargos": item.total_cargos,
            "total_descuentos": item.total_descuentos,
            "total_impuestos": item.total_impuestos,
            "category": item.category,
            "category_code": item.category_code,
            "product_code": item.product_code,
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
