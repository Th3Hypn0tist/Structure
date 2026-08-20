from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELETION = (ROOT / "static" / "canonical_deletion.js").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "structure.html").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


class CanonicalDeletionInteractionTests(unittest.TestCase):
    def test_deletion_module_is_loaded_after_event_editor_and_served(self):
        event_index = HTML.index('/static/event_rule_editor.js')
        deletion_index = HTML.index('/static/canonical_deletion.js')
        self.assertLess(event_index, deletion_index)
        self.assertIn('"/static/canonical_deletion.js"', APP)

    def test_entity_deletion_preflights_before_mutating_entities(self):
        body = DELETION.split('function deleteSelectedEntitiesCanonical()', 1)[1].split('deleteSelectedEntities =', 1)[0]
        self.assertLess(body.index('deletionBlockers('), body.index('assertWorkspace().entities ='))
        self.assertIn('if (deletionBlocked(', body)
        self.assertIn('deletionLinkClosure(rootRefs)', body)

    def test_surviving_function_and_coordinate_space_refs_block_deletion(self):
        blockers = DELETION.split('function deletionBlockers(', 1)[1].split('function deletionBlocked', 1)[0]
        self.assertIn('entity.coordinate_space_ref', blockers)
        self.assertIn("['input_refs', 'output_refs']", blockers)
        self.assertIn('deletedRefs.has(ref)', blockers)

    def test_event_deletion_removes_incident_links_only_after_preflight(self):
        body = DELETION.split('function deleteCanonicalEvent(eventRef)', 1)[1].split('function deleteSelectedEntitiesCanonical', 1)[0]
        self.assertIn('deletionLinkClosure(removedPropertyIds)', body)
        self.assertLess(body.index('deletionBlockers('), body.index('record.owner.properties ='))
        self.assertIn('removeCanonicalLinks(linkIds)', body)

    def test_direct_link_delete_does_not_rewrite_other_canonical_semantics(self):
        body = DELETION.split('function deleteCanonicalLink(linkRef)', 1)[1].split('function deleteCanonicalEvent', 1)[0]
        self.assertIn("deletionPropertyRecord(linkRef, 'link')", body)
        self.assertIn('record.owner.properties = record.owner.properties.filter', body)
        self.assertNotIn('coordinate_space_ref =', body)
        self.assertNotIn('input_refs =', body)
        self.assertNotIn('output_refs =', body)

    def test_left_panel_exposes_link_and_event_delete_actions(self):
        self.assertIn('data-canonical-link-delete', DELETION)
        self.assertIn('data-canonical-event-delete', DELETION)
        self.assertIn("document.querySelectorAll('#selection .link-row')", DELETION)
        self.assertIn("document.querySelectorAll('[data-event-rule-open]')", DELETION)


if __name__ == '__main__':
    unittest.main()
