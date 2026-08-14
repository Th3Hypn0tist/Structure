from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
import math
from typing import Any

from visual_layouts import LAYOUTS, build_layout


BASE_STYLE_SPECS: dict[str, dict[str, dict[str, Any]]] = {
    "map": {
        "atlas": {
            "label": "Atlas",
            "builder": "atlas_grid",
            "layout": "tiled_grid",
            "description": "Tiled atlas of the selected scope. 2D uses grouped card grids; 3D uses stacked grid planes by projection depth. Never radial.",
        },
        "radial": {
            "label": "Radial map",
            "layout": "radial_shells",
            "description": "Radial distance shells around the selected scope; 3D uses spherical shells.",
        },
        "tree": {
            "label": "Topic tree",
            "layout": "hierarchy_tree",
            "description": "Hierarchy arranged by projection depth and explicit/layout parent relationships.",
        },
    },
    "event": {
        "causal_flow": {
            "label": "Causal flow",
            "builder": "event_causal_flow",
            "layout": "directed_causal_axis",
            "description": "Explicit Event causal path on the main axis with non-causal context and gaps kept outside the causal chain.",
        },
        "mechanism_lanes": {
            "label": "Mechanism lanes",
            "builder": "event_mechanism_lanes",
            "layout": "semantic_lanes",
            "description": "Separate lanes for Event, payload, context, Flow, causal steps, other steps and gaps.",
        },
        "evidence_stack": {
            "label": "Evidence stack",
            "builder": "event_evidence_stack",
            "layout": "evidence_layers",
            "description": "Evidence categories stacked as ordered layers; 3D places each category on its own plane.",
        },
    },
    "dependency": {
        "directional_flow": {
            "label": "Upstream / downstream",
            "builder": "directional",
            "layout": "directed_sides",
            "description": "Selected scope in the center, incoming dependency direction upstream and outgoing direction downstream.",
        },
        "tree": {
            "label": "Dependency tree",
            "layout": "hierarchy_tree",
            "description": "Dependency surface arranged as a depth tree while preserving the selected dependency edges.",
        },
        "shells": {
            "label": "Dependency shells",
            "layout": "distance_shells",
            "description": "Dependency nodes grouped into graph-distance shells around the selected scope.",
        },
    },
    "relation": {
        "network": {
            "label": "Radial relation network",
            "layout": "radial_shells",
            "description": "Relation network arranged as radial/spherical distance shells.",
        },
        "matrix": {
            "label": "Relation matrix",
            "layout": "adjacency_matrix",
            "description": "Adjacency-style matrix with relation cells at source/target intersections.",
        },
        "orbits": {
            "label": "Relation orbits",
            "layout": "connectivity_orbits",
            "description": "Nodes placed on orbits grouped by connectivity degree.",
        },
    },
    "authority": {
        "directional_flow": {
            "label": "Authority direction",
            "builder": "directional",
            "layout": "directed_sides",
            "description": "Authority paths separated by incoming and outgoing direction around the selected scope.",
        },
        "layers": {
            "label": "Authority depth layers",
            "layout": "depth_layers",
            "description": "Authority surface separated into projection-depth layers.",
        },
        "tree": {
            "label": "Authority tree",
            "layout": "hierarchy_tree",
            "description": "Authority surface arranged as a depth tree while preserving authority edges.",
        },
    },
    "ownership": {
        "tree": {
            "label": "Ownership tree",
            "layout": "hierarchy_tree",
            "description": "Ownership surface arranged as a depth tree while preserving ownership edges.",
        },
        "layers": {
            "label": "Ownership depth layers",
            "layout": "depth_layers",
            "description": "Ownership surface separated into projection-depth layers.",
        },
        "islands": {
            "label": "Ownership islands",
            "layout": "connected_components",
            "description": "Disconnected ownership components shown as separate islands.",
        },
    },
    "containment": {
        "tree": {
            "label": "Containment tree",
            "layout": "hierarchy_tree",
            "description": "Containment surface arranged as a depth tree while preserving containment edges.",
        },
        "layers": {
            "label": "Containment depth layers",
            "layout": "depth_layers",
            "description": "Containment surface separated into projection-depth layers.",
        },
        "islands": {
            "label": "Containment islands",
            "layout": "connected_components",
            "description": "Disconnected containment components shown as separate islands.",
        },
    },
}


BUILDERS = {
    "atlas_grid",
    "event_causal_flow",
    "event_mechanism_lanes",
    "event_evidence_stack",
    "directional",
}


