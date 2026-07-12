
# OC Parser Improvement Research

Date: 2026-07-12
Scope: `src/osint_mercado/parser.py`, `schema.py`, `models.py`, `store.py` — the Orden de Compra
(OC) detail parser shared by OSINT-Mercado (municipal overpricing watchdog) and the planned
mining-procurement data product.

This is a research report only. No source code was modified. Claims are cited; anything not
directly confirmed against a real Mercado Publico payload is explicitly marked
"to confirm against a real payload."

---

## 1. What the parser extracts today

Read directly from `src/osint_mercado/parser.py`, `schema.py`, `models.py`, `store.py` and
`docs/api/ordenes-de-compra-schema.md` (which documents a real captured fixture,
`tests/fixtures/oc_detail_sample.json`, captured 2026-07-12).

Per order, the parser keeps only:

- `Codigo`, `Nombre`
- `Fechas.FechaCreacion` (order creation date; note the code correctly reads it via the nested
  `Fechas` object, not the top-level envelope `FechaCreacion` which is the API response
  timestamp)
- `Comprador`: `NombreOrganismo`, `CodigoOrganismo`, `ComunaUnidad`, `RegionUnidad`
- `Items.Listado[]`: `Producto`, `Cantidad`, `PrecioNeto`

`store.py` then flattens this into a Polars items dataframe with columns:
`oc_id, buyer_name, buyer_code, comuna, region, fecha, product, quantity, unit_price, oc_url,
captured_at`.

Per the schema doc's real fixture capture, the **order object itself contains far more fields
than are read**: `CantidadEvaluacion`, `Cargos`, `CodigoEstado`, `CodigoEstadoProveedor`,
`CodigoLicitacion`, `CodigoTipo`, `Descripcion`, `Descuentos`, `Estado`, `EstadoProveedor`,
`Financiamiento`, `FormaPago`, `Impuestos`, `Pais`, `PorcentajeIva`, `PromedioCalificacion`,
`Proveedor`, `TieneItems`, `Tipo`, `TipoDespacho`, `TipoMoneda`, `Total`, `TotalNeto`. The
`Comprador` object also contains unread fields: `Actividad`, `CargoContacto`, `CodigoUnidad`,
`DireccionUnidad`, `FonoContacto`, `MailContacto`, `NombreContacto`, `RutUnidad`. Each line item
in `Items.Listado[]` contains unread fields: `Categoria`, `CodigoCategoria`, `CodigoProducto`,
`Correlativo`, `EspecificacionComprador`, `EspecificacionProveedor`, `Moneda`, `Total`,
`TotalCargos`, `TotalDescuentos`, `TotalImpuestos`, `Unidad`.

In short: the parser currently reads 4 of roughly 26 order-level fields and 3 of 14 item-level
fields that are actually present in the payload. Nothing about currency, tax, order status,
supplier identity, or product/category coding is captured today, even though the raw payload
already carries it.

---

## 2. Prioritized improvements

Improvements are grouped by what they add. For each: what to add, why it matters (anomaly
detection for OSINT-Mercado and/or reuse for the mining product), how to implement, rough
effort, and sources.

### 2.1 Currency and amount fields (Moneda/TipoMoneda, PrecioNeto vs Total, Impuestos, Cargos, Descuentos)

**What to add:** At the item level, capture `Moneda` (currency of that item's price) alongside
the existing `PrecioNeto`, plus `Total`, `TotalImpuestos`, `TotalCargos`, `TotalDescuentos`. At
the order level, capture `TipoMoneda`, `PorcentajeIva`, `Total`, `TotalNeto`, `Impuestos`,
`Cargos`, `Descuentos`.

**Why it matters:** Confirmed via a direct fetch of the official API documentation page
(`https://www.chilecompra.cl/api/`) that Mercado Publico purchase orders can be denominated in
five currency types: CLP, CLF (UF), USD, UTM, and EUR. Comparing `unit_price` across orders
without checking `Moneda`/`TipoMoneda` first will silently mix pesos with UF/USD/UTM amounts —
this is a correctness bug waiting to happen the moment a non-CLP order appears in the dataset,
and it would corrupt every downstream overpricing comparison. `PrecioNeto` is net-of-tax; the
order carries a separate `Total`/`TotalNeto` and `PorcentajeIva` (observed as a field in the real
fixture). Comparing an OC's `PrecioNeto` to a retail sticker price (which in Chile is legally
gross, IVA-included per SERNAC rules) without adjusting for the 19% IVA produces an apples-to-
oranges comparison that systematically understates OC prices relative to retail by ~19%. This
is confirmed generally: in Chile "el precio neto es el valor del producto o servicio antes de
agregar impuestos... el precio bruto incluye el IVA con una tasa del 19%" (retailbase.cl). For
the mining product, `Cargos`/`Descuentos`/`Fletes`-type adjustments matter even more because
mining OCs for freight-heavy commodities (reagents, spare parts) can have material freight/
discount line items relative to net price.

