from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from typing import Any


INDEX_VERSION = "1.0"


def _entries(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("id")): entry
        for entry in tree.get("entries", [])
        if isinstance(entry, dict) and entry.get("id") is not None
    }


def _topics(tree: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        topic for topic in tree.get("topics", [])
        if isinstance(topic, dict) and topic.get("id")
    ]


def _flow_surface_ids(tree: dict[str, Any], flow_ids: set[str], entry_ids: set[str]) -> set[str]:
    by_flow = {
        str(flow.get("id")): flow
        for flow in tree.get("flows", [])
        if isinstance(flow, dict) and flow.get("id")
    }
    out: set[str] = set()
    queue = deque(sorted(flow_ids))
    seen: set[str] = set()
    while queue:
        flow_id = queue.popleft()
        if flow_id in seen:
            continue
        seen.add(flow_id)
        flow = by_flow.get(flow_id)
        if flow is None:
            continue
        owner_ref = flow.get("owner_ref")
        if isinstance(owner_ref, str) and owner_ref in entry_ids:
            out.add(owner_ref)
        for step in flow.get("steps", []):
            if not isinstance(step, dict):
                continue
            for field in ("actor_ref", "action_ref", "data_ref", "target_ref", "cause_ref", "condition_ref", "payload_ref"):
                ref = step.get(field)
                if isinstance(ref, str) and ref in entry_ids:
                    out.add(ref)
            for field in ("result_refs", "error_refs"):
                for ref in step.get(field, []):
                    if isinstance(ref, str) and ref in entry_ids:
                        out.add(ref)
            for ref in step.get("subflow_refs", []):
                if isinstance(ref, str):
                    queue.append(ref)
    return out


def _direct_topic_surface(tree: dict[str, Any], topic: dict[str, Any], entry_ids: set[str]) -> set[str]:
    out: set[str] = set()
    flow_ids: set[str] = set()
    relation_ids: set[str] = set()

    for field in ("member_refs", "operation_refs", "event_refs", "resolved_grouping_member_refs"):
        out.update(str(ref) for ref in topic.get(field, []) if str(ref) in entry_ids)

    composed = topic.get("composed_trace_surface") if isinstance(topic.get("composed_trace_surface"), dict) else {}
    for field in ("member_refs", "operation_refs", "event_refs"):
        out.update(str(ref) for ref in composed.get(field, []) if str(ref) in entry_ids)

    flow_ids.update(str(ref) for ref in topic.get("flow_refs", []) if isinstance(ref, str))
    flow_ids.update(str(ref) for ref in composed.get("flow_refs", []) if isinstance(ref, str))
    relation_ids.update(str(ref) for ref in topic.get("relation_refs", []) if isinstance(ref, str))
    relation_ids.update(str(ref) for ref in composed.get("relation_refs", []) if isinstance(ref, str))

    out.update(_flow_surface_ids(tree, flow_ids, entry_ids))
    for link in tree.get("links", []):
        if not isinstance(link, dict) or str(link.get("id") or "") not in relation_ids:
            continue
        for field in ("source_id", "target_id"):
            ref = link.get(field)
            if isinstance(ref, str) and ref in entry_ids:
                out.add(ref)
    return out


def _identifier_label(topic_id: str) -> str:
    # Presentation only. The identity itself comes directly from the source.
    value = topic_id[6:] if topic_id.startswith("TOPIC_") else topic_id
    return value.replace("_", " ") or topic_id


