import json
from pathlib import Path

from osint_mercado import matcher
from osint_mercado.basket import load_basket

BASKET = load_basket("data/basket.json")
LABELED = json.loads(
    (Path(__file__).parent / "fixtures" / "labeled_line_items.json").read_text(encoding="utf-8")
)


def _match(producto="", espec_proveedor="", espec_comprador=""):
    return matcher.match(producto, espec_proveedor, espec_comprador, BASKET)


def test_normalize_strips_accents_lowercases_and_collapses_whitespace():
    assert matcher.normalize("Tóner   HP  85A") == "toner hp 85a"


def test_build_match_text_joins_identity_fields_excluding_category():
    text = matcher.build_match_text("Producto", "EspecProv", "EspecComp")
    assert "producto" in text and "especprov" in text and "especcomp" in text


def test_extintor_positive_matches_by_keyword():
    r = _match(producto="Extintor", espec_proveedor="Extintor PQS ABC 6 kilos certificado")
    assert r.sku_id == "extintor_pqs_6kg"
    assert r.rule == "keyword"


def test_mouse_positive_matches_by_keyword():
    r = _match(producto="Mouse", espec_proveedor="Mouse USB optico Genius negro")
    assert r.sku_id == "mouse_usb"


def test_exclude_keywords_reject_non_steeltoe_and_specialized_footwear():
    # "sin punta acero" (no steel toe) and "soldador" (specialized welder boot) are
    # not the commodity steel-toe SKU, so they must NOT match (QA signal from curation).
    r1 = _match(producto="Zapatos seguridad",
                espec_proveedor="ZAPATOS SEGURIDAD EDELBROCK PVC SIN PUNTA ACERO 42")
    assert r1.sku_id is None
    r2 = _match(producto="Botas de hombre",
                espec_proveedor="BOTA DE SEGURIDAD V-FLEX V301 SOLDADOR ANTICLAVO")
    assert r2.sku_id is None


def test_off_basket_line_item_does_not_match():
    r = _match(producto="Notebook", espec_proveedor="Notebook 15 pulgadas Core i5 8GB RAM")
    assert r.sku_id is None
    assert r.rule == "none"


def test_empty_text_returns_no_match():
    assert _match().sku_id is None


def test_multiple_keyword_candidates_are_disambiguated_by_fuzzy():
    # A line mentioning both AA and AAA fires both battery SKUs (AA substrings AAA);
    # fuzzy disambiguation must resolve to one of them, not error.
    r = _match(producto="Pilas", espec_proveedor="pilas alcalinas AA y AAA pack")
    assert r.sku_id in {"pilas_aa_blister4", "pilas_aaa_blister4"}
    assert r.rule == "keyword+fuzzy"


def test_labeled_sample_precision_is_perfect_and_recall_documented():
    tp = fp = fn = correct_pos = total_pos = 0
    misses = []
    for row in LABELED:
        r = matcher.match(
            row["producto"], row["espec_proveedor"], row["espec_comprador"], BASKET
        )
        expected = row["expected_sku_id"]
        if expected is not None:
            total_pos += 1
            if r.sku_id == expected:
                correct_pos += 1
            else:
                fn += 1
                misses.append((row["producto"], expected, r.sku_id))
        if r.sku_id is not None:
            if r.sku_id == expected:
                tp += 1
            else:
                fp += 1
                misses.append((row["producto"], expected, r.sku_id))

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = correct_pos / total_pos if total_pos else 1.0
    # Precision must be perfect: a false positive is a false public accusation (ADR 0006).
    assert precision == 1.0, f"precision {precision}, offenders={misses}"
    # Recall floor on the labeled positives (documented, per PRD success criteria).
    assert recall >= 0.9, f"recall {recall}, misses={misses}"
