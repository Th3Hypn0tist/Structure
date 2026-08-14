from __future__ import annotations

from copy import deepcopy
from typing import Any

from event_trace import build_event_impact


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


def _topic_contexts(tree: dict[str, Any], event_id: str) -> list[dict[str, Any]]:
    out = []
    for topic in tree.get("topics", []):
        if not isinstance(topic, dict) or not topic.get("id"):
            continue
        if event_id not in {str(ref) for ref in topic.get("event_refs", [])}:
            continue
        out.append({
            "id": str(topic["id"]),
            "name": str(topic.get("name") or topic["id"]),
            "owner_ref": str(topic.get("owner_ref") or "") or None,
            "operation_refs": [str(ref) for ref in topic.get("operation_refs", [])],
            "flow_refs": [str(ref) for ref in topic.get("flow_refs", [])],
            "relation_refs": [str(ref) for ref in topic.get("relation_refs", [])],
        })
    return sorted(out, key=lambda item: item["id"])


def _flow_index(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(flow.get("id")): flow
        for flow in tree.get("flows", [])
        if isinstance(flow, dict) and flow.get("id")
    }


def _step_event_bindings(tree: dict[str, Any], event_id: str) -> list[dict[str, Any]]:
    """Return exact machine-readable Event references from Flow data.

    Only cause_ref is a causal Event->step binding. Other fields are explicit
    contextual references and are surfaced as evidence without becoming causal.
    """
    scalar_fields = ("actor_ref", "action_ref", "data_ref", "target_ref", "cause_ref", "condition_ref", "payload_ref", "resume_ref")
    list_fields = ("result_refs", "error_refs", "next_step_refs", "subflow_refs")
    out: list[dict[str, Any]] = []
    for flow in tree.get("flows", []):
        if not isinstance(flow, dict) or not flow.get("id"):
            continue
        flow_id = str(flow["id"])
        if event_id in {str(ref) for ref in flow.get("entry_refs", [])}:
            out.append({"flow_id": flow_id, "step_id": None, "field": "entry_refs", "causal": False})
        if event_id in {str(ref) for ref in flow.get("exit_refs", [])}:
            out.append({"flow_id": flow_id, "step_id": None, "field": "exit_refs", "causal": False})
        for step in flow.get("steps", []):
            if not isinstance(step, dict) or not step.get("id"):
                continue
            step_id = str(step["id"])
            for field in scalar_fields:
                if step.get(field) == event_id:
                    out.append({"flow_id": flow_id, "step_id": step_id, "field": field, "causal": field == "cause_ref"})
            for field in list_fields:
                if event_id in {str(ref) for ref in step.get(field, [])}:
                    out.append({"flow_id": flow_id, "step_id": step_id, "field": field, "causal": False})
    return sorted(out, key=lambda item: (item["flow_id"], str(item.get("step_id") or ""), item["field"]))


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


