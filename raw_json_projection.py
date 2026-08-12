from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any


def build_raw_json_space_3d(graph: dict[str, Any]) -> dict[str, Any]:
    """Project RawJSON syntax structure into deterministic 3D space.

    This projection uses only explicit RawJSON containment edges and stable node
    identities. It does not interpret key names or infer semantic relations.
    """
    nodes = sorted(graph.get("nodes", []), key=lambda n: str(n.get("id", "")))
    edges = sorted(
        [e for e in graph.get("edges", []) if e.get("dimension") == "containment"],
        key=lambda e: (str(e.get("source", "")), str(e.get("target", ""))),
    )
    by_id = {str(n.get("id")): n for n in nodes}
    children: dict[str, list[str]] = defaultdict(list)
    incoming: set[str] = set()
    for edge in edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in by_id and target in by_id:
            children[source].append(target)
            incoming.add(target)
    for key in children:
        children[key].sort()

    roots = sorted(nid for nid in by_id if nid not in incoming)
    if not roots and nodes:
        roots = [str(nodes[0].get("id"))]

    depth: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    queue: deque[tuple[str, int, str | None]] = deque((root, 0, None) for root in roots)
    while queue:
        nid, d, parent_id = queue.popleft()
        if nid in depth:
            continue
        depth[nid] = d
        parent[nid] = parent_id
        for child in children.get(nid, []):
            queue.append((child, d + 1, nid))

    # Any disconnected nodes remain explicit and are placed on depth zero.
    for nid in by_id:
        if nid not in depth:
            depth[nid] = 0
            parent[nid] = None

    levels: dict[int, list[str]] = defaultdict(list)
    for nid, d in depth.items():
        levels[d].append(nid)
    for d in levels:
        levels[d].sort()

    projected: list[dict[str, Any]] = []
    max_radius = 260.0
    level_gap = 230.0
    for d in sorted(levels):
        members = levels[d]
        total = max(1, len(members))
        radius = max(120.0, min(1450.0, 80.0 + math.sqrt(total) * 115.0))
        max_radius = max(max_radius, radius)
        for i, nid in enumerate(members):
            angle = (2.0 * math.pi * i / total) + d * 0.43
            node = by_id[nid]
            projected.append({
                "id": nid,
                "name": node.get("name") or node.get("label") or nid,
                "type": node.get("type") or node.get("kind"),
                "status": node.get("status"),
                "source_role": "raw_json_syntax",
                "source": node.get("source"),
                "kind": node.get("kind") or "raw_json_node",
                "x": math.cos(angle) * radius,
                "y": -d * level_gap,
                "z": math.sin(angle) * radius,
                "depth": d,
                "parent_id": parent.get(nid),
            })

    return {
        "id": "raw_json_space_3d",
        "title": "JSON Space 3D",
        "dimension": "3d",
        "kind": "raw_json_space",
        "node_count": len(projected),
        "edge_count": len(edges),
        "nodes": projected,
        "edges": edges,
        "groups": [
            {"id": str(d), "title": f"JSON depth {d}", "y": -d * level_gap, "count": len(levels[d])}
            for d in sorted(levels)
        ],
        "extent": max(700.0, max_radius * 1.5, (max(depth.values(), default=0) + 1) * level_gap),
        "projection_rule": "JSON syntax containment only; no semantic inference",
    }
