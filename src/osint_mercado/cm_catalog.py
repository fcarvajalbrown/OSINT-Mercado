"""Convenio Marco (CM) reference-price catalog (ADR 0024).

ChileCompra publishes, per active Convenio Marco, a "maestra de productos" listing
every catalogued product a public buyer could have bought under the framework
agreement, with a per-region shelf price ("PRECIO EN TIENDA", shown net of IVA -
same basis as an OC line's PrecioNeto). This is the *normative* reference: not what
the market charges (retail / peer engines) but what the organism itself was bound
to consider. If a municipality paid materially more than the CM price for the same
product at the same size, that is the most defensible overprice lead we can raise.

This module fetches the weekly index, downloads each CM's zipped CSV, and caches a
deduped, RM-relevant (METROPOLITANA + NACIONAL) parquet. Field access is pinned
here (as with schema.py): the 20-column inner CSV is comma-delimited, UTF-8 BOM,
Content-Type octet-stream (parse by extension). Pure parsing is separated from the
network so it is unit-tested against a fixture, never live.
"""

import csv
import io
import zipfile
from collections.abc import Iterable, Iterator

from osint_mercado.matcher import normalize

INDEX_URL = "https://transparenciachc.blob.core.windows.net/maestrascm/CM_publicados.csv"

# Regions a Región Metropolitana buyer could purchase under: the RM-specific rows
# plus national convenios, which are available to every region (ADR 0024).
RM_REGIONS = ("METROPOLITANA", "NACIONAL")

# Pinned inner-CSV column names (the documented 20-column header). Nothing else
# hard-codes these strings; import from here.
COL_CODIGO_ONU = "CÓDIGO ONU"
COL_PRODUCTO = "PRODUCTO"
COL_MARCA = "MARCA"
COL_MODELO = "MODELO"
COL_MEDIDA = "MEDIDA"
COL_REGION = "REGIÓN"
COL_PRECIO_TIENDA = "PRECIO EN TIENDA"
COL_PROVEEDOR = "NOMBRE PROVEEDOR"
COL_RUT = "RUT PROVEEDOR"

# The stored per-row fields the scoring core needs.
FIELDS = ("code", "region", "producto", "marca", "modelo", "medida",
          "proveedor", "rut", "precio_neto")


def _clean(value) -> str:
    return (value or "").strip()


def parse_price(value) -> float | None:
    """Parse a PRECIO EN TIENDA cell to a positive float, or None."""
    text = _clean(value).replace(".", "").replace(",", ".") if value else ""
    if not text:
        return None
    try:
        price = float(text)
    except ValueError:
        return None
    return price if price > 0 else None


def normalize_row(raw: dict) -> dict | None:
    """Turn one raw CSV row into a stored record, or None to drop it.

    Dropped: non-RM regions, an empty / "0" CÓDIGO ONU (scope artifact - a line
    with no UNSPSC code is not joinable to an OC purchase), and a non-positive
    price.
    """
    region = _clean(raw.get(COL_REGION))
    if region not in RM_REGIONS:
        return None
    code = _clean(raw.get(COL_CODIGO_ONU))
    if not code or code == "0":
        return None
    price = parse_price(raw.get(COL_PRECIO_TIENDA))
    if price is None:
        return None
    return {
        "code": code,
        "region": region,
        "producto": _clean(raw.get(COL_PRODUCTO)),
        "marca": _clean(raw.get(COL_MARCA)),
        "modelo": _clean(raw.get(COL_MODELO)),
        "medida": _clean(raw.get(COL_MEDIDA)),
        "proveedor": _clean(raw.get(COL_PROVEEDOR)),
        "rut": _clean(raw.get(COL_RUT)),
        "precio_neto": price,
    }


def parse_catalog_csv(text: str) -> list[dict]:
    """Parse a decoded inner CM CSV into stored, RM-relevant records."""
    reader = csv.DictReader(io.StringIO(text))
    out: list[dict] = []
    for raw in reader:
        rec = normalize_row(raw)
        if rec is not None:
            out.append(rec)
    return out


def descriptive_text(rec: dict) -> str:
    """The identity text for size-parsing and token-matching a CM product.

    Sizes and the specific product live across PRODUCTO / MODELO / MEDIDA / MARCA
    (e.g. the GAS convenio carries "11 KG" in MODELO, not MEDIDA), so combine them
    rather than trusting a single field.
    """
    return normalize(" ".join(
        str(rec.get(f) or "") for f in ("producto", "marca", "modelo", "medida")
    ))


def dedup(records: Iterable[dict]) -> list[dict]:
    """Collapse exact-duplicate offers, preserving distinct (product, price) rows."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for r in records:
        key = tuple(r.get(f) for f in FIELDS)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


# --- network + cache (thin; the parsing above is what tests cover) -----------

def fetch_index(session) -> list[str]:
    """Return the download URLs of every active CM maestra file."""
    r = session.get(INDEX_URL, timeout=60)
    r.raise_for_status()
    text = r.content.decode("utf-8-sig")
    urls: list[str] = []
    for line in text.splitlines()[1:]:
        parts = line.split(";")
        if len(parts) >= 2 and parts[1].strip():
            urls.append(parts[1].strip())
    return urls


def fetch_maestra(session, url: str) -> Iterator[dict]:
    """Download one zipped CM maestra and yield its stored, RM-relevant records."""
    r = session.get(url, timeout=180)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    for name in zf.namelist():
        if not name.lower().endswith(".csv"):
            continue
        text = zf.read(name).decode("utf-8-sig", errors="replace")
        yield from parse_catalog_csv(text)


def build_catalog(session) -> list[dict]:
    """Fetch the whole index and return the deduped RM-relevant CM catalog."""
    records: list[dict] = []
    for url in fetch_index(session):
        records.extend(fetch_maestra(session, url))
    return dedup(records)


def save_catalog(records: list[dict], path) -> None:
    import polars as pl

    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(records, schema={
        "code": pl.Utf8, "region": pl.Utf8, "producto": pl.Utf8, "marca": pl.Utf8,
        "modelo": pl.Utf8, "medida": pl.Utf8, "proveedor": pl.Utf8, "rut": pl.Utf8,
        "precio_neto": pl.Float64,
    }).write_parquet(path)


def load_catalog(path) -> dict[str, list[dict]]:
    """Load the cached catalog grouped by UNSPSC code for O(1) per-code lookup."""
    import polars as pl

    df = pl.read_parquet(path)
    by_code: dict[str, list[dict]] = {}
    for rec in df.iter_rows(named=True):
        by_code.setdefault(rec["code"], []).append(rec)
    return by_code
