from osint_mercado import cm_catalog

# A minimal CSV mirroring the real MaestraProd inner file (comma-delimited, the
# 20-column ChileCompra header). One METROPOLITANA row, one NACIONAL row, one
# other-region row (must be dropped), one code=0 row, one blank-price row.
HEADER = (
    "CONVENIO MARCO,NÚMERO LICITACIÓN,ID CONVENIO MARCO,ID PROVEEDOR,"
    "NOMBRE PROVEEDOR,RUT PROVEEDOR,ID PRODUCTO,CÓDIGO ONU,PRODUCTO,"
    "ID TIPO PRODUCTO,TIPO PRODUCTO,REGIÓN,MARCA,MODELO,MEDIDA,STOCK,"
    "PRECIO EN TIENDA,PRECIO REGULAR,PRECIO OFERTA,FECHA EJECUCIÓN"
)


def _row(region, code, producto, marca, modelo, medida, precio, prov="ABASTIBLE S.A."):
    return (
        f"GAS,2239-1-LR25,5802379,26592,{prov},91.806.000-6,4510558,{code},"
        f"{producto},10010,TIPO,{region},{marca},{modelo},{medida},SI,"
        f"{precio},{precio},,2026-07-13"
    )


def _csv(*rows):
    return "\n".join([HEADER, *rows])


def test_normalize_row_keeps_metropolitana():
    text = _csv(_row("METROPOLITANA", "15111510", "GAS LICUADO 11 KG", "-", "11 KG", "11 KG", "14368"))
    recs = cm_catalog.parse_catalog_csv(text)
    assert len(recs) == 1
    r = recs[0]
    assert r["code"] == "15111510"
    assert r["region"] == "METROPOLITANA"
    assert r["producto"] == "GAS LICUADO 11 KG"
    assert r["precio_neto"] == 14368.0
    assert r["proveedor"] == "ABASTIBLE S.A."


def test_keeps_nacional_drops_other_regions():
    text = _csv(
        _row("NACIONAL", "44121701", "LAPIZ PASTA AZUL", "BIC", "GRUESA", "UNIDAD", "300"),
        _row("VALPARAÍSO", "44121701", "LAPIZ PASTA AZUL", "BIC", "GRUESA", "UNIDAD", "300"),
        _row("TARAPACÁ", "44121701", "LAPIZ PASTA AZUL", "BIC", "GRUESA", "UNIDAD", "300"),
    )
    recs = cm_catalog.parse_catalog_csv(text)
    assert [r["region"] for r in recs] == ["NACIONAL"]


def test_drops_zero_code_and_nonpositive_price():
    text = _csv(
        _row("METROPOLITANA", "0", "SERVICIO SIN CODIGO", "-", "-", "-", "5000"),
        _row("METROPOLITANA", "", "SERVICIO SIN CODIGO", "-", "-", "-", "5000"),
        _row("METROPOLITANA", "15111510", "GAS 11 KG", "-", "11 KG", "11 KG", "0"),
        _row("METROPOLITANA", "15111510", "GAS 11 KG", "-", "11 KG", "11 KG", ""),
    )
    assert cm_catalog.parse_catalog_csv(text) == []


def test_descriptive_text_combines_identity_fields():
    rec = {"producto": "CAFE INSTANTANEO GOLD", "marca": "NESCAFE",
           "modelo": "TARRO", "medida": "170 G"}
    text = cm_catalog.descriptive_text(rec)
    assert "cafe" in text.lower()
    assert "170 g" in text.lower()
    assert "nescafe" in text.lower()


def test_dedup_collapses_identical_offers():
    r = {"code": "15111510", "region": "METROPOLITANA", "producto": "GAS 11 KG",
         "marca": "-", "modelo": "11 KG", "medida": "11 KG", "proveedor": "ABASTIBLE S.A.",
         "rut": "91.806.000-6", "precio_neto": 14368.0}
    out = cm_catalog.dedup([dict(r), dict(r), {**r, "precio_neto": 13408.0}])
    assert len(out) == 2
