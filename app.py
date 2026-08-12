from __future__ import annotations

import os
import urllib.parse
from http.server import ThreadingHTTPServer

from explicit_view_renderer import build_explicit_view_geometry
from master_map_renderer import build_master_map_projection
from nanocms import projection, resolve_page, resolve_view
from raw_json_mapper import build_raw_json_graph
from structureprojector import (
    APP_HOST,
    APP_PORT,
    SOURCE_REPO,
    Handler as BaseHandler,
    ProjectorError,
    build_graph,
    list_branches,
    load_snapshot,
)
from view_rules import ViewRuleError, binding_children, build_view_projection

INDEX_HTML = os.path.join(os.path.dirname(__file__), 'static', 'index_v09.html')


class Handler(BaseHandler):
    server_version = 'StructureProjector/0.9.0'

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
                    self._json(404, {'valid': False, 'errors': [{'id': 'SP_NANOCMS_RESOLUTION', 'message': f'Unknown nanoCMS page/view: {exc.args[0]}'}]})
                return

            if parsed.path == '/api/branches':
                self._json(200, {'repository': SOURCE_REPO, 'branches': list_branches()})
                return

            if parsed.path == '/api/binding-children':
                qs = urllib.parse.parse_qs(parsed.query)
                branch = qs.get('branch', ['main'])[0]
                source_path = qs.get('source_path', [None])[0]
                pointer = qs.get('pointer', ['/'])[0]
                if not source_path:
                    self._json(400, {'valid': False, 'errors': [{'id': 'SP_BINDING_SOURCE_REQUIRED', 'message': 'source_path is required'}]})
                    return
                snapshot = load_snapshot(branch)
                result = binding_children(snapshot, source_path, pointer)
                result['valid'] = True
                result['source'] = {'repository': snapshot.repo, 'branch': snapshot.branch, 'revision': snapshot.revision}
                self._json(200, result)
                return

            if parsed.path == '/api/project':
                qs = urllib.parse.parse_qs(parsed.query)
                branch = qs.get('branch', ['main'])[0]
                page_id = qs.get('page', ['canonical'])[0]
                view_id = qs.get('view', [None])[0]
                selected_path = qs.get('path', [None])[0]
                context_id = qs.get('context', [None])[0]
                try:
                    page = resolve_page(page_id)
                    placement = resolve_view(page_id, view_id)
                except KeyError as exc:
                    self._json(400, {'valid': False, 'errors': [{'id': 'SP_NANOCMS_RESOLUTION', 'message': f'Unknown nanoCMS page/view: {exc.args[0]}'}]})
                    return

                snapshot = load_snapshot(branch)
                ruleset = placement['ruleset']
                if ruleset == 'ExplicitJSONView':
                    view_projection = build_view_projection(snapshot, placement['view_ruleset'])
                    geometry = build_explicit_view_geometry(view_projection)
                    result = {
                        'valid': True, 'ruleset': 'ExplicitJSONView',
                        'source': {'repository': snapshot.repo, 'branch': snapshot.branch, 'revision': snapshot.revision, 'files': len(snapshot.files)},
                        'graph': {'nodes': [], 'edges': []}, 'view_projection': view_projection,
                        'projection': geometry, 'geometry': geometry, 'errors': [],
                    }
                elif ruleset == 'CanonicalContract':
                    result = build_graph(snapshot)
                    result['ruleset'] = 'CanonicalContract'
                elif ruleset == 'RawJSON':
                    result = build_raw_json_graph(snapshot, selected_path)
                else:
                    self._json(500, {'valid': False, 'errors': [{'id': 'SP_UNKNOWN_RULESET', 'message': f'Unknown ruleset in placement: {ruleset}'}]})
                    return

                result['page'] = page
                result['placement'] = placement
                result['context'] = context_id
                if result['valid'] and placement.get('renderer') == 'svg_master_map':
                    result['projection'] = build_master_map_projection(result['graph'], context_id=context_id)
                self._json(200 if result['valid'] else 422, result)
                return

            if parsed.path == '/api/health':
                self._json(200, {
                    'ok': True, 'service': 'StructureProjector', 'version': '0.9.0',
                    'view_shell': 'nanoCMS', 'rulesets': ['ExplicitJSONView', 'CanonicalContract', 'RawJSON'],
                    'render_rulesets': ['render.aigmos_master_map'],
                    'renderers': ['svg_view_rules', 'svg', 'svg_master_map', 'javascript_3d'],
                    'viewport': 'cursor_anchored_wheel_zoom + local_reflow_navigation',
                    'binding_navigation': 'recursive direct JSON children by source_path + JSON Pointer',
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
    print(f'StructureProjector 0.9.0: http://{APP_HOST}:{APP_PORT}')
    print(f'Source: {SOURCE_REPO}')
    print('Navigation: local reflow + recursive binding children + cursor-anchored wheel zoom')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
