from osint_mercado import cm_scoring


def _cm(producto, precio, *, code="50201709", region="METROPOLITANA",
        marca="-", modelo="-", medida="-"):
    return {"code": code, "region": region, "producto": producto, "marca": marca,
            "modelo": modelo, "medida": medida, "proveedor": "P", "rut": "1-9",
            "precio_neto": float(precio)}


# ---- coverage / token match within a shared code ----

def test_no_cm_rows_returns_none():
    assert cm_scoring.compare("CAFE 170 G", 5000.0, []) is None


def test_requires_two_shared_distinctive_tokens():
    # A "mesa plegable" carrying the same UNSPSC code as "pala de aseo" must NOT be
    # compared: code is the join key, never the match (the ONU-codes pitfall).
    cm_rows = [_cm("PALA DE ASEO PLASTICA CON MANGO 70 CM", 1600) for _ in range(4)]
    assert cm_scoring.compare("MESA PLEGABLE 180 CM POLIETILENO", 30000.0, cm_rows) is None


# ---- size normalization: per gram / ml / m ----

def test_size_normalized_per_gram():
    # CM: three 50 g coffees at $2000 -> $40/g. OC: 170 g at $13600 -> $80/g -> 2.0x.
    cm_rows = [_cm("CAFE INSTANTANEO GOLD TARRO 50 G", 2000) for _ in range(3)]
    r = cm_scoring.compare("CAFE INSTANTANEO GOLD TARRO 170 G", 13600.0, cm_rows)
    assert r is not None
    assert r.dimension == "g"
    assert r.ratio == 2.0
    assert r.severity == "high"


# ---- pack-count normalization (per-unit goods): the friend's pen-set case ----

def test_pack_count_normalized_divides_by_set_size():
    # CM: plain blue pens at $300 each. OC: a SET of 8 at $4800 total -> $600/pen -> 2.0x.
    cm_rows = [_cm("LAPIZ PASTA BIC AZUL UNIDAD", 300, code="44121701") for _ in range(3)]
    r = cm_scoring.compare("SET DE LAPIZ PASTA AZUL 8 UNIDADES", 4800.0, cm_rows)
    assert r is not None
    assert r.dimension == "unit"
    assert r.ratio == 2.0


# ---- CM outliers: median, never the raw min (the te-100-bolsas artifact) ----

def test_reference_is_median_not_min():
    prices = [300, 320, 310, 305, 1]  # the $1 row is a per-pack data artifact
    cm_rows = [_cm("LAPIZ PASTA BIC AZUL UNIDAD", p, code="44121701") for p in prices]
    r = cm_scoring.compare("LAPIZ PASTA BIC AZUL UNIDAD", 620.0, cm_rows)
    assert r is not None
    # median of [1, 300, 305, 310, 320] is 305 - the $1 artifact does not drag it down.
    assert r.cm_reference_per_unit == 305.0
    assert r.ratio == 2.0328


# ---- plausibility band and thresholds ----

def test_below_watch_is_not_a_lead():
    cm_rows = [_cm("LAPIZ PASTA BIC AZUL UNIDAD", 300, code="44121701") for _ in range(3)]
    assert cm_scoring.compare("LAPIZ PASTA BIC AZUL UNIDAD", 360.0, cm_rows) is None  # 1.2x


def test_above_band_routed_out_as_scope_artifact():
    cm_rows = [_cm("LAPIZ PASTA BIC AZUL UNIDAD", 300, code="44121701") for _ in range(3)]
    assert cm_scoring.compare("LAPIZ PASTA BIC AZUL UNIDAD", 12000.0, cm_rows) is None  # 40x


def test_min_refs_enforced():
    # Only two matched CM references: a two-row median is too thin (min_refs=3).
    cm_rows = [_cm("LAPIZ PASTA BIC AZUL UNIDAD", 300, code="44121701") for _ in range(2)]
    assert cm_scoring.compare("LAPIZ PASTA BIC AZUL UNIDAD", 600.0, cm_rows) is None


# ---- lead carries evidence + provenance ----

def test_score_cm_returns_lead_with_evidence_and_provenance():
    cm_rows = [_cm("CAFE INSTANTANEO GOLD TARRO 50 G", 2000, region="NACIONAL")
               for _ in range(3)]
    lead = cm_scoring.score_cm(
        oc_id="700-1-SE24", correlativo=3, comuna="Buin", product_code="50201709",
        oc_text="CAFE INSTANTANEO GOLD TARRO 170 G", unit_price_clp_net=13600.0,
        oc_url="https://example/oc", captured_at="2026-07-10", cm_rows=cm_rows,
    )
    assert lead is not None
    assert lead.oc_id == "700-1-SE24"
    assert lead.comuna == "Buin"
    assert lead.product_code == "50201709"
    assert lead.ratio == 2.0
    assert lead.severity == "high"
    assert lead.dimension == "g"
    assert lead.n_refs == 3
    assert lead.cm_reference_per_unit == 40.0
    assert lead.cm_region == "NACIONAL"
    assert "CAFE" in lead.cm_sample_producto
    assert lead.oc_url == "https://example/oc"
    assert lead.status == "pending"
    assert lead.id  # stable id present
