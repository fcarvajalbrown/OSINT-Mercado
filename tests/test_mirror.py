import copy
import json

from osint_mercado import integrity, mirror

CONTACT = {"NombreContacto": "Ana", "CargoContacto": "Jefa", "FonoContacto": "22", "MailContacto": "a@x.cl"}
RAW = {
    "Cantidad": 1,
    "Listado": [{
        "Codigo": "1-1",
        "Comprador": {"NombreOrganismo": "Municipalidad", **CONTACT},
        "Proveedor": {"Nombre": "Proveedor SpA", **CONTACT},
        "Items": {"Listado": [{"Correlativo": 1, "PrecioNeto": 7800.0}]},
    }],
}
NOW = "2026-10-09T21:15:00+00:00"


def test_redact_blanks_only_contact_fields_and_keeps_the_original():
    original = copy.deepcopy(RAW)
    out = mirror.redact(RAW)
    order = out["Listado"][0]
    for side in ("Comprador", "Proveedor"):
        assert all(order[side][k] is None for k in CONTACT)
    assert order["Comprador"]["NombreOrganismo"] == "Municipalidad"
    assert order["Proveedor"]["Nombre"] == "Proveedor SpA"
    assert order["Items"] == RAW["Listado"][0]["Items"]
    assert RAW == original


def test_redact_drops_free_text_description_and_masks_emails_and_phones():
    raw = copy.deepcopy(RAW)
    raw["Listado"][0]["Descripcion"] = "coordinar con ANA PEREZ correo: ana.perez@muni.cl fono 228290846"
    raw["Listado"][0]["Items"]["Listado"][0]["EspecificacionProveedor"] = (
        "Pendrive 16GB, consultas a ventas@proveedor.cl o +56 9 8765 4321, OC 600/00155/2026"
    )
    out = mirror.redact(raw)["Listado"][0]
    assert out["Descripcion"] is None
    spec = out["Items"]["Listado"][0]["EspecificacionProveedor"]
    assert "ventas@proveedor.cl" not in spec
    assert "8765" not in spec
    assert "600/00155/2026" in spec
    assert spec.startswith("Pendrive 16GB")


def test_public_copy_carries_hash_of_untouched_record():
    doc = mirror.public_copy("1-1", RAW, NOW)
    assert doc["oc_id"] == "1-1"
    assert doc["fetched_at"] == NOW
    assert doc["raw_sha256"] == integrity.leaf(RAW)
    assert doc["record"] == mirror.redact(RAW)
    assert "ticket" not in doc["source"]


def test_mirror_orders_writes_raw_and_public_and_never_overwrites(tmp_path):
    calls = []

    def fetch(oc_id):
        calls.append(oc_id)
        return RAW

    written = mirror.mirror_orders(["1-1"], fetch, tmp_path, lambda: NOW)
    assert written == ["1-1"]
    raw = json.loads((tmp_path / "raw" / "1-1.json").read_text(encoding="utf-8"))
    pub = json.loads((tmp_path / "public" / "1-1.json").read_text(encoding="utf-8"))
    assert raw == RAW
    assert pub["raw_sha256"] == integrity.leaf(RAW)

    assert mirror.mirror_orders(["1-1"], fetch, tmp_path, lambda: "later") == []
    assert calls == ["1-1"]


def test_rebuild_public_reapplies_redaction_and_keeps_capture_time(tmp_path):
    mirror.mirror_orders(["1-1"], lambda _oc: RAW, tmp_path, lambda: NOW)
    public = tmp_path / "public" / "1-1.json"
    stale = json.loads(public.read_text(encoding="utf-8"))
    stale["record"] = RAW
    public.write_text(json.dumps(stale), encoding="utf-8")
    assert mirror.rebuild_public(tmp_path) == ["1-1"]
    rebuilt = json.loads(public.read_text(encoding="utf-8"))
    assert rebuilt == mirror.public_copy("1-1", RAW, NOW)


def test_attach_mirrors_hashes_public_copy_into_flag(tmp_path):
    mirror.mirror_orders(["1-1"], lambda _oc: RAW, tmp_path, lambda: NOW)
    flags = [{"id": "a", "oc_id": "1-1"}, {"id": "b", "oc_id": "9-9"}]
    out, mirrors = integrity.attach_mirrors(flags, tmp_path / "public")
    assert out[0]["mirror_sha256"] == integrity.leaf(mirrors["1-1"])
    assert "mirror_sha256" not in out[1]
    assert set(mirrors) == {"1-1"}