**How to implement:** Add `moneda`, `total`, `total_impuestos`, `total_cargos`,
`total_descuentos` to `LineItem`; add `tipo_moneda`, `porcentaje_iva`, `total`, `total_neto`,
`impuestos`, `cargos`, `descuentos` to `PurchaseOrder`. Add a currency-normalization step (see
2.2) before any cross-order comparison. Add new `schema.py` constants for all of the above,
matching the existing style (uppercase constant = literal JSON key).

**Effort:** Small (new field extraction, same pattern as existing fields) plus Medium for the
normalization logic in 2.2.

**Sources:**
- https://www.chilecompra.cl/api/ (official API page; directly lists currency types CLP/CLF/USD/UTM/EUR, purchase order type/status/payment/dispatch code tables — fetched and reproduced below in 2.3)
- `docs/api/ordenes-de-compra-schema.md` (real fixture, confirms `Impuestos`, `Cargos`, `Descuentos`, `PorcentajeIva`, `Total`, `TotalNeto` exist on the order; `Moneda`, `Total`, `TotalCargos`, `TotalDescuentos`, `TotalImpuestos` exist per item)
- https://www.retailbase.cl/blogs/impuestos/chile/diferencia-entre-precio-bruto-y-neto/ (net vs gross / IVA 19% definitions in Chile)
- http://www.chilecompra.cl/wp-content/uploads/2026/03/Documentacion-API-Mercado-Publico-oc.pdf (official data dictionary PDF; downloaded but not machine-text-extractable during this research — flagged as a follow-up in section 4)

### 2.2 Currency normalization to CLP (UTM, UF/CLF, USD, EUR)

**What to add:** A normalization utility that converts any `Moneda`/`TipoMoneda` value to CLP
using the order's `Fechas.FechaCreacion` (or `FechaEnvio`/`FechaAceptacion`, to confirm which
is most appropriate) as the as-of date for the exchange rate.

**Why it matters:** Directly required by 2.1 — without this, cross-order price comparison is
invalid whenever a non-CLP order appears. Both products need this: municipal orders occasionally
use UTM-denominated amounts (e.g., thresholds like "Purchase order under 3 UTM" are a documented
order *type*, code 6/"R1" — see 2.3 — implying UTM-scale orders exist), and mining orders are
more likely to include USD-denominated equipment/reagent purchases given global commodity
pricing.

**How to implement:** `mindicador.cl` is a free, no-API-key, open-source REST service replicating
Banco Central de Chile's official published values for UF, UTM, Dolar (observado), Euro, IPC,
IMACEC, TPM, and other indicators, with an endpoint pattern `https://mindicador.cl/api/{tipo}`
that returns historical daily/monthly series. This is the practical low-effort option for a
watchdog-scale project (no auth, JSON, historical lookups by date). For UF specifically, since it
compounds daily based on inflation, use the date-specific value, not a fixed constant. Cache
converted rates locally (e.g., a small on-disk table keyed by date+currency) to avoid a network
call per order at parse time — build this as a batch/pre-fetch step, not inline in
`parse_detail`, to keep the parser pure and testable. The Banco Central's own "Indicadores
diarios" database is the primary source mindicador.cl mirrors, and is the authoritative
fallback/cross-check if mindicador.cl availability is a concern.

**Effort:** Medium. This is a new module (`currency.py` or similar), not a parser change per se
— parser should keep raw values + currency code; normalization is a downstream concern to avoid
coupling the parser to network calls.

**Sources:**
- https://mindicador.cl/ (open, non-profit REST API for Chilean economic indicators, UF/UTM/Dolar/Euro, mirrors Banco Central de Chile values, no API key required)
- https://si3.bcentral.cl/Indicadoressiete/secure/Indicadoresdiarios.aspx (Banco Central de Chile's own daily indicators database, primary source)
- https://www.expat.cl/guide-chile/banking/uf-utm/ (UF adjusts daily with inflation; UTM is the "administrative equivalent," updated monthly)

### 2.3 Order status, type, and payment/dispatch codes (Estado/CodigoEstado, CodigoTipo, FormaPago, TipoDespacho)

**What to add:** `CodigoEstado`/`Estado`, `CodigoTipo`/`Tipo`, `CodigoEstadoProveedor`/
`EstadoProveedor`, `FormaPago`, `TipoDespacho`, `Financiamiento` at the order level.

**Why it matters:** This is the single highest-leverage correctness gap. The parser currently
has no way to know whether an order is cancelled, rejected, or still pending — meaning a
cancelled order (`Estado`/`CodigoEstado` = Cancelada) could currently be counted as a real,
completed purchase with a real price, directly poisoning any overpricing/anomaly statistic. The
official API page (fetched directly, `https://www.chilecompra.cl/api/`) documents this
enumerated status table for purchase orders:

| Estado | CodigoEstado |
|---|---|
| Enviada a Proveedor | 4 |
| En proceso | 5 |
| Aceptada | 6 |
| Cancelada | 9 |
| Recepción Conforme | 12 |
| Pendiente de Recepcionar | 13 |
| Recepcionada Parcialmente | 14 |
| Recepcion Conforme Incompleta | 15 |

