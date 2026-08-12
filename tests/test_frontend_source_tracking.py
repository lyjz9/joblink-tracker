from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_source_tracking_helpers_with_node():
    node = os.environ.get("NODE_BINARY") or shutil.which("node")
    if not node:
        pytest.skip("Node.js is not available for the frontend helper test.")

    completed = subprocess.run(
        [node, str(ROOT / "tests" / "frontend_source_tracking.test.cjs")],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "Frontend source-tracking tests passed" in completed.stdout


def test_source_tracking_helpers_load_before_the_application_script():
    template = (ROOT / "scraper" / "templates" / "index.html").read_text(
        encoding="utf-8"
    )

    assert template.index("../static/source_tracking.js") < template.index("../static/app.js")
