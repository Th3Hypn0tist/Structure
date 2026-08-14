from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any


def _entry_index(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("id")): entry
        for entry in tree.get("entries", [])
        if isinstance(entry, dict) and entry.get("id") is not None
    }


def _graph_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("id")): node
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("id") is not None
    }


def _indexes(tree: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    indexes = tree.get("indexes") if isinstance(tree.get("indexes"), dict) else {}
    flows = indexes.get("flows") if isinstance(indexes.get("flows"), dict) else {}
    topics = indexes.get("topic_membership") if isinstance(indexes.get("topic_membership"), dict) else {}
    behavior = indexes.get("behavior") if isinstance(indexes.get("behavior"), dict) else {}
    if not flows or not topics:
        raise ValueError("Event projection requires pre-resolved StructureTree indexes")
    return flows, topics, behavior


def _synthetic_node(node_id: str, name: str, *, kind: str, depth: int, parent: str | None, role: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": node_id,
        "name": name,
        "kind": kind,
        "type": kind,
        "projection_depth": depth,
        "projection_generation": depth + 1,
        "projection_parent_id": parent,
        "hierarchy_depth": depth,
        "projection_role": role,
        **extra,
    }


def _real_node(raw: dict[str, Any], *, depth: int, parent: str | None, role: str) -> dict[str, Any]:
    node = deepcopy(raw)
    node["projection_depth"] = depth
    node["projection_generation"] = depth + 1
    node["projection_parent_id"] = parent
    node["hierarchy_depth"] = depth
    node["projection_role"] = role
    return node


def _edge(edge_id: str, source: str, target: str, *, dimension: str, relation_type: str, causal: bool, evidence: str) -> dict[str, Any]:
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "dimension": dimension,
        "relation_type": relation_type,
        "causal": causal,
        "evidence": evidence,
        "inference": False,
    }


def _causal_step_slice(
    start_step_refs: list[str],
    step_by_id: dict[str, dict[str, Any]],
    flow_by_id: dict[str, dict[str, Any]],
    *,
    max_depth: int,
) -> tuple[dict[str, int], dict[str, str | None]]:
    depth: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    queue = deque()
    for ref in sorted(set(start_step_refs)):
        if ref not in step_by_id:
            continue
        depth[ref] = 0
        parent[ref] = None
        queue.append(ref)

    while queue:
        current = queue.popleft()
        current_depth = depth[current]
        if current_depth >= max_depth:
            continue
        step = step_by_id.get(current) or {}
        next_refs = [str(ref) for ref in step.get("next_step_refs", []) if str(ref) in step_by_id]
        for subflow_ref in step.get("subflow_refs", []):
            flow = flow_by_id.get(str(subflow_ref)) or {}
            explicit_entries = [str(ref) for ref in flow.get("entry_refs", []) if str(ref) in step_by_id]
            if explicit_entries:
                next_refs.extend(explicit_entries)
            else:
                step_refs = flow.get("step_refs", [])
                if step_refs:
                    next_refs.append(str(step_refs[0]))
        for ref in sorted(set(next_refs)):
            candidate = current_depth + 1
            if ref not in depth or candidate < depth[ref]:
                depth[ref] = candidate
                parent[ref] = current
                queue.append(ref)
    return depth, parent


