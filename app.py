from __future__ import annotations

import json
import os
import urllib.parse
from http.server import ThreadingHTTPServer

from canonical_projections import PROJECTIONS as CORE_PROJECTIONS, build_canonical_projection
from canonical_projections_extra3d import PROJECTIONS as EXTRA_PROJECTIONS, build_projection as build_extra_projection
from dependency_flow_projection import build_dependency_flow_3d
from input_modules.canonical import read as read_canonical
from input_modules.raw_json import read as read_raw_json
from nanocms import projection, resolve_page, resolve_view
from primitive_registry import load_registry
from raw_json_projection import build_raw_json_space_3d
from scene_composer import compose_scene
from scene_contract import projection_to_scene, validate_scene
from source_adapter import list_branches, load_snapshot
from structure_tree import tree_to_graph
from structureprojector import (
    APP_HOST,
    APP_PORT,
    SOURCE_REPO,
    Handler as BaseHandler,
    ProjectorError,
)
from view_rules import MAX_BINDING_DEPTH, ViewRuleError, binding_children, binding_tree

BASE_DIR = os.path.dirname(__file__)
SCENE_VIEWER_HTML = os.path.join(BASE_DIR, 'static', 'scene_viewer_v31.html')
LEGACY_INDEX_HTML = os.path.join(BASE_DIR, 'static', 'scene_viewer_v2.html')

ALL_CANONICAL_PROJECTIONS = {
    **{k: v for k, v in CORE_PROJECTIONS.items() if v.get('dimension') == '3d'},
    **EXTRA_PROJECTIONS,
}


def _html_payload(path: str) -> bytes:
    with open(path, 'r', encoding='utf-8') as handle:
        return handle.read().encode('utf-8')


def _build_canonical_projection(graph: dict, projection_id: str) -> dict:
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
    result['scene'] = scene
    scene_errors = validate_scene(scene)
    if scene_errors:
        result.setdefault('errors', []).extend(scene_errors)
        result['valid'] = False
        result.setdefault('warnings', []).append({
            'id': 'SP_SCENE_INVALID',
            'message': 'Projection produced a Scene that does not satisfy Scene Contract 1.1.',
        })


def _build_result(snapshot, page: str, view: str | None = None) -> dict:
    if page == 'raw-json':
        tree = read_raw_json(snapshot, {'path': view} if view else None)
        result = _result_from_tree(tree, 'raw_json_syntax')
        base_projection = build_raw_json_space_3d(result['graph'])
        _attach_scene(result, base_projection)
        return result

    tree = read_canonical(snapshot)
    result = _result_from_tree(tree, 'canonical_contract')
    selected_view = resolve_view(page, view)
    projection_id = selected_view['projection_id']
    base_projection = _build_canonical_projection(result['graph'], projection_id)
    _attach_scene(result, base_projection)
    return result


def _compose_scene_result(snapshot, page: str, views: list[str]) -> dict:
    tree = read_canonical(snapshot)
    result = _result_from_tree(tree, 'canonical_contract')
    selected_views = [resolve_view(page, view_id) for view_id in views]
    projections = [_build_canonical_projection(result['graph'], item['projection_id']) for item in selected_views]
    scene = compose_scene(projections, tree)
    result['scene'] = scene
    result['views'] = selected_views
    scene_errors = list(scene.get('validation_errors', []))
    if scene_errors:
        result.setdefault('errors', []).extend(scene_errors)
        result['valid'] = False
    return result


class Handler(BaseHandler):
    server_version = 'StructureProjector/0.21.3'

    def _write_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_html(self, path: str) -> None:
        body = _html_payload(path)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == '/':
                return self._write_html(SCENE_VIEWER_HTML)
            if path == '/legacy':
                return self._write_html(LEGACY_INDEX_HTML)
            if path == '/api/health':
                return self._write_json({
                    'ok': True,
                    'server': self.server_version,
                    'input_model': 'StructureTree/1.0',
                    'scene_model': 'Scene/1.1',
                    'renderer': 'webgl2_instanced_scene_v3.1',
                    'effects': 'none',
                })
            if path == '/api/primitives':
                return self._write_json(load_registry())
            if path == '/api/branches':
                return self._write_json({'branches': list_branches(SOURCE_REPO)})
            if path == '/api/nanocms':
                page = query.get('page', ['canonical'])[0]
                return self._write_json(projection(page))
            if path == '/api/scene':
                branch = query.get('branch', ['main'])[0]
                page = query.get('page', ['canonical'])[0]
                views_arg = query.get('views', [''])[0]
                views = [part for part in views_arg.split(',') if part]
                if not views:
                    selected_page = resolve_page(page)
                    placements = selected_page.get('placements', [])
                    views = [item['id'] for item in placements[:2]]
                snapshot = load_snapshot(branch=branch, repo=SOURCE_REPO)
                result = _compose_scene_result(snapshot, page, views)
                return self._write_json(result, 200 if result.get('projectable') else 422)
            if path == '/api/project':
                branch = query.get('branch', ['main'])[0]
                page = query.get('page', ['canonical'])[0]
                view = query.get('view', [None])[0]
                snapshot = load_snapshot(branch=branch, repo=SOURCE_REPO)
                result = _build_result(snapshot, page, view)
                return self._write_json(result, 200 if result.get('projectable') else 422)
            if path == '/api/binding-tree':
                branch = query.get('branch', ['main'])[0]
                root = query.get('root', [None])[0]
                depth = int(query.get('depth', ['1'])[0])
                budget = int(query.get('budget', ['1500'])[0])
                snapshot = load_snapshot(branch=branch, repo=SOURCE_REPO)
                tree = read_canonical(snapshot)
                return self._write_json(binding_tree(tree_to_graph(tree), root=root, depth=depth, budget=budget))
            if path == '/api/binding-children':
                branch = query.get('branch', ['main'])[0]
                node_id = query.get('node', [None])[0]
                snapshot = load_snapshot(branch=branch, repo=SOURCE_REPO)
                tree = read_canonical(snapshot)
                return self._write_json(binding_children(tree_to_graph(tree), node_id=node_id))
            return super().do_GET()
        except (ProjectorError, ViewRuleError, ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, ProjectorError):
                payload = {'ok': False, 'error': exc.to_dict()}
            else:
                payload = {'ok': False, 'error': {'id': 'SP_REQUEST_FAILED', 'message': str(exc)}}
            return self._write_json(payload, 400)


def main() -> None:
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), Handler)
    print(f'StructureProjector listening on http://{APP_HOST}:{APP_PORT}')
    server.serve_forever()


if __name__ == '__main__':
    main()
