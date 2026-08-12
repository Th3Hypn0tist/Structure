from __future__ import annotations

from typing import Any


def _item_height(template: str, item: dict[str, Any]) -> int:
    if template == "chip_grid":
        return 34
    if template == "registry_grid":
        return 82
    summary = str(item.get("summary") or "")
    return 92 if len(summary) < 120 else 122


def build_explicit_view_geometry(view: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic, navigable SVG geometry from a resolved view.

    Occurrences are projection-only. Status is carried through only when it is
    explicit in the source/view projection; geometry never invents lifecycle state.
    """
    width = 3680
    margin = 44
    section_gap = 28
    section_pad = 24
    block_gap = 20
    title_h = 64
    usable_w = width - margin * 2

    occurrences: list[dict[str, Any]] = []
    y = 92

    for section in view.get("sections", []):
        section_id = section["id"]
        section_y = y
        block_y = section_y + title_h
        block_occurrences: list[dict[str, Any]] = []

        for block in section.get("blocks", []):
            block_id = f"{section_id}::{block['id']}"
            template = block.get("template", "card_grid")
            items = block.get("items", [])
            block_title_h = 42
            inner_w = usable_w - section_pad * 2

            if template == "chip_grid":
                cols = 8
                item_gap = 8
                item_w = int((inner_w - (cols - 1) * item_gap) / cols)
                rows = max(1, (len(items) + cols - 1) // cols)
                item_h = 34
                content_h = rows * item_h + max(0, rows - 1) * item_gap
            elif template == "registry_grid":
                cols = 3
                item_gap = 14
                item_w = int((inner_w - (cols - 1) * item_gap) / cols)
                rows = max(1, (len(items) + cols - 1) // cols)
                item_h = 82
                content_h = rows * item_h + max(0, rows - 1) * item_gap
            else:
                cols = 3 if len(items) <= 9 else 4
                item_gap = 14
                item_w = int((inner_w - (cols - 1) * item_gap) / cols)
                heights = [_item_height(template, item) for item in items] or [92]
                rows_list = [heights[i:i + cols] for i in range(0, len(heights), cols)]
                row_heights = [max(row) for row in rows_list]
                content_h = sum(row_heights) + max(0, len(row_heights) - 1) * item_gap

            block_h = block_title_h + content_h + 22
            block_occurrences.append({
                "kind": "block",
                "id": block_id,
                "parent_id": section_id,
                "title": block.get("title", block["id"]),
                "template": template,
                "accent": block.get("accent", section.get("accent", "primary")),
                "status": block.get("status"),
                "x": margin + section_pad,
                "y": block_y,
                "width": inner_w,
                "height": block_h,
                "child_count": len(items),
            })

            item_y0 = block_y + block_title_h
            if template in ("chip_grid", "registry_grid"):
                for index, item in enumerate(items):
                    row, col = divmod(index, cols)
                    item_h = 34 if template == "chip_grid" else 82
                    item_x = margin + section_pad + col * (item_w + item_gap)
                    item_y = item_y0 + row * (item_h + item_gap)
                    block_occurrences.append({
                        "kind": "item",
                        "role": item.get("role", "card"),
                        "id": f"{block_id}::{index}",
                        "parent_id": block_id,
                        "title": item.get("title", ""),
                        "summary": item.get("summary", ""),
                        "status": item.get("status"),
                        "value": item.get("value"),
                        "provenance": item.get("provenance"),
                        "x": item_x,
                        "y": item_y,
                        "width": item_w,
                        "height": item_h,
                        "child_count": 0,
                    })
            else:
                row_y = item_y0
                for row_start in range(0, len(items), cols):
                    row_items = items[row_start:row_start + cols]
                    row_h = max((_item_height(template, item) for item in row_items), default=92)
                    for col, item in enumerate(row_items):
                        index = row_start + col
                        item_x = margin + section_pad + col * (item_w + item_gap)
                        block_occurrences.append({
                            "kind": "item",
                            "role": item.get("role", "card"),
                            "id": f"{block_id}::{index}",
                            "parent_id": block_id,
                            "title": item.get("title", ""),
                            "summary": item.get("summary", ""),
                            "status": item.get("status"),
                            "value": item.get("value"),
                            "provenance": item.get("provenance"),
                            "x": item_x,
                            "y": row_y,
                            "width": item_w,
                            "height": _item_height(template, item),
                            "child_count": 0,
                        })
                    row_y += row_h + item_gap

            block_y += block_h + block_gap

        section_h = max(150, block_y - section_y + section_pad - block_gap)
        occurrences.append({
            "kind": "section",
            "id": section_id,
            "parent_id": None,
            "title": section.get("title", section_id),
            "subtitle": section.get("subtitle", ""),
            "template": section.get("template", "large_frame"),
            "accent": section.get("accent", "primary"),
            "status": section.get("status"),
            "x": margin,
            "y": section_y,
            "width": usable_w,
            "height": section_h,
            "child_count": len(section.get("blocks", [])),
        })
        occurrences.extend(block_occurrences)
        y += section_h + section_gap

    return {
        "kind": "explicit_view_geometry",
        "view_id": view.get("id"),
        "title": view.get("title"),
        "subtitle": view.get("subtitle"),
        "status": view.get("status"),
        "view_box": {"width": width, "height": max(900, y + 60)},
        "occurrences": occurrences,
        "navigation": {
            "focusable_kinds": ["section", "block", "item"],
            "rule": "Focus changes only the projection frame. Source semantics remain unchanged.",
        },
    }
