from __future__ import annotations

import re
import unittest
from pathlib import Path

from cw_oracle import CW_EVENT_IO_POINT_SCALE

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
SERVER = ROOT / "server"


def source(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


class ArchitectureTests(unittest.TestCase):
    def test_every_local_static_dependency_loaded_by_html_is_served(self):
        html = source("structure.html")
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        paths = set(re.findall(r'(?:src|href)="(/static/[^"]+)"', html))
        self.assertTrue(paths)
        for path in sorted(paths):
            with self.subTest(path=path):
                self.assertIn(f'"{path}"', app)
                self.assertTrue((STATIC / path.removeprefix("/static/")).exists())

    def test_client_canonical_index_reads_entities_and_properties_without_parallel_model(self):
        app = source("app.js")
        self.assertIn("function canonicalIndex()", app)
        self.assertIn("for (const entity of assertWorkspace().entities)", app)
        self.assertIn("for (const property of entity.properties)", app)
        self.assertNotIn("entity_type_ref", app)
        self.assertNotIn("canonicalEntities", app)
        self.assertNotIn("semanticGraph", app)

    def test_event_editor_writes_canonical_properties_and_links(self):
        event_editor = source("event_rule_editor.js")
        self.assertIn("subject.owner.properties.push", event_editor)
        self.assertIn("property_type_ref: 'link'", event_editor)
        self.assertIn("property_type_ref: 'effect'", event_editor)
        self.assertIn("ruleset.semantic_roles", event_editor)
        forbidden_parallel_models = ["eventRules =", "eventEffects =", "eventGraph =", "eventModel ="]
        for pattern in forbidden_parallel_models:
            self.assertNotIn(pattern, event_editor)

    def test_type_editor_writes_explicit_type_property(self):
        editor = source("entity_editor.js")
        self.assertIn("function setEntityType", editor)
        self.assertIn("property_type_ref: 'type'", editor)
        self.assertIn("ruleset_ref: 'RULESET_TYPE'", editor)
        self.assertNotIn("entity.entity_type_ref", editor)

    def test_semantic_export_boundary_is_entities_rulesets_colors_only(self):
        export = source("abstraction_library.js")
        semantic_body = export.split("function canonicalSemanticPayload()", 1)[1].split("function cwExportDocument()", 1)[0]
        self.assertIn("entities: structuredClone(source.entities)", semantic_body)
        self.assertIn("rulesets: structuredClone(source.rulesets)", semantic_body)
        self.assertIn("color_spaces: structuredClone(source.color_spaces)", semantic_body)
        for forbidden in ("camera", "settings", "runtime", "projection", "playback"):
            self.assertNotIn(forbidden, semantic_body)

    def test_scene_semantic_objects_are_world_space_not_dom_instances(self):
        causal = source("causal_projection.js")
        links = source("link_projection.js")
        scene = source("scene_ui_3d.js")
        self.assertIn("drawBox", causal)
        self.assertIn("drawLine", causal)
        self.assertIn("drawBox", links)
        self.assertIn("drawLine", links)
        self.assertIn("drawSceneText3D", causal)
        self.assertIn("gl.drawArrays", scene)
        for semantic_source in (causal, links):
            self.assertNotIn("createElementNS", semantic_source)
            self.assertNotIn("document.createElement('button')", semantic_source)
            self.assertNotIn("document.createElement(\"button\")", semantic_source)

    def test_projection_derives_props_and_events_from_canonical_property_type(self):
        causal = source("causal_projection.js")
        self.assertIn("property.property_type_ref === 'event'", causal)
        self.assertIn("item.propertyType", causal)
        self.assertIn("['link', 'event'].includes", causal)
        self.assertNotIn("propsData", causal)
        self.assertNotIn("eventsData", causal)

    def test_event_io_is_one_tiny_shared_point_pair_per_entity_layout(self):
        causal = source("causal_projection.js")
        expected = f"const pointHalf = nodeHalf * {CW_EVENT_IO_POINT_SCALE:.2f}".rstrip("0")
        # Current JS uses .10 spelling; normalize whitespace/leading decimal for semantic check.
        self.assertRegex(causal, r"const\s+pointHalf\s*=\s*nodeHalf\s*\*\s*(?:0?\.10|0?\.1)\s*;")
        self.assertIn("inCenter:", causal)
        self.assertIn("outCenter:", causal)
        self.assertIn("propsCenter[1]", causal)
        self.assertNotIn("drawSceneText3D('Event in'", causal)
        self.assertNotIn("drawSceneText3D('Event out'", causal)
        self.assertNotIn("row.inAnchor", causal)
        self.assertNotIn("row.outAnchor", causal)
        self.assertTrue(expected.startswith("const pointHalf"))

    def test_event_trace_is_derived_only_from_canonical_links(self):
        causal = source("causal_projection.js")
        self.assertIn("canonicalLinks()", causal)
        self.assertIn("buildCausalGraph", causal)
        self.assertIn("currentEvents: []", causal)
        self.assertIn("trace.graph.edges", causal)
        self.assertIn("EVENT_TRACE_COLORS", causal)
        self.assertIn("drawTransientTraceRoute", causal)
        self.assertNotIn("syntheticEdge", causal)
        self.assertNotIn("inferredRoute", causal)

    def test_event_playback_state_is_runtime_not_server_semantics(self):
        playback = source("playback_runtime.js")
        semantics = (SERVER / "semantics.py").read_text(encoding="utf-8")
        timing_fields = (
            "event_activation_duration",
            "effect_travel_duration",
            "target_effect_duration",
            "next_event_delay",
            "branch_delay",
            "completion_hold",
            "fade_out_duration",
            "playback_speed",
        )
        for field in timing_fields:
            self.assertIn(field, playback)
            self.assertNotIn(field, semantics)
        self.assertIn("stepPlayback", playback)
        self.assertIn("setPlaybackPaused", playback)

    def test_projection_visibility_filters_view_without_rewriting_canonical_properties(self):
        projection = source("projection_visibility.js")
        self.assertIn("function activeLinkProperties()", projection)
        self.assertIn("linkProperties()", projection)
        self.assertIn("hidden_link_types", projection)
        self.assertNotIn(".properties =", projection)
        self.assertNotIn("splice(", projection)
        self.assertNotIn("push({", projection)

    def test_generic_visual_aggregation_key_retains_link_type(self):
        projection = source("projection_visibility.js")
        self.assertIn("${parentEntity.id}\\u0000${childEntity.id}\\u0000${linkType}", projection)

    def test_no_silent_client_or_server_semantic_compatibility_layer(self):
        server_sources = "\n".join((SERVER / name).read_text(encoding="utf-8") for name in ("workspace.py", "semantics.py", "abstractions.py"))
        self.assertNotIn(".setdefault(", server_sources)
        client_sources = "\n".join(source(name) for name in ("app.js", "entity_editor.js", "event_rule_editor.js"))
        for legacy in ("entity_type_ref", "ensureWorkspace", "DEFAULT_RULESETS", "DEFAULT_COLOR_SPACES"):
            self.assertNotIn(legacy, client_sources)


if __name__ == "__main__":
    unittest.main()
