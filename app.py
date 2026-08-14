from __future__ import annotations

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from base_visual_projections import PROJECTIONS, build_projection
from nanocms import projection
from primitive_registry import load_registry
from session_cache import cache_stats
from session_engine import build_session_scene, load_masters, normalize_sources, session_catalog
from source_adapter import list_branches
from source_selection import browse_directories, source_spec_from_query
from structure_runtime import APP_HOST, APP_PORT, SUGGESTED_SOURCE_REPO, StructureError
from view_rules import ViewRuleError, binding_children, binding_tree


BASE_DIR = os.path.dirname(__file__)
STRUCTURE_HTML = os.path.join(BASE_DIR, "static", "structure.html")
RENDERER_JS = os.path.join(BASE_DIR, "static", "renderer.js")
SOURCE_SELECT_UI_JS = os.path.join(BASE_DIR, "static", "source_select_ui.js")
SOURCE_PICKER_BROWSE_JS = os.path.join(BASE_DIR, "static", "source_picker_browse.js")
EVENT_TRACE_VIEWER_JS = os.path.join(BASE_DIR, "static", "event_trace_viewer.js")
SESSION_UI_JS = os.path.join(BASE_DIR, "static", "session_ui.js")
DIAGNOSTICS_UI_JS = os.path.join(BASE_DIR, "static", "diagnostics_ui.js")


def _file_payload(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def _session_result(body: dict) -> dict:
    masters = load_masters(normalize_sources(body))
    instances = body.get("instances")
    if not isinstance(instances, list) or not instances or not all(isinstance(item, dict) for item in instances):
        raise ValueError("POST /api/scene requires a non-empty instances array of objects")

    result = build_session_scene(masters, instances, build_projection)
    errors: list[dict] = []
    warnings: list[dict] = []
    valid = True
    projectable = True
    for master in masters.values():
        tree = master["tree"]
        errors.extend(tree.get("errors", []))
        warnings.extend(tree.get("warnings", []))
        valid = valid and bool(tree.get("valid"))
        projectable = projectable and bool(tree.get("projectable"))

    result.update({
        "valid": valid and not errors,
        "projectable": projectable,
        "degraded": bool(errors or warnings or not valid),
        "finding_count": len(errors) + len(warnings),
        "errors": errors,
        "warnings": warnings,
        "ruleset": "structure_session",
        "projection_policy": "canonical_findings_are_visible_not_blocking",
    })
    return result


def _query_master(query: dict[str, list[str]]) -> dict:
    source = source_spec_from_query(query)
    return load_masters([{"id": "master-1", "name": "master-1", "source": source}])["master-1"]


class Handler(BaseHTTPRequestHandler):
    server_version = "Structure/0.34.0"

    def _write_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _write_body(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _write_file(self, path: str, content_type: str) -> None:
        self._write_body(_file_payload(path), content_type)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON request body must be an object")
        return data

    def _error(self, exc: Exception) -> None:
        payload = exc.as_dict() if isinstance(exc, StructureError) else {
            "id": "STRUCTURE_REQUEST_FAILED",
            "message": str(exc),
            "type": type(exc).__name__,
        }
        self._write_json({"ok": False, "error": payload}, 400)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/":
                return self._write_file(STRUCTURE_HTML, "text/html; charset=utf-8")
            static_routes = {
                "/static/renderer.js": RENDERER_JS,
                "/static/source_select_ui.js": SOURCE_SELECT_UI_JS,
                "/static/source_picker_browse.js": SOURCE_PICKER_BROWSE_JS,
                "/static/event_trace_viewer.js": EVENT_TRACE_VIEWER_JS,
                "/static/session_ui.js": SESSION_UI_JS,
                "/static/diagnostics_ui.js": DIAGNOSTICS_UI_JS,
            }
            if path in static_routes:
                return self._write_file(static_routes[path], "application/javascript; charset=utf-8")
            if path == "/api/health":
                return self._write_json({
                    "ok": True,
                    "server": self.server_version,
                    "startup": "empty",
                    "projection_api": "POST /api/scene only",
                    "projection_contract": ["projection_base", "projection_style", "scope_type", "scope_ref", "scope_style", "projection_dimension"],
                    "projection_generators": sorted(PROJECTIONS),
                    "compatibility_aliases": False,
                    "automatic_source_read": False,
                    "automatic_projection": False,
                    "structure_tree_indexes": "resolved_once_at_import",
                    "source_cache": cache_stats(),
                    "cross_master_inference": False,
                })
            if path == "/api/primitives":
                return self._write_json(load_registry())
            if path == "/api/branches":
                repo = (query.get("repo") or [SUGGESTED_SOURCE_REPO])[0]
                return self._write_json({"repository": repo, "branches": list_branches(repo)})
            if path == "/api/directories":
                return self._write_json(browse_directories((query.get("path") or [None])[0]))
            if path == "/api/nanocms":
                return self._write_json(projection(query.get("page", ["canonical"])[0]))
            if path == "/api/projection-catalog":
                master = _query_master(query)
                catalog = session_catalog({"master-1": master})
                catalog["relation_depth"] = {"min": 0, "max": 32, "default": 0}
                return self._write_json(catalog)
            if path == "/api/binding-tree":
                master = _query_master(query)
                return self._write_json(binding_tree(
                    master["graph"],
                    root=query.get("root", [None])[0],
                    depth=int(query.get("depth", ["1"])[0]),
                    budget=int(query.get("budget", ["1500"])[0]),
                ))
            if path == "/api/binding-children":
                master = _query_master(query)
                return self._write_json(binding_children(master["graph"], node_id=query.get("node", [None])[0]))
            return self._write_json({"ok": False, "error": {"id": "STRUCTURE_NOT_FOUND", "message": path}}, 404)
        except (StructureError, ViewRuleError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return self._error(exc)

    def do_POST(self) -> None:
        try:
            if urllib.parse.urlparse(self.path).path != "/api/scene":
                return self._write_json({"ok": False, "error": {"id": "STRUCTURE_NOT_FOUND", "message": self.path}}, 404)
            result = _session_result(self._read_json_body())
            return self._write_json(result, 200 if result.get("projectable") else 422)
        except (StructureError, ViewRuleError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return self._error(exc)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), Handler)
    print(f"Structure listening on http://{APP_HOST}:{APP_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
