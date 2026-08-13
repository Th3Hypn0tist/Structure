from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath
from typing import Any

from input_modules.canonical import read as read_canonical
from input_modules.raw_json import read as read_raw_json
from projection_instances import topic_catalog
from source_adapter import load_snapshot
from source_target_isolation import normalize_repository
from structure_tree import tree_to_graph


class InputScopeCollision(ValueError):
    id = "STRUCTURE_INPUT_SCOPE_COLLISION"


SUPPORTED_DETECTORS = {
    "canonical": "Canonical",
    "raw_json": "Raw JSON",
}


def _scope(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().replace("\\", "/").strip("/")
    if not raw or raw == ".":
        return None
    parts = PurePosixPath(raw).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Invalid input directory scope: {value!r}")
    return "/".join(parts)


def _overlap(a: str, b: str) -> bool:
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def normalize_input(spec: dict[str, Any], index: int = 0) -> dict[str, Any]:
    input_id = str(spec.get("id") or f"input-{index + 1}").strip()
    name = str(spec.get("name") or input_id).strip()
    role = str(spec.get("role") or "other").strip()
    detector = str(spec.get("detector") or "canonical").strip()
    repository = str(spec.get("repository") or "").strip()
    branch = str(spec.get("branch") or "main").strip()
    directory = _scope(spec.get("directory"))
    path = str(spec.get("path") or "").strip() or None
    enabled = spec.get("enabled") is not False

    if not input_id or not name:
        raise ValueError("Input id and name must not be empty")
    if detector not in SUPPORTED_DETECTORS:
        raise ValueError(f"Unsupported input detector: {detector}")
    if "/" not in repository:
        raise ValueError(f"Input repository must be owner/repository: {repository!r}")
    if not branch:
        raise ValueError("Input branch must not be empty")

    return {
        "id": input_id,
        "name": name,
        "role": role,
        "detector": detector,
        "repository": repository,
        "branch": branch,
        "directory": directory,
        "path": path,
        "enabled": enabled,
    }


def validate_input_scopes(inputs: list[dict[str, Any]]) -> None:
    enabled = [item for item in inputs if item.get("enabled") is not False]
    ids = [str(item["id"]) for item in enabled]
    if len(ids) != len(set(ids)):
        raise ValueError("Input ids must be unique")

    for index, left in enumerate(enabled):
        left_repo = normalize_repository(left["repository"])
        for right in enabled[index + 1:]:
            if left_repo != normalize_repository(right["repository"]):
                continue
            left_dir = left.get("directory")
            right_dir = right.get("directory")
            if not left_dir or not right_dir:
                raise InputScopeCollision(
                    f"Inputs {left['id']!r} and {right['id']!r} share repository {left['repository']!r}; both require explicit disjoint directory scopes."
                )
            if _overlap(left_dir, right_dir):
                raise InputScopeCollision(
                    f"Input scopes overlap in {left['repository']!r}: {left_dir!r} and {right_dir!r}."
                )


def normalize_inputs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(specs, list) or not specs:
        raise ValueError("At least one input is required")
    if not all(isinstance(item, dict) for item in specs):
        raise ValueError("Every input must be an object")
    normalized = [normalize_input(spec, index) for index, spec in enumerate(specs)]
    validate_input_scopes(normalized)
    return normalized


def _scoped_snapshot(input_spec: dict[str, Any]):
    snapshot = load_snapshot(branch=input_spec["branch"], repo=input_spec["repository"])
    directory = input_spec.get("directory")
    if not directory:
        return snapshot
    prefix = directory.rstrip("/") + "/"
    files = {
        path[len(prefix):]: content
        for path, content in snapshot.files.items()
        if path.startswith(prefix) and len(path) > len(prefix)
    }
    if not files:
        raise ValueError(
            f"Input {input_spec['id']!r} directory {directory!r} contains no files at revision {snapshot.revision}."
        )
    return replace(snapshot, files=files)


def load_input(input_spec: dict[str, Any]) -> dict[str, Any]:
    snapshot = _scoped_snapshot(input_spec)
    detector = input_spec["detector"]
    if detector == "canonical":
        tree = read_canonical(snapshot)
        ruleset = "canonical_contract"
    elif detector == "raw_json":
        options = {"path": input_spec["path"]} if input_spec.get("path") else None
        tree = read_raw_json(snapshot, options)
        ruleset = "raw_json_syntax"
    else:
        raise ValueError(f"Unsupported input detector: {detector}")

    tree.setdefault("source", {})["input_id"] = input_spec["id"]
    tree["source"]["input_name"] = input_spec["name"]
    tree["source"]["input_role"] = input_spec["role"]
    tree["source"]["input_directory"] = input_spec.get("directory")
    tree["source"]["detector"] = detector
    return {
        "input": input_spec,
        "snapshot": snapshot,
        "tree": tree,
        "graph": tree_to_graph(tree),
        "ruleset": ruleset,
    }


def input_catalog(specs: list[dict[str, Any]]) -> dict[str, Any]:
    inputs = normalize_inputs(specs)
    items: list[dict[str, Any]] = []
    for input_spec in inputs:
        if not input_spec["enabled"]:
            items.append({"input": input_spec, "disabled": True, "topics": []})
            continue
        loaded = load_input(input_spec)
        tree = loaded["tree"]
        topics = [{"id": "all", "label": "all", "entry_count": len(tree.get("entries", []))}]
        if input_spec["detector"] == "canonical":
            topics += topic_catalog(tree)
        items.append({
            "input": input_spec,
            "disabled": False,
            "revision": loaded["snapshot"].revision,
            "valid": bool(tree.get("valid")),
            "projectable": bool(tree.get("projectable")),
            "entry_count": len(tree.get("entries", [])),
            "link_count": len(tree.get("links", [])),
            "topics": topics,
        })
    return {"inputs": items, "detectors": [{"id": key, "label": value} for key, value in SUPPORTED_DETECTORS.items()]}
