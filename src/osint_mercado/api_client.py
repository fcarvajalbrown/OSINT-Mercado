import time
from urllib.parse import urlencode

import requests
import truststore

truststore.inject_into_ssl()  # verify TLS against the OS trust store

BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico/ordenesdecompra.json"


class ApiError(RuntimeError):
    """Raised when the OC API request fails."""


def build_list_url(fecha: str, ticket: str) -> str:
    return f"{BASE_URL}?{urlencode({'fecha': fecha, 'ticket': ticket})}"


def build_detail_url(codigo: str, ticket: str) -> str:
    return f"{BASE_URL}?{urlencode({'codigo': codigo, 'ticket': ticket})}"


def build_by_organism_url(fecha: str, codigo_organismo: str, ticket: str) -> str:
    return f"{BASE_URL}?{urlencode({'fecha': fecha, 'CodigoOrganismo': codigo_organismo, 'ticket': ticket})}"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "osint-mercado/0.1"})
    return session


def fetch_json(url, session, *, max_retries=4, backoff_base=1.0, sleep=time.sleep):
    attempt = 0
    while True:
        try:
            resp = session.get(url, timeout=60)
            if resp.status_code == 429 and attempt < max_retries:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else backoff_base * (2 ** attempt)
                sleep(delay)
                attempt += 1
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise ApiError(f"OC API request failed: {type(exc).__name__}") from exc
