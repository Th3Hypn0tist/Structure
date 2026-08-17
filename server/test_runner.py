from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = PROJECT_ROOT / "tests" / "modules"


def suite_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(TEST_ROOT),
        "-p",
        "test_*.py",
    ]


def run_startup_suite() -> None:
    print("[structure:cw] conformance gate")
    result = subprocess.run(suite_command(), cwd=PROJECT_ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(
            f"Structure CW conformance gate failed ({result.returncode}); server not started"
        )
    print("[structure:cw] conformance gate passed")
