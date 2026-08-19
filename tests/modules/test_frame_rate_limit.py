from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"


class FrameRateLimitTests(unittest.TestCase):
    def test_frame_rate_limit_is_served_and_bootstrapped(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        playback = (STATIC / "playback_runtime.js").read_text(encoding="utf-8")
        self.assertIn('"/static/frame_rate_limit.js"', app)
        self.assertIn("loadStructureScript('/static/frame_rate_limit.js')", playback)

    def test_default_is_25_with_requested_settings_options(self):
        source = (STATIC / "frame_rate_limit.js").read_text(encoding="utf-8")
        self.assertIn("const DEFAULT_FPS = 25", source)
        self.assertIn("[15, 25, 30, 60, 120, 0]", source)
        self.assertIn("option.textContent = value === 0 ? 'Display' : String(value)", source)
        self.assertIn("select.id = 'frameRateLimit'", source)

    def test_cap_only_schedules_render_and_does_not_touch_playback_semantics(self):
        source = (STATIC / "frame_rate_limit.js").read_text(encoding="utf-8")
        self.assertIn("requestAnimationFrame(render)", source)
        self.assertNotIn("playbackClock", source)
        self.assertNotIn("event_activation_duration", source)
        self.assertNotIn("canonical", source.lower().replace("canonical semantics", ""))


if __name__ == "__main__":
    unittest.main()
