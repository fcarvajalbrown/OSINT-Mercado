import json
from pathlib import Path

from osint_mercado import schema

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_list_fixture_has_envelope():
    data = _load("oc_list_sample.json")
    assert schema.LIST_LISTADO in data
    assert isinstance(data[schema.LIST_LISTADO], list) and data[schema.LIST_LISTADO]


def test_detail_fixture_has_order_fields():
    data = _load("oc_detail_sample.json")
    order = data[schema.LIST_LISTADO][0]
    assert order[schema.OC_CODIGO]
    assert schema.OC_COMPRADOR in order
    assert schema.OC_ITEMS in order
