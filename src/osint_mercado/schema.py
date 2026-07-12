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

OC_CODIGO_ESTADO = "CodigoEstado"
OC_ESTADO = "Estado"
OC_CODIGO_TIPO = "CodigoTipo"
OC_TIPO = "Tipo"
OC_CODIGO_ESTADO_PROVEEDOR = "CodigoEstadoProveedor"
OC_ESTADO_PROVEEDOR = "EstadoProveedor"

# The official status table at https://www.chilecompra.cl/api/ lists eight
# CodigoEstado values (4, 5, 6, 9, 12, 13, 14, 15). Only this one is currently relied
# on by the pipeline (order_status.drop_cancelled); the others are extracted and
# stored but not otherwise acted on, since only CodigoEstado=6 ("Aceptada") is
# confirmed against a real captured fixture.
ESTADO_CANCELADA = 9

OC_TIPO_MONEDA = "TipoMoneda"
OC_PORCENTAJE_IVA = "PorcentajeIva"
OC_TOTAL = "Total"
OC_TOTAL_NETO = "TotalNeto"
OC_IMPUESTOS = "Impuestos"
OC_CARGOS = "Cargos"
OC_DESCUENTOS = "Descuentos"

# Buyer (Comprador) fields
COMPRADOR_NOMBRE = "NombreOrganismo"
COMPRADOR_CODIGO = "CodigoOrganismo"
COMPRADOR_COMUNA = "ComunaUnidad"
COMPRADOR_REGION = "RegionUnidad"

# Items container and line-item fields
OC_ITEMS = "Items"
ITEMS_LISTADO = "Listado"
ITEM_CORRELATIVO = "Correlativo"
ITEM_PRODUCTO = "Producto"
ITEM_UNIDAD = "Unidad"
# The real product identity lives in these free-text spec fields, not in Producto
# (which is only the generic UNSPSC label). They are the matcher's primary input.
ITEM_ESPEC_COMPRADOR = "EspecificacionComprador"
ITEM_ESPEC_PROVEEDOR = "EspecificacionProveedor"
ITEM_CANTIDAD = "Cantidad"
ITEM_PRECIO = "PrecioNeto"
ITEM_MONEDA = "Moneda"
ITEM_TOTAL = "Total"
ITEM_TOTAL_CARGOS = "TotalCargos"
ITEM_TOTAL_DESCUENTOS = "TotalDescuentos"
ITEM_TOTAL_IMPUESTOS = "TotalImpuestos"
ITEM_CATEGORIA = "Categoria"
ITEM_CODIGO_CATEGORIA = "CodigoCategoria"
ITEM_CODIGO_PRODUCTO = "CodigoProducto"
