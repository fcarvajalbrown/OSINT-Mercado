from osint_mercado import order_status
from osint_mercado.models import Buyer, PurchaseOrder


def _order(codigo, codigo_estado):
    return PurchaseOrder(codigo, "n", "01012026", Buyer("Municipalidad de Test", "1", "X", "Y"), [],
                          codigo_estado=codigo_estado)


def test_is_cancelled_true_for_estado_9():
    assert order_status.is_cancelled(_order("C1", 9))


def test_is_cancelled_false_for_other_estados():
    assert not order_status.is_cancelled(_order("C1", 6))


def test_drop_cancelled_keeps_only_non_cancelled():
    orders = [_order("C1", 6), _order("C2", 9), _order("C3", 12)]
    kept = order_status.drop_cancelled(orders)
    assert [o.codigo for o in kept] == ["C1", "C3"]
