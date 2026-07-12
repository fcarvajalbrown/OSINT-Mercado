"""Single source of truth for mindicador.cl field names and the OC currency map.

Mirrors the role of schema.py for the Mercado Publico API: nothing else in the
codebase hard-codes these strings; import from here.

Verified live 2026-07-12 against https://mindicador.cl/api and
https://mindicador.cl/api/uf/09-06-2026 (response version 1.7.0). The historical
per-indicator endpoint is GET {API_BASE}/{indicador}/{dd-mm-yyyy} and returns
{version, autor, codigo, nombre, unidad_medida, serie: [{fecha, valor}]}, where
`valor` is the CLP value of one unit of the indicator on that date.

Currency codes come from the official ChileCompra API page (per
docs/research/2026-07-12-parser-improvement.md, section 2.1): Mercado Publico
purchase orders can be denominated in CLP, CLF (UF), USD, UTM, EUR.
"""

API_BASE = "https://mindicador.cl/api"

# Indicator path segments (also the mindicador response `codigo` values).
IND_UF = "uf"
IND_UTM = "utm"
IND_DOLAR = "dolar"
IND_EURO = "euro"

# Response field names.
RESP_VERSION = "version"
RESP_SERIE = "serie"
SERIE_FECHA = "fecha"
SERIE_VALOR = "valor"

# Order/item currency code (Moneda / TipoMoneda) -> mindicador indicator.
# CLP needs no conversion. CLF is the ISO 4217 code for the UF; "UF" is a
# defensive colloquial alias in case the API ever emits it that way.
CURRENCY_TO_INDICATOR: dict[str, str | None] = {
    "CLP": None,
    "CLF": IND_UF,
    "UF": IND_UF,
    "USD": IND_DOLAR,
    "UTM": IND_UTM,
    "EUR": IND_EURO,
}
