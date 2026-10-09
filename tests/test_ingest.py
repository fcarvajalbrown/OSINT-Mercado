import json
from pathlib import Path

import polars as pl
import responses

from osint_mercado import api_client, ingest, schema

FIX = Path(__file__).parent / "fixtures"


def _detail_payload():
    return json.loads((FIX / "oc_detail_sample.json").read_text(encoding="utf-8"))


@responses.activate
def test_run_writes_municipal_items(tmp_path):
    detail = _detail_payload()
    detail[schema.LIST_LISTADO][0][schema.OC_COMPRADOR][schema.COMPRADOR_NOMBRE] = "Municipalidad de Test"
    codigo = detail[schema.LIST_LISTADO][0][schema.OC_CODIGO]
    listing = {schema.LIST_CANTIDAD: 1, schema.LIST_LISTADO: [{schema.OC_CODIGO: codigo}]}
    responses.add(responses.GET, api_client.BASE_URL, json=listing, status=200)   # by-organism
    responses.add(responses.GET, api_client.BASE_URL, json=detail, status=200)    # detail

    codes_file = tmp_path / "codes.json"
    codes_file.write_text(json.dumps(
        [{"comuna": "Test", "nombre_organismo": "MUNICIPALIDAD DE TEST", "codigo_organismo": "9999"}]),
        encoding="utf-8")

    out = ingest.run(fecha="09072026", out_dir=tmp_path, ticket="T-1",
                     codes_path=codes_file, session=api_client.make_session())
    df = pl.read_parquet(out)
    assert df.height >= 1
    assert df.row(0, named=True)["buyer_name"].startswith("Municipalidad")


@responses.activate
def test_run_tolerates_failed_detail(tmp_path):
    detail = _detail_payload()
    detail[schema.LIST_LISTADO][0][schema.OC_COMPRADOR][schema.COMPRADOR_NOMBRE] = "Municipalidad de Test"
    good_code = detail[schema.LIST_LISTADO][0][schema.OC_CODIGO]
    listing = {schema.LIST_CANTIDAD: 2,
               schema.LIST_LISTADO: [{schema.OC_CODIGO: "BAD-1"}, {schema.OC_CODIGO: good_code}]}
    responses.add(responses.GET, api_client.BASE_URL, json=listing, status=200)  # by-organism
    responses.add(responses.GET, api_client.BASE_URL, status=500)                # BAD-1 detail -> ApiError
    responses.add(responses.GET, api_client.BASE_URL, json=detail, status=200)   # good detail
    codes_file = tmp_path / "codes.json"
    codes_file.write_text(json.dumps(
        [{"comuna": "Test", "nombre_organismo": "X", "codigo_organismo": "9999"}]), encoding="utf-8")
    out = ingest.run(fecha="09072026", out_dir=tmp_path, ticket="T-1",
                     codes_path=codes_file, session=api_client.make_session())
    df = pl.read_parquet(out)
    assert df.height >= 1  # good order survived despite the failed one


@responses.activate
def test_max_per_organism_caps_each_municipality(tmp_path):
    base = _detail_payload()

    def muni_detail(code, name):
        d = json.loads(json.dumps(base))
        d[schema.LIST_LISTADO][0][schema.OC_CODIGO] = code
        d[schema.LIST_LISTADO][0][schema.OC_COMPRADOR][schema.COMPRADOR_NOMBRE] = name
        return d

    responses.add(responses.GET, api_client.BASE_URL,
                  json={schema.LIST_LISTADO: [{schema.OC_CODIGO: "A1"}, {schema.OC_CODIGO: "A2"}]}, status=200)
    responses.add(responses.GET, api_client.BASE_URL,
                  json={schema.LIST_LISTADO: [{schema.OC_CODIGO: "B1"}, {schema.OC_CODIGO: "B2"}]}, status=200)
    responses.add(responses.GET, api_client.BASE_URL, json=muni_detail("A1", "Municipalidad A"), status=200)
    responses.add(responses.GET, api_client.BASE_URL, json=muni_detail("B1", "Municipalidad B"), status=200)
    codes_file = tmp_path / "codes.json"
    codes_file.write_text(json.dumps([
        {"comuna": "A", "nombre_organismo": "MA", "codigo_organismo": "1"},
        {"comuna": "B", "nombre_organismo": "MB", "codigo_organismo": "2"},
    ]), encoding="utf-8")
    out = ingest.run(fecha="09072026", out_dir=tmp_path, ticket="T-1", codes_path=codes_file,
                     session=api_client.make_session(), max_per_organism=1)
    df = pl.read_parquet(out)
    buyers = set(df["buyer_name"].to_list())
    assert any(b.startswith("Municipalidad A") for b in buyers)
    assert any(b.startswith("Municipalidad B") for b in buyers)


