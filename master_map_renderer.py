from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_RULESET = os.path.join(
    os.path.dirname(__file__), "rulesets", "render", "AIGMos_Master_Map_v1.0.json"
)


def load_ruleset(path: str = DEFAULT_RULESET) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        rules = json.load(handle)
    if rules.get("id") != "render.aigmos_master_map":
        raise ValueError("unexpected render ruleset")
    return rules


def _containment(graph: dict[str, Any]) -> tuple[dict[str, list[str]], dict[str, str]]:
    nodes = graph.get("nodes", [])
    children = {node["id"]: [] for node in nodes}
    parent: dict[str, str] = {}
    for edge in graph.get("edges", []):
        if edge.get("dimension") != "containment":
            continue
        source, target = edge.get("source"), edge.get("target")
        if source in children and target in children:
            children[source].append(target)
            parent[target] = source
    return children, parent


def _descendant_count(root: str, children: dict[str, list[str]]) -> int:
    total = 0
    stack = list(children.get(root, []))
    seen = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        total += 1
        stack.extend(children.get(current, []))
    return total


def _is_descendant_of(node_id: str, root_id: str, parent: dict[str, str]) -> bool:
    current = node_id
    seen = set()
    while current in parent and current not in seen:
        seen.add(current)
        current = parent[current]
        if current == root_id:
            return True
    return False


def build_master_map_projection(
    graph: dict[str, Any],
    context_id: str | None = None,
    ruleset_path: str = DEFAULT_RULESET,
) -> dict[str, Any]:
    rules = load_ruleset(ruleset_path)
    nodes = graph.get("nodes", [])
    by_id = {node["id"]: node for node in nodes}

    if not nodes:
        return {
            "ruleset": rules["id"],
            "view_box": {"width": rules["canvas"]["reference_width"], "height": 600},
            "grid": rules["canvas"]["grid"],
            "root": None,
            "occurrences": [],
            "scope": {"visible_depth": 3, "omitted_deeper_descendants": 0},
        }

    children, parent = _containment(graph)
    roots = [node["id"] for node in nodes if node["id"] not in parent]
    root_id = context_id if context_id in by_id else (roots[0] if roots else nodes[0]["id"])

    geom = rules["geometry"]
    layout = rules["layout"]
    width = int(rules["canvas"]["reference_width"])
    margin = int(layout.get("outer_margin_px", 50))
    frame_pad = int(geom["frame"]["padding_px"])
    section_pad = int(geom["section"]["padding_px"])
    card_w = int(geom["card"]["preferred_width_px"])
    card_gap = int(layout.get("card_gap_px", layout.get("preferred_inter_card_gap_px", 20)))
    row_gap = int(layout.get("row_gap_px", layout.get("preferred_inter_card_gap_px", 20)))
    section_gap = int(layout.get("section_gap_px", layout.get("minimum_inter_section_gap_px", 25)))
    max_cols = int(layout.get("max_columns", 6))
    chip_height = geom["chip"].get("height_px", 24)
    chip_h = int(chip_height[0] if isinstance(chip_height, list) else chip_height)
    card_min_h = int(geom["card"]["min_height_px"])

    occurrences: list[dict[str, Any]] = []
    frame_x = margin
    frame_y = margin
    frame_w = width - margin * 2
    current_y = frame_y + frame_pad + 60

    root_node = by_id[root_id]
    direct = children.get(root_id, [])
    sections = direct if direct else [root_id]

    for section_id in sections:
        section_node = by_id[section_id]
        card_ids = children.get(section_id, []) or [section_id]
        usable_w = frame_w - frame_pad * 2 - section_pad * 2
        columns = max(1, min(max_cols, int((usable_w + card_gap) // (card_w + card_gap))))
        actual_card_w = int((usable_w - (columns - 1) * card_gap) / columns)

        card_specs = []
        for card_id in card_ids:
            child_ids = children.get(card_id, [])
            card_h = max(card_min_h, 72 + len(child_ids) * (chip_h + 4))
            deeper = sum(_descendant_count(cid, children) for cid in child_ids)
            if deeper:
                card_h += 22
            card_specs.append((card_id, child_ids, deeper, card_h))

        rows = [card_specs[i:i + columns] for i in range(0, len(card_specs), columns)]
        content_h = sum(max(spec[3] for spec in row) for row in rows)
        content_h += max(0, len(rows) - 1) * row_gap
        section_h = section_pad + 46 + content_h + section_pad
        section_x = frame_x + frame_pad
        section_w = frame_w - frame_pad * 2

        occurrences.append({
            "id": section_id, "role": "section", "x": section_x, "y": current_y,
            "width": section_w, "height": section_h,
            "title": section_node.get("name") or section_id,
            "subtitle": section_node.get("type") or section_node.get("kind") or "",
        })

        card_y = current_y + section_pad + 46
        for row in rows:
            row_h = max(spec[3] for spec in row)
            for col, (card_id, chip_ids, deeper, card_h) in enumerate(row):
                card_node = by_id[card_id]
                card_x = section_x + section_pad + col * (actual_card_w + card_gap)
                occurrences.append({
                    "id": card_id, "role": "card", "x": card_x, "y": card_y,
                    "width": actual_card_w, "height": card_h,
                    "title": card_node.get("name") or card_id,
                    "subtitle": card_node.get("type") or card_node.get("kind") or "",
                    "value": card_node.get("value"), "deeper_descendants": deeper,
                })
                chip_y = card_y + 66
                for chip_id in chip_ids:
                    chip_node = by_id[chip_id]
                    occurrences.append({
                        "id": chip_id, "role": "chip", "x": card_x + 16, "y": chip_y,
                        "width": actual_card_w - 32, "height": chip_h,
                        "title": chip_node.get("name") or chip_id,
                        "subtitle": chip_node.get("type") or chip_node.get("kind") or "",
                        "value": chip_node.get("value"),
                    })
                    chip_y += chip_h + 4
            card_y += row_h + row_gap
        current_y += section_h + section_gap

    frame_h = max(180, current_y - frame_y + frame_pad - section_gap)
    occurrences.insert(0, {
        "id": root_id, "role": "frame", "x": frame_x, "y": frame_y,
        "width": frame_w, "height": frame_h,
        "title": root_node.get("name") or root_id,
        "subtitle": root_node.get("type") or root_node.get("kind") or "",
    })

    visible_ids = {occ["id"] for occ in occurrences}
    omitted = sum(
        1 for node in nodes
        if node["id"] not in visible_ids and _is_descendant_of(node["id"], root_id, parent)
    )
    policy = rules.get("projection_policy", {})
    return {
        "ruleset": rules["id"],
        "ruleset_version": rules.get("version"),
        "view_box": {"width": width, "height": int(frame_y + frame_h + margin)},
        "grid": rules["canvas"]["grid"],
        "root": root_id,
        "occurrences": occurrences,
        "scope": {
            "visible_depth": policy.get("visible_depth", 3),
            "omitted_deeper_descendants": omitted,
            "omission_policy": policy.get("deeper_descendants", "summarize_count"),
        },
    }