def build_event_projection(
    tree: dict[str, Any],
    graph: dict[str, Any],
    event_id: str,
    *,
    max_depth: int = 32,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    """Build an informative Event projection without inventing causality.

    The projection contains four explicitly separated surfaces:
      1. the Event identity and payload schema,
      2. its behavior owner and Topic declarations,
      3. mechanism Flow context explicitly co-declared by those Topics,
      4. actual Event->Flow causal bindings, or an explicit gap when absent.

    Topic co-membership is context only. Flow step continuation is causal only
    inside the Flow. The Event starts a causal path only when cause_ref names the
    exact Event identity.
    """
    event_id = str(event_id or "").strip()
    entries = _entry_index(tree)
    graph_nodes = _graph_index(graph)
    event_entry = entries.get(event_id)
    if event_entry is None or event_id not in graph_nodes:
        raise KeyError(f"Unknown Impact entry Event: {event_id}")

    event_metadata = event_entry.get("metadata") if isinstance(event_entry.get("metadata"), dict) else {}
    event_raw = event_metadata.get("raw") if isinstance(event_metadata.get("raw"), dict) else {}
    owner_ref = str(event_metadata.get("behavior_owner") or event_entry.get("parent_id") or "") or None
    topics = _topic_contexts(tree, event_id)
    flows = _flow_index(tree)
    bindings = _step_event_bindings(tree, event_id)
    trace = build_event_impact(tree, event_id, max_depth=max_depth)
    causal_start_steps = {str(ref) for ref in trace.get("start_step_refs", [])}

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
        edges.append(_edge(
            f"event-owner:{event_id}->{owner_ref}", event_id, owner_ref,
            dimension="context", relation_type="behavior_owner", causal=False,
            evidence="behavior event metadata.behavior_owner",
        ))

    payload_fields = [str(value) for value in event_raw.get("payload", []) if isinstance(value, str)]
    for index, field in enumerate(payload_fields):
        node_id = f"event-payload:{event_id}:{index}"
        add_node(_synthetic_node(
            node_id, f"payload · {field}", kind="event_payload_field", depth=1,
            parent=event_id, role="payload_field", payload_field=field,
        ))
        edges.append(_edge(
            f"event-payload-edge:{event_id}:{index}", event_id, node_id,
            dimension="payload", relation_type="declares_payload_field", causal=False,
            evidence="behavior.events[].payload",
        ))

    mechanism_flow_ids: set[str] = set()
    operation_refs: set[str] = set()
    for topic in topics:
        topic_id = topic["id"]
        topic_node_id = f"topic-context:{topic_id}"
        add_node(_synthetic_node(
            topic_node_id, f"Topic · {topic['name']}", kind="topic_context", depth=1,
            parent=event_id, role="topic_context", topic_ref=topic_id,
        ))
        edges.append(_edge(
            f"event-topic:{topic_id}->{event_id}", topic_node_id, event_id,
            dimension="topic_context", relation_type="explicit_event_ref", causal=False,
            evidence=f"Topic {topic_id}.event_refs contains {event_id}",
        ))
        mechanism_flow_ids.update(ref for ref in topic["flow_refs"] if ref in flows)
        operation_refs.update(topic["operation_refs"])

    # Show operations explicitly co-declared with the Event Topic. They are
    # context, not Event effects, until a Flow step binds them causally.
    for operation_ref in sorted(operation_refs):
        if operation_ref not in graph_nodes:
            continue
        add_node(_real_node(graph_nodes[operation_ref], depth=2, parent=event_id, role="mechanism_operation"))
        edges.append(_edge(
            f"event-op-context:{event_id}->{operation_ref}", event_id, operation_ref,
            dimension="mechanism_context", relation_type="topic_operation_context", causal=False,
            evidence="same explicit Topic operation_refs/event_refs surface",
        ))

    # Include flows that either explicitly reference the Event or are explicitly
    # co-declared with it by the same Topic. The latter remains context-only.
    mechanism_flow_ids.update(binding["flow_id"] for binding in bindings if binding["flow_id"] in flows)
    step_node_ids: dict[tuple[str, str], str] = {}
    for flow_index, flow_id in enumerate(sorted(mechanism_flow_ids)):
        flow = flows[flow_id]
        flow_node_id = f"flow-context:{flow_id}"
        add_node(_synthetic_node(
            flow_node_id, f"Flow · {flow.get('name') or flow_id}", kind="flow_context", depth=2,
            parent=event_id, role="flow_context", flow_ref=flow_id, flow_type=flow.get("flow_type"),
        ))
        edges.append(_edge(
            f"event-flow-context:{event_id}->{flow_id}", event_id, flow_node_id,
            dimension="mechanism_context", relation_type="declared_flow_context", causal=False,
            evidence="Flow is explicitly referenced by an Event-owning Topic or explicitly references the Event",
        ))

        steps = [step for step in flow.get("steps", []) if isinstance(step, dict) and step.get("id")]
        local_step_ids = {str(step["id"]) for step in steps}
        for step_index, step in enumerate(steps):
            step_id = str(step["id"])
            node_id = f"flow-step:{flow_id}:{step_id}"
            step_node_ids[(flow_id, step_id)] = node_id
            action_ref = str(step.get("action_ref") or "")
            action_name = str(entries.get(action_ref, {}).get("name") or action_ref or step_id)
            condition = str(step.get("condition_ref") or "").strip()
            target = str(step.get("target_ref") or "").strip()
            label = f"{step_index + 1} · {action_name}"
            if target:
                label += f" → {target}"
            if condition:
                label += f" · if {condition}"
            causal_from_event = step_id in causal_start_steps
            add_node(_synthetic_node(
                node_id, label, kind="flow_step", depth=3 + step_index,
                parent=flow_node_id if step_index == 0 else None,
                role="causal_step" if causal_from_event else "flow_step_context",
                flow_ref=flow_id,
                step_ref=step_id,
                actor_ref=step.get("actor_ref"),
                action_ref=step.get("action_ref"),
                data_ref=step.get("data_ref"),
                target_ref=step.get("target_ref"),
                cause_ref=step.get("cause_ref"),
                condition_ref=step.get("condition_ref"),
                payload_ref=step.get("payload_ref"),
                result_refs=deepcopy(step.get("result_refs", [])),
                error_refs=deepcopy(step.get("error_refs", [])),
            ))
            if step_index == 0:
                edges.append(_edge(
                    f"flow-membership:{flow_id}:{step_id}", flow_node_id, node_id,
                    dimension="flow_context", relation_type="flow_contains_step", causal=False,
                    evidence="behavior.flows[].steps",
                ))
            if causal_from_event:
                edges.append(_edge(
                    f"event-cause:{event_id}->{step_id}", event_id, node_id,
                    dimension="impact", relation_type="explicit_event_cause", causal=True,
                    evidence=f"{flow_id}.{step_id}.cause_ref == {event_id}",
                ))

        for step in steps:
            source_step_id = str(step["id"])
            source_node_id = step_node_ids.get((flow_id, source_step_id))
            if not source_node_id:
                continue
            for next_ref in step.get("next_step_refs", []):
                next_ref = str(next_ref)
                if next_ref not in local_step_ids:
                    continue
                target_node_id = step_node_ids.get((flow_id, next_ref))
                if target_node_id:
                    edges.append(_edge(
                        f"flow-next:{flow_id}:{source_step_id}->{next_ref}", source_node_id, target_node_id,
                        dimension="flow", relation_type="explicit_next_step", causal=True,
                        evidence="behavior.flows[].steps[].next_step_refs",
                    ))

    if not causal_start_steps:
        gap_id = f"gap:event-causal-binding:{event_id}"
        add_node(_synthetic_node(
            gap_id,
            "GAP · no explicit Event → Flow causal binding",
            kind="semantic_gap",
            depth=2,
            parent=event_id,
            role="semantic_gap",
            gap_type="missing_event_causal_binding",
            gap_detail="No Flow step has cause_ref equal to this Event identity. Topic co-membership and generic relations are not causality.",
        ))
        edges.append(_edge(
            f"event-gap:{event_id}", event_id, gap_id,
            dimension="gap", relation_type="missing_explicit_causal_binding", causal=False,
            evidence="No behavior.flows[].steps[].cause_ref equals selected Event identity",
        ))

    # If exact non-causal Event references exist, expose them as evidence nodes.
    for index, binding in enumerate(binding for binding in bindings if not binding["causal"]):
        binding_id = f"event-binding:{event_id}:{index}"
        step_part = f" · {binding['step_id']}" if binding.get("step_id") else ""
        add_node(_synthetic_node(
            binding_id,
            f"explicit ref · {binding['field']} · {binding['flow_id']}{step_part}",
            kind="event_reference_evidence", depth=2, parent=event_id,
            role="reference_evidence", **binding,
        ))
        edges.append(_edge(
            f"event-binding-edge:{event_id}:{index}", event_id, binding_id,
            dimension="evidence", relation_type="explicit_noncausal_event_reference", causal=False,
            evidence=f"Exact Event identity appears in Flow field {binding['field']}",
        ))

    projected = {
        "nodes": nodes,
        "edges": edges,
        "projection_root": event_id,
        "projection_root_name": str(event_entry.get("name") or event_id),
        "projection_base_ids": [event_id],
        "projection_relation_depth": max_depth,
        "projection_external_references": [],
        "projection_semantic_kind": "event_impact",
        "event_impact": {
            "event_id": event_id,
            "owner_ref": owner_ref,
            "payload_fields": payload_fields,
            "topic_refs": [topic["id"] for topic in topics],
            "mechanism_flow_refs": sorted(mechanism_flow_ids),
            "explicit_bindings": bindings,
            "causal_start_step_refs": sorted(causal_start_steps),
            "causal_binding_present": bool(causal_start_steps),
            "gap_count": 0 if causal_start_steps else 1,
        },
    }
    metadata = {
        "projection_style": "impact",
        "scope_type": "event",
        "scope_ref": event_id,
        "semantic_kind": "event_impact",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "wave_count": len(trace.get("waves", [])),
        "trace": trace,
        "causality": trace.get("causal_source"),
        "causal_binding_present": bool(causal_start_steps),
        "gap_count": 0 if causal_start_steps else 1,
        "topic_context_is_causal": False,
        "generic_relations_extend_causality": False,
        "inference": False,
    }
    return projected, metadata, depth_by_ref


__all__ = ["build_event_projection"]
