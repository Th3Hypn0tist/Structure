from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any


PROJECTIONS: dict[str, dict[str, str]] = {
    "atlas_3d": {"title": "Architecture Atlas 3D", "dimension": "3d", "kind": "atlas3d"},
    "relation_web_3d": {"title": "Relation Web 3D", "dimension": "3d", "kind": "web3d"},
    "adjacency_matrix_3d": {"title": "Adjacency Matrix 3D", "dimension": "3d", "kind": "matrix3d"},
    "lifecycle_lanes_3d": {"title": "Lifecycle Lanes 3D", "dimension": "3d", "kind": "lanes3d"},
    "dependency_flow_3d": {"title": "Dependency Flow 3D", "dimension": "3d", "kind": "flow3d"},
}


def _stable_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(graph.get("nodes", []), key=lambda n: str(n.get("id", "")))


def _stable_edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        graph.get("edges", []),
        key=lambda e: (
            str(e.get("dimension", "")),
            str(e.get("source", "")),
            str(e.get("target", "")),
            str(e.get("id", "")),
        ),
    )


def _public(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "name": node.get("name") or node.get("id"),
        "type": node.get("type"),
        "status": node.get("status"),
        "source_role": node.get("source_role") or (node.get("raw") or {}).get("source_role"),
        "source": node.get("source"),
        "kind": node.get("kind"),
        "hierarchy_depth": node.get("hierarchy_depth"),
        "projection_depth": node.get("projection_depth"),
        "projection_generation": node.get("projection_generation"),
        "projection_parent_id": node.get("projection_parent_id"),
        "relation_depth": node.get("relation_depth"),
    }


