"""Single source of truth for Mercado Publico OC field names.

Values below are the documented names. After capturing the real fixture
(this task), verify each against tests/fixtures/oc_detail_sample.json and
correct any that differ. Nothing else in the codebase may hard-code these
strings; import from here.
"""

# List-by-date envelope
LIST_CANTIDAD = "Cantidad"
LIST_LISTADO = "Listado"

# Order (detail) fields
OC_CODIGO = "Codigo"
OC_NOMBRE = "Nombre"
# FechaCreacion is NOT a direct key on the order. The order's own creation
# date is nested under a "Fechas" object (order[OC_FECHAS][OC_FECHA]).
# A top-level "FechaCreacion" also exists on the detail envelope itself, but
# that is the API response timestamp, not the order's date. See
# docs/api/ordenes-de-compra-schema.md for the reconciliation notes.
OC_FECHAS = "Fechas"
OC_FECHA = "FechaCreacion"
OC_COMPRADOR = "Comprador"

# Buyer (Comprador) fields
COMPRADOR_NOMBRE = "NombreOrganismo"
COMPRADOR_CODIGO = "CodigoOrganismo"
COMPRADOR_COMUNA = "ComunaUnidad"
COMPRADOR_REGION = "RegionUnidad"

# Items container and line-item fields
OC_ITEMS = "Items"
ITEMS_LISTADO = "Listado"
ITEM_PRODUCTO = "Producto"
ITEM_CANTIDAD = "Cantidad"
ITEM_PRECIO = "PrecioNeto"
