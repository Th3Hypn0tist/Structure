from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any


PROJECTIONS: dict[str, dict[str, str]] = {
    "atlas_2d": {"title": "Architecture Atlas", "dimension": "2d", "kind": "atlas"},
    "relation_web_2d": {"title": "Relation Web", "dimension": "2d", "kind": "web"},
    "adjacency_matrix_2d": {"title": "Adjacency Matrix", "dimension": "2d", "kind": "matrix"},
    "lifecycle_lanes_2d": {"title": "Lifecycle Lanes", "dimension": "2d", "kind": "lanes"},
    "dependency_flow_2d": {"title": "Dependency Flow", "dimension": "2d", "kind": "flow"},
    "semantic_galaxy_3d": {"title": "Semantic Galaxy", "dimension": "3d", "kind": "galaxy"},
    "role_layers_3d": {"title": "Role Layers", "dimension": "3d", "kind": "layers"},
    "dependency_tower_3d": {"title": "Dependency Tower", "dimension": "3d", "kind": "tower"},
    "authority_space_3d": {"title": "Authority Space", "dimension": "3d", "kind": "authority"},
    "relation_orbits_3d": {"title": "Relation Orbits", "dimension": "3d", "kind": "orbits"},
    "spatial_dependency_3d": {"title": "Spatial Dependency", "dimension": "3d", "kind": "spatial_dependency"},
}

EDGE_DIMENSIONS = ("containment", "relations", "ownership", "authority", "dependencies")


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


def _public_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "name": node.get("name") or node.get("id"),
        "type": node.get("type"),
        "status": node.get("status"),
        "source_role": node.get("source_role") or (node.get("raw") or {}).get("source_role"),
        "source": node.get("source"),
        "kind": node.get("kind"),
    }


