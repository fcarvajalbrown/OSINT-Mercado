# 0012 — Controlled-basket matcher: implementation

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Felipe Carvajal Brown

## Context

ADR 0005 settled the *approach* — a curated per-SKU keyword classifier over a tight basket,
with fuzzy matching only as a disambiguator, developed test-first against a labeled sample of
real line-items. Phase 3 had to turn that into concrete rules. Inspecting a real captured
order revealed that the parsed `Producto` field is only the generic UNSPSC label
("Zapatos de hombre", "Ropa reflectante o accesorios"); the actual product identity lives in
`EspecificacionProveedor`/`EspecificacionComprador`, which the parser did not previously
extract (fixed in the Phase 3 parser extension). A bounded live capture of 319 real RM
line-items exposed concrete failure modes: over-generic keywords like `caja 100` matched tea
("TÉ ... CAJA 100 BOLSAS") and `caja 50` matched oatmeal ("AVENA ... CAJA 500 G"); the broad
UNSPSC `Categoria` label ("Escobas, trapeadores...") matched a dustpan to `escoba`; and plain
substring matching broke on plurals and on the "TAMAÑO" token inserted mid-phrase.

## Decision

- **Match inputs:** the normalized concatenation of `Producto + EspecificacionProveedor +
  EspecificacionComprador` only. The UNSPSC `Categoria` label is deliberately excluded — it is
  a broad bucket that over-generalizes and leaks false positives.
- **Keyword rule:** a keyword matches when *every* one of its meaningful tokens (after
  dropping Spanish stopwords) appears as a substring of the normalized text. Per-token
  (not whole-phrase) substring survives inserted words like "TAMAÑO"; substring (not exact
  token) survives plurals ("escobillon" in "escobillones").
- **Fuzzy role:** rapidfuzz `token_set_ratio` is used *only* to pick among multiple keyword
  candidates. There is no keyword-less fuzzy fallback — a match requires a curated keyword to
  fire. Recall is bounded by keyword coverage, which keeps precision high.
- **Keyword curation:** basket keywords were retuned to distinctive tokens (e.g. `nitrilo`
  instead of `caja 100`; `papel fotocopia carta` / `resma carta 500` instead of bare `resma`;
  added `escobillon`, `bota seguridad`, `botin seguridad`).
- **Validation:** a hand-labeled sample of real RM line-items
  (`tests/fixtures/labeled_line_items.json`, positives + hard negatives) drives a
  precision/recall test. The bar: **precision == 1.0** (a false positive is a false public
  accusation, ADR 0006) with a documented recall floor.

## Consequences

- False positives from generic pack-size tokens and category-label leakage are eliminated on
  the labeled sample; the tea/oatmeal/dustpan cases are correctly rejected.
- Recall is limited to what the curated keywords cover — the intended controlled-basket
  trade-off. SKUs absent from the captured sample (e.g. toner, pilas, teclado) have untested
  recall; widening coverage is additive keyword work as more real data is seen.
- `rapidfuzz` is a new runtime dependency, used narrowly for disambiguation.
- Precision-first means some genuine basket purchases with unusual wording will be missed
  rather than mismatched; that is the correct bias for a watchdog and is backstopped by the
  human curation gate.

## Alternatives considered

- **Include the UNSPSC `Categoria` in the match text.** Rejected: it leaked false positives
  (dustpan → escoba) for little recall gain.
- **Keyword-less fuzzy fallback over the whole basket.** Rejected: it was the dominant
  false-positive source (e.g. opalina cardstock scoring high against the paper blob) and
  contradicts ADR 0005's "fuzzy only to disambiguate".
- **UNSPSC product codes as the primary join key.** Deferred: codes are coarse
  ("Zapatos de hombre" ≠ steel-toe safety shoe) and unpopulated per SKU; a candidate signal
  for a later phase.
