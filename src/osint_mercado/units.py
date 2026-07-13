"""Unit normalization for the anomaly scorer (extends ADR 0013).

Municipal line-items price wildly different packagings of the same commodity: a
box of 12 pens, a set of 4 markers, a 200 m tape roll, a 15 kg gas cylinder. The
retail baseline is defined for one canonical unit, so a raw price ratio conflates
"overpriced" with "bigger pack". These helpers pull an explicit pack COUNT or a
SIZE (in a target dimension) out of the free-text spec so the scorer can compare
like-for-like. Deterministic, no network.

Conservative by design: a count is only returned when the text explicitly names a
packaging quantity, and a size only when a magnitude in the requested dimension is
present. When nothing parses, the scorer falls back to "one base unit" — so this
can only ever *correct* an inflated ratio, never fabricate a new one.
"""

import re
import unicodedata


def _norm(text: str) -> str:
    """Lowercase, strip accents, keep digits/letters and decimal separators."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = without_marks.lower()
    # Keep alphanumerics and decimal separators; everything else becomes a space.
    return re.sub(r"[^a-z0-9,.]+", " ", lowered)


# --- pack count -------------------------------------------------------------

_NUM = r"(\d{1,6})"
# Ordered by priority: an explicit "N unidades" beats a "packaging de N" beats a
# bare "N <count-noun>" beats "x N".
_COUNT_PATTERNS = [
    rf"\b{_NUM}\s*(?:unidades|unidad|unid|und)\b",
    r"\b(?:pack|set|caja|cajas|bolsa|estuche|paquete|paq|juego|blister|display|"
    rf"dispensador)\s+(?:de\s+|x\s*)?{_NUM}\b",
    rf"\b{_NUM}\s*(?:colores|bolsas|bolsitas|sobres|pliegos|pares|corchetes|grapas)\b",
]


def parse_count(text: str) -> int | None:
    """Return the explicit packaging count bundled in the priced unit, or None.

    Size measures ("500 cc", "74 cm", "15 kg") are deliberately not counts.
    """
    norm = _norm(text)
    for pattern in _COUNT_PATTERNS:
        m = re.search(pattern, norm)
        if m:
            value = int(m.group(1))
            if value >= 1:
                return value
    return None


# --- size in a target dimension --------------------------------------------

_DECIMAL = r"(\d+(?:[.,]\d+)?)"
# For each canonical dimension, tokens mapping to a multiplier into the base unit
# (base units: ml, g, m). Longest tokens first so "gramos" wins over "g".
_DIM_TOKENS = {
    "ml": [
        ("mililitros", 1.0), ("mililitro", 1.0), ("cm3", 1.0), ("cc", 1.0), ("ml", 1.0),
        ("litros", 1000.0), ("litro", 1000.0), ("lts", 1000.0), ("lt", 1000.0), ("l", 1000.0),
    ],
    "g": [
        ("gramos", 1.0), ("gramo", 1.0), ("grs", 1.0), ("gr", 1.0), ("g", 1.0),
        ("kilos", 1000.0), ("kilo", 1000.0), ("kgs", 1000.0), ("kg", 1000.0), ("k", 1000.0),
    ],
    "m": [
        ("metros", 1.0), ("metro", 1.0), ("mts", 1.0), ("mt", 1.0), ("m", 1.0),
        ("centimetros", 0.01), ("centimetro", 0.01), ("cms", 0.01), ("cm", 0.01),
    ],
}


def parse_size_in_dim(text: str, dim: str) -> float | None:
    """Return the dominant magnitude (in base unit) found for `dim`, or None.

    "5 cm x 200 mts" in dim 'm' returns 200.0 (the roll length, not the width):
    the largest magnitude in the dimension is taken, which is what discriminates
    a bigger-format purchase from an overprice.
    """
    norm = _norm(text)
    best: float | None = None
    for token, factor in _DIM_TOKENS[dim]:
        for m in re.finditer(rf"{_DECIMAL}\s*{re.escape(token)}\b", norm):
            magnitude = float(m.group(1).replace(",", ".")) * factor
            if best is None or magnitude > best:
                best = magnitude
    return best
