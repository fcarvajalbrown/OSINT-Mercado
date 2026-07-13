import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Sku:
    sku_id: str
    canonical_name: str
    keywords: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    unit: str = ""
    category: str = ""
    unspsc_category_code: int = 0
    unspsc_product_code: int = 0
    # Unit-normalization base (see units.py + scoring.py). A SKU is either
    # count-based (baseline price is for `base_count` items; default 1) or
    # size-based (baseline price is for `base_size` of `base_dim`, one of
    # ml/g/m). base_dim != "" selects size-based normalization.
    base_count: int = 1
    base_size: float = 0.0
    base_dim: str = ""


@dataclass(frozen=True)
class PriceObservation:
    sku_id: str
    retailer: str
    price_clp: float
    observed_at: str
    url: str


def load_basket(path) -> list[Sku]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Sku(
            sku_id=row["sku_id"],
            canonical_name=row["canonical_name"],
            keywords=list(row.get("keywords") or []),
            exclude=list(row.get("exclude") or []),
            unit=row.get("unit", ""),
            category=row.get("category", ""),
            unspsc_category_code=int(row.get("unspsc_category_code") or 0),
            unspsc_product_code=int(row.get("unspsc_product_code") or 0),
            base_count=int(row.get("base_count") or 1),
            base_size=float(row.get("base_size") or 0.0),
            base_dim=row.get("base_dim", ""),
        )
        for row in rows
    ]


def load_seed_observations(path) -> list[PriceObservation]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        PriceObservation(
            sku_id=row["sku_id"],
            retailer=row["retailer"],
            price_clp=float(row["price_clp"]),
            observed_at=row["observed_at"],
            url=row["url"],
        )
        for row in rows
    ]
