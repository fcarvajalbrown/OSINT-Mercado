from dataclasses import dataclass


@dataclass(frozen=True)
class Buyer:
    name: str
    code: str
    comuna: str
    region: str


@dataclass(frozen=True)
class LineItem:
    product: str
    quantity: float
    unit_price: float
    moneda: str = ""
    total: float = 0.0
    total_cargos: float = 0.0
    total_descuentos: float = 0.0
    total_impuestos: float = 0.0
    category: str = ""
    category_code: int = 0
    product_code: int = 0


@dataclass(frozen=True)
class PurchaseOrder:
    codigo: str
    name: str
    fecha: str
    buyer: Buyer
    items: list[LineItem]
    codigo_estado: int = 0
    estado: str = ""
    codigo_tipo: str = ""
    tipo: str = ""
    codigo_estado_proveedor: int = 0
    estado_proveedor: str = ""
    tipo_moneda: str = ""
    porcentaje_iva: float = 0.0
    total: float = 0.0
    total_neto: float = 0.0
    impuestos: float = 0.0
    cargos: float = 0.0
    descuentos: float = 0.0
