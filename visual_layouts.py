from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
import math
from typing import Any


LAYOUTS = {
    "radial_shells",
    "adjacency_matrix",
    "hierarchy_tree",
    "distance_shells",
    "connectivity_orbits",
    "depth_layers",
    "connected_components",
}


def _nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [deepcopy(node) for node in graph.get("nodes", []) if isinstance(node, dict) and node.get("id") is not None],
        key=lambda node: str(node.get("id")),
    )


def _edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(edge) for edge in graph.get("edges", []) if isinstance(edge, dict)]


def _ids(nodes: list[dict[str, Any]]) -> set[str]:
    return {str(node["id"]) for node in nodes}


def _public(node: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(node)
    out["id"] = str(node.get("id"))
    out["name"] = str(node.get("name") or node.get("id"))
    return out


def _adjacency(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, list[str]]:
    ids = _ids(nodes)
    out: dict[str, set[str]] = {node_id: set() for node_id in ids}
    for edge in edges:
        source, target = str(edge.get("source") or ""), str(edge.get("target") or "")
        if source in ids and target in ids:
            out[source].add(target)
            out[target].add(source)
    return {node_id: sorted(values) for node_id, values in out.items()}


def _degree(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    adjacency = _adjacency(nodes, edges)
    return {node_id: len(values) for node_id, values in adjacency.items()}


def _base_ids(graph: dict[str, Any], nodes: list[dict[str, Any]]) -> set[str]:
    ids = _ids(nodes)
    explicit = {str(ref) for ref in graph.get("projection_base_ids", []) if str(ref) in ids}
    if explicit:
        return explicit
    depth_zero = {str(node["id"]) for node in nodes if int(node.get("projection_depth") or 0) == 0}
    return depth_zero or ({str(nodes[0]["id"])} if nodes else set())


def _depths(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    depth: dict[str, int] = {}
    for node in nodes:
        raw = node.get("projection_depth")
        if isinstance(raw, int) and raw >= 0:
            depth[str(node["id"])] = raw
    adjacency = _adjacency(nodes, edges)
    queue = deque()
    for ref in sorted(_base_ids(graph, nodes)):
        depth[ref] = 0
        queue.append(ref)
    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, []):
            candidate = depth[current] + 1
            if neighbor not in depth or candidate < depth[neighbor]:
                depth[neighbor] = candidate
                queue.append(neighbor)
    fallback = max(depth.values(), default=-1) + 1
    for node in nodes:
        depth.setdefault(str(node["id"]), fallback)
    return depth


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
    for members in out.values():
        members.sort(key=lambda node: str(node["id"]))
    return out


def _radial_shells(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    depth = _depths(graph, nodes, edges)
    degree = _degree(nodes, edges)
    groups, projected = [], []
    by_depth = _by_depth(nodes, depth)
    if dimension == "2d":
        cx, cy = 1600.0, 1200.0
        for level, members in sorted(by_depth.items()):
            members.sort(key=lambda node: (-degree[str(node["id"])], str(node["id"])))
            radius = 0.0 if level == 0 and len(members) == 1 else 180.0 + level * 260.0
            groups.append({"id": f"shell-{level}", "title": f"distance {level}", "radius": radius, "count": len(members)})
            for index, node in enumerate(members):
                x, y = _circle(index, len(members), radius)
                p = _public(node)
                p.update({"x": cx + x, "y": cy + y, "z": 0.0, "radius": 30 + min(20, degree[str(node["id"])] * 2), "projection_depth": level})
                projected.append(p)
        return {"nodes": projected, "edges": edges, "groups": groups, "bounds": {"width": 3200.0, "height": 2400.0}}
    for level, members in sorted(by_depth.items()):
        radius = 0.0 if level == 0 and len(members) == 1 else 160.0 + level * 300.0
        groups.append({"id": f"shell-{level}", "title": f"distance {level}", "radius": radius, "count": len(members)})
        for index, node in enumerate(members):
            x, y, z = _sphere(index, len(members), radius)
            p = _public(node)
            p.update({"x": x, "y": y, "z": z, "projection_depth": level})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, 300.0 + max(by_depth, default=0) * 340.0)}


def _adjacency_matrix(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    degree = _degree(nodes, edges)
    ordered = sorted(nodes, key=lambda node: (-degree[str(node["id"])], str(node["id"])))
    index = {str(node["id"]): i for i, node in enumerate(ordered)}
    spacing = 74.0
    center = (len(ordered) - 1) * spacing / 2.0
    projected, matrix_edges = [], []
    for i, node in enumerate(ordered):
        p = _public(node)
        if dimension == "2d":
            p.update({"x": 260.0 + i * spacing, "y": 260.0 + i * spacing, "z": 0.0, "width": 64.0, "height": 64.0})
        else:
            p.update({"x": i * spacing - center, "y": -320.0, "z": i * spacing - center})
        projected.append(p)
    for edge_index, edge in enumerate(edges):
        source, target = str(edge.get("source") or ""), str(edge.get("target") or "")
        if source not in index or target not in index:
            continue
        cell_id = f"matrix:{edge.get('id') or edge_index}:{source}:{target}"
        cell = {
            "id": cell_id,
            "name": str(edge.get("type") or edge.get("relation_type") or edge.get("dimension") or "relation"),
            "type": "relation_cell",
            "kind": "relation_cell",
            "relation_source": source,
            "relation_target": target,
            "relation_dimension": edge.get("dimension"),
        }
        if dimension == "2d":
            cell.update({"x": 260.0 + index[source] * spacing, "y": 260.0 + index[target] * spacing, "z": 0.0, "width": 38.0, "height": 38.0})
        else:
            cell.update({"x": index[source] * spacing - center, "y": 0.0, "z": index[target] * spacing - center})
        projected.append(cell)
        matrix_edges.extend([
            {"id": f"matrix-source:{edge_index}", "source": source, "target": cell_id, "dimension": edge.get("dimension"), "type": edge.get("type")},
            {"id": f"matrix-target:{edge_index}", "source": cell_id, "target": target, "dimension": edge.get("dimension"), "type": edge.get("type")},
        ])
    size = max(1000.0, 520.0 + len(ordered) * spacing)
    return {"nodes": projected, "edges": matrix_edges, "groups": [], **({"bounds": {"width": size, "height": size}} if dimension == "2d" else {"extent": max(900.0, center * 1.35 + 500.0)})}


def _layout_parents(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], depth: dict[str, int]) -> dict[str, str | None]:
    ids = _ids(nodes)
    adjacency = _adjacency(nodes, edges)
    parent: dict[str, str | None] = {}
    for node in nodes:
        node_id = str(node["id"])
        explicit = node.get("projection_parent_id")
        if explicit is not None and str(explicit) in ids:
            parent[node_id] = str(explicit)
        elif depth[node_id] == 0:
            parent[node_id] = None
        else:
            candidates = [ref for ref in adjacency.get(node_id, []) if depth.get(ref) == depth[node_id] - 1]
            parent[node_id] = min(candidates) if candidates else None
    return parent


def _hierarchy_tree(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    depth = _depths(graph, nodes, edges)
    parent = _layout_parents(graph, nodes, edges, depth)
    by_depth = _by_depth(nodes, depth)
    projected, groups = [], []
    if dimension == "2d":
        width = 3600.0
        for level, members in sorted(by_depth.items()):
            step = width / (len(members) + 1)
            groups.append({"id": f"tree-{level}", "title": f"depth {level}", "count": len(members)})
            for index, node in enumerate(members, start=1):
                p = _public(node)
                p.update({"x": index * step - 150.0, "y": 100.0 + level * 190.0, "z": 0.0, "width": 300.0, "height": 84.0, "layout_parent_id": parent[str(node["id"])], "projection_depth": level})
                projected.append(p)
        return {"nodes": projected, "edges": edges, "groups": groups, "bounds": {"width": width, "height": max(900.0, 300.0 + max(by_depth, default=0) * 200.0)}}
    for level, members in sorted(by_depth.items()):
        cols = max(1, math.ceil(math.sqrt(len(members))))
        rows = max(1, math.ceil(len(members) / cols))
        groups.append({"id": f"tree-{level}", "title": f"depth {level}", "count": len(members)})
        for index, node in enumerate(members):
            row, col = divmod(index, cols)
            p = _public(node)
            p.update({"x": (col - (cols - 1) / 2.0) * 330.0, "y": -level * 300.0, "z": (row - (rows - 1) / 2.0) * 190.0, "layout_parent_id": parent[str(node["id"])], "projection_depth": level})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, 400.0 + max(by_depth, default=0) * 340.0)}


