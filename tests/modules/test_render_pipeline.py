from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"


class RenderPipelineTests(unittest.TestCase):
    def source(self, name: str) -> str:
        return (STATIC / name).read_text(encoding="utf-8")

    def test_pipeline_is_only_render_raf_scheduler(self):
        app = self.source("app.js")
        pipeline = self.source("render_pipeline.js")
        batch = self.source("structure_render_batch.js")
        benchmark = self.source("structure_benchmark.js")

        self.assertNotIn("requestAnimationFrame(render)", app)
        self.assertNotIn("requestAnimationFrame(render)", batch)
        self.assertNotIn("globalThis.render =", benchmark)
        self.assertNotIn("render = function", benchmark)
        self.assertIn("requestAnimationFrame(render)", pipeline)
        self.assertIn("render = renderDispatcher", pipeline)

    def test_benchmark_metrics_are_pipeline_hooks(self):
        pipeline = self.source("render_pipeline.js")
        benchmark = self.source("structure_benchmark.js")
        self.assertIn("addAfterFrame", pipeline)
        self.assertIn("addBeforeFrame('benchmark-metrics-start'", benchmark)
        self.assertIn("addAfterFrame('benchmark-metrics-end'", benchmark)

    def test_pipeline_starts_only_after_workspace_exists(self):
        pipeline = self.source("render_pipeline.js")
        self.assertIn("function startWhenWorkspaceReady()", pipeline)
        self.assertIn("typeof ws !== 'undefined' && ws", pipeline)
        self.assertIn("window.addEventListener('load', startWhenWorkspaceReady", pipeline)


if __name__ == "__main__":
    unittest.main()
