from osint_mercado import municipal
from osint_mercado.models import Buyer, PurchaseOrder


def _order(buyer_name):
    return PurchaseOrder("C1", "n", "01012026", Buyer(buyer_name, "1", "X", "Y"), [])


def test_is_municipal_matches_municipalidad():
    assert municipal.is_municipal("I. MUNICIPALIDAD DE NUNOA")
    assert municipal.is_municipal("Municipalidad de Santiago")
    assert municipal.is_municipal("CORPORACION MUNICIPAL DE VALPARAISO")


def test_is_municipal_rejects_non_municipal():
    assert not municipal.is_municipal("SERVICIO DE SALUD METROPOLITANO")
    assert not municipal.is_municipal("MINISTERIO DE OBRAS PUBLICAS")


def test_filter_municipal_keeps_only_municipal():
    orders = [_order("Municipalidad de Maipu"), _order("Ministerio de Salud")]
    kept = municipal.filter_municipal(orders)
    assert len(kept) == 1
    assert kept[0].buyer.name == "Municipalidad de Maipu"
