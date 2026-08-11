from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

APP_HOST = os.getenv('STRUCTUREPROJECTOR_HOST', '127.0.0.1')
APP_PORT = int(os.getenv('STRUCTUREPROJECTOR_PORT', '6969'))
SOURCE_REPO = os.getenv('STRUCTUREPROJECTOR_SOURCE_REPO', 'Th3Hypn0tist/AIGMos_docs')
USER_AGENT = 'StructureProjector/0.1'
FORMAT_MAGIC = 'AIGMOS_CANONICAL_CONTRACT'
FORMAT_VERSION = '1.0'


class ProjectorError(Exception):
    def __init__(self, error_id: str, message: str, *, path: str | None = None):
        super().__init__(message)
        self.error_id = error_id
        self.message = message
        self.path = path

    def as_dict(self) -> dict[str, Any]:
        result = {'id': self.error_id, 'message': self.message}
        if self.path:
            result['path'] = self.path
        return result


@dataclass(frozen=True)
class SourceSnapshot:
    repo: str
    branch: str
    revision: str
    files: dict[str, bytes]


def _github_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': USER_AGENT,
        'X-GitHub-Api-Version': '2022-11-28',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise ProjectorError('SP_SOURCE_HTTP', f'GitHub returned HTTP {exc.code}: {exc.reason}') from exc
    except urllib.error.URLError as exc:
        raise ProjectorError('SP_SOURCE_UNAVAILABLE', f'GitHub source unavailable: {exc.reason}') from exc


def list_branches(repo: str = SOURCE_REPO) -> list[dict[str, str]]:
    owner, name = repo.split('/', 1)
    out: list[dict[str, str]] = []
    page = 1
    while True:
        url = f'https://api.github.com/repos/{owner}/{name}/branches?per_page=100&page={page}'
        chunk = _github_json(url)
        if not chunk:
            break
        for item in chunk:
            out.append({'name': item['name'], 'sha': item['commit']['sha']})
        if len(chunk) < 100:
            break
        page += 1
    return out


def resolve_branch(branch: str, repo: str = SOURCE_REPO) -> str:
    owner, name = repo.split('/', 1)
    quoted = urllib.parse.quote(branch, safe='')
    data = _github_json(f'https://api.github.com/repos/{owner}/{name}/branches/{quoted}')
    return data['commit']['sha']


def load_snapshot(branch: str, repo: str = SOURCE_REPO) -> SourceSnapshot:
    revision = resolve_branch(branch, repo)
    owner, name = repo.split('/', 1)
    url = f'https://codeload.github.com/{owner}/{name}/zip/{revision}'
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise ProjectorError('SP_SOURCE_ARCHIVE_HTTP', f'GitHub archive returned HTTP {exc.code}: {exc.reason}') from exc
    except urllib.error.URLError as exc:
        raise ProjectorError('SP_SOURCE_ARCHIVE_UNAVAILABLE', f'GitHub archive unavailable: {exc.reason}') from exc

    files: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [n for n in archive.namelist() if not n.endswith('/')]
        prefix = names[0].split('/', 1)[0] + '/' if names else ''
        for name_in_zip in names:
            rel = name_in_zip[len(prefix):] if name_in_zip.startswith(prefix) else name_in_zip
            if rel and not rel.startswith('.git/'):
                files[rel] = archive.read(name_in_zip)
    return SourceSnapshot(repo=repo, branch=branch, revision=revision, files=files)


REQUIRED_TOP = [
    'format', 'identity', 'status', 'source_role', 'purpose', 'scope', 'members',
    'structure', 'behavior', 'constraints', 'references', 'prose'
]
STRUCTURE_DIMS = ['containment', 'relations', 'ownership', 'authority', 'dependencies']
BEHAVIOR_DIMS = ['states', 'interfaces', 'operations', 'events']


def detect_contract(data: Any) -> bool:
    return isinstance(data, dict) and data.get('format', {}).get('contract_format') == FORMAT_MAGIC


