from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
import math
from typing import Any

from semantic_visual_projections import build_visual_projection


# User-facing projection style names are contracts, not decorative labels.
# Every style declares the geometry it promises. The implementation must match
# that promise in both 2D and 3D.
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
            "generic": "map",
            "layout": "radial_shells",
            "description": "Radial distance shells around the selected scope; 3D uses spherical shells.",
        },
        "tree": {
            "label": "Topic tree",
            "generic": "hierarchy_tree",
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
            "generic": "hierarchy_tree",
            "layout": "hierarchy_tree",
            "description": "Dependency surface arranged as a depth tree while preserving the selected dependency edges.",
        },
        "shells": {
            "label": "Dependency shells",
            "generic": "relation_shells",
            "layout": "distance_shells",
            "description": "Dependency nodes grouped into graph-distance shells around the selected scope.",
        },
    },
    "relation": {
        "network": {
            "label": "Radial relation network",
            "generic": "map",
            "layout": "radial_shells",
            "description": "Relation network arranged as radial/spherical distance shells.",
        },
        "matrix": {
            "label": "Relation matrix",
            "generic": "matrix",
            "layout": "adjacency_matrix",
            "description": "Adjacency-style matrix with relation cells at source/target intersections.",
        },
        "orbits": {
            "label": "Relation orbits",
            "generic": "relation_orbits",
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
            "generic": "role_layers",
            "layout": "depth_layers",
            "description": "Authority surface separated into projection-depth layers.",
        },
        "tree": {
            "label": "Authority tree",
            "generic": "hierarchy_tree",
            "layout": "hierarchy_tree",
            "description": "Authority surface arranged as a depth tree while preserving authority edges.",
        },
    },
    "ownership": {
        "tree": {
            "label": "Ownership tree",
            "generic": "hierarchy_tree",
            "layout": "hierarchy_tree",
            "description": "Ownership surface arranged as a depth tree while preserving ownership edges.",
        },
        "layers": {
            "label": "Ownership depth layers",
            "generic": "role_layers",
            "layout": "depth_layers",
            "description": "Ownership surface separated into projection-depth layers.",
        },
        "islands": {
            "label": "Ownership islands",
            "generic": "component_islands",
            "layout": "connected_components",
            "description": "Disconnected ownership components shown as separate islands.",
        },
    },
    "containment": {
        "tree": {
            "label": "Containment tree",
            "generic": "hierarchy_tree",
            "layout": "hierarchy_tree",
            "description": "Containment surface arranged as a depth tree while preserving containment edges.",
        },
        "layers": {
            "label": "Containment depth layers",
            "generic": "role_layers",
            "layout": "depth_layers",
            "description": "Containment surface separated into projection-depth layers.",
        },
        "islands": {
            "label": "Containment islands",
            "generic": "component_islands",
            "layout": "connected_components",
            "description": "Disconnected containment components shown as separate islands.",
        },
    },
}


_KNOWN_BUILDERS = {
    "atlas_grid",
    "event_causal_flow",
    "event_mechanism_lanes",
    "event_evidence_stack",
    "directional",
}
_KNOWN_GENERIC_LAYOUTS = {
    "map",
    "matrix",
    "hierarchy_tree",
    "relation_shells",
    "relation_orbits",
    "role_layers",
    "component_islands",
}


def validate_style_specs() -> None:
    for base_id, styles in BASE_STYLE_SPECS.items():
        for style_id, spec in styles.items():
            for field in ("label", "layout", "description"):
                if not str(spec.get(field) or "").strip():
                    raise ValueError(f"Projection style {base_id}/{style_id} is missing {field}")
            builder = spec.get("builder")
            generic = spec.get("generic")
            if bool(builder) == bool(generic):
                raise ValueError(f"Projection style {base_id}/{style_id} must declare exactly one implementation")
            if builder and builder not in _KNOWN_BUILDERS:
                raise ValueError(f"Projection style {base_id}/{style_id} has unknown builder {builder}")
            if generic and generic not in _KNOWN_GENERIC_LAYOUTS:
                raise ValueError(f"Projection style {base_id}/{style_id} has unknown generic layout {generic}")


validate_style_specs()


PROJECTIONS: dict[str, dict[str, Any]] = {}
for _base, _styles in BASE_STYLE_SPECS.items():
    for _style_id, _spec in _styles.items():
        for _dimension in ("2d", "3d"):
            PROJECTIONS[f"base_{_base}_{_style_id}_{_dimension}"] = {
                "projection_base": _base,
                "projection_style": _style_id,
                "dimension": _dimension,
                **deepcopy(_spec),
            }