def _connectivity_orbits(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    degree = _degree(nodes, edges)
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        d = degree[str(node["id"])]
        buckets[0 if d == 0 else int(math.log2(d)) + 1].append(node)
    projected, groups = [], []
    for orbit_index, bucket in enumerate(sorted(buckets)):
        members = sorted(buckets[bucket], key=lambda node: str(node["id"]))
        radius = 170.0 + orbit_index * 240.0
        groups.append({"id": f"orbit-{bucket}", "title": f"connectivity orbit {bucket}", "count": len(members)})
        for index, node in enumerate(members):
            x, z = _circle(index, len(members), radius)
            p = _public(node)
            if dimension == "2d":
                p.update({"x": 1600.0 + x, "y": 1200.0 + z, "z": 0.0, "degree": degree[str(node["id"])]})
            else:
                p.update({"x": x, "y": (orbit_index - (len(buckets) - 1) / 2.0) * 130.0, "z": z, "degree": degree[str(node["id"])]})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, **({"bounds": {"width": 3200.0, "height": 2400.0}} if dimension == "2d" else {"extent": 450.0 + len(buckets) * 280.0})}


def _depth_layers(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    depth = _depths(graph, nodes, edges)
    by_depth = _by_depth(nodes, depth)
    projected, groups = [], []
    if dimension == "2d":
        for column, (level, members) in enumerate(sorted(by_depth.items())):
            groups.append({"id": f"layer-{level}", "title": f"depth {level}", "count": len(members)})
            for row, node in enumerate(members):
                p = _public(node)
                p.update({"x": 100.0 + column * 420.0, "y": 100.0 + row * 110.0, "z": 0.0, "width": 330.0, "height": 84.0, "projection_depth": level})
                projected.append(p)
        return {"nodes": projected, "edges": edges, "groups": groups, "bounds": {"width": max(1400.0, 300.0 + len(by_depth) * 420.0), "height": max(900.0, 260.0 + max((len(v) for v in by_depth.values()), default=1) * 110.0)}}
    for level, members in sorted(by_depth.items()):
        cols = max(1, math.ceil(math.sqrt(len(members))))
        rows = max(1, math.ceil(len(members) / cols))
        groups.append({"id": f"layer-{level}", "title": f"depth {level}", "count": len(members)})
        for index, node in enumerate(members):
            row, col = divmod(index, cols)
            p = _public(node)
            p.update({"x": (col - (cols - 1) / 2.0) * 320.0, "y": -level * 300.0, "z": (row - (rows - 1) / 2.0) * 190.0, "projection_depth": level})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(900.0, 400.0 + max(by_depth, default=0) * 340.0)}