def build_topic_index(tree: dict[str, Any]) -> dict[str, Any]:
    """Resolve a reusable Topic projection index into StructureTree.

    A Topic becomes a heading when the source explicitly uses that Topic
    identity as another Topic's parent/container, or when it is an explicit
    root Topic. Referenced-but-undefined parent Topic identities are preserved
    as unresolved headings instead of being guessed or discarded.

    No directory names, software names, known AIGMos modules, display-name
    matching, thresholds or hand-authored topic lists participate in this
    resolution.
    """
    topics = _topics(tree)
    entries = _entries(tree)
    entry_ids = set(entries)

    definitions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for topic in topics:
        definitions[str(topic["id"])].append(topic)
    defined_ids = set(definitions)

    # child -> explicit parent relations. container/child_topics remain distinct
    # from parent_topic_refs because Topic inheritance is not containment.
    parents_by_topic: dict[str, set[str]] = defaultdict(set)
    edge_kinds: dict[tuple[str, str], set[str]] = defaultdict(set)

    for topic in topics:
        topic_id = str(topic["id"])
        for ref in topic.get("parent_topic_refs", []):
            if not isinstance(ref, str) or not ref:
                continue
            parents_by_topic[topic_id].add(ref)
            edge_kinds[(ref, topic_id)].add("parent_topic_ref")
        container = topic.get("container_topic_ref")
        if isinstance(container, str) and container:
            parents_by_topic[topic_id].add(container)
            edge_kinds[(container, topic_id)].add("container_topic_ref")
        for child_ref in topic.get("child_topic_refs", []):
            if not isinstance(child_ref, str) or not child_ref:
                continue
            parents_by_topic[child_ref].add(topic_id)
            edge_kinds[(topic_id, child_ref)].add("child_topic_ref")

    explicit_parent_targets = {parent for parents in parents_by_topic.values() for parent in parents}
    explicit_roots = {
        topic_id for topic_id in defined_ids
        if not parents_by_topic.get(topic_id)
    }
    heading_ids = explicit_parent_targets | explicit_roots

    children_by_heading: dict[str, set[str]] = defaultdict(set)
    for child_id, parent_ids in parents_by_topic.items():
        for parent_id in parent_ids:
            children_by_heading[parent_id].add(child_id)

    def descendants(topic_id: str) -> set[str]:
        seen: set[str] = set()
        queue = deque([topic_id])
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            queue.extend(sorted(children_by_heading.get(current, set())))
        return seen

    direct_surfaces: dict[str, set[str]] = {}
    for topic_id, records in definitions.items():
        surface: set[str] = set()
        for record in records:
            surface.update(_direct_topic_surface(tree, record, entry_ids))
        direct_surfaces[topic_id] = surface

    topic_records: dict[str, dict[str, Any]] = {}
    for topic_id in sorted(defined_ids):
        related_topic_ids = descendants(topic_id)
        projection_base_ids: set[str] = set()
        for related_id in related_topic_ids:
            projection_base_ids.update(direct_surfaces.get(related_id, set()))
        first = definitions[topic_id][0]
        topic_records[topic_id] = {
            "id": topic_id,
            "label": str(first.get("name") or topic_id),
            "defined": True,
            "definition_count": len(definitions[topic_id]),
            "heading": topic_id in heading_ids,
            "explicit_parent_refs": sorted(parents_by_topic.get(topic_id, set())),
            "direct_topic_refs": sorted(children_by_heading.get(topic_id, set())),
            "resolved_topic_refs": sorted(related_topic_ids),
            "projection_base_ids": sorted(projection_base_ids),
            "entry_count": len(projection_base_ids),
            "semantic_authority": False,
            "derived_projection_index": True,
        }

    heading_records: list[dict[str, Any]] = []
    for heading_id in sorted(heading_ids):
        related_topic_ids = descendants(heading_id)
        projection_base_ids: set[str] = set()
        for related_id in related_topic_ids:
            projection_base_ids.update(direct_surfaces.get(related_id, set()))

        records = definitions.get(heading_id, [])
        defined = bool(records)
        first = records[0] if records else {}
        parent_heading_refs = sorted(
            ref for ref in parents_by_topic.get(heading_id, set())
            if ref in heading_ids
        )
        heading_records.append({
            "id": heading_id,
            "label": str(first.get("name") or _identifier_label(heading_id)),
            "defined": defined,
            "unresolved": not defined,
            "definition_count": len(records),
            "parent_heading_refs": parent_heading_refs,
            "direct_topic_refs": sorted(children_by_heading.get(heading_id, set())),
            "resolved_topic_refs": sorted(related_topic_ids),
            "projection_base_ids": sorted(projection_base_ids),
            "entry_count": len(projection_base_ids),
            "semantic_authority": False,
            "derived_projection_index": True,
            "evidence": "explicit Topic parent/container/root topology",
        })

    heading_edges: list[dict[str, Any]] = []
    for (parent_id, child_id), kinds in sorted(edge_kinds.items()):
        if parent_id not in heading_ids or child_id not in heading_ids:
            continue
        for kind in sorted(kinds):
            heading_edges.append({
                "id": f"topic-index:{kind}:{parent_id}->{child_id}",
                "source": parent_id,
                "target": child_id,
                "dimension": "topic_container" if kind in {"container_topic_ref", "child_topic_ref"} else "topic_parent",
                "type": kind,
                "inference": False,
            })

    heading_parent_ids: set[str] = set()
    for edge in heading_edges:
        heading_parent_ids.add(str(edge["target"]))
    root_heading_refs = sorted(heading_ids - heading_parent_ids)

    topic_to_heading_refs: dict[str, list[str]] = {}
    for topic_id in sorted(defined_ids):
        if topic_id in heading_ids:
            topic_to_heading_refs[topic_id] = [topic_id]
        else:
            topic_to_heading_refs[topic_id] = sorted(
                ref for ref in parents_by_topic.get(topic_id, set())
                if ref in heading_ids
            )

    index = {
        "version": INDEX_VERSION,
        "heading_rule": "explicit Topic parent/container target or explicit root Topic",
        "heading_count": len(heading_records),
        "defined_heading_count": sum(1 for item in heading_records if item["defined"]),
        "unresolved_heading_count": sum(1 for item in heading_records if item["unresolved"]),
        "root_heading_refs": root_heading_refs,
        "headings": heading_records,
        "heading_edges": heading_edges,
        "topics": topic_records,
        "topic_to_heading_refs": topic_to_heading_refs,
        "rules": {
            "resolved_at": "StructureTree import",
            "paths_are_semantic": False,
            "display_names_create_grouping": False,
            "hardcoded_topic_names": False,
            "parent_topic_refs_preserve_inheritance_semantics": True,
            "container_topic_refs_preserve_container_semantics": True,
            "unresolved_explicit_topic_refs_are_preserved_as_gaps": True,
            "projection_reanalysis_required": False,
            "inference": False,
        },
    }
    tree["topic_index"] = index

    # Cache each resolved Topic surface on the Topic record too. Projection
    # engines can therefore consume the normalized StructureTree directly.
    for topic in topics:
        topic_id = str(topic["id"])
        cached = topic_records.get(topic_id)
        if cached:
            topic["projection_heading_refs"] = deepcopy(topic_to_heading_refs.get(topic_id, []))
            topic["projection_topic_refs"] = deepcopy(cached["resolved_topic_refs"])
            topic["projection_base_ids"] = deepcopy(cached["projection_base_ids"])

    return index