def validate_style_specs() -> None:
    custom_layouts = {
        "tiled_grid",
        "directed_causal_axis",
        "semantic_lanes",
        "evidence_layers",
        "directed_sides",
    }
    for base_id, styles in BASE_STYLE_SPECS.items():
        for style_id, spec in styles.items():
            for field in ("label", "layout", "description"):
                if not str(spec.get(field) or "").strip():
                    raise ValueError(f"Projection style {base_id}/{style_id} is missing {field}")
            layout = str(spec["layout"])
            builder = spec.get("builder")
            if builder is not None:
                if builder not in BUILDERS:
                    raise ValueError(f"Projection style {base_id}/{style_id} has unknown builder {builder}")
                if layout not in custom_layouts:
                    raise ValueError(f"Projection style {base_id}/{style_id} custom builder/layout mismatch")
            elif layout not in LAYOUTS:
                raise ValueError(f"Projection style {base_id}/{style_id} has unknown layout {layout}")


validate_style_specs()


PROJECTIONS: dict[str, dict[str, Any]] = {}
for base_id, styles in BASE_STYLE_SPECS.items():
    for style_id, spec in styles.items():
        for dimension in ("2d", "3d"):
            PROJECTIONS[f"base_{base_id}_{style_id}_{dimension}"] = {
                "projection_base": base_id,
                "projection_style": style_id,
                "dimension": dimension,
                **deepcopy(spec),
            }


def style_catalog(base_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": style_id,
            "label": spec["label"],
            "layout": spec["layout"],
            "description": spec["description"],
            "dimensions": ["2d", "3d"],
            "variants": {
                "2d": f"base_{base_id}_{style_id}_2d",
                "3d": f"base_{base_id}_{style_id}_3d",
            },
        }
        for style_id, spec in BASE_STYLE_SPECS.get(base_id, {}).items()
    ]


def resolve_style(base_id: str, style_id: str, dimension: str) -> tuple[str, str, str]:
    styles = BASE_STYLE_SPECS.get(base_id)
    if not styles:
        raise KeyError(f"Unknown projection base: {base_id}")
    style_id = str(style_id or "").strip()
    if style_id not in styles:
        raise ValueError(f"Projection style {style_id} is not compatible with projection base {base_id}")
    dimension = str(dimension or "3d").lower().strip()
    if dimension not in {"2d", "3d"}:
        raise ValueError(f"Unsupported projection dimension: {dimension}")
    return style_id, dimension, f"base_{base_id}_{style_id}_{dimension}"


def _nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [deepcopy(node) for node in graph.get("nodes", []) if isinstance(node, dict) and node.get("id") is not None],
        key=lambda node: str(node.get("id")),
    )


def _edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(edge) for edge in graph.get("edges", []) if isinstance(edge, dict)]


