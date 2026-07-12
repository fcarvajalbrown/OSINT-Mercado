from osint_mercado import schema
from osint_mercado.models import Buyer, LineItem, PurchaseOrder


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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
            moneda=str(row.get(schema.ITEM_MONEDA, "")),
            total=_to_float(row.get(schema.ITEM_TOTAL)),
            total_cargos=_to_float(row.get(schema.ITEM_TOTAL_CARGOS)),
            total_descuentos=_to_float(row.get(schema.ITEM_TOTAL_DESCUENTOS)),
            total_impuestos=_to_float(row.get(schema.ITEM_TOTAL_IMPUESTOS)),
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
            codigo_estado=_to_int(order.get(schema.OC_CODIGO_ESTADO)),
            estado=str(order.get(schema.OC_ESTADO, "")),
            codigo_tipo=str(order.get(schema.OC_CODIGO_TIPO, "")),
            tipo=str(order.get(schema.OC_TIPO, "")),
            codigo_estado_proveedor=_to_int(order.get(schema.OC_CODIGO_ESTADO_PROVEEDOR)),
            estado_proveedor=str(order.get(schema.OC_ESTADO_PROVEEDOR, "")),
            tipo_moneda=str(order.get(schema.OC_TIPO_MONEDA, "")),
            porcentaje_iva=_to_float(order.get(schema.OC_PORCENTAJE_IVA)),
            total=_to_float(order.get(schema.OC_TOTAL)),
            total_neto=_to_float(order.get(schema.OC_TOTAL_NETO)),
            impuestos=_to_float(order.get(schema.OC_IMPUESTOS)),
            cargos=_to_float(order.get(schema.OC_CARGOS)),
            descuentos=_to_float(order.get(schema.OC_DESCUENTOS)),
        )
        for order in orders
    ]