def build_event_projection(
    tree: dict[str, Any],
    graph: dict[str, Any],
    event_id: str,
    *,
    max_depth: int = 32,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    """Assemble an Event projection from StructureTree indexes only."""
    event_id = str(event_id or "").strip()
    max_depth = max(0, min(64, int(max_depth)))
    entries = _entry_index(tree)
    graph_nodes = _graph_index(graph)
    event_entry = entries.get(event_id)
    if event_entry is None or event_id not in graph_nodes:
        raise KeyError(f"Unknown Event projection scope: {event_id}")

    flow_index, topic_index, behavior_index = _indexes(tree)
    flow_by_id = flow_index.get("by_id") if isinstance(flow_index.get("by_id"), dict) else {}
    step_by_id = flow_index.get("step_by_id") if isinstance(flow_index.get("step_by_id"), dict) else {}
    step_to_flow = flow_index.get("step_to_flow") if isinstance(flow_index.get("step_to_flow"), dict) else {}
    cause_steps = [str(ref) for ref in flow_index.get("event_cause_steps", {}).get(event_id, [])]
    explicit_bindings = [deepcopy(item) for item in flow_index.get("explicit_refs_by_identity", {}).get(event_id, []) if isinstance(item, dict)]
    topics_by_identity = topic_index.get("topics_by_identity") if isinstance(topic_index.get("topics_by_identity"), dict) else {}
    topic_by_id = topic_index.get("by_id") if isinstance(topic_index.get("by_id"), dict) else {}
    owner_by_id = behavior_index.get("owner_by_id") if isinstance(behavior_index.get("owner_by_id"), dict) else {}
    raw_by_id = behavior_index.get("raw_by_id") if isinstance(behavior_index.get("raw_by_id"), dict) else {}

    owner_ref = owner_by_id.get(event_id) or (str(event_entry.get("parent_id")) if event_entry.get("parent_id") is not None else None)
    event_raw = raw_by_id.get(event_id) if isinstance(raw_by_id.get(event_id), dict) else {}
    payload_fields = [str(value) for value in event_raw.get("payload", []) if isinstance(value, str)]
    topic_refs = [str(ref) for ref in topics_by_identity.get(event_id, [])]
    topics = [topic_by_id[ref] for ref in topic_refs if ref in topic_by_id]

    mechanism_flow_ids: set[str] = set()
    operation_refs: set[str] = set()
    for topic in topics:
        mechanism_flow_ids.update(str(ref) for ref in topic.get("flow_refs", []) if str(ref) in flow_by_id)
        operation_refs.update(str(ref) for ref in topic.get("operation_refs", []) if str(ref) in graph_nodes)
    mechanism_flow_ids.update(str(item.get("flow_id")) for item in explicit_bindings if str(item.get("flow_id")) in flow_by_id)
    mechanism_flow_ids.update(str(step_to_flow[ref]) for ref in cause_steps if ref in step_to_flow)

    causal_depths, causal_parents = _causal_step_slice(cause_steps, step_by_id, flow_by_id, max_depth=max_depth)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    depth_by_ref: dict[str, int] = {}
    node_ids: set[str] = set()

    def add_node(node: dict[str, Any]) -> None:
        node_id = str(node.get("id") or "")
        if not node_id or node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append(node)
        depth_by_ref[node_id] = int(node.get("projection_depth") or 0)

    add_node(_real_node(graph_nodes[event_id], depth=0, parent=None, role="event"))

    if owner_ref and owner_ref in graph_nodes:
        add_node(_real_node(graph_nodes[owner_ref], depth=1, parent=event_id, role="behavior_owner"))
        edges.append(_edge(f"event-owner:{event_id}->{owner_ref}", event_id, owner_ref, dimension="context", relation_type="behavior_owner", causal=False, evidence="indexes.behavior.owner_by_id"))

    for index, field in enumerate(payload_fields):
        node_id = f"event-payload:{event_id}:{index}"
        add_node(_synthetic_node(node_id, f"payload · {field}", kind="event_payload_field", depth=1, parent=event_id, role="payload_field", payload_field=field))
        edges.append(_edge(f"event-payload-edge:{event_id}:{index}", event_id, node_id, dimension="payload", relation_type="declares_payload_field", causal=False, evidence="indexes.behavior.raw_by_id payload"))

    for topic in sorted(topics, key=lambda item: str(item.get("id"))):
        topic_id = str(topic["id"])
        node_id = f"topic-context:{topic_id}"
        add_node(_synthetic_node(node_id, f"Topic · {topic.get('name') or topic_id}", kind="topic_context", depth=1, parent=event_id, role="topic_context", topic_ref=topic_id))
        edges.append(_edge(f"event-topic:{topic_id}->{event_id}", node_id, event_id, dimension="topic_context", relation_type="explicit_event_membership", causal=False, evidence="indexes.topic_membership.topics_by_identity"))

    for operation_ref in sorted(operation_refs):
        add_node(_real_node(graph_nodes[operation_ref], depth=2, parent=event_id, role="mechanism_operation"))
        edges.append(_edge(f"event-op-context:{event_id}->{operation_ref}", event_id, operation_ref, dimension="mechanism_context", relation_type="topic_operation_context", causal=False, evidence="indexes.topic_membership.by_id.operation_refs"))

    step_node_ids: dict[str, str] = {}
    for flow_id in sorted(mechanism_flow_ids):
        flow = flow_by_id.get(flow_id)
        if not isinstance(flow, dict):
            continue
        flow_node_id = f"flow-context:{flow_id}"
        add_node(_synthetic_node(flow_node_id, f"Flow · {flow.get('name') or flow_id}", kind="flow_context", depth=2, parent=event_id, role="flow_context", flow_ref=flow_id, flow_type=flow.get("flow_type")))
        edges.append(_edge(f"event-flow-context:{event_id}->{flow_id}", event_id, flow_node_id, dimension="mechanism_context", relation_type="declared_flow_context", causal=False, evidence="cached Topic/Flow/Event indexes"))

        for order, step_id in enumerate(flow.get("step_refs", [])):
            step_id = str(step_id)
            step = step_by_id.get(step_id)
            if not isinstance(step, dict):
                continue
            node_id = f"flow-step:{flow_id}:{step_id}"
            step_node_ids[step_id] = node_id
            action_ref = str(step.get("action_ref") or "")
            action_name = str(entries.get(action_ref, {}).get("name") or action_ref or step_id)
            condition = str(step.get("condition_ref") or "").strip()
            target = str(step.get("target_ref") or "").strip()
            label = f"{order + 1} · {action_name}"
            if target:
                label += f" → {target}"
            if condition:
                label += f" · if {condition}"
            is_causal = step_id in causal_depths
            depth = 3 + causal_depths[step_id] if is_causal else 3 + order
            add_node(_synthetic_node(
                node_id, label, kind="flow_step", depth=depth, parent=flow_node_id,
                role="causal_step" if is_causal else "flow_step_context",
                flow_ref=flow_id, step_ref=step_id, actor_ref=step.get("actor_ref"), action_ref=step.get("action_ref"),
                data_ref=step.get("data_ref"), target_ref=step.get("target_ref"), cause_ref=step.get("cause_ref"),
                condition_ref=step.get("condition_ref"), payload_ref=step.get("payload_ref"),
                result_refs=deepcopy(step.get("result_refs", [])), error_refs=deepcopy(step.get("error_refs", [])),
            ))
            if order == 0:
                edges.append(_edge(f"flow-membership:{flow_id}:{step_id}", flow_node_id, node_id, dimension="flow_context", relation_type="flow_contains_step", causal=False, evidence="indexes.flows.by_id.step_refs"))
            if step_id in cause_steps:
                edges.append(_edge(f"event-cause:{event_id}->{step_id}", event_id, node_id, dimension="impact", relation_type="explicit_event_cause", causal=True, evidence="indexes.flows.event_cause_steps"))

    for source_step, source_node in sorted(step_node_ids.items()):
        step = step_by_id.get(source_step) or {}
        for target_step in step.get("next_step_refs", []):
            target_step = str(target_step)
            target_node = step_node_ids.get(target_step)
            if target_node:
                edges.append(_edge(f"flow-next:{source_step}->{target_step}", source_node, target_node, dimension="flow", relation_type="explicit_next_step", causal=True, evidence="indexes.flows.step_by_id.next_step_refs"))

    if not cause_steps:
        gap_id = f"gap:event-causal-binding:{event_id}"
        add_node(_synthetic_node(gap_id, "GAP · no explicit Event → Flow causal binding", kind="semantic_gap", depth=2, parent=event_id, role="semantic_gap", gap_type="missing_event_causal_binding", gap_detail="No cached Flow step has cause_ref equal to this Event identity."))
        edges.append(_edge(f"event-gap:{event_id}", event_id, gap_id, dimension="gap", relation_type="missing_explicit_causal_binding", causal=False, evidence="indexes.flows.event_cause_steps has no Event entry"))

    for index, binding in enumerate(item for item in explicit_bindings if item.get("field") != "cause_ref"):
        binding_id = f"event-binding:{event_id}:{index}"
        step_part = f" · {binding.get('step_id')}" if binding.get("step_id") else ""
        add_node(_synthetic_node(binding_id, f"explicit ref · {binding.get('field')} · {binding.get('flow_id')}{step_part}", kind="event_reference_evidence", depth=2, parent=event_id, role="reference_evidence", **binding))
        edges.append(_edge(f"event-binding-edge:{event_id}:{index}", event_id, binding_id, dimension="evidence", relation_type="explicit_noncausal_event_reference", causal=False, evidence="indexes.flows.explicit_refs_by_identity"))

    projected = {
        "nodes": nodes,
        "edges": edges,
        "projection_root": event_id,
        "projection_root_name": str(event_entry.get("name") or event_id),
        "projection_base_ids": [event_id],
        "projection_relation_depth": max_depth,
        "projection_external_references": [],
        "projection_semantic_kind": "event",
        "event_projection": {
            "event_id": event_id,
            "owner_ref": owner_ref,
            "payload_fields": payload_fields,
            "topic_refs": topic_refs,
            "mechanism_flow_refs": sorted(mechanism_flow_ids),
            "explicit_bindings": explicit_bindings,
            "causal_start_step_refs": sorted(cause_steps),
            "causal_binding_present": bool(cause_steps),
            "gap_count": 0 if cause_steps else 1,
        },
    }
    metadata = {
        "projection_base": "event",
        "scope_type": "event",
        "scope_ref": event_id,
        "semantic_kind": "event",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "causal_binding_present": bool(cause_steps),
        "causal_step_count": len(causal_depths),
        "gap_count": 0 if cause_steps else 1,
        "structure_tree_index_sources": ["indexes.behavior", "indexes.topic_membership", "indexes.flows"],
        "projection_reanalysis_required": False,
        "topic_context_is_causal": False,
        "generic_relations_extend_causality": False,
        "inference": False,
    }
    return projected, metadata, depth_by_ref


__all__ = ["build_event_projection"]
