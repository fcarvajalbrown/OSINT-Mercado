from osint_mercado import store
from osint_mercado.models import Buyer, LineItem, PurchaseOrder


def _orders():
    buyer = Buyer("Municipalidad de Nunoa", "1", "Nunoa", "RM")
    items = [LineItem("Toner HP 85A", 2.0, 45000.0)]
    return [PurchaseOrder("1234-5-SE26", "compra", "01072026", buyer, items)]


def test_orders_to_items_df_one_row_per_item():
    df = store.orders_to_items_df(_orders(), captured_at="2026-07-12T00:00:00Z")
    assert df.height == 1
    assert set(store.ITEM_COLUMNS).issubset(set(df.columns))
    row = df.row(0, named=True)
    assert row["oc_id"] == "1234-5-SE26"
    assert row["unit_price"] == 45000.0
    assert row["oc_url"].endswith("1234-5-SE26")
    assert row["captured_at"] == "2026-07-12T00:00:00Z"


def test_write_parquet_roundtrip(tmp_path):
    import polars as pl

    df = store.orders_to_items_df(_orders(), captured_at="2026-07-12T00:00:00Z")
    out = tmp_path / "items.parquet"
    store.write_parquet(df, out)
    assert out.exists()
    assert pl.read_parquet(out).height == 1
