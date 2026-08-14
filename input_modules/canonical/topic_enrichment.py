from __future__ import annotations

import json
from typing import Any

from cw14_model import materialize_topics

ACTIVE_STATUSES = {"unlocked", "locked"}
NON_NODE_SOURCE_ROLES = {"reconciliation", "historical_or_migration", "derived_projection"}


def _has_explicit_topics(snapshot: Any) -> bool:
    """Return True only when active canonical source explicitly contains topics[].

    Topic support is detected from structured source capability, not from a
    hard-coded Contract Format version number. This preserves the no-guessing
    rule while allowing additive/newer canonical formats to expose Topics.
    """
    for path in sorted(snapshot.files):
        if not path.startswith("canonical/json/") or not path.endswith(".json") or path.endswith("00_Contract_Format.json"):
            continue
        try:
            data = json.loads(snapshot.files[path].decode("utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("format", {}).get("contract_format") != "AIGMOS_CANONICAL_CONTRACT":
            continue
        if data.get("status") not in ACTIVE_STATUSES or data.get("source_role") in NON_NODE_SOURCE_ROLES:
            continue
        if isinstance(data.get("topics"), list):
            return True
    return False


def enrich_topics(tree: dict[str, Any], snapshot: Any) -> dict[str, Any]:
    """Expose explicit topics[] without inventing legacy semantic roots."""
    if not _has_explicit_topics(snapshot):
        tree.setdefault("topics", [])
        tree.setdefault("source_result", {})["canonical_topics"] = {
            "enabled": False,
            "source": "topics[] only",
            "reason": "no explicit active topics[] present",
            "legacy_root_fallback": False,
            "inference": False,
        }
        return tree

    errors = list(tree.get("errors", []))
    errors.extend(materialize_topics(tree, snapshot))
    tree["errors"] = errors
    tree.setdefault("source_result", {})["canonical_topics"] = {
        "enabled": True,
        "source": "contract.topics[] recursively",
        "activation": "explicit structured capability",
        "version_gate": False,
        "legacy_root_fallback": False,
        "topic_semantic_authority": False,
        "inference": False,
    }
    return tree


__all__ = ["enrich_topics"]
