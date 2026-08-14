from __future__ import annotations

import math
from collections import defaultdict, deque
from copy import deepcopy
from typing import Any


# Visual styles are geometry only. They never decide which semantic edges or
# identities belong to a projection; the semantic projection engine has already
# done that before this module is called.
STYLE_FAMILIES: dict[str, dict[str, Any]] = {
    "atlas": {"label": "Atlas"},
    "map": {"label": "Map"},
    "matrix": {"label": "Matrix"},
    "lifecycle_lanes": {"label": "Lanes"},
    "dependency_flow": {"label": "Flow"},
    "galaxy": {"label": "Galaxy"},
    "role_layers": {"label": "Layers"},
    "dependency_tower": {"label": "Tower"},
    "authority_space": {"label": "Space"},
    "relation_orbits": {"label": "Orbits"},
    "hierarchy_tree": {"label": "Tree"},
    "relation_generations": {"label": "Generations"},
    "component_islands": {"label": "Islands"},
    "relation_shells": {"label": "Shells"},
    "structure_spine": {"label": "Spine"},
}

PROJECTIONS: dict[str, dict[str, str]] = {}
for _style_id, _style in STYLE_FAMILIES.items():
    for _dimension in ("2d", "3d"):
        _generator = f"semantic_{_style_id}_{_dimension}"
        PROJECTIONS[_generator] = {
            "title": f"{_style['label']} {_dimension.upper()}",
            "dimension": _dimension,
            "kind": "semantic_visual",
            "style": _style_id,
        }


# Old generator ids are accepted as compatibility aliases, but they resolve to
# the new semantics-first visual kernel.
LEGACY_GENERATOR_ALIASES: dict[str, tuple[str, str]] = {
    "atlas_2d": ("atlas", "2d"),
    "atlas_3d": ("atlas", "3d"),
    "relation_web_2d": ("map", "2d"),
    "relation_web_3d": ("map", "3d"),
    "adjacency_matrix_2d": ("matrix", "2d"),
    "adjacency_matrix_3d": ("matrix", "3d"),
    "lifecycle_lanes_2d": ("lifecycle_lanes", "2d"),
    "lifecycle_lanes_3d": ("lifecycle_lanes", "3d"),
    "dependency_flow_2d": ("dependency_flow", "2d"),
    "dependency_flow_3d": ("dependency_flow", "3d"),
    "semantic_galaxy_3d": ("galaxy", "3d"),
    "role_layers_3d": ("role_layers", "3d"),
    "dependency_tower_3d": ("dependency_tower", "3d"),
    "authority_space_3d": ("authority_space", "3d"),
    "relation_orbits_3d": ("relation_orbits", "3d"),
    "hierarchy_tree_2d": ("hierarchy_tree", "2d"),
    "relation_generations_2d": ("relation_generations", "2d"),
    "component_islands_2d": ("component_islands", "2d"),
    "relation_shells_3d": ("relation_shells", "3d"),
    "structure_spine_3d": ("structure_spine", "3d"),
}


def style_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": style_id,
            "label": spec["label"],
            "dimensions": ["2d", "3d"],
            "variants": {
                "2d": f"semantic_{style_id}_2d",
                "3d": f"semantic_{style_id}_3d",
            },
            "kind": "semantic_visual",
            "semantic_neutral": True,
        }
        for style_id, spec in STYLE_FAMILIES.items()
    ]


def resolve_visual_style(style: str, dimension: str | None = None) -> tuple[str, str, str]:
    style = str(style or "atlas").strip()
    requested_dimension = str(dimension or "3d").lower().strip()
    if requested_dimension not in {"2d", "3d"}:
        raise KeyError(f"Unsupported projection dimension: {requested_dimension}")

    if style in LEGACY_GENERATOR_ALIASES:
        family, legacy_dimension = LEGACY_GENERATOR_ALIASES[style]
        if dimension is None:
            requested_dimension = legacy_dimension
        style = family
    elif style in PROJECTIONS:
        meta = PROJECTIONS[style]
        family = meta["style"]
        generator_dimension = meta["dimension"]
        if dimension is None:
            requested_dimension = generator_dimension
        style = family

    if style not in STYLE_FAMILIES:
        raise KeyError(f"Unknown visual style: {style}")
    return style, requested_dimension, f"semantic_{style}_{requested_dimension}"