and the order *type* table (`CodigoTipo`/`Tipo`), which is directly relevant to procurement-
mechanism analysis (Convenio Marco vs. direct/emergency/confidential purchase — mechanisms
with materially different price-competition dynamics):

| Codigo | Abrev. | Descripcion |
|---|---|---|
| 1 | OC | Automatica |
| 2 | D1 | Trato o contratación directa - proveedor único |
| 3 | C1 | Trato directo por emergencia, urgencia o imprevisto |
| 4 | F3 | Trato directo por confidencialidad |
| 5 | G1 | Trato directo por naturaleza de la negociación |
| 6 | R1 | Orden de compra menor a 3 UTM |
| 7 | CA | Orden de compra sin resolución |
| 8 | SE | Sin emisión automática |
| 9 | CM | Convenio Marco |
| 10 | FG | Trato Directo (Art. 8 f-g) |
| 12 | MC | Micro compra |
| 13 | AG | Compra ágil |
| 14 | CC | Compra coordinada |

(Note: this table was extracted by an automated fetch of the ChileCompra API page and should be
spot-checked against a handful of real orders before being hard-relied-upon — mark as
"to confirm against a real payload" for the exact code-to-CodigoTipo mapping, since WebFetch
summarization can occasionally mis-transcribe a table. The *existence* of `Estado`/`CodigoEstado`
and `Tipo`/`CodigoTipo` as real fields is independently confirmed by the raw fixture capture in
`docs/api/ordenes-de-compra-schema.md`.)

This directly matters for both products: OSINT-Mercado needs to filter out or flag cancelled/
rejected orders before computing any price-anomaly signal, and it needs `CodigoTipo` to
distinguish Convenio Marco (pre-negotiated catalog prices, lower expected variance) from Trato
Directo (single-supplier, no competition, higher overpricing risk) orders — these are different
statistical populations and should probably not be pooled naively. The mining product benefits
identically: CODELCO/ENAMI-adjacent municipal and public-agency spend will show the same
type/status distinctions.

**How to implement:** Add `codigo_estado`, `estado`, `codigo_tipo`, `tipo`,
`codigo_estado_proveedor`, `estado_proveedor`, `forma_pago`, `tipo_despacho`, `financiamiento` to
`PurchaseOrder`. Consider an `Enum` (Python `enum.IntEnum` or `StrEnum`) for `CodigoEstado` and
`CodigoTipo` once the code tables are confirmed against real payloads, so downstream filtering
reads as `order.codigo_estado == EstadoOC.CANCELADA` rather than a magic number. Add a filtering
helper (e.g., `is_active(order)` or similar) that callers can use to exclude cancelled/rejected
orders from aggregate statistics — but keep raw capture of all statuses in the parser itself, so
"what fraction of orders get cancelled" remains an analyzable signal in its own right (that ratio
is itself a candidate anomaly/quality-of-process indicator worth tracking per buyer).

**Effort:** Small for extraction; Small-Medium for the enum/status-table encoding once confirmed.

**Sources:**
- https://www.chilecompra.cl/api/ (fetched directly; source of the two tables above — verify against live payloads before hard-coding)
- `docs/api/ordenes-de-compra-schema.md` (confirms `Estado`, `CodigoEstado`, `CodigoTipo`, `Tipo`, `EstadoProveedor`, `CodigoEstadoProveedor`, `FormaPago`, `TipoDespacho`, `Financiamiento` are present in the real fixture)
- https://ayuda.mercadopublico.cl/preguntasfrecuentes/articulo/?id=KA-01944 (Guía para la Gestión de una Orden de Compra — describes lifecycle: emitida, enviada, aceptada, rechazada, cancelada)
- https://ayuda.mercadopublico.cl/preguntasfrecuentes/articulo/?id=KA-02011 (what happens when supplier does not accept the OC — rejection has consequences including seriedad-de-oferta guarantee execution, relevant context for why rejected/cancelled orders are not real transactions)

### 2.4 Supplier identity (Proveedor: RUT, name)

**What to add:** `Proveedor` object fields — at minimum RUT and name (exact field names to
confirm against a real payload; the schema doc lists `Proveedor` as present on the order but its
internal shape was not enumerated in the captured documentation excerpt read for this report).
The parallel `Comprador` object's `RutUnidad` field is already confirmed present but also unread.