def _components(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[str]]:
    adjacency = _adjacency(nodes, edges)
    unseen = set(adjacency)
    components: list[list[str]] = []
    while unseen:
        seed = min(unseen)
        unseen.remove(seed)
        queue = deque([seed])
        component = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in adjacency.get(current, []):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    return sorted(components, key=lambda values: (-len(values), values[0] if values else ""))


def _connected_components(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    components = _components(nodes, edges)
    node_index = {str(node["id"]): node for node in nodes}
    projected, groups = [], []
    if dimension == "2d":
        cursor_x, cursor_y, row_h = 80.0, 80.0, 0.0
        width = 3600.0
        for component_index, component in enumerate(components):
            cols = max(1, min(5, math.ceil(math.sqrt(len(component)))))
            rows = max(1, math.ceil(len(component) / cols))
            island_w, island_h = 60.0 + cols * 280.0, 80.0 + rows * 104.0
            if cursor_x + island_w > width - 80.0 and cursor_x > 80.0:
                cursor_x = 80.0
                cursor_y += row_h + 100.0
                row_h = 0.0
            groups.append({"id": f"component-{component_index}", "title": f"component {component_index + 1}", "count": len(component)})
            for index, node_id in enumerate(component):
                row, col = divmod(index, cols)
                p = _public(node_index[node_id])
                p.update({"x": cursor_x + 30.0 + col * 280.0, "y": cursor_y + 55.0 + row * 104.0, "z": 0.0, "width": 250.0, "height": 82.0, "component": component_index})
                projected.append(p)
            cursor_x += island_w + 100.0
            row_h = max(row_h, island_h)
        return {"nodes": projected, "edges": edges, "groups": groups, "bounds": {"width": width, "height": max(900.0, cursor_y + row_h + 120.0)}}
    cluster_gap = 900.0
    for component_index, component in enumerate(components):
        center_x = (component_index - (len(components) - 1) / 2.0) * cluster_gap
        radius = max(160.0, 65.0 * math.sqrt(len(component)))
        groups.append({"id": f"component-{component_index}", "title": f"component {component_index + 1}", "count": len(component)})
        for index, node_id in enumerate(component):
            x, y, z = _sphere(index, len(component), radius)
            p = _public(node_index[node_id])
            p.update({"x": center_x + x, "y": y, "z": z, "component": component_index})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": max(1000.0, 500.0 + len(components) * 480.0)}


def build_layout(graph: dict[str, Any], layout: str, dimension: str) -> dict[str, Any]:
    if layout not in LAYOUTS:
        raise KeyError(f"Unknown visual layout: {layout}")
    if dimension not in {"2d", "3d"}:
        raise ValueError(f"Unsupported visual dimension: {dimension}")
    nodes, edges = _nodes(graph), _edges(graph)
    if layout in {"radial_shells", "distance_shells"}:
        return _radial_shells(graph, nodes, edges, dimension)
    if layout == "adjacency_matrix":
        return _adjacency_matrix(graph, nodes, edges, dimension)
    if layout == "hierarchy_tree":
        return _hierarchy_tree(graph, nodes, edges, dimension)
    if layout == "connectivity_orbits":
        return _connectivity_orbits(graph, nodes, edges, dimension)
    if layout == "depth_layers":
        return _depth_layers(graph, nodes, edges, dimension)
    if layout == "connected_components":
        return _connected_components(graph, nodes, edges, dimension)
    raise AssertionError(layout)


__all__ = ["LAYOUTS", "build_layout"]
