from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

VIEW_RULESET_DIR = os.path.join(os.path.dirname(__file__), "rulesets", "view")


class ViewRuleError(ValueError):
    pass


def _decode_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


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
                raise ViewRuleError(f"Unresolved array pointer token {token!r} in {pointer}") from exc
        elif isinstance(current, dict):
            if token not in current:
                raise ViewRuleError(f"Unresolved object pointer token {token!r} in {pointer}")
            current = current[token]
        else:
            raise ViewRuleError(f"Pointer crosses primitive at {token!r} in {pointer}")
    return current


def _read_json(snapshot: Any, source_path: str, cache: dict[str, Any]) -> Any:
    if source_path in cache:
        return cache[source_path]
    if source_path not in snapshot.files:
        raise ViewRuleError(f"View ruleset source path does not exist: {source_path}")
    try:
        data = json.loads(snapshot.files[source_path].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ViewRuleError(f"View ruleset source is not valid UTF-8 JSON: {source_path}") from exc
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
            if key in value and isinstance(value[key], (str, int, float, bool)):
                return str(value[key])
    if isinstance(value, (str, int, float, bool)) or value is None:
        return str(value)
    return fallback


def _summary(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("purpose", "summary", "rule", "final_lock", "classification", "type"):
            item = value.get(key)
            if isinstance(item, (str, int, float, bool)):
                return str(item)
        return f"{len(value)} fields"
    if isinstance(value, list):
        return f"{len(value)} entries"
    if value is None:
        return "null"
    return str(value)


def _binding_value(snapshot: Any, binding: dict[str, Any], cache: dict[str, Any]) -> tuple[Any, dict[str, str]]:
    source_path = binding["source_path"]
    pointer = binding.get("pointer", "")
    data = _read_json(snapshot, source_path, cache)
    value = resolve_pointer(data, pointer)
    provenance = {"source_path": source_path, "pointer": pointer or "/"}
    return value, provenance


def _materialize_collection(
    snapshot: Any,
    binding: dict[str, Any],
    cache: dict[str, Any],
    role: str,
) -> list[dict[str, Any]]:
    value, provenance = _binding_value(snapshot, binding, cache)
    mode = binding.get("mode", "value")
    limit = binding.get("limit")
    items: list[dict[str, Any]] = []

    if mode == "array":
        if not isinstance(value, list):
            raise ViewRuleError(f"Expected array at {provenance}")
        iterable = list(enumerate(value))
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

    for key, item in iterable:
        item_pointer = provenance["pointer"]
        if mode == "array":
            item_pointer = ("" if item_pointer == "/" else item_pointer) + f"/{key}"
        elif mode in ("object_entries", "object_keys"):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            item_pointer = ("" if item_pointer == "/" else item_pointer) + f"/{escaped}"
        items.append({
            "role": role,
            "key": str(key),
            "title": _label(item, str(key)),
            "summary": _summary(item),
            "value": deepcopy(item) if not isinstance(item, (dict, list)) else None,
            "provenance": {"source_path": provenance["source_path"], "pointer": item_pointer or "/"},
        })
    return items


def build_view_projection(snapshot: Any, ruleset_id: str) -> dict[str, Any]:
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
                "accent": block.get("accent", section.get("accent", "primary")),
                "items": [],
            }
            if "binding" in block:
                materialized["items"] = _materialize_collection(
                    snapshot, block["binding"], cache, block.get("item_role", "card")
                )
            for item in block.get("items", []):
                if "binding" in item:
                    value, provenance = _binding_value(snapshot, item["binding"], cache)
                    materialized["items"].append({
                        "role": item.get("role", "card"),
                        "key": item["id"],
                        "title": item.get("title") or _label(value, item["id"]),
                        "summary": item.get("summary") or _summary(value),
                        "value": deepcopy(value) if not isinstance(value, (dict, list)) else None,
                        "provenance": provenance,
                    })
                else:
                    materialized["items"].append({
                        "role": item.get("role", "card"),
                        "key": item["id"],
                        "title": item.get("title", item["id"]),
                        "summary": item.get("summary", ""),
                        "value": item.get("value"),
                        "provenance": item.get("provenance"),
                    })
            projected["blocks"].append(materialized)
        sections.append(projected)

    return {
        "id": rules["id"],
        "name": rules.get("name", rules["id"]),
        "version": rules.get("version"),
        "status": rules.get("status"),
        "title": rules.get("title", rules.get("name", rules["id"])),
        "subtitle": rules.get("subtitle", ""),
        "render_ruleset": rules.get("render_ruleset", "render.aigmos_master_map"),
        "source_revision": snapshot.revision,
        "sections": sections,
        "hard_gates": rules.get("hard_gates", []),
    }
