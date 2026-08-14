from __future__ import annotations

from copy import deepcopy
from typing import Any

from semantic_visual_projections import STYLE_FAMILIES, resolve_visual_style


PROJECTION_BASES: dict[str, dict[str, Any]] = {
    "map": {
        "label": "Map",
        "engine": "topic",
        "scope_types": ["all", "topic"],
        "styles": ["atlas", "map", "matrix", "galaxy", "component_islands", "hierarchy_tree", "relation_shells", "structure_spine"],
        "default_style": "atlas",
        "question": "What are the resolved semantic areas and what is inside the selected area?",
    },
    "event": {
        "label": "Event",
        "engine": "event",
        "scope_types": ["event"],
        "styles": ["lifecycle_lanes", "dependency_flow", "hierarchy_tree", "relation_generations", "atlas", "structure_spine"],
        "default_style": "dependency_flow",
        "question": "What explicit mechanism, evidence and causal path belongs to this Event?",
    },
    "dependency": {
        "label": "Dependency",
        "engine": "structural",
        "edge_dimension": "dependencies",
        "scope_types": ["identity", "topic"],
        "styles": ["dependency_flow", "dependency_tower", "hierarchy_tree", "relation_generations", "relation_shells", "structure_spine"],
        "default_style": "dependency_flow",
        "question": "What does this scope require and what explicitly depends on it?",
    },
    "relation": {
        "label": "Relation",
        "engine": "structural",
        "edge_dimension": "relations",
        "scope_types": ["identity", "topic"],
        "styles": ["map", "matrix", "relation_orbits", "relation_shells", "galaxy", "component_islands"],
        "default_style": "relation_orbits",
        "question": "Which explicit typed relations connect this scope?",
    },
    "authority": {
        "label": "Authority",
        "engine": "structural",
        "edge_dimension": "authority",
        "scope_types": ["identity", "topic"],
        "styles": ["authority_space", "hierarchy_tree", "relation_generations", "relation_shells"],
        "default_style": "authority_space",
        "question": "Which explicit authority paths reach this scope?",
    },
    "ownership": {
        "label": "Ownership",
        "engine": "structural",
        "edge_dimension": "ownership",
        "scope_types": ["identity", "topic"],
        "styles": ["role_layers", "hierarchy_tree", "component_islands", "relation_shells"],
        "default_style": "role_layers",
        "question": "Who or what explicitly owns this scope?",
    },
    "containment": {
        "label": "Containment",
        "engine": "structural",
        "edge_dimension": "containment",
        "scope_types": ["identity", "topic"],
        "styles": ["hierarchy_tree", "structure_spine", "component_islands", "atlas"],
        "default_style": "hierarchy_tree",
        "question": "What explicitly contains what in this scope?",
    },
}


SCOPE_STYLES: dict[str, dict[str, Any]] = {
    "semantic_roles": {
        "label": "Semantic roles",
        "description": "Selected/base = blue, context = silver, causal = gold, gaps/unresolved = red.",
    },
    "depth": {
        "label": "Depth",
        "description": "Projection depth parity: even = blue, odd = silver; gaps stay red.",
    },
    "monochrome": {
        "label": "Monochrome",
        "description": "Neutral silver nodes; gaps/unresolved stay red.",
    },
}


LEGACY_BASE_ALIASES = {
    "topic": "map",
    "impact": "event",
}


def projection_base_catalog() -> list[dict[str, Any]]:
    return [
        {"id": base_id, **deepcopy(spec)}
        for base_id, spec in PROJECTION_BASES.items()
    ]


def scope_style_catalog() -> list[dict[str, Any]]:
    return [
        {"id": style_id, **deepcopy(spec)}
        for style_id, spec in SCOPE_STYLES.items()
    ]


def normalize_projection_base(value: Any) -> str:
    base = str(value or "map").strip()
    base = LEGACY_BASE_ALIASES.get(base, base)
    if base not in PROJECTION_BASES:
        raise KeyError(f"Unknown projection base: {base}")
    return base


def compatible_projection_styles(base_id: str) -> list[dict[str, Any]]:
    base = PROJECTION_BASES[normalize_projection_base(base_id)]
    out = []
    for style_id in base["styles"]:
        family = STYLE_FAMILIES.get(style_id)
        if family is None:
            continue
        out.append({
            "id": style_id,
            "label": family["label"],
            "dimensions": ["2d", "3d"],
            "variants": {
                "2d": f"semantic_{style_id}_2d",
                "3d": f"semantic_{style_id}_3d",
            },
        })
    return out


def resolve_projection_style(base_id: str, style: Any, dimension: Any) -> tuple[str, str, str]:
    base = PROJECTION_BASES[normalize_projection_base(base_id)]
    style_id = str(style or base["default_style"]).strip()
    if style_id not in base["styles"]:
        raise ValueError(f"Projection style {style_id} is not compatible with projection base {base_id}")
    return resolve_visual_style(style_id, str(dimension or "3d"))


def normalize_scope_style(value: Any) -> str:
    style_id = str(value or "semantic_roles").strip()
    if style_id not in SCOPE_STYLES:
        raise KeyError(f"Unknown scope style: {style_id}")
    return style_id


def _scope_role(node: dict[str, Any], base_ids: set[str]) -> str:
    node_id = str(node.get("id") or "")
    kind = str(node.get("kind") or node.get("type") or "").lower()
    role = str(node.get("projection_role") or "").lower()
    if node.get("unresolved") or "gap" in kind or "gap" in role:
        return "gap"
    if "causal" in role:
        return "causal"
    if node_id in base_ids or int(node.get("projection_depth") or 0) == 0:
        return "base"
    if "context" in role or "context" in kind:
        return "context"
    return "related"


def apply_scope_style(graph: dict[str, Any], scope_style: str) -> dict[str, Any]:
    style_id = normalize_scope_style(scope_style)
    out = deepcopy(graph)
    base_ids = {str(ref) for ref in out.get("projection_base_ids", [])}
    for node in out.get("nodes", []):
        if not isinstance(node, dict):
            continue
        role = _scope_role(node, base_ids)
        depth = int(node.get("projection_depth") or 0)
        if role == "gap":
            color = "#FF176B"
        elif style_id == "monochrome":
            color = "#AAB2C2"
        elif style_id == "depth":
            color = "#087CFF" if depth % 2 == 0 else "#AAB2C2"
        elif role == "causal":
            color = "#FFD83D"
        elif role == "base":
            color = "#087CFF"
        else:
            color = "#AAB2C2"
        node["scope_style"] = style_id
        node["scope_role"] = role
        node["scope_color"] = color
    out["scope_style"] = style_id
    return out


__all__ = [
    "PROJECTION_BASES",
    "SCOPE_STYLES",
    "projection_base_catalog",
    "scope_style_catalog",
    "normalize_projection_base",
    "compatible_projection_styles",
    "resolve_projection_style",
    "normalize_scope_style",
    "apply_scope_style",
]
