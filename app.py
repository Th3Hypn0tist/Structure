from __future__ import annotations

import json
import os
import urllib.parse
from http.server import ThreadingHTTPServer

from canonical_graph import build_graph
from canonical_projections import PROJECTIONS, build_canonical_projection
from master_map_renderer import build_master_map_projection
from nanocms import projection, resolve_page, resolve_view
from projection_controls import apply_controls
from raw_json_mapper import build_raw_json_graph
from source_adapter import list_branches, load_snapshot
from structureprojector import (
    APP_HOST,
    APP_PORT,
    SOURCE_REPO,
    Handler as BaseHandler,
    ProjectorError,
)
from view_rules import MAX_BINDING_DEPTH, ViewRuleError, binding_children, binding_tree

INDEX_HTML = os.path.join(os.path.dirname(__file__), 'static', 'index_v12.html')


class Handler(BaseHandler):
    server_version = 'StructureProjector/0.12.0'

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path == '/':
                with open(INDEX_HTML, 'rb') as f:
                    payload = f.read()
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

                snapshot = load_snapshot(branch)
                ruleset = placement['ruleset']

                if ruleset == 'CanonicalContract':
                    result = build_graph(snapshot)
                    result['ruleset'] = 'CanonicalContract'
                    if result['valid'] and placement.get('projection_id'):
                        base_projection = build_canonical_projection(
                            result['graph'], placement['projection_id']
                        )
                        result['projection'] = apply_controls(base_projection, supplied_params)
                elif ruleset == 'RawJSON':
                    result = build_raw_json_graph(snapshot, selected_path)
                    if result['valid'] and placement.get('renderer') == 'svg_master_map':
                        result['projection'] = build_master_map_projection(
                            result['graph'], context_id=context_id
                        )
                else:
                    self._json(500, {
                        'valid': False,
                        'errors': [{'id': 'SP_UNKNOWN_RULESET', 'message': f'Unknown ruleset in placement: {ruleset}'}],
                    })
                    return

                result['page'] = page
                result['placement'] = placement
                result['context'] = context_id
                self._json(200 if result['valid'] else 422, result)
                return

            if parsed.path == '/api/health':
                self._json(200, {
                    'ok': True,
                    'service': 'StructureProjector',
                    'version': '0.12.0',
                    'view_shell': 'nanoCMS',
                    'rulesets': ['CanonicalContract', 'RawJSON'],
                    'canonical_contract_format': 'bootstrap-driven',
                    'canonical_projections': PROJECTIONS,
                    'projection_controls': 'declarative backend schema + bounded values + local browser presets',
                    'renderers': ['canonical_projection_2d', 'canonical_projection_3d', 'svg', 'svg_master_map'],
                    'viewport': 'cursor_anchored_wheel_zoom + drag_pan',
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
    print(f'StructureProjector 0.12.0: http://{APP_HOST}:{APP_PORT}')
    print(f'Source: {SOURCE_REPO}')
    print('Canonical projections: 5 x 2D + 5 x 3D')
    print('Projection controls: declarative schemas + browser-local presets')
    print('Viewport: cursor-anchored wheel zoom + drag pan')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
