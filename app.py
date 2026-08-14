from __future__ import annotations

import json
import os
import urllib.parse
from http.server import ThreadingHTTPServer

from canonical_projections import PROJECTIONS as CORE_PROJECTIONS, build_canonical_projection
from canonical_projections_extra3d import PROJECTIONS as EXTRA_PROJECTIONS, build_projection as build_extra_projection
from dependency_flow_projection import build_dependency_flow_3d
from event_trace import build_event_surface
from input_modules.canonical import read as read_canonical
from input_modules.raw_json import read as read_raw_json
from nanocms import projection, resolve_page, resolve_view
from primitive_registry import load_registry
from raw_json_projection import build_raw_json_space_3d
from scene_composer import compose_scene
from scene_contract import projection_to_scene, validate_scene
from semantic_visual_projections import PROJECTIONS as SEMANTIC_VISUAL_PROJECTIONS, build_visual_projection
from session_engine import build_session_scene, load_masters, normalize_sources, session_catalog
from source_adapter import list_branches
from source_selection import browse_directories, load_source, source_spec_from_query
from structure_reveal_projections import PROJECTIONS as STRUCTURE_REVEAL_PROJECTIONS, build_projection as build_structure_reveal_projection
from structure_tree import tree_to_graph
from structureprojector import APP_HOST, APP_PORT, SOURCE_REPO, Handler as BaseHandler, ProjectorError
from view_rules import ViewRuleError, binding_children, binding_tree

BASE_DIR = os.path.dirname(__file__)
SCENE_VIEWER_HTML = os.path.join(BASE_DIR, 'static', 'scene_viewer_v4.html')
SCENE_VIEWER_JS = os.path.join(BASE_DIR, 'static', 'scene_viewer_v4.js')
SOURCE_SELECT_UI_JS = os.path.join(BASE_DIR, 'static', 'source_select_ui.js')
SOURCE_PICKER_BROWSE_JS = os.path.join(BASE_DIR, 'static', 'source_picker_browse.js')
EVENT_TRACE_VIEWER_JS = os.path.join(BASE_DIR, 'static', 'event_trace_viewer.js')
SESSION_UI_JS = os.path.join(BASE_DIR, 'static', 'session_ui.js')
DIAGNOSTICS_UI_JS = os.path.join(BASE_DIR, 'static', 'diagnostics_ui.js')

ALL_CANONICAL_PROJECTIONS = {
    **CORE_PROJECTIONS,
    **EXTRA_PROJECTIONS,
    **STRUCTURE_REVEAL_PROJECTIONS,
    **SEMANTIC_VISUAL_PROJECTIONS,
}


def _file_payload(path: str) -> bytes:
    with open(path, 'rb') as handle:
        return handle.read()


def _viewer_js_payload() -> bytes:
    text = _file_payload(SCENE_VIEWER_JS).decode('utf-8')
    empty_bootstrap = '''(function initEmptyStructure(){
  try {
    S.catalog = null;
    S.scene = null;
    S.source = null;
    S.instances = [];
    S.objectState = {};
    S.objectStyle = {};
    S.channelState = {};
    S.renderer = new Renderer($('#gl'));
    bindStatic();
    renderInstances();
    renderChannels();
    $('#revision').textContent = '';
    $('#sceneInfo').textContent = 'Choose a source. The first selected source becomes the first master.';
    $('#error').textContent = 'None.';
    setStatus('choose source');
    syncView();
    draw();
  } catch (e) { showError(e); }
})();'''
    stripped = text.rstrip()
    if stripped.endswith('init();'):
        return (stripped[:-len('init();')] + empty_bootstrap + '\n').encode('utf-8')
    if 'initEmptyStructure' in text:
        return text.encode('utf-8')
    raise RuntimeError('scene_viewer_v4.js startup call not found')


def _build_canonical_projection(graph: dict, projection_id: str) -> dict:
    if projection_id in SEMANTIC_VISUAL_PROJECTIONS:
        return build_visual_projection(graph, projection_id)
    if projection_id in STRUCTURE_REVEAL_PROJECTIONS:
        return build_structure_reveal_projection(graph, projection_id)
    if projection_id == 'dependency_flow_3d':
        return build_dependency_flow_3d(graph)
    if projection_id in EXTRA_PROJECTIONS:
        return build_extra_projection(graph, projection_id)
    return build_canonical_projection(graph, projection_id)


