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
- `CodigoEstado` (int, observed `6`) / `Estado` (str, observed `"Aceptada"`) — order
  status. Matches `schema.OC_CODIGO_ESTADO`/`schema.OC_ESTADO`. Only `CodigoEstado == 9`
  ("Cancelada", per the official status table at `https://www.chilecompra.cl/api/`) is
  currently acted on, by `order_status.drop_cancelled`; the pipeline has never observed
  a real order with a status other than `6` to confirm the rest of the table against.
- `CodigoTipo` (str, observed `"8"` — a JSON string, not an int) / `Tipo` (str, observed
  `"SE"`) — order type. Matches `schema.OC_CODIGO_TIPO`/`schema.OC_TIPO`. Not currently
  used for filtering, only stored for future analysis (Convenio Marco vs. Trato Directo).
- `CodigoEstadoProveedor` (int, observed `4`) / `EstadoProveedor` (str, observed
  `"Aceptada"`) — supplier-side acceptance status. Matches
  `schema.OC_CODIGO_ESTADO_PROVEEDOR`/`schema.OC_ESTADO_PROVEEDOR`. **Open question:**
  no real fixture example of a rejected order exists yet to confirm whether this field
  (rather than `CodigoEstado`) is where order rejection actually surfaces — the
  official `CodigoEstado` table has no distinct "Rechazada" value. Revisit once a
  rejected-order payload is captured.
- `TipoMoneda` (str, observed `"CLP"`), `PorcentajeIva` (float, observed `19.0`),
  `Total` (float, observed `539041.0`), `TotalNeto` (float, observed `452976.0`),
  `Impuestos` (float, observed `86065.0`), `Cargos` (float, observed `0.0`),
  `Descuentos` (float, observed `0.0`) — order-level currency/tax. Matches
  `schema.OC_TIPO_MONEDA`, `schema.OC_PORCENTAJE_IVA`, `schema.OC_TOTAL`,
  `schema.OC_TOTAL_NETO`, `schema.OC_IMPUESTOS`, `schema.OC_CARGOS`,
  `schema.OC_DESCUENTOS`. Captured raw only — no CLP conversion yet, see ADR 0009.

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
- `ITEM_MONEDA = "Moneda"` — matches (str, observed `"CLP"`).
- `ITEM_TOTAL = "Total"` — matches (float, observed `379152.0` for the first item;
  note this collides in name with the order-level `Total` field — the flattened
  Parquet output (`store.py`) disambiguates as `order_total` vs. `total`).
- `ITEM_TOTAL_CARGOS = "TotalCargos"`, `ITEM_TOTAL_DESCUENTOS = "TotalDescuentos"`,
  `ITEM_TOTAL_IMPUESTOS = "TotalImpuestos"` — match (float, all observed `0.0` for this
  order's items).
- `ITEM_CATEGORIA = "Categoria"` — matches (str, observed
  `"Ropa, maletas y productos de aseo personal / Calzado / Zapatos"`).
- `ITEM_CODIGO_CATEGORIA = "CodigoCategoria"` — matches (int, observed `53111600`, a
  UNSPSC class-level code).
- `ITEM_CODIGO_PRODUCTO = "CodigoProducto"` — matches (int, observed `53111601`, a
  UNSPSC commodity-level code).

## Summary of reconciliation

Of the 12 original constants in `schema.py`, 11 matched the real fixture
exactly with no changes. One (`OC_FECHA`) pointed to a key name that is
correct but nested one level deeper than assumed; fixed by adding a new
`OC_FECHAS` container constant rather than renaming `OC_FECHA`, so
downstream code composes `[OC_FECHAS][OC_FECHA]` to reach the real value.
