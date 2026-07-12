import json

from osint_mercado.basket import Sku, PriceObservation, load_basket, load_seed_observations


def test_load_basket_parses_sku_records(tmp_path):
    path = tmp_path / "basket.json"
    path.write_text(json.dumps([
        {
            "sku_id": "toner_hp_cf283a",
            "canonical_name": "Toner HP CF283A",
            "keywords": ["toner", "cf283a", "83a"],
            "unit": "unidad",
            "unspsc_category_code": 0,
            "unspsc_product_code": 0,
        }
    ]), encoding="utf-8")

    skus = load_basket(path)

    assert skus == [Sku(
        sku_id="toner_hp_cf283a",
        canonical_name="Toner HP CF283A",
        keywords=["toner", "cf283a", "83a"],
        unit="unidad",
        unspsc_category_code=0,
        unspsc_product_code=0,
    )]


def test_load_basket_defaults_missing_unspsc_codes(tmp_path):
    path = tmp_path / "basket.json"
    path.write_text(json.dumps([
        {"sku_id": "escoba_fibra", "canonical_name": "Escoba de fibra",
         "keywords": ["escoba"], "unit": "unidad"}
    ]), encoding="utf-8")

    skus = load_basket(path)

    assert skus[0].unspsc_category_code == 0
    assert skus[0].unspsc_product_code == 0


def test_load_seed_observations_parses_price_records(tmp_path):
    path = tmp_path / "seed_prices.json"
    path.write_text(json.dumps([
        {
            "sku_id": "toner_hp_cf283a",
            "retailer": "Sodimac",
            "price_clp": 45990.0,
            "observed_at": "2026-07-10",
            "url": "https://www.sodimac.cl/sodimac-cl/product/123",
        }
    ]), encoding="utf-8")

    observations = load_seed_observations(path)

    assert observations == [PriceObservation(
        sku_id="toner_hp_cf283a",
        retailer="Sodimac",
        price_clp=45990.0,
        observed_at="2026-07-10",
        url="https://www.sodimac.cl/sodimac-cl/product/123",
    )]
