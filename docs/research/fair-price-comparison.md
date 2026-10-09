# Fair price comparison: is "price paid vs retail" a fair test of overpricing?

Research study for OSINT-Mercado. The question is whether the current comparison between a
municipal unit price and a retail reference price is economically fair, which legitimate effects
can separate the two, how large those effects plausibly are, and what adjustments would make a
flag defensible as evidence of overpricing. Nothing here is decided. Section 4 lists candidate
decisions for Felipe. Section 5 lists the questions only he can answer.

Conventions: every external figure carries its URL. Figures computed for this study from the
project's own data are marked "computed here" and name the file they come from. Where no evidence
for an effect's size was found, the effect is marked unquantified. Statistics are median / MAD /
IQR only, per the project rule. This document cites laws only as sources of fact and does not
interpret them.

---

## 1. How the comparison works today

### 1.1 Retail-basket engine (the engine that produced all 4 published flags)

1. **Currency.** The OC unit price is converted to CLP at the order's own date via mindicador
   (`src/osint_mercado/fx.py:60-71`, rate lookup with weekend backfill at `fx.py:33-57`;
   `scoring.py:119`).
2. **IVA.** The OC price is net (`PrecioNeto`), so it is grossed up with the order-level
   `PorcentajeIva`: `gross = net * (1 + iva/100)` (`scoring.py:61-63`, applied at `scoring.py:120`;
   rationale in ADR 0011). The retail baseline is assumed to be a gross shelf price. No per-source
   check that a retail price really is gross exists in the code or the seed data.
3. **Unit normalization.** A divisor from the free-text spec rescales pack counts and sizes
   (`scoring.py:81-102`, parsers in `units.py:42-54` and `units.py:96-110`). It can only lower a
   ratio (`units.py:10-13`). Small formats below half the base size are routed to review
   (`scoring.py:34`, `scoring.py:146-150`).
4. **Reference price.** The median of the seed observations for the SKU
   (`baseline.py:20-26`, `baseline.py:35-36`). Confidence is `high` only with at least 2
   observations and a spread `(max-min)/median <= 0.25`; everything else that is fresh is `medium`,
   **including a single observation** (`baseline.py:43-48`). Both `medium` and `high` are scorable
   (`scoring.py:29`, `scoring.py:137-142`).
5. **Freshness.** Measured against the date the baselines are built (`build_baselines.py:47`,
   `date.today()`), not against the order date (`baseline.py:37-43`, 90-day window at
   `baseline.py:6`). The seed observations behind the 4 flags were taken 12-13 July; the orders
   are dated 25 June to 8 July.
6. **Ratio and tiers.** `ratio = normalized gross OC price / reference` (`scoring.py:144`). Watch
   >= 1.5, High >= 2.0, Severe >= 3.0 (`scoring.py:18-20`, `scoring.py:66-73`). Ratios below 0.3 or
   above 20 are routed to `unit_ambiguous` (`scoring.py:25-26`, `scoring.py:147`).
7. **What is not modelled at all:** order quantity or order size, delivery or installation bundled
   in the unit price, the payment term, the procurement mechanism (`codigo_tipo`: Compra Agil,
   Convenio Marco, order from a licitacion), the commune, the brand or tier named in the spec, and
   the time gap between the order and the retail observation.

### 1.2 Peer engine (ADR 0018)

Groups gross CLP prices by UNSPSC product code, needs `MIN_PEERS = 5` (`peers.py:22`), and flags a
line when it is both robustly extreme (robust z >= 3.5, `peers.py:25`, `peers.py:54-57`) and at
least 1.5x the peer median, capped at 12x (`peers.py:26-30`, `peers.py:99-116`). Peers share a
UNSPSC code, not a product, so a peer median can mix very different goods.

### 1.3 SoloTodo retail source (ADR 0022)

Takes the store's `offer_price` before `normal_price` (`solotodo.py:32`), then the median across
offers (`solotodo.py:49-56`). An offer price can be a promotional or payment-method price, so it
leans the reference down. It did not anchor any of the 4 published flags; a query for 16 GB
pendrives returns no confident match (computed here, live call through `solotodo.retail_quote`).

### 1.4 Convenio Marco engine (ADR 0024)

Net-to-net against the median of same-product CM rows in METROPOLITANA + NACIONAL
(`cm_scoring.py:12-15`, `cm_scoring.py:196`), with at least 3 references (`cm_scoring.py:28`),
2 shared distinctive tokens (`cm_scoring.py:32-33`) and a [1.5x, 15x] band
(`cm_scoring.py:38-39`). It never auto-publishes.