def _nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [deepcopy(node) for node in graph.get("nodes", []) if isinstance(node, dict) and node.get("id") is not None],
        key=lambda node: str(node.get("id")),
    )


def _edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [deepcopy(edge) for edge in graph.get("edges", []) if isinstance(edge, dict)],
        key=lambda edge: (
            str(edge.get("dimension") or ""),
            str(edge.get("source") or ""),
            str(edge.get("target") or ""),
            str(edge.get("id") or ""),
        ),
    )


def _node_ids(nodes: list[dict[str, Any]]) -> set[str]:
    return {str(node["id"]) for node in nodes}


def _public(node: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(node)
    out["id"] = str(node.get("id"))
    out["name"] = node.get("name") or node.get("id")
    return out


def _base_ids(graph: dict[str, Any], nodes: list[dict[str, Any]]) -> set[str]:
    ids = _node_ids(nodes)
    explicit = {str(ref) for ref in graph.get("projection_base_ids", []) if str(ref) in ids}
    if explicit:
        return explicit
    depth_zero = {
        str(node["id"])
        for node in nodes
        if isinstance(node.get("projection_depth"), int) and int(node["projection_depth"]) == 0
    }
    if depth_zero:
        return depth_zero
    root = str(graph.get("projection_root") or "")
    if root in ids:
        return {root}
    return {min(ids)} if ids else set()


def _adjacency(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, list[str]]:
    ids = _node_ids(nodes)
    out: dict[str, set[str]] = {node_id: set() for node_id in ids}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in ids and target in ids:
            out[source].add(target)
            out[target].add(source)
    return {node_id: sorted(values) for node_id, values in out.items()}


def _degree(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    adjacency = _adjacency(nodes, edges)
    return {node_id: len(values) for node_id, values in adjacency.items()}


def _semantic_depths(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    ids = _node_ids(nodes)
    depth: dict[str, int] = {}
    for node in nodes:
        raw = node.get("projection_depth")
        if isinstance(raw, int) and raw >= 0:
            depth[str(node["id"])] = raw
    if len(depth) == len(ids):
        return depth

    adjacency = _adjacency(nodes, edges)
    queue = deque()
    for base in sorted(_base_ids(graph, nodes)):
        if base not in depth or depth[base] != 0:
            depth[base] = 0
        queue.append(base)
    while queue:
        current = queue.popleft()
        current_depth = depth[current]
        for neighbor in adjacency.get(current, []):
            candidate = current_depth + 1
            if neighbor not in depth or candidate < depth[neighbor]:
                depth[neighbor] = candidate
                queue.append(neighbor)
    fallback = max(depth.values(), default=-1) + 1
    for node_id in sorted(ids):
        if node_id not in depth:
            depth[node_id] = fallback
    return depth


def _layout_parents(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], depth: dict[str, int]) -> dict[str, str | None]:
    ids = _node_ids(nodes)
    adjacency = _adjacency(nodes, edges)
    parent: dict[str, str | None] = {}
    for node in nodes:
        node_id = str(node["id"])
        raw = node.get("projection_parent_id")
        if raw is not None and str(raw) in ids:
            parent[node_id] = str(raw)
            continue
        if depth.get(node_id, 0) <= 0:
            parent[node_id] = None
            continue
        candidates = [neighbor for neighbor in adjacency.get(node_id, []) if depth.get(neighbor) == depth[node_id] - 1]
        parent[node_id] = min(candidates) if candidates else None
    return parent


def _components(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[str]]:
    adjacency = _adjacency(nodes, edges)
    unseen = set(adjacency)
    out: list[list[str]] = []
    while unseen:
        seed = min(unseen)
        queue = deque([seed])
        unseen.remove(seed)
        component: list[str] = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in adjacency.get(current, []):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
        out.append(sorted(component))
    return sorted(out, key=lambda values: (-len(values), values[0] if values else ""))


def _circle(index: int, total: int, radius: float) -> tuple[float, float]:
    if total <= 1:
        return 0.0, 0.0
    angle = 2.0 * math.pi * index / total
    return math.cos(angle) * radius, math.sin(angle) * radius


def _sphere(index: int, total: int, radius: float) -> tuple[float, float, float]:
    if total <= 1:
        return 0.0, 0.0, 0.0
    golden = math.pi * (3.0 - math.sqrt(5.0))
    y = 1.0 - (index / float(total - 1)) * 2.0
    radial = math.sqrt(max(0.0, 1.0 - y * y))
    theta = golden * index
    return math.cos(theta) * radial * radius, y * radius, math.sin(theta) * radial * radius


def _by_depth(nodes: list[dict[str, Any]], depth: dict[str, int]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        out[depth[str(node["id"])]].append(node)
    for values in out.values():
        values.sort(key=lambda node: str(node["id"]))
    return out


def _atlas(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    depth = _semantic_depths(graph, nodes, edges)
    groups = []
    projected = []
    by_depth = _by_depth(nodes, depth)
    if dimension == "2d":
        width = 3600.0
        y = 80.0
        for level in sorted(by_depth):
            members = by_depth[level]
            cols = max(1, min(9, len(members)))
            rows = max(1, math.ceil(len(members) / cols))
            card_w, card_h, gap = 330.0, 84.0, 26.0
            row_w = cols * card_w + (cols - 1) * gap
            start_x = (width - row_w) / 2.0
            groups.append({"id": f"depth-{level}", "title": f"projection depth {level}", "y": y, "count": len(members)})
            for index, node in enumerate(members):
                row, col = divmod(index, cols)
                p = _public(node)
                p.update({"x": start_x + col * (card_w + gap), "y": y + row * 106.0, "width": card_w, "height": card_h, "projection_depth": level})
                projected.append(p)
            y += rows * 106.0 + 120.0
        return {"bounds": {"width": width, "height": max(900.0, y)}, "nodes": projected, "edges": edges, "groups": groups}

    depth_gap = 300.0
    for level in sorted(by_depth):
        members = by_depth[level]
        radius = max(180.0, 72.0 * len(members))
        groups.append({"id": f"depth-{level}", "title": f"projection depth {level}", "y": -level * depth_gap, "count": len(members)})
        for index, node in enumerate(members):
            x, z = _circle(index, len(members), radius)
            p = _public(node)
            p.update({"x": x, "y": -level * depth_gap, "z": z, "projection_depth": level})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, (max(by_depth, default=0) + 1) * depth_gap)}


def _map(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    depth = _semantic_depths(graph, nodes, edges)
    degree = _degree(nodes, edges)
    by_depth = _by_depth(nodes, depth)
    projected = []
    groups = []
    if dimension == "2d":
        cx, cy = 1600.0, 1200.0
        for level in sorted(by_depth):
            members = sorted(by_depth[level], key=lambda node: (-degree[str(node["id"])], str(node["id"])))
            radius = 0.0 if level == 0 and len(members) == 1 else 180.0 + level * 250.0
            groups.append({"id": f"shell-{level}", "title": f"distance {level}", "radius": radius, "count": len(members)})
            for index, node in enumerate(members):
                x, y = _circle(index, len(members), radius)
                p = _public(node)
                p.update({"x": cx + x, "y": cy + y, "radius": 30 + min(22, degree[str(node["id"])] * 2), "projection_depth": level})
                projected.append(p)
        max_level = max(by_depth, default=0)
        size = max(1800.0, 700.0 + max_level * 550.0)
        return {"bounds": {"width": max(3200.0, size), "height": max(2400.0, size)}, "nodes": projected, "edges": edges, "groups": groups}

    for level in sorted(by_depth):
        members = sorted(by_depth[level], key=lambda node: (-degree[str(node["id"])], str(node["id"])))
        radius = 100.0 + level * 300.0
        groups.append({"id": f"shell-{level}", "title": f"distance {level}", "radius": radius, "count": len(members)})
        for index, node in enumerate(members):
            x, y, z = _sphere(index, len(members), radius)
            p = _public(node)
            p.update({"x": x, "y": y, "z": z, "degree": degree[str(node["id"])], "projection_depth": level})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, 250.0 + max(by_depth, default=0) * 360.0)}


def _matrix(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    degree = _degree(nodes, edges)
    ordered = sorted(nodes, key=lambda node: (-degree[str(node["id"])], str(node["id"])))
    ids = [str(node["id"]) for node in ordered]
    index = {node_id: i for i, node_id in enumerate(ids)}
    spacing = 74.0
    center = (len(ids) - 1) * spacing / 2.0
    projected = []
    matrix_edges = []
    for i, node in enumerate(ordered):
        p = _public(node)
        if dimension == "2d":
            p.update({"x": 260.0 + i * spacing, "y": 260.0 + i * spacing, "width": 64.0, "height": 64.0, "degree": degree[str(node["id"])]})
        else:
            p.update({"x": i * spacing - center, "y": -320.0, "z": i * spacing - center, "degree": degree[str(node["id"])]})
        projected.append(p)
    for edge_index, edge in enumerate(edges):
        source, target = str(edge.get("source") or ""), str(edge.get("target") or "")
        if source not in index or target not in index:
            continue
        cell_id = f"matrix:{edge.get('id') or edge_index}:{source}:{target}"
        cell = {
            "id": cell_id,
            "name": edge.get("type") or edge.get("relation_type") or edge.get("dimension") or "relation",
            "type": "relation_cell",
            "kind": "relation_cell",
            "relation_source": source,
            "relation_target": target,
            "relation_dimension": edge.get("dimension"),
        }
        if dimension == "2d":
            cell.update({"x": 260.0 + index[source] * spacing, "y": 260.0 + index[target] * spacing, "width": 38.0, "height": 38.0})
        else:
            cell.update({"x": index[source] * spacing - center, "y": 0.0, "z": index[target] * spacing - center})
        projected.append(cell)
        matrix_edges.append({"id": f"matrix-source:{edge_index}", "source": source, "target": cell_id, "dimension": edge.get("dimension"), "type": edge.get("type")})
        matrix_edges.append({"id": f"matrix-target:{edge_index}", "source": cell_id, "target": target, "dimension": edge.get("dimension"), "type": edge.get("type")})
    if dimension == "2d":
        size = max(1000.0, 520.0 + len(ids) * spacing)
        return {"bounds": {"width": size, "height": size}, "nodes": projected, "edges": matrix_edges, "groups": []}
    return {"nodes": projected, "edges": matrix_edges, "groups": [], "extent": max(900.0, center * 1.35 + 500.0)}


def _lanes(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    depth = _semantic_depths(graph, nodes, edges)
    by_depth = _by_depth(nodes, depth)
    projected = []
    groups = []
    if dimension == "2d":
        lane_w, gap = 360.0, 70.0
        max_rows = 1
        for column, level in enumerate(sorted(by_depth)):
            members = by_depth[level]
            x = 80.0 + column * (lane_w + gap)
            groups.append({"id": f"lane-{level}", "title": f"projection depth {level}", "x": x, "count": len(members)})
            max_rows = max(max_rows, len(members))
            for row, node in enumerate(members):
                p = _public(node)
                p.update({"x": x, "y": 100.0 + row * 106.0, "width": lane_w, "height": 82.0, "projection_depth": level})
                projected.append(p)
        return {"bounds": {"width": max(1200.0, 160.0 + len(by_depth) * (lane_w + gap)), "height": max(900.0, 220.0 + max_rows * 106.0)}, "nodes": projected, "edges": edges, "groups": groups}

    gap = 260.0
    for level in sorted(by_depth):
        members = by_depth[level]
        cols = max(1, math.ceil(math.sqrt(len(members))))
        rows = max(1, math.ceil(len(members) / cols))
        groups.append({"id": f"lane-{level}", "title": f"projection depth {level}", "y": -level * gap, "count": len(members)})
        for index, node in enumerate(members):
            row, col = divmod(index, cols)
            p = _public(node)
            p.update({"x": (col - (cols - 1) / 2.0) * 190.0, "y": -level * gap, "z": (row - (rows - 1) / 2.0) * 190.0, "projection_depth": level})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, (max(by_depth, default=0) + 1) * gap)}


def _flow(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    # The semantic engine already selected the correct edge type. Flow layout
    # only uses projection depth as the stable ordering axis and preserves the
    # original edge direction visually.
    depth = _semantic_depths(graph, nodes, edges)
    by_depth = _by_depth(nodes, depth)
    projected = []
    groups = []
    if dimension == "2d":
        x_gap = 430.0
        max_rows = 1
        for column, level in enumerate(sorted(by_depth)):
            members = by_depth[level]
            x = 100.0 + column * x_gap
            groups.append({"id": f"flow-{level}", "title": f"step {level}", "x": x, "count": len(members)})
            max_rows = max(max_rows, len(members))
            for row, node in enumerate(members):
                p = _public(node)
                p.update({"x": x, "y": 100.0 + row * 110.0, "width": 330.0, "height": 84.0, "projection_depth": level})
                projected.append(p)
        return {"bounds": {"width": max(1400.0, 260.0 + len(by_depth) * x_gap), "height": max(900.0, 240.0 + max_rows * 110.0)}, "nodes": projected, "edges": edges, "groups": groups}

    y_gap = 300.0
    for level in sorted(by_depth):
        members = by_depth[level]
        radius = max(150.0, len(members) * 55.0)
        groups.append({"id": f"flow-{level}", "title": f"step {level}", "y": -level * y_gap, "count": len(members)})
        for index, node in enumerate(members):
            x, z = _circle(index, len(members), radius)
            p = _public(node)
            p.update({"x": x, "y": -level * y_gap, "z": z, "projection_depth": level})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, (max(by_depth, default=0) + 1) * y_gap)}


