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
