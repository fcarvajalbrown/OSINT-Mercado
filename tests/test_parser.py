import json
from pathlib import Path

from osint_mercado import parser
from osint_mercado.models import PurchaseOrder

FIX = Path(__file__).parent / "fixtures"


def _detail():
    return json.loads((FIX / "oc_detail_sample.json").read_text(encoding="utf-8"))


def test_parse_detail_returns_orders():
    orders = parser.parse_detail(_detail())
    assert orders and isinstance(orders[0], PurchaseOrder)


def test_parsed_order_has_core_fields():
    order = parser.parse_detail(_detail())[0]
    assert order.codigo
    assert order.buyer.name
    assert order.items
    assert order.items[0].unit_price > 0
    assert order.items[0].quantity > 0
