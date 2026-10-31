"""Run the demo with redirected output and a legacy Windows encoding."""

import os
from pathlib import Path
import subprocess
import sys


def test_demo_redirected_output_uses_utf8_with_legacy_windows_encoding(tmp_path):
    env = os.environ.copy()
    env.update({
        "PYTHONIOENCODING": "cp1255",
        "PYTHONDONTWRITEBYTECODE": "1",
        "WEATHER_MODE": "default",
    })
    demo_path = Path(__file__).resolve().parents[1] / "main.py"

    result = subprocess.run(
        [sys.executable, str(demo_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        # The demo reads no input; without this the child inherits pytest's stdin,
        # which is invalid when tests run from an IDE or CI (WinError 6 on Windows).
        stdin=subprocess.DEVNULL,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    output = result.stdout.decode("utf-8")
    assert "✓ Status changed to IN_TRANSIT" in output
    assert "📍" in output
    assert "Same results, same input order: True" in output
    assert "REPORT - after the change:" in output
    assert "Senior-approval backlog (DANGER orders waiting for a logistics manager): 0" in output
    assert "Weather check failed for Haifa" in result.stderr.decode("utf-8")
