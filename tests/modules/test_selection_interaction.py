from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
WORKSPACE_SOURCE = (ROOT / "server" / "workspace.py").read_text(encoding="utf-8")


class SelectionInteractionTests(unittest.TestCase):
    def test_selection_is_runtime_state_with_one_toggle_operation(self):
        self.assertIn("let selected = new Set();", APP_SOURCE)
        self.assertIn("function toggleSelection(ids)", APP_SOURCE)
        toggle = APP_SOURCE.split("function toggleSelection(ids)", 1)[1].split("function selectionBoxElement", 1)[0]
        self.assertIn("selected.delete(id)", toggle)
        self.assertIn("selected.add(id)", toggle)
        self.assertIn("normalizeActiveSelection()", toggle)
        self.assertNotIn("assertWorkspace().selected", toggle)

    def test_ctrl_node_binding_uses_toggle_selection(self):
        self.assertIn("if(event.ctrlKey||event.shiftKey){toggleSelection(entity.id);}", APP_SOURCE)

    def test_ctrl_empty_space_starts_box_selection_instead_of_pan(self):
        self.assertIn("if(!entity){if(event.ctrlKey)", APP_SOURCE)
        self.assertIn("boxSelection={startX:event.clientX,startY:event.clientY,currentX:event.clientX,currentY:event.clientY}", APP_SOURCE)

    def test_box_result_uses_same_toggle_operation_and_never_replaces_selection(self):
        mouseup = APP_SOURCE.split("window.onmouseup=event=>", 1)[1].split("window.onmousemove=event=>", 1)[0]
        self.assertIn("const ids=entitiesInSelectionBox(box).map(entity=>entity.id)", mouseup)
        self.assertIn("toggleSelection(ids)", mouseup)
        self.assertNotIn("selected=new Set(ids)", mouseup)
        self.assertNotIn("selected.clear()", mouseup.split("if(boxSelection)", 1)[1].split("if(pan)", 1)[0])

    def test_box_membership_is_projected_visible_node_center(self):
        box = APP_SOURCE.split("function entitiesInSelectionBox(box)", 1)[1].split("function inspect", 1)[0]
        self.assertIn("visibleEntityIds()", box)
        self.assertIn("project(entity.position,vp)", box)
        self.assertIn("center[0]>=left", box)
        self.assertIn("center[1]>=top", box)

    def test_selection_state_is_not_persisted_in_workspace_schema(self):
        self.assertNotIn('"selected"', WORKSPACE_SOURCE)
        self.assertNotIn('"boxSelection"', WORKSPACE_SOURCE)


if __name__ == "__main__":
    unittest.main()
