import argparse
import json
from datetime import date
from pathlib import Path

from osint_mercado.basket import load_basket, load_seed_observations
from osint_mercado.baseline import compute_reference


def build(basket_path, seed_prices_path, as_of: date) -> list[dict]:
    skus = load_basket(basket_path)
    observations = load_seed_observations(seed_prices_path)

    by_sku: dict[str, list] = {}
    for obs in observations:
        by_sku.setdefault(obs.sku_id, []).append(obs)

    baselines = [
        compute_reference(sku.sku_id, by_sku.get(sku.sku_id, []), as_of)
        for sku in skus
    ]
    return [
        {
            "sku_id": b.sku_id,
            "reference_price_clp": b.reference_price_clp,
            "confidence": b.confidence,
            "n_observations": b.n_observations,
            "freshest_observed_at": b.freshest_observed_at,
            "spread_ratio": b.spread_ratio,
        }
        for b in baselines
    ]


def write_baselines(rows: list[dict], path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute retail baselines for the controlled basket")
    ap.add_argument("--basket", default="data/basket.json")
    ap.add_argument("--seed-prices", default="data/seed_prices.json")
    ap.add_argument("--out", default="data/baselines.json")
    args = ap.parse_args()
    rows = build(args.basket, args.seed_prices, date.today())
    write_baselines(rows, args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
