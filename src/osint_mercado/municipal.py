import unicodedata

from osint_mercado.models import PurchaseOrder


def _normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    return "".join(c for c in stripped if not unicodedata.combining(c)).upper()


def is_municipal(buyer_name: str) -> bool:
    return "MUNICIPAL" in _normalize(buyer_name)


def filter_municipal(orders: list[PurchaseOrder]) -> list[PurchaseOrder]:
    return [o for o in orders if is_municipal(o.buyer.name)]
