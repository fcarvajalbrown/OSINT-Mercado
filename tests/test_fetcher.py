import json

import pytest
import requests
import responses

from osint_mercado import api_client
from osint_mercado.fetcher import CircuitOpen, Fetcher, QuotaExhausted, UsageLog

OK = {"Cantidad": 0, "Listado": []}


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def make(tmp_path, **kw):
    defaults = dict(session=api_client.make_session(), ticket="T-1", cache_dir=tmp_path / "cache",
                    usage=UsageLog(tmp_path / "usage.log", limit=100, clock=Clock()),
                    sleep=lambda *_: None, rand=lambda a, b: b)
    defaults.update(kw)
    return Fetcher(**defaults)


@responses.activate
def test_detail_is_cached_and_cache_hits_spend_no_quota(tmp_path):
    responses.add(responses.GET, api_client.BASE_URL, json=OK, status=200)
    f = make(tmp_path)
    assert f.get_detail("1-1") == OK
    assert f.get_detail("1-1") == OK
    assert len(responses.calls) == 1
    assert f.usage.count() == 1
    assert json.loads((tmp_path / "cache" / "detail" / "1-1.json").read_text(encoding="utf-8")) == OK


@responses.activate
def test_listing_is_cached_per_date_and_organism(tmp_path):
    responses.add(responses.GET, api_client.BASE_URL, json=OK, status=200)
    f = make(tmp_path)
    f.get_listing("09072026", "9999")
    f.get_listing("09072026", "9999")
    assert len(responses.calls) == 1
    assert (tmp_path / "cache" / "listing" / "09072026_9999.json").exists()


def test_usage_log_stops_at_limit_and_forgets_after_24h(tmp_path):
    clock = Clock()
    log = UsageLog(tmp_path / "usage.log", limit=2, clock=clock)
    log.spend()
    log.spend()
    with pytest.raises(QuotaExhausted):
        log.spend()
    clock.now += 86_401
    log.spend()
    assert log.count() == 1


@responses.activate
def test_quota_is_checked_before_every_attempt_including_retries(tmp_path):
    responses.add(responses.GET, api_client.BASE_URL, status=503)
    f = make(tmp_path, usage=UsageLog(tmp_path / "usage.log", limit=2, clock=Clock()))
    with pytest.raises(QuotaExhausted):
        f.get_detail("1-1")
    assert len(responses.calls) == 2


@responses.activate
def test_retries_5xx_and_timeouts_then_succeeds(tmp_path):
    responses.add(responses.GET, api_client.BASE_URL, status=502)
    responses.add(responses.GET, api_client.BASE_URL, body=requests.Timeout())
    responses.add(responses.GET, api_client.BASE_URL, json=OK, status=200)
    f = make(tmp_path)
    assert f.get_detail("1-1") == OK
    assert len(responses.calls) == 3


@responses.activate
def test_backoff_uses_full_jitter_and_honours_retry_after(tmp_path):
    waits = []
    responses.add(responses.GET, api_client.BASE_URL, status=429, headers={"Retry-After": "7"})
    responses.add(responses.GET, api_client.BASE_URL, status=500)
    responses.add(responses.GET, api_client.BASE_URL, json=OK, status=200)
    f = make(tmp_path, sleep=waits.append, rand=lambda a, b: (a + b) / 2, backoff_base=2.0)
    f.get_detail("1-1")
    assert waits == [7.0, 2.0]


@responses.activate
def test_failure_raises_api_error_and_breaker_opens_after_threshold(tmp_path):
    responses.add(responses.GET, api_client.BASE_URL, status=500)
    f = make(tmp_path, max_retries=1, breaker_threshold=2)
    with pytest.raises(api_client.ApiError):
        f.get_detail("a")
    with pytest.raises(CircuitOpen):
        f.get_detail("b")
    assert not (tmp_path / "cache" / "detail" / "a.json").exists()


@responses.activate
def test_success_resets_the_breaker(tmp_path):
    responses.add(responses.GET, api_client.BASE_URL, status=500)
    responses.add(responses.GET, api_client.BASE_URL, json=OK, status=200)
    responses.add(responses.GET, api_client.BASE_URL, status=500)
    f = make(tmp_path, max_retries=0, breaker_threshold=2)
    with pytest.raises(api_client.ApiError):
        f.get_detail("a")
    f.get_detail("b")
    with pytest.raises(api_client.ApiError):
        f.get_detail("c")


@responses.activate
def test_non_retryable_4xx_fails_without_retry(tmp_path):
    responses.add(responses.GET, api_client.BASE_URL, status=404)
    f = make(tmp_path)
    with pytest.raises(api_client.ApiError):
        f.get_detail("a")
    assert len(responses.calls) == 1
