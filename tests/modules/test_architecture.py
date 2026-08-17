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
            "scene_ui_3d.js",
            "entity_editor.js",
            "playback_runtime.js",
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

    def test_link_projection_is_world_space_3d_not_svg_or_dom_scene_content(self):
        source = (STATIC / "link_projection.js").read_text(encoding="utf-8")
        self.assertIn("function drawGenericLinks3D(time)", source)
        self.assertIn("drawLine(start, end, baseColor)", source)
        self.assertIn("drawBox(pulse", source)
        self.assertIn("drawBox(world", source)
        self.assertNotIn("createElementNS", source)
        self.assertNotIn("linkFlowSvg", source)
        self.assertNotIn("linkEventFlashLayer", source)
        self.assertNotIn("querySelectorAll('.causal-edge')", source)
        self.assertNotIn("LINK_FLOW_MASK_PIXELS", source)

    def test_scene_projection_is_world_space_3d_not_dom_scene_content(self):
        source = (STATIC / "causal_projection.js").read_text(encoding="utf-8")
        self.assertIn("function drawSceneProjection3D()", source)
        self.assertIn("function eventListLayout(entity)", source)
        self.assertIn("function propsListLayout(entity, items)", source)
        self.assertIn("drawSceneText3D", source)
        self.assertNotIn("document.createElement('button')", source)
        self.assertNotIn("document.createElementNS", source)
        self.assertNotIn(".event-button", source)
        self.assertNotIn(".property-panel", source)

    def test_event_routes_keep_baseline_flow_and_overlay_transient_traces(self):
        causal = (STATIC / "causal_projection.js").read_text(encoding="utf-8")
        links = (STATIC / "link_projection.js").read_text(encoding="utf-8")
        playback = (STATIC / "playback_runtime.js").read_text(encoding="utf-8")
        self.assertIn("currentEvents: []", causal)
        self.assertIn("EVENT_TRACE_COLORS", causal)
        self.assertIn("function allEventRoutes(layouts)", causal)
        self.assertIn("function drawTransientTraceRoute", causal)
        self.assertIn("function traceAlpha", causal)
        self.assertIn("eventRouteFlowProgress", causal)
        self.assertIn("base_flow_speed", causal)
        self.assertNotIn("active_link_speed", causal)
        self.assertIn("function activationAmount(propertyId)", links)
        self.assertIn("base_flow_speed", links)
        self.assertIn("active_link_speed", links)
        self.assertNotIn("LINK_EVENT_BOOST_MS", links)
        self.assertNotIn("NODE_EVENT_FLASH_MS", links)
        self.assertIn("pause", playback.lower())
        self.assertIn("stepPlayback", playback)
        self.assertIn("playback_speed", playback)

    def test_event_io_is_tiny_shared_point_projection(self):
        causal = (STATIC / "causal_projection.js").read_text(encoding="utf-8")
        self.assertIn("const pointHalf = nodeHalf * .10", causal)
        self.assertIn("inCenter: [leftEdge - gap - pointHalf", causal)
        self.assertIn("outCenter: [rightEdge + gap + pointHalf", causal)
        self.assertNotIn("drawSceneText3D('Event in'", causal)
        self.assertNotIn("drawSceneText3D('Event out'", causal)

    def test_event_playback_timing_is_visual_runtime_not_canonical_semantics(self):
        playback = (STATIC / "playback_runtime.js").read_text(encoding="utf-8")
        semantics = (SERVER / "semantics.py").read_text(encoding="utf-8")
        for field in [
            "event_activation_duration",
            "effect_travel_duration",
            "target_effect_duration",
            "next_event_delay",
            "branch_delay",
            "completion_hold",
            "fade_out_duration",
            "playback_speed",
        ]:
            with self.subTest(field=field):
                self.assertIn(field, playback)
                self.assertNotIn(field, semantics)

    def test_cw_export_uses_canonical_semantic_source_only(self):
        source = (STATIC / "abstraction_library.js").read_text(encoding="utf-8")
        html = (STATIC / "structure.html").read_text(encoding="utf-8")
        self.assertIn('id="exportCw"', html)
        self.assertIn("function canonicalSemanticPayload()", source)
        self.assertIn("entities: structuredClone(source.entities)", source)
        self.assertIn("rulesets: structuredClone(source.rulesets)", source)
        self.assertIn("color_spaces: structuredClone(source.color_spaces)", source)
        self.assertIn("function cwExportDocument()", source)
        self.assertNotIn("camera: structuredClone", source)
        self.assertNotIn("settings: structuredClone", source)
        self.assertIn("Structure_CW_", source)

    def test_toolbar_and_right_controls_follow_current_layout_contract(self):
        html = (STATIC / "structure.html").read_text(encoding="utf-8")
        css = (STATIC / "style.css").read_text(encoding="utf-8")
        self.assertIn('href="https://aigm.fi"', html)
        self.assertIn('id="rightControls"', html)
        self.assertLess(html.index('id="gridToggle"'), html.index('>VIEW</summary>'))
        self.assertLess(html.index('id="snapToggle"'), html.index('>VIEW</summary>'))
        self.assertIn('<details class="right-control-group" open>', html)
        self.assertIn('>VIEW</summary>', html)
        self.assertIn('>VISIBILITY</summary>', html)
        self.assertIn('background:#000', css)
        self.assertIn('flex-wrap:wrap', css)
        self.assertIn('top:var(--toolbar-clearance)', css)
        self.assertIn('.structure-brand-logo{display:block;width:auto;height:33px', css)
        self.assertIn('font-variant-caps:small-caps', css)


if __name__ == "__main__":
    unittest.main()
