from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from topic_index import build_topic_index


INDEX_VERSION = "1.1"


def _entry_index(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("id")): entry
        for entry in tree.get("entries", [])
        if isinstance(entry, dict) and entry.get("id") is not None
    }


def _link_indexes(tree: dict[str, Any]) -> dict[str, Any]:
    by_dimension: dict[str, list[str]] = defaultdict(list)
    by_node: dict[str, list[str]] = defaultdict(list)
    adjacency_by_dimension: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    links_by_id: dict[str, dict[str, Any]] = {}

    for index, link in enumerate(tree.get("links", [])):
        if not isinstance(link, dict):
            continue
        source = str(link.get("source_id") or "")
        target = str(link.get("target_id") or "")
        if not source or not target:
            continue
        dimension = str(link.get("dimension") or "semantic")
        link_id = str(link.get("id") or f"link-{index}")
        links_by_id[link_id] = {
            "id": link_id,
            "source_id": source,
            "target_id": target,
            "dimension": dimension,
            "type": link.get("type") or dimension,
        }
        by_dimension[dimension].append(link_id)
        by_node[source].append(link_id)
        by_node[target].append(link_id)
        adjacency_by_dimension[dimension][source].append(target)
        adjacency_by_dimension[dimension][target].append(source)

    return {
        "by_id": links_by_id,
        "by_dimension": {key: sorted(values) for key, values in sorted(by_dimension.items())},
        "by_node": {key: sorted(values) for key, values in sorted(by_node.items())},
        "adjacency_by_dimension": {
            dimension: {node_id: sorted(set(targets)) for node_id, targets in sorted(nodes.items())}
            for dimension, nodes in sorted(adjacency_by_dimension.items())
        },
    }


def _hierarchy_index(tree: dict[str, Any]) -> dict[str, Any]:
    entries = _entry_index(tree)
    children: dict[str, list[str]] = defaultdict(list)
    roots: list[str] = []
    for entry_id, entry in entries.items():
        parent = entry.get("parent_id")
        if parent is None:
            roots.append(entry_id)
        elif str(parent) in entries:
            children[str(parent)].append(entry_id)

    depth: dict[str, int | None] = {}

    def resolve(entry_id: str, stack: set[str]) -> int | None:
        if entry_id in depth:
            return depth[entry_id]
        if entry_id in stack:
            depth[entry_id] = None
            return None
        parent = entries[entry_id].get("parent_id")
        if parent is None:
            depth[entry_id] = 0
            return 0
        parent_id = str(parent)
        if parent_id not in entries:
            depth[entry_id] = None
            return None
        parent_depth = resolve(parent_id, stack | {entry_id})
        depth[entry_id] = None if parent_depth is None else parent_depth + 1
        return depth[entry_id]

    for entry_id in entries:
        resolve(entry_id, set())

    return {
        "roots": sorted(roots),
        "children_by_parent": {key: sorted(values) for key, values in sorted(children.items())},
        "depth_by_id": depth,
    }


def _behavior_index(tree: dict[str, Any]) -> dict[str, Any]:
    by_dimension: dict[str, list[str]] = defaultdict(list)
    owner_by_id: dict[str, str] = {}
    raw_by_id: dict[str, dict[str, Any]] = {}
    for entry in tree.get("entries", []):
        if not isinstance(entry, dict) or entry.get("id") is None:
            continue
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        dimension = metadata.get("behavior_dimension")
        if not isinstance(dimension, str) or not dimension:
            continue
        entry_id = str(entry["id"])
        by_dimension[dimension].append(entry_id)
        owner = metadata.get("behavior_owner") or entry.get("parent_id")
        if owner is not None:
            owner_by_id[entry_id] = str(owner)
        raw = metadata.get("raw")
        if isinstance(raw, dict):
            raw_by_id[entry_id] = deepcopy(raw)
    return {
        "by_dimension": {key: sorted(values) for key, values in sorted(by_dimension.items())},
        "owner_by_id": owner_by_id,
        "raw_by_id": raw_by_id,
    }