### 1.5 Like-for-like verdict on today's design

| Dimension | Retail engine | Like with like? |
|---|---|---|
| Currency | Converted at order date | Yes |
| IVA | OC grossed up; retail assumed gross | Yes if every retail source is gross; not verified per source |
| Pack / size | Spec-parsed divisor | Partly; it can only lower ratios, which is the safe direction |
| Brand / tier / spec grade | Not compared | No |
| Quantity / order size | Not compared | No |
| Delivery to the municipality | Included in the OC price, excluded from the shelf price | No |
| Payment term | OC carries it, shelf price is paid on the spot | No |
| Mechanism (CM / Compra Agil / licitacion) | Ignored | No |
| Time | Retail observed after the order, freshness tied to build date | Approximately |

---

## 2. Effects that can separate a public unit price from a retail shelf price

Each entry gives the mechanism, the evidence, the plausible size (or "unquantified") and whether
the pipeline already accounts for it.

### 2.1 IVA (19%), gross vs net

- **Mechanism.** The OC line price (`PrecioNeto`) is net of IVA. Chilean consumer law requires an
  advertised price to include taxes: "El monto del precio deberá comprender el valor total del bien
  o servicio, incluidos los impuestos correspondientes" (Ley 19.496, art. 30, as published by
  SERNAC: https://sernac.cl/portal/609/w3-propertyvalue-58774.html). Convenio Marco store prices are
  net (a university purchasing guide: "los valores del portal se encuentran en neto",
  https://dicyt.usach.cl/wp-content/uploads/2021/10/7-Instructivo-Gestión-Compras.pdf; the project
  also confirmed it empirically, ADR 0024).
