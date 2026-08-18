from __future__ import annotations

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server.abstractions import AbstractionLibrary
from server.test_runner import run_startup_suite
from server.workspace import WORKSPACE_VERSION, WorkspaceStore, starting_workspace

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
HOST = os.environ.get("STRUCTURE_HOST", "127.0.0.1")
PORT = int(os.environ.get("STRUCTURE_PORT", "8765"))
STORE = WorkspaceStore(os.path.join(BASE_DIR, "workspace.json"))
ABSTRACTIONS = AbstractionLibrary(os.path.join(BASE_DIR, "library", "abstractions"))
STATIC = {
    "/": ("structure.html", "text/html; charset=utf-8"),
    "/static/3d/core.js": ("3d/core.js", "application/javascript; charset=utf-8"),
    "/static/3d/math.js": ("3d/math.js", "application/javascript; charset=utf-8"),
    "/static/3d/renderer.js": ("3d/renderer.js", "application/javascript; charset=utf-8"),
    "/static/3d/render_store.js": ("3d/render_store.js", "application/javascript; charset=utf-8"),
    "/static/3d/webgl_batch_renderer.js": ("3d/webgl_batch_renderer.js", "application/javascript; charset=utf-8"),
    "/static/3d/benchmark.js": ("3d/benchmark.js", "application/javascript; charset=utf-8"),
    "/static/3d/benchmark_webgl.js": ("3d/benchmark_webgl.js", "application/javascript; charset=utf-8"),
    "/static/3d/benchmark_panel.js": ("3d/benchmark_panel.js", "application/javascript; charset=utf-8"),
    "/static/3d/objects/object.js": ("3d/objects/object.js", "application/javascript; charset=utf-8"),
    "/static/3d/objects/primitives.js": ("3d/objects/primitives.js", "application/javascript; charset=utf-8"),
    "/static/3d/objects/anchors.js": ("3d/objects/anchors.js", "application/javascript; charset=utf-8"),
    "/static/3d/objects/links.js": ("3d/objects/links.js", "application/javascript; charset=utf-8"),
    "/static/3d/objects/props_item.js": ("3d/objects/props_item.js", "application/javascript; charset=utf-8"),
    "/static/3d/objects/props.js": ("3d/objects/props.js", "application/javascript; charset=utf-8"),
    "/static/3d/objects/event_item.js": ("3d/objects/event_item.js", "application/javascript; charset=utf-8"),
    "/static/3d/objects/events.js": ("3d/objects/events.js", "application/javascript; charset=utf-8"),
    "/static/3d/objects/pulse.js": ("3d/objects/pulse.js", "application/javascript; charset=utf-8"),
    "/static/3d/objects/highlight.js": ("3d/objects/highlight.js", "application/javascript; charset=utf-8"),
    "/static/structure_s3d_adapter.js": ("structure_s3d_adapter.js", "application/javascript; charset=utf-8"),
    "/static/structure_frame_cache.js": ("structure_frame_cache.js", "application/javascript; charset=utf-8"),
    "/static/structure_render_batch.js": ("structure_render_batch.js", "application/javascript; charset=utf-8"),
    "/static/structure_benchmark.js": ("structure_benchmark.js", "application/javascript; charset=utf-8"),
    "/static/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/static/scene_ui_3d.js": ("scene_ui_3d.js", "application/javascript; charset=utf-8"),
    "/static/entity_editor.js": ("entity_editor.js", "application/javascript; charset=utf-8"),
    "/static/playback_runtime.js": ("playback_runtime.js", "application/javascript; charset=utf-8"),
    "/static/causal_projection.js": ("causal_projection.js", "application/javascript; charset=utf-8"),
    "/static/projection_visibility.js": ("projection_visibility.js", "application/javascript; charset=utf-8"),
    "/static/event_rule_editor.js": ("event_rule_editor.js", "application/javascript; charset=utf-8"),
    "/static/canonical_deletion.js": ("canonical_deletion.js", "application/javascript; charset=utf-8"),
    "/static/abstraction_library.js": ("abstraction_library.js", "application/javascript; charset=utf-8"),
    "/static/link_projection.js": ("link_projection.js", "application/javascript; charset=utf-8"),
    "/static/style.css": ("style.css", "text/css; charset=utf-8"),
}
IMAGES = {
    "/images/AIGM-LOGO-tight.png": ("AIGM-LOGO-tight.png", "image/png"),
}


class Handler(BaseHTTPRequestHandler):
    server_version = f"Structure/{WORKSPACE_VERSION}"

    def _body(self) -> dict:
        size = int(self.headers.get("Content-Length", "0") or 0)
        if not size:
            raise ValueError("request body is required")
        payload = json.loads(self.rfile.read(size).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _file(self, directory: str, filename: str, content_type: str) -> None:
        path = os.path.join(directory, filename)
        with open(path, "rb") as fh:
            raw = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path in STATIC:
                filename, content_type = STATIC[path]
                return self._file(STATIC_DIR, filename, content_type)
            if path in IMAGES:
                filename, content_type = IMAGES[path]
                return self._file(IMAGES_DIR, filename, content_type)
            if path == "/api/health":
                return self._json({"ok": True, "service": "Structure", "version": WORKSPACE_VERSION})
            if path == "/api/workspace":
                return self._json({"ok": True, "workspace": STORE.load()})
            if path == "/api/starting-scene":
                return self._json({"ok": True, "workspace": STORE._validate(starting_workspace())})
            if path == "/api/abstractions":
                return self._json({"ok": True, "abstractions": ABSTRACTIONS.list()})
            if path.startswith("/api/abstractions/"):
                abstraction_id = urllib.parse.unquote(path.removeprefix("/api/abstractions/"))
                return self._json({"ok": True, "abstraction": ABSTRACTIONS.get(abstraction_id)})
            return self._json({"ok": False, "error": "not_found"}, 404)
        except FileNotFoundError as exc:
            return self._json({"ok": False, "error": str(exc)}, 404)
        except Exception as exc:
            return self._json({"ok": False, "error": str(exc)}, 400)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/workspace":
                workspace = STORE.save(self._body())
                return self._json({"ok": True, "workspace": workspace})
            if path == "/api/abstractions":
                abstraction = ABSTRACTIONS.publish(self._body())
                return self._json({"ok": True, "abstraction": abstraction}, 201)
            return self._json({"ok": False, "error": "not_found"}, 404)
        except FileExistsError as exc:
            return self._json({"ok": False, "error": str(exc)}, 409)
        except Exception as exc:
            return self._json({"ok": False, "error": str(exc)}, 400)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[structure] {self.address_string()} {fmt % args}")


def main() -> None:
    run_startup_suite()
    print(f"Structure {WORKSPACE_VERSION} -> http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
