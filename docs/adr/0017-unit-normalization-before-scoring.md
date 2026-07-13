# 0017 - Unit normalization before overprice scoring

Status: Accepted
Date: 2026-07-13
Deciders: Felipe Carvajal Brown

## Context

After the basket grew to 75 SKUs (ADR 0005 line), a triage of the real 2026-07-09 RM
capture showed that almost every "pending" overprice flag was a **unit mismatch**, not a
real overprice: a pack of 4 markers scored against a per-marker baseline (~4x), a 200 m tape
roll against a 40 m baseline (~3.5x), a pack of 12 water bottles against a single 1.5 L
bottle (~6.5x), an electric stapler against a manual one, a box of 5000 staples against a
per-box baseline. Publishing these would be false public accusations against named communes —
exactly what the curation gate (ADR 0006) and the precision-first matcher (ADR 0012) exist to
prevent, but the raw ratio conflated "overpriced" with "bigger pack / different format".

The per-unit plausibility band of ADR 0013 (`[0.3x, 20x]`) only caught the extreme cases and
routed them to `unit_ambiguous`; the moderate mismatches still surfaced as confident flags.

## Decision

Introduce a deterministic **unit-normalization** step (`units.py`) that runs inside the scorer
before the ratio is computed:

1. Each SKU declares a canonical **base unit**: either count-based (`base_count`, the number of
   items the baseline price represents; default 1) or size-based (`base_size` + `base_dim`, one
   of `ml`/`g`/`m`).
2. From the line-item's free text (`product` + both `especificacion` fields) the scorer parses
   an explicit pack **count** ("caja de 12", "set de 4", "1000 unidades") and, for size-based
   SKUs, a **size** in the base dimension ("500 cc", "15 kg", "200 mts"). Parsing is
   conservative: a size measure is never read as a count, and when nothing parses the divisor is
   1.0 (previous behaviour), so normalization can only ever correct an inflated ratio, never
   fabricate one.
3. The gross unit price is divided by that normalized quantity, and the overprice ratio uses the
   **normalized** price. The anomaly records `unit_divisor` and `normalized_unit_price_clp` for
   curation transparency.
4. **Small-format guard:** for size-based SKUs, scaling a much smaller format *up* to the base
   size is unreliable (per-unit price is non-linear: a 75 ml sachet is dearer per litre than a
   1 L bottle). When the size divisor is below `MIN_SIZE_DIVISOR` (0.5), the line routes to
   `unit_ambiguous` for human review instead of being flagged.

The matcher also gained three excludes the triage exposed (`potasico`/`abono` for agricultural
potassium soap vs hand soap; `electrica` for electric vs manual stapler; `plumon`/`correccion`
for marker sets vs ballpoint pens), each backed by a real hard-negative in the labeled sample.

## Consequences

- On the 2026-07-09 capture the pending queue went from 13 mixed flags (mostly false) to 8
  like-for-like normalized candidates; the mismatches moved to `unit_ambiguous`, still reviewable
  but not presented as confident overprices. The published site stays trustworthy.
- Scoring now depends on per-SKU base metadata in `data/basket.json`; a wrong `base_size` yields a
  wrong ratio, so base units are set only where the baseline's canonical size is known, and left
  at the default count=1 otherwise.
- The `Anomaly` record gained two fields (`unit_divisor`, `normalized_unit_price_clp`); consumers
  that read the raw `unit_price_clp_gross` are unaffected.
- Recall is deliberately traded for precision: genuinely overpriced small-format items may land in
  `unit_ambiguous` rather than `pending`. Acceptable for a public-accusation tool.

## Alternatives considered

- **Keep raw ratios, lean on curation.** Rejected: floods the human gate with false positives and
  makes the pending queue unreviewable, which is the concrete failure this ADR responds to.
- **Full size engine (parse every dimension, width x length, density).** Rejected for v1 as
  error-prone; a wrong size parse produces a wrong accusation. The conservative count + single-
  dimension size, with a small-format guard, covers the dominant mismatch classes safely.
- **Per-unit-count SKUs only (no size).** Rejected: misses the size-driven mismatches (tape length,
  gas kg, bottle volume) that were a large share of the false flags.
