from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from canonical_graph import build_graph  # noqa: E402
from structureprojector import SourceSnapshot  # noqa: E402


def main() -> int:
    source_root = ROOT / "_diagnostic_source"
    files: dict[str, bytes] = {}
    for path in source_root.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            files[path.relative_to(source_root).as_posix()] = path.read_bytes()

    snapshot = SourceSnapshot(
        repo="Th3Hypn0tist/AIGMos_docs",
        branch="main",
        revision="diagnostic-checkout",
        files=files,
    )
    result = build_graph(snapshot)
    summary = {
        "valid": result.get("valid"),
        "source": result.get("source"),
        "node_count": len(result.get("graph", {}).get("nodes", [])),
        "edge_count": len(result.get("graph", {}).get("edges", [])),
        "error_count": len(result.get("errors", [])),
        "errors": result.get("errors", [])[:100],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
