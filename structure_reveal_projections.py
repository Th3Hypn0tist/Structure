from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any


PROJECTIONS: dict[str, dict[str, str]] = {
    "hierarchy_tree_2d": {
        "title": "Hierarchy Tree 2D",
        "dimension": "2d",
        "kind": "structure_reveal",
    },
    "relation_generations_2d": {
        "title": "Relation Generations 2D",
        "dimension": "2d",
        "kind": "structure_reveal",
    },
    "component_islands_2d": {
        "title": "Component Islands 2D",
        "dimension": "2d",
        "kind": "structure_reveal",
    },
    "relation_shells_3d": {
        "title": "Relation Shells 3D",
        "dimension": "3d",
        "kind": "structure_reveal",
    },
    "structure_spine_3d": {
        "title": "Structure Spine 3D",
        "dimension": "3d",
        "kind": "structure_reveal",
    },
}


def _stable_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(graph.get("nodes", []), key=lambda node: str(node.get("id", "")))


def _stable_edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        graph.get("edges", []),
        key=lambda edge: (
            str(edge.get("dimension", "")),
            str(edge.get("source", "")),
            str(edge.get("target", "")),
            str(edge.get("id", "")),
        ),
    )


def _public_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "name": node.get("name") or node.get("id"),
        "type": node.get("type"),
        "status": node.get("status"),
        "source_role": node.get("source_role") or (node.get("raw") or {}).get("metadata", {}).get("source_role"),
        "source": node.get("source"),
        "kind": node.get("kind"),
    }


def _node_ids(nodes: list[dict[str, Any]]) -> set[str]:
    return {str(node.get("id")) for node in nodes if node.get("id") is not None}


def _adjacency(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, list[str]]:
    ids = _node_ids(nodes)
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in ids}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in ids and target in ids:
            adjacency[source].add(target)
            adjacency[target].add(source)
    return {node_id: sorted(neighbors) for node_id, neighbors in adjacency.items()}


def _tree_parent_map(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, str]:
    """Resolve only explicit hierarchy edges.

    StructureTree parent edges use dimension `tree`. Canonical containment is
    accepted as a fallback when the tree edge is absent. Stable ordering is a
    layout tie-breaker only; it does not manufacture a semantic relation.
    """
    ids = _node_ids(nodes)
    candidates: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for edge in edges:
        dimension = str(edge.get("dimension") or "")
        if dimension not in {"tree", "containment"}:
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in ids or target not in ids:
            continue
        priority = 0 if dimension == "tree" else 1
        candidates[target].append((priority, source))
    return {
        target: sorted(values)[0][1]
        for target, values in candidates.items()
        if values
    }


def _hierarchy_depths(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int | None]:
    ids = sorted(_node_ids(nodes))
    parents = _tree_parent_map(nodes, edges)
    memo: dict[str, int | None] = {}

    def resolve(node_id: str, stack: set[str]) -> int | None:
        if node_id in memo:
            return memo[node_id]
        if node_id in stack:
            memo[node_id] = None
            return None
        parent = parents.get(node_id)
        if parent is None or parent not in ids:
            memo[node_id] = 0
            return 0
        parent_depth = resolve(parent, stack | {node_id})
        memo[node_id] = None if parent_depth is None else parent_depth + 1
        return memo[node_id]

    for node_id in ids:
        resolve(node_id, set())
    return memo


