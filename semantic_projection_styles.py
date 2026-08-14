from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

from event_trace import build_event_impact
from projection_instances import projection_base_ids, topic_catalog


PROJECTION_STYLES: dict[str, dict[str, Any]] = {
    "topic": {
        "label": "Topic",
        "class": "structural",
        "question": "What belongs to this semantic comparison surface?",
        "scope_types": ["topic", "all"],
        "implemented": True,
    },
    "impact": {
        "label": "Impact",
        "class": "behavioral",
        "question": "What does this entry affect, under which explicit conditions, and in what causal order?",
        "scope_types": ["event"],
        "implemented": True,
    },
    "dependency": {
        "label": "Dependency",
        "class": "structural",
        "question": "What does this require and what explicitly depends on it?",
        "scope_types": ["identity", "topic"],
        "implemented": True,
        "edge_dimension": "dependencies",
    },
    "authority": {
        "label": "Authority",
        "class": "structural",
        "question": "Which explicit authority paths reach this scope?",
        "scope_types": ["identity", "topic"],
        "implemented": True,
        "edge_dimension": "authority",
    },
    "ownership": {
        "label": "Ownership",
        "class": "structural",
        "question": "Who or what explicitly owns the selected structure?",
        "scope_types": ["identity", "topic"],
        "implemented": True,
        "edge_dimension": "ownership",
    },
    "containment": {
        "label": "Containment",
        "class": "structural",
        "question": "What explicitly contains what?",
        "scope_types": ["identity", "topic"],
        "implemented": True,
        "edge_dimension": "containment",
    },
    "relation": {
        "label": "Relation",
        "class": "structural",
        "question": "Which explicit typed relations connect the selected identities?",
        "scope_types": ["identity", "topic"],
        "implemented": True,
        "edge_dimension": "relations",
    },
    "flow": {"label": "Flow", "class": "behavioral", "question": "How does an explicit Flow execute?", "scope_types": ["flow"], "implemented": False},
    "state": {"label": "State", "class": "behavioral", "question": "Which explicit states and transitions exist?", "scope_types": ["identity", "topic"], "implemented": False},
    "interface": {"label": "Interface", "class": "structural", "question": "Which interfaces are exposed and how do they bind?", "scope_types": ["identity", "topic"], "implemented": False},
    "contract_coverage": {"label": "Contract Coverage", "class": "comparison", "question": "Which requirements of one source are covered by another source?", "scope_types": ["source", "topic"], "implemented": False},
    "conformance": {"label": "Conformance", "class": "comparison", "question": "Does observed behavior conform to expected behavior?", "scope_types": ["source", "event", "flow"], "implemented": False},
    "gap": {"label": "Gap", "class": "comparison", "question": "What is missing, unresolved or contradictory between sources?", "scope_types": ["source", "topic"], "implemented": False},
    "traceability": {"label": "Traceability", "class": "comparison", "question": "How does an identity trace across requirement, structure and evidence?", "scope_types": ["identity"], "implemented": False},
    "boundary": {"label": "Boundary", "class": "structural", "question": "What is explicitly inside and outside the selected boundary?", "scope_types": ["identity", "topic"], "implemented": False},
    "change_impact": {"label": "Change Impact", "class": "comparison", "question": "What explicitly connected structure is exposed by a change?", "scope_types": ["identity", "topic"], "implemented": False},
}


STRUCTURAL_DIMENSION_STYLES = {
    style_id: str(spec["edge_dimension"])
    for style_id, spec in PROJECTION_STYLES.items()
    if spec.get("implemented") and spec.get("edge_dimension")
}


def projection_style_catalog(*, include_unimplemented: bool = False) -> list[dict[str, Any]]:
    """Return selectable semantic projection styles.

    The interactive catalog exposes only working styles. Planned styles stay in
    PROJECTION_STYLES for the contract/roadmap, but are not rendered as dead UI
    controls that can only fail at runtime.
    """
    return [
        {"id": style_id, **deepcopy(spec)}
        for style_id, spec in PROJECTION_STYLES.items()
        if include_unimplemented or spec.get("implemented")
    ]


def _entry_index(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("id")): entry
        for entry in tree.get("entries", [])
        if isinstance(entry, dict) and entry.get("id") is not None
    }


def _node_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("id")): node
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("id") is not None
    }


def _scope_base_ids(tree: dict[str, Any], graph: dict[str, Any], scope_type: str, scope_ref: str) -> tuple[set[str], str]:
    nodes = _node_index(graph)
    if scope_type == "identity":
        if scope_ref not in nodes:
            raise KeyError(f"Unknown projection identity: {scope_ref}")
        return {scope_ref}, str(nodes[scope_ref].get("name") or scope_ref)
    if scope_type == "topic":
        base_ids = projection_base_ids(tree, scope_ref)
        topic = next((item for item in topic_catalog(tree) if str(item.get("id")) == scope_ref), None)
        return {ref for ref in base_ids if ref in nodes}, str((topic or {}).get("label") or scope_ref)
    raise ValueError(f"Unsupported structural projection scope type: {scope_type}")


