from pathlib import Path

from osint_mercado.basket import load_basket

BASKET_PATH = Path(__file__).parent.parent / "data" / "basket.json"


def test_v1_basket_has_nineteen_unique_skus():
    skus = load_basket(BASKET_PATH)
    assert len(skus) == 19
    assert len({s.sku_id for s in skus}) == 19


def test_every_sku_has_canonical_name_unit_and_keywords():
    skus = load_basket(BASKET_PATH)
    for sku in skus:
        assert sku.canonical_name
        assert sku.unit
        assert sku.keywords


def test_every_sku_has_a_dashboard_category():
    skus = load_basket(BASKET_PATH)
    cats = {s.category for s in skus}
    assert "" not in cats
    assert cats == {"Oficina y computación", "Seguridad y EPP", "Limpieza"}
