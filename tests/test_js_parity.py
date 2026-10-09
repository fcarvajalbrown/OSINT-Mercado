import json
import shutil
import subprocess
from pathlib import Path

import pytest

from osint_mercado import build_site

NODE = shutil.which("node")
PARITY = Path("tests/js/parity.mjs")
ANCHORS = Path("data/anchors.json")

pytestmark = pytest.mark.skipif(not NODE or not ANCHORS.exists(), reason="needs node and an anchor")


def _run(site: Path) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, str(PARITY), str(site)], capture_output=True, text=True)


def test_browser_hashes_match_the_python_anchor(tmp_path):
    site = build_site.build("data/confirmed_flags.json", "data/basket.json", "frontend", tmp_path / "dist")
    result = _run(site)
    assert result.returncode == 0, result.stdout + result.stderr


def test_browser_detects_a_tampered_price(tmp_path):
    site = build_site.build("data/confirmed_flags.json", "data/basket.json", "frontend", tmp_path / "dist")
    flags_path = site / "data" / "flags.json"
    flags = json.loads(flags_path.read_text(encoding="utf-8"))
    flags[0]["unit_price_clp_gross"] = flags[0]["reference_price_clp"]
    flags_path.write_text(json.dumps(flags, ensure_ascii=False), encoding="utf-8")
    result = _run(site)
    assert result.returncode == 1
    assert flags[0]["id"] in result.stdout