- **Size.** Exactly a factor of 1.19 when the two sides are on different bases.
- **Pipeline.** Handled correctly in principle: retail engine grosses the OC up (`scoring.py:120`),
  CM engine is net-to-net. **Gap:** nothing verifies that each seed retail price is gross. A shop
  selling mainly to businesses can show net prices. The pendrive baseline rests on one price from
  Alcaplus; its page returned HTTP 403 to every fetch for this study, so its IVA basis could not be
  confirmed. If that price were net, the Buin ratio would fall from 2.76x to 2.32x (computed here:
  9,282 / (3,368 x 1.19)). The other seed sources were not individually checked either, except
  ferreteria.cl, whose Stanley PowerLock page states "$12.990, con IVA incluido"
  (https://ferreteria.cl/ficha/5170/huincha-de-medir-stanley-powerlock-5-metros).

### 2.2 Quantity and bundle effects

- **Mechanism.** Larger orders usually earn lower unit prices, and very small orders carry fixed
  costs spread over few units. Within one multi-line order a supplier can also spread margin
  unevenly across lines, so a single line can look expensive while the order as a whole does not.
- **Evidence.** An Italian study proposes the elasticity of unit price to quantity as a spending
  review indicator for standardized goods and estimates savings of about 17% of spending in
  medical devices (De Leverano and Baulia, ZEW DP 23-063,
  https://www.zew.de/publikationen/a-new-indicator-to-implement-effective-spending-review-policies-in-the-public-procurement-for-standardized-goods).
  No Chilean estimate of the quantity elasticity was found.
- **Project data (computed here, `data/oc_items_*.parquet`).** The Buin order 2721-217-AG26 has ten
  lines from one supplier. The pendrive line is 2.76x the baseline, but the same order sells AAA and
  AA batteries at 350 CLP net each, against baselines of 4,740 and 3,790 CLP per blister of four.
  Across the three basket-matched lines the order totals 140,539 CLP gross against 118,616 CLP at
  baseline prices, a ratio of about 1.18x, assuming the battery lines are priced per single cell
  (the spec does not say).
- **Size.** Unquantified for Chile.
- **Pipeline.** Not accounted for. Each line is scored alone; quantity and order total are ignored.

### 2.3 Delivery, installation, warranty and logistics bundled into the unit price

- **Mechanism.** A public OC price is a delivered price: the supplier delivers to a municipal
  address, often on a schedule, and invoices. A retail shelf price is a pickup or
  plus-shipping price.
- **Evidence.** All four flagged orders carry `FormaPago 2` and a delivery instruction
  (`TipoDespacho` 7 or 12) in the order record (`data/mirror/public/*.json`). The ChileCompra API
  documentation defines code 2 as "30 días contra la recepción de la factura", code 7 as
  "Despachar a Dirección de envío" and code 12 as "Otra Forma de Despacho, Ver Instruc"
  (https://www.chilecompra.cl/api/). The El Bosque order requires delivery in two milestones to the
  municipal warehouse and states "No se reciben despachos parcializados". None of the four orders
  bills delivery separately (`cargos` = 0 in the captured data), so any delivery cost is inside the
  unit price. On the retail side, one of the huincha baseline shops (Herramientas Total) offers free
  delivery in Santiago only above $149,990
  (https://herramientastotal.cl/products/huincha-medir-5m-x-25mm-total). The Convenio Marco for
  office supplies has been described by ChileCompra as including free delivery ("con despacho
  gratuito", https://www.chilecompra.cl/2023/08/ya-se-encuentra-disponible-en-la-tienda-de-convenio-marco-el-nuevo-catalogo-de-articulos-de-escritorio-y-papeleria/).
- **Size.** Unquantified. It matters most for single-unit, low-value orders, where a fixed delivery
  cost is a large share of the line.
- **Pipeline.** Not accounted for in the retail engine. The CM engine compares against CM prices,
  which already include the CM delivery conditions, so it is closer to like-for-like on this point.

### 2.4 Payment terms and the supplier's financing cost

- **Mechanism.** The supplier finances the goods from delivery until payment. A shelf price is paid
  at once.
- **Evidence.** Legal term: Ley 21.131 sets 30 days from invoice receipt (summary by Carey:
  https://www.carey.cl/ley-n-21-131-establece-pago-a-treinta-dias). Observed delays: a
  CobranzaOnline.com study cited by Emol reports municipalities take on average 136 days to pay an
  invoice (https://www.emol.com/noticias/Economia/2026/02/09/1190708/municipios-morosidad-regiones-chile.html).
  A search result attributes to Ex-Ante a figure of 43 days for municipalities from the Bolsa de
  Productos payer ranking; the page returned HTTP 403 and that number is unverified
  (https://www.ex-ante.cl/?p=370583). ChileCompra reported that in 2016, 61.9% of invoices were paid
  on time (https://www.chilecompra.cl/2017/09/municipios-y-salud-lideran-reclamos-por-retrasos-en-pago-a-proveedores/).
  Paraguay: about 80% of invoices paid after 30 days, average payment time rising from 37 to more
  than 52 days (https://www.open-contracting.org/2019/02/22/a-case-study-on-how-paraguay-could-save-millions-by-reducing-late-payments-in-public-procurement/).
  Brazil, 214,564 electronic auction records: prices "can be 1.06 times lower" when suppliers no
  longer price in late-payment costs (Libório et al., IJPM 18(2), 2023,
  https://ideas.repec.org/a/ids/ijpman/v18y2023i2p260-278.html).
- **Size.** On the order of a few percent. The only direct price estimate found is about 6% (Brazil).
  Arithmetic bound (computed here): the cost of carrying a price for d days at annual rate r is about
  r x d / 365. For financing alone to explain a 1.5x ratio over 136 days, r would have to be about
  134% a year ((1.5 - 1) x 365 / 136); over the stated 30-day term, about 608%. Financing cannot
  explain a Watch-tier flag on its own.
- **Pipeline.** Not accounted for.

### 2.5 Transaction and compliance costs of selling to the State

- **Mechanism.** Registration, bid preparation, guarantees, document handling and slow collection
  are fixed costs a supplier recovers through price, more heavily on small orders.
- **Evidence.** Being registered in the Registro de Proveedores is a paid service; the fee is shown
  at the end of the procedure and was not found in the sources reached
  (https://www.chileatiende.gob.cl/fichas/538-inscripcion-en-el-registro-electronico-oficial-de-proveedores-del-estado).
  ChileCompra's page on the registry says it may charge registration and renewal fees with
  differentiated schemes for smaller firms (https://www.chilecompra.cl/registro-proveedores-del-estado/).
  The Brazilian study above also finds prices about 1.2% lower per additional bidder, which
  links compliance burden to competition, not only to cost.
- **Size.** Unquantified for Chile.
- **Pipeline.** Not accounted for.

### 2.6 Small-order fixed costs and the Compra Agil channel

- **Mechanism.** Compra Agil is the channel for small purchases. Fixed costs per order (quoting,
  dispatch, invoicing) weigh more on a low total.
- **Evidence.** Compra Agil covers purchases "por montos iguales o inferiores a 100 UTM", requires
  at least three quotes but may proceed with fewer, is by general rule carried out with Empresas de
  Menor Tamano and local suppliers, and a buyer who does not pick the lowest offer must justify it
  in the OC (https://www.chilecompra.cl/ley-compra-agil/). The Observatorio ChileCompra referred to
  Contraloria a municipal Compra Agil in which the lowest offer was not chosen
  (https://www.chilecompra.cl/2025/05/observatorio-chilecompra-detecta-seleccion-no-fundamentada-de-proveedor-en-proceso-de-compra-agil-de-municipio/).
  With the UTM at 71,649 CLP in July 2026 (https://mindicador.cl/api/utm/06-07-2026), the Pirque
  order (189,900 CLP net) is about 2.7 UTM and the Buin order (1,268,600 CLP net) about 17.7 UTM
  (computed here).
- **Size.** Unquantified.
- **Pipeline.** Not accounted for. `codigo_tipo` is captured but unused in scoring.

### 2.7 Regional and commune effects within the Region Metropolitana

- **Mechanism.** Delivery to a peri-urban commune (Pirque, Buin) can cost more than to central
  Santiago.
- **Evidence.** The Convenio Marco catalogue prices products per region, with a single
  METROPOLITANA price and no commune field (`data/cm_catalog.parquet`: 418,012 METROPOLITANA rows,
  16,770 NACIONAL, computed here). That means CM suppliers commit to one price for the whole RM.
  The Dipres CM study found higher overspending in the Region Metropolitana than in other regions
  (https://www.dipres.gob.cl/598/articles-366422_doc_pdf.pdf, section 5).
- **Size.** Unquantified within the RM. The single RM-wide CM price suggests suppliers can absorb
  intra-RM delivery differences.
- **Pipeline.** Not accounted for, and probably a small effect inside the RM.

### 2.8 Timing and inflation between the order and the retail observation

- **Mechanism.** Prices drift between the order date and the date the retail price was observed.
- **Evidence.** INE: IPC July 2026 monthly variation 0.1%, 3.5% over twelve months
  (https://www.ine.gob.cl/sala-de-prensa/prensa/general/noticia/2026/08/07/%C3%ADndice-de-precios-al-consumidor-%28ipc%29-de-julio-present%C3%B3-una-variaci%C3%B3n-mensual-de-0-1).
  The gap for the 4 flags is between 4 and 17 days.
- **Size.** Well under 1% for these flags. It would matter for a stale baseline or for goods with
  their own price dynamics (electronics fall, nuts follow harvests).
- **Pipeline.** Partly. Freshness is measured against the build date (`build_baselines.py:47`), not
  the order date. The seed prices behind the published flags were observed 12-13 July; a rebuild
  more than 90 days later turns them `insufficient` (`baseline.py:43-44`).

### 2.9 Brand, tier and specification mismatch versus the basket SKU

- **Mechanism.** The OC may name a premium brand or a higher specification than the basket item.
  That makes the purchase dearer without any supplier overcharge. Paying for a dearer variant can
  still be waste, but it is a different claim (the buyer's choice) from overpricing (the supplier's
  price).
- **Evidence.** Bandiera, Prat and Valletti find that Italian public bodies pay systematically
  different prices for observationally equivalent goods (central administration at least 22% more
  than semi-autonomous agencies) and attribute most of it, 83% of estimated waste, to passive waste
  (inefficiency) rather than active waste (corruption) (AER 2009;
  https://econpapers.repec.org/paper/rtvceisrp/115.htm). Celhay, Gertler, Olivares and Undurraga
  measured overpricing against the 5th percentile of comparable substitutes in the CM store: the
  average was 7.6% sobreprecio and 6.1% sobregasto across services in 2019, with about 10% of
  services above 9% (Dipres report, https://www.dipres.gob.cl/597/articles-266611_r_ejecutivo_institucional.pdf,
  section 5.1.2).
- **Project data (computed here, `data/cm_catalog.parquet`).** Inside the Convenio Marco, the same
  "corchetera oficina 30 hojas" spans brand medians from 1,840 CLP net (OFFIXNEW) to 25,579.5 CLP
  net (ISOFIT), with TORRE at 8,903.5. Metal 5 m measuring tapes run from about 2,554 CLP net
  (INGCO) to 10,239 (STANLEY). A brand choice alone can produce a 3x to 10x spread.
- **Size.** Product-specific, often larger than the publish thresholds.
- **Pipeline.** Not accounted for in the ratio. ADR 0023 handles it only partly, through a
  tier-stable SKU allowlist and red-context keywords. The 4 flags are all on allowlisted SKUs, yet
  two of them name or imply a specific brand or grade (section 3).

### 2.10 Convenio Marco versus spot purchases (Compra Agil, trato directo, licitacion)

- **Mechanism.** Each channel has its own competition structure. CM prices come from a
  pre-qualified catalogue; Compra Agil from a few quotes; an SE order here from a licitacion.
- **Evidence.**
  - Dipres measured CM sobregasto against the lowest available price for the same product in the
    same region at purchase time: 3.6% of central-government spend across 12 standardized CMs in
    2022-2023, concentrated in food, cleaning, hardware and office supplies
    (https://www.dipres.gob.cl/598/articles-366422_doc_pdf.pdf, sections 4.1 and 5). Municipalities
    were excluded from that estimate.
  - The FNE market study (2020) found CMs "no han funcionado de manera competitiva", with 78% of
    applicants selected, so "no es necesario ofrecer precios bajos para ser parte"
    (https://www.pauta.cl/economia/compras-publicas-estudio-fne-riesgos-competencia-mayores-costos).
    It estimated savings of between US$290 and US$855 million a year from its recommendations
    (https://www.elmostrador.cl/dia/2020/08/25/ahorro-entre-us-290-y-855-millones-fne-propone-cambios-a-compras-publicas/).
  - ChileCompra contracted a mass market-price monitor for about 9,000 CM products to ensure they
    have "un precio igual o menor al de mercado"
    (https://www.chilecompra.cl/2021/07/participa-en-la-licitacion-para-monitoreo-masivo-de-precios-de-mercado-de-productos-de-tienda-de-convenio-marco/).
  - The office-supplies CM is available "por montos superiores a 10 UTM y un máximo de 25.000 UTM"
    (https://www.chilecompra.cl/2024/12/sumate-y-oferta-en-la-nueva-licitacion-para-el-convenio-marco-de-escritorio-y-papeleria/).
  - ChileCompra's glossary defines CM as "Orden de compra proveniente de una licitación por Convenio
    Marco" (https://www.chilecompra.cl/glosario/cm/) and AG as "Orden de compra proveniente de una
    Compra Ágil" (https://www.chilecompra.cl/glosario/ag/). The El Bosque order (SE) is titled
    "ORDEN DE COMPRA DESDE 1736-55-LE26", so it comes from a licitacion.
- **Size.** Within-CM gaps for identical products average single digits (3.6% Dipres, 7.6% Celhay
  et al. with substitutes). No source with a CM-vs-retail gap size was found.
- **Pipeline.** The CM engine exists but is a separate lead queue. The retail engine treats a CM
  purchase like any other and therefore can flag a buyer for paying the official catalogue price.

### 2.11 Retail reference construction

- **Mechanism.** The reference itself can be too low: a single observation, a promotional or
  card-only price, a different model, or an unusually cheap shop.
- **Evidence.** For 16 GB pendrives, a Falabella listing page captured for this study (about three
  months after the order) shows branded units at $8,990 (Philips), $9,689 and $12,200 (Adata) and
  $12,300 (Maxell) (https://www.falabella.com/falabella-cl/shop/pendrive-16gb). The project
  baseline for the same SKU is one price of $3,368 (`data/seed_prices.json`). Celhay et al. chose
  the 5th percentile over the minimum precisely because minimum prices are often mislabelled
  per-unit or per-pack entries (Celhay et al. report above, methodology section).
- **Size.** Can exceed 2x on its own for thinly traded goods (pendrive case).
- **Pipeline.** Median of seed observations, but a single observation is scorable as `medium`
  (`baseline.py:47-48`). SoloTodo prefers offer prices (`solotodo.py:32`).

### 2.12 How established monitors set a fair threshold

- **Open Contracting Partnership** (unit-price analysis in Eastern Europe and Central Asia): use the
  median, not the mean; treat Q1-Q3 as the normal range; treat prices at least 1.5 IQR above Q3 as
  clear anomalies; acceptable deviation differs by product (examples of 5% and 25%) and "should be
  calibrated by the oversight experts"; build references only from competitively awarded contracts,
  since "Single-sourcing is a bad indicator of fair prices"
  (https://www.open-contracting.org/2022/03/16/analyzing-unit-prices-in-public-procurement-in-eastern-europe-and-central-asia/).
- **Brazil, IN SEGES 65/2021:** the estimated price may be the mean, median or lowest of at least
  three prices, discarding "inexequíveis, inconsistentes e excessivamente elevados" values, with no
  fixed percentage (text of the norm as hosted by UEM:
  https://pad.uem.br/dmp/instrucoes-de-servicos/instrucao-normativa-seges-no-65-2021.pdf/@@download/file/INSTRUÇÃO%20NORMATIVA%20SEGES%20Nº%2065-2021.pdf;
  TCU guidance on the calculation:
  https://licitacoesecontratos.tcu.gov.br/4-3-9-3-definicao-e-execucao-da-forma-de-calculo-do-valor-estimado-da-contratacao/).
  Both were read through search summaries, not in full.
  A TCE-RN course citing TCU Acordao 2621/2019 states the TCU applies no tolerance margin when
  assessing sobrepreco (https://tce.rn.gov.br/as/EscolaContas/ArquivosCurso/127/1._Orçamento_Estimativo_e_Pesquisa_de_Preço.pdf);
  that is a secondary source and the acordao itself was not read.
- **Chile, Dipres / Celhay et al.:** reference = minimum or 5th percentile of the same or comparable
  CM product in the same region at the time of purchase (sources in 2.9 and 2.10).

The common thread: a robust central or low quantile of a **like-for-like, same-channel,
same-time** distribution, plus a product-specific tolerance. None of these monitors compares a
delivered public price to a single retail shelf price.

### 2.13 Summary table

| Effect | Plausible size | Evidence quality | In pipeline today |
|---|---|---|---|
| IVA basis | exactly 1.19x if mismatched | Law + project check | Yes, but retail sources not verified gross |
| Quantity / bundle within order | unquantified (17% savings potential in Italy) | Weak for Chile | No |
| Delivery bundled | unquantified; large for tiny orders | Order records + shop terms | No |
| Payment term / financing | a few % (about 6% in Brazil) | Moderate | No |
| Compliance / registry cost | unquantified | Weak | No |
| Small-order fixed cost | unquantified | Weak | No |
| Commune within RM | probably small (CM uses one RM price) | Indirect | No |
| Inflation / timing | under 1% for these flags | Strong (INE) | Partly |
| Brand / tier / spec | 3x-10x within one CM product class | Strong (project CM data) | Partly (allowlist) |
| CM vs spot channel | within-CM waste 3.6-7.6% | Strong (Dipres) | Separate engine only |
| Reference construction | can exceed 2x | Strong for the pendrive case | Partly |

The quantifiable legitimate wedges (IVA once aligned, financing, inflation) add up to single-digit
percentages. The effects that can produce 2x or more are spec/brand mismatch and a weak reference.
Those are the ones that decide whether a flag is fair.

---

## 3. The 4 published flags in this light

All figures computed here from `data/confirmed_flags.json`, `data/seed_prices.json`,
`data/cm_catalog.parquet`, `data/oc_items_*.parquet`, `data/peer_pending.json`,
`data/cm_pending.json` and `data/mirror/public/*.json`.

### 3.1 Buin, pendrive 16 GB (2721-217-AG26 / 8), published at 2.76x, "high"

- Compra Agil, 12 units, spec "PENDRIVE DE 16 GB" (no brand), supplier CARIBBEAN GROUP SPA,
  30-day payment, delivery to the buyer's address.
- Paid 7,800 net = 9,282 gross. Baseline 3,368 is **one** observation (Alcaplus Kingston
  DataTraveler), confidence `medium` only because n=1 is allowed. Its IVA basis could not be checked.
- Convenio Marco, same product class (16 GB pendrives, RM): median 3,478 net, MAD 495.5, n=108.
  Buin paid 2.24x that median; robust z = 0.6745 x (7,800 - 3,478) / 495.5 = 5.9.
- Retail listings captured later (Falabella) show branded 16 GB units at $8,990-$12,300 gross; on
  those Buin's 9,282 gross is near parity.
- The same order prices batteries far below the baseline; across the three basket-matched lines
  the order is about 1.18x (section 2.2, with its assumption).
- **Verdict: at risk as published.** The "2.8x over retail" claim rests on a single, possibly
  unrepresentative retail price. A fair restatement survives as "2.2x the Convenio Marco median
  for the same class of product, robust z about 5.9", which is a different and more defensible
  claim. It is not robust to the retail framing.

### 3.2 El Bosque, nueces 1 kg (1736-668-SE26 / 40), published at 2.25x, "high"

- Order from licitacion 1736-55-LE26, 49 food lines, 1 unit of "Nueces 1 kilogramo PIWEN" (brand
  named by the supplier), delivery to the municipal warehouse in two milestones, 30-day payment;
  the supplier accepted the order four weeks after it was sent.
- Paid 23,664 net = 28,160 gross. Baseline 12,490 = median of two specialist shops (11,990 and
  12,990), confidence `high`, spread 0.08.
- The peer engine independently rates the line severe at 3.46x the peer median of 8,144 (n=19),
  though that UNSPSC code mixes nuts and dried fruit.
- No CM row for walnuts by the kilo exists in the cached catalogue. No retail price for Piwen 1 kg
  was found in the sources reached. A web search over yapo.cl classified ads in the RM returned
  mariposa walnut offers of about 5,000-9,000 CLP/kg, which suggests the baseline is not low
  (search-result snippets from yapo.cl pages such as
  https://www.yapo.cl/supermercado-alimentos/region-metropolitana.5; individual ads not opened,
  weak evidence).
- Break-even (computed here): the flag drops below "high" if Piwen 1 kg retails at 14,080 gross or
  more, and below "watch" at 18,773 or more.
- **Verdict: probably survives, conditional on one check.** Every quantified legitimate wedge
  (financing, delivery, inflation) is small next to 2.25x, and a second method agrees. The open
  risk is a brand premium for Piwen, which is unknown. One verified Piwen retail price settles it.

### 3.3 Pirque, huincha de medir 5 m (2719-381-AG26 / 3), published at 2.18x, "high"

- Compra Agil, one unit, order total 189,900 CLP net (about 2.7 UTM) across four measuring
  instruments, supplier IMPORTADORA MEDIM LIMITADA (Las Condes), delivery to Pirque, 30-day payment.
  Spec: metal tape, 5 m, about 19 mm wide, polyester coating, ABS impact-resistant case, locking,
  compensating hook "o equivalente". That is a mid-to-upper grade description.
- Paid 16,500 net = 19,635 gross. Baseline 8,990 = median of a Stanley PowerLock 5 m (12,990, IVA
  included) and a Total 5 m x 25 mm (4,990, material not stated). Spread 0.89, still `medium`.
- Against the spec-closest retail item (Stanley PowerLock, 12,990): **1.51x**.
- Against the CM "HUINCHA DE MEDIR STANLEY METÁLICA 5M" (median 10,239 net, n=12): **1.61x**.
- The CM engine's own lead on this line (7.2x, `data/cm_pending.json`) is contaminated by plastic
  tailor's tapes in the matched set and should not be used.
- **Verdict: does not survive as "high".** On a spec-matched reference the ratio sits at the Watch
  boundary, and the order is exactly the type (single unit, tiny total, peri-urban delivery) where
  unquantified small-order and delivery costs are largest. The 2.18x figure is mostly a product of
  averaging two different tiers into the baseline.

### 3.4 San Bernardo, corchetera (2341-311-CM26 / 5), published at 2.77x, "high"

- **Convenio Marco order**, 100 units of CM product 4404798 "CORCHETERA TORRE OFICINA 30 HOJAS
  METAL/PLÁSTICO 24/6 A 26/6MM UNIDAD RM" from DIMERC S.A.
- Paid 8,275 net = 9,847 gross. Baseline 3,555.5 = median of two **20-sheet** staplers (Fultons
  3,790, Nuovo 3,321). The curation note says "producto exacto", but sheet capacity and brand differ.
- In the cached CM catalogue, the identical TORRE product has 66 offers, median 8,903.5 net,
  MAD 70; DIMERC's own offers include exactly 8,275. San Bernardo paid **0.93x the CM median for
  the exact product**, at the low end of its offers.
- Across all 30-sheet office staplers in the CM, the median is 4,167 net (n=301) and brand medians
  run from 1,840 to 25,579.5. Choosing TORRE over a cheaper 30-sheet brand is where the gap comes
  from.
- **Verdict: does not survive as an overpricing flag.** The supplier charged the catalogue price
  through the official channel. What remains is a brand-choice question (passive waste in the
  Bandiera et al. sense), which is a different claim, and its size depends on whether TORRE has a
  functional difference, which this study could not establish.

### 3.5 Summary

| Flag | Published | Fair restatement | Status |
|---|---|---|---|
| Buin pendrive | 2.76x retail | 2.24x CM median (z about 5.9); near parity with later retail listings | At risk as worded; defensible only on the CM framing |
| El Bosque nueces | 2.25x retail | unchanged pending Piwen price; peer 3.46x | Probably survives |
| Pirque huincha | 2.18x retail | 1.51x (Stanley retail) / 1.61x (Stanley CM) | Does not survive as "high" |
| San Bernardo corchetera | 2.77x retail | 0.93x CM median for the exact item | Does not survive as overpricing |

---

## 4. Proposed adjustments, ranked by impact on fairness

All candidates; none decided. Each is phrased as the decision Felipe would approve or reject.

1. **Same-specification reference, with brand choice as a separate claim.** When the OC or the
   supplier names a brand or grade, compare against that brand or grade (retail or CM). Keep a
   cheaper-substitute comparison only as a separately labelled "dearer variant chosen" signal, not
   as overpricing. *Why first:* spec/brand mismatch is the only effect found that routinely reaches
   2x-10x, and it drives two of the four published flags.
2. **Mechanism-aware reference.** For a CM order, compare first against the CM distribution for the
   exact product at the order date (Dipres method); a CM purchase at or below that median is not
   supplier overpricing. For AG and licitacion orders, show the CM median for the same product
   alongside the retail reference. *Why:* the CM price is the official, delivered, net,
   same-region price, which removes IVA, delivery and regional doubts at once.
3. **Minimum reference evidence for publishing.** Require at least 2 independent retail observations
   with a robust spread limit (for example, MAD / median below a set value) before a retail ratio
   can be published; n=1 stays a lead. Record each seed price's IVA basis with evidence. *Why:* the
   pendrive flag rests on one unverified price; the huincha baseline averages two tiers.
4. **Publish threshold that clears the legitimate wedges.** Keep Watch/High/Severe for the queue,
   but publish a retail-only flag only above a threshold that exceeds the sum of plausible
   legitimate premiums for that order type, or measure against an upper quantile (Q3) of the
   reference offers instead of their median, in the spirit of the OCP Q3 + 1.5 IQR rule. *Why:* the
   quantified wedges are small, but delivery and small-order costs are unquantified and largest in
   tiny orders.
5. **Small-order handling.** Treat orders below a set size (for example, the 10 UTM CM floor, or a
   Compra Agil total below some UTM value) as leads only, or apply a stricter publish threshold.
   *Why:* Pirque's order is 2.7 UTM and a single unit; fixed delivery and quoting costs are not
   measurable from the data.
6. **Order-level context on every flag.** Show the ratio across all basket-matched lines of the same
   order next to the line ratio. *Why:* the Buin order is about 1.18x overall although one line is
   2.76x; a reader should see both.
7. **Time alignment.** Measure baseline freshness against the order date (for example, a retail
   observation within a set window of the order) rather than the build date. *Why:* small effect for
   these flags, but the current rule lets baselines expire or survive for reasons unrelated to the
   order.
8. **Prefer normal over offer prices from SoloTodo**, or record both. *Why:* offer prices can be
   promotional or payment-method prices that a municipality cannot get; small effect, cheap fix.
9. **Financing allowance: not recommended as a separate adjustment.** Its plausible size (a few
   percent) is far below the Watch tier; it is better absorbed into the threshold in item 4.

---

## 5. Open questions only Felipe can answer

1. **What does a published flag claim?** "The supplier charged more than the market", "the
   municipality paid more than it needed to", or "the same thing was available cheaper in the CM"?
   Each needs a different reference, and the current wording mixes them.
2. **Should a dearer brand or grade chosen by the buyer ever be published**, and if so under what
   label?
3. **What to do with the four published flags:** keep, re-word with the fair restatement, move back
   to review, or dismiss, flag by flag. In particular San Bernardo (bought at the CM catalogue price)
   and Pirque (1.5x on a spec-matched reference).
4. **Can you confirm a retail price for Piwen nueces 1 kg** around the order date? It decides the
   El Bosque flag.
5. **Was the Alcaplus pendrive price gross or net?** The site refused every automated fetch.
6. **Which order-size floor, if any, should keep small orders as leads only**, and in what unit
   (UTM, CLP, number of units)?
7. **Should references be drawn only from competitive channels** (as the OCP guidance suggests),
   which would exclude trato directo prices from peer medians?
8. **The retail baselines behind the published flags were observed 12-13 July and approach the
   90-day freshness limit.** Should they be re-observed before any of these flags is re-stated?