def topic_heading_catalog(tree: dict[str, Any]) -> list[dict[str, Any]]:
    index = tree.get("topic_index") if isinstance(tree.get("topic_index"), dict) else {}
    return [deepcopy(item) for item in index.get("headings", []) if isinstance(item, dict)]


def _heading_depths(index: dict[str, Any]) -> dict[str, int]:
    headings = {str(item.get("id")) for item in index.get("headings", []) if isinstance(item, dict) and item.get("id")}
    children: dict[str, list[str]] = defaultdict(list)
    incoming: set[str] = set()
    for edge in index.get("heading_edges", []):
        if not isinstance(edge, dict):
            continue
        source, target = str(edge.get("source") or ""), str(edge.get("target") or "")
        if source in headings and target in headings:
            children[source].append(target)
            incoming.add(target)
    roots = [str(ref) for ref in index.get("root_heading_refs", []) if str(ref) in headings]
    if not roots:
        roots = sorted(headings - incoming)
    depth: dict[str, int] = {root: 0 for root in roots}
    queue = deque(sorted(roots))
    while queue:
        current = queue.popleft()
        for child in sorted(children.get(current, [])):
            candidate = depth[current] + 1
            if child not in depth or candidate < depth[child]:
                depth[child] = candidate
                queue.append(child)
    fallback = max(depth.values(), default=-1) + 1
    for heading_id in sorted(headings):
        depth.setdefault(heading_id, fallback)
    return depth


