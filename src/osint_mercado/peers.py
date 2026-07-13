"""Peer-price anomaly core (ADR 0018).

Where the controlled-basket engine compares a purchase to a hand-researched retail
baseline (ADR 0005/0013), the peer engine compares it to *what other public buyers
paid for the same catalogued product* on Mercado Publico itself. The market is its
own baseline: no retail research, so it covers the whole catalogue - including the
big-ticket construction/services spend the commodity basket can never price.

For each product code, the peer distribution's median and MAD (median absolute
deviation - robust to the very outliers we hunt) define "normal". A line is flagged
when it is both statistically extreme (robust z) and materially above the median
(ratio), and only within product codes that have enough peers to be meaningful.
Deterministic: no randomness, no network (currency conversion happens upstream).
"""

from dataclasses import dataclass

from osint_mercado import scoring

# A product code needs at least this many peer observations before its median is
# trustworthy enough to accuse anyone of overpaying against it.
MIN_PEERS = 5

# Flag only lines that are BOTH robustly extreme and materially above the median.
Z_THRESHOLD = 3.5
MIN_RATIO = 1.5  # must clear at least the Watch tier over the peer median
# Above this multiple of the peer median, the line is almost never a real overprice
# but a scope/unit artifact (a whole contract vs a per-unit job under one product
# code). Route it out rather than publish an implausible accusation.
RATIO_CAP = 12.0

_MAD_TO_SIGMA = 0.6745  # 0.6745 = Phi^-1(0.75); scales MAD to a normal-sigma estimate


def median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def mad(values: list[float]) -> float:
    """Median absolute deviation from the median."""
    if not values:
        return 0.0
    med = median(values)
    return median([abs(v - med) for v in values])


def robust_z(x: float, med: float, mad_value: float) -> float:
    if mad_value == 0:
        return 0.0
    return _MAD_TO_SIGMA * (x - med) / mad_value


@dataclass(frozen=True)
class PeerStat:
    product_code: str
    product_name: str
    median_clp: float
    mad_clp: float
    n: int


@dataclass(frozen=True)
class PeerHit:
    ratio: float
    robust_z: float
    severity: str


def build_peer_stats(rows: list[tuple[str, str, float]]) -> dict[str, PeerStat]:
    """rows = (product_code, product_name, unit_price_clp_gross).

    Returns one PeerStat per product code with at least MIN_PEERS observations.
    """
    grouped: dict[str, list[float]] = {}
    names: dict[str, str] = {}
    for code, name, price in rows:
        if not code or code == "0":
            continue
        grouped.setdefault(code, []).append(price)
        names.setdefault(code, name)
    stats: dict[str, PeerStat] = {}
    for code, prices in grouped.items():
        if len(prices) < MIN_PEERS:
            continue
        stats[code] = PeerStat(
            product_code=code, product_name=names[code],
            median_clp=median(prices), mad_clp=mad(prices), n=len(prices),
        )
    return stats


def classify(price: float, stat: PeerStat) -> PeerHit | None:
    """Flag `price` as a peer outlier above `stat`, or None if it is in line.

    Requires the price to be both materially above the median (ratio >= MIN_RATIO)
    and, when the peer spread is non-zero, robustly extreme (z >= Z_THRESHOLD).
    Cheaper-than-peers is never an overprice.
    """
    if stat.median_clp <= 0 or price <= stat.median_clp:
        return None
    ratio = round(price / stat.median_clp, 4)
    if ratio < MIN_RATIO or ratio > RATIO_CAP:
        return None
    z = robust_z(price, stat.median_clp, stat.mad_clp)
    if stat.mad_clp > 0 and z < Z_THRESHOLD:
        return None
    sev = scoring.severity(ratio)
    if sev is None:
        return None
    return PeerHit(ratio=ratio, robust_z=round(z, 2), severity=sev)
