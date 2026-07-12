import pytest
import responses
from osint_mercado import api_client


def test_build_list_url_has_fecha_and_ticket():
    url = api_client.build_list_url("09072026", "T-1")
    assert url.startswith(api_client.BASE_URL)
    assert "fecha=09072026" in url
    assert "ticket=T-1" in url


def test_build_detail_url_has_codigo_and_ticket():
    url = api_client.build_detail_url("1234-5-SE20", "T-1")
    assert "codigo=1234-5-SE20" in url
    assert "ticket=T-1" in url


def test_build_by_organism_url_has_all_params():
    url = api_client.build_by_organism_url("09072026", "6945", "T-1")
    assert "fecha=09072026" in url
    assert "CodigoOrganismo=6945" in url
    assert "ticket=T-1" in url


@responses.activate
def test_fetch_json_returns_payload():
    responses.add(responses.GET, api_client.BASE_URL, json={"Cantidad": 0, "Listado": []}, status=200)
    session = api_client.make_session()
    out = api_client.fetch_json(api_client.build_list_url("09072026", "T-1"), session)
    assert out["Cantidad"] == 0


@responses.activate
def test_fetch_json_raises_on_http_error():
    responses.add(responses.GET, api_client.BASE_URL, status=500)
    session = api_client.make_session()
    with pytest.raises(api_client.ApiError):
        api_client.fetch_json(api_client.build_list_url("09072026", "T-1"), session)


@responses.activate
def test_fetch_json_retries_on_429_then_succeeds():
    responses.add(responses.GET, api_client.BASE_URL, status=429)
    responses.add(responses.GET, api_client.BASE_URL, json={"Cantidad": 0, "Listado": []}, status=200)
    session = api_client.make_session()
    out = api_client.fetch_json(api_client.build_list_url("09072026", "T-1"), session,
                                backoff_base=0, sleep=lambda *_: None)
    assert out["Cantidad"] == 0


@responses.activate
def test_fetch_json_raises_after_exhausting_retries():
    for _ in range(6):
        responses.add(responses.GET, api_client.BASE_URL, status=429)
    session = api_client.make_session()
    with pytest.raises(api_client.ApiError):
        api_client.fetch_json(api_client.build_list_url("09072026", "T-1"), session,
                              max_retries=3, backoff_base=0, sleep=lambda *_: None)