def _degree(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    out = {str(n["id"]): 0 for n in nodes}
    for edge in edges:
        a = str(edge.get("source", ""))
        b = str(edge.get("target", ""))
        if a in out:
            out[a] += 1
        if b in out:
            out[b] += 1
    return out


def _hierarchy_depths(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int | None]:
    ids = {str(node.get("id")) for node in nodes if node.get("id") is not None}
    candidates: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for edge in edges:
        dimension = str(edge.get("dimension") or "")
        if dimension not in {"tree", "containment"}:
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in ids or target not in ids:
            continue
        candidates[target].append((0 if dimension == "tree" else 1, source))

    parents: dict[str, str | None] = {}
    ambiguous: set[str] = set()
    for target, values in candidates.items():
        best_priority = min(priority for priority, _source in values)
        best_sources = sorted({source for priority, source in values if priority == best_priority})
        if len(best_sources) == 1:
            parents[target] = best_sources[0]
        else:
            parents[target] = None
            ambiguous.add(target)

    memo: dict[str, int | None] = {}

    def resolve(node_id: str, stack: set[str]) -> int | None:
        if node_id in memo:
            return memo[node_id]
        if node_id in stack or node_id in ambiguous:
            memo[node_id] = None
            return None
        parent = parents.get(node_id)
        if parent is None:
            memo[node_id] = 0
            return 0
        if parent not in ids:
            memo[node_id] = None
            return None
        parent_depth = resolve(parent, stack | {node_id})
        memo[node_id] = None if parent_depth is None else parent_depth + 1
        return memo[node_id]

    for node_id in sorted(ids):
        resolve(node_id, set())
    return memo


def _dependency_depths(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    ids = [str(n["id"]) for n in nodes]
    incoming = {nid: 0 for nid in ids}
    outgoing: dict[str, list[str]] = {nid: [] for nid in ids}
    for edge in edges:
        if edge.get("dimension") != "dependencies":
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in outgoing and target in incoming:
            outgoing[source].append(target)
            incoming[target] += 1
    queue = deque(sorted(nid for nid, count in incoming.items() if count == 0))
    depth = {nid: 0 for nid in ids}
    seen = 0
    while queue:
        current = queue.popleft()
        seen += 1
        for target in sorted(outgoing[current]):
            depth[target] = max(depth[target], depth[current] + 1)
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    if seen < len(ids):
        cycle_depth = max(depth.values(), default=0) + 1
        for nid, count in incoming.items():
            if count > 0:
                depth[nid] = cycle_depth
    return depth


def _atlas_3d(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    hierarchy = _hierarchy_depths(nodes, edges)
    node_by_id = {str(node.get("id")): node for node in nodes}
    ids = set(node_by_id)
    depth_by_id: dict[str, int | None] = {}
    parent_by_id: dict[str, str | None] = {}
    for node_id, node in node_by_id.items():
        explicit_depth = node.get("projection_depth")
        depth_by_id[node_id] = explicit_depth if isinstance(explicit_depth, int) and explicit_depth >= 0 else hierarchy.get(node_id)
        raw_parent = node.get("projection_parent_id")
        parent_by_id[node_id] = str(raw_parent) if raw_parent is not None and str(raw_parent) in ids else None

    children: dict[str, list[str]] = defaultdict(list)
    roots: list[str] = []
    unresolved: list[str] = []
    for node_id in sorted(ids):
        if depth_by_id[node_id] is None:
            unresolved.append(node_id)
            continue
        parent_id = parent_by_id[node_id]
        if parent_id is None or depth_by_id.get(parent_id) is None:
            roots.append(node_id)
        else:
            children[parent_id].append(node_id)
    for values in children.values():
        values.sort()

    depth_gap = 300.0
    sibling_gap = 210.0
    root_gap = 900.0
    positions: dict[str, tuple[float, float, float]] = {}
    for root_index, root_id in enumerate(sorted(roots)):
        root_x = (root_index - (len(roots) - 1) / 2.0) * root_gap
        root_depth = depth_by_id[root_id] or 0
        positions[root_id] = (root_x, -root_depth * depth_gap, 0.0)
        queue = deque([root_id])
        while queue:
            parent_id = queue.popleft()
            px, _py, pz = positions[parent_id]
            child_ids = children.get(parent_id, [])
            count = len(child_ids)
            if not count:
                continue
            cols = max(1, math.ceil(math.sqrt(count)))
            rows = max(1, math.ceil(count / cols))
            for index, child_id in enumerate(child_ids):
                row, col = divmod(index, cols)
                x = px + (col - (cols - 1) / 2.0) * sibling_gap
                z = pz + (row - (rows - 1) / 2.0) * sibling_gap
                depth = depth_by_id[child_id]
                y = -(depth if isinstance(depth, int) else 0) * depth_gap
                positions[child_id] = (x, y, z)
                queue.append(child_id)

    missing = [node_id for node_id in sorted(ids) if depth_by_id[node_id] is not None and node_id not in positions]
    for index, node_id in enumerate(missing):
        depth = depth_by_id[node_id] or 0
        positions[node_id] = (1200.0 + index * sibling_gap, -depth * depth_gap, 0.0)

    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    by_depth: dict[int, list[str]] = defaultdict(list)
    for node_id, depth in depth_by_id.items():
        if isinstance(depth, int):
            by_depth[depth].append(node_id)
    for depth in sorted(by_depth):
        members = sorted(by_depth[depth])
        groups.append({"id": f"projection-depth-{depth}", "title": f"projection depth {depth}", "x": 0.0, "y": -depth * depth_gap, "z": 0.0, "count": len(members)})
        for node_id in members:
            node = node_by_id[node_id]
            x, y, z = positions[node_id]
            p = _public(node)
            p.update({"x": x, "y": y, "z": z, "hierarchy_depth": hierarchy.get(node_id), "projection_depth": depth, "projection_generation": node.get("projection_generation"), "projection_parent_id": parent_by_id.get(node_id)})
            projected.append(p)

    if unresolved:
        unresolved_x = max(1500.0, (len(roots) + 1) * root_gap / 2.0 + 650.0)
        groups.append({"id": "projection-depth-unresolved", "title": "projection depth unresolved", "x": unresolved_x, "y": 0.0, "z": 0.0, "count": len(unresolved)})
        for index, node_id in enumerate(sorted(unresolved)):
            node = node_by_id[node_id]
            p = _public(node)
            p.update({"x": unresolved_x + index * sibling_gap, "y": 0.0, "z": 0.0, "hierarchy_depth": hierarchy.get(node_id), "projection_depth": None, "projection_generation": node.get("projection_generation"), "projection_parent_id": parent_by_id.get(node_id)})
            projected.append(p)

    max_extent = max([850.0] + [abs(coord) + 500.0 for position in positions.values() for coord in position])
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max_extent, "layout_rule": "children anchor to projection_parent_id; canonical child direction is -Y; siblings spread on the perpendicular X/Z plane", "child_direction_default": {"x": 0.0, "y": -1.0, "z": 0.0}, "inference": False}


def _relation_web_3d(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    degree = _degree(nodes, edges)
    ordered = sorted(nodes, key=lambda n: (-degree[str(n["id"])], str(n["id"])))
    max_degree = max(degree.values(), default=0)
    projected = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i, node in enumerate(ordered):
        d = degree[str(node["id"])]
        normalized = 0.0 if max_degree == 0 else 1.0 - d / max_degree
        radius = 140.0 + normalized * 1050.0
        y = ((i * 97) % 260 - 130) * (0.45 + normalized)
        theta = i * golden
        p = _public(node)
        p.update({"x": math.cos(theta) * radius, "y": y, "z": math.sin(theta) * radius, "degree": d})
        projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": [], "extent": 1450.0}


def _adjacency_matrix_3d(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    degree = _degree(nodes, edges)
    ordered = sorted(nodes, key=lambda n: (-degree[str(n["id"])], str(n["id"])))
    ids = [str(n["id"]) for n in ordered]
    index = {nid: i for i, nid in enumerate(ids)}
    spacing = 72.0
    dimension_y = {"containment": -220.0, "relations": -110.0, "ownership": 0.0, "authority": 110.0, "dependencies": 220.0}
    center = (len(ids) - 1) * spacing / 2.0
    projected: list[dict[str, Any]] = []
    matrix_edges: list[dict[str, Any]] = []
    for i, node in enumerate(ordered):
        p = _public(node)
        p.update({"x": i * spacing - center, "y": -360.0, "z": i * spacing - center, "degree": degree[str(node["id"])], "projection_parent_id": node.get("projection_parent_id"), "projection_generation": node.get("projection_generation"), "projection_depth": node.get("projection_depth")})
        projected.append(p)
    for edge in edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source not in index or target not in index:
            continue
        cell_id = f"matrix:{edge.get('id') or edge.get('dimension')}:{source}:{target}"
        projected.append({"id": cell_id, "name": edge.get("type") or edge.get("dimension") or "relation", "type": edge.get("dimension"), "status": None, "source_role": "relation_cell", "source": None, "kind": "relation_cell", "x": index[source] * spacing - center, "y": dimension_y.get(str(edge.get("dimension")), 0.0), "z": index[target] * spacing - center, "relation_source": source, "relation_target": target})
        matrix_edges.append({"id": edge.get("id"), "dimension": edge.get("dimension"), "source": source, "target": cell_id, "type": edge.get("type")})
        matrix_edges.append({"id": f"{edge.get('id')}:target" if edge.get("id") else None, "dimension": edge.get("dimension"), "source": cell_id, "target": target, "type": edge.get("type")})
    groups = [{"id": dim, "title": dim, "y": y, "count": sum(1 for e in edges if e.get("dimension") == dim)} for dim, y in dimension_y.items()]
    return {"nodes": projected, "edges": matrix_edges, "groups": groups, "extent": max(900.0, center * 1.35)}


def _lifecycle_lanes_3d(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    preferred = ["unlocked", "locked", "validated", "superseded", "deprecated"]
    statuses = sorted({str(n.get("status") or "unspecified") for n in nodes})
    ordered_statuses = [s for s in preferred if s in statuses] + [s for s in statuses if s not in preferred]
    projected = []
    groups = []
    lane_gap = 330.0
    node_gap = 135.0
    for si, status in enumerate(ordered_statuses):
        members = sorted([n for n in nodes if str(n.get("status") or "unspecified") == status], key=lambda n: str(n["id"]))
        x = (si - (len(ordered_statuses) - 1) / 2) * lane_gap
        groups.append({"id": status, "title": status, "x": x, "y": 0.0, "z": 0.0, "count": len(members)})
        offset = (len(members) - 1) * node_gap / 2.0
        for i, node in enumerate(members):
            p = _public(node)
            p.update({"x": x, "y": ((i % 3) - 1) * 48.0, "z": i * node_gap - offset, "group": status})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(850.0, len(ordered_statuses) * lane_gap, max((len(g) for g in [nodes]), default=1) * 6.0)}


def _dependency_flow_3d(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    depths = _dependency_depths(nodes, edges)
    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_depth[depths[str(node["id"])]] .append(node)
    projected = []
    groups = []
    depth_gap = 330.0
    spacing = 150.0
    for depth in sorted(by_depth):
        members = sorted(by_depth[depth], key=lambda n: str(n["id"]))
        cols = max(1, math.ceil(math.sqrt(len(members))))
        rows = max(1, math.ceil(len(members) / cols))
        z = depth * depth_gap - ((max(by_depth) if by_depth else 0) * depth_gap / 2.0)
        groups.append({"id": str(depth), "title": f"dependency depth {depth}", "x": 0.0, "y": 0.0, "z": z, "count": len(members)})
        for i, node in enumerate(members):
            row, col = divmod(i, cols)
            p = _public(node)
            p.update({"x": (col - (cols - 1) / 2) * spacing, "y": (row - (rows - 1) / 2) * spacing, "z": z, "depth": depth})
            projected.append(p)
    dep_edges = [e for e in edges if e.get("dimension") == "dependencies"]
    return {"nodes": projected, "edges": dep_edges, "groups": groups, "extent": max(900.0, (max(by_depth, default=0) + 1) * depth_gap)}


def build_projection(graph: dict[str, Any], projection_id: str) -> dict[str, Any]:
    if projection_id not in PROJECTIONS:
        raise KeyError(projection_id)
    nodes = _stable_nodes(graph)
    edges = _stable_edges(graph)
    if projection_id == "atlas_3d":
        body = _atlas_3d(nodes, edges)
    elif projection_id == "relation_web_3d":
        body = _relation_web_3d(nodes, edges)
    elif projection_id == "adjacency_matrix_3d":
        body = _adjacency_matrix_3d(nodes, edges)
    elif projection_id == "lifecycle_lanes_3d":
        body = _lifecycle_lanes_3d(nodes, edges)
    elif projection_id == "dependency_flow_3d":
        body = _dependency_flow_3d(nodes, edges)
    else:
        raise KeyError(projection_id)
    meta = PROJECTIONS[projection_id]
    return {"id": projection_id, "title": meta["title"], "dimension": "3d", "kind": meta["kind"], "node_count": len(nodes), "edge_count": len(edges), **body}
