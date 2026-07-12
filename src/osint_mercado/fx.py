"""CLP conversion via mindicador.cl with a date-keyed rate cache.

Implements the currency normalization deferred by ADR 0009. TLS is verified
against the OS trust store because this imports api_client, which calls
truststore.inject_into_ssl() at import (never disable verification).
"""

import json
from datetime import date, timedelta
from pathlib import Path

from osint_mercado import api_client
from osint_mercado import mindicador_schema as ms


def cache_key(indicator: str, on_date: date) -> str:
    return f"{indicator}:{on_date.isoformat()}"


def build_rate_url(indicator: str, on_date: date) -> str:
    # mindicador expects the path date as dd-mm-yyyy.
    return f"{ms.API_BASE}/{indicator}/{on_date.strftime('%d-%m-%Y')}"


def _fetch_valor(indicator: str, on_date: date, session) -> float | None:
    payload = api_client.fetch_json(build_rate_url(indicator, on_date), session)
    serie = payload.get(ms.RESP_SERIE) or []
    if not serie:
        return None
    return float(serie[0][ms.SERIE_VALOR])


def get_rate(
    indicator: str, on_date: date, cache: dict, session, *, max_backfill_days: int = 7
) -> float:
    """Return the indicator's CLP value on `on_date`, cache-first.

    On a cache miss, fetch from mindicador; if the requested date has no
    published value (weekend/holiday for dolar/euro), walk back up to
    `max_backfill_days` to the nearest prior published value. The resolved
    value is cached under the originally-requested date so re-runs are stable.
    """
    key = cache_key(indicator, on_date)
    if key in cache:
        return cache[key]

    probe = on_date
    for _ in range(max_backfill_days + 1):
        valor = _fetch_valor(indicator, probe, session)
        if valor is not None:
            cache[key] = valor
            return valor
        probe = probe - timedelta(days=1)

    raise RuntimeError(
        f"no mindicador {indicator} rate within {max_backfill_days}d of {on_date.isoformat()}"
    )


def to_clp(amount: float, currency_code: str, on_date: date, cache: dict, session) -> float:
    """Convert `amount` in `currency_code` to CLP as of `on_date`.

    CLP passes through unchanged. An unknown currency code raises ValueError
    rather than silently mis-converting.
    """
    if currency_code not in ms.CURRENCY_TO_INDICATOR:
        raise ValueError(f"unknown currency code: {currency_code!r}")
    indicator = ms.CURRENCY_TO_INDICATOR[currency_code]
    if indicator is None:
        return amount
    return amount * get_rate(indicator, on_date, cache, session)


def load_fx_cache(path) -> dict[str, float]:
    p = Path(path)
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {str(k): float(v) for k, v in raw.items()}


def save_fx_cache(cache: dict, path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ordered = dict(sorted(cache.items()))
    p.write_text(json.dumps(ordered, indent=2, ensure_ascii=False), encoding="utf-8")