def topic_all_graph(tree: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    index = tree.get("topic_index") if isinstance(tree.get("topic_index"), dict) else {}
    headings = topic_heading_catalog(tree)
    depths = _heading_depths(index)
    nodes: list[dict[str, Any]] = []
    for heading in headings:
        heading_id = str(heading["id"])
        depth = depths.get(heading_id, 0)
        nodes.append({
            "id": heading_id,
            "name": heading.get("label") or heading_id,
            "kind": "topic_heading_gap" if heading.get("unresolved") else "topic_heading",
            "type": "topic_heading",
            "projection_depth": depth,
            "projection_generation": depth + 1,
            "hierarchy_depth": depth,
            "projection_parent_id": (heading.get("parent_heading_refs") or [None])[0],
            "topic_count": len(heading.get("resolved_topic_refs", [])),
            "entry_count": heading.get("entry_count", 0),
            "unresolved": bool(heading.get("unresolved")),
            "defined": bool(heading.get("defined")),
        })
    graph = {
        "nodes": nodes,
        "edges": deepcopy(index.get("heading_edges", [])),
        "projection_root": "all",
        "projection_root_name": "All Topic headings",
        "projection_base_ids": [str(item["id"]) for item in headings],
        "projection_relation_depth": 0,
        "projection_external_references": [],
        "projection_semantic_kind": "topic_heading_index",
    }
    metadata = {
        "projection_style": "topic",
        "scope_type": "all",
        "scope_ref": "all",
        "semantic_kind": "topic_heading_index",
        "heading_count": len(nodes),
        "unresolved_heading_count": index.get("unresolved_heading_count", 0),
        "resolved_at": "StructureTree import",
        "source": "tree.topic_index",
        "inference": False,
    }
    return graph, metadata, depths


def topic_scope_graph(
    tree: dict[str, Any],
    graph: dict[str, Any],
    topic_id: str,
    *,
    relation_depth: int = 0,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    """Project a cached Topic heading/detail surface plus explicit graph edges."""
    index = tree.get("topic_index") if isinstance(tree.get("topic_index"), dict) else {}
    headings = {str(item.get("id")): item for item in index.get("headings", []) if isinstance(item, dict) and item.get("id")}
    topic_records = index.get("topics") if isinstance(index.get("topics"), dict) else {}
    record = headings.get(topic_id) or topic_records.get(topic_id)
    if not isinstance(record, dict):
        raise KeyError(f"Unknown normalized Topic heading: {topic_id}")

    nodes_by_id = {
        str(node.get("id")): node
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("id") is not None
    }
    base_ids = {str(ref) for ref in record.get("projection_base_ids", []) if str(ref) in nodes_by_id}
    relation_depth = max(0, min(32, int(relation_depth)))

    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source, target = str(edge.get("source") or ""), str(edge.get("target") or "")
        if source in nodes_by_id and target in nodes_by_id:
            adjacency[source].append(target)
            adjacency[target].append(source)

    depth_by_ref: dict[str, int] = {ref: 0 for ref in sorted(base_ids)}
    parent_by_ref: dict[str, str | None] = {ref: None for ref in sorted(base_ids)}
    queue = deque(sorted(base_ids))
    while queue:
        current = queue.popleft()
        current_depth = depth_by_ref[current]
        if current_depth >= relation_depth:
            continue
        for neighbor in sorted(adjacency.get(current, [])):
            if neighbor in depth_by_ref:
                continue
            depth_by_ref[neighbor] = current_depth + 1
            parent_by_ref[neighbor] = current
            queue.append(neighbor)

    included = set(depth_by_ref)
    nodes: list[dict[str, Any]] = []
    for node_id in sorted(included):
        raw = deepcopy(nodes_by_id[node_id])
        depth = depth_by_ref[node_id]
        raw["projection_depth"] = depth
        raw["projection_generation"] = depth + 1
        raw["projection_parent_id"] = parent_by_ref.get(node_id)
        raw["hierarchy_depth"] = depth
        nodes.append(raw)

    edges = [
        deepcopy(edge) for edge in graph.get("edges", [])
        if isinstance(edge, dict)
        and str(edge.get("source") or "") in included
        and str(edge.get("target") or "") in included
    ]
    projected = {
        "nodes": nodes,
        "edges": edges,
        "projection_root": topic_id,
        "projection_root_name": str(record.get("label") or topic_id),
        "projection_base_ids": sorted(base_ids),
        "projection_relation_depth": relation_depth,
        "projection_external_references": [],
        "projection_semantic_kind": "topic_cached_surface",
    }
    metadata = {
        "projection_style": "topic",
        "scope_type": "topic",
        "scope_ref": topic_id,
        "semantic_kind": "topic_cached_surface",
        "base_node_count": len(base_ids),
        "node_count": len(nodes),
        "relation_depth": relation_depth,
        "topic_resolution_source": "tree.topic_index",
        "topic_resolution_recomputed": False,
        "inference": False,
    }
    return projected, metadata, depth_by_ref


__all__ = [
    "build_topic_index",
    "topic_heading_catalog",
    "topic_all_graph",
    "topic_scope_graph",
]