def _explicit_root_base(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> set[str]:
    ids = _node_ids(nodes)
    root = str(graph.get("projection_root") or "")
    if not root or root == "all" or root not in ids:
        return set(ids) if root == "all" else set()

    children: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if str(edge.get("dimension") or "") not in {"tree", "containment"}:
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in ids and target in ids:
            children[source].append(target)
    for values in children.values():
        values.sort()

    base: set[str] = set()
    queue = deque([root])
    while queue:
        current = queue.popleft()
        if current in base:
            continue
        base.add(current)
        queue.extend(children.get(current, []))
    return base


def _relation_depths(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int | None]:
    ids = _node_ids(nodes)
    base = _explicit_root_base(graph, nodes, edges)
    if not base:
        # There is no explicit projection root available. Keep the layout
        # deterministic without pretending that an arbitrary node is the root.
        return {node_id: None for node_id in ids}
    if base == ids:
        return {node_id: 0 for node_id in ids}

    adjacency = _adjacency(nodes, edges)
    depth: dict[str, int | None] = {node_id: None for node_id in ids}
    queue = deque()
    for node_id in sorted(base):
        depth[node_id] = 0
        queue.append(node_id)
    while queue:
        current = queue.popleft()
        current_depth = int(depth[current] or 0)
        for neighbor in adjacency.get(current, []):
            if depth[neighbor] is not None:
                continue
            depth[neighbor] = current_depth + 1
            queue.append(neighbor)
    return depth


def _components(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[str]]:
    adjacency = _adjacency(nodes, edges)
    unseen = set(adjacency)
    components: list[list[str]] = []
    while unseen:
        seed = min(unseen)
        queue = deque([seed])
        component: list[str] = []
        unseen.remove(seed)
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in adjacency.get(current, []):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    return sorted(components, key=lambda c: (-len(c), c[0] if c else ""))


def _hierarchy_tree_2d(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    depths = _hierarchy_depths(nodes, edges)
    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    unknown: list[dict[str, Any]] = []
    for node in nodes:
        d = depths[str(node["id"])]
        if d is None:
            unknown.append(node)
        else:
            by_depth[d].append(node)

    width = 3600
    margin = 70
    card_w = 310
    card_h = 92
    row_gap = 110
    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    y = 80
    for depth in sorted(by_depth):
        members = sorted(by_depth[depth], key=lambda n: str(n["id"]))
        cols = max(1, min(10, len(members)))
        gap = 24
        actual_w = min(card_w, (width - margin * 2 - gap * (cols - 1)) / cols)
        start_x = (width - (cols * actual_w + gap * (cols - 1))) / 2
        rows = max(1, math.ceil(len(members) / cols))
        groups.append({"id": f"hierarchy-{depth}", "title": f"hierarchy depth {depth}", "y": y, "count": len(members)})
        for index, node in enumerate(members):
            row, col = divmod(index, cols)
            p = _public_node(node)
            p.update({
                "x": start_x + col * (actual_w + gap),
                "y": y + row * (card_h + 18),
                "width": actual_w,
                "height": card_h,
                "hierarchy_depth": depth,
            })
            projected.append(p)
        y += rows * (card_h + 18) + row_gap

    if unknown:
        groups.append({"id": "hierarchy-unknown", "title": "hierarchy unresolved", "y": y, "count": len(unknown)})
        for index, node in enumerate(sorted(unknown, key=lambda n: str(n["id"]))):
            p = _public_node(node)
            p.update({"x": margin + (index % 8) * 410, "y": y + (index // 8) * 110, "width": card_w, "height": card_h, "hierarchy_depth": None})
            projected.append(p)
        y += max(1, math.ceil(len(unknown) / 8)) * 110 + row_gap

    return {"bounds": {"width": width, "height": max(900, y)}, "nodes": projected, "edges": edges, "groups": groups}


def _relation_generations_2d(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    depths = _relation_depths(graph, nodes, edges)
    buckets: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        buckets[depths[str(node["id"])]].append(node)

    width = 3800
    card_w = 300
    card_h = 92
    column_gap = 110
    known_depths = sorted(d for d in buckets if d is not None)
    columns = known_depths + ([None] if None in buckets else [])
    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    if not columns:
        return {"bounds": {"width": width, "height": 900}, "nodes": [], "edges": edges, "groups": []}

    usable = width - 120
    col_w = max(320, (usable - column_gap * max(0, len(columns) - 1)) / len(columns))
    max_rows = 1
    for ci, depth in enumerate(columns):
        members = sorted(buckets[depth], key=lambda n: str(n["id"]))
        x = 60 + ci * (col_w + column_gap)
        groups.append({"id": f"relation-{depth}", "title": "unreached" if depth is None else f"relation generation {depth}", "x": x, "count": len(members)})
        max_rows = max(max_rows, len(members))
        for ri, node in enumerate(members):
            p = _public_node(node)
            p.update({"x": x, "y": 90 + ri * 112, "width": min(card_w, col_w - 20), "height": card_h, "relation_depth": depth})
            projected.append(p)
    return {"bounds": {"width": max(width, 120 + len(columns) * (col_w + column_gap)), "height": max(900, 180 + max_rows * 112)}, "nodes": projected, "edges": edges, "groups": groups}


def _component_islands_2d(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    components = _components(nodes, edges)
    node_index = {str(node["id"]): node for node in nodes}
    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    island_gap = 130
    width = 3600
    x = 80
    y = 80
    row_h = 0

    for ci, component in enumerate(components):
        count = len(component)
        cols = max(1, min(5, math.ceil(math.sqrt(count))))
        rows = max(1, math.ceil(count / cols))
        card_w = 260
        card_h = 84
        island_w = 40 + cols * (card_w + 18)
        island_h = 70 + rows * (card_h + 18)
        if x + island_w > width - 80 and x > 80:
            x = 80
            y += row_h + island_gap
            row_h = 0
        groups.append({"id": f"component-{ci}", "title": f"component {ci + 1}", "x": x, "y": y, "width": island_w, "height": island_h, "count": count})
        for ni, node_id in enumerate(component):
            row, col = divmod(ni, cols)
            p = _public_node(node_index[node_id])
            p.update({
                "x": x + 20 + col * (card_w + 18),
                "y": y + 54 + row * (card_h + 18),
                "width": card_w,
                "height": card_h,
                "component": ci,
            })
            projected.append(p)
        x += island_w + island_gap
        row_h = max(row_h, island_h)

    height = y + row_h + 100
    return {"bounds": {"width": width, "height": max(900, height)}, "nodes": projected, "edges": edges, "groups": groups}


def _sphere_point(index: int, total: int, radius: float) -> tuple[float, float, float]:
    if total <= 1:
        return radius, 0.0, 0.0
    golden = math.pi * (3.0 - math.sqrt(5.0))
    y = 1.0 - (index / float(total - 1)) * 2.0
    radial = math.sqrt(max(0.0, 1.0 - y * y))
    theta = golden * index
    return math.cos(theta) * radial * radius, y * radius, math.sin(theta) * radial * radius


def _relation_shells_3d(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    depths = _relation_depths(graph, nodes, edges)
    buckets: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        buckets[depths[str(node["id"])]].append(node)
    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    max_shell = 0
    known = sorted(d for d in buckets if d is not None)
    for depth in known:
        members = sorted(buckets[depth], key=lambda n: str(n["id"]))
        radius = 170 + depth * 260
        max_shell = max(max_shell, radius)
        groups.append({"id": f"shell-{depth}", "title": f"relation shell {depth}", "radius": radius, "count": len(members)})
        for index, node in enumerate(members):
            x, y, z = _sphere_point(index, len(members), radius)
            p = _public_node(node)
            p.update({"x": x, "y": y, "z": z, "relation_depth": depth})
            projected.append(p)
    if None in buckets:
        members = sorted(buckets[None], key=lambda n: str(n["id"]))
        radius = max(430, max_shell + 320)
        groups.append({"id": "shell-unreached", "title": "unreached", "radius": radius, "count": len(members)})
        for index, node in enumerate(members):
            x, y, z = _sphere_point(index, len(members), radius)
            p = _public_node(node)
            p.update({"x": x, "y": y, "z": z, "relation_depth": None})
            projected.append(p)
        max_shell = radius
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(650, max_shell * 1.25)}


def _structure_spine_3d(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    hierarchy = _hierarchy_depths(nodes, edges)
    relation = _relation_depths(graph, nodes, edges)
    buckets: dict[tuple[int | None, int | None], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        node_id = str(node["id"])
        buckets[(relation[node_id], hierarchy[node_id])].append(node)

    known_h = [d for d in hierarchy.values() if d is not None]
    unknown_h_y = -(max(known_h, default=0) + 2) * 220
    known_r = [d for d in relation.values() if d is not None]
    unknown_r_x = (max(known_r, default=0) + 2) * 280
    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []

    for (relation_depth, hierarchy_depth), members in sorted(
        buckets.items(),
        key=lambda item: (
            10_000 if item[0][0] is None else item[0][0],
            10_000 if item[0][1] is None else item[0][1],
        ),
    ):
        members = sorted(members, key=lambda n: str(n["id"]))
        x = unknown_r_x if relation_depth is None else relation_depth * 280
        y = unknown_h_y if hierarchy_depth is None else -hierarchy_depth * 220
        groups.append({
            "id": f"r{relation_depth}-h{hierarchy_depth}",
            "title": f"relation {relation_depth} / hierarchy {hierarchy_depth}",
            "x": x,
            "y": y,
            "count": len(members),
        })
        span = max(1, len(members) - 1)
        for index, node in enumerate(members):
            z = (index - span / 2) * 150
            p = _public_node(node)
            p.update({
                "x": x,
                "y": y,
                "z": z,
                "relation_depth": relation_depth,
                "hierarchy_depth": hierarchy_depth,
            })
            projected.append(p)

    extent = max(900, abs(unknown_r_x) + 400, abs(unknown_h_y) + 400)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": extent}


def build_projection(graph: dict[str, Any], projection_id: str) -> dict[str, Any]:
    if projection_id not in PROJECTIONS:
        raise KeyError(projection_id)
    nodes = _stable_nodes(graph)
    edges = _stable_edges(graph)
    meta = PROJECTIONS[projection_id]

    if projection_id == "hierarchy_tree_2d":
        body = _hierarchy_tree_2d(graph, nodes, edges)
    elif projection_id == "relation_generations_2d":
        body = _relation_generations_2d(graph, nodes, edges)
    elif projection_id == "component_islands_2d":
        body = _component_islands_2d(graph, nodes, edges)
    elif projection_id == "relation_shells_3d":
        body = _relation_shells_3d(graph, nodes, edges)
    elif projection_id == "structure_spine_3d":
        body = _structure_spine_3d(graph, nodes, edges)
    else:  # pragma: no cover
        raise KeyError(projection_id)

    return {
        "id": projection_id,
        "title": meta["title"],
        "dimension": meta["dimension"],
        "kind": meta["kind"],
        "node_count": len(nodes),
        "edge_count": len(edges),
        "structure_reveal": True,
        "inference": False,
        "layout_rule": "coordinates derive only from explicit nodes, explicit edges and explicit projection root",
        **body,
    }
