import json
import shutil
import subprocess
from pathlib import Path

import pytest

from osint_mercado import build_site

NODE = shutil.which("node")
STELLAR = Path("tests/js/stellar.mjs")
ANCHORS = Path("data/anchors.json")

pytestmark = pytest.mark.skipif(not NODE or not ANCHORS.exists(), reason="needs node and an anchor")


def _site(tmp_path: Path) -> Path:
    return build_site.build("data/confirmed_flags.json", "data/basket.json", "frontend", tmp_path / "dist")


def _run(site: Path) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, str(STELLAR), str(site)], capture_output=True, text=True)


def test_stellar_page_matches_the_anchor_and_catches_edits(tmp_path):
    result = _run(_site(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr


def test_stellar_page_fails_on_a_published_edit(tmp_path):
    site = _site(tmp_path)
    flags_path = site / "data" / "flags.json"
    flags = json.loads(flags_path.read_text(encoding="utf-8"))
    flags[0]["unit_price_clp_gross"] = flags[0]["reference_price_clp"]
    flags_path.write_text(json.dumps(flags, ensure_ascii=False), encoding="utf-8")
    result = _run(site)
    assert result.returncode == 1
    assert flags[0]["id"] in result.stdout
