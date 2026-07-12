import json

from osint_mercado import score, store
from osint_mercado.models import Buyer, LineItem, PurchaseOrder

BASELINES = "data/baselines.json"
BASKET = "data/basket.json"


def _order(codigo, comuna, item):
    buyer = Buyer(f"Municipalidad de {comuna}", "1", comuna, "RM")
    return PurchaseOrder(
        codigo, "compra", "2026-07-09T00:00:00", buyer, [item],
        codigo_estado=6, estado="Aceptada", tipo_moneda="CLP", porcentaje_iva=19.0,
    )


def _items_parquet(tmp_path):
    overpriced = LineItem(
        "Mouse", 1.0, 10000.0, moneda="CLP", correlativo=1,
        espec_proveedor="Mouse USB optico Genius",
    )
    fair = LineItem(
        "Extintor", 1.0, 30000.0, moneda="CLP", correlativo=1,
        espec_proveedor="Extintor PQS ABC 6 kilos",
    )
    orders = [_order("1-1-SE26", "Nunoa", overpriced), _order("2-1-SE26", "Maipu", fair)]
    df = store.orders_to_items_df(orders, captured_at="2026-07-12T00:00:00Z")
    p = tmp_path / "oc_items.parquet"
    store.write_parquet(df, p)
    return p


def test_run_emits_only_the_overpriced_line(tmp_path):
    items = _items_parquet(tmp_path)
    out = tmp_path / "pending_anomalies.json"
    fxc = tmp_path / "fx_rates.json"
    score.run(items, BASELINES, BASKET, fxc, out, session=None)

    rows = json.loads(out.read_text(encoding="utf-8"))
    assert len(rows) == 1
    a = rows[0]
    assert a["oc_id"] == "1-1-SE26"
    assert a["sku_id"] == "mouse_usb"
    assert a["status"] == "pending"
    assert a["unit_price_clp_gross"] == 11900.0
    assert a["severity"] == "severe"


def test_run_is_deterministic(tmp_path):
    items = _items_parquet(tmp_path)
    out = tmp_path / "pending_anomalies.json"
    fxc = tmp_path / "fx_rates.json"
    score.run(items, BASELINES, BASKET, fxc, out, session=None)
    first = out.read_bytes()
    score.run(items, BASELINES, BASKET, fxc, out, session=None)
    assert out.read_bytes() == first
