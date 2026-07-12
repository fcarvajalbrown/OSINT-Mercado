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


def test_parsed_order_has_status_and_type():
    order = parser.parse_detail(_detail())[0]
    assert order.codigo_estado == 6
    assert order.estado == "Aceptada"
    assert order.codigo_tipo == "8"
    assert order.tipo == "SE"
    assert order.codigo_estado_proveedor == 4
    assert order.estado_proveedor == "Aceptada"


def test_parsed_order_has_currency_and_tax_fields():
    order = parser.parse_detail(_detail())[0]
    assert order.tipo_moneda == "CLP"
    assert order.porcentaje_iva == 19.0
    assert order.total == 539041.0
    assert order.total_neto == 452976.0
    assert order.impuestos == 86065.0
    assert order.cargos == 0.0
    assert order.descuentos == 0.0


def test_parsed_item_has_currency_and_tax_fields():
    item = parser.parse_detail(_detail())[0].items[0]
    assert item.moneda == "CLP"
    assert item.total == 379152.0
    assert item.total_cargos == 0.0
    assert item.total_descuentos == 0.0
    assert item.total_impuestos == 0.0


def test_parsed_item_has_category_codes():
    item = parser.parse_detail(_detail())[0].items[0]
    assert item.category == "Ropa, maletas y productos de aseo personal / Calzado / Zapatos"
    assert item.category_code == 53111600
    assert item.product_code == 53111601


def test_parsed_item_has_identity_fields():
    item = parser.parse_detail(_detail())[0].items[0]
    assert item.correlativo == 1
    assert "BOTIN PANAMA JACK" in item.espec_proveedor
    assert item.espec_comprador.startswith("RES X")
    # Fixture Unidad is null -> defaults to empty string, not the literal "None".
    assert item.unidad == ""
