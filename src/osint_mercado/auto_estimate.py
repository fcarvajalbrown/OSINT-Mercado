import statistics
from datetime import datetime, timedelta

import polars as pl

from osint_mercado.units import parse_any_size, parse_count

METHOD = "cgu-alice-2025+ufmg-tukey-2024"
MIN_COMPARABLES = 10
WINDOW_DAYS = 365
CV_LIMIT = 0.25
TUKEY_K = 1.5
DATA_ERROR_FACTOR = 100
RM_REGION = "Región Metropolitana de Santiago"
BASE_UNIT_LABELS = {"u": "unidad", "g": "gramo", "ml": "mililitro", "m": "metro"}


def normalise_unit(value) -> str:
    return " ".join(str(value or "").lower().split())


def base_quantity(text: str) -> tuple[str, float]:
    count = parse_count(text) or 1
    size = parse_any_size(text)
    if size is None:
        return "u", float(count)
    dim, magnitude = size
    return dim, count * magnitude


def _band(prices: list[float]) -> list[float]:
    mean = statistics.fmean(prices)
    sd = statistics.pstdev(prices)
    kept = [p for p in prices if mean - sd <= p <= mean + sd]
    return kept or prices


def cgu_reference(prices: list[float]) -> dict:
    kept = _band(_band(prices))
    mean = statistics.fmean(kept)
    cv = statistics.pstdev(kept) / mean if mean else 0.0
    use_mean = cv <= CV_LIMIT
    return {
        "reference": mean if use_mean else statistics.median(kept),
        "rule": "media" if use_mean else "mediana",
        "cv": cv,
        "kept": len(kept),
    }


def tukey_fence(prices: list[float]) -> tuple[float, float, float]:
    q1, _, q3 = statistics.quantiles(prices, n=4, method="inclusive")
    return q1, q3, q3 + TUKEY_K * (q3 - q1)


def level(price: float, q3: float, fence: float) -> str:
    if price > DATA_ERROR_FACTOR * fence:
        return "error_de_datos"
    if price > fence:
        return "fuera_de_rango"
    if price > q3:
        return "alto"
    return "normal"


def _line_text(row: dict) -> str:
    return " ".join(str(row.get(k) or "") for k in TEXT_COLUMNS)


TEXT_COLUMNS = ("product", "espec_comprador", "espec_proveedor")


def comparable_lines(items: pl.DataFrame) -> pl.DataFrame:
    items = items.with_columns([pl.lit(None, pl.String).alias(c) for c in TEXT_COLUMNS if c not in items.columns])
    lines = (
        items.filter(
            (pl.col("moneda") == "CLP")
            & (pl.col("region") == RM_REGION)
            & pl.col("product_code").is_not_null()
            & (pl.col("unit_price") > 0)
        )
        .unique(["oc_id", "correlativo"], keep="first")
        .with_columns(
            pl.col("fecha").cast(pl.String).str.slice(0, 19)
            .str.to_datetime("%Y-%m-%dT%H:%M:%S", strict=False).alias("at"),
            pl.col("unidad").map_elements(normalise_unit, return_dtype=pl.String).alias("unit"),
            pl.col("product_code").cast(pl.Int64).alias("code"),
        )
        .filter(pl.col("at").is_not_null())
    )
    texts = [_line_text(row) for row in lines.select(TEXT_COLUMNS).iter_rows(named=True)]
    bases = [base_quantity(t) for t in texts]
    return lines.with_columns(
        pl.Series("dim", [b[0] for b in bases], dtype=pl.String),
        pl.Series("base_qty", [b[1] for b in bases], dtype=pl.Float64),
    ).with_columns(
        (pl.col("unit_price") / pl.col("base_qty")).alias("base_price"),
    ).select("oc_id", "correlativo", "at", "code", "unit", "dim", "base_qty", "unit_price", "base_price")


def _round(value: float) -> float:
    return round(value, 2)


def estimate_line(price: float, at: datetime, prices_before: list[float]) -> dict | None:
    if len(prices_before) < MIN_COMPARABLES:
        return None
    ref = cgu_reference(prices_before)
    if ref["cv"] > CV_LIMIT:
        return None
    q1, q3, fence = tukey_fence(prices_before)
    return {
        "method": METHOD,
        "price_clp": _round(price),
        "reference_clp": _round(ref["reference"]),
        "reference_rule": ref["rule"],
        "cv_pct": _round(100 * ref["cv"]),
        "overprice_pct": _round(100 * (price - ref["reference"]) / ref["reference"]),
        "level": level(price, q3, fence),
        "q1_clp": _round(q1),
        "q3_clp": _round(q3),
        "fence_clp": _round(fence),
        "n_comparables": len(prices_before),
        "n_kept": ref["kept"],
        "window_from": (at - timedelta(days=WINDOW_DAYS)).date().isoformat(),
        "window_to": at.date().isoformat(),
        "basis": "neto",
    }


def estimates_for(items: pl.DataFrame, keys: set[tuple[str, int]]) -> dict[tuple[str, int], dict]:
    lines = comparable_lines(items)
    if lines.is_empty() or not keys:
        return {}
    groups = {
        key: frame.sort("at")
        for key, frame in lines.group_by(["code", "unit", "dim"])
    }
    out = {}
    for row in lines.iter_rows(named=True):
        key = (row["oc_id"], row["correlativo"])
        if key not in keys:
            continue
        group = groups[(row["code"], row["unit"], row["dim"])]
        start = row["at"] - timedelta(days=WINDOW_DAYS)
        before = group.filter((pl.col("at") < row["at"]) & (pl.col("at") >= start))["base_price"].to_list()
        est = estimate_line(float(row["base_price"]), row["at"], [float(p) for p in before])
        if est:
            est["base_unit"] = BASE_UNIT_LABELS[row["dim"]]
            est["base_qty"] = row["base_qty"]
            out[key] = est
    return out
