from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
SERVER = ROOT / "server"


class ArchitectureTests(unittest.TestCase):
    def test_removed_client_compatibility_patterns_do_not_return(self):
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                STATIC / "app.js",
                STATIC / "entity_editor.js",
                STATIC / "projection_visibility.js",
                STATIC / "event_rule_editor.js",
                STATIC / "link_projection.js",
            ]
        )
        forbidden = [
            "entity_type_ref",
            "activeLinkProperties =",
            "visibleEntityIds = function",
            "linkSlots = typedLinkSlots",
            "const baseInspect = inspect",
            "ensureWorkspace",
            "DEFAULT_RULESETS",
            "DEFAULT_COLOR_SPACES",
        ]
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, sources)

    def test_server_has_no_setdefault_migration_layer(self):
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SERVER / "workspace.py", SERVER / "semantics.py", SERVER / "abstractions.py"]
        )
        self.assertNotIn(".setdefault(", sources)

    def test_obsolete_projection_module_is_deleted(self):
        self.assertFalse((STATIC / "view_projection.js").exists())

    def test_every_loaded_static_module_is_served(self):
        html = (STATIC / "structure.html").read_text(encoding="utf-8")
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        for name in [
            "app.js",
            "entity_editor.js",
            "causal_projection.js",
            "projection_visibility.js",
            "event_rule_editor.js",
            "abstraction_library.js",
            "link_projection.js",
            "style.css",
        ]:
            with self.subTest(name=name):
                self.assertIn(f'/static/{name}', html)
                self.assertIn(f'"/static/{name}"', app)

    def test_link_projection_owns_one_typed_port_key_per_direction(self):
        source = (STATIC / "link_projection.js").read_text(encoding="utf-8")
        self.assertIn("${entity.id}\\u0000${direction}\\u0000${linkType}", source)
        self.assertIn("propertyBoxBottom(entity) - gap", source)
        self.assertIn("entity.position[1] + nodeHalfSize() + gap", source)
        self.assertIn("LINK_FLOW_MASK_PIXELS = 100", source)


if __name__ == "__main__":
    unittest.main()
