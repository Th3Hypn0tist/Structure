from __future__ import annotations

from copy import deepcopy
from typing import Any

from event_trace import build_event_impact


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
    "dependency": {"label": "Dependency", "class": "structural", "question": "What does this require and what explicitly depends on it?", "scope_types": ["identity", "topic"], "implemented": False},
    "authority": {"label": "Authority", "class": "structural", "question": "Which explicit authority paths reach this scope?", "scope_types": ["identity", "topic"], "implemented": False},
    "ownership": {"label": "Ownership", "class": "structural", "question": "Who or what explicitly owns the selected structure?", "scope_types": ["identity", "topic"], "implemented": False},
    "containment": {"label": "Containment", "class": "structural", "question": "What explicitly contains what?", "scope_types": ["identity", "topic"], "implemented": False},
    "relation": {"label": "Relation", "class": "structural", "question": "Which explicit typed relations connect the selected identities?", "scope_types": ["identity", "topic"], "implemented": False},
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


def projection_style_catalog() -> list[dict[str, Any]]:
    return [
        {"id": style_id, **deepcopy(spec)}
        for style_id, spec in PROJECTION_STYLES.items()
    ]


def _entry_index(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("id")): entry
        for entry in tree.get("entries", [])
        if isinstance(entry, dict) and entry.get("id") is not None
    }


def impact_graph(tree: dict[str, Any], graph: dict[str, Any], event_id: str, *, max_depth: int = 32) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a projection graph from explicit Event causality only.

    The semantic graph is intentionally distinct from a Topic/containment graph.
    Visible identities are arranged by causal wave. Generic graph relations are
    not used to extend the impact surface.
    """
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


__all__ = ["PROJECTION_STYLES", "projection_style_catalog", "impact_graph"]
