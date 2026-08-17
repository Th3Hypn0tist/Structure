from __future__ import annotations

import unittest
from pathlib import Path

from cw_oracle import CW_PROPERTY_TYPES

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"


def text(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


class CWCapabilityTests(unittest.TestCase):
    """Hard UI capability gate for CW primitives.

    CW conformance is not only parser acceptance. Normal Structure use must have
    an explicit authoring path for every CW Property primitive; raw JSON is not
    an acceptable missing editor.
    """

    def authoring_evidence(self) -> dict[str, bool]:
        html = text("structure.html")
        app = text("app.js")
        entity = text("entity_editor.js")
        event = text("event_rule_editor.js")
        abstractions = text("abstraction_library.js")
        combined = "\n".join((html, app, entity, event, abstractions))
        return {
            "type": "setEntityType" in entity and "id=\"entityType\"" in html,
            "mount": "mountPublishedAbstraction" in abstractions and "property_type_ref: 'mount'" in abstractions,
            "link": "id=\"addLink\"" in html and "createLink" in app and "property_type_ref:'link'" in app.replace(" ", ""),
            "event": "id=\"addEvent\"" in html and "property_type_ref:'event'" in app.replace(" ", ""),
            "effect": "createEventRuleEffect" in event and "property_type_ref: 'effect'" in event,
            "data": "property_type_ref: 'data'" in combined or 'property_type_ref:"data"' in combined,
            "function": "property_type_ref: 'function'" in combined or 'property_type_ref:"function"' in combined,
        }

    def test_every_cw_property_primitive_has_explicit_normal_authoring_path(self):
        evidence = self.authoring_evidence()
        self.assertEqual(set(evidence), CW_PROPERTY_TYPES)
        missing = sorted(property_type for property_type, available in evidence.items() if not available)
        self.assertFalse(
            missing,
            "CW authoring capability missing for: " + ", ".join(missing) + ". Raw JSON does not satisfy CW authoring.",
        )

    def test_event_effect_authoring_uses_ruleset_roles_not_hardcoded_endpoint_guessing(self):
        event = text("event_rule_editor.js")
        self.assertIn("eventRuleEndpointField", event)
        self.assertIn("ruleset.semantic_roles", event)
        self.assertIn("createEventRuleLink", event)
        self.assertIn("createEventRuleEffect", event)

    def test_mount_authoring_creates_reference_not_embedded_abstraction_copy(self):
        abstractions = text("abstraction_library.js")
        mount_body = abstractions.split("function mountPublishedAbstraction", 1)[1].split("window.addEventListener", 1)[0]
        self.assertIn("abstraction_ref: abstractionRef", mount_body)
        self.assertNotIn("entities:", mount_body)
        self.assertNotIn("rulesets:", mount_body)

    def test_type_can_be_explicitly_removed_back_to_unresolved(self):
        entity = text("entity_editor.js")
        set_type = entity.split("function setEntityType", 1)[1].split("function machineContractStatus", 1)[0]
        self.assertIn("if (!value)", set_type)
        self.assertIn("entity.properties = entity.properties.filter", set_type)

    def test_no_authoring_feature_requires_raw_json_as_only_semantic_editor(self):
        html = text("structure.html")
        # JSON parameter editing may exist for Link parameters, but the core CW
        # primitive creation surface itself must be explicit controls.
        self.assertNotIn("Edit workspace JSON", html)
        self.assertNotIn("Raw canonical JSON", html)


if __name__ == "__main__":
    unittest.main()
