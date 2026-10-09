import statistics
from datetime import datetime, timedelta

import polars as pl

METHOD = "cgu-alice-2025+ufmg-tukey-2024"
MIN_COMPARABLES = 10
WINDOW_DAYS = 365
CV_LIMIT = 0.25
TUKEY_K = 1.5
DATA_ERROR_FACTOR = 100
RM_REGION = "Región Metropolitana de Santiago"


def normalise_unit(value) -> str:
    return " ".join(str(value or "").lower().split())


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
        return "sobreprecio"
    if price > q3:
        return "alto"
    return "normal"


def comparable_lines(items: pl.DataFrame) -> pl.DataFrame:
    return (
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
        .select("oc_id", "correlativo", "at", "code", "unit", "unit_price")
    )


def _round(value: float) -> float:
    return round(value, 2)


def estimate_line(price: float, at: datetime, prices_before: list[float]) -> dict | None:
    if len(prices_before) < MIN_COMPARABLES:
        return None
    ref = cgu_reference(prices_before)
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
        (code, unit): frame.sort("at")
        for (code, unit), frame in lines.group_by(["code", "unit"])
    }
    out = {}
    for row in lines.iter_rows(named=True):
        key = (row["oc_id"], row["correlativo"])
        if key not in keys:
            continue
        group = groups[(row["code"], row["unit"])]
        start = row["at"] - timedelta(days=WINDOW_DAYS)
        before = group.filter((pl.col("at") < row["at"]) & (pl.col("at") >= start))["unit_price"].to_list()
        est = estimate_line(float(row["unit_price"]), row["at"], [float(p) for p in before])
        if est:
            out[key] = est
    return out
