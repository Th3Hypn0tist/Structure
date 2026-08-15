from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = PROJECT_ROOT / "tests"


def suite_command() -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", str(TEST_ROOT)]


def run_startup_suite() -> None:
    print("[structure:test] startup suite")
    result = subprocess.run(suite_command(), cwd=PROJECT_ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Structure startup test suite failed ({result.returncode}); server not started")
    print("[structure:test] suite passed")
