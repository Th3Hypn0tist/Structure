from __future__ import annotations

import os
import urllib.parse
from http.server import ThreadingHTTPServer

from nanocms import projection, resolve_page
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

INDEX_HTML = os.path.join(os.path.dirname(__file__), 'static', 'index_v03.html')


class Handler(BaseHandler):
    server_version = 'StructureProjector/0.3'

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
                try:
                    self._json(200, projection(page))
                except KeyError:
                    self._json(404, {
                        'valid': False,
                        'errors': [{'id': 'SP_NANOCMS_PAGE_NOT_FOUND', 'message': f'Unknown nanoCMS page: {page}'}]
                    })
                return

            if parsed.path == '/api/branches':
                self._json(200, {'repository': SOURCE_REPO, 'branches': list_branches()})
                return

            if parsed.path == '/api/project':
                qs = urllib.parse.parse_qs(parsed.query)
                branch = qs.get('branch', ['main'])[0]
                page_id = qs.get('page', ['canonical-structure'])[0]
                selected_path = qs.get('path', [None])[0]

                try:
                    page = resolve_page(page_id)
                except KeyError:
                    self._json(400, {
                        'valid': False,
                        'errors': [{'id': 'SP_NANOCMS_PAGE_NOT_FOUND', 'message': f'Unknown nanoCMS page: {page_id}'}]
                    })
                    return

                placements = page.get('placements', [])
                if len(placements) != 1:
                    self._json(500, {
                        'valid': False,
                        'errors': [{'id': 'SP_NANOCMS_PLACEMENT', 'message': f'Page {page_id} must resolve to exactly one view placement in v0.3.'}]
                    })
                    return

                placement = placements[0]
                ruleset = placement['ruleset']
                snapshot = load_snapshot(branch)

                if ruleset == 'CanonicalContract':
                    result = build_graph(snapshot)
                    result['ruleset'] = 'CanonicalContract'
                elif ruleset == 'RawJSON':
                    result = build_raw_json_graph(snapshot, selected_path)
                else:
                    self._json(500, {
                        'valid': False,
                        'errors': [{'id': 'SP_UNKNOWN_RULESET', 'message': f'Unknown ruleset in placement: {ruleset}'}]
                    })
                    return

                result['page'] = page
                result['placement'] = placement
                self._json(200 if result['valid'] else 422, result)
                return

            if parsed.path == '/api/health':
                self._json(200, {
                    'ok': True,
                    'service': 'StructureProjector',
                    'version': '0.3.0',
                    'view_shell': 'nanoCMS',
                    'rulesets': ['CanonicalContract', 'RawJSON'],
                })
                return

            self._json(404, {'error': 'not found'})
        except ProjectorError as exc:
            self._json(502, {'valid': False, 'errors': [exc.as_dict()]})
        except Exception as exc:
            self._json(500, {'valid': False, 'errors': [{'id': 'SP_INTERNAL', 'message': str(exc)}]})


def main() -> None:
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), Handler)
    print(f'StructureProjector 0.3.0: http://{APP_HOST}:{APP_PORT}')
    print(f'Source: {SOURCE_REPO}')
    print('View shell: nanoCMS')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
