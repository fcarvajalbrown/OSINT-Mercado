from osint_mercado import schema
from osint_mercado.models import PurchaseOrder


def is_cancelled(order: PurchaseOrder) -> bool:
    return order.codigo_estado == schema.ESTADO_CANCELADA


def drop_cancelled(orders: list[PurchaseOrder]) -> list[PurchaseOrder]:
    return [o for o in orders if not is_cancelled(o)]