**Why it matters:** This is a foundational anomaly-detection primitive missing entirely today.
Without supplier RUT, the codebase cannot compute supplier concentration (is one supplier
winning a suspicious share of a buyer's orders), cannot detect newly-registered shell suppliers
receiving large contracts (a pattern directly documented in Chilean investigative journalism —
CIPER Chile reported cases of companies registering with unrelated business lines days before
winning multi-million-peso pandemic contracts), and cannot join against the RUT-keyed supplier/
sanctions registries that ChileCompra's own "Observatorio" and "Cardinal" (Open Contracting
Partnership's open-source red-flags library) use for indicators like bidder-disqualification
history and beneficial-owner-is-official conflicts of interest. RUT is also the natural join key
for the mining product to link OC suppliers to SII business-registry or company-formation-date
data external to Mercado Publico.

**How to implement:** Add a `Supplier` dataclass mirroring `Buyer` (name, rut, code) to
`models.py`; parse `Proveedor` into it in `parser.py`; add `rut` to `Buyer` too (`RutUnidad`,
already confirmed present but unread). RUT should be normalized (strip dots/dashes to a canonical
`NNNNNNNN-D` or fully-stripped form) and optionally validated via the standard Chilean modulo-11
check-digit algorithm — multiplying digits by factors [2,3,4,5,6,7,2,3] from the right, an
invalid check digit on a RUT already present in upstream data is itself a data-quality signal
worth logging rather than silently dropping.

**Effort:** Small for extraction; Small for RUT normalization; Medium if check-digit validation
and canonicalization utilities are built out properly with tests.

**Sources:**
- `docs/api/ordenes-de-compra-schema.md` (confirms `Proveedor` object exists on the order; confirms `RutUnidad` exists on `Comprador`)
- https://www.ciperchile.cl/2021/01/23/sobreprecios-y-vinculos-familiares-en-compras-publicas-a-empresas-creadas-en-pandemia/ (documented cases of shell companies formed shortly before winning large public contracts — motivates supplier-age/concentration analysis)
- https://www.open-contracting.org/2024/06/12/cardinal-an-open-source-library-to-calculate-public-procurement-red-flags/ (Cardinal red-flag indicators R035/R036/R038 explicitly require bidder/tenderer identity plus disqualification status — RUT is the natural identity key)
- https://dev.to/fdograph/como-validar-un-rut-chileno-5335 and https://inflow.cl/blog/validacion-rut (RUT modulo-11 check-digit algorithm and normalization guidance)

### 2.5 Product/category classification codes (Categoria, CodigoCategoria, CodigoProducto — UNSPSC)

**What to add:** `Categoria`, `CodigoCategoria`, `CodigoProducto` per line item.

**Why it matters:** Today, `product` is a free-text string (`"Zapatos de hombre"` per the real
fixture example). Free text cannot be reliably matched to a controlled basket of goods for price
comparison — "Zapatos de hombre" vs. "Calzado de seguridad" vs. "Zapato industrial" may all refer
to comparable products but will never string-match. `CodigoCategoria`/`CodigoProducto` are (per
multiple independent sources) derived from UNSPSC (Código Estándar de Productos y Servicios de
Naciones Unidas), a hierarchical 8-digit code — Segment (2 digits) / Family (4 digits) / Class
(6 digits) / Commodity (8 digits) — used across Latin American public-procurement systems,
including explicit confirmation that Mercado Publico's "rubro" classification derives from UNSPSC
Level 3/4 ("Class"). This is the single most valuable structural field for matching OC line items
to a controlled basket: category code equality is a hard, language-independent join key, whereas
free-text product-name matching requires fuzzy NLP with much higher false-positive/negative risk.
For the mining product specifically, UNSPSC has known segment/class codes for mining-relevant
goods (explosives sit under UNSPSC class 1213 within the Chemicals/Gas Materials segment 12, per
public UNSPSC references), so `CodigoCategoria`/`CodigoProducto` on mining-adjacent municipal or
public-agency orders would let the product filter to mining-relevant spend categories without
text matching.

**How to implement:** Add `category`, `category_code`, `product_code` to `LineItem`. Build (or
source) a UNSPSC code-to-description lookup table for enrichment/human-readable category display
— UNGM (https://www.ungm.org/public/unspsc) publishes the canonical list; several public mirrors
exist. Use `CodigoCategoria`/`CodigoProducto` as the primary join key for "same product across
different orders/buyers" comparisons, falling back to free-text similarity only when codes are
missing or too coarse.

**Effort:** Small for extraction; Medium for building/sourcing the UNSPSC lookup table and
category-based basket-matching logic.

**Sources:**
- `docs/api/ordenes-de-compra-schema.md` (confirms `Categoria`, `CodigoCategoria`, `CodigoProducto` present per line item in the real fixture)
- https://www.licita360.com/post/codigos-onu-mercado-publico ("Lo que debes saber sobre Códigos ONU en el Mercado Público" — confirms Mercado Publico's rubro/category classification is UNSPSC-derived)
- https://wisepim.com/guides/product-taxonomy/unspsc and https://www.doa.nc.gov/documents/commodity-codes/unspsc-commodity-codes/open (UNSPSC 4-level Segment/Family/Class/Commodity hierarchy, worked example)
- https://www.ungm.org/public/unspsc (canonical UNSPSC code list, UN Global Marketplace)
- (to confirm against a real payload) exact UNSPSC segment/class for mining-specific goods relevant to the second product — general UNSPSC mining-segment references (segment 20000000, "Mining, Oil, Gas and Utility Services") and explosives (class ~1213) were found via general UNSPSC documentation, not verified against actual Mercado Publico mining-adjacent OC line items

### 2.6 Unit of measure (Unidad)

**What to add:** `Unidad` per line item.

**Why it matters:** `unit_price` today is computed purely from `PrecioNeto` divided implicitly
by whatever `Cantidad` means for that line — but if `Cantidad` counts packs, cases, or boxes
rather than individual units, `unit_price` is not comparable across orders that specify the same
product in different pack sizes. This is a well-documented general procurement pitfall: unit
price comparison requires normalizing to a common base unit ("12 x 330 ml" vs. a single-unit
price are not directly comparable without expanding the multipack), and vendors/buyers reporting
in inconsistent units is called out generally as a source of "pack size chaos" that breaks price
comparison. Without `Unidad`, an OSINT-Mercado anomaly score could flag a per-box price as
wildly cheap or wildly expensive relative to a per-unit retail baseline purely due to unit
mismatch, producing false positives that undermine the watchdog's credibility.

**How to implement:** Add `unit` (string) to `LineItem`, capturing `Unidad` verbatim. Treat
unit-normalization as a separate, later enrichment step (likely joined against the UNSPSC/
category code from 2.5, since expected unit varies by product type) rather than something the
parser itself computes — the parser's job is to preserve the raw signal faithfully, not to
infer conversion factors.

**Effort:** Small for extraction. Medium-Large for a genuine unit-normalization layer (out of
scope for the parser itself, but worth flagging as a downstream dependency this field unlocks).

**Sources:**
- `docs/api/ordenes-de-compra-schema.md` (confirms `Unidad` present per line item in the real fixture)
- https://ficstar.medium.com/pack-size-chaos-why-competitor-price-comparison-fails-without-unit-normalization-1c24eac7004e (pack-size/unit normalization is required for valid price comparison; multipack expansion process described)
- https://dataweave.com/blog/why-unit-of-measure-normalization-is-critical-for-accurate-and-actionable-competitive-pricing-intelligence (unit-of-measure normalization framed as critical for pricing intelligence specifically)

### 2.7 Order dates beyond creation (Fechas: FechaEnvio, FechaAceptacion, FechaCancelacion, FechaUltimaModificacion)

**What to add:** The remaining `Fechas` sub-fields already visible in the real fixture:
`FechaEnvio`, `FechaAceptacion`, `FechaCancelacion`, `FechaUltimaModificacion`.

**Why it matters:** `FechaCancelacion` (non-null) is a direct, cheap corroborating signal for
order status (2.3) — it tells you *when* an order was cancelled, which combined with
`FechaCreacion` gives a time-to-cancellation metric that could itself be a red flag (orders
cancelled suspiciously fast, or very slow acceptance times, are the kind of timeline-based signal
the OCP red-flags literature repeatedly uses — e.g., compressed submission periods as a collusion
indicator R003). `FechaUltimaModificacion` is useful for detecting whether an order was amended
after initial issuance, a weaker proxy for the "enmiendas" (amendments) signal the user's brief
asked about — Mercado Publico's OC API does not appear to expose a distinct amendment-history
object per this research (not confirmed in either the real fixture's key list or the API docs
found), so `FechaUltimaModificacion` != `FechaCreacion` may be the best available proxy for "this
order changed after issuance" until a real payload with an actual amendment is inspected.

**How to implement:** Add `fecha_envio`, `fecha_aceptacion`, `fecha_cancelacion`,
`fecha_ultima_modificacion` to `PurchaseOrder`, all as raw strings (matching the existing
`fecha: str` convention — do not silently coerce to `datetime` in the parser layer, keep parsing
permissive per the project's existing dataclass style, push type coercion to a later stage if
needed).

**Effort:** Small — same pattern as the existing `_parse_fecha` helper, generalized to pull all
five `Fechas` keys instead of one.

**Sources:**
- `docs/api/ordenes-de-compra-schema.md` (verbatim real `Fechas` object with all five keys shown, including a null `FechaCancelacion` example)
- https://www.open-contracting.org/wp-content/uploads/2024/12/OCP2024-RedFlagProcurement-1.pdf and https://www.open-contracting.org/2024/06/12/cardinal-an-open-source-library-to-calculate-public-procurement-red-flags/ (submission-period/timing-based red flags such as R003 and R030 rely on comparable date fields)
- (to confirm against a real payload) whether any Mercado Publico OC ever actually carries a non-null `FechaCancelacion` or a genuinely amended history, and whether a distinct "enmienda" object exists anywhere in the API that this research did not surface

### 2.8 OCDS field mapping as a longer-term enrichment layer

**What to add:** Not a parser change per se, but a documented mapping from the current internal
model to OCDS's five blocks (planning, tender, award, contract, implementation), to be revisited
once ChileCompra's own OCDS bulk exports are evaluated as a possible parallel/alternate data
source.

**Why it matters:** ChileCompra already publishes an OCDS-standard export covering Licitación,
Trato Directo, and Convenio Marco processes (explicitly **excluding** "Compra Ágil" and public
companies/war-material procurement) — confirmed via the Open Contracting Partnership's own data
registry entry for Chile, which documents Jan 2022–May 2026 coverage with tender/award/contract/
document blocks, but a known data-quality caveat: "Some awards have multiple suppliers, but a
single contract is associated with the award," making individual-supplier-level value attribution
unreliable in that particular export. This matters because it tells us the OCDS bulk export is
not a drop-in replacement for the OC-detail API this parser already targets — the OC API is
order-level (already the right granularity for a per-transaction price signal), while the OCDS
export is tender/award-level and has documented supplier-attribution ambiguity. The practical
recommendation is to treat OCDS as a secondary enrichment source (e.g., joining an OC back to its
originating `CodigoLicitacion` — already present in the fixture's order-level field list — to
pull in tender-level context like number of bidders, which the OC-detail payload itself does not
carry) rather than a replacement for the current OC-detail parsing approach.

**How to implement:** No parser change now. Document the mapping as a design note; consider a
follow-up ADR if/when OCDS enrichment is actually implemented, since it is an architecturally
significant decision (new data source, new join key `CodigoLicitacion`, new failure modes).

**Effort:** Research/documentation only for now (Small); Large if actually implemented as a data
source.

**Sources:**
- https://data.open-contracting.org/en/publication/144 (OCP's own registry entry for Chile's ChileCompra OCDS publication — coverage dates, block counts, and the multi-supplier/single-contract caveat, fetched directly)
- https://www.open-contracting.org/what-is-open-contracting/e-procurement/ and https://standard.open-contracting.org/latest/en/primer/how/ (OCDS block structure: planning, tender, awards, contracts, implementation)
- https://developmentgateway.org/blog/como-utilizar-estandares-internacionales-para-mejorar-los-datos-abiertos-de-compras-y-contrataciones-publicas-el-caso-de-chilecompra/ (Development Gateway's 2017 consulting engagement mapping ChileCompra fields to OCDS blocks — found coverage "high" across the five OCDS blocks)
- `docs/api/ordenes-de-compra-schema.md` (confirms `CodigoLicitacion` exists on the order object, the natural join key back to tender-level OCDS data)

### 2.9 Robustness of parsing itself: validation library choice

**What to add:** Not new fields, but a recommendation on how the *parsing layer itself* should
evolve as field count grows from ~7 to ~25+.

**Why it matters:** The current parser is entirely manual (`dict.get()` chains with a
`_to_float` helper for defensive coercion) using plain `dataclasses` for the output models. This
works fine at today's field count but will become harder to maintain and easier to silently
break (e.g., a renamed upstream key just returns an empty string/0.0 instead of raising) as field
count roughly quadruples per the improvements above. Two credible options were researched:

- **pydantic v2**: full validation framework, ~10-20x faster than pydantic v1 but still slower
  than msgspec; strong ecosystem, good error messages, widely known.
- **msgspec**: a Rust-backed struct/validation library, benchmarked as 2-5x faster than pydantic
  v2 for decode/validate, ~10-80x faster than plain json+manual validation for supported types,
  and specifically able to decode directly into a schema so unused fields are dropped without
  ever materializing full Python objects for them — relevant given Mercado Publico payloads carry
  many fields the codebase may still choose not to keep. msgspec's validation is strict by
  default (no silent type coercion), which is a double-edged sword for "messy" government JSON:
  it will loudly fail on the field-level type inconsistencies this codebase currently coerces
  away silently via `_to_float`.

Given that this codebase is presently choosing defensive, always-degrade-to-empty-string/0.0
parsing (arguably the right call for a watchdog tool ingesting a big daily volume of variably-
messy government JSON, where a single malformed order should not crash a whole day's ingest),
**pydantic v2 with `Optional[...] = default` fields and a top-level `try/except ValidationError`
per-order (log and skip, don't crash the batch)** is the better fit than msgspec's strict-by-
default posture, despite being slower — correctness-under-partial-failure matters more than raw
throughput at this data volume (single-digit-thousands of orders per day, not millions). If
ingest volume becomes the actual bottleneck later (e.g., backfilling years of historical data),
msgspec becomes worth revisiting specifically for the bulk/backfill path, potentially as a second,
narrower "fast path" parser used only for historical batch loads, while pydantic (or the current
manual approach) stays as a "slow but forgiving" path for live daily ingest.

**How to implement:** Not urgent — the current manual/dataclass approach is not broken at 7
fields, and this recommendation is explicitly to revisit once the field count from 2.1-2.7 lands.
If/when adopted: define `PurchaseOrder`/`LineItem`/`Buyer`/`Supplier` as pydantic `BaseModel`
subclasses with `Optional[X] = None` or typed defaults for every field (mirroring the current
"never raise, always return something" philosophy), keep `schema.py`'s field-name constants as
the aliasing source (`Field(alias=schema.OC_CODIGO)`), and add one `model_validate` call per
order inside a try/except in `parse_detail`.

**Effort:** Medium-Large if migrated (touches parser, schema, models, and all consuming tests).
Not recommended as an immediate task — flagged as a "when field count grows" trigger, not a
now-action.

**Sources:**
- https://hrekov.com/blog/msgspec-vs-pydantic-v2-benchmark and https://gist.github.com/jcrist/d62f450594164d284fbea957fd48b743 (msgspec vs pydantic v2 benchmarks, 2-5x range)
- https://github.com/msgspec/msgspec and https://pythonspeed.com/articles/faster-python-json-parsing/ (msgspec's schema-driven decode-only-what-you-need behavior, strict-by-default validation)
- https://skaaptjop.medium.com/how-i-use-pydantic-unrequired-fields-so-that-the-schema-works-0010d8758072 and https://pydantic.dev/docs/validation/latest/concepts/json/ (pydantic v2 patterns for optional/missing-field-tolerant parsing of third-party JSON)

### 2.10 Data-quality guardrails specific to Mercado Publico

**What to add:** Defensive checks/flags (not necessarily new fields) informed by documented
data-quality issues:

- **Negative-value orders.** ChileCompra's own open-data documentation notes that some purchase
  orders carry negative values, which agencies incorrectly issue to formalize discounts — this
  is "inappropriate for public purchases" per ChileCompra's own characterization, but it exists
  in the live data. The parser (or a validation layer just above it) should flag, not silently
  accept, negative `PrecioNeto`/`Total` values, since a naive overpricing detector could otherwise
  treat a large negative "discount order" as an enormous outlier price signal in either direction.
- **Self-declared, unverified data.** ChileCompra explicitly disclaims responsibility for data
  accuracy — figures are "self-declared estimates by platform users," meaning buyer/supplier data
  entry errors (typos in quantity, wrong category code, etc.) are expected background noise, not
  edge cases. This supports treating any single-order anomaly signal as a hypothesis to
  corroborate (e.g., cross-check against multiple orders for the same product/buyer) rather than
  a standalone accusation — relevant to how OSINT-Mercado should frame findings, not just to the
  parser.
- **`Compra Ágil` exclusion from the OC API.** ChileCompra has publicly confirmed (via their own
  X/Twitter support account, cited by search results) that the API does not currently expose
  Compra Ágil (quick-purchase, sub-100-UTM, quotation-based) transactions — those are only
  available via CSV bulk download on the Datos Abiertos site, not the `ordenesdecompra` JSON API
  this parser targets. This is a coverage gap worth documenting explicitly: today's data pipeline
  is structurally blind to an entire class of small-value purchases, which for a municipal
  watchdog product could be significant, since Compra Ágil is exactly the mechanism most likely
  to be used for small, frequent, harder-to-scrutinize purchases.
- **Encoding.** No Mercado Publico-specific encoding bug was found in this research, but
  UTF-8-misread-as-Latin-1 mojibake (garbled tildes/ñ) is the generically most common failure
  mode for Latin American government APIs and is cheap to guard against — ensure all HTTP fetch
  and file-write paths explicitly declare `encoding="utf-8"` end to end (not implicitly inherited
  from OS locale, which on Windows defaults to something other than UTF-8) and add this to code
  review checklist rather than the parser itself. Flagged as unconfirmed for this specific API but
  worth a defensive check against the real fixture's raw bytes.

**Why it matters:** These are correctness/trust issues, not feature gaps — for a watchdog tool
whose entire value proposition is credible anomaly-flagging, a false positive caused by an
unflagged negative-value "discount order" or an encoding artifact is reputationally worse than a
missed true positive.

**How to implement:** Add validation warnings (log, don't raise) in `parse_detail` or a thin
wrapper around it for: `PrecioNeto < 0`, `Cantidad <= 0`, `Total` disagreeing with
`PrecioNeto * Cantidad` beyond a tolerance (once `Cargos`/`Descuentos`/`Impuestos` from 2.1 are
available to explain the difference legitimately). Document the Compra Ágil coverage gap in
`docs/api/ordenes-de-compra-schema.md` itself so future readers of that doc know the boundary of
what the OC API can see.

**Effort:** Small (mostly logging/documentation, not new parsing logic).

**Sources:**
- https://www.alejandrobarros.com/chilecompra-y-sus-problemas-con-los-datos-abiertos/ (ChileCompra open-data quality/transparency critique; general context, no specific encoding/duplicate finding confirmed in this piece)
- https://x.com/ChileCompra/status/1891814279378092319 (ChileCompra's own support account confirming Compra Ágil is not available via the API, only via CSV download on Datos Abiertos)
- https://www.ciperchile.cl/2021/01/23/sobreprecios-y-vinculos-familiares-en-compras-publicas-a-empresas-creadas-en-pandemia/ (self-declared/unverified nature of procurement data and shell-company patterns, motivating a "corroborate, don't accuse from one row" posture)
- (paraphrased from search-engine-summarized ChileCompra open-data documentation; original page not independently re-fetched in full for exact wording — mark the "negative value orders" and "self-declared estimates" characterizations as to confirm against ChileCompra's own datos-abiertos documentation pages directly, e.g. https://datos-abiertos.chilecompra.cl/ and https://datos-abiertos.chilecompra.cl/datos-abiertos/definiciones)

---

## 3. Highest-leverage next 3

1. **Order status/type filtering (2.3) — `CodigoEstado`, `CodigoTipo`.** Cheapest to implement
   (same extraction pattern as existing fields) and fixes a correctness bug that exists right
   now: cancelled/rejected orders are currently indistinguishable from completed ones, meaning
   every anomaly statistic computed today may already include phantom transactions with no real
   price. This is the one change most likely to change existing output, not just add new
   capability.

2. **Currency + net/gross normalization (2.1 + 2.2) — `Moneda`/`TipoMoneda`, `PorcentajeIva`,
   plus a `mindicador.cl`-backed CLP conversion utility.** Second cheapest, and the second
   correctness bug: any price comparison today silently assumes everything is CLP and net-of-tax,
   which is false for at least UTM-scale and (plausibly, for mining) USD-scale orders, and always
   understates OC prices ~19% relative to any gross retail baseline.

3. **Category codes (2.5) — `CodigoCategoria`/`CodigoProducto` (UNSPSC).** Highest strategic
   value for both products: this is the field that turns "compare free-text product names" (weak,
   language-dependent, high false-positive risk) into "compare identical UNSPSC codes" (strong,
   language-independent join key), and it is the same field the mining product would use to
   filter to mining-relevant spend without any text heuristics at all.

---

## 4. Open questions to confirm against a real payload

- Exact shape of the `Proveedor` object (RUT field name, whether it matches `RutUnidad`'s naming
  convention or differs) — not enumerated in the schema doc excerpt read for this report.
- Exact numeric-to-label mapping for `CodigoTipo` (order type codes 1-14 listed in section 2.3)
  and `CodigoEstado` (status codes 4-15) — sourced from an automated WebFetch summary of
  `https://www.chilecompra.cl/api/`, not manually cross-checked against several live orders of
  known status. Recommend pulling ~20 real orders across different known states/types and
  confirming the code table before hard-coding an enum.
  Immediate spot-check the parser/schema author can do without another web fetch: the *existing*
  captured fixture (`tests/fixtures/oc_detail_sample.json`) already has real `CodigoEstado` and
  `CodigoTipo` values recorded — reading that file directly would confirm at least one row of the
  table for free.
- Whether `PrecioNeto * Cantidad` reconciles with the item's `Total` field once `TotalImpuestos`/
  `TotalCargos`/`TotalDescuentos` are accounted for, and whether the tolerance for disagreement
  reveals additional undocumented fee types.
- Whether any real order in practice carries a non-CLP `Moneda`/`TipoMoneda` (UF, USD, UTM, EUR)
  — the code table's existence was confirmed from the API's own documentation, but this parser's
  own captured fixture only shows one example order and its currency was not stated in the schema
  doc excerpt read for this report.
- Whether Mercado Publico's OC-detail API exposes any distinct amendment/`enmienda` history
  object beyond the `FechaUltimaModificacion` proxy discussed in 2.7 — not found in either the
  real fixture's field list or the official API documentation pages fetched during this research;
  may simply not exist at the OC-detail level (amendments might live at the tender/`Licitacion`
  level instead, reachable via `CodigoLicitacion`).
- Whether the `Compra Ágil` API-coverage gap (section 2.10) is still current as of this
  research date — the confirming source is a 2026-dated public support reply on X/Twitter, which
  is reasonably fresh but worth a direct confirmation against `datos-abiertos.chilecompra.cl`
  documentation before being treated as permanent architecture.
- CODELCO/ENAMI-specific procurement: confirmed that CODELCO runs its own SAP Ariba-based supplier
  portal for its bidding/tender process (separate from Mercado Publico), meaning CODELCO's own
  primary procurement is **not** expected to appear in the Mercado Publico OC API at all. What was
  not confirmed: whether CODELCO or ENAMI, as state-owned enterprises, still appear as *buyers*
  (`Comprador.CodigoOrganismo`) for any subset of purchases channeled through Mercado Publico
  (e.g., smaller/administrative purchases not run through Ariba), or whether they are entirely
  absent from this data source. This materially affects the mining-product's scoping and should
  be checked directly against the API (e.g., search `CodigoOrganismo` for known CODELCO/ENAMI
  organism codes) before assuming Mercado Publico is a viable primary data source for CODELCO/
  ENAMI-specific mining procurement analysis — municipal/regional-government mining-adjacent
  spend (e.g., royalty-funded municipal purchases in Calama, Antofagasta) remains reachable via
  Mercado Publico regardless of this question, and CIPER Chile has already reported on
  transparency gaps in how mining-royalty funds are spent by beneficiary municipalities, which is
  a promising angle independent of CODELCO/ENAMI's own procurement channel.
- Exact content of the official data dictionary PDF
  (`http://www.chilecompra.cl/wp-content/uploads/2026/03/Documentacion-API-Mercado-Publico-oc.pdf`)
  — downloaded successfully (340KB) but not machine-text-extractable via the tools available in
  this research session (returned binary/compressed stream rather than parseable text). This PDF
  is very likely the single best remaining source for exact field types and enumerated values and
  should be opened manually (e.g., in a PDF reader, or re-attempted with a PDF-text-extraction
  tool) as a priority follow-up before finalizing any new `schema.py` constants.
