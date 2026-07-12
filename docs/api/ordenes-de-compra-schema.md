# Ordenes de Compra API — observed real schema

Captured live from `https://api.mercadopublico.cl/servicios/v1/publico/ordenesdecompra.json`
on 2026-07-12, using `fecha=09072026` for the list call and the first returned
`Codigo` for the detail call. Fixtures: `tests/fixtures/oc_list_sample.json`
(list-by-date, 16664 orders) and `tests/fixtures/oc_detail_sample.json`
(single order detail).

## Does the list response already contain buyer/items?

**No.** The list-by-date response (`GET ?fecha=...`) returns a lightweight
envelope where each entry in `Listado` has only three fields:

```json
{"Codigo": "1002-211-SE26", "Nombre": "EPP FUNC. OSORNO", "CodigoEstado": 6}
```

No buyer (`Comprador`), items (`Items`), or amount fields are present at the
list level. The two-step list -> detail flow assumed by the plan is
required: later tasks (parser, CLI) must fetch each order's detail via
`?codigo=...` to get buyer and line-item data. This cannot be skipped.

## List envelope (top level, `?fecha=...`)

```
Cantidad      int    — count of orders returned (16664 observed)
FechaCreacion str    — timestamp the API generated this response, NOT an order date
Version       str    — API version tag, e.g. "v1"
Listado       array  — order stubs, shape shown above
```

## Detail envelope (top level, `?codigo=...`)

Same envelope shape as the list response: `Cantidad`, `FechaCreacion`,
`Version`, `Listado`. For a `codigo` query, `Cantidad` is 1 and `Listado`
has a single, fully populated order object. `parser.parse_detail` (Task 3)
reads `payload[schema.LIST_LISTADO]`, which works unchanged for both
envelope types.

Note: the top-level `FechaCreacion` here is the **API response** timestamp
(when this detail payload was generated), not the order's creation date —
see below.

## Order object (one entry of detail `Listado`)

Full observed key set: `CantidadEvaluacion`, `Cargos`, `Codigo`,
`CodigoEstado`, `CodigoEstadoProveedor`, `CodigoLicitacion`, `CodigoTipo`,
`Comprador`, `Descripcion`, `Descuentos`, `Estado`, `EstadoProveedor`,
`Fechas`, `Financiamiento`, `FormaPago`, `Impuestos`, `Items`, `Nombre`,
`Pais`, `PorcentajeIva`, `PromedioCalificacion`, `Proveedor`, `TieneItems`,
`Tipo`, `TipoDespacho`, `TipoMoneda`, `Total`, `TotalNeto`.

Fields used by `schema.py` today:

- `Codigo` (str) — order code, e.g. `"1002-211-SE26"`. Matches `schema.OC_CODIGO`.
- `Nombre` (str) — order title, e.g. `"EPP FUNC. OSORNO"`. Matches `schema.OC_NOMBRE`.
- `Comprador` (object) — buyer, see below. Matches `schema.OC_COMPRADOR`.
- `Items` (object) — line items container, see below. Matches `schema.OC_ITEMS`.

### Correction: order creation date is nested, not a flat field

The plan's original `schema.OC_FECHA = "FechaCreacion"` assumed the order
object has a direct `FechaCreacion` key. **It does not.** The order's own
creation date is nested one level down, under a `Fechas` object:

```json
"Fechas": {
  "FechaCreacion": "2026-06-08T10:35:20.823",
  "FechaEnvio": "2026-06-08T12:34:20.31",
  "FechaAceptacion": "2026-07-09T11:54:27.81",
  "FechaCancelacion": null,
  "FechaUltimaModificacion": "2026-06-11T16:34:00"
}
```

A direct `order["FechaCreacion"]` lookup returns nothing — that key name
only exists at the *envelope* top level (the API response timestamp, not
the order date), which is a different value entirely (observed:
`2026-07-12T14:25:20...` for the envelope vs `2026-06-08T10:35:20...` for
the order's actual `Fechas.FechaCreacion`).

**Fix applied in `schema.py`:** added `OC_FECHAS = "Fechas"` alongside the
existing `OC_FECHA = "FechaCreacion"` (the leaf key name is still correct,
it is the access path that changes). Any code that needs the order's
creation date must read `order[schema.OC_FECHAS][schema.OC_FECHA]`, not
`order[schema.OC_FECHA]`. This affects Task 3's `parser.parse_detail`,
which is not part of this task but should use the two-level path when
implemented.

## Comprador (buyer) object

Observed keys: `Actividad`, `CargoContacto`, `CodigoOrganismo`,
`CodigoUnidad`, `ComunaUnidad`, `DireccionUnidad`, `FonoContacto`,
`MailContacto`, `NombreContacto`, `NombreOrganismo`, `NombreUnidad`,
`Pais`, `RegionUnidad`, `RutUnidad`.

All four `schema.py` buyer constants matched the real payload exactly, no
corrections needed:

- `COMPRADOR_NOMBRE = "NombreOrganismo"` — matches.
- `COMPRADOR_CODIGO = "CodigoOrganismo"` — matches.
- `COMPRADOR_COMUNA = "ComunaUnidad"` — matches (observed value was `"* "`,
  a placeholder/blank-looking value for this particular order — worth
  treating comuna as potentially empty/dirty data downstream, not a schema
  problem).
- `COMPRADOR_REGION = "RegionUnidad"` — matches.

## Items container and line item

`Items` object: `{"Cantidad": int, "Listado": [...]}`. Matches
`schema.OC_ITEMS = "Items"` and `schema.ITEMS_LISTADO = "Listado"` exactly.

Each item in `Items.Listado` observed keys: `Cantidad`, `Categoria`,
`CodigoCategoria`, `CodigoProducto`, `Correlativo`, `EspecificacionComprador`,
`EspecificacionProveedor`, `Moneda`, `PrecioNeto`, `Producto`, `Total`,
`TotalCargos`, `TotalDescuentos`, `TotalImpuestos`, `Unidad`.

- `ITEM_PRODUCTO = "Producto"` — matches (e.g. `"Zapatos de hombre"`).
- `ITEM_CANTIDAD = "Cantidad"` — matches (float, e.g. `4.0`).
- `ITEM_PRECIO = "PrecioNeto"` — matches (float, e.g. `94788.0`).

## Summary of reconciliation

Of the 12 original constants in `schema.py`, 11 matched the real fixture
exactly with no changes. One (`OC_FECHA`) pointed to a key name that is
correct but nested one level deeper than assumed; fixed by adding a new
`OC_FECHAS` container constant rather than renaming `OC_FECHA`, so
downstream code composes `[OC_FECHAS][OC_FECHA]` to reach the real value.