def _edge_degree(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    degree = {str(n["id"]): 0 for n in nodes}
    for edge in edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in degree:
            degree[source] += 1
        if target in degree:
            degree[target] += 1
    return degree


def _dependency_depths(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    ids = [str(n["id"]) for n in nodes]
    incoming: dict[str, int] = {nid: 0 for nid in ids}
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
        fallback = (max(depth.values()) if depth else 0) + 1
        for nid, count in incoming.items():
            if count > 0:
                depth[nid] = fallback
    return depth


def _atlas(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        groups[str(node.get("source_role") or "member")].append(node)
    canvas_w = 3600
    margin = 60
    gap = 28
    group_cols = 3
    group_w = int((canvas_w - margin * 2 - gap * (group_cols - 1)) / group_cols)
    y_by_col = [100] * group_cols
    projected, group_boxes = [], []
    for role, members in sorted(groups.items()):
        col = min(range(group_cols), key=lambda c: y_by_col[c])
        x, y = margin + col * (group_w + gap), y_by_col[col]
        card_gap, card_cols = 12, 2 if len(members) > 1 else 1
        inner_w = group_w - 36
        card_w, card_h = int((inner_w - card_gap * (card_cols - 1)) / card_cols), 76
        rows = max(1, math.ceil(len(members) / card_cols))
        group_h = 64 + rows * (card_h + card_gap) + 20
        group_boxes.append({"id": role, "title": role, "x": x, "y": y, "width": group_w, "height": group_h, "count": len(members)})
        for i, node in enumerate(sorted(members, key=lambda n: str(n["id"]))):
            row, c = divmod(i, card_cols)
            p = _public_node(node)
            p.update({"x": x + 18 + c * (card_w + card_gap), "y": y + 52 + row * (card_h + card_gap), "width": card_w, "height": card_h, "group": role})
            projected.append(p)
        y_by_col[col] = y + group_h + gap
    return {"bounds": {"width": canvas_w, "height": max(y_by_col) + 40}, "groups": group_boxes, "nodes": projected, "edges": edges}


def _relation_web(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    degree = _edge_degree(nodes, edges)
    ordered = sorted(nodes, key=lambda n: (-degree[str(n["id"])], str(n["id"])))
    width, height = 2600, 1800
    cx, cy = width / 2, height / 2
    max_degree = max(degree.values(), default=0)
    projected = []
    total = max(1, len(ordered))
    for i, node in enumerate(ordered):
        d = degree[str(node["id"])]
        ring = 0 if max_degree == 0 else max_degree - d
        radius = 180 + ring * 86
        angle = (2 * math.pi * i / total) + ring * 0.37
        p = _public_node(node)
        p.update({"x": cx + math.cos(angle) * radius, "y": cy + math.sin(angle) * radius, "radius": 34 + min(22, d * 2), "degree": d})
        projected.append(p)
    return {"bounds": {"width": width, "height": height}, "nodes": projected, "edges": edges}


def _matrix(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    degree = _edge_degree(nodes, edges)
    ordered = sorted(nodes, key=lambda n: (-degree[str(n["id"])], str(n["id"])))
    ids = [str(n["id"]) for n in ordered]
    index = {nid: i for i, nid in enumerate(ids)}
    cells = []
    for edge in edges:
        source, target = str(edge.get("source", "")), str(edge.get("target", ""))
        if source in index and target in index:
            cells.append({"row": index[source], "col": index[target], "dimension": edge.get("dimension"), "type": edge.get("type"), "id": edge.get("id")})
    return {"order": [_public_node(n) | {"degree": degree[str(n["id"])]} for n in ordered], "cells": cells, "edges": edges, "cell_size": 18, "label_size": 260}


def _lanes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    preferred = ["unlocked", "locked", "validated", "superseded", "deprecated"]
    statuses = sorted({str(n.get("status") or "unspecified") for n in nodes})
    ordered_statuses = [s for s in preferred if s in statuses] + [s for s in statuses if s not in preferred]
    width, margin, lane_gap = 3200, 50, 24
    lane_w = int((width - margin * 2 - lane_gap * max(0, len(ordered_statuses) - 1)) / max(1, len(ordered_statuses)))
    projected, lanes, max_h = [], [], 0
    for li, status in enumerate(ordered_statuses):
        members = sorted([n for n in nodes if str(n.get("status") or "unspecified") == status], key=lambda n: str(n["id"]))
        x, card_h = margin + li * (lane_w + lane_gap), 70
        lane_h = 70 + len(members) * 82
        max_h = max(max_h, lane_h)
        lanes.append({"id": status, "title": status, "x": x, "y": 80, "width": lane_w, "height": lane_h, "count": len(members)})
        for i, node in enumerate(members):
            p = _public_node(node)
            p.update({"x": x + 12, "y": 132 + i * 82, "width": lane_w - 24, "height": card_h, "group": status})
            projected.append(p)
    return {"bounds": {"width": width, "height": max(900, max_h + 160)}, "groups": lanes, "nodes": projected, "edges": edges}


def _dependency_flow(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    depths = _dependency_depths(nodes, edges)
    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_depth[depths[str(node["id"])]].append(node)
    width, margin, layer_gap, card_w, card_h = 3400, 60, 160, 330, 72
    projected, layers, y = [], [], 100
    for depth in sorted(by_depth):
        members = sorted(by_depth[depth], key=lambda n: str(n["id"]))
        cols, gap = max(1, min(8, len(members))), 22
        row_count = max(1, math.ceil(len(members) / cols))
        layer_h = 60 + row_count * (card_h + gap)
        layers.append({"id": str(depth), "title": f"dependency depth {depth}", "x": margin, "y": y, "width": width - margin * 2, "height": layer_h, "count": len(members)})
        usable = width - margin * 2 - 40
        actual_w = min(card_w, int((usable - gap * (cols - 1)) / cols))
        row_width = cols * actual_w + (cols - 1) * gap
        start_x = (width - row_width) / 2
        for i, node in enumerate(members):
            row, col = divmod(i, cols)
            p = _public_node(node)
            p.update({"x": start_x + col * (actual_w + gap), "y": y + 46 + row * (card_h + gap), "width": actual_w, "height": card_h, "depth": depth})
            projected.append(p)
        y += layer_h + layer_gap
    return {"bounds": {"width": width, "height": max(900, y)}, "groups": layers, "nodes": projected, "edges": [e for e in edges if e.get("dimension") == "dependencies"]}


def _fibonacci_sphere(index: int, total: int, radius: float) -> tuple[float, float, float]:
    if total <= 1:
        return 0.0, 0.0, 0.0
    golden = math.pi * (3.0 - math.sqrt(5.0))
    y = 1.0 - (index / float(total - 1)) * 2.0
    r = math.sqrt(max(0.0, 1.0 - y * y))
    theta = golden * index
    return math.cos(theta) * r * radius, y * radius, math.sin(theta) * r * radius


def _semantic_galaxy(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    degree = _edge_degree(nodes, edges)
    ordered = sorted(nodes, key=lambda n: (-degree[str(n["id"])], str(n["id"])))
    radius = max(320.0, 120.0 * math.sqrt(max(1, len(ordered))))
    projected = []
    for i, node in enumerate(ordered):
        x, y, z = _fibonacci_sphere(i, len(ordered), radius)
        p = _public_node(node)
        p.update({"x": x, "y": y, "z": z, "degree": degree[str(node["id"])]})
        projected.append(p)
    return {"nodes": projected, "edges": edges, "extent": radius * 1.35}


def _role_layers(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        groups[str(node.get("source_role") or "member")].append(node)
    projected, layers = [], []
    roles, layer_gap = sorted(groups), 220
    for ri, role in enumerate(roles):
        members = sorted(groups[role], key=lambda n: str(n["id"]))
        y = (ri - (len(roles) - 1) / 2) * layer_gap
        cols = max(1, math.ceil(math.sqrt(len(members))))
        spacing, rows = 150, max(1, math.ceil(len(members) / cols))
        layers.append({"id": role, "title": role, "y": y, "count": len(members)})
        for i, node in enumerate(members):
            row, col = divmod(i, cols)
            p = _public_node(node)
            p.update({"x": (col - (cols - 1) / 2) * spacing, "y": y, "z": (row - (rows - 1) / 2) * spacing, "group": role})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": layers, "extent": max(600, len(roles) * layer_gap)}


def _dependency_tower(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    depths = _dependency_depths(nodes, edges)
    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_depth[depths[str(node["id"])]].append(node)
    projected, layers = [], []
    for depth in sorted(by_depth):
        members = sorted(by_depth[depth], key=lambda n: str(n["id"]))
        y, radius = -depth * 230, 180 + max(0, len(members) - 1) * 14
        layers.append({"id": str(depth), "title": f"depth {depth}", "y": y, "count": len(members)})
        total = max(1, len(members))
        for i, node in enumerate(members):
            angle = 2 * math.pi * i / total
            p = _public_node(node)
            p.update({"x": math.cos(angle) * radius, "y": y, "z": math.sin(angle) * radius, "depth": depth})
            projected.append(p)
    return {"nodes": projected, "edges": [e for e in edges if e.get("dimension") == "dependencies"], "groups": layers, "extent": max(700, len(by_depth) * 260)}


def _authority_space(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    own_in, auth_in, own_out, auth_out = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    for edge in edges:
        source, target = str(edge.get("source", "")), str(edge.get("target", ""))
        if edge.get("dimension") == "ownership":
            own_out[source] += 1; own_in[target] += 1
        elif edge.get("dimension") == "authority":
            auth_out[source] += 1; auth_in[target] += 1
    roles = sorted({str(n.get("source_role") or "member") for n in nodes})
    role_index = {role: i for i, role in enumerate(roles)}
    projected = []
    for i, node in enumerate(nodes):
        nid, role = str(node["id"]), str(node.get("source_role") or "member")
        angle, jitter = (i * 2.399963229728653) % (2 * math.pi), 36 + (i % 7) * 7
        p = _public_node(node)
        p.update({"x": (own_out[nid] - own_in[nid]) * 180 + math.cos(angle) * jitter, "y": (role_index[role] - (len(roles) - 1) / 2) * 170, "z": (auth_out[nid] - auth_in[nid]) * 180 + math.sin(angle) * jitter, "ownership_in": own_in[nid], "ownership_out": own_out[nid], "authority_in": auth_in[nid], "authority_out": auth_out[nid]})
        projected.append(p)
    return {"nodes": projected, "edges": [e for e in edges if e.get("dimension") in ("ownership", "authority")], "extent": 1100}


def _relation_orbits(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    degree = _edge_degree(nodes, edges)
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        d = degree[str(node["id"])]
        buckets[0 if d == 0 else int(math.log2(d)) + 1].append(node)
    projected, groups = [], []
    for bi, bucket in enumerate(sorted(buckets)):
        members = sorted(buckets[bucket], key=lambda n: str(n["id"]))
        radius, y = 160 + bi * 180, (bi - (len(buckets) - 1) / 2) * 95
        groups.append({"id": str(bucket), "title": f"degree orbit {bucket}", "radius": radius, "y": y, "count": len(members)})
        total = max(1, len(members))
        for i, node in enumerate(members):
            angle = 2 * math.pi * i / total + bi * 0.41
            p = _public_node(node)
            p.update({"x": math.cos(angle) * radius, "y": y, "z": math.sin(angle) * radius, "degree": degree[str(node["id"])], "orbit": bucket})
            projected.append(p)
    return {"nodes": projected, "edges": edges, "groups": groups, "extent": 200 + len(buckets) * 200}


def _spatial_edge_role(edge: dict[str, Any]) -> str | None:
    dim = str(edge.get("dimension") or "")
    etype = str(edge.get("type") or "").lower()
    if dim == "containment": return "containment"
    if dim == "dependencies": return "dependency"
    if dim == "authority": return "authority"
    if dim == "relations":
        if "compos" in etype: return "composition"
        if "refer" in etype or "use" in etype: return "reference"
        if "flow" in etype: return "flow"
    return None


def _spatial_dependency(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], context_id: str | None) -> dict[str, Any]:
    by_id = {str(n["id"]): n for n in nodes}
    root_id = context_id if context_id in by_id else None
    if root_id is None:
        masters = [str(n["id"]) for n in nodes if n.get("source_role") == "boundary_master"]
        if len(masters) == 1:
            root_id = masters[0]
    if root_id is None:
        return {"nodes": [], "edges": [], "extent": 900, "requires_root": True, "root_id": None, "forward_depth": 2}

    enabled = {"containment", "dependency", "composition", "authority"}
    outgoing: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
    for edge in edges:
        role = _spatial_edge_role(edge)
        if role in enabled:
            outgoing[str(edge.get("source"))].append((edge, role))

    depth = {root_id: 0}
    queue = deque([root_id])
    selected_edges: list[dict[str, Any]] = []
    seen_edge_ids: set[tuple[str, str, str, str]] = set()
    max_depth = 2
    while queue:
        source = queue.popleft()
        if depth[source] >= max_depth:
            continue
        for edge, role in outgoing.get(source, []):
            target = str(edge.get("target"))
            if target not in by_id:
                continue
            key = (str(edge.get("id") or ""), source, target, role)
            if key not in seen_edge_ids:
                selected_edges.append({**edge, "spatial_role": role})
                seen_edge_ids.add(key)
            nd = depth[source] + 1
            if target not in depth or nd < depth[target]:
                depth[target] = nd
                queue.append(target)

    levels: dict[int, list[str]] = defaultdict(list)
    for nid, d in depth.items(): levels[d].append(nid)
    projected = []
    for d in sorted(levels):
        ids = sorted(levels[d])
        count = max(1, len(ids))
        radius = 0 if d == 0 else 260 + (d - 1) * 230
        y = -d * 180
        for i, nid in enumerate(ids):
            angle = 0 if d == 0 else (2 * math.pi * i / count + d * 0.33)
            p = _public_node(by_id[nid])
            scale = 1.28 if d == 0 else 1.0 if d == 1 else 0.84
            p.update({"x": math.cos(angle) * radius, "y": y, "z": math.sin(angle) * radius, "depth": d, "node_scale": scale, "is_root": d == 0})
            projected.append(p)
    return {"nodes": projected, "edges": selected_edges, "extent": 950, "root_id": root_id, "forward_depth": max_depth, "requires_root": False, "camera": {"type": "perspective", "fov_degrees": 40, "elevation_degrees": 25, "yaw_degrees": 22, "transition_ms": 520}, "preset": "presets/StructureProjector_AIGMos_Spatial_Dependency_Preset_v1.0.json"}


def build_canonical_projection(graph: dict[str, Any], projection_id: str, context_id: str | None = None) -> dict[str, Any]:
    if projection_id not in PROJECTIONS:
        raise KeyError(projection_id)
    nodes, edges, meta = _stable_nodes(graph), _stable_edges(graph), PROJECTIONS[projection_id]
    if projection_id == "atlas_2d": body = _atlas(nodes, edges)
    elif projection_id == "relation_web_2d": body = _relation_web(nodes, edges)
    elif projection_id == "adjacency_matrix_2d": body = _matrix(nodes, edges)
    elif projection_id == "lifecycle_lanes_2d": body = _lanes(nodes, edges)
    elif projection_id == "dependency_flow_2d": body = _dependency_flow(nodes, edges)
    elif projection_id == "semantic_galaxy_3d": body = _semantic_galaxy(nodes, edges)
    elif projection_id == "role_layers_3d": body = _role_layers(nodes, edges)
    elif projection_id == "dependency_tower_3d": body = _dependency_tower(nodes, edges)
    elif projection_id == "authority_space_3d": body = _authority_space(nodes, edges)
    elif projection_id == "relation_orbits_3d": body = _relation_orbits(nodes, edges)
    elif projection_id == "spatial_dependency_3d": body = _spatial_dependency(nodes, edges, context_id)
    else: raise KeyError(projection_id)
    return {"id": projection_id, "title": meta["title"], "dimension": meta["dimension"], "kind": meta["kind"], "node_count": len(nodes), "edge_count": len(edges), "edge_dimensions": list(EDGE_DIMENSIONS), **body}
