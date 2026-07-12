from osint_mercado import schema
from osint_mercado.models import Buyer, LineItem, PurchaseOrder


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_fecha(order: dict) -> str:
    fechas = order.get(schema.OC_FECHAS) or {}
    return str(fechas.get(schema.OC_FECHA, ""))


def _parse_buyer(order: dict) -> Buyer:
    comprador = order.get(schema.OC_COMPRADOR) or {}
    return Buyer(
        name=str(comprador.get(schema.COMPRADOR_NOMBRE, "")),
        code=str(comprador.get(schema.COMPRADOR_CODIGO, "")),
        comuna=str(comprador.get(schema.COMPRADOR_COMUNA, "")),
        region=str(comprador.get(schema.COMPRADOR_REGION, "")),
    )


def _parse_items(order: dict) -> list[LineItem]:
    container = order.get(schema.OC_ITEMS) or {}
    rows = container.get(schema.ITEMS_LISTADO) or []
    return [
        LineItem(
            product=str(row.get(schema.ITEM_PRODUCTO, "")),
            quantity=_to_float(row.get(schema.ITEM_CANTIDAD)),
            unit_price=_to_float(row.get(schema.ITEM_PRECIO)),
        )
        for row in rows
    ]


def parse_detail(payload: dict) -> list[PurchaseOrder]:
    orders = payload.get(schema.LIST_LISTADO) or []
    return [
        PurchaseOrder(
            codigo=str(order.get(schema.OC_CODIGO, "")),
            name=str(order.get(schema.OC_NOMBRE, "")),
            fecha=_parse_fecha(order),
            buyer=_parse_buyer(order),
            items=_parse_items(order),
        )
        for order in orders
    ]