def _public(node: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(node)
    out["id"] = str(node.get("id"))
    out["name"] = str(node.get("name") or node.get("id"))
    return out


def _base_ids(graph: dict[str, Any], nodes: list[dict[str, Any]]) -> set[str]:
    ids = {str(node["id"]) for node in nodes}
    explicit = {str(ref) for ref in graph.get("projection_base_ids", []) if str(ref) in ids}
    if explicit:
        return explicit
    zero = {str(node["id"]) for node in nodes if int(node.get("projection_depth") or 0) == 0}
    return zero or ({str(nodes[0]["id"])} if nodes else set())


def _spread(index: int, total: int, step: float) -> float:
    return (index - (total - 1) / 2.0) * step


def _circle(index: int, total: int, radius: float) -> tuple[float, float]:
    if total <= 1:
        return 0.0, 0.0
    angle = 2.0 * math.pi * index / total
    return math.cos(angle) * radius, math.sin(angle) * radius


def _result(projection_id: str, spec: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": projection_id,
        "title": f"{spec['label']} {spec['dimension'].upper()}",
        "dimension": spec["dimension"],
        "kind": "base_visual",
        "projection_base": spec["projection_base"],
        "projection_style": spec["projection_style"],
        "projection_layout": spec["layout"],
        "projection_style_description": spec["description"],
        "semantic_graph_only": True,
        "inference": False,
        **payload,
    }


def _atlas_grid(graph: dict[str, Any], projection_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _nodes(graph), _edges(graph)
    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_depth[max(0, int(node.get("projection_depth") or 0))].append(node)
    for members in by_depth.values():
        members.sort(key=lambda node: str(node["id"]))
    projected, groups = [], []
    if spec["dimension"] == "2d":
        width, cursor_y = 3600.0, 100.0
        for level, members in sorted(by_depth.items()):
            cols = max(1, min(9, math.ceil(math.sqrt(len(members)))))
            rows = max(1, math.ceil(len(members) / cols))
            card_w, card_h, gap_x, gap_y = 320.0, 84.0, 28.0, 24.0
            start_x = (width - (cols * card_w + max(0, cols - 1) * gap_x)) / 2.0
            groups.append({"id": f"atlas-depth-{level}", "title": f"projection depth {level}", "layout": "grid", "count": len(members)})
            for index, node in enumerate(members):
                row, col = divmod(index, cols)
                p = _public(node)
                p.update({"x": start_x + col * (card_w + gap_x), "y": cursor_y + row * (card_h + gap_y), "z": 0.0, "width": card_w, "height": card_h, "depth": 54.0, "projection_depth": level})
                projected.append(p)
            cursor_y += rows * (card_h + gap_y) + 150.0
        return _result(projection_id, spec, {"nodes": projected, "edges": edges, "groups": groups, "bounds": {"width": width, "height": max(1000.0, cursor_y + 100.0)}})
    plane_gap, max_span = 320.0, 0.0
    for level, members in sorted(by_depth.items()):
        cols = max(1, min(9, math.ceil(math.sqrt(len(members)))))
        rows = max(1, math.ceil(len(members) / cols))
        gap_x, gap_z = 360.0, 190.0
        max_span = max(max_span, max(0.0, (cols - 1) * gap_x), max(0.0, (rows - 1) * gap_z))
        groups.append({"id": f"atlas-depth-{level}", "title": f"projection depth {level}", "layout": "grid_plane", "y": -level * plane_gap, "rows": rows, "columns": cols, "count": len(members)})
        for index, node in enumerate(members):
            row, col = divmod(index, cols)
            p = _public(node)
            p.update({"x": (col - (cols - 1) / 2.0) * gap_x, "y": -level * plane_gap, "z": (row - (rows - 1) / 2.0) * gap_z, "width": 300.0, "height": 82.0, "depth": 58.0, "projection_depth": level})
            projected.append(p)
    return _result(projection_id, spec, {"nodes": projected, "edges": edges, "groups": groups, "extent": max(1000.0, max_span * 0.75 + (max(by_depth, default=0) + 1) * plane_gap)})


def _event_role(node: dict[str, Any], base_ids: set[str]) -> str:
    node_id = str(node.get("id") or "")
    role = str(node.get("projection_role") or "").lower()
    kind = str(node.get("kind") or node.get("type") or "").lower()
    if node.get("unresolved") or "gap" in role or "gap" in kind:
        return "gap"
    if node_id in base_ids or role == "event":
        return "event"
    if role == "payload_field" or "payload" in kind:
        return "payload"
    if role == "causal_step":
        return "causal"
    if role == "flow_step_context":
        return "step_context"
    if role == "flow_context":
        return "flow"
    return "context"


def _causal_depths(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], base_ids: set[str]) -> dict[str, int]:
    ids = {str(node["id"]) for node in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if not bool(edge.get("causal")):
            continue
        source, target = str(edge.get("source") or ""), str(edge.get("target") or "")
        if source in ids and target in ids:
            outgoing[source].append(target)
    depth = {ref: 0 for ref in base_ids}
    queue = deque(sorted(base_ids))
    while queue:
        current = queue.popleft()
        for target in sorted(outgoing.get(current, [])):
            candidate = depth[current] + 1
            if target not in depth or candidate < depth[target]:
                depth[target] = candidate
                queue.append(target)
    return depth


def _event_causal_flow(graph: dict[str, Any], projection_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _nodes(graph), _edges(graph)
    bases = _base_ids(graph, nodes)
    causal_depth = _causal_depths(nodes, edges, bases)
    causal_ids = set(causal_depth)
    projected, groups = [], [{"id": "causal", "title": "Explicit causal path", "count": len(causal_ids)}]
    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    context: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        node_id = str(node["id"])
        if node_id in causal_ids:
            by_depth[causal_depth[node_id]].append(node)
        else:
            context[_event_role(node, bases)].append(node)
    for level, members in sorted(by_depth.items()):
        members.sort(key=lambda node: str(node["id"]))
        for index, node in enumerate(members):
            p = _public(node)
            if spec["dimension"] == "2d":
                p.update({"x": 150.0 + level * 420.0, "y": 650.0 + _spread(index, len(members), 120.0), "z": 0.0, "width": 320.0, "height": 86.0, "depth": 56.0})
            else:
                p.update({"x": level * 360.0, "y": 0.0, "z": _spread(index, len(members), 170.0), "width": 300.0, "height": 82.0, "depth": 64.0})
            p["projection_depth"] = level
            projected.append(p)
    lane_specs = [("payload", -1, "Payload"), ("context", 1, "Context / evidence"), ("flow", 2, "Flow context"), ("step_context", 3, "Non-causal Flow steps"), ("gap", 4, "Gaps")]
    for role, lane, title in lane_specs:
        members = sorted(context.get(role, []), key=lambda node: (int(node.get("projection_depth") or 0), str(node["id"])))
        if not members:
            continue
        groups.append({"id": role, "title": title, "count": len(members)})
        for index, node in enumerate(members):
            p = _public(node)
            source_depth = int(node.get("projection_depth") or 1)
            if spec["dimension"] == "2d":
                p.update({"x": 150.0 + max(0, source_depth - 1) * 300.0 + index * 80.0, "y": 650.0 + lane * 180.0, "z": 0.0, "width": 280.0, "height": 76.0, "depth": 52.0})
            else:
                radius = 300.0 + abs(lane) * 120.0
                y, z = _circle(index, len(members), radius)
                p.update({"x": max(0, source_depth - 1) * 240.0, "y": y + lane * 75.0, "z": z, "width": 260.0, "height": 74.0, "depth": 58.0})
            projected.append(p)
    payload = {"nodes": projected, "edges": edges, "groups": groups}
    if spec["dimension"] == "2d":
        payload["bounds"] = {"width": max(1800.0, 700.0 + max(causal_depth.values(), default=0) * 440.0), "height": max(1500.0, 1000.0 + len(groups) * 180.0)}
    else:
        payload["extent"] = max(1100.0, 600.0 + max(causal_depth.values(), default=0) * 380.0)
    return _result(projection_id, spec, payload)


def _event_mechanism_lanes(graph: dict[str, Any], projection_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _nodes(graph), _edges(graph)
    bases = _base_ids(graph, nodes)
    lane_order = ["event", "payload", "context", "flow", "causal", "step_context", "gap"]
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        buckets[_event_role(node, bases)].append(node)
    projected, groups = [], []
    max_count = 1
    for lane_index, role in enumerate(lane_order):
        members = sorted(buckets.get(role, []), key=lambda node: (int(node.get("projection_depth") or 0), str(node["id"])))
        if not members:
            continue
        max_count = max(max_count, len(members))
        groups.append({"id": role, "title": role.replace("_", " ").title(), "count": len(members)})
        for index, node in enumerate(members):
            p = _public(node)
            if spec["dimension"] == "2d":
                p.update({"x": 120.0 + lane_index * 390.0, "y": 100.0 + index * 112.0, "z": 0.0, "width": 320.0, "height": 82.0, "depth": 54.0})
            else:
                p.update({"x": _spread(index, len(members), 210.0), "y": -lane_index * 260.0, "z": int(node.get("projection_depth") or 0) * 150.0, "width": 290.0, "height": 78.0, "depth": 60.0})
            projected.append(p)
    payload = {"nodes": projected, "edges": edges, "groups": groups}
    if spec["dimension"] == "2d":
        payload["bounds"] = {"width": max(1800.0, 300.0 + len(groups) * 390.0), "height": max(1000.0, 250.0 + max_count * 112.0)}
    else:
        payload["extent"] = max(1100.0, 500.0 + len(groups) * 260.0)
    return _result(projection_id, spec, payload)


def _event_evidence_stack(graph: dict[str, Any], projection_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _nodes(graph), _edges(graph)
    bases = _base_ids(graph, nodes)
    order = ["event", "payload", "context", "flow", "causal", "step_context", "gap"]
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        buckets[_event_role(node, bases)].append(node)
    projected, groups = [], []
    cursor_y = 80.0
    for layer, role in enumerate(order):
        members = sorted(buckets.get(role, []), key=lambda node: str(node["id"]))
        if not members:
            continue
        groups.append({"id": role, "title": role.replace("_", " ").title(), "count": len(members)})
        cols = max(1, min(6, len(members)))
        for index, node in enumerate(members):
            row, col = divmod(index, cols)
            p = _public(node)
            if spec["dimension"] == "2d":
                p.update({"x": 120.0 + col * 340.0, "y": cursor_y + row * 108.0, "z": 0.0, "width": 300.0, "height": 80.0, "depth": 54.0})
            else:
                x, z = _circle(index, len(members), max(180.0, len(members) * 45.0))
                p.update({"x": x, "y": -layer * 260.0, "z": z, "width": 280.0, "height": 76.0, "depth": 58.0})
            projected.append(p)
        cursor_y += math.ceil(len(members) / cols) * 108.0 + 120.0
    payload = {"nodes": projected, "edges": edges, "groups": groups}
    if spec["dimension"] == "2d":
        payload["bounds"] = {"width": 2300.0, "height": max(1000.0, cursor_y + 100.0)}
    else:
        payload["extent"] = max(1000.0, 450.0 + len(groups) * 280.0)
    return _result(projection_id, spec, payload)


def _directional_distances(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], base_ids: set[str]) -> dict[str, tuple[str, int]]:
    ids = {str(node["id"]) for node in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        source, target = str(edge.get("source") or ""), str(edge.get("target") or "")
        if source in ids and target in ids:
            outgoing[source].append(target)
            incoming[target].append(source)
    def bfs(adjacency: dict[str, list[str]]) -> dict[str, int]:
        depth = {ref: 0 for ref in base_ids}
        queue = deque(sorted(base_ids))
        while queue:
            current = queue.popleft()
            for neighbor in sorted(adjacency.get(current, [])):
                candidate = depth[current] + 1
                if neighbor not in depth or candidate < depth[neighbor]:
                    depth[neighbor] = candidate
                    queue.append(neighbor)
        return depth
    downstream, upstream = bfs(outgoing), bfs(incoming)
    result = {}
    for node in nodes:
        node_id = str(node["id"])
        if node_id in base_ids:
            result[node_id] = ("base", 0)
            continue
        up, down = upstream.get(node_id), downstream.get(node_id)
        if up is not None and down is not None:
            result[node_id] = ("both", min(up, down))
        elif up is not None:
            result[node_id] = ("upstream", up)
        elif down is not None:
            result[node_id] = ("downstream", down)
        else:
            result[node_id] = ("disconnected", max(1, int(node.get("projection_depth") or 1)))
    return result


def _directional(graph: dict[str, Any], projection_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _nodes(graph), _edges(graph)
    direction = _directional_distances(nodes, edges, _base_ids(graph, nodes))
    buckets: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        buckets[direction[str(node["id"])]].append(node)
    projected, groups = [], []
    for (kind, depth), members in sorted(buckets.items(), key=lambda item: (item[0][1], item[0][0])):
        members.sort(key=lambda node: str(node["id"]))
        groups.append({"id": f"{kind}-{depth}", "title": f"{kind} {depth}", "count": len(members)})
        sign = -1 if kind == "upstream" else 1 if kind == "downstream" else 0
        x = sign * depth * 390.0 if kind != "disconnected" else (depth + 1) * 390.0
        for index, node in enumerate(members):
            p = _public(node)
            p["direction_role"] = kind
            p["direction_depth"] = depth
            if spec["dimension"] == "2d":
                p.update({"x": 1600.0 + x, "y": 650.0 + _spread(index, len(members), 120.0), "z": 0.0, "width": 310.0, "height": 82.0, "depth": 56.0})
            else:
                y, z = _circle(index, len(members), max(140.0, len(members) * 45.0))
                p.update({"x": x, "y": y, "z": z, "width": 290.0, "height": 78.0, "depth": 60.0})
            projected.append(p)
    max_depth = max((depth for _kind, depth in direction.values()), default=0)
    payload = {"nodes": projected, "edges": edges, "groups": groups}
    if spec["dimension"] == "2d":
        payload["bounds"] = {"width": max(3200.0, 1200.0 + max_depth * 850.0), "height": 1500.0}
    else:
        payload["extent"] = max(1000.0, 650.0 + max_depth * 430.0)
    return _result(projection_id, spec, payload)


def build_projection(graph: dict[str, Any], projection_id: str) -> dict[str, Any]:
    spec = PROJECTIONS.get(projection_id)
    if spec is None:
        raise KeyError(f"Unknown projection generator: {projection_id}")
    builder = spec.get("builder")
    if builder == "atlas_grid":
        return _atlas_grid(graph, projection_id, spec)
    if builder == "event_causal_flow":
        return _event_causal_flow(graph, projection_id, spec)
    if builder == "event_mechanism_lanes":
        return _event_mechanism_lanes(graph, projection_id, spec)
    if builder == "event_evidence_stack":
        return _event_evidence_stack(graph, projection_id, spec)
    if builder == "directional":
        return _directional(graph, projection_id, spec)
    return _result(projection_id, spec, build_layout(graph, spec["layout"], spec["dimension"]))


__all__ = ["BASE_STYLE_SPECS", "PROJECTIONS", "style_catalog", "resolve_style", "validate_style_specs", "build_projection"]
