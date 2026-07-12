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