def _flow_index(tree: dict[str, Any]) -> dict[str, Any]:
    flows_by_id: dict[str, dict[str, Any]] = {}
    step_to_flow: dict[str, str] = {}
    step_by_id: dict[str, dict[str, Any]] = {}
    event_cause_steps: dict[str, list[str]] = defaultdict(list)
    event_refs: dict[str, list[dict[str, str]]] = defaultdict(list)

    scalar_fields = ("actor_ref", "action_ref", "data_ref", "target_ref", "cause_ref", "condition_ref", "payload_ref", "resume_ref")
    list_fields = ("result_refs", "error_refs", "next_step_refs", "subflow_refs")

    for flow in tree.get("flows", []):
        if not isinstance(flow, dict) or not flow.get("id"):
            continue
        flow_id = str(flow["id"])
        flow_record = {
            "id": flow_id,
            "name": str(flow.get("name") or flow_id),
            "owner_ref": flow.get("owner_ref"),
            "flow_type": flow.get("flow_type"),
            "entry_refs": [str(ref) for ref in flow.get("entry_refs", [])],
            "exit_refs": [str(ref) for ref in flow.get("exit_refs", [])],
            "step_refs": [],
        }
        for ref in flow_record["entry_refs"]:
            event_refs[ref].append({"flow_id": flow_id, "step_id": "", "field": "entry_refs"})
        for ref in flow_record["exit_refs"]:
            event_refs[ref].append({"flow_id": flow_id, "step_id": "", "field": "exit_refs"})

        for step in flow.get("steps", []):
            if not isinstance(step, dict) or not step.get("id"):
                continue
            step_id = str(step["id"])
            flow_record["step_refs"].append(step_id)
            step_to_flow[step_id] = flow_id
            step_by_id[step_id] = deepcopy(step)
            cause_ref = step.get("cause_ref")
            if isinstance(cause_ref, str) and cause_ref:
                event_cause_steps[cause_ref].append(step_id)
            for field in scalar_fields:
                ref = step.get(field)
                if isinstance(ref, str) and ref:
                    event_refs[ref].append({"flow_id": flow_id, "step_id": step_id, "field": field})
            for field in list_fields:
                for ref in step.get(field, []):
                    if isinstance(ref, str) and ref:
                        event_refs[ref].append({"flow_id": flow_id, "step_id": step_id, "field": field})
        flows_by_id[flow_id] = flow_record

    return {
        "by_id": flows_by_id,
        "step_to_flow": step_to_flow,
        "step_by_id": step_by_id,
        "event_cause_steps": {key: sorted(set(values)) for key, values in sorted(event_cause_steps.items())},
        "explicit_refs_by_identity": {
            key: sorted(values, key=lambda item: (item["flow_id"], item["step_id"], item["field"]))
            for key, values in sorted(event_refs.items())
        },
    }


def _topic_membership_index(tree: dict[str, Any]) -> dict[str, Any]:
    topics_by_identity: dict[str, list[str]] = defaultdict(list)
    topics_by_flow: dict[str, list[str]] = defaultdict(list)
    topic_by_id: dict[str, dict[str, Any]] = {}
    for topic in tree.get("topics", []):
        if not isinstance(topic, dict) or not topic.get("id"):
            continue
        topic_id = str(topic["id"])
        composed = topic.get("composed_trace_surface") if isinstance(topic.get("composed_trace_surface"), dict) else {}
        member_refs = set(str(ref) for ref in topic.get("member_refs", []) if isinstance(ref, str))
        operation_refs = set(str(ref) for ref in topic.get("operation_refs", []) if isinstance(ref, str))
        event_refs = set(str(ref) for ref in topic.get("event_refs", []) if isinstance(ref, str))
        flow_refs = set(str(ref) for ref in topic.get("flow_refs", []) if isinstance(ref, str))
        relation_refs = set(str(ref) for ref in topic.get("relation_refs", []) if isinstance(ref, str))
        member_refs.update(str(ref) for ref in topic.get("resolved_grouping_member_refs", []) if isinstance(ref, str))
        member_refs.update(str(ref) for ref in composed.get("member_refs", []) if isinstance(ref, str))
        operation_refs.update(str(ref) for ref in composed.get("operation_refs", []) if isinstance(ref, str))
        event_refs.update(str(ref) for ref in composed.get("event_refs", []) if isinstance(ref, str))
        flow_refs.update(str(ref) for ref in composed.get("flow_refs", []) if isinstance(ref, str))
        relation_refs.update(str(ref) for ref in composed.get("relation_refs", []) if isinstance(ref, str))

        topic_by_id[topic_id] = {
            "id": topic_id,
            "name": str(topic.get("name") or topic_id),
            "owner_ref": topic.get("owner_ref"),
            "member_refs": sorted(member_refs),
            "operation_refs": sorted(operation_refs),
            "event_refs": sorted(event_refs),
            "flow_refs": sorted(flow_refs),
            "relation_refs": sorted(relation_refs),
        }
        for ref in member_refs | operation_refs | event_refs:
            topics_by_identity[ref].append(topic_id)
        for ref in flow_refs:
            topics_by_flow[ref].append(topic_id)
    return {
        "by_id": topic_by_id,
        "topics_by_identity": {key: sorted(set(values)) for key, values in sorted(topics_by_identity.items())},
        "topics_by_flow": {key: sorted(set(values)) for key, values in sorted(topics_by_flow.items())},
    }


def build_structure_indexes(tree: dict[str, Any]) -> dict[str, Any]:
    """Resolve reusable lookup/projection foundations once during import."""
    topic_index = build_topic_index(tree)
    indexes = {
        "version": INDEX_VERSION,
        "resolved_at": "StructureTree import",
        "identity": {"ids": sorted(_entry_index(tree))},
        "hierarchy": _hierarchy_index(tree),
        "links": _link_indexes(tree),
        "behavior": _behavior_index(tree),
        "flows": _flow_index(tree),
        "topic_membership": _topic_membership_index(tree),
        "topics": {
            "heading_refs": [str(item.get("id")) for item in topic_index.get("headings", []) if item.get("id")],
            "root_heading_refs": deepcopy(topic_index.get("root_heading_refs", [])),
        },
        "rules": {
            "source_semantics_resolved_once": True,
            "projection_reanalysis_required": False,
            "dynamic_projection_work": "scope slicing, bounded cached adjacency traversal, visual geometry only",
            "hardcoded_domain_names": False,
            "path_inference": False,
            "display_name_inference": False,
            "inference": False,
        },
    }
    tree["indexes"] = indexes
    return indexes


__all__ = ["build_structure_indexes"]
