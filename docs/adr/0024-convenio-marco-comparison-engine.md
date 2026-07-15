# 0024 - Convenio Marco size-normalized comparison engine

Status: Accepted
Date: 2026-07-14
Deciders: Felipe Carvajal Brown

## Context

The retail-basket (ADR 0005/0013), peer (ADR 0018), and auto-catalog (ADR 0019) engines
compare a purchase against, respectively, a hand-researched retail price, what other communes
paid, and a self-referential market median. None of them answers the most *defensible* question
for a public-procurement watchdog: could the organism have bought this cheaper under the
**Convenio Marco** (CM) framework agreement it was legally bound to consider first? A CM price is
normative, official, and published by ChileCompra itself, so a gap against it is far harder to
dismiss than a gap against a private retailer.

ChileCompra publishes, per active CM, a weekly "maestra de productos": every catalogued product a
buyer could purchase under the agreement, with a per-region shelf price. The source was verified
and cached (ADR 0022 had already flagged it as the candidate official secondary anchor, deferred
until its download URL was captured):

- Index (semicolon-delimited, UTF-8 BOM):
  `https://transparenciachc.blob.core.windows.net/maestrascm/CM_publicados.csv` - 18 active CM
  files, refreshed Tuesdays. No auth.
- Each entry -> `MaestraProd_cm_<ID>.zip`; inner CSV comma-delimited, UTF-8 BOM, 20 columns
  (CÓDIGO ONU = 8-digit UNSPSC, PRODUCTO, MARCA, MODELO, MEDIDA, REGIÓN, PRECIO EN TIENDA, NOMBRE
  PROVEEDOR, ...). Content-Type is octet-stream; parse by extension. Two of the 18 zips carry
  multiple category CSVs (9 and 16), all of which must be read.
- Join key: OC `product_code` == CM `CÓDIGO ONU` (both 8-digit UNSPSC).

The join is only the start. Real pitfalls, all observed in the data:

1. **UNSPSC codes are broad and misused.** "pala de aseo" and "mesa plegable" share a code;
   buyers also misclassify. A friend reviewing the live site put it exactly: "los códigos ONU son
   los que en teoría estandarizan la compra, pero no siempre es así." Code-only comparison is
   invalid.
2. **Size/format mismatch dominates the residue.** "café 170 g" vs a CM "50 g" row, "maní 1000 g"
   vs "38 g", "cinta 45.7 m" vs "5 m". Unnormalized, the ratio measures packaging, not price.
3. **CM per-unit vs per-pack artifacts.** A té-100-bolsas row at $299 (a per-pack total mislabeled)
   would poison a min or mean.
4. **Region.** CM prices are per REGIÓN; an RM buyer's comparison set is the RM-specific rows plus
   national convenios.
5. **IVA basis.** OC `unit_price` is `PrecioNeto`; the CM basis had to be confirmed, not assumed.
6. **Scope artifacts.** CÓDIGO ONU "0"/empty rows, whole-contract totals, service lines.

## Decision

Build the CM engine as four deterministic, test-first pieces plus a CLI, emitting investigative
leads to the human curation gate (ADR 0006) - **never auto-published** (a new engine has no track
record, and price alone is an indicio, not proof).

- **`cm_catalog.py`** - fetch the index, read every inner CSV (including the multi-CSV zips), keep
  **METROPOLITANA + NACIONAL** rows (a national CM is available to RM buyers) with a valid 8-digit
  code and positive net price, dedup, and cache `data/cm_catalog.parquet` (434,782 rows, 471 codes).
  Column names are pinned in one place, as with `schema.py`.
- **`cm_scoring.py`** - the core. For one OC line: (1) look up CM rows by shared code; (2) keep
  only same-product rows by **>= 2 shared distinctive tokens** (length >= 4, non-stopword,
  non-generic) - the code is the join key, never the match; (3) determine the comparison dimension
  from the matched CM set (g / ml / m, or per-unit); (4) **size/pack-normalize both sides** to per
  gram / ml / m / each (reusing `units.py`, extended with `parse_any_size`); (5) reference =
  **median** of the matched CM per-unit prices (median, not min - absorbs the per-pack artifact);
  (6) ratio in a **plausibility band [1.5x, 15x]**, severity via `scoring.severity`; a minimum of
  **3 matched references** is required. fx-to-CLP conversion stays upstream so the core is pure.
- **`cm_verify.py`** - the quality gate, reusing `verify.py`'s red-context signals and adding
  CM-adapted **bundle** (set / kit / surtido / enumerated / verbose) and **unresolved pack/box**
  detectors, tagging each lead clean-or-not with a reason for the reviewer. It does not gate
  publishing; it ranks what the human sees.
- **`cm_score.py` / `osint-cm-score`** - runs the captures against the cached catalog, converts
  net unit prices to CLP (skipping the negligible minority it cannot convert rather than aborting),
  scores, tags, and writes a deterministic `data/cm_pending.json` with the order's provenance
  (`oc_url`, ids, capture) and the matched CM product / price / region as evidence.

**IVA basis (confirmed, not assumed).** CM `PRECIO EN TIENDA` is shown **net of IVA** - confirmed
both from ChileCompra store documentation ("los precios ... se muestran en valores netos") and an
empirical cross-check: for tightly-comparable products the CM/OC-net ratio sits near parity
(microfibre cloths 1.03, carpeta oficio 1.09), which is impossible if CM were gross against an OC
net. OC `unit_price` is also net (`PrecioNeto`). The comparison is therefore **net-to-net, with no
gross-up on either side** - unlike the retail engine, which grosses OC up to meet gross retail.

## Consequences

- The most defensible engine we have: every lead cites an official CM product, its net price, and
  its region, next to the order's own source link.
- Size normalization is the load-bearing step. It only ever *corrects* an inflated ratio (a bigger
  format divides the price down); it cannot fabricate one. Lines whose size cannot be parsed, or
  that lack 3 matched references, produce no lead rather than a guess.
- Coverage is honestly bounded: of ~21k RM line-items, ~4.5k fall under a CM-covered code, and only
  a fraction of those survive same-product matching, size normalization, and the band. The number
  that survives is small by design - precision over recall, because each lead is a public claim.
- The cached catalog is a committed reference dataset (a `.gitignore` negation over the general
  `data/*.parquet` rule), so a lead's evidence is versioned and reviewable. If weekly refreshes
  bloat history, it can move to gitignored + rebuilt-in-CI via `osint-cm-fetch` without touching
  the engine.
- Politeness: the blob is public and unauthenticated; fetch weekly, cache, and pin field access
  behind `cm_catalog.py`.

## Alternatives considered

- **Code-only comparison (join on UNSPSC, compare prices).** Rejected: broad/misused codes make it
  invalid, as the data and the reviewer both showed. Same-product token matching is mandatory.
- **Compare against the CM `min` price (the cheapest offer).** Rejected: a single mislabeled
  per-pack row becomes the reference and manufactures false overprices. The median is robust to it.
- **Gross both sides up.** Rejected once the net basis was confirmed: it would cancel out but adds a
  needless assumption; net-to-net is the honest like-for-like.
- **Compare only against the RM-specific rows.** Rejected: national convenios are genuinely
  available to RM buyers, and some products exist only as NACIONAL rows; excluding them drops real
  normative references. Other regions' rows are still excluded.
- **Auto-publish CM leads (they are "official").** Rejected: a normative gap is still only an
  indicio, and the engine is new. Every lead goes through the human gate (ADR 0006).
