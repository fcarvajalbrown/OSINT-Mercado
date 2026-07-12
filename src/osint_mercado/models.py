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
