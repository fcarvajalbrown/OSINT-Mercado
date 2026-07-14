from osint_mercado import verify
from osint_mercado.basket import Sku


def _f(sev="severe", ratio=5.0, status="pending"):
    return {"status": status, "severity": sev, "overprice_ratio": ratio}


PAPEL = Sku("papel_resma_oficio_75g", "Papel resma oficio", ["papel fotocopia oficio", "resma oficio 500"])
JABON = Sku("jabon_liquido", "Jabon liquido", ["jabon liquido"])
ESMALTE = Sku("pintura_esmalte_gal", "Esmalte", ["esmalte al agua", "esmalte sintetico"])


def test_clean_exact_match_is_publishable():
    ok, _ = verify.is_publishable(_f(), "PAPEL FOTOCOPIA OFICIO 75G. 500 HOJAS.", PAPEL, peer_confirmed=True)
    assert ok


def test_dispenser_of_the_consumable_is_rejected():
    ok, why = verify.is_publishable(_f(), "DISPENSADOR METALICO DE PARED PARA JABON LIQUIDO 500 ML", JABON, peer_confirmed=True)
    assert not ok and "context" in why


def test_multi_gallon_container_is_rejected():
    ok, why = verify.is_publishable(_f(sev="high", ratio=2.8), "ESMALTE AL AGUA SHERWIN WILLIAMS 4 GL BLANCO", ESMALTE, peer_confirmed=True)
    assert not ok


def test_quote_request_line_is_rejected():
    ok, why = verify.is_publishable(_f(), "ESMALTE AL AGUA, EL PROVEEDOR DEBERA ADJUNTAR COTIZACION FORMAL", ESMALTE, peer_confirmed=True)
    assert not ok


def test_requires_peer_confirmation():
    ok, why = verify.is_publishable(_f(), "PAPEL FOTOCOPIA OFICIO 75G 500 HOJAS", PAPEL, peer_confirmed=False)
    assert not ok and "peer" in why


def test_keyword_must_appear_in_espec():
    # espec describes a different product; the SKU keyword is absent
    ok, why = verify.is_publishable(_f(), "TIJERA ESCOLAR 16 CM", PAPEL, peer_confirmed=True)
    assert not ok


def test_below_high_tier_not_published():
    ok, why = verify.is_publishable(_f(sev="watch", ratio=1.7), "PAPEL FOTOCOPIA OFICIO 500 HOJAS", PAPEL, peer_confirmed=True)
    assert not ok


def test_implausible_ratio_rejected():
    ok, why = verify.is_publishable(_f(ratio=50.0), "PAPEL FOTOCOPIA OFICIO 500 HOJAS", PAPEL, peer_confirmed=True)
    assert not ok


def test_auto_publish_requires_tier_stable_sku():
    # te is tier-variable (flavored vs plain): passes is_publishable but NOT auto.
    TE = Sku("te_caja100", "Te", ["te negro bolsas", "bolsitas de te"])
    ok, _ = verify.is_publishable(_f(), "TE NEGRO 100 BOLSAS SUPREMO", TE, peer_confirmed=True)
    auto, why = verify.is_auto_publishable(_f(), "TE NEGRO 100 BOLSAS SUPREMO", TE, peer_confirmed=True)
    assert ok and not auto and "tier-variable" in why


def test_auto_publish_allows_tier_stable_sku():
    auto, _ = verify.is_auto_publishable(_f(), "PAPEL FOTOCOPIA OFICIO 75G 500 HOJAS", PAPEL, peer_confirmed=True)
    assert auto
