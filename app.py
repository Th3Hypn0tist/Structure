from __future__ import annotations

import json
import os
import urllib.parse
from http.server import ThreadingHTTPServer

from canonical_graph import build_graph
from canonical_projections import PROJECTIONS as CORE_PROJECTIONS, build_canonical_projection
from canonical_projections_extra3d import PROJECTIONS as EXTRA_PROJECTIONS, build_projection as build_extra_projection
from dependency_flow_projection import build_dependency_flow_3d
from effects3d import apply_effects, controls as effect_controls, defaults as effect_defaults, manifest as effect_manifest, presets as effect_presets
from nanocms import projection, resolve_page, resolve_view
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

ALL_CANONICAL_PROJECTIONS = {
    **{k: v for k, v in CORE_PROJECTIONS.items() if v.get('dimension') == '3d'},
    **EXTRA_PROJECTIONS,
}


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


def _build_canonical_3d(graph: dict, projection_id: str) -> dict:
    if projection_id == 'dependency_flow_3d':
        return build_dependency_flow_3d(graph)
    if projection_id in EXTRA_PROJECTIONS:
        return build_extra_projection(graph, projection_id)
    return build_canonical_projection(graph, projection_id)


def _apply_universal_effects(base_projection: dict, supplied_params: dict[str, object], result: dict) -> None:
    try:
        result['projection'] = apply_effects(base_projection, supplied_params)
    except Exception as exc:
        # Effects are presentation-only. A library/control failure must never
        # invalidate a proven graph or base 3D projection.
        result['projection'] = base_projection
        result['projection']['control_schema'] = effect_controls()
        result['projection']['control_schema_version'] = 1
        result['projection']['control_values'] = effect_defaults()
        result['projection']['builtin_presets'] = effect_presets()
        result['projection']['effect_library'] = effect_manifest()
        result.setdefault('warnings', []).append({
            'id': 'SP_3D_EFFECT_LIBRARY_FALLBACK',
            'message': f'Universal 3D effect library failed; base projection rendered without effect transforms: {exc}',
        })


class Handler(BaseHandler):
    server_version = 'StructureProjector/0.16.0'

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

            if parsed.path == '/api/effects/3d':
                self._json(200, effect_manifest())
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
                        base_projection = _build_canonical_3d(result['graph'], projection_id)
                        _apply_universal_effects(base_projection, supplied_params, result)
                    if result.get('projectable') and not result.get('valid'):
                        result.setdefault('warnings', []).append({
                            'id': 'SP_CANONICAL_DEGRADED',
                            'message': 'Canonical graph contains explicit projectable structure, but one or more validation gates failed. Projection is read-only and errors remain visible.',
                        })
                elif ruleset == 'RawJSON':
                    result = build_raw_json_graph(snapshot, selected_path)
                    result['ruleset'] = 'RawJSON'
                    if result.get('valid'):
                        base_projection = build_raw_json_space_3d(result['graph'])
                        _apply_universal_effects(base_projection, supplied_params, result)
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
                manifest = effect_manifest()
                self._json(200, {
                    'ok': True,
                    'service': 'StructureProjector',
                    'version': '0.16.0',
                    'view_shell': 'nanoCMS',
                    'projection_policy': '3d_only',
                    'rulesets': ['CanonicalContract', 'RawJSON'],
                    'canonical_contract_format': 'bootstrap-driven',
                    'canonical_projections': ALL_CANONICAL_PROJECTIONS,
                    'raw_json_projection': 'raw_json_space_3d',
                    'effect_library': {
                        'root': manifest.get('root'),
                        'version': manifest.get('version'),
                        'effect_count': len(manifest.get('effects', [])),
                        'groups': [g.get('id') for g in manifest.get('groups', [])],
                        'applies_to': 'all 3D projections from every mapper',
                    },
                    'canonical_projection_policy': 'project proven explicit structure even when validation is degraded',
                    'renderers': ['canonical_projection_3d+universal_effect_library'],
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
    print(f'StructureProjector 0.16.0: http://{APP_HOST}:{APP_PORT}')
    print(f'Source: {SOURCE_REPO}')
    print('Projection policy: 3D only')
    print('3D effects: universal effects/3d library shared by Canonical, Raw JSON and future mappers')
    print('Effect groups: ' + ', '.join(sorted(effect_presets())))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
