import pytest
from osint_mercado import config


def test_load_ticket_reads_env(monkeypatch):
    monkeypatch.setenv("CHILECOMPRA_API_TICKET", "TICKET-123")
    assert config.load_ticket() == "TICKET-123"


def test_load_ticket_missing_raises(monkeypatch):
    monkeypatch.delenv("CHILECOMPRA_API_TICKET", raising=False)
    # python-dotenv's load_dotenv() walks up from config.py's own file
    # location (not cwd) to find a .env, so it would otherwise find this
    # repo's real .env and repopulate the var we just deleted. Neutralize
    # it for this test only; config.py itself is unchanged.
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: False)
    with pytest.raises(RuntimeError, match="CHILECOMPRA_API_TICKET"):
        config.load_ticket()
