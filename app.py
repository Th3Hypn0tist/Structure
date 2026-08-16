from __future__ import annotations

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server.test_runner import run_startup_suite
from server.workspace import WorkspaceStore, starting_workspace

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
HOST = os.environ.get("STRUCTURE_HOST", "127.0.0.1")
PORT = int(os.environ.get("STRUCTURE_PORT", "8765"))
STORE = WorkspaceStore(os.path.join(BASE_DIR, "workspace.json"))
STATIC = {
    "/": ("structure.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/static/entity_editor.js": ("entity_editor.js", "application/javascript; charset=utf-8"),
    "/static/causal_projection.js": ("causal_projection.js", "application/javascript; charset=utf-8"),
    "/static/view_projection.js": ("view_projection.js", "application/javascript; charset=utf-8"),
    "/static/style.css": ("style.css", "text/css; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "Structure/0.2.0"

    def _body(self) -> dict:
        size = int(self.headers.get("Content-Length", "0") or 0)
        if not size:
            return {}
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

    def _file(self, filename: str, content_type: str) -> None:
        path = os.path.join(STATIC_DIR, filename)
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
                return self._file(filename, content_type)
            if path == "/api/health":
                return self._json({"ok": True, "service": "Structure", "version": "0.2.0"})
            if path == "/api/workspace":
                return self._json({"ok": True, "workspace": STORE.load()})
            if path == "/api/starting-scene":
                return self._json({"ok": True, "workspace": STORE._validate(starting_workspace())})
            return self._json({"ok": False, "error": "not_found"}, 404)
        except Exception as exc:
            return self._json({"ok": False, "error": str(exc)}, 400)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/workspace":
                workspace = STORE.save(self._body())
                return self._json({"ok": True, "workspace": workspace})
            return self._json({"ok": False, "error": "not_found"}, 404)
        except Exception as exc:
            return self._json({"ok": False, "error": str(exc)}, 400)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[structure] {self.address_string()} {fmt % args}")


def main() -> None:
    run_startup_suite()
    print(f"Structure 0.2.0 -> http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