def _result_from_tree(tree: dict, ruleset: str) -> dict:
    tree_validation = list(tree.get('validation_errors', []))
    errors = list(tree.get('errors', [])) + tree_validation
    return {
        'valid': bool(tree.get('valid')),
        'projectable': bool(tree.get('projectable')),
        'ruleset': ruleset,
        'source': tree.get('source', {}),
        'structure_tree': tree,
        'graph': tree_to_graph(tree),
        'errors': errors,
        'warnings': list(tree.get('warnings', [])),
    }


def _attach_scene(result: dict, base_projection: dict) -> None:
    result['projection'] = base_projection
    scene = projection_to_scene(base_projection, result['structure_tree'])
    scene['event_surface'] = build_event_surface(result['structure_tree'])
    result['scene'] = scene
    scene_errors = validate_scene(scene)
    if scene_errors:
        result.setdefault('errors', []).extend(scene_errors)
        result['valid'] = False


def _build_result(snapshot, page: str, view: str | None = None) -> dict:
    if page == 'raw-json':
        tree = read_raw_json(snapshot, {'path': view} if view else None)
        result = _result_from_tree(tree, 'raw_json_syntax')
        _attach_scene(result, build_raw_json_space_3d(result['graph']))
        return result
    tree = read_canonical(snapshot)
    result = _result_from_tree(tree, 'canonical_contract')
    selected_view = resolve_view(page, view)
    _attach_scene(result, _build_canonical_projection(result['graph'], selected_view['projection_id']))
    return result


def _compose_scene_result(snapshot, page: str, views: list[str]) -> dict:
    tree = read_canonical(snapshot)
    result = _result_from_tree(tree, 'canonical_contract')
    selected_views = [resolve_view(page, view_id) for view_id in views]
    projections = [_build_canonical_projection(result['graph'], item['projection_id']) for item in selected_views]
    scene = compose_scene(projections, tree)
    scene['event_surface'] = build_event_surface(tree)
    result['scene'] = scene
    result['views'] = selected_views
    return result


def _session_result(body: dict) -> dict:
    masters = load_masters(normalize_sources(body))
    instances = body.get('instances')
    if not isinstance(instances, list) or not instances or not all(isinstance(item, dict) for item in instances):
        raise ValueError('POST /api/scene requires a non-empty instances array of objects')

    result = build_session_scene(masters, instances, _build_canonical_projection)
    errors, warnings = [], []
    valid = projectable = True
    for master in masters.values():
        tree = master['tree']
        errors.extend(tree.get('errors', []))
        warnings.extend(tree.get('warnings', []))
        valid = valid and bool(tree.get('valid'))
        projectable = projectable and bool(tree.get('projectable'))

    result.update({
        'valid': valid and not errors,
        'projectable': projectable,
        'degraded': bool(errors or warnings or not valid),
        'finding_count': len(errors) + len(warnings),
        'errors': errors,
        'warnings': warnings,
        'ruleset': 'structure_session',
        'projection_policy': 'canonical_findings_are_visible_not_blocking',
    })
    return result


