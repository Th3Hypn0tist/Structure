from __future__ import annotations

from copy import deepcopy
from typing import Any

# StructureProjector-local nanoCMS projection.
#
# The model intentionally follows the AIGMos nanoCMSStructure contract:
# recursive Page identities + ordered child references + ordered placements.
# This standalone copy owns only StructureProjector view placement/navigation.
# It does not own the semantics of the rulesets, graphs or renderers it places.

PAGES: dict[str, dict[str, Any]] = {
    "structureprojector": {
        "id": "structureprojector",
        "title": "StructureProjector",
        "menuitem": "StructureProjector",
        "description": "Read-only structural projection views.",
        "children": ["canonical-structure", "raw-json"],
        "placements": [],
    },
    "canonical-structure": {
        "id": "canonical-structure",
        "title": "Canonical Structure",
        "menuitem": "Canonical",
        "description": "CanonicalContract semantic structure map.",
        "children": [],
        "placements": ["view.canonical_structure_map"],
    },
    "raw-json": {
        "id": "raw-json",
        "title": "Raw JSON",
        "menuitem": "Raw JSON",
        "description": "Raw JSON object/array/key/value containment view.",
        "children": [],
        "placements": ["view.raw_json_tree"],
    },
}

PLACEMENTS: dict[str, dict[str, Any]] = {
    "view.canonical_structure_map": {
        "id": "view.canonical_structure_map",
        "type": "structureprojector_view",
        "view": "canonical_structure_map",
        "ruleset": "CanonicalContract",
        "renderer": "svg",
    },
    "view.raw_json_tree": {
        "id": "view.raw_json_tree",
        "type": "structureprojector_view",
        "view": "raw_json_tree",
        "ruleset": "RawJSON",
        "renderer": "svg",
    },
}

ROOT_PAGE = "structureprojector"
DEFAULT_PAGE = "canonical-structure"


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


_validate()


def resolve_page(page_id: str | None) -> dict[str, Any]:
    resolved_id = page_id or DEFAULT_PAGE
    if resolved_id not in PAGES:
        raise KeyError(resolved_id)
    page = deepcopy(PAGES[resolved_id])
    page["children"] = [deepcopy(PAGES[child]) for child in page["children"]]
    page["placements"] = [deepcopy(PLACEMENTS[p]) for p in page["placements"]]
    return page


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


def projection(page_id: str | None = None) -> dict[str, Any]:
    selected = page_id or DEFAULT_PAGE
    return {
        "name": "StructureProjector nanoCMS",
        "model": "recursive Page + ordered children + placements",
        "root": deepcopy(PAGES[ROOT_PAGE]),
        "default_page": DEFAULT_PAGE,
        "selected_page": resolve_page(selected),
        "navigation": navigation(),
    }
