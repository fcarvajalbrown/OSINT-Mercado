import datetime as dt

import pytest
import responses

from osint_mercado import api_client, fx

D = dt.date(2026, 6, 9)


def _session():
    return api_client.make_session()


def _serie(valor):
    return {
        "version": "1.7.0",
        "codigo": "uf",
        "serie": [{"fecha": "2026-06-09T04:00:00.000Z", "valor": valor}],
    }


def test_cache_key_format():
    assert fx.cache_key("uf", D) == "uf:2026-06-09"


def test_build_rate_url_uses_dd_mm_yyyy():
    assert fx.build_rate_url("uf", D) == "https://mindicador.cl/api/uf/09-06-2026"


@responses.activate
def test_get_rate_cache_hit_makes_no_request():
    cache = {"uf:2026-06-09": 39179.0}
    assert fx.get_rate("uf", D, cache, _session()) == 39179.0
    assert len(responses.calls) == 0


@responses.activate
def test_get_rate_cache_miss_fetches_and_stores():
    responses.add(responses.GET, fx.build_rate_url("uf", D), json=_serie(39179.0), status=200)
    cache = {}
    assert fx.get_rate("uf", D, cache, _session()) == 39179.0
    assert cache["uf:2026-06-09"] == 39179.0


@responses.activate
def test_get_rate_walks_back_to_prior_business_day():
    sunday = dt.date(2026, 6, 7)
    responses.add(responses.GET, fx.build_rate_url("dolar", sunday), json={"serie": []}, status=200)
    responses.add(
        responses.GET, fx.build_rate_url("dolar", dt.date(2026, 6, 6)),
        json={"serie": []}, status=200,
    )
    responses.add(
        responses.GET, fx.build_rate_url("dolar", dt.date(2026, 6, 5)),
        json=_serie(950.5), status=200,
    )
    cache = {}
    assert fx.get_rate("dolar", sunday, cache, _session()) == 950.5
    # Cached under the originally-requested date, for re-run stability.
    assert cache["dolar:2026-06-07"] == 950.5


@responses.activate
def test_get_rate_raises_when_no_value_in_window():
    for i in range(8):
        d = D - dt.timedelta(days=i)
        responses.add(responses.GET, fx.build_rate_url("uf", d), json={"serie": []}, status=200)
    with pytest.raises(RuntimeError):
        fx.get_rate("uf", D, {}, _session(), max_backfill_days=7)


@responses.activate
def test_to_clp_passthrough_for_clp():
    cache = {}
    assert fx.to_clp(1000.0, "CLP", D, cache, _session()) == 1000.0
    assert len(responses.calls) == 0


@responses.activate
def test_to_clp_converts_uf_amount():
    responses.add(responses.GET, fx.build_rate_url("uf", D), json=_serie(39000.0), status=200)
    assert fx.to_clp(2.0, "CLF", D, {}, _session()) == 78000.0


def test_to_clp_unknown_currency_raises():
    with pytest.raises(ValueError):
        fx.to_clp(1.0, "XYZ", D, {}, None)


def test_cache_roundtrip(tmp_path):
    p = tmp_path / "fx_rates.json"
    fx.save_fx_cache({"uf:2026-06-09": 39179.0}, p)
    assert fx.load_fx_cache(p) == {"uf:2026-06-09": 39179.0}


def test_load_missing_cache_returns_empty(tmp_path):
    assert fx.load_fx_cache(tmp_path / "nope.json") == {}
