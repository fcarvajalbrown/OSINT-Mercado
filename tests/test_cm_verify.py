from osint_mercado import cm_verify


def test_clean_single_product_is_clean():
    clean, _ = cm_verify.assess("CAFE INSTANTANEO GOLD TARRO 170 G")
    assert clean is True


def test_red_context_is_not_clean():
    # Reuses verify.py's red-context signals (dispenser, arriendo, industrial, ...).
    assert cm_verify.assess("DISPENSADOR DE JABON LIQUIDO")[0] is False
    assert cm_verify.assess("ARRIENDO DE NOTEBOOK POR MES")[0] is False


def test_bundle_set_is_not_clean():
    # The friend's pen case: a colored SET of 8, not one plain pen.
    clean, reason = cm_verify.assess("SET DE LAPIZ PASTA DE COLORES SET 8 UNIDADES")
    assert clean is False
    assert "bundle" in reason


def test_bundle_multiflavor_enumeration_is_not_clean():
    # The friend's juice case: a multi-flavor, multi-bottle line.
    text = "2 BOTELLAS DE 1.5 LITROS DE JUGOS NECTAR SABORES\n.- PINA\n.- NARANJA\n.- FRUTILLA"
    assert cm_verify.assess(text)[0] is False


def test_unresolved_pack_box_multiplier_is_not_clean():
    # A box/pack line whose multiplier is not a clean per-unit price.
    assert cm_verify.assess("5 CAJAS DE 100 HOJAS CADA CAJA DE OPALINA")[0] is False
    assert cm_verify.assess("PAPEL FOTOCOPIA CARTA 75G RESMAS")[0] is False


def test_reason_is_returned_for_clean():
    clean, reason = cm_verify.assess("PENDRIVE DE 16 GB")
    assert clean is True
    assert isinstance(reason, str) and reason


def test_assess_lead_rejects_when_cm_reference_is_a_bundle():
    # A clean single-product OC line, but the matched CM reference is a 12-colour
    # SET - the per-unit comparison is apples-to-oranges.
    clean, reason = cm_verify.assess_lead(
        "TEMPERA LIQUIDA GIOTTO CAFE 250 G",
        "TEMPERA ESCOLAR GIOTTO 12 COLORES NO TOXICO LAVABLE 15 ML",
    )
    assert clean is False
    assert "reference" in reason


def test_assess_lead_clean_when_both_single_product():
    clean, _ = cm_verify.assess_lead(
        "CAFE INSTANTANEO GOLD TARRO 170 G", "CAFE INSTANTANEO GOLD TARRO 50 G"
    )
    assert clean is True
