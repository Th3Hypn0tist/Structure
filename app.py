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
from projection_instances import style_catalog, topic_catalog
from raw_json_projection import build_raw_json_space_3d
from scene_composer import compose_scene
from scene_contract import projection_to_scene, validate_scene
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
SCENE_VIEWER_CARDS_JS = os.path.join(BASE_DIR, 'static', 'scene_viewer_v4_cards.js')
SOURCE_PICKER_BROWSE_JS = os.path.join(BASE_DIR, 'static', 'source_picker_browse.js')
EVENT_TRACE_VIEWER_JS = os.path.join(BASE_DIR, 'static', 'event_trace_viewer.js')
LEGACY_INDEX_HTML = os.path.join(BASE_DIR, 'static', 'scene_viewer_v31.html')

ALL_CANONICAL_PROJECTIONS = {**CORE_PROJECTIONS, **EXTRA_PROJECTIONS, **STRUCTURE_REVEAL_PROJECTIONS}


def _file_payload(path: str) -> bytes:
    with open(path, 'rb') as handle:
        return handle.read()


def _viewer_html_payload() -> bytes:
    text = _file_payload(SCENE_VIEWER_HTML).decode('utf-8')
    text = text.replace('<title>StructureProjector</title>', '<title>Structure</title>')
    text = text.replace('<header><strong>StructureProjector</strong>', '<header><strong>Structure</strong>')
    text = text.replace('even = blue, odd = silver', 'odd = blue, even = silver')
    if '/static/source_picker_browse.js' not in text:
        text = text.replace('</body>', '<script src="/static/source_picker_browse.js"></script>\n</body>')
    if '/static/event_trace_viewer.js' not in text:
        text = text.replace('</body>', '<script src="/static/event_trace_viewer.js"></script>\n</body>')
    return text.encode('utf-8')


def _viewer_cards_payload() -> bytes:
    return _file_payload(SCENE_VIEWER_CARDS_JS)


def _build_canonical_projection(graph: dict, projection_id: str) -> dict:
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
    return {'valid': bool(tree.get('valid')), 'projectable': bool(tree.get('projectable')), 'ruleset': ruleset, 'source': tree.get('source', {}), 'structure_tree': tree, 'graph': tree_to_graph(tree), 'errors': errors, 'warnings': list(tree.get('warnings', []))}


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
    errors = []
    warnings = []
    valid = True
    projectable = True
    for master in masters.values():
        tree = master['tree']
        errors.extend(tree.get('errors', []))
        warnings.extend(tree.get('warnings', []))
        valid = valid and bool(tree.get('valid'))
        projectable = projectable and bool(tree.get('projectable'))
    result.update({'valid': valid and not errors, 'projectable': projectable and not errors, 'errors': errors, 'warnings': warnings, 'ruleset': 'structure_session'})
    return result


class Handler(BaseHandler):
    server_version = 'Structure/0.26.0'

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
        payload = {'ok': False, 'error': exc.as_dict() if isinstance(exc, ProjectorError) else {'id': 'SP_REQUEST_FAILED', 'message': str(exc)}}
        self._write_json(payload, 400)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == '/':
                return self._write_body(_viewer_html_payload(), 'text/html; charset=utf-8')
            if path == '/static/scene_viewer_v4.js':
                return self._write_file(SCENE_VIEWER_JS, 'application/javascript; charset=utf-8')
            if path == '/static/scene_viewer_v4_cards.js':
                return self._write_body(_viewer_cards_payload(), 'application/javascript; charset=utf-8')
            if path == '/static/source_picker_browse.js':
                return self._write_file(SOURCE_PICKER_BROWSE_JS, 'application/javascript; charset=utf-8')
            if path == '/static/event_trace_viewer.js':
                return self._write_file(EVENT_TRACE_VIEWER_JS, 'application/javascript; charset=utf-8')
            if path == '/legacy':
                return self._write_file(LEGACY_INDEX_HTML, 'text/html; charset=utf-8')
            if path == '/api/health':
                return self._write_json({'ok': True, 'server': self.server_version, 'input_model': 'StructureTree/1.1', 'scene_model': 'Scene/1.1', 'multi_master': True, 'projection_master_cardinality': 'source 1:N projection', 'semantic_projection_styles': True, 'implemented_semantic_styles': ['topic', 'impact'], 'visual_style_separate': True, 'selectable_sources': ['github', 'directory'], 'directory_browser': True, 'event_trace_causality': 'explicit_only', 'cross_master_inference': False, 'effects': 'none'})
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
                masters = {'master-1': {'id': 'master-1', 'name': 'master-1', 'source_spec': {}, 'snapshot': snapshot, 'tree': tree, 'graph': tree_to_graph(tree)}}
                catalog = session_catalog(masters)
                # Legacy keys remain during viewer migration.
                catalog['styles'] = style_catalog()
                catalog['topics'] = [{'id': 'all', 'label': 'all', 'entry_count': len(tree.get('entries', []))}] + topic_catalog(tree)
                catalog['relation_depth'] = {'min': 0, 'max': 32, 'default': 0}
                catalog['defaults'] = {'semantic_projection_style': 'topic', 'visual_style': 'atlas', 'projection_dimension': '3d', 'relation_depth': 0}
                return self._write_json(catalog)
            if path == '/api/scene':
                page = query.get('page', ['canonical'])[0]
                views = [part for part in query.get('views', [''])[0].split(',') if part]
                if not views:
                    views = [item['id'] for item in resolve_page(page).get('placements', [])[:2]]
                result = _compose_scene_result(load_source(source_spec_from_query(query)), page, views)
                return self._write_json(result, 200 if result.get('projectable') else 422)
            if path == '/api/project':
                result = _build_result(load_source(source_spec_from_query(query)), query.get('page', ['canonical'])[0], query.get('view', [None])[0])
                return self._write_json(result, 200 if result.get('projectable') else 422)
            if path == '/api/binding-tree':
                tree = read_canonical(load_source(source_spec_from_query(query)))
                return self._write_json(binding_tree(tree_to_graph(tree), root=query.get('root', [None])[0], depth=int(query.get('depth', ['1'])[0]), budget=int(query.get('budget', ['1500'])[0])))
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
