import os
from dotenv import load_dotenv

TICKET_ENV = "CHILECOMPRA_API_TICKET"


def load_ticket() -> str:
    """Return the Mercado Publico API ticket from the environment (.env locally)."""
    load_dotenv()  # no-op if there is no .env (e.g. CI, where the secret is a real env var)
    ticket = os.getenv(TICKET_ENV)
    if not ticket:
        raise RuntimeError(f"{TICKET_ENV} is not set (put it in .env locally or a CI secret)")
    return ticket
