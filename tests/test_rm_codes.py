import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "rm_municipal_codes.json"

REQUIRED_KEYS = ("comuna", "nombre_organismo", "codigo_organismo")


def _load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_rm_codes_file_is_non_empty_list():
    data = _load()
    assert isinstance(data, list)
    assert len(data) > 0


def test_rm_codes_entries_have_required_non_empty_string_fields():
    data = _load()
    for entry in data:
        assert isinstance(entry, dict)
        for key in REQUIRED_KEYS:
            assert key in entry
            assert isinstance(entry[key], str)
            assert entry[key].strip() != ""


def test_rm_codes_codigo_organismo_values_are_unique():
    data = _load()
    codes = [entry["codigo_organismo"] for entry in data]
    assert len(codes) == len(set(codes))
