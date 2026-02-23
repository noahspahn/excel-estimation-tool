from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "test_api_endpoints.py"


@pytest.mark.integration
def test_api_smoke_suite() -> None:
    base_url = os.getenv("API_TEST_BASE_URL", "http://127.0.0.1:8000")
    timeout = os.getenv("API_TEST_TIMEOUT", "30")
    wait_seconds = os.getenv("API_TEST_WAIT_SECONDS", "8")
    token = os.getenv("API_TEST_BEARER_TOKEN")

    cmd = [
        sys.executable,
        str(SCRIPT),
        "--base-url",
        base_url,
        "--timeout",
        timeout,
        "--wait-seconds",
        wait_seconds,
    ]
    if token:
        cmd.extend(["--token", token])

    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )

    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    if proc.returncode == 2 and "Backend is not reachable" in combined:
        pytest.skip(combined.strip())

    assert proc.returncode == 0, combined.strip()
