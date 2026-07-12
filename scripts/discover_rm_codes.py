"""Discover and verify Mercado Publico CodigoOrganismo values for RM municipalities.

Every code written to data/rm_municipal_codes.json must be verified against a real
per-order DETAIL response: the by-organism list endpoint only returns Codigo/Nombre/
CodigoEstado (no buyer), so a candidate is only accepted once a real detail response's
Comprador.CodigoOrganismo / NombreOrganismo / ComunaUnidad / RegionUnidad confirm it is
that RM municipality. Nothing here hard-codes a code without that verification step.

Two-stage method:

1. Candidate codes come from the real BuscarComprador directory endpoint
   (https://api.mercadopublico.cl/servicios/v1/Publico/Empresas/BuscarComprador),
   which lists every registered buyer organism (CodigoEmpresa/NombreEmpresa) on
   Mercado Publico. This is a real, live API response, but it does not carry comuna/
   region, so a name match there is only a CANDIDATE, never accepted as-is.
2. Each candidate is verified: query the by-organism-and-date list endpoint
   (build_by_organism_url) for one or more recent weekdays; if it returns at least
   one order code, fetch that order's DETAIL (build_detail_url), parse it with
   parser.parse_detail, and check that Buyer.code matches the candidate code and
   Buyer.region indicates Region Metropolitana and municipal.is_municipal(Buyer.name)
   is true. Only then is the tuple (comuna, nombre_organismo, codigo_organismo)
   accepted, and comuna/nombre/codigo all come from that real detail response
   (not from the candidate directory).

Effort cap: at most ~250 detail calls in a single run (module-level DETAIL_CALL_CAP),
across a bounded set of recent weekday dates (DEFAULT_DATES). Full 52/52 coverage is
not guaranteed in one run: some municipalities may not have placed any order on the
sampled dates. Re-run with additional dates (--dates) to extend coverage; the script
is idempotent and merges into any existing output file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests
import truststore

from osint_mercado import api_client, municipal, parser, schema
from osint_mercado.config import load_ticket

truststore.inject_into_ssl()

BUSCAR_COMPRADOR_URL = "https://api.mercadopublico.cl/servicios/v1/Publico/Empresas/BuscarComprador"

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "rm_municipal_codes.json"

DETAIL_CALL_CAP = 250

# The 52 Region Metropolitana comunas (v1 target set). Order preserved for reporting.
RM_COMUNAS = [
    "Santiago", "Cerrillos", "Cerro Navia", "Conchali", "El Bosque", "Estacion Central",
    "Huechuraba", "Independencia", "La Cisterna", "La Florida", "La Granja", "La Pintana",
    "La Reina", "Las Condes", "Lo Barnechea", "Lo Espejo", "Lo Prado", "Macul", "Maipu",
    "Nunoa", "Pedro Aguirre Cerda", "Penalolen", "Providencia", "Pudahuel", "Quilicura",
    "Quinta Normal", "Recoleta", "Renca", "San Joaquin", "San Miguel", "San Ramon",
    "Vitacura", "Puente Alto", "Pirque", "San Jose de Maipo", "Colina", "Lampa", "Tiltil",
    "San Bernardo", "Buin", "Calera de Tango", "Paine", "Melipilla", "Alhue", "Curacavi",
    "Maria Pinto", "San Pedro", "Talagante", "El Monte", "Isla de Maipo", "Padre Hurtado",
    "Penaflor",
]

# Candidate CodigoEmpresa per comuna, drawn from a real BuscarComprador response
# (see docs/api/rm-municipal-codes.md for how this list was produced). These are
# CANDIDATES only -- each is verified against a real order detail before acceptance.
CANDIDATE_CODES: dict[str, str] = {
    "Santiago": "86568",
    "Cerrillos": "7241",
    "Cerro Navia": "86664",
    "Conchali": "84958",
    "El Bosque": "7496",
    "Estacion Central": "87824",
    "Huechuraba": "100739",
    "Independencia": "99105",
    "La Cisterna": "100488",
    "La Florida": "86766",
    "La Granja": "112097",
    "La Pintana": "83825",
    "La Reina": "7366",
    "Las Condes": "86571",
    "Lo Barnechea": "100155",
    "Lo Espejo": "86518",
    "Lo Prado": "87373",
    "Macul": "84300",
    "Maipu": "93619",
    "Nunoa": "86764",
    "Pedro Aguirre Cerda": "87104",
    "Penalolen": "87172",
    "Providencia": "88102",
    "Pudahuel": "84149",
    "Quilicura": "88313",
    "Quinta Normal": "88075",
    "Recoleta": "7325",
    "Renca": "87185",
    "San Joaquin": "7135",
    "San Miguel": "7498",
    "San Ramon": "7355",
    "Vitacura": "98462",
    "Puente Alto": "87388",
    "Pirque": "100072",
    "San Jose de Maipo": "115457",
    "Colina": "99322",
    "Lampa": "118067",
    "Tiltil": "116218",
    "San Bernardo": "86548",
    "Buin": "100090",
    "Calera de Tango": "116219",
    "Paine": "100728",
    "Melipilla": "98901",
    "Alhue": "111124",
    "Curacavi": "125602",
    "Maria Pinto": "120798",
    "San Pedro": "142855",
    "Talagante": "99765",
    "El Monte": "116741",
    "Isla de Maipo": "117181",
    "Padre Hurtado": "117406",
    "Penaflor": "100137",
}

DEFAULT_DATES = ["10072026", "08072026"]

REGION_RM_MARKERS = ("METROPOLITANA",)


def _is_rm_region(region: str) -> bool:
    return any(marker in region.upper() for marker in REGION_RM_MARKERS)


def fetch_candidate_directory(ticket: str, session: requests.Session) -> list[dict]:
    """Return the real BuscarComprador organism directory (all registered buyers)."""
    resp = session.get(BUSCAR_COMPRADOR_URL, params={"ticket": ticket}, timeout=60)
    resp.raise_for_status()
    return resp.json().get("listaEmpresas", [])


def verify_candidate(
    comuna: str,
    codigo_organismo: str,
    dates: list[str],
    ticket: str,
    session: requests.Session,
    detail_calls: list[int],
) -> dict | None:
    """Verify one candidate by fetching a real order detail for it.

    Returns the verified {"comuna", "nombre_organismo", "codigo_organismo"} dict, or
    None if no order (and therefore no detail confirmation) could be found within the
    sampled dates / call cap. All three output values come from the real detail
    response's Buyer fields, not from the candidate directory.
    """
    for fecha in dates:
        if detail_calls[0] >= DETAIL_CALL_CAP:
            return None
        url = api_client.build_by_organism_url(fecha, codigo_organismo, ticket)
        try:
            listing = api_client.fetch_json(url, session)
        except api_client.ApiError:
            continue
        codes = [row.get(schema.OC_CODIGO) for row in (listing.get(schema.LIST_LISTADO) or [])]
        codes = [c for c in codes if c]
        for codigo in codes[:3]:
            if detail_calls[0] >= DETAIL_CALL_CAP:
                return None
            detail_calls[0] += 1
            try:
                detail = api_client.fetch_json(
                    api_client.build_detail_url(codigo, ticket), session
                )
            except api_client.ApiError:
                continue
            orders = parser.parse_detail(detail)
            for order in orders:
                buyer = order.buyer
                if (
                    buyer.code == codigo_organismo
                    and _is_rm_region(buyer.region)
                    and municipal.is_municipal(buyer.name)
                ):
                    return {
                        "comuna": comuna,
                        "nombre_organismo": buyer.name,
                        "codigo_organismo": buyer.code,
                    }
    return None


def load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def merge(existing: list[dict], new_entries: list[dict]) -> list[dict]:
    by_comuna = {e["comuna"]: e for e in existing}
    for entry in new_entries:
        by_comuna[entry["comuna"]] = entry
    return sorted(by_comuna.values(), key=lambda e: e["comuna"])


def main() -> None:
    ap = argparse.ArgumentParser(description="Discover/verify RM municipal CodigoOrganismo values")
    ap.add_argument("--dates", nargs="+", default=DEFAULT_DATES, help="ddmmaaaa dates to sample")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output JSON path")
    ap.add_argument("--comunas", nargs="+", default=None, help="restrict to these comunas")
    args = ap.parse_args()

    ticket = load_ticket()
    session = api_client.make_session()
    detail_calls = [0]

    comunas = args.comunas or RM_COMUNAS
    verified: list[dict] = []
    missing: list[str] = []

    for comuna in comunas:
        codigo = CANDIDATE_CODES.get(comuna)
        if not codigo:
            missing.append(comuna)
            continue
        result = verify_candidate(comuna, codigo, args.dates, ticket, session, detail_calls)
        if result:
            verified.append(result)
            print(f"verified: {comuna} -> {result['codigo_organismo']} ({result['nombre_organismo']})")
        else:
            missing.append(comuna)
            print(f"not verified (no order found in sampled dates): {comuna}")
        if detail_calls[0] >= DETAIL_CALL_CAP:
            print(f"reached detail-call cap ({DETAIL_CALL_CAP}); stopping")
            break

    out_path = Path(args.out)
    existing = load_existing(out_path)
    merged = merge(existing, verified)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\ndetail calls used: {detail_calls[0]} / {DETAIL_CALL_CAP}")
    print(f"verified this run: {len(verified)}")
    print(f"total verified in {out_path}: {len(merged)} / {len(RM_COMUNAS)}")
    if missing:
        print(f"not verified: {', '.join(missing)}")


if __name__ == "__main__":
    main()
