import json
import logging
import os
import random
import time
from pathlib import Path

import requests

from osint_mercado import api_client
from osint_mercado.api_client import ApiError

logger = logging.getLogger(__name__)

DAY_SECONDS = 86_400
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class QuotaExhausted(RuntimeError):
    pass


class CircuitOpen(RuntimeError):
    pass


class UsageLog:
    def __init__(self, path, limit: int, clock=time.time):
        self.path = Path(path)
        self.limit = limit
        self.clock = clock

    def _recent(self) -> list[float]:
        if not self.path.exists():
            return []
        cutoff = self.clock() - DAY_SECONDS
        stamps = [float(x) for x in self.path.read_text(encoding="utf-8").split()]
        return [s for s in stamps if s > cutoff]

    def count(self) -> int:
        return len(self._recent())

    def spend(self) -> None:
        recent = self._recent()
        if len(recent) >= self.limit:
            raise QuotaExhausted(f"{len(recent)} API requests in the last 24 h (limit {self.limit})")
        recent.append(self.clock())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(f"{s:.3f}" for s in recent) + "\n", encoding="utf-8")


class Fetcher:
    def __init__(self, session, ticket: str, cache_dir, usage: UsageLog, *, max_retries=4,
                 backoff_base=1.0, max_delay=60.0, breaker_threshold=5, pace_seconds=0.0,
                 sleep=time.sleep, rand=random.uniform):
        self.session = session
        self.ticket = ticket
        self.cache_dir = Path(cache_dir)
        self.usage = usage
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.max_delay = max_delay
        self.breaker_threshold = breaker_threshold
        self.pace_seconds = pace_seconds
        self.sleep = sleep
        self.rand = rand
        self.consecutive_failures = 0

    def get_detail(self, codigo: str) -> dict:
        return self._cached(self.cache_dir / "detail" / f"{codigo}.json",
                            api_client.build_detail_url(codigo, self.ticket))

    def get_listing(self, fecha: str, codigo_organismo: str) -> dict:
        return self._cached(self.cache_dir / "listing" / f"{fecha}_{codigo_organismo}.json",
                            api_client.build_by_organism_url(fecha, codigo_organismo, self.ticket))

    def _cached(self, path: Path, url: str) -> dict:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        data = self._request(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        return data

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after and retry_after.isdigit():
            return float(retry_after)
        return self.rand(0, min(self.max_delay, self.backoff_base * (2 ** attempt)))

    def _request(self, url: str) -> dict:
        attempt = 0
        while True:
            self.usage.spend()
            retry_after = None
            try:
                resp = self.session.get(url, timeout=(10, 60))
                status = resp.status_code
                if status < 400:
                    data = resp.json()
                    self.consecutive_failures = 0
                    if self.pace_seconds:
                        self.sleep(self.pace_seconds)
                    return data
                retry_after = resp.headers.get("Retry-After")
                resp.close()
                if status not in RETRYABLE_STATUS:
                    raise ApiError(f"OC API request failed: HTTP {status}")
                reason = f"HTTP {status}"
            except (requests.Timeout, requests.ConnectionError) as exc:
                reason = type(exc).__name__
            except (requests.RequestException, ValueError) as exc:
                raise ApiError(f"OC API request failed: {type(exc).__name__}") from exc
            if attempt >= self.max_retries:
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.breaker_threshold:
                    raise CircuitOpen(f"{self.consecutive_failures} consecutive failed requests, last: {reason}")
                raise ApiError(f"OC API request failed after {attempt + 1} attempts: {reason}")
            delay = self._delay(attempt, retry_after)
            logger.warning("retry %d after %s, waiting %.1f s", attempt + 1, reason, delay)
            self.sleep(delay)
            attempt += 1