def structural_dimension_graph(
    tree: dict[str, Any],
    graph: dict[str, Any],
    *,
    projection_style: str,
    scope_type: str,
    scope_ref: str,
    max_depth: int = 0,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    """Project one explicit structural dimension without semantic inference.

    Traversal is deliberately bidirectional so the selected surface can show
    both incoming and outgoing explicit edges. Edge direction is preserved in
    the returned graph, so dependency/authority/ownership semantics are not
    reversed or collapsed. No other structural dimension is allowed to extend
    the traversal.
    """
    edge_dimension = STRUCTURAL_DIMENSION_STYLES.get(projection_style)
    if edge_dimension is None:
        raise ValueError(f"Projection style is not an implemented structural dimension: {projection_style}")

    max_depth = max(0, min(32, int(max_depth)))
    nodes_by_id = _node_index(graph)
    base_ids, root_name = _scope_base_ids(tree, graph, scope_type, scope_ref)

    selected_edges: list[dict[str, Any]] = []
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for raw in graph.get("edges", []):
        if not isinstance(raw, dict):
            continue
        dimension = str(raw.get("dimension") or "")
        if dimension != edge_dimension:
            continue
        source = str(raw.get("source") or "")
        target = str(raw.get("target") or "")
        if not source or not target or source not in nodes_by_id or target not in nodes_by_id:
            continue
        edge = deepcopy(raw)
        selected_edges.append(edge)
        adjacency.setdefault(source, []).append((target, edge))
        adjacency.setdefault(target, []).append((source, edge))

    depth_by_ref: dict[str, int] = {ref: 0 for ref in sorted(base_ids)}
    parent_by_ref: dict[str, str | None] = {ref: None for ref in sorted(base_ids)}
    queue = deque(sorted(base_ids))
    while queue:
        current = queue.popleft()
        current_depth = depth_by_ref[current]
        if current_depth >= max_depth:
            continue
        for neighbor, _edge in adjacency.get(current, []):
            if neighbor in depth_by_ref:
                continue
            depth_by_ref[neighbor] = current_depth + 1
            parent_by_ref[neighbor] = current
            queue.append(neighbor)

    included = set(depth_by_ref)
    nodes: list[dict[str, Any]] = []
    for node_id in sorted(included):
        raw = nodes_by_id.get(node_id)
        if raw is None:
            continue
        node = deepcopy(raw)
        depth = depth_by_ref[node_id]
        node["hierarchy_depth"] = depth
        node["projection_depth"] = depth
        node["projection_generation"] = depth + 1
        node["projection_parent_id"] = parent_by_ref.get(node_id)
        node["projection_dimension_semantic"] = edge_dimension
        nodes.append(node)

    edges = [
        edge for edge in selected_edges
        if str(edge.get("source") or "") in included and str(edge.get("target") or "") in included
    ]

    projected = {
        "nodes": nodes,
        "edges": edges,
        "projection_root": scope_ref,
        "projection_root_name": root_name,
        "projection_base_ids": sorted(base_ids),
        "projection_relation_depth": max_depth,
        "projection_external_references": [],
    }
    metadata = {
        "projection_style": projection_style,
        "scope_type": scope_type,
        "scope_ref": scope_ref,
        "edge_dimension": edge_dimension,
        "relation_depth": max_depth,
        "base_node_count": len(base_ids),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "traversal": "bidirectional",
        "edge_direction_preserved": True,
        "other_dimensions_extend_surface": False,
        "inference": False,
    }
    return projected, metadata, depth_by_ref


def impact_graph(tree: dict[str, Any], graph: dict[str, Any], event_id: str, *, max_depth: int = 32) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a projection graph from explicit Event causality only."""
    event_id = str(event_id or "").strip()
    entries = _entry_index(tree)
    if event_id not in entries:
        raise KeyError(f"Unknown Impact entry Event: {event_id}")

    trace = build_event_impact(tree, event_id, max_depth=max_depth)
    waves = trace.get("waves", [])
    depth_by_ref: dict[str, int] = {event_id: 0}
    parent_by_ref: dict[str, str | None] = {event_id: None}
    previous_anchor = event_id

    for wave_index, wave in enumerate(waves, start=1):
        refs = [str(ref) for ref in wave.get("refs", []) if str(ref) in entries]
        for ref in refs:
            if ref not in depth_by_ref:
                depth_by_ref[ref] = wave_index
                parent_by_ref[ref] = previous_anchor
        if refs:
            previous_anchor = refs[0]

    included = set(depth_by_ref)
    nodes: list[dict[str, Any]] = []
    for raw in graph.get("nodes", []):
        node_id = str(raw.get("id") or "")
        if node_id not in included:
            continue
        node = deepcopy(raw)
        node["hierarchy_depth"] = depth_by_ref[node_id]
        node["projection_depth"] = depth_by_ref[node_id]
        node["projection_generation"] = depth_by_ref[node_id] + 1
        node["projection_parent_id"] = parent_by_ref.get(node_id)
        node["impact_wave"] = depth_by_ref[node_id]
        nodes.append(node)

    edges: list[dict[str, Any]] = []
    for node_id, parent_id in parent_by_ref.items():
        if parent_id is None or node_id == event_id:
            continue
        edges.append({
            "id": f"impact:{parent_id}->{node_id}",
            "source": parent_id,
            "target": node_id,
            "dimension": "impact",
            "relation_type": "explicit_causal_wave",
            "semantic_authority": False,
            "evidence": "Event cause_ref + explicit Flow continuation",
        })

    projected = {
        "nodes": nodes,
        "edges": edges,
        "projection_root": event_id,
        "projection_root_name": str(entries[event_id].get("name") or event_id),
        "projection_base_ids": [event_id],
        "projection_relation_depth": max_depth,
        "projection_external_references": [],
    }
    metadata = {
        "projection_style": "impact",
        "scope_type": "event",
        "scope_ref": event_id,
        "node_count": len(nodes),
        "wave_count": len(waves),
        "trace": trace,
        "causality": trace.get("causal_source"),
        "generic_relations_extend_causality": False,
        "inference": False,
    }
    return projected, metadata


__all__ = [
    "PROJECTION_STYLES",
    "STRUCTURAL_DIMENSION_STYLES",
    "projection_style_catalog",
    "structural_dimension_graph",
    "impact_graph",
]
