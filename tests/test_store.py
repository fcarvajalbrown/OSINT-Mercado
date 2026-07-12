from osint_mercado import store
from osint_mercado.models import Buyer, LineItem, PurchaseOrder


def _orders():
    buyer = Buyer("Municipalidad de Nunoa", "1", "Nunoa", "RM")
    items = [LineItem(
        "Toner HP 85A", 2.0, 45000.0,
        moneda="CLP", total=90000.0, total_cargos=0.0, total_descuentos=0.0,
        total_impuestos=0.0, category="Toner", category_code=44103109, product_code=44103110,
        correlativo=1, unidad="", espec_comprador="compra toner",
        espec_proveedor="HP 85A CE285A original",
    )]
    return [PurchaseOrder(
        "1234-5-SE26", "compra", "01072026", buyer, items,
        codigo_estado=6, estado="Aceptada", codigo_tipo="8", tipo="SE",
        codigo_estado_proveedor=4, estado_proveedor="Aceptada",
        tipo_moneda="CLP", porcentaje_iva=19.0, total=107100.0, total_neto=90000.0,
        impuestos=17100.0, cargos=0.0, descuentos=0.0,
    )]


def test_orders_to_items_df_one_row_per_item():
    df = store.orders_to_items_df(_orders(), captured_at="2026-07-12T00:00:00Z")
    assert df.height == 1
    assert set(store.ITEM_COLUMNS).issubset(set(df.columns))
    row = df.row(0, named=True)
    assert row["oc_id"] == "1234-5-SE26"
    assert row["unit_price"] == 45000.0
    assert row["oc_url"].endswith("1234-5-SE26")
    assert row["captured_at"] == "2026-07-12T00:00:00Z"


def test_orders_to_items_df_includes_status_currency_and_category_columns():
    df = store.orders_to_items_df(_orders(), captured_at="2026-07-12T00:00:00Z")
    row = df.row(0, named=True)
    assert row["codigo_estado"] == 6
    assert row["estado"] == "Aceptada"
    assert row["codigo_tipo"] == "8"
    assert row["tipo"] == "SE"
    assert row["tipo_moneda"] == "CLP"
    assert row["porcentaje_iva"] == 19.0
    assert row["order_total"] == 107100.0
    assert row["order_total_neto"] == 90000.0
    assert row["moneda"] == "CLP"
    assert row["total"] == 90000.0
    assert row["category"] == "Toner"
    assert row["category_code"] == 44103109
    assert row["product_code"] == 44103110
    assert row["correlativo"] == 1
    assert row["unidad"] == ""
    assert row["espec_proveedor"] == "HP 85A CE285A original"
    assert row["espec_comprador"] == "compra toner"


def test_write_parquet_roundtrip(tmp_path):
    import polars as pl

    df = store.orders_to_items_df(_orders(), captured_at="2026-07-12T00:00:00Z")
    out = tmp_path / "items.parquet"
    store.write_parquet(df, out)
    assert out.exists()
    assert pl.read_parquet(out).height == 1