def validate_contract(path: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    def err(error_id: str, message: str, field: str | None = None) -> None:
        item = {'id': error_id, 'contract': path, 'message': message}
        if field:
            item['field'] = field
        errors.append(item)

    for field in REQUIRED_TOP:
        if field not in data:
            err('CF_MISSING_REQUIRED_FIELD', f'Missing required top-level field: {field}', field)

    fmt = data.get('format', {})
    if fmt.get('contract_format') != FORMAT_MAGIC:
        err('CF_UNSUPPORTED_FORMAT', 'Unsupported contract format', 'format.contract_format')
    if fmt.get('format_version') != FORMAT_VERSION:
        err('CF_UNSUPPORTED_FORMAT_VERSION', f'Expected format version {FORMAT_VERSION}', 'format.format_version')

    identity = data.get('identity', {})
    for field in ['id', 'name', 'type', 'version']:
        if not identity.get(field):
            err('CF_MISSING_REQUIRED_FIELD', f'Missing identity.{field}', f'identity.{field}')

    structure = data.get('structure', {})
    for dim in STRUCTURE_DIMS:
        if dim not in structure or not isinstance(structure.get(dim), list):
            err('CF_MISSING_REQUIRED_FIELD', f'structure.{dim} must be an array', f'structure.{dim}')

    behavior = data.get('behavior', {})
    for dim in BEHAVIOR_DIMS:
        if dim not in behavior or not isinstance(behavior.get(dim), list):
            err('CF_MISSING_REQUIRED_FIELD', f'behavior.{dim} must be an array', f'behavior.{dim}')

    constraints = data.get('constraints', {})
    for dim in ['invariants', 'hard_gates']:
        if dim not in constraints or not isinstance(constraints.get(dim), list):
            err('CF_MISSING_REQUIRED_FIELD', f'constraints.{dim} must be an array', f'constraints.{dim}')

    return errors


def load_contracts(snapshot: SourceSnapshot) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    contracts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []

    for path in sorted(snapshot.files):
        content = snapshot.files[path]
        inventory.append({'path': path, 'size': len(content), 'type': 'file'})
        if not path.lower().endswith('.json'):
            continue
        try:
            data = json.loads(content.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not detect_contract(data):
            continue
        contract_errors = validate_contract(path, data)
        errors.extend(contract_errors)
        contracts.append({'path': path, 'data': data})

    return contracts, errors, inventory


def build_graph(snapshot: SourceSnapshot) -> dict[str, Any]:
    contracts, errors, inventory = load_contracts(snapshot)
    if not contracts:
        errors.append({
            'id': 'SP_NO_CANONICAL_CONTRACTS',
            'message': f'No {FORMAT_MAGIC} v{FORMAT_VERSION} contracts were detected in the selected revision.'
        })

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    refs_to_check: list[tuple[str, str, str]] = []

    for item in contracts:
        path, data = item['path'], item['data']
        root = data.get('identity', {})
        root_id = root.get('id')
        if root_id:
            if root_id in nodes:
                errors.append({'id': 'CF_AMBIGUOUS_IDENTITY', 'message': f'Duplicate active identity: {root_id}', 'contract': path})
            else:
                nodes[root_id] = {
                    'id': root_id,
                    'name': root.get('name', root_id),
                    'type': root.get('type'),
                    'version': root.get('version'),
                    'status': data.get('status'),
                    'source': path,
                    'kind': 'contract',
                    'raw': data,
                }
        for member in data.get('members', []):
            member_id = member.get('id')
            if not member_id:
                continue
            if member_id in nodes:
                errors.append({'id': 'CF_AMBIGUOUS_IDENTITY', 'message': f'Duplicate active identity: {member_id}', 'contract': path})
            else:
                nodes[member_id] = {
                    'id': member_id,
                    'name': member.get('name', member_id),
                    'type': member.get('type'),
                    'status': member.get('status'),
                    'source': path,
                    'kind': 'member',
                    'raw': member,
                }

    def add_edge(dim: str, edge: dict[str, Any], source_key: str, target_key: str) -> None:
        source = edge.get(source_key)
        target = edge.get(target_key)
        if not source or not target:
            return
        normalized = {
            'id': edge.get('id'),
            'dimension': dim,
            'source': source,
            'target': target,
            'type': edge.get('relation_type') or edge.get('ownership_type') or edge.get('authority_type') or edge.get('dependency_type') or dim,
            'raw': edge,
        }
        edges.append(normalized)
        refs_to_check.append((source, normalized['id'] or dim, 'source'))
        refs_to_check.append((target, normalized['id'] or dim, 'target'))

    for item in contracts:
        structure = item['data'].get('structure', {})
        for edge in structure.get('containment', []):
            add_edge('containment', edge, 'parent_ref', 'child_ref')
        for edge in structure.get('relations', []):
            add_edge('relations', edge, 'source_ref', 'target_ref')
        for edge in structure.get('ownership', []):
            add_edge('ownership', edge, 'owner_ref', 'target_ref')
        for edge in structure.get('authority', []):
            add_edge('authority', edge, 'authority_ref', 'target_ref')
        for edge in structure.get('dependencies', []):
            add_edge('dependencies', edge, 'source_ref', 'target_ref')
        for ref in item['data'].get('references', []):
            target = ref.get('target_ref')
            if target:
                refs_to_check.append((target, ref.get('id', 'reference'), 'target_ref'))

    for ref, owner, role in refs_to_check:
        if ref not in nodes:
            errors.append({'id': 'CF_UNRESOLVED_REFERENCE', 'message': f'Unresolved reference {ref} in {owner} ({role})'})

    valid = not errors
    return {
        'valid': valid,
        'source': {
            'repository': snapshot.repo,
            'branch': snapshot.branch,
            'revision': snapshot.revision,
            'files': len(snapshot.files),
            'contracts': len(contracts),
        },
        'inventory': inventory,
        'graph': {
            'nodes': list(nodes.values()) if valid else [],
            'edges': edges if valid else [],
        },
        'errors': errors,
    }


INDEX_HTML = os.path.join(os.path.dirname(__file__), 'static', 'index.html')


class Handler(BaseHTTPRequestHandler):
    server_version = 'StructureProjector/0.1'

    def _json(self, status: int, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)

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
            if parsed.path == '/api/branches':
                self._json(200, {'repository': SOURCE_REPO, 'branches': list_branches()})
                return
            if parsed.path == '/api/project':
                qs = urllib.parse.parse_qs(parsed.query)
                branch = qs.get('branch', ['main'])[0]
                result = build_graph(load_snapshot(branch))
                self._json(200 if result['valid'] else 422, result)
                return
            if parsed.path == '/api/health':
                self._json(200, {'ok': True, 'service': 'StructureProjector', 'version': '0.1.0'})
                return
            self._json(404, {'error': 'not found'})
        except ProjectorError as exc:
            self._json(502, {'valid': False, 'errors': [exc.as_dict()]})
        except Exception as exc:
            self._json(500, {'valid': False, 'errors': [{'id': 'SP_INTERNAL', 'message': str(exc)}]})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f'{self.address_string()} - {fmt % args}')


def main() -> None:
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), Handler)
    print(f'StructureProjector 0.1.0: http://{APP_HOST}:{APP_PORT}')
    print(f'Source: {SOURCE_REPO}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
