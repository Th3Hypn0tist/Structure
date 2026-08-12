from __future__ import annotations

import json
import os
import urllib.parse
from http.server import ThreadingHTTPServer

from canonical_graph import build_graph
from canonical_projections import PROJECTIONS, build_canonical_projection
from nanocms import projection, resolve_page, resolve_view
from projection_controls import apply_controls, defaults_for, schema_for
from raw_json_mapper import build_raw_json_graph
from raw_json_projection import build_raw_json_space_3d
from source_adapter import list_branches, load_snapshot
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
FX_CSS = os.path.join(BASE_DIR, 'static', 'fx_v13.css')
FX_JS = os.path.join(BASE_DIR, 'static', 'fx_v13.js')


def _index_payload() -> bytes:
    with open(INDEX_HTML, 'r', encoding='utf-8') as handle:
        html = handle.read()
    with open(FX_CSS, 'r', encoding='utf-8') as handle:
        css = handle.read()
    with open(FX_JS, 'r', encoding='utf-8') as handle:
        js = handle.read()
    html = html.replace('</head>', f'<style id="sp-fx-v13">{css}</style></head>')
    html = html.replace('</body>', f'<script id="sp-fx-v13-script">{js}</script></body>')
    return html.encode('utf-8')


def _apply_projection_controls(base_projection: dict, projection_id: str, supplied_params: dict[str, object], result: dict) -> None:
    try:
        result['projection'] = apply_controls(base_projection, supplied_params)
    except Exception as exc:
        result['projection'] = base_projection
        schema = schema_for(projection_id)
        result['projection']['control_schema'] = schema.get('controls', [])
        result['projection']['control_schema_version'] = schema.get('version', 1)
        result['projection']['control_values'] = defaults_for(projection_id)
        result['projection']['builtin_presets'] = schema.get('presets', {})
        result.setdefault('warnings', []).append({
            'id': 'SP_PROJECTION_CONTROLS_FALLBACK',
            'message': f'Projection controls failed; projection rendered with base geometry: {exc}',
        })


class Handler(BaseHandler):
    server_version = 'StructureProjector/0.14.0'

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

            if parsed.path == '/api/project':
                qs = urllib.parse.parse_qs(parsed.query)
                branch = qs.get('branch', ['main'])[0]
                page_id = qs.get('page', ['canonical'])[0]
                view_id = qs.get('view', [None])[0]
                selected_path = qs.get('path', [None])[0]
                context_id = qs.get('context', [None])[0]
                supplied_params: dict[str, object] = {}
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
                    supplied_params = decoded

                try:
                    page = resolve_page(page_id)
                    placement = resolve_view(page_id, view_id)
                except KeyError as exc:
                    self._json(400, {
                        'valid': False,
                        'errors': [{'id': 'SP_NANOCMS_RESOLUTION', 'message': f'Unknown nanoCMS page/view: {exc.args[0]}'}],
                    })
                    return

                if placement.get('renderer') != 'canonical_projection_3d':
                    self._json(500, {
                        'valid': False,
                        'errors': [{'id': 'SP_3D_ONLY_VIOLATION', 'message': f'Active placement is not 3D: {placement.get("id")}'}],
                    })
                    return

                snapshot = load_snapshot(branch)
                ruleset = placement['ruleset']

                if ruleset == 'CanonicalContract':
                    result = build_graph(snapshot)
                    result['ruleset'] = 'CanonicalContract'
                    if result.get('projectable') and placement.get('projection_id'):
                        projection_id = placement['projection_id']
                        base_projection = build_canonical_projection(result['graph'], projection_id)
                        _apply_projection_controls(base_projection, projection_id, supplied_params, result)
                    if result.get('projectable') and not result.get('valid'):
                        result.setdefault('warnings', []).append({
                            'id': 'SP_CANONICAL_DEGRADED',
                            'message': 'Canonical graph contains explicit projectable structure, but one or more validation gates failed. Projection is read-only and errors remain visible.',
                        })
                elif ruleset == 'RawJSON':
                    result = build_raw_json_graph(snapshot, selected_path)
                    result['ruleset'] = 'RawJSON'
                    if result.get('valid'):
                        projection_id = placement['projection_id']
                        base_projection = build_raw_json_space_3d(result['graph'])
                        _apply_projection_controls(base_projection, projection_id, supplied_params, result)
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
                    'version': '0.14.0',
                    'view_shell': 'nanoCMS',
                    'projection_policy': '3d_only',
                    'rulesets': ['CanonicalContract', 'RawJSON'],
                    'canonical_contract_format': 'bootstrap-driven',
                    'canonical_projections': {k: v for k, v in PROJECTIONS.items() if v.get('dimension') == '3d'},
                    'raw_json_projection': 'raw_json_space_3d',
                    'projection_controls': 'presentation-only fail-soft controls + local browser presets',
                    'canonical_projection_policy': 'project proven explicit structure even when validation is degraded',
                    'renderers': ['canonical_projection_3d+fx'],
                    'fx_layer': 'isolated CSS 3D extrusion + emissive status edges + adjustable glow',
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
    print(f'StructureProjector 0.14.0: http://{APP_HOST}:{APP_PORT}')
    print(f'Source: {SOURCE_REPO}')
    print('Projection policy: 3D only')
    print('Canonical: Galaxy, Role Layers, Dependency Tower, Authority Space, Relation Orbits')
    print('Raw JSON: JSON Space')
    print('3D FX: extrusion + emissive glow + edge glow, presentation-only')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
