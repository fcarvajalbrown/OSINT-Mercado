"""Capture one real list-by-date and one detail response as test fixtures.

Run locally with a valid ticket in .env. TLS is verified via the OS trust
store (truststore), so the dev machine's intercepting cert is trusted
without weakening verification.
"""
import json
import sys
from pathlib import Path

import requests
import truststore

from osint_mercado.config import load_ticket

truststore.inject_into_ssl()

BASE = "https://api.mercadopublico.cl/servicios/v1/publico/ordenesdecompra.json"
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def get(params: dict) -> dict:
    resp = requests.get(BASE, params=params, timeout=60)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        # requests embeds the full request URL (including the ticket) in the
        # default HTTPError message; re-raise without it.
        raise SystemExit(f"HTTP {resp.status_code} error calling OC API") from None
    return resp.json()


def save(name: str, payload: dict, ticket: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if ticket in text:
        raise SystemExit(f"Refusing to save {name}: ticket present in payload")
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / name).write_text(text, encoding="utf-8")
    print(f"wrote {name} ({len(text)} bytes)")


def main() -> None:
    ticket = load_ticket()
    fecha = sys.argv[1] if len(sys.argv) > 1 else "09072026"
    listing = get({"fecha": fecha, "ticket": ticket})
    save("oc_list_sample.json", listing, ticket)
    first = (listing.get("Listado") or [None])[0]
    if not first:
        raise SystemExit(f"No orders returned for fecha={fecha}; try another date")
    codigo = first["Codigo"]
    detail = get({"codigo": codigo, "ticket": ticket})
    save("oc_detail_sample.json", detail, ticket)


if __name__ == "__main__":
    main()
