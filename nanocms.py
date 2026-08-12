from __future__ import annotations

from copy import deepcopy
from typing import Any

# StructureProjector-local nanoCMS projection.
# Page = stable inspection context. Placement = alternative view of that context.
# Changing a placement MUST NOT change the selected semantic/tree context.

CANONICAL_PROJECTION_PLACEMENTS = [
    "view.atlas_2d",
    "view.relation_web_2d",
    "view.adjacency_matrix_2d",
    "view.lifecycle_lanes_2d",
    "view.dependency_flow_2d",
    "view.semantic_galaxy_3d",
    "view.role_layers_3d",
    "view.dependency_tower_3d",
    "view.authority_space_3d",
    "view.relation_orbits_3d",
]

PAGES: dict[str, dict[str, Any]] = {
    "structureprojector": {
        "id": "structureprojector",
        "title": "StructureProjector",
        "menuitem": "StructureProjector",
        "description": "Read-only structural projection contexts.",
        "children": ["canonical", "raw-json"],
        "placements": [],
    },
    "canonical": {
        "id": "canonical",
        "title": "Canonical",
        "menuitem": "Canonical",
        "description": "Canonical AIGMos inspection context.",
        "children": [],
        "placements": CANONICAL_PROJECTION_PLACEMENTS,
    },
    "raw-json": {
        "id": "raw-json",
        "title": "Raw JSON",
        "menuitem": "Raw JSON",
        "description": "Raw JSON structural tree context.",
        "children": [],
        "placements": ["view.raw_json_tree", "view.raw_json_master_map"],
    },
}


def _canonical_projection(
    placement_id: str,
    title: str,
    projection_id: str,
    renderer: str,
) -> dict[str, Any]:
    return {
        "id": placement_id,
        "title": title,
        "type": "structureprojector_view",
        "view": projection_id,
        "ruleset": "CanonicalContract",
        "view_ruleset": None,
        "renderer": renderer,
        "context_model": "semantic_identity",
        "render_ruleset": projection_id,
        "projection_id": projection_id,
    }


PLACEMENTS: dict[str, dict[str, Any]] = {
    "view.atlas_2d": _canonical_projection("view.atlas_2d", "Atlas 2D", "atlas_2d", "canonical_projection_2d"),
    "view.relation_web_2d": _canonical_projection("view.relation_web_2d", "Relation Web", "relation_web_2d", "canonical_projection_2d"),
    "view.adjacency_matrix_2d": _canonical_projection("view.adjacency_matrix_2d", "Matrix", "adjacency_matrix_2d", "canonical_projection_2d"),
    "view.lifecycle_lanes_2d": _canonical_projection("view.lifecycle_lanes_2d", "Lifecycle", "lifecycle_lanes_2d", "canonical_projection_2d"),
    "view.dependency_flow_2d": _canonical_projection("view.dependency_flow_2d", "Dependency Flow", "dependency_flow_2d", "canonical_projection_2d"),
    "view.semantic_galaxy_3d": _canonical_projection("view.semantic_galaxy_3d", "Galaxy 3D", "semantic_galaxy_3d", "canonical_projection_3d"),
    "view.role_layers_3d": _canonical_projection("view.role_layers_3d", "Role Layers", "role_layers_3d", "canonical_projection_3d"),
    "view.dependency_tower_3d": _canonical_projection("view.dependency_tower_3d", "Dependency Tower", "dependency_tower_3d", "canonical_projection_3d"),
    "view.authority_space_3d": _canonical_projection("view.authority_space_3d", "Authority Space", "authority_space_3d", "canonical_projection_3d"),
    "view.relation_orbits_3d": _canonical_projection("view.relation_orbits_3d", "Relation Orbits", "relation_orbits_3d", "canonical_projection_3d"),
    "view.raw_json_tree": {
        "id": "view.raw_json_tree",
        "title": "JSON Tree",
        "type": "structureprojector_view",
        "view": "raw_json_tree",
        "ruleset": "RawJSON",
        "view_ruleset": None,
        "renderer": "svg",
        "context_model": "json_pointer",
        "render_ruleset": None,
    },
    "view.raw_json_master_map": {
        "id": "view.raw_json_master_map",
        "title": "Map 2D",
        "type": "structureprojector_view",
        "view": "raw_json_master_map",
        "ruleset": "RawJSON",
        "view_ruleset": None,
        "renderer": "svg_master_map",
        "context_model": "json_pointer",
        "render_ruleset": "render.aigmos_master_map",
    },
}

ROOT_PAGE = "structureprojector"
DEFAULT_PAGE = "canonical"


def _validate() -> None:
    if ROOT_PAGE not in PAGES:
        raise ValueError("nanoCMS root page is missing")
    if DEFAULT_PAGE not in PAGES:
        raise ValueError("nanoCMS default page is missing")
    for page_id, page in PAGES.items():
        if page.get("id") != page_id:
            raise ValueError(f"nanoCMS page identity mismatch: {page_id}")
        for field in ("title", "menuitem", "description", "children", "placements"):
            if field not in page:
                raise ValueError(f"nanoCMS page {page_id} missing {field}")
        for child_ref in page["children"]:
            if child_ref not in PAGES:
                raise ValueError(f"nanoCMS page {page_id} has unresolved child {child_ref}")
        for placement_ref in page["placements"]:
            if placement_ref not in PLACEMENTS:
                raise ValueError(f"nanoCMS page {page_id} has unresolved placement {placement_ref}")
    for placement_id, placement in PLACEMENTS.items():
        if placement.get("id") != placement_id:
            raise ValueError(f"nanoCMS placement identity mismatch: {placement_id}")
        for field in ("title", "view", "ruleset", "renderer", "context_model", "render_ruleset", "view_ruleset"):
            if field not in placement:
                raise ValueError(f"nanoCMS placement {placement_id} missing {field}")


_validate()


def resolve_page(page_id: str | None) -> dict[str, Any]:
    resolved_id = page_id or DEFAULT_PAGE
    if resolved_id not in PAGES:
        raise KeyError(resolved_id)
    page = deepcopy(PAGES[resolved_id])
    page["children"] = [deepcopy(PAGES[child]) for child in page["children"]]
    page["placements"] = [deepcopy(PLACEMENTS[p]) for p in page["placements"]]
    return page


def resolve_view(page_id: str | None, view_id: str | None = None) -> dict[str, Any]:
    page = resolve_page(page_id)
    placements = page["placements"]
    if not placements:
        raise KeyError(view_id or "")
    if view_id is None:
        return deepcopy(placements[0])
    for placement in placements:
        if placement["id"] == view_id or placement["view"] == view_id:
            return deepcopy(placement)
    raise KeyError(view_id)


def navigation() -> list[dict[str, str]]:
    root = PAGES[ROOT_PAGE]
    return [
        {
            "id": child_id,
            "title": PAGES[child_id]["title"],
            "menuitem": PAGES[child_id]["menuitem"],
            "description": PAGES[child_id]["description"],
        }
        for child_id in root["children"]
    ]


def projection(page_id: str | None = None, view_id: str | None = None) -> dict[str, Any]:
    selected_page = page_id or DEFAULT_PAGE
    page = resolve_page(selected_page)
    selected_view = resolve_view(selected_page, view_id)
    return {
        "name": "StructureProjector nanoCMS",
        "model": "recursive Page context + ordered alternative view placements",
        "context_rule": "Changing view placement preserves the selected tree/semantic context.",
        "root": deepcopy(PAGES[ROOT_PAGE]),
        "default_page": DEFAULT_PAGE,
        "selected_page": page,
        "selected_view": selected_view,
        "navigation": navigation(),
    }
