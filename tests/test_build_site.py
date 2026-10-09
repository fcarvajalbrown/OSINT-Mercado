import hashlib
import json

from osint_mercado import build_site
from osint_mercado.basket import load_basket

SKUS = load_basket("data/basket.json")

CONFIRMED = [
    {"id": "x1", "comuna": "Nunoa", "sku_id": "mouse_usb", "oc_id": "1-1", "correlativo": 1,
     "unit_price_clp_gross": 11900.0, "reference_price_clp": 3651.0, "overprice_ratio": 3.26,
     "severity": "severe", "status": "confirmed", "oc_url": "http://x/1",
     "reviewed_at": "2026-07-12", "curation_note": "real"},
]


def test_build_flags_enriches_with_name_category_and_pct():
    flags = build_site.build_flags(CONFIRMED, SKUS)
    f = flags[0]
    assert f["canonical_name"] == "Mouse óptico USB"
    assert f["category"] == "Oficina y computación"
    assert f["overprice_pct"] == 226  # round((3.26 - 1) * 100)
    assert f["comuna"] == "Nunoa"
    assert f["oc_url"] == "http://x/1"


def test_build_flags_empty_input():
    assert build_site.build_flags([], SKUS) == []


def test_build_writes_site(tmp_path):
    confirmed = tmp_path / "confirmed.json"
    confirmed.write_text(json.dumps(CONFIRMED), encoding="utf-8")
    out = tmp_path / "dist"
    build_site.build(confirmed, "data/basket.json", "frontend", out)
    assert (out / "index.html").exists()
    assert (out / "app.js").exists()
    assert (out / "styles.css").exists()
    data = json.loads((out / "data" / "flags.json").read_text(encoding="utf-8"))
    assert data[0]["canonical_name"] == "Mouse óptico USB"
    assert json.loads((out / "data" / "sources.json").read_text(encoding="utf-8")) == {}


def test_build_is_deterministic(tmp_path):
    confirmed = tmp_path / "confirmed.json"
    confirmed.write_text(json.dumps(CONFIRMED), encoding="utf-8")
    out = tmp_path / "dist"
    build_site.build(confirmed, "data/basket.json", "frontend", out)
    first = (out / "data" / "flags.json").read_bytes()
    build_site.build(confirmed, "data/basket.json", "frontend", out)
    assert (out / "data" / "flags.json").read_bytes() == first


def test_fingerprint_assets_versions_local_css_js_and_svg(tmp_path):
    (tmp_path / "styles.css").write_text("a{}", encoding="utf-8")
    (tmp_path / "app.js").write_text("1", encoding="utf-8")
    (tmp_path / "index.html").write_text(
        '<link href="./styles.css"><script src="./app.js"></script>'
        '<a href="./data/flags.json"></a><a href="./stellar.html"></a><script src="./missing.js"></script>',
        encoding="utf-8",
    )
    build_site.fingerprint_assets(tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    css_v = hashlib.sha256(b"a{}").hexdigest()[:10]
    assert f'href="./styles.css?v={css_v}"' in html
    assert 'src="./app.js?v=' in html
    assert 'href="./data/flags.json"' in html
    assert 'href="./stellar.html"' in html
    assert 'src="./missing.js"' in html
