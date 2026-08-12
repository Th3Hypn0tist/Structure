from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


def _dependency_depths(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    ids = [str(n.get("id")) for n in nodes]
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


def _public(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "name": node.get("name") or node.get("id"),
        "type": node.get("type"),
        "status": node.get("status"),
        "source_role": node.get("source_role") or (node.get("raw") or {}).get("source_role"),
        "source": node.get("source"),
        "kind": node.get("kind"),
    }


def build_dependency_flow_3d(graph: dict[str, Any]) -> dict[str, Any]:
    """Dependency flow with exact horizontal semantic depth planes.

    Coordinate contract:
      Y = dependency depth, shallow -> deep from top to bottom
      X = all nodes belonging to one dependency depth
      Z = 0 for the semantic layout

    Node extrusion still gives every rendered object physical Z depth, but the
    layout itself never uses Z to wrap a dependency level. This guarantees that
    all identities at one dependency depth remain visually aligned on one Y
    plane regardless of camera pitch.
    """
    nodes = sorted(graph.get("nodes", []), key=lambda n: str(n.get("id", "")))
    edges = sorted(
        graph.get("edges", []),
        key=lambda e: (
            str(e.get("dimension", "")),
            str(e.get("source", "")),
            str(e.get("target", "")),
            str(e.get("id", "")),
        ),
    )
    depths = _dependency_depths(nodes, edges)
    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_depth[depths[str(node.get("id"))]].append(node)

    max_depth = max(by_depth, default=0)
    layer_gap = 260.0
    x_spacing = 185.0
    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []

    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    for depth in sorted(by_depth):
        members = sorted(by_depth[depth], key=lambda n: str(n.get("id", "")))
        y = (depth - max_depth / 2.0) * layer_gap
        width = max(0.0, (len(members) - 1) * x_spacing)
        start_x = -width / 2.0
        groups.append({
            "id": str(depth),
            "title": f"dependency depth {depth}",
            "x": 0.0,
            "y": y,
            "z": 0.0,
            "count": len(members),
        })
        for i, node in enumerate(members):
            x = start_x + i * x_spacing
            p = _public(node)
            p.update({"x": x, "y": y, "z": 0.0, "depth": depth})
            projected.append(p)
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)

    dependency_edges = [e for e in edges if e.get("dimension") == "dependencies"]

    if not projected:
        extent = 700.0
        bounds = {
            "min_x": 0.0,
            "max_x": 0.0,
            "min_y": 0.0,
            "max_y": 0.0,
            "min_z": 0.0,
            "max_z": 0.0,
        }
    else:
        span_x = max_x - min_x
        span_y = max_y - min_y
        extent = max(700.0, span_x * 0.56, span_y * 0.82)
        bounds = {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "min_z": 0.0,
            "max_z": 0.0,
        }

    return {
        "id": "dependency_flow_3d",
        "title": "Dependency Flow 3D",
        "dimension": "3d",
        "kind": "flow3d",
        "node_count": len(nodes),
        "edge_count": len(dependency_edges),
        "nodes": projected,
        "edges": dependency_edges,
        "groups": groups,
        "extent": extent,
        "bounds3d": bounds,
        "camera_hint": {"rot_x": -8, "rot_y": 16},
        "coordinate_contract": {
            "x": "all nodes within one dependency depth, centered horizontally",
            "y": "dependency depth",
            "z": "zero for layout; physical depth comes only from node extrusion",
        },
    }
