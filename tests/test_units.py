from osint_mercado import units


# ---- parse_count: how many base items the priced unit bundles ----

def test_pack_de_n():
    assert units.parse_count("PACK DE 4 UNIDADES DESTACADORES DE COLORES") == 4


def test_caja_de_n_unidades():
    assert units.parse_count("LAPIZ TINTA SUPER GEL AZUL, CAJA DE 12 UNIDADES") == 12


def test_set_de_n_colores():
    assert units.parse_count("Set de Plumones permanentes de 4 colores") == 4


def test_n_unidades_plain():
    assert units.parse_count("24 unidades de galletas de 126 gramos") == 24


def test_n_bolsas_for_tea_box():
    assert units.parse_count("TE SUPREMO NEGRO ARGENTINA CAJA 100 BOLSAS") == 100


def test_corchetes_thousands():
    assert units.parse_count("CORCHETE 26/6 1000 UNIDADES") == 1000


def test_no_count_returns_none():
    assert units.parse_count("Cartulina de colores espanola") is None


def test_size_measure_is_not_a_count():
    # "500 cc" / "74 cm" / "15 kg" must not be read as pack counts.
    assert units.parse_count("agua mineral de 500 cc") is None
    assert units.parse_count("PALA ASEO PLASTICA CON MANGO DE 74 cm") is None
    assert units.parse_count("GAS LICUADO VALE DE RECARGA 15 KG") is None


# ---- parse_size_in_dim: magnitude in a target dimension (ml / g / m) ----

def test_size_cc_to_ml():
    assert units.parse_size_in_dim("aerosol frutos del bosque 360 ml", "ml") == 360.0
    assert units.parse_size_in_dim("agua con gas de 500 cc", "ml") == 500.0


def test_size_litres_to_ml_with_decimal_comma():
    assert units.parse_size_in_dim("bebida 1,5 lt", "ml") == 1500.0


def test_size_kg_to_g():
    assert units.parse_size_in_dim("GAS LICUADO VALE DE RECARGA 15 KG", "g") == 15000.0
    assert units.parse_size_in_dim("galletas de 126 gramos", "g") == 126.0


def test_size_metres_takes_dominant_length():
    # A tape "5 CM X 200 MTS" is a 200 m roll; take the dominant length, not the 5 cm width.
    assert units.parse_size_in_dim("CINTA EMBALAJE ROLLO 5 CM X 200 MTS", "m") == 200.0


def test_size_absent_returns_none():
    assert units.parse_size_in_dim("Cartulina de colores", "ml") is None
    assert units.parse_size_in_dim("agua mineral 500 cc", "g") is None
