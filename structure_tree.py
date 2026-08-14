from __future__ import annotations

from copy import deepcopy
from typing import Any

FORMAT = "STRUCTUREPROJECTOR_STRUCTURE_TREE"
VERSION = "1.1"


def new_tree(*, input_module: str, source: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "version": VERSION,
        "input_module": input_module,
        "source": deepcopy(source),
        "roots": [],
        "entries": [],
        "links": [],
        "topics": [],
        "flows": [],
        "outsiders": {},
        "errors": [],
        "warnings": [],
    }


def add_entry(
    tree: dict[str, Any],
    *,
    entry_id: str,
    name: str,
    kind: str,
    parent_id: str | None,
    entry_type: str | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = {
        "id": entry_id,
        "name": name,
        "kind": kind,
        "type": entry_type,
        "parent_id": parent_id,
        "status": status,
        "metadata": deepcopy(metadata or {}),
        "provenance": deepcopy(provenance or {}),
    }
    tree["entries"].append(entry)
    if parent_id is None:
        tree["roots"].append(entry_id)
    return entry


def add_link(
    tree: dict[str, Any],
    *,
    link_id: str | None,
    source_id: str,
    target_id: str,
    dimension: str,
    link_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    link = {
        "id": link_id,
        "source_id": source_id,
        "target_id": target_id,
        "dimension": dimension,
        "type": link_type or dimension,
        "metadata": deepcopy(metadata or {}),
        "provenance": deepcopy(provenance or {}),
    }
    tree["links"].append(link)
    return link


def add_flow(
    tree: dict[str, Any],
    *,
    flow_id: str,
    kind: str,
    actor_ref: str,
    action_ref: str,
    target_ref: str,
    cause_ref: str,
    result_refs: list[str],
    data_ref: str | None = None,
    condition_ref: str | None = None,
    payload_ref: str | None = None,
    error_refs: list[str] | None = None,
    owner_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Legacy flat-flow writer retained for pre-1.4 inputs."""
    flow = {
        "id": flow_id,
        "kind": kind,
        "actor_ref": actor_ref,
        "action_ref": action_ref,
        "data_ref": data_ref,
        "target_ref": target_ref,
        "cause_ref": cause_ref,
        "result_refs": list(result_refs),
        "condition_ref": condition_ref,
        "payload_ref": payload_ref,
        "error_refs": list(error_refs or []),
        "owner_ref": owner_ref,
        "metadata": deepcopy(metadata or {}),
        "provenance": deepcopy(provenance or {}),
    }
    tree["flows"].append(flow)
    return flow


def _validate_flat_flow(flow: dict[str, Any], ids: set[str], errors: list[dict[str, Any]]) -> None:
    flow_id = str(flow.get("id") or "")
    for field, error_id in (
        ("actor_ref", "CW_FLOW_UNRESOLVED_ACTOR"),
        ("action_ref", "CW_FLOW_UNRESOLVED_ACTION"),
        ("target_ref", "CW_FLOW_UNRESOLVED_TARGET"),
        ("cause_ref", "CW_FLOW_UNRESOLVED_CAUSE"),
    ):
        ref = flow.get(field)
        if not isinstance(ref, str) or ref not in ids:
            errors.append({"id": error_id, "message": f"Flow {flow_id} has unresolved {field}: {ref}", "flow": flow_id, "field": field})
    data_ref = flow.get("data_ref")
    if data_ref is not None and data_ref not in ids:
        errors.append({"id": "CW_FLOW_HIDDEN_REFERENCE", "message": f"Flow {flow_id} has unresolved data_ref: {data_ref}", "flow": flow_id})
    result_refs = flow.get("result_refs")
    if not isinstance(result_refs, list):
        errors.append({"id": "CW_FLOW_RESULT_REFS_SHAPE", "message": f"Flow {flow_id} result_refs must be an array", "flow": flow_id})
    else:
        for ref in result_refs:
            if ref not in ids:
                errors.append({"id": "CW_FLOW_UNRESOLVED_RESULT", "message": f"Flow {flow_id} has unresolved result_ref: {ref}", "flow": flow_id})


def _validate_flow_container(
    flow: dict[str, Any],
    ids: set[str],
    flow_ids: set[str],
    global_step_ids: set[str],
    errors: list[dict[str, Any]],
) -> None:
    flow_id = str(flow.get("id") or "")
    owner_ref = flow.get("owner_ref")
    if not isinstance(owner_ref, str) or owner_ref not in ids:
        errors.append({"id": "CW_FLOW_UNRESOLVED_OWNER", "message": f"Flow {flow_id} has unresolved owner_ref: {owner_ref}", "flow": flow_id})

    steps = flow.get("steps")
    if not isinstance(steps, list):
        errors.append({"id": "CW_FLOW_STEPS_SHAPE", "message": f"Flow {flow_id} steps must be an array", "flow": flow_id})
        return
    local_step_ids = {str(step.get("id")) for step in steps if isinstance(step, dict) and step.get("id")}

    for field in ("entry_refs", "exit_refs"):
        refs = flow.get(field)
        if not isinstance(refs, list):
            errors.append({"id": "CW_FLOW_REFERENCE_SHAPE", "message": f"Flow {flow_id} {field} must be an array", "flow": flow_id, "field": field})
            continue
        for ref in refs:
            if ref not in local_step_ids and ref not in ids:
                errors.append({"id": "CW_FLOW_UNRESOLVED_REFERENCE", "message": f"Flow {flow_id} has unresolved {field}: {ref}", "flow": flow_id, "field": field})

    for step in steps:
        if not isinstance(step, dict):
            errors.append({"id": "CW_FLOW_STEP_SHAPE", "message": f"Flow {flow_id} contains a non-object step", "flow": flow_id})
            continue
        step_id = str(step.get("id") or "")
        if not step_id:
            errors.append({"id": "CW_FLOW_STEP_MISSING_ID", "message": f"Flow {flow_id} contains a step without id", "flow": flow_id})
            continue
        for field in ("actor_ref", "action_ref", "data_ref", "target_ref", "cause_ref", "condition_ref", "payload_ref"):
            ref = step.get(field)
            if ref is not None and ref not in ids:
                errors.append({"id": "CW_FLOW_STEP_UNRESOLVED_REFERENCE", "message": f"Step {step_id} has unresolved {field}: {ref}", "flow": flow_id, "step": step_id, "field": field})
        for field in ("result_refs", "error_refs"):
            refs = step.get(field)
            if not isinstance(refs, list):
                errors.append({"id": "CW_FLOW_STEP_REFERENCE_SHAPE", "message": f"Step {step_id} {field} must be an array", "flow": flow_id, "step": step_id, "field": field})
                continue
            for ref in refs:
                if ref not in ids:
                    errors.append({"id": "CW_FLOW_STEP_UNRESOLVED_REFERENCE", "message": f"Step {step_id} has unresolved {field}: {ref}", "flow": flow_id, "step": step_id, "field": field})
        next_refs = step.get("next_step_refs")
        if not isinstance(next_refs, list):
            errors.append({"id": "CW_FLOW_STEP_REFERENCE_SHAPE", "message": f"Step {step_id} next_step_refs must be an array", "flow": flow_id, "step": step_id})
        else:
            for ref in next_refs:
                if ref not in local_step_ids:
                    errors.append({"id": "CW_FLOW_UNRESOLVED_NEXT_STEP", "message": f"Step {step_id} has unresolved next_step_ref: {ref}", "flow": flow_id, "step": step_id})
        subflow_refs = step.get("subflow_refs")
        if not isinstance(subflow_refs, list):
            errors.append({"id": "CW_FLOW_STEP_REFERENCE_SHAPE", "message": f"Step {step_id} subflow_refs must be an array", "flow": flow_id, "step": step_id})
        else:
            for ref in subflow_refs:
                if ref not in flow_ids:
                    errors.append({"id": "CW_FLOW_UNRESOLVED_SUBFLOW", "message": f"Step {step_id} has unresolved subflow_ref: {ref}", "flow": flow_id, "step": step_id})
        resume_ref = step.get("resume_ref")
        if resume_ref is not None and resume_ref not in global_step_ids:
            errors.append({"id": "CW_FLOW_UNRESOLVED_RESUME", "message": f"Step {step_id} has unresolved resume_ref: {resume_ref}", "flow": flow_id, "step": step_id})


def validate_tree(tree: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if tree.get("format") != FORMAT:
        errors.append({"id": "SP_TREE_FORMAT", "message": f"Expected {FORMAT}"})
    if tree.get("version") != VERSION:
        errors.append({"id": "SP_TREE_VERSION", "message": f"Expected StructureTree version {VERSION}"})

    entries = tree.get("entries")
    links = tree.get("links")
    topics = tree.get("topics", [])
    flows = tree.get("flows")
    if not isinstance(entries, list):
        return errors + [{"id": "SP_TREE_ENTRIES", "message": "entries must be an array"}]
    if not isinstance(links, list):
        return errors + [{"id": "SP_TREE_LINKS", "message": "links must be an array"}]
    if not isinstance(topics, list):
        return errors + [{"id": "SP_TREE_TOPICS", "message": "topics must be an array"}]
    if not isinstance(flows, list):
        return errors + [{"id": "SP_TREE_FLOWS", "message": "flows must be an array"}]

    ids: set[str] = set()
    for entry in entries:
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            errors.append({"id": "SP_TREE_ENTRY_ID", "message": "Every entry requires a non-empty id"})
            continue
        if entry_id in ids:
            errors.append({"id": "SP_TREE_DUPLICATE_ID", "message": f"Duplicate StructureTree entry: {entry_id}"})
        ids.add(entry_id)

    for entry in entries:
        parent_id = entry.get("parent_id")
        if parent_id is not None and parent_id not in ids:
            errors.append({"id": "SP_TREE_PARENT", "message": f"Unresolved parent_id: {parent_id}", "entry": entry.get("id")})

    for link in links:
        source_id = link.get("source_id")
        target_id = link.get("target_id")
        if source_id not in ids:
            errors.append({"id": "SP_TREE_LINK_SOURCE", "message": f"Unresolved link source: {source_id}"})
        if target_id not in ids:
            errors.append({"id": "SP_TREE_LINK_TARGET", "message": f"Unresolved link target: {target_id}"})

    topic_ids: set[str] = set()
    for topic in topics:
        topic_id = topic.get("id") if isinstance(topic, dict) else None
        if not isinstance(topic_id, str) or not topic_id:
            errors.append({"id": "SP_TREE_TOPIC_ID", "message": "Every Topic requires a non-empty id"})
            continue
        if topic_id in topic_ids:
            errors.append({"id": "SP_TREE_DUPLICATE_TOPIC_ID", "message": f"Duplicate StructureTree Topic: {topic_id}"})
        topic_ids.add(topic_id)

    flow_ids: set[str] = set()
    global_step_ids: set[str] = set()
    for flow in flows:
        if not isinstance(flow, dict):
            errors.append({"id": "CW_FLOW_SHAPE", "message": "Every flow must be an object"})
            continue
        flow_id = flow.get("id")
        if not isinstance(flow_id, str) or not flow_id:
            errors.append({"id": "CW_FLOW_MISSING_ID", "message": "Every flow requires a non-empty id"})
            continue
        if flow_id in flow_ids:
            errors.append({"id": "CW_FLOW_DUPLICATE_ID", "message": f"Duplicate flow id: {flow_id}"})
        flow_ids.add(flow_id)
        if isinstance(flow.get("steps"), list):
            for step in flow["steps"]:
                if not isinstance(step, dict) or not step.get("id"):
                    continue
                step_id = str(step["id"])
                if step_id in global_step_ids:
                    errors.append({"id": "CW_FLOW_DUPLICATE_STEP_ID", "message": f"Duplicate flow step id: {step_id}"})
                global_step_ids.add(step_id)

    for flow in flows:
        if not isinstance(flow, dict) or not flow.get("id"):
            continue
        if "steps" in flow:
            _validate_flow_container(flow, ids, flow_ids, global_step_ids, errors)
        else:
            _validate_flat_flow(flow, ids, errors)
    return errors


def tree_to_graph(tree: dict[str, Any]) -> dict[str, Any]:
    """Compatibility adapter for projection engines; preserves Topics and flows separately."""
    nodes = []
    for entry in tree.get("entries", []):
        nodes.append({
            "id": entry.get("id"),
            "name": entry.get("name"),
            "type": entry.get("type"),
            "status": entry.get("status"),
            "source_role": entry.get("metadata", {}).get("source_role"),
            "source": entry.get("provenance", {}).get("path"),
            "kind": entry.get("kind"),
            "raw": deepcopy(entry),
        })

    edges = []
    for link in tree.get("links", []):
        edges.append({
            "id": link.get("id"),
            "dimension": link.get("dimension"),
            "source": link.get("source_id"),
            "target": link.get("target_id"),
            "type": link.get("type"),
            "raw": deepcopy(link),
        })

    existing = {(edge["source"], edge["target"], edge["dimension"]) for edge in edges}
    for entry in tree.get("entries", []):
        parent_id = entry.get("parent_id")
        if parent_id is None:
            continue
        key = (parent_id, entry.get("id"), "tree")
        if key in existing:
            continue
        edges.append({
            "id": f"tree:{parent_id}->{entry.get('id')}",
            "dimension": "tree",
            "source": parent_id,
            "target": entry.get("id"),
            "type": "contains",
            "raw": {"source": "StructureTree.parent_id"},
        })
    return {
        "nodes": nodes,
        "edges": edges,
        "topics": deepcopy(tree.get("topics", [])),
        "flows": deepcopy(tree.get("flows", [])),
        "outsiders": deepcopy(tree.get("outsiders", {})),
    }
