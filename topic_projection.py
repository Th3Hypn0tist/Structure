from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math
from typing import Any


PROJECTION_BASE = {
    "id": "topic",
    "label": "Topic",
    "scope_types": ["all", "topic"],
    "default_style": "atlas",
    "question": "What belongs to the selected Topic scope?",
}

TOPIC_STYLES: dict[str, dict[str, Any]] = {
    "atlas": {
        "label": "Atlas",
        "layout": "tiled_grid",
        "description": "Topic members arranged as a tiled grid. 3D stacks projection-depth grids on separate planes.",
        "dimensions": ["2d", "3d"],
    },
}

SCOPE_STYLES: dict[str, dict[str, Any]] = {
    "semantic_roles": {
        "label": "Semantic roles",
        "description": "Selected/base = blue, related = silver, unresolved/gaps = red.",
    },
    "depth": {
        "label": "Depth",
        "description": "Even projection depth = blue, odd projection depth = silver; unresolved/gaps stay red.",
    },
    "monochrome": {
        "label": "Monochrome",
        "description": "Neutral silver nodes; unresolved/gaps stay red.",
    },
}

PROJECTIONS = {
    f"topic_atlas_{dimension}": {
        "projection_base": "topic",
        "projection_style": "atlas",
        "dimension": dimension,
        **deepcopy(TOPIC_STYLES["atlas"]),
    }
    for dimension in ("2d", "3d")
}


def projection_base_catalog() -> list[dict[str, Any]]:
    return [{**deepcopy(PROJECTION_BASE), "styles": ["atlas"]}]


def projection_style_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": style_id,
            **deepcopy(spec),
            "projection_bases": ["topic"],
            "variants": {dimension: f"topic_{style_id}_{dimension}" for dimension in spec["dimensions"]},
        }
        for style_id, spec in TOPIC_STYLES.items()
    ]


def projection_styles_by_base() -> dict[str, list[dict[str, Any]]]:
    return {"topic": projection_style_catalog()}


def scope_style_catalog() -> list[dict[str, Any]]:
    return [{"id": style_id, **deepcopy(spec)} for style_id, spec in SCOPE_STYLES.items()]


def normalize_projection_base(value: Any) -> str:
    base = str(value or "topic").strip()
    if base != "topic":
        raise KeyError(f"Unknown projection base: {base}. Structure currently supports Topic only.")
    return base


def resolve_projection_style(style: Any, dimension: Any) -> tuple[str, str, str]:
    style_id = str(style or "atlas").strip()
    if style_id not in TOPIC_STYLES:
        raise KeyError(f"Unknown Topic projection style: {style_id}")
    dimension_id = str(dimension or "3d").lower().strip()
    if dimension_id not in TOPIC_STYLES[style_id]["dimensions"]:
        raise ValueError(f"Unsupported Topic projection dimension: {dimension_id}")
    return style_id, dimension_id, f"topic_{style_id}_{dimension_id}"


def normalize_scope_style(value: Any) -> str:
    style_id = str(value or "semantic_roles").strip()
    if style_id not in SCOPE_STYLES:
        raise KeyError(f"Unknown scope style: {style_id}")
    return style_id


def apply_scope_style(graph: dict[str, Any], scope_style: str) -> dict[str, Any]:
    style_id = normalize_scope_style(scope_style)
    out = deepcopy(graph)
    base_ids = {str(ref) for ref in out.get("projection_base_ids", [])}
    for node in out.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        kind = str(node.get("kind") or node.get("type") or "").lower()
        depth = max(0, int(node.get("projection_depth") or 0))
        if node.get("unresolved") or "gap" in kind:
            role, color = "gap", "#FF176B"
        elif node_id in base_ids or depth == 0:
            role = "base"
            if style_id == "monochrome":
                color = "#AAB2C2"
            elif style_id == "depth":
                color = "#087CFF" if depth % 2 == 0 else "#AAB2C2"
            else:
                color = "#087CFF"
        else:
            role = "related"
            if style_id == "depth":
                color = "#087CFF" if depth % 2 == 0 else "#AAB2C2"
            else:
                color = "#AAB2C2"
        node["scope_style"] = style_id
        node["scope_role"] = role
        node["scope_color"] = color
    out["scope_style"] = style_id
    return out


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


def build_topic_visual(graph: dict[str, Any], generator: str) -> dict[str, Any]:
    spec = PROJECTIONS.get(generator)
    if spec is None:
        raise KeyError(f"Unknown Topic projection generator: {generator}")
    if spec["projection_style"] != "atlas":
        raise KeyError(f"Unsupported Topic projection style: {spec['projection_style']}")

    nodes = _nodes(graph)
    edges = _edges(graph)
    by_depth: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_depth[max(0, int(node.get("projection_depth") or 0))].append(node)
    for members in by_depth.values():
        members.sort(key=lambda node: str(node["id"]))

    projected: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    dimension = spec["dimension"]

    if dimension == "2d":
        width = 3600.0
        cursor_y = 100.0
        for level, members in sorted(by_depth.items()):
            cols = max(1, min(9, math.ceil(math.sqrt(len(members)))))
            rows = max(1, math.ceil(len(members) / cols))
            card_w, card_h, gap_x, gap_y = 320.0, 84.0, 28.0, 24.0
            grid_w = cols * card_w + max(0, cols - 1) * gap_x
            start_x = (width - grid_w) / 2.0
            groups.append({
                "id": f"topic-depth-{level}",
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
        bounds = {"width": width, "height": max(1000.0, cursor_y + 100.0)}
        extent = None
    else:
        plane_gap = 320.0
        max_span = 0.0
        for level, members in sorted(by_depth.items()):
            cols = max(1, min(9, math.ceil(math.sqrt(len(members)))))
            rows = max(1, math.ceil(len(members) / cols))
            gap_x, gap_z = 360.0, 190.0
            span_x = max(0.0, (cols - 1) * gap_x)
            span_z = max(0.0, (rows - 1) * gap_z)
            max_span = max(max_span, span_x, span_z)
            groups.append({
                "id": f"topic-depth-{level}",
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
        bounds = None
        extent = max(1000.0, max_span * 0.75 + (max(by_depth, default=0) + 1) * plane_gap)

    result = {
        "id": generator,
        "title": f"Topic · Atlas {dimension.upper()}",
        "dimension": dimension,
        "kind": "topic_projection",
        "projection_base": "topic",
        "projection_style": "atlas",
        "projection_layout": "tiled_grid",
        "semantic_graph_only": True,
        "inference": False,
        "nodes": projected,
        "edges": edges,
        "groups": groups,
        "projection_base_ids": deepcopy(graph.get("projection_base_ids", [])),
    }
    if bounds is not None:
        result["bounds"] = bounds
    if extent is not None:
        result["extent"] = extent
    return result


__all__ = [
    "PROJECTION_BASE",
    "TOPIC_STYLES",
    "SCOPE_STYLES",
    "PROJECTIONS",
    "projection_base_catalog",
    "projection_style_catalog",
    "projection_styles_by_base",
    "scope_style_catalog",
    "normalize_projection_base",
    "resolve_projection_style",
    "normalize_scope_style",
    "apply_scope_style",
    "build_topic_visual",
]