class Handler(BaseHandler):
    server_version = 'Structure/0.30.0'

    def _write_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_body(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_file(self, path: str, content_type: str) -> None:
        self._write_body(_file_payload(path), content_type)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get('Content-Length', '0') or 0)
        if length <= 0:
            return {}
        data = json.loads(self.rfile.read(length).decode('utf-8'))
        if not isinstance(data, dict):
            raise ValueError('JSON request body must be an object')
        return data

    def _error(self, exc: Exception) -> None:
        payload = exc.as_dict() if isinstance(exc, ProjectorError) else {
            'id': 'SP_REQUEST_FAILED',
            'message': str(exc),
            'type': type(exc).__name__,
        }
        self._write_json({'ok': False, 'error': payload}, 400)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == '/':
                return self._write_file(SCENE_VIEWER_HTML, 'text/html; charset=utf-8')
            if path == '/static/scene_viewer_v4.js':
                return self._write_body(_viewer_js_payload(), 'application/javascript; charset=utf-8')
            if path == '/static/source_select_ui.js':
                return self._write_file(SOURCE_SELECT_UI_JS, 'application/javascript; charset=utf-8')
            if path == '/static/source_picker_browse.js':
                return self._write_file(SOURCE_PICKER_BROWSE_JS, 'application/javascript; charset=utf-8')
            if path == '/static/event_trace_viewer.js':
                return self._write_file(EVENT_TRACE_VIEWER_JS, 'application/javascript; charset=utf-8')
            if path == '/static/session_ui.js':
                return self._write_file(SESSION_UI_JS, 'application/javascript; charset=utf-8')
            if path == '/static/diagnostics_ui.js':
                return self._write_file(DIAGNOSTICS_UI_JS, 'application/javascript; charset=utf-8')
            if path == '/api/health':
                return self._write_json({
                    'ok': True,
                    'server': self.server_version,
                    'startup': 'empty',
                    'automatic_source_read': False,
                    'automatic_projection': False,
                    'first_selected_source_becomes_first_master': True,
                    'multi_master': True,
                    'projection_master_cardinality': 'source 1:N projection',
                    'projection_contract': ['projection_base', 'projection_style', 'scope_type', 'scope_ref', 'scope_style', 'projection_dimension'],
                    'projection_bases': ['map', 'event', 'dependency', 'relation', 'authority', 'ownership', 'containment'],
                    'projection_styles_are_base_compatible': True,
                    'scope_style_is_color_only': True,
                    'structure_tree_indexes': 'resolved_once_at_import',
                    'visual_dimensions': ['2d', '3d'],
                    'selectable_sources': ['github', 'directory'],
                    'directory_browser': True,
                    'event_trace_causality': 'explicit_only',
                    'cross_master_inference': False,
                    'diagnostics': 'structured',
                    'legacy_frontend_overlays': False,
                })
            if path == '/api/primitives':
                return self._write_json(load_registry())
            if path == '/api/branches':
                repo = (query.get('repo') or [SOURCE_REPO])[0]
                return self._write_json({'repository': repo, 'branches': list_branches(repo)})
            if path == '/api/directories':
                return self._write_json(browse_directories((query.get('path') or [None])[0]))
            if path == '/api/nanocms':
                return self._write_json(projection(query.get('page', ['canonical'])[0]))
            if path == '/api/projection-catalog':
                snapshot = load_source(source_spec_from_query(query))
                tree = read_canonical(snapshot)
                masters = {
                    'master-1': {
                        'id': 'master-1',
                        'name': 'master-1',
                        'source_spec': {},
                        'snapshot': snapshot,
                        'tree': tree,
                        'graph': tree_to_graph(tree),
                    }
                }
                catalog = session_catalog(masters)
                catalog['relation_depth'] = {'min': 0, 'max': 32, 'default': 0}
                return self._write_json(catalog)
            if path == '/api/scene':
                page = query.get('page', ['canonical'])[0]
                views = [part for part in query.get('views', [''])[0].split(',') if part]
                if not views:
                    views = [item['id'] for item in resolve_page(page).get('placements', [])[:2]]
                result = _compose_scene_result(load_source(source_spec_from_query(query)), page, views)
                return self._write_json(result, 200 if result.get('projectable') else 422)
            if path == '/api/project':
                result = _build_result(
                    load_source(source_spec_from_query(query)),
                    query.get('page', ['canonical'])[0],
                    query.get('view', [None])[0],
                )
                return self._write_json(result, 200 if result.get('projectable') else 422)
            if path == '/api/binding-tree':
                tree = read_canonical(load_source(source_spec_from_query(query)))
                return self._write_json(binding_tree(
                    tree_to_graph(tree),
                    root=query.get('root', [None])[0],
                    depth=int(query.get('depth', ['1'])[0]),
                    budget=int(query.get('budget', ['1500'])[0]),
                ))
            if path == '/api/binding-children':
                tree = read_canonical(load_source(source_spec_from_query(query)))
                return self._write_json(binding_children(tree_to_graph(tree), node_id=query.get('node', [None])[0]))
            return super().do_GET()
        except (ProjectorError, ViewRuleError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return self._error(exc)

    def do_POST(self) -> None:
        try:
            if urllib.parse.urlparse(self.path).path != '/api/scene':
                return self._write_json({'ok': False, 'error': {'id': 'SP_NOT_FOUND', 'message': self.path}}, 404)
            result = _session_result(self._read_json_body())
            return self._write_json(result, 200 if result.get('projectable') else 422)
        except (ProjectorError, ViewRuleError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return self._error(exc)


def main() -> None:
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), Handler)
    print(f'Structure listening on http://{APP_HOST}:{APP_PORT}')
    server.serve_forever()


if __name__ == '__main__':
    main()
