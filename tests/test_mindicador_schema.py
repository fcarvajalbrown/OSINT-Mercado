from osint_mercado import mindicador_schema as ms


def test_api_base_is_verified_literal():
    assert ms.API_BASE == "https://mindicador.cl/api"


def test_response_keys_are_verified_literals():
    assert ms.RESP_SERIE == "serie"
    assert ms.SERIE_FECHA == "fecha"
    assert ms.SERIE_VALOR == "valor"


def test_clp_maps_to_no_indicator():
    assert ms.CURRENCY_TO_INDICATOR["CLP"] is None


def test_non_clp_currencies_map_to_indicators():
    # Verified against the official ChileCompra API page: CLP, CLF (UF), USD, UTM, EUR.
    assert ms.CURRENCY_TO_INDICATOR["CLF"] == ms.IND_UF
    assert ms.CURRENCY_TO_INDICATOR["USD"] == ms.IND_DOLAR
    assert ms.CURRENCY_TO_INDICATOR["UTM"] == ms.IND_UTM
    assert ms.CURRENCY_TO_INDICATOR["EUR"] == ms.IND_EURO


def test_uf_alias_maps_to_uf_indicator():
    # Defensive alias: the code table lists CLF, but "UF" is the colloquial label.
    assert ms.CURRENCY_TO_INDICATOR["UF"] == ms.IND_UF


def test_indicator_names_are_mindicador_paths():
    assert ms.IND_UF == "uf"
    assert ms.IND_UTM == "utm"
    assert ms.IND_DOLAR == "dolar"
    assert ms.IND_EURO == "euro"
