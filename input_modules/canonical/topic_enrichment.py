from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

ACTIVE_STATUSES = {"unlocked", "locked"}
NON_NODE_SOURCE_ROLES = {"reconciliation", "historical_or_migration", "derived_projection"}


def _json_documents(snapshot: Any):
    """Yield structured canonical JSON documents from the entire canonical tree.

    Canonical architecture artifacts are not required to live under
    canonical/json. Directory placement is not used to infer Topic semantics;
    only explicit structured `topics` / `topic` fields are consumed.
    """
    for path in sorted(snapshot.files):
        normalized = path.replace("\\", "/")
        if not normalized.startswith("canonical/") or not normalized.endswith(".json"):
            continue
        try:
            data = json.loads(snapshot.files[path].decode("utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            yield path, data


def _active_document(data: dict[str, Any]) -> bool:
    status = data.get("status")
    if status is not None and status not in ACTIVE_STATUSES:
        return False
    if data.get("source_role") in NON_NODE_SOURCE_ROLES:
        return False
    return True


def _explicit_topic_arrays(value: Any, field_path: str = ""):
    """Find only fields explicitly named `topics` or `topic`.

    This intentionally does not use filenames, directory names, object names or
    type-name heuristics. A Topic must identify itself through structured data.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{field_path}.{key}" if field_path else key
            if key == "topics" and isinstance(child, list):
                yield child_path, child
                continue
            if key == "topic" and isinstance(child, dict):
                yield child_path, [child]
                continue
            # child_topics belong to a Topic and are flattened with that Topic;
            # do not rediscover them as independent document-level roots.
            if key == "child_topics":
                continue
            yield from _explicit_topic_arrays(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _explicit_topic_arrays(child, f"{field_path}[{index}]")


def _string_refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _flatten_topic(
    raw: dict[str, Any],
    *,
    path: str,
    field_path: str,
    snapshot: Any,
    owner_ref: str | None,
    container_topic_ref: str | None,
    out: list[dict[str, Any]],
    seen: set[str],
    errors: list[dict[str, Any]],
) -> None:
    topic_id = str(raw.get("id") or "").strip()
    if not topic_id:
        errors.append({
            "id": "SP_TOPIC_ID_REQUIRED",
            "message": "Explicit Topic object requires id",
            "contract": path,
            "field": field_path,
        })
        return
    if topic_id in seen:
        errors.append({
            "id": "SP_TOPIC_ID_DUPLICATE",
            "message": f"Duplicate explicit Topic identity: {topic_id}",
            "contract": path,
            "field": field_path,
        })
        return
    seen.add(topic_id)

    child_topics = raw.get("child_topics") if isinstance(raw.get("child_topics"), list) else []
    child_ids = [
        str(child.get("id"))
        for child in child_topics
        if isinstance(child, dict) and child.get("id")
    ]

    topic = {
        "id": topic_id,
        "name": str(raw.get("name") or raw.get("label") or topic_id),
        "purpose": str(raw.get("purpose") or ""),
        "owner_ref": raw.get("owner_ref") or owner_ref,
        "container_topic_ref": container_topic_ref,
        "parent_topic_refs": _string_refs(raw.get("parent_topic_refs")),
        "composed_topic_refs": _string_refs(raw.get("composed_topic_refs")),
        "member_refs": _string_refs(raw.get("member_refs")),
        "relation_refs": _string_refs(raw.get("relation_refs")),
        "operation_refs": _string_refs(raw.get("operation_refs")),
        "event_refs": _string_refs(raw.get("event_refs")),
        "flow_refs": _string_refs(raw.get("flow_refs")),
        "child_topic_refs": child_ids,
        "metadata": deepcopy(raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}),
        "provenance": {
            "path": path,
            "field": field_path,
            "repository": snapshot.repo,
            "branch": snapshot.branch,
            "revision": snapshot.revision,
        },
    }
    out.append(topic)

    for index, child in enumerate(child_topics):
        if not isinstance(child, dict):
            errors.append({
                "id": "SP_TOPIC_CHILD_INVALID",
                "message": f"Topic {topic_id} child_topics contains a non-object item",
                "contract": path,
                "field": f"{field_path}.child_topics[{index}]",
            })
            continue
        _flatten_topic(
            child,
            path=path,
            field_path=f"{field_path}.child_topics[{index}]",
            snapshot=snapshot,
            owner_ref=topic.get("owner_ref"),
            container_topic_ref=topic_id,
            out=out,
            seen=seen,
            errors=errors,
        )


def _materialize_explicit_topics(snapshot: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    topics: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    seen: set[str] = set()

    for path, data in _json_documents(snapshot):
        if not _active_document(data):
            continue
        identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
        owner_ref = str(identity.get("id")) if identity.get("id") else None
        for field_path, raw_topics in _explicit_topic_arrays(data):
            if not raw_topics:
                continue
            sources.append({"path": path, "field": field_path})
            for index, raw in enumerate(raw_topics):
                if not isinstance(raw, dict):
                    errors.append({
                        "id": "SP_TOPIC_INVALID",
                        "message": "Explicit topics array contains a non-object item",
                        "contract": path,
                        "field": f"{field_path}[{index}]",
                    })
                    continue
                _flatten_topic(
                    raw,
                    path=path,
                    field_path=f"{field_path}[{index}]",
                    snapshot=snapshot,
                    owner_ref=owner_ref,
                    container_topic_ref=None,
                    out=topics,
                    seen=seen,
                    errors=errors,
                )
    return topics, errors, sources


def enrich_topics(tree: dict[str, Any], snapshot: Any) -> dict[str, Any]:
    """Expose explicit Topics wherever Canonical stores their structured data."""
    topics, topic_errors, sources = _materialize_explicit_topics(snapshot)
    tree["topics"] = topics
    tree["errors"] = list(tree.get("errors", [])) + topic_errors

    tree.setdefault("source_result", {})["canonical_topics"] = {
        "enabled": bool(topics),
        "topic_count": len(topics),
        "sources": sources,
        "source": "explicit structured topics/topic fields across canonical tree",
        "reason": None if topics else "no explicit structured topics/topic fields present",
        "version_gate": False,
        "path_semantics": False,
        "legacy_root_fallback": False,
        "topic_semantic_authority": False,
        "inference": False,
    }
    return tree


__all__ = ["enrich_topics"]
