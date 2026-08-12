from __future__ import annotations

import math
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
    """Dependency flow with semantic depth on the vertical Y axis.

    Coordinate contract:
      Y = dependency depth, shallow -> deep from top to bottom
      X = horizontal distribution inside one depth level
      Z = secondary row depth only inside one level

    The layout uses only explicit dependency edges. No semantic ordering is
    inferred from names, paths or labels.
    """
    nodes = sorted(graph.get("nodes", []), key=lambda n: str(n.get("id", "")))
    edges = sorted(
        graph.get("edges", []),
        key=lambda e: (str(e.get("dimension", "")), str(e.get("source", "")), str(e.get("target", "")), str(e.get("id", ""))),
    )
    depths = _dependency_depths(nodes, edges)
    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_depth[depths[str(node.get("id"))]].append(node)

    max_depth = max(by_depth, default=0)
    layer_gap = 260.0
    x_spacing = 190.0
    z_spacing = 145.0
    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []

    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

    for depth in sorted(by_depth):
        members = sorted(by_depth[depth], key=lambda n: str(n.get("id", "")))
        # Keep layers broad and shallow so the hierarchy reads vertically instead
        # of becoming a wall viewed edge-on.
        cols = max(1, min(9, math.ceil(math.sqrt(len(members) * 1.8))))
        rows = max(1, math.ceil(len(members) / cols))
        y = (depth - max_depth / 2.0) * layer_gap
        groups.append({
            "id": str(depth),
            "title": f"dependency depth {depth}",
            "x": 0.0,
            "y": y,
            "z": 0.0,
            "count": len(members),
        })
        for i, node in enumerate(members):
            row, col = divmod(i, cols)
            x = (col - (cols - 1) / 2.0) * x_spacing
            z = (row - (rows - 1) / 2.0) * z_spacing
            p = _public(node)
            p.update({"x": x, "y": y, "z": z, "depth": depth})
            projected.append(p)
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            min_z, max_z = min(min_z, z), max(max_z, z)

    dependency_edges = [e for e in edges if e.get("dimension") == "dependencies"]

    if not projected:
        extent = 700.0
        bounds = {"min_x": 0.0, "max_x": 0.0, "min_y": 0.0, "max_y": 0.0, "min_z": 0.0, "max_z": 0.0}
    else:
        span_x = max_x - min_x
        span_y = max_y - min_y
        span_z = max_z - min_z
        # Renderer uses one scalar scene scale, so the extent must be based on
        # actual coordinate span rather than just number of dependency layers.
        extent = max(700.0, span_x * 0.62, span_y * 0.78, span_z * 0.82)
        bounds = {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "min_z": min_z,
            "max_z": max_z,
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
        "camera_hint": {"rot_x": -12, "rot_y": 18},
        "coordinate_contract": {
            "x": "within-layer horizontal distribution",
            "y": "dependency depth",
            "z": "within-layer secondary row depth",
        },
    }