def style_catalog(base_id: str) -> list[dict[str, Any]]:
    styles = BASE_STYLE_SPECS.get(base_id, {})
    return [
        {
            "id": style_id,
            "label": str(spec.get("label") or style_id),
            "layout": str(spec.get("layout") or ""),
            "description": str(spec.get("description") or ""),
            "dimensions": ["2d", "3d"],
            "variants": {
                "2d": f"base_{base_id}_{style_id}_2d",
                "3d": f"base_{base_id}_{style_id}_3d",
            },
        }
        for style_id, spec in styles.items()
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


def _projection_result(
    projection_id: str,
    spec: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    groups: list[dict[str, Any]] | None = None,
    bounds: dict[str, Any] | None = None,
    extent: float | None = None,
) -> dict[str, Any]:
    out = {
        "id": projection_id,
        "title": f"{spec['label']} {spec['dimension'].upper()}",
        "dimension": spec["dimension"],
        "kind": "base_visual",
        "projection_base": spec["projection_base"],
        "projection_style": spec["projection_style"],
        "projection_layout": spec.get("layout"),
        "projection_style_description": spec.get("description"),
        "semantic_graph_only": True,
        "inference": False,
        "nodes": nodes,
        "edges": edges,
        "groups": groups or [],
    }
    if bounds is not None:
        out["bounds"] = bounds
    if extent is not None:
        out["extent"] = extent
    return out


def _atlas_grid(graph: dict[str, Any], projection_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Atlas is a tiled index, never a radial/orbit layout.

    2D: each projection-depth group is a card matrix.
    3D: the same matrices become stacked X/Z planes along Y.
    """
    nodes, edges = _nodes(graph), _edges(graph)
    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_depth[max(0, int(node.get("projection_depth") or 0))].append(node)
    for members in by_depth.values():
        members.sort(key=lambda node: str(node["id"]))

    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    if spec["dimension"] == "2d":
        width = 3600.0
        cursor_y = 100.0
        for level in sorted(by_depth):
            members = by_depth[level]
            cols = max(1, min(9, math.ceil(math.sqrt(len(members)))))
            rows = max(1, math.ceil(len(members) / cols))
            card_w, card_h, gap_x, gap_y = 320.0, 84.0, 28.0, 24.0
            grid_w = cols * card_w + max(0, cols - 1) * gap_x
            start_x = (width - grid_w) / 2.0
            groups.append({
                "id": f"atlas-depth-{level}",
                "title": f"projection depth {level}",
                "layout": "grid",
                "count": len(members),
            })
            for index, node in enumerate(members):
                row, col = divmod(index, cols)
                p = _public(node)
                p.update({
                    "x": start_x + col * (card_w + gap_x),
                    "y": cursor_y + row * (card_h + gap_y),
                    "z": 0.0,
                    "width": card_w,
                    "height": card_h,
                    "depth": 54.0,
                    "projection_depth": level,
                })
                projected.append(p)
            cursor_y += rows * (card_h + gap_y) + 150.0
        return _projection_result(
            projection_id,
            spec,
            projected,
            edges,
            groups=groups,
            bounds={"width": width, "height": max(1000.0, cursor_y + 100.0)},
        )

    plane_gap = 320.0
    max_span = 0.0
    for level in sorted(by_depth):
        members = by_depth[level]
        cols = max(1, min(9, math.ceil(math.sqrt(len(members)))))
        rows = max(1, math.ceil(len(members) / cols))
        gap_x, gap_z = 360.0, 190.0
        span_x = max(0.0, (cols - 1) * gap_x)
        span_z = max(0.0, (rows - 1) * gap_z)
        max_span = max(max_span, span_x, span_z)
        groups.append({
            "id": f"atlas-depth-{level}",
            "title": f"projection depth {level}",
            "layout": "grid_plane",
            "y": -level * plane_gap,
            "rows": rows,
            "columns": cols,
            "count": len(members),
        })
        for index, node in enumerate(members):
            row, col = divmod(index, cols)
            p = _public(node)
            p.update({
                "x": (col - (cols - 1) / 2.0) * gap_x,
                "y": -level * plane_gap,
                "z": (row - (rows - 1) / 2.0) * gap_z,
                "width": 300.0,
                "height": 82.0,
                "depth": 58.0,
                "projection_depth": level,
            })
            projected.append(p)
    return _projection_result(
        projection_id,
        spec,
        projected,
        edges,
        groups=groups,
        extent=max(1000.0, max_span * 0.75 + (max(by_depth, default=0) + 1) * plane_gap),
    )


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
    if role in {"behavior_owner", "topic_context", "mechanism_operation", "reference_evidence"}:
        return "context"
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
        source = queue.popleft()
        for target in sorted(outgoing.get(source, [])):
            candidate = depth[source] + 1
            if target not in depth or candidate < depth[target]:
                depth[target] = candidate
                queue.append(target)
    return depth


def _event_causal_flow(graph: dict[str, Any], projection_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _nodes(graph), _edges(graph)
    bases = _base_ids(graph, nodes)
    causal_depth = _causal_depths(nodes, edges, bases)
    causal_nodes = [node for node in nodes if str(node["id"]) in causal_depth]
    context_by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        if str(node["id"]) in causal_depth:
            continue
        context_by_role[_event_role(node, bases)].append(node)
    projected: list[dict[str, Any]] = []
    dimension = spec["dimension"]

    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in causal_nodes:
        by_depth[causal_depth[str(node["id"])]].append(node)
    for depth in sorted(by_depth):
        members = sorted(by_depth[depth], key=lambda node: str(node["id"]))
        for index, node in enumerate(members):
            p = _public(node)
            if dimension == "2d":
                p.update({"x": 150.0 + depth * 420.0, "y": 650.0 + _spread(index, len(members), 120.0), "width": 320.0, "height": 86.0, "depth": 56.0})
            else:
                p.update({"x": depth * 360.0, "y": 0.0, "z": _spread(index, len(members), 170.0), "width": 300.0, "height": 82.0, "depth": 64.0})
            p["projection_depth"] = depth
            projected.append(p)

    lane_specs = [
        ("payload", -1, "Payload"),
        ("context", 1, "Context / evidence"),
        ("flow", 2, "Flow context"),
        ("step_context", 3, "Non-causal Flow steps"),
        ("gap", 4, "Gaps"),
    ]
    groups = [{"id": "causal", "title": "Explicit causal path", "count": len(causal_nodes)}]
    max_items = 1
    for role, lane, title in lane_specs:
        members = sorted(context_by_role.get(role, []), key=lambda node: (int(node.get("projection_depth") or 0), str(node["id"])))
        if not members:
            continue
        groups.append({"id": role, "title": title, "count": len(members)})
        max_items = max(max_items, len(members))
        for index, node in enumerate(members):
            p = _public(node)
            source_depth = int(node.get("projection_depth") or 1)
            if dimension == "2d":
                y = 650.0 + lane * 180.0
                p.update({"x": 150.0 + max(0, source_depth - 1) * 300.0 + index * 80.0, "y": y, "width": 280.0, "height": 76.0, "depth": 52.0})
            else:
                ring_radius = 300.0 + abs(lane) * 120.0
                ry, rz = _circle(index, len(members), ring_radius)
                p.update({"x": max(0, source_depth - 1) * 240.0, "y": ry + lane * 75.0, "z": rz, "width": 260.0, "height": 74.0, "depth": 58.0})
            projected.append(p)

    if dimension == "2d":
        max_depth = max(causal_depth.values(), default=0)
        return _projection_result(projection_id, spec, projected, edges, groups=groups, bounds={"width": max(1800.0, 700.0 + max_depth * 440.0), "height": max(1500.0, 1000.0 + len([g for g in groups if g['id'] != 'causal']) * 180.0)})
    return _projection_result(projection_id, spec, projected, edges, groups=groups, extent=max(1100.0, 600.0 + max(causal_depth.values(), default=0) * 380.0))


def _event_mechanism_lanes(graph: dict[str, Any], projection_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _nodes(graph), _edges(graph)
    bases = _base_ids(graph, nodes)
    lanes = ["event", "payload", "context", "flow", "causal", "step_context", "gap"]
    labels = {
        "event": "Event",
        "payload": "Payload",
        "context": "Owner / Topic / Operations / Evidence",
        "flow": "Flows",
        "causal": "Causal steps",
        "step_context": "Other Flow steps",
        "gap": "Gaps",
    }
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        buckets[_event_role(node, bases)].append(node)
    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    dimension = spec["dimension"]
    max_count = 1
    for lane_index, role in enumerate(lanes):
        members = sorted(buckets.get(role, []), key=lambda node: (int(node.get("projection_depth") or 0), str(node["id"])))
        if not members:
            continue
        max_count = max(max_count, len(members))
        groups.append({"id": role, "title": labels[role], "count": len(members)})
        for index, node in enumerate(members):
            p = _public(node)
            if dimension == "2d":
                p.update({"x": 120.0 + lane_index * 390.0, "y": 100.0 + index * 112.0, "width": 320.0, "height": 82.0, "depth": 54.0})
            else:
                p.update({"x": _spread(index, len(members), 210.0), "y": -lane_index * 260.0, "z": int(node.get("projection_depth") or 0) * 150.0, "width": 290.0, "height": 78.0, "depth": 60.0})
            projected.append(p)
    if dimension == "2d":
        return _projection_result(projection_id, spec, projected, edges, groups=groups, bounds={"width": max(1800.0, 300.0 + len(groups) * 390.0), "height": max(1000.0, 250.0 + max_count * 112.0)})
    return _projection_result(projection_id, spec, projected, edges, groups=groups, extent=max(1100.0, 500.0 + len(groups) * 260.0))


def _event_evidence_stack(graph: dict[str, Any], projection_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _nodes(graph), _edges(graph)
    bases = _base_ids(graph, nodes)
    order = ["event", "payload", "context", "flow", "causal", "step_context", "gap"]
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        buckets[_event_role(node, bases)].append(node)
    projected: list[dict[str, Any]] = []
    groups = []
    dimension = spec["dimension"]
    y = 80.0
    for layer, role in enumerate(order):
        members = sorted(buckets.get(role, []), key=lambda node: str(node["id"]))
        if not members:
            continue
        groups.append({"id": role, "title": role.replace("_", " ").title(), "count": len(members)})
        cols = max(1, min(6, len(members)))
        for index, node in enumerate(members):
            row, col = divmod(index, cols)
            p = _public(node)
            if dimension == "2d":
                p.update({"x": 120.0 + col * 340.0, "y": y + row * 108.0, "width": 300.0, "height": 80.0, "depth": 54.0})
            else:
                px, pz = _circle(index, len(members), max(180.0, len(members) * 45.0))
                p.update({"x": px, "y": -layer * 260.0, "z": pz, "width": 280.0, "height": 76.0, "depth": 58.0})
            projected.append(p)
        y += math.ceil(len(members) / cols) * 108.0 + 120.0
    if dimension == "2d":
        return _projection_result(projection_id, spec, projected, edges, groups=groups, bounds={"width": 2300.0, "height": max(1000.0, y + 100.0)})
    return _projection_result(projection_id, spec, projected, edges, groups=groups, extent=max(1000.0, 450.0 + len(groups) * 280.0))


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

    downstream = bfs(outgoing)
    upstream = bfs(incoming)
    result: dict[str, tuple[str, int]] = {}
    for node_id in ids:
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
            result[node_id] = ("disconnected", int(next((n.get("projection_depth") for n in nodes if str(n["id"]) == node_id), 1) or 1))
    return result


def _directional(graph: dict[str, Any], projection_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _nodes(graph), _edges(graph)
    bases = _base_ids(graph, nodes)
    direction = _directional_distances(nodes, edges, bases)
    buckets: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        buckets[direction[str(node["id"])]].append(node)
    projected: list[dict[str, Any]] = []
    groups = []
    dimension = spec["dimension"]
    for (kind, depth), members in sorted(buckets.items(), key=lambda item: ({"upstream": -1, "base": 0, "both": 0, "downstream": 1, "disconnected": 2}.get(item[0][0], 2) * item[0][1], item[0][0])):
        members = sorted(members, key=lambda node: str(node["id"]))
        groups.append({"id": f"{kind}-{depth}", "title": f"{kind} {depth}", "count": len(members)})
        sign = -1 if kind == "upstream" else 1 if kind == "downstream" else 0
        x = sign * depth * 390.0
        if kind == "disconnected":
            x = (depth + 1) * 390.0
        for index, node in enumerate(members):
            p = _public(node)
            p["direction_role"] = kind
            p["direction_depth"] = depth
            if dimension == "2d":
                p.update({"x": 1600.0 + x, "y": 650.0 + _spread(index, len(members), 120.0), "width": 310.0, "height": 82.0, "depth": 56.0})
            else:
                py, pz = _circle(index, len(members), max(140.0, len(members) * 45.0))
                p.update({"x": x, "y": py, "z": pz, "width": 290.0, "height": 78.0, "depth": 60.0})
            projected.append(p)
    max_depth = max((depth for _kind, depth in direction.values()), default=0)
    if dimension == "2d":
        return _projection_result(projection_id, spec, projected, edges, groups=groups, bounds={"width": max(3200.0, 1200.0 + max_depth * 850.0), "height": 1500.0})
    return _projection_result(projection_id, spec, projected, edges, groups=groups, extent=max(1000.0, 650.0 + max_depth * 430.0))


def build_projection(graph: dict[str, Any], projection_id: str) -> dict[str, Any]:
    spec = PROJECTIONS.get(projection_id)
    if spec is None:
        raise KeyError(f"Unknown projection-base visual generator: {projection_id}")
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
    generic = str(spec.get("generic") or "atlas")
    projection = build_visual_projection(graph, f"semantic_{generic}_{spec['dimension']}")
    projection["id"] = projection_id
    projection["title"] = f"{spec['label']} {spec['dimension'].upper()}"
    projection["kind"] = "base_visual"
    projection["projection_base"] = spec["projection_base"]
    projection["projection_style"] = spec["projection_style"]
    projection["projection_layout"] = spec.get("layout")
    projection["projection_style_description"] = spec.get("description")
    return projection


__all__ = [
    "BASE_STYLE_SPECS",
    "PROJECTIONS",
    "style_catalog",
    "resolve_style",
    "validate_style_specs",
    "build_projection",
]
