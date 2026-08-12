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
INDEX_HTML = os.path.join(BASE_DIR, 'static', 'index_v12.html')

ALL_CANONICAL_PROJECTIONS = {
    **{k: v for k, v in CORE_PROJECTIONS.items() if v.get('dimension') == '3d'},
    **EXTRA_PROJECTIONS,
}


def _index_payload() -> bytes:
    with open(INDEX_HTML, 'r', encoding='utf-8') as handle:
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
            'message': 'Projection produced a Scene that does not satisfy Scene Contract v1.',
        })


def _decode_transforms(raw: str) -> dict:
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError('transforms must be a JSON object') from exc
    if not isinstance(decoded, dict):
        raise ValueError('transforms must be a JSON object')
    return decoded


class Handler(BaseHandler):
    server_version = 'StructureProjector/0.18.0'

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path == '/':
                payload = _index_payload()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if parsed.path == '/api/nanocms':
                qs = urllib.parse.parse_qs(parsed.query)
                page = qs.get('page', [None])[0]
                view = qs.get('view', [None])[0]
                try:
                    self._json(200, projection(page, view))
                except KeyError as exc:
                    self._json(404, {
                        'valid': False,
                        'errors': [{'id': 'SP_NANOCMS_RESOLUTION', 'message': f'Unknown nanoCMS page/view: {exc.args[0]}'}],
                    })
                return

            if parsed.path == '/api/branches':
                self._json(200, {'repository': SOURCE_REPO, 'branches': list_branches()})
                return

            if parsed.path in ('/api/binding-children', '/api/binding-tree'):
                qs = urllib.parse.parse_qs(parsed.query)
                branch = qs.get('branch', ['main'])[0]
                source_path = qs.get('source_path', [None])[0]
                pointer = qs.get('pointer', ['/'])[0]
                if not source_path:
                    self._json(400, {
                        'valid': False,
                        'errors': [{'id': 'SP_BINDING_SOURCE_REQUIRED', 'message': 'source_path is required'}],
                    })
                    return
                snapshot = load_snapshot(branch)
                if parsed.path == '/api/binding-tree':
                    try:
                        requested_depth = int(qs.get('depth', ['1'])[0])
                    except ValueError:
                        self._json(400, {
                            'valid': False,
                            'errors': [{'id': 'SP_DEPTH_INVALID', 'message': 'depth must be an integer'}],
                        })
                        return
                    result = binding_tree(snapshot, source_path, pointer, requested_depth)
                else:
                    result = binding_children(snapshot, source_path, pointer)
                result['valid'] = True
                result['source'] = {
                    'repository': snapshot.repo,
                    'branch': snapshot.branch,
                    'revision': snapshot.revision,
                }
                self._json(200, result)
                return

            if parsed.path == '/api/scene':
                qs = urllib.parse.parse_qs(parsed.query)
                branch = qs.get('branch', ['main'])[0]
                page_id = qs.get('page', ['canonical'])[0]
                raw_views = qs.get('views', [''])[0]
                view_ids = [item.strip() for item in raw_views.split(',') if item.strip()]
                if not view_ids:
                    self._json(400, {
                        'valid': False,
                        'errors': [{'id': 'SP_SCENE_VIEWS_REQUIRED', 'message': 'views requires one or more comma-separated projection/view ids'}],
                    })
                    return
                try:
                    transforms = _decode_transforms(qs.get('transforms', [''])[0])
                except ValueError as exc:
                    self._json(400, {'valid': False, 'errors': [{'id': 'SP_SCENE_TRANSFORMS_INVALID', 'message': str(exc)}]})
                    return

                snapshot = load_snapshot(branch)
                if page_id == 'canonical':
                    tree = read_canonical(snapshot)
                    result = _result_from_tree(tree, 'CanonicalContract')
                    projections = []
                    placements = []
                    for view_id in view_ids:
                        try:
                            placement = resolve_view(page_id, view_id)
                        except KeyError:
                            self._json(400, {
                                'valid': False,
                                'errors': [{'id': 'SP_NANOCMS_RESOLUTION', 'message': f'Unknown canonical view: {view_id}'}],
                            })
                            return
                        projection_id = placement.get('projection_id')
                        if not projection_id:
                            continue
                        projections.append(_build_canonical_projection(result['graph'], projection_id))
                        placements.append(placement)
                elif page_id == 'raw-json':
                    selected_path = qs.get('path', [None])[0]
                    tree = read_raw_json(snapshot, {'path': selected_path})
                    result = _result_from_tree(tree, 'RawJSON')
                    projections = [build_raw_json_space_3d(result['graph'])]
                    placements = [resolve_view('raw-json', view_ids[0])]
                else:
                    self._json(400, {
                        'valid': False,
                        'errors': [{'id': 'SP_SCENE_PAGE', 'message': f'Unsupported Scene page: {page_id}'}],
                    })
                    return

                if not result.get('projectable'):
                    self._json(422, result)
                    return

                scene = compose_scene(projections, tree, transforms=transforms)
                result['scene'] = scene
                result['placements'] = placements
                result['projection_ids'] = [p.get('id') for p in projections]
                scene_errors = list(scene.get('validation_errors', []))
                if scene_errors:
                    result.setdefault('errors', []).extend(scene_errors)
                    result['valid'] = False
                self._json(200, result)
                return

            if parsed.path == '/api/project':
                qs = urllib.parse.parse_qs(parsed.query)
                branch = qs.get('branch', ['main'])[0]
                page_id = qs.get('page', ['canonical'])[0]
                view_id = qs.get('view', [None])[0]
                selected_path = qs.get('path', [None])[0]
                context_id = qs.get('context', [None])[0]

                raw_params = qs.get('params', [''])[0]
                if raw_params:
                    try:
                        decoded = json.loads(raw_params)
                    except json.JSONDecodeError:
                        self._json(400, {
                            'valid': False,
                            'errors': [{'id': 'SP_PARAMS_INVALID', 'message': 'params must be a JSON object'}],
                        })
                        return
                    if not isinstance(decoded, dict):
                        self._json(400, {
                            'valid': False,
                            'errors': [{'id': 'SP_PARAMS_INVALID', 'message': 'params must be a JSON object'}],
                        })
                        return

                try:
                    page = resolve_page(page_id)
                    placement = resolve_view(page_id, view_id)
                except KeyError as exc:
                    self._json(400, {
                        'valid': False,
                        'errors': [{'id': 'SP_NANOCMS_RESOLUTION', 'message': f'Unknown nanoCMS page/view: {exc.args[0]}'}],
                    })
                    return

                snapshot = load_snapshot(branch)
                ruleset = placement['ruleset']

                if ruleset == 'CanonicalContract':
                    tree = read_canonical(snapshot)
                    result = _result_from_tree(tree, 'CanonicalContract')
                    if result.get('projectable') and placement.get('projection_id'):
                        base_projection = _build_canonical_projection(result['graph'], placement['projection_id'])
                        _attach_scene(result, base_projection)
                    if result.get('projectable') and not result.get('valid'):
                        result.setdefault('warnings', []).append({
                            'id': 'SP_CANONICAL_DEGRADED',
                            'message': 'Canonical input contains explicit projectable structure, but validation errors remain visible.',
                        })
                elif ruleset == 'RawJSON':
                    tree = read_raw_json(snapshot, {'path': selected_path})
                    result = _result_from_tree(tree, 'RawJSON')
                    if result.get('projectable'):
                        base_projection = build_raw_json_space_3d(result['graph'])
                        _attach_scene(result, base_projection)
                else:
                    self._json(500, {
                        'valid': False,
                        'errors': [{'id': 'SP_UNKNOWN_RULESET', 'message': f'Unknown ruleset in placement: {ruleset}'}],
                    })
                    return

                result['page'] = page
                result['placement'] = placement
                result['context'] = context_id
                usable = bool(result.get('valid')) or bool(result.get('projectable'))
                self._json(200 if usable else 422, result)
                return

            if parsed.path == '/api/health':
                self._json(200, {
                    'ok': True,
                    'service': 'StructureProjector',
                    'version': '0.18.0',
                    'view_shell': 'nanoCMS',
                    'input_contract': 'StructureTree/1.0',
                    'scene_contract': 'Scene/1.0',
                    'input_modules': ['canonical', 'raw_json'],
                    'rulesets': ['CanonicalContract', 'RawJSON'],
                    'canonical_contract_format': 'bootstrap-driven',
                    'active_projection_family': '3d',
                    'projection_architecture': 'dimension-neutral StructureTree -> multiple projections -> composited Scene -> viewer',
                    'scene_api': '/api/scene',
                    'canonical_projections': ALL_CANONICAL_PROJECTIONS,
                    'raw_json_projection': 'raw_json_space_3d',
                    'effects': 'disabled',
                    'primitive_registry': 'primitives/registry.json',
                    'connection_channels': 'independent enabled/color style registry per Scene',
                    'cross_projection_rule': 'only explicit StructureTree links create cross-projection connections',
                    'canonical_projection_policy': 'project proven explicit structure even when validation is degraded',
                    'renderers': ['baseline_web_renderer'],
                    'default_recursion_depth': 1,
                    'max_recursion_depth': MAX_BINDING_DEPTH,
                    'source_adapter': 'cached immutable commit snapshots',
                })
                return

            self._json(404, {'error': 'not found'})
        except ViewRuleError as exc:
            self._json(422, {'valid': False, 'errors': [{'id': 'SP_VIEW_RULE', 'message': str(exc)}]})
        except ProjectorError as exc:
            self._json(502, {'valid': False, 'errors': [exc.as_dict()]})
        except Exception as exc:
            self._json(500, {'valid': False, 'errors': [{'id': 'SP_INTERNAL', 'message': str(exc)}]})


def main() -> None:
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), Handler)
    print(f'StructureProjector 0.18.0: http://{APP_HOST}:{APP_PORT}')
    print(f'Source: {SOURCE_REPO}')
    print('Input: Canonical/RawJSON -> StructureTree')
    print('Projection: StructureTree -> one or more SceneObjects -> Scene')
    print('Viewer: reads Scene; does not own source structure')
    print('Effects: disabled until Scene/primitive baseline is locked')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
