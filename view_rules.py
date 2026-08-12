from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

VIEW_RULESET_DIR = os.path.join(os.path.dirname(__file__), "rulesets", "view")
MAX_BINDING_DEPTH = 6
MAX_BINDING_NODES = 1500


class ViewRuleError(ValueError):
    pass


def _decode_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _encode_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def resolve_pointer(data: Any, pointer: str) -> Any:
    if pointer in ("", "/"):
        return data
    if not pointer.startswith("/"):
        raise ViewRuleError(f"JSON Pointer must start with '/': {pointer}")
    current = data
    for raw in pointer[1:].split("/"):
        token = _decode_pointer_token(raw)
        if isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError) as exc:
                raise ViewRuleError(
                    f"Unresolved array pointer token {token!r} in {pointer}"
                ) from exc
        elif isinstance(current, dict):
            if token not in current:
                raise ViewRuleError(
                    f"Unresolved object pointer token {token!r} in {pointer}"
                )
            current = current[token]
        else:
            raise ViewRuleError(
                f"Pointer crosses primitive at {token!r} in {pointer}"
            )
    return current


def _read_json(snapshot: Any, source_path: str, cache: dict[str, Any]) -> Any:
    if source_path in cache:
        return cache[source_path]
    if source_path not in snapshot.files:
        raise ViewRuleError(
            f"View ruleset source path does not exist: {source_path}"
        )
    try:
        data = json.loads(snapshot.files[source_path].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ViewRuleError(
            f"View ruleset source is not valid UTF-8 JSON: {source_path}"
        ) from exc
    cache[source_path] = data
    return data


def load_view_ruleset(ruleset_id: str) -> dict[str, Any]:
    for filename in sorted(os.listdir(VIEW_RULESET_DIR)):
        if not filename.lower().endswith(".json"):
            continue
        path = os.path.join(VIEW_RULESET_DIR, filename)
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if data.get("id") == ruleset_id:
            return data
    raise ViewRuleError(f"Unknown view ruleset: {ruleset_id}")


def _label(value: Any, fallback: str) -> str:
    if isinstance(value, dict):
        for key in ("name", "title", "id", "classification", "type"):
            item = value.get(key)
            if isinstance(item, (str, int, float, bool)):
                return str(item)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return str(value)
    return fallback


def _summary(value: Any) -> str:
    if isinstance(value, dict):
        for key in (
            "purpose",
            "summary",
            "rule",
            "final_lock",
            "classification",
            "type",
        ):
            item = value.get(key)
            if isinstance(item, (str, int, float, bool)):
                return str(item)
        return f"{len(value)} fields"
    if isinstance(value, list):
        return f"{len(value)} entries"
    if value is None:
        return "null"
    return str(value)


def _explicit_status(value: Any, document: Any) -> str | None:
    if isinstance(value, dict) and isinstance(value.get("status"), str):
        return value["status"]
    if isinstance(document, dict) and isinstance(document.get("status"), str):
        return document["status"]
    return None


def _child_count(value: Any) -> int:
    if isinstance(value, (list, dict)):
        return len(value)
    return 0


def _pointer_child(base_pointer: str, key: str) -> str:
    base = "" if base_pointer in ("", "/") else base_pointer
    return f"{base}/{_encode_pointer_token(key)}" or "/"


def _iter_children(value: Any) -> list[tuple[str, Any]]:
    if isinstance(value, list):
        return [(str(index), child) for index, child in enumerate(value)]
    if isinstance(value, dict):
        return [(str(key), child) for key, child in value.items()]
    return []


def _binding_value(
    snapshot: Any,
    binding: dict[str, Any],
    cache: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    source_path = binding["source_path"]
    pointer = binding.get("pointer", "")
    document = _read_json(snapshot, source_path, cache)
    value = resolve_pointer(document, pointer)
    provenance = {
        "source_path": source_path,
        "pointer": pointer or "/",
        "source_status": (
            document.get("status") if isinstance(document, dict) else None
        ),
    }
    return value, provenance


def _binding_node(
    *,
    source_path: str,
    pointer: str,
    key: str,
    value: Any,
    document: Any,
    depth: int,
    parent_id: str | None,
) -> dict[str, Any]:
    return {
        "id": pointer or "/",
        "key": key,
        "title": _label(value, key),
        "summary": _summary(value),
        "status": _explicit_status(value, document),
        "child_count": _child_count(value),
        "value": (
            deepcopy(value) if not isinstance(value, (dict, list)) else None
        ),
        "depth": depth,
        "parent_id": parent_id,
        "provenance": {
            "source_path": source_path,
            "pointer": pointer or "/",
            "source_status": (
                document.get("status")
                if isinstance(document, dict)
                else None
            ),
        },
    }


def binding_children(
    snapshot: Any,
    source_path: str,
    pointer: str,
) -> dict[str, Any]:
    """Return the direct structural children of an explicit JSON binding."""
    cache: dict[str, Any] = {}
    document = _read_json(snapshot, source_path, cache)
    value = resolve_pointer(document, pointer)
    children: list[dict[str, Any]] = []

    for key, child in _iter_children(value):
        child_pointer = _pointer_child(pointer, key)
        children.append(
            _binding_node(
                source_path=source_path,
                pointer=child_pointer,
                key=key,
                value=child,
                document=document,
                depth=1,
                parent_id=pointer or "/",
            )
        )

    return {
        "source_path": source_path,
        "pointer": pointer or "/",
        "status": _explicit_status(value, document),
        "child_count": len(children),
        "children": children,
    }


def binding_tree(
    snapshot: Any,
    source_path: str,
    pointer: str,
    requested_depth: int,
) -> dict[str, Any]:
    """Return a bounded structural traversal rooted at one explicit JSON binding."""
    if requested_depth < 0:
        requested_depth = 0
    effective_limit = min(requested_depth, MAX_BINDING_DEPTH)

    cache: dict[str, Any] = {}
    document = _read_json(snapshot, source_path, cache)
    root_value = resolve_pointer(document, pointer)
    root_pointer = pointer or "/"
    root_key = (
        _decode_pointer_token(root_pointer.rstrip("/").split("/")[-1])
        if root_pointer not in ("", "/")
        else "/"
    )

    nodes: list[dict[str, Any]] = [
        _binding_node(
            source_path=source_path,
            pointer=root_pointer,
            key=root_key,
            value=root_value,
            document=document,
            depth=0,
            parent_id=None,
        )
    ]
    truncated = False
    max_depth_seen = 0

    queue: list[tuple[str, Any, int]] = [(root_pointer, root_value, 0)]
    qindex = 0
    while qindex < len(queue):
        parent_pointer, parent_value, parent_depth = queue[qindex]
        qindex += 1
        if parent_depth >= effective_limit:
            continue

        for key, child in _iter_children(parent_value):
            if len(nodes) >= MAX_BINDING_NODES:
                truncated = True
                queue.clear()
                break

            child_pointer = _pointer_child(parent_pointer, key)
            child_depth = parent_depth + 1
            nodes.append(
                _binding_node(
                    source_path=source_path,
                    pointer=child_pointer,
                    key=key,
                    value=child,
                    document=document,
                    depth=child_depth,
                    parent_id=parent_pointer,
                )
            )
            max_depth_seen = max(max_depth_seen, child_depth)
            if child_depth < effective_limit and isinstance(
                child, (dict, list)
            ):
                queue.append((child_pointer, child, child_depth))

    return {
        "source_path": source_path,
        "pointer": root_pointer,
        "status": _explicit_status(root_value, document),
        "child_count": _child_count(root_value),
        "requested_depth": requested_depth,
        "effective_depth": min(effective_limit, max_depth_seen)
        if nodes
        else 0,
        "max_depth": MAX_BINDING_DEPTH,
        "node_budget": MAX_BINDING_NODES,
        "node_count": len(nodes),
        "truncated": truncated,
        "nodes": nodes,
    }


def _materialize_collection(
    snapshot: Any,
    binding: dict[str, Any],
    cache: dict[str, Any],
    role: str,
) -> list[dict[str, Any]]:
    value, provenance = _binding_value(snapshot, binding, cache)
    document = _read_json(snapshot, provenance["source_path"], cache)
    mode = binding.get("mode", "value")
    limit = binding.get("limit")

    if mode == "array":
        if not isinstance(value, list):
            raise ViewRuleError(f"Expected array at {provenance}")
        iterable: list[tuple[Any, Any]] = list(enumerate(value))
    elif mode == "object_entries":
        if not isinstance(value, dict):
            raise ViewRuleError(f"Expected object at {provenance}")
        iterable = list(value.items())
    elif mode == "object_keys":
        if not isinstance(value, dict):
            raise ViewRuleError(f"Expected object at {provenance}")
        iterable = [(key, key) for key in value.keys()]
    elif mode == "value":
        iterable = [(binding.get("label", "value"), value)]
    else:
        raise ViewRuleError(f"Unknown view binding mode: {mode}")

    if isinstance(limit, int) and limit >= 0:
        iterable = iterable[:limit]

    items: list[dict[str, Any]] = []
    for key, item in iterable:
        item_pointer = provenance["pointer"]
        if mode == "array":
            item_pointer = _pointer_child(item_pointer, str(key))
        elif mode in ("object_entries", "object_keys"):
            item_pointer = _pointer_child(item_pointer, str(key))

        items.append(
            {
                "role": role,
                "key": str(key),
                "title": _label(item, str(key)),
                "summary": _summary(item),
                "status": _explicit_status(item, document),
                "child_count": _child_count(item),
                "value": (
                    deepcopy(item)
                    if not isinstance(item, (dict, list))
                    else None
                ),
                "provenance": {
                    "source_path": provenance["source_path"],
                    "pointer": item_pointer or "/",
                    "source_status": provenance.get("source_status"),
                },
            }
        )
    return items


def _uniform_status(items: list[dict[str, Any]]) -> str | None:
    statuses = {item.get("status") for item in items if item.get("status")}
    return next(iter(statuses)) if len(statuses) == 1 else None


def build_view_projection(
    snapshot: Any,
    ruleset_id: str,
) -> dict[str, Any]:
    rules = load_view_ruleset(ruleset_id)
    cache: dict[str, Any] = {}
    sections: list[dict[str, Any]] = []

    for section in rules.get("sections", []):
        projected = {
            "id": section["id"],
            "title": section.get("title", section["id"]),
            "subtitle": section.get("subtitle", ""),
            "template": section.get("template", "section"),
            "accent": section.get("accent", "primary"),
            "blocks": [],
        }

        for block in section.get("blocks", []):
            materialized = {
                "id": block["id"],
                "title": block.get("title", block["id"]),
                "template": block.get("template", "card_grid"),
                "accent": block.get(
                    "accent", section.get("accent", "primary")
                ),
                "items": [],
            }

            if "binding" in block:
                materialized["items"] = _materialize_collection(
                    snapshot,
                    block["binding"],
                    cache,
                    block.get("item_role", "card"),
                )

            for item in block.get("items", []):
                if "binding" in item:
                    value, provenance = _binding_value(
                        snapshot, item["binding"], cache
                    )
                    document = _read_json(
                        snapshot, provenance["source_path"], cache
                    )
                    materialized["items"].append(
                        {
                            "role": item.get("role", "card"),
                            "key": item["id"],
                            "title": item.get("title")
                            or _label(value, item["id"]),
                            "summary": item.get("summary")
                            or _summary(value),
                            "status": _explicit_status(value, document),
                            "child_count": _child_count(value),
                            "value": (
                                deepcopy(value)
                                if not isinstance(value, (dict, list))
                                else None
                            ),
                            "provenance": provenance,
                        }
                    )
                else:
                    materialized["items"].append(
                        {
                            "role": item.get("role", "card"),
                            "key": item["id"],
                            "title": item.get("title", item["id"]),
                            "summary": item.get("summary", ""),
                            "status": item.get("status"),
                            "child_count": item.get("child_count", 0),
                            "value": item.get("value"),
                            "provenance": item.get("provenance"),
                        }
                    )

            materialized["status"] = _uniform_status(
                materialized["items"]
            )
            projected["blocks"].append(materialized)

        block_statuses = [
            {"status": block.get("status")}
            for block in projected["blocks"]
            if block.get("status")
        ]
        projected["status"] = _uniform_status(block_statuses)
        sections.append(projected)

    return {
        "id": rules["id"],
        "name": rules.get("name", rules["id"]),
        "version": rules.get("version"),
        "status": rules.get("status"),
        "title": rules.get("title", rules.get("name", rules["id"])),
        "subtitle": rules.get("subtitle", ""),
        "render_ruleset": rules.get(
            "render_ruleset", "render.aigmos_master_map"
        ),
        "source_revision": snapshot.revision,
        "sections": sections,
        "hard_gates": rules.get("hard_gates", []),
    }