@responses.activate
def test_run_drops_cancelled_orders(tmp_path):
    detail = _detail_payload()
    detail[schema.LIST_LISTADO][0][schema.OC_COMPRADOR][schema.COMPRADOR_NOMBRE] = "Municipalidad de Test"
    detail[schema.LIST_LISTADO][0][schema.OC_CODIGO_ESTADO] = 9
    codigo = detail[schema.LIST_LISTADO][0][schema.OC_CODIGO]
    listing = {schema.LIST_CANTIDAD: 1, schema.LIST_LISTADO: [{schema.OC_CODIGO: codigo}]}
    responses.add(responses.GET, api_client.BASE_URL, json=listing, status=200)
    responses.add(responses.GET, api_client.BASE_URL, json=detail, status=200)

    codes_file = tmp_path / "codes.json"
    codes_file.write_text(json.dumps(
        [{"comuna": "Test", "nombre_organismo": "MUNICIPALIDAD DE TEST", "codigo_organismo": "9999"}]),
        encoding="utf-8")

    out = ingest.run(fecha="09072026", out_dir=tmp_path, ticket="T-1",
                     codes_path=codes_file, session=api_client.make_session())
    df = pl.read_parquet(out)
    assert df.height == 0


class FakeFetcher:
    def __init__(self, listing, details, fail=(), raise_on=None):
        self.listing = listing
        self.details = details
        self.fail = set(fail)
        self.raise_on = raise_on

    def get_listing(self, fecha, org):
        return self.listing

    def get_detail(self, codigo):
        if self.raise_on and codigo == self.raise_on[0]:
            raise self.raise_on[1]
        if codigo in self.fail:
            raise api_client.ApiError("boom")
        return self.details[codigo]


def _one_org(tmp_path):
    codes_file = tmp_path / "codes.json"
    codes_file.write_text(json.dumps(
        [{"comuna": "Test", "nombre_organismo": "X", "codigo_organismo": "9999"}]), encoding="utf-8")
    return codes_file


def _fetcher_case(**kw):
    detail = _detail_payload()
    detail[schema.LIST_LISTADO][0][schema.OC_COMPRADOR][schema.COMPRADOR_NOMBRE] = "Municipalidad de Test"
    good = detail[schema.LIST_LISTADO][0][schema.OC_CODIGO]
    listing = {schema.LIST_CANTIDAD: 2, schema.LIST_LISTADO: [{schema.OC_CODIGO: "BAD-1"}, {schema.OC_CODIGO: good}]}
    return FakeFetcher(listing, {good: detail}, **kw)


def test_run_with_fetcher_records_gaps_for_failed_requests(tmp_path):
    out = ingest.run(fecha="09072026", out_dir=tmp_path, ticket="T-1", codes_path=_one_org(tmp_path),
                     fetcher=_fetcher_case(fail={"BAD-1"}))
    assert pl.read_parquet(out).height >= 1
    gaps = json.loads((tmp_path / "oc_items_09072026.gaps.json").read_text(encoding="utf-8"))
    assert gaps == [{"kind": "detail", "codigo": "BAD-1"}]


def test_clean_run_removes_a_stale_gaps_file(tmp_path):
    stale = tmp_path / "oc_items_09072026.gaps.json"
    stale.write_text("[]", encoding="utf-8")
    case = _fetcher_case()
    case.details["BAD-1"] = case.details[next(iter(case.details))]
    ingest.run(fecha="09072026", out_dir=tmp_path, ticket="T-1", codes_path=_one_org(tmp_path), fetcher=case)
    assert not stale.exists()


def test_breaker_or_quota_stop_writes_no_day_file(tmp_path):
    import pytest
    from osint_mercado.fetcher import CircuitOpen

    with pytest.raises(CircuitOpen):
        ingest.run(fecha="09072026", out_dir=tmp_path, ticket="T-1", codes_path=_one_org(tmp_path),
                   fetcher=_fetcher_case(raise_on=("BAD-1", CircuitOpen("open"))))
    assert not (tmp_path / "oc_items_09072026.parquet").exists()