def _galaxy(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    degree = _degree(nodes, edges)
    depth = _semantic_depths(graph, nodes, edges)
    ordered = sorted(nodes, key=lambda node: (depth[str(node["id"])], -degree[str(node["id"])], str(node["id"])))
    projected = []
    if dimension == "2d":
        cx, cy = 1600.0, 1200.0
        for index, node in enumerate(ordered):
            d = depth[str(node["id"])]
            radius = 160.0 + d * 230.0 + (index % 5) * 16.0
            angle = index * 2.399963229728653
            p = _public(node)
            p.update({"x": cx + math.cos(angle) * radius, "y": cy + math.sin(angle) * radius, "radius": 28 + min(20, degree[str(node["id"])] * 2), "projection_depth": d})
            projected.append(p)
        max_depth = max(depth.values(), default=0)
        size = max(2600.0, 900.0 + max_depth * 520.0)
        return {"bounds": {"width": size, "height": size}, "nodes": projected, "edges": edges, "groups": []}

    radius = max(420.0, 100.0 * math.sqrt(max(1, len(ordered))))
    for index, node in enumerate(ordered):
        x, y, z = _sphere(index, len(ordered), radius + depth[str(node["id"])] * 80.0)
        p = _public(node)
        p.update({"x": x, "y": y, "z": z, "degree": degree[str(node["id"])], "projection_depth": depth[str(node["id"])]})
        projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": [], "extent": radius * 1.5 + max(depth.values(), default=0) * 100.0}


def _layers(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    return _lanes(graph, nodes, edges, dimension)


def _tower(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    depth = _semantic_depths(graph, nodes, edges)
    by_depth = _by_depth(nodes, depth)
    projected = []
    groups = []
    if dimension == "2d":
        width = 3200.0
        y = 90.0
        for level in sorted(by_depth):
            members = by_depth[level]
            card_w = 300.0
            gap = 24.0
            row_w = len(members) * card_w + max(0, len(members) - 1) * gap
            start_x = max(60.0, (width - row_w) / 2.0)
            groups.append({"id": f"tower-{level}", "title": f"level {level}", "y": y, "count": len(members)})
            for index, node in enumerate(members):
                p = _public(node)
                p.update({"x": start_x + index * (card_w + gap), "y": y, "width": card_w, "height": 84.0, "projection_depth": level})
                projected.append(p)
            y += 180.0
        return {"bounds": {"width": width, "height": max(900.0, y + 80.0)}, "nodes": projected, "edges": edges, "groups": groups}

    gap = 250.0
    for level in sorted(by_depth):
        members = by_depth[level]
        radius = 160.0 + max(0, len(members) - 1) * 22.0
        y = -level * gap
        groups.append({"id": f"tower-{level}", "title": f"level {level}", "y": y, "count": len(members)})
        for index, node in enumerate(members):
            x, z = _circle(index, len(members), radius)
            p = _public(node)
            p.update({"x": x, "y": y, "z": z, "projection_depth": level})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, (max(by_depth, default=0) + 1) * gap)}


def _space(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    ids = _node_ids(nodes)
    incoming = {node_id: 0 for node_id in ids}
    outgoing = {node_id: 0 for node_id in ids}
    for edge in edges:
        source, target = str(edge.get("source") or ""), str(edge.get("target") or "")
        if source in outgoing:
            outgoing[source] += 1
        if target in incoming:
            incoming[target] += 1
    depth = _semantic_depths(graph, nodes, edges)
    projected = []
    for index, node in enumerate(nodes):
        node_id = str(node["id"])
        x = (outgoing[node_id] - incoming[node_id]) * 190.0
        y = -depth[node_id] * 210.0
        jitter_x, jitter_z = _circle(index, max(1, len(nodes)), 80.0 + (index % 4) * 16.0)
        p = _public(node)
        if dimension == "2d":
            p.update({"x": 1600.0 + x + jitter_x, "y": 120.0 + depth[node_id] * 240.0 + jitter_z, "width": 280.0, "height": 82.0, "incoming": incoming[node_id], "outgoing": outgoing[node_id], "projection_depth": depth[node_id]})
        else:
            z = (incoming[node_id] + outgoing[node_id]) * 120.0 + jitter_z
            p.update({"x": x + jitter_x, "y": y, "z": z, "incoming": incoming[node_id], "outgoing": outgoing[node_id], "projection_depth": depth[node_id]})
        projected.append(p)
    if dimension == "2d":
        return {"bounds": {"width": 3200.0, "height": max(1600.0, 500.0 + max(depth.values(), default=0) * 260.0)}, "nodes": projected, "edges": edges, "groups": []}
    return {"nodes": projected, "edges": edges, "groups": [], "extent": max(1000.0, 500.0 + max(depth.values(), default=0) * 240.0)}


def _orbits(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    degree = _degree(nodes, edges)
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        d = degree[str(node["id"])]
        bucket = 0 if d == 0 else int(math.log2(d)) + 1
        buckets[bucket].append(node)
    projected = []
    groups = []
    cx, cy = 1600.0, 1200.0
    for bucket_index, bucket in enumerate(sorted(buckets)):
        members = sorted(buckets[bucket], key=lambda node: str(node["id"]))
        radius = 170.0 + bucket_index * 230.0
        groups.append({"id": f"orbit-{bucket}", "title": f"connectivity orbit {bucket}", "radius": radius, "count": len(members)})
        for index, node in enumerate(members):
            x, z = _circle(index, len(members), radius)
            p = _public(node)
            if dimension == "2d":
                p.update({"x": cx + x, "y": cy + z, "radius": 30 + min(18, degree[str(node["id"])] * 2), "degree": degree[str(node["id"])]})
            else:
                p.update({"x": x, "y": (bucket_index - (len(buckets) - 1) / 2.0) * 110.0, "z": z, "degree": degree[str(node["id"])]})
            projected.append(p)
    if dimension == "2d":
        return {"bounds": {"width": 3200.0, "height": 2400.0}, "nodes": projected, "edges": edges, "groups": groups}
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": 400.0 + len(buckets) * 260.0}


def _tree(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    depth = _semantic_depths(graph, nodes, edges)
    parents = _layout_parents(graph, nodes, edges, depth)
    by_depth = _by_depth(nodes, depth)
    children: dict[str, list[str]] = defaultdict(list)
    for child, parent in parents.items():
        if parent:
            children[parent].append(child)
    for values in children.values():
        values.sort()
    node_index = {str(node["id"]): node for node in nodes}
    projected = []
    groups = []
    if dimension == "2d":
        width = 3600.0
        for level in sorted(by_depth):
            members = by_depth[level]
            step = width / (len(members) + 1)
            groups.append({"id": f"tree-{level}", "title": f"depth {level}", "y": 100.0 + level * 190.0, "count": len(members)})
            for index, node in enumerate(members, start=1):
                p = _public(node)
                p.update({"x": index * step - 150.0, "y": 100.0 + level * 190.0, "width": 300.0, "height": 84.0, "layout_parent_id": parents[str(node["id"])], "projection_depth": level})
                projected.append(p)
        return {"bounds": {"width": width, "height": max(900.0, 300.0 + max(by_depth, default=0) * 200.0)}, "nodes": projected, "edges": edges, "groups": groups}

    roots = sorted([node_id for node_id, parent in parents.items() if parent is None])
    positions: dict[str, tuple[float, float, float]] = {}
    root_gap = 700.0
    for root_index, root in enumerate(roots):
        positions[root] = ((root_index - (len(roots) - 1) / 2.0) * root_gap, 0.0, 0.0)
        queue = deque([root])
        while queue:
            parent_id = queue.popleft()
            px, _py, pz = positions[parent_id]
            values = children.get(parent_id, [])
            for index, child in enumerate(values):
                x, z = _circle(index, len(values), max(170.0, len(values) * 48.0))
                positions[child] = (px + x, -depth[child] * 260.0, pz + z)
                queue.append(child)
    for node_id in sorted(node_index):
        if node_id not in positions:
            positions[node_id] = (0.0, -depth[node_id] * 260.0, 0.0)
        x, y, z = positions[node_id]
        p = _public(node_index[node_id])
        p.update({"x": x, "y": y, "z": z, "layout_parent_id": parents[node_id], "projection_depth": depth[node_id]})
        projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, (max(depth.values(), default=0) + 1) * 300.0)}


def _generations(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    return _flow(graph, nodes, edges, dimension)


def _islands(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    components = _components(nodes, edges)
    index = {str(node["id"]): node for node in nodes}
    projected = []
    groups = []
    if dimension == "2d":
        width = 3600.0
        x, y, row_h = 80.0, 80.0, 0.0
        for component_index, component in enumerate(components):
            cols = max(1, min(5, math.ceil(math.sqrt(len(component)))))
            rows = max(1, math.ceil(len(component) / cols))
            island_w = 60.0 + cols * 280.0
            island_h = 80.0 + rows * 102.0
            if x + island_w > width - 80.0 and x > 80.0:
                x = 80.0
                y += row_h + 100.0
                row_h = 0.0
            groups.append({"id": f"component-{component_index}", "title": f"component {component_index + 1}", "x": x, "y": y, "width": island_w, "height": island_h, "count": len(component)})
            for item_index, node_id in enumerate(component):
                row, col = divmod(item_index, cols)
                p = _public(index[node_id])
                p.update({"x": x + 30.0 + col * 280.0, "y": y + 55.0 + row * 102.0, "width": 250.0, "height": 82.0, "component": component_index})
                projected.append(p)
            x += island_w + 100.0
            row_h = max(row_h, island_h)
        return {"bounds": {"width": width, "height": max(900.0, y + row_h + 100.0)}, "nodes": projected, "edges": edges, "groups": groups}

    cluster_gap = 900.0
    for component_index, component in enumerate(components):
        center_x = (component_index - (len(components) - 1) / 2.0) * cluster_gap
        radius = max(160.0, 65.0 * math.sqrt(len(component)))
        groups.append({"id": f"component-{component_index}", "title": f"component {component_index + 1}", "x": center_x, "count": len(component)})
        for item_index, node_id in enumerate(component):
            x, y, z = _sphere(item_index, len(component), radius)
            p = _public(index[node_id])
            p.update({"x": center_x + x, "y": y, "z": z, "component": component_index})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, len(components) * cluster_gap / 2.0 + 600.0)}


def _shells(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    return _map(graph, nodes, edges, dimension)


def _spine(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    depth = _semantic_depths(graph, nodes, edges)
    parents = _layout_parents(graph, nodes, edges, depth)
    children: dict[str, list[str]] = defaultdict(list)
    for child, parent in parents.items():
        if parent:
            children[parent].append(child)
    for values in children.values():
        values.sort()

    # Choose the deepest explicit/layout chain as the visual spine. This is a
    # presentation choice only; it does not become semantic authority.
    deepest = max(depth, key=lambda node_id: (depth[node_id], node_id), default=None)
    spine: list[str] = []
    current = deepest
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        spine.append(current)
        current = parents.get(current)
    spine.reverse()
    spine_set = set(spine)
    node_index = {str(node["id"]): node for node in nodes}
    projected = []
    groups = [{"id": "spine", "title": "layout spine", "count": len(spine)}]

    if dimension == "2d":
        x_step = 390.0
        positions: dict[str, tuple[float, float]] = {}
        for index, node_id in enumerate(spine):
            positions[node_id] = (120.0 + index * x_step, 700.0)
        branch_index = defaultdict(int)
        for node_id in sorted(node_index, key=lambda value: (depth[value], value)):
            if node_id in spine_set:
                continue
            ancestor = parents.get(node_id)
            while ancestor and ancestor not in spine_set:
                ancestor = parents.get(ancestor)
            anchor = ancestor if ancestor in positions else (spine[0] if spine else None)
            ax, ay = positions.get(anchor, (120.0, 700.0))
            slot = branch_index[anchor]
            branch_index[anchor] += 1
            side = -1 if slot % 2 == 0 else 1
            positions[node_id] = (ax, ay + side * (150.0 + (slot // 2) * 120.0))
        for node_id, node in node_index.items():
            x, y = positions.get(node_id, (120.0, 700.0))
            p = _public(node)
            p.update({"x": x, "y": y, "width": 300.0, "height": 84.0, "on_layout_spine": node_id in spine_set, "layout_parent_id": parents.get(node_id)})
            projected.append(p)
        return {"bounds": {"width": max(1600.0, 500.0 + len(spine) * x_step), "height": 1500.0}, "nodes": projected, "edges": edges, "groups": groups}

    y_step = 280.0
    positions3: dict[str, tuple[float, float, float]] = {}
    for index, node_id in enumerate(spine):
        positions3[node_id] = (0.0, -index * y_step, 0.0)
    branch_index = defaultdict(int)
    for node_id in sorted(node_index, key=lambda value: (depth[value], value)):
        if node_id in spine_set:
            continue
        ancestor = parents.get(node_id)
        while ancestor and ancestor not in spine_set:
            ancestor = parents.get(ancestor)
        anchor = ancestor if ancestor in positions3 else (spine[0] if spine else None)
        ax, ay, az = positions3.get(anchor, (0.0, 0.0, 0.0))
        slot = branch_index[anchor]
        branch_index[anchor] += 1
        angle = slot * 2.399963229728653
        radius = 260.0 + (slot // 6) * 120.0
        positions3[node_id] = (ax + math.cos(angle) * radius, ay, az + math.sin(angle) * radius)
    for node_id, node in node_index.items():
        x, y, z = positions3.get(node_id, (0.0, 0.0, 0.0))
        p = _public(node)
        p.update({"x": x, "y": y, "z": z, "on_layout_spine": node_id in spine_set, "layout_parent_id": parents.get(node_id)})
        projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, 500.0 + len(spine) * y_step)}


_BUILDERS = {
    "atlas": _atlas,
    "map": _map,
    "matrix": _matrix,
    "lifecycle_lanes": _lanes,
    "dependency_flow": _flow,
    "galaxy": _galaxy,
    "role_layers": _layers,
    "dependency_tower": _tower,
    "authority_space": _space,
    "relation_orbits": _orbits,
    "hierarchy_tree": _tree,
    "relation_generations": _generations,
    "component_islands": _islands,
    "relation_shells": _shells,
    "structure_spine": _spine,
}


def build_visual_projection(graph: dict[str, Any], projection_id: str) -> dict[str, Any]:
    if projection_id not in PROJECTIONS:
        raise KeyError(f"Unknown semantics-first visual generator: {projection_id}")
    meta = PROJECTIONS[projection_id]
    nodes = _nodes(graph)
    edges = _edges(graph)
    body = _BUILDERS[meta["style"]](graph, nodes, edges, meta["dimension"])
    return {
        "id": projection_id,
        "title": meta["title"],
        "dimension": meta["dimension"],
        "kind": meta["kind"],
        "visual_style": meta["style"],
        "node_count": len(nodes),
        "edge_count": len(edges),
        "semantic_graph_only": True,
        "layout_semantics": "none; geometry consumes only the already-selected semantic projection graph",
        "inference": False,
        **body,
    }


__all__ = [
    "STYLE_FAMILIES",
    "PROJECTIONS",
    "style_catalog",
    "resolve_visual_style",
    "build_visual_projection",
]
