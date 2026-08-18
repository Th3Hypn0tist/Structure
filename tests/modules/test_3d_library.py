from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
LIB = STATIC / "3d"


class ThreeDLibraryTests(unittest.TestCase):
    def test_generic_object_library_exists(self):
        expected = (
            "core.js",
            "math.js",
            "renderer.js",
            "render_store.js",
            "webgl_batch_renderer.js",
            "benchmark.js",
            "benchmark_webgl.js",
            "benchmark_panel.js",
            "objects/object.js",
            "objects/primitives.js",
            "objects/anchors.js",
            "objects/links.js",
            "objects/props.js",
            "objects/props_item.js",
            "objects/events.js",
            "objects/event_item.js",
            "objects/pulse.js",
            "objects/highlight.js",
        )
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue((LIB / name).is_file())

    def test_library_does_not_own_structure_canonical_semantics(self):
        semantic_library_files = [
            path for path in LIB.rglob("*.js")
            if path.name != "benchmark_panel.js"
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in semantic_library_files)
        forbidden = (
            "property_type_ref",
            "ruleset_ref",
            "link_type_ref",
            "canonicalIndex",
            "assertWorkspace",
            "StructurePlayback",
            "StructureCausalProjection",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_anchor_and_link_are_generic_object_mechanics(self):
        anchors = (LIB / "objects" / "anchors.js").read_text(encoding="utf-8")
        links = (LIB / "objects" / "links.js").read_text(encoding="utf-8")
        self.assertIn("class Anchor", anchors)
        self.assertIn("worldPosition()", anchors)
        self.assertIn("class Link", links)
        self.assertIn("from instanceof S3D.Anchor", links)
        self.assertIn("to instanceof S3D.Anchor", links)
        self.assertIn("pointAt", links)

    def test_props_and_events_are_instantiable_drawable_object_groups(self):
        props = (LIB / "objects" / "props.js").read_text(encoding="utf-8")
        props_item = (LIB / "objects" / "props_item.js").read_text(encoding="utf-8")
        events = (LIB / "objects" / "events.js").read_text(encoding="utf-8")
        event_item = (LIB / "objects" / "event_item.js").read_text(encoding="utf-8")
        self.assertIn("class Props extends S3D.Group", props)
        self.assertIn("class Events extends S3D.Group", events)
        self.assertIn("addItem", props)
        self.assertIn("addItem", events)
        self.assertIn("renderer?.box", props_item)
        self.assertIn("renderer?.box", event_item)

    def test_structure_playback_uses_library_instance(self):
        adapter = (STATIC / "playback_runtime.js").read_text(encoding="utf-8")
        self.assertIn("new window.S3D.Playback", adapter)
        self.assertIn("clock: playbackClock", adapter)
        self.assertIn("playbackClock.step()", adapter)
        self.assertNotIn("manualAdvanceMs += next - current", adapter)

    def test_structure_adapter_instantiates_events_props_anchors_and_links(self):
        adapter = (STATIC / "structure_s3d_adapter.js").read_text(encoding="utf-8")
        for token in (
            "new S3D.SceneObject",
            "new S3D.Events",
            "new S3D.EventItem",
            "new S3D.Props",
            "new S3D.PropsItem",
            "new S3D.Anchor",
            "new S3D.Link",
            "new S3D.Pulse",
        ):
            with self.subTest(token=token):
                self.assertIn(token, adapter)
        self.assertIn("drawSceneProjection3D = function drawSceneProjectionViaS3D", adapter)
        self.assertIn("drawGenericLinks3D = function drawGenericLinksViaS3D", adapter)

    def test_structure_semantics_stay_outside_library_boundary(self):
        adapter = (STATIC / "structure_s3d_adapter.js").read_text(encoding="utf-8")
        library = "\n".join(
            path.read_text(encoding="utf-8")
            for path in LIB.rglob("*.js")
            if path.name != "benchmark_panel.js"
        )
        self.assertIn("propertyDisplayName", adapter)
        self.assertIn("activeLinkProperties", adapter)
        self.assertNotIn("propertyDisplayName", library)
        self.assertNotIn("activeLinkProperties", library)

    def test_render_store_collects_boxes_lines_and_glyphs_without_semantics(self):
        source = (LIB / "render_store.js").read_text(encoding="utf-8")
        self.assertIn("class RenderStore", source)
        self.assertIn("solidBoxes", source)
        self.assertIn("outlineBoxes", source)
        self.assertIn("lineVertices", source)
        self.assertIn("glyphs", source)
        self.assertIn("box(position, scale, color", source)
        self.assertIn("line(start, end, color)", source)
        self.assertIn("glyph(center, size, uvRect, color)", source)

    def test_webgl_production_renderer_is_instanced_and_batched(self):
        source = (LIB / "webgl_batch_renderer.js").read_text(encoding="utf-8")
        self.assertIn("class WebGLBatchRenderer", source)
        self.assertIn("gl.vertexAttribDivisor", source)
        self.assertIn("gl.drawElementsInstanced", source)
        self.assertIn("gl.drawArrays(gl.LINES", source)
        self.assertIn("class GlyphAtlas", source)
        self.assertIn("gl.drawArraysInstanced(gl.TRIANGLE_STRIP", source)
        self.assertNotIn("property_type_ref", source)
        self.assertNotIn("ruleset_ref", source)

    def test_structure_render_bridge_batches_existing_projection_calls(self):
        source = (STATIC / "structure_render_batch.js").read_text(encoding="utf-8")
        self.assertIn("new S3D.WebGLBatchRenderer(gl)", source)
        self.assertIn("drawBox = function drawBoxBatched", source)
        self.assertIn("drawLine = function drawLineBatched", source)
        self.assertIn("drawSceneText3D = function drawSceneText3DBatched", source)
        self.assertIn("renderer.begin(viewProjection())", source)
        self.assertIn("renderer.flush(cameraRight(), cameraUp())", source)

    def test_structure_frame_cache_memoizes_expensive_projection_work_once_per_frame(self):
        source = (STATIC / "structure_frame_cache.js").read_text(encoding="utf-8")
        for token in (
            "canonicalIndexCached",
            "linkPropertiesCached",
            "activeLinkPropertiesCached",
            "visibleEntityIdsCached",
            "buildSceneLayoutsCached",
            "linkSlotsCached",
            "allEventRoutesCached",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertIn("function resetFrame()", source)
        self.assertIn("render = function renderWithFrameCache()", source)
        self.assertIn("window.StructureFrameCache", source)

    def test_dynamic_adapter_renderer_cache_and_real_benchmark_assets_are_served(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        playback = (STATIC / "playback_runtime.js").read_text(encoding="utf-8")
        paths = (
            "/static/3d/renderer.js",
            "/static/structure_s3d_adapter.js",
            "/static/structure_frame_cache.js",
            "/static/3d/render_store.js",
            "/static/3d/webgl_batch_renderer.js",
            "/static/structure_render_batch.js",
            "/static/3d/benchmark.js",
            "/static/structure_benchmark.js",
            "/static/3d/benchmark_panel.js",
        )
        for path in paths:
            self.assertIn(path, app)
            self.assertIn(path, playback)
        self.assertLess(playback.index("/static/structure_s3d_adapter.js"), playback.index("/static/structure_frame_cache.js"))
        self.assertLess(playback.index("/static/structure_frame_cache.js"), playback.index("/static/structure_render_batch.js"))
        self.assertNotIn("loadStructureScript('/static/3d/benchmark_webgl.js')", playback)

    def test_gpu_microbenchmark_remains_instanced_batched_baseline(self):
        source = (LIB / "benchmark_webgl.js").read_text(encoding="utf-8")
        benchmark = (LIB / "benchmark.js").read_text(encoding="utf-8")
        self.assertIn("nodes: 20000", benchmark)
        self.assertIn("gl.drawArraysInstanced", source)
        self.assertIn("gl.vertexAttribDivisor(1, 1)", source)
        self.assertIn("gl.drawArrays(gl.LINES", source)
        self.assertIn("camera-only frame: 0 object uploads", source)

    def test_real_benchmark_builds_normal_structure_nodes_props_events_effects_and_links(self):
        source = (STATIC / "structure_benchmark.js").read_text(encoding="utf-8")
        self.assertIn("workspace.entities = [trigger, ...nodes.map(item => item.entity)]", source)
        self.assertIn("'data', 'RULESET_DATA'", source)
        self.assertIn("'event', 'RULESET_EVENT'", source)
        self.assertIn("'effect', 'RULESET_EFFECT'", source)
        self.assertIn("'RULESET_LINK_EVENT_EFFECT'", source)
        self.assertIn("'RULESET_LINK_EFFECT_TARGET'", source)
        self.assertIn("'RULESET_LINK_EVENT_CAUSE'", source)
        self.assertIn("'RULESET_LINK_DEPENDENCY'", source)
        self.assertNotIn("new S3D.WebGLBenchmark", source)

    def test_real_benchmark_has_left_trigger_entity_and_uses_normal_causal_trigger(self):
        source = (STATIC / "structure_benchmark.js").read_text(encoding="utf-8")
        self.assertIn("const triggerId = 'BENCH_TRIGGER'", source)
        self.assertIn("entity(triggerId, 'TRIGGER', [minX - 5.0, 0, 0]", source)
        self.assertIn("triggerEventRef: 'EVENT_BENCH_TRIGGER'", source)
        self.assertIn("triggerCausalProjection(BENCH.triggerEventRef)", source)
        self.assertIn("RULESET_LINK_EVENT_CAUSE", source)
        self.assertIn("causalProjection.maxDepth", source)

    def test_real_benchmark_is_temporary_and_restores_original_workspace(self):
        source = (STATIC / "structure_benchmark.js").read_text(encoding="utf-8")
        self.assertIn("workspace: ws", source)
        self.assertIn("ws = built.workspace", source)
        self.assertIn("ws = previous.workspace", source)
        self.assertIn("benchmark stopped · workspace restored", source)

    def test_benchmark_is_hidden_in_settings_with_100_to_20k_slider_and_live_metrics(self):
        panel = (LIB / "benchmark_panel.js").read_text(encoding="utf-8")
        self.assertIn("document.querySelector('#settings')", panel)
        self.assertIn("S3D Benchmark", panel)
        self.assertIn("min: '100'", panel)
        self.assertIn("max: '20000'", panel)
        self.assertIn("step: '100'", panel)
        self.assertIn("Run real Structure benchmark", panel)
        self.assertIn("STRUCTURE BENCHMARK", panel)
        self.assertIn("fps", panel)
        self.assertIn("draw_calls", panel)
        self.assertIn("buffer uploads", panel)
        self.assertNotIn("s3dBenchmarkCanvas", panel)


if __name__ == "__main__":
    unittest.main()
