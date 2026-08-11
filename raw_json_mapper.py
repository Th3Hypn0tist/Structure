from __future__ import annotations

import json
from typing import Any


def _pointer_token(value: str) -> str:
    return value.replace('~', '~0').replace('/', '~1')


def _node_id(path: str, pointer: str) -> str:
    return f'rawjson:{path}#{pointer or "/"}'


def _json_type(value: Any) -> str:
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return 'number'
    if isinstance(value, list):
        return 'array'
    if isinstance(value, dict):
        return 'object'
    return type(value).__name__


def build_raw_json_graph(snapshot: Any, path: str | None = None) -> dict[str, Any]:
    """Map one JSON file into a structural graph without domain-semantic inference.

    The mapper treats JSON syntax only as JSON syntax:
    object/array containers, object keys, array indices and primitive leaf values.
    JSON Pointer is used as the stable path-local identity within the selected file.
    """
    json_paths = sorted(p for p in snapshot.files if p.lower().endswith('.json'))
    if not json_paths:
        return {
            'valid': False,
            'ruleset': 'RawJSON',
            'source': {
                'repository': snapshot.repo,
                'branch': snapshot.branch,
                'revision': snapshot.revision,
                'files': len(snapshot.files),
                'available_json_files': [],
                'path': None,
            },
            'graph': {'nodes': [], 'edges': []},
            'errors': [{'id': 'RAWJSON_NO_JSON_FILES', 'message': 'No .json files exist in the selected revision.'}],
            'warnings': [],
        }

    selected = path or json_paths[0]
    if selected not in json_paths:
        return {
            'valid': False,
            'ruleset': 'RawJSON',
            'source': {
                'repository': snapshot.repo,
                'branch': snapshot.branch,
                'revision': snapshot.revision,
                'files': len(snapshot.files),
                'available_json_files': json_paths,
                'path': selected,
            },
            'graph': {'nodes': [], 'edges': []},
            'errors': [{'id': 'RAWJSON_PATH_NOT_FOUND', 'message': f'JSON file not found in selected revision: {selected}'}],
            'warnings': [],
        }

    try:
        data = json.loads(snapshot.files[selected].decode('utf-8'))
    except UnicodeDecodeError as exc:
        return {
            'valid': False,
            'ruleset': 'RawJSON',
            'source': {
                'repository': snapshot.repo,
                'branch': snapshot.branch,
                'revision': snapshot.revision,
                'files': len(snapshot.files),
                'available_json_files': json_paths,
                'path': selected,
            },
            'graph': {'nodes': [], 'edges': []},
            'errors': [{'id': 'RAWJSON_ENCODING', 'message': f'JSON file is not valid UTF-8: {selected}'}],
            'warnings': [],
        }
    except json.JSONDecodeError as exc:
        return {
            'valid': False,
            'ruleset': 'RawJSON',
            'source': {
                'repository': snapshot.repo,
                'branch': snapshot.branch,
                'revision': snapshot.revision,
                'files': len(snapshot.files),
                'available_json_files': json_paths,
                'path': selected,
            },
            'graph': {'nodes': [], 'edges': []},
            'errors': [{
                'id': 'RAWJSON_INVALID_JSON',
                'message': f'Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}',
                'path': selected,
            }],
            'warnings': [],
        }

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(value: Any, pointer: str, name: str, parent: str | None, relation: str | None, relation_data: Any = None) -> str:
        node_id = _node_id(selected, pointer)
        value_type = _json_type(value)
        raw: Any
        if isinstance(value, dict):
            raw = {'json_type': 'object', 'size': len(value)}
        elif isinstance(value, list):
            raw = {'json_type': 'array', 'size': len(value)}
        else:
            raw = value

        nodes.append({
            'id': node_id,
            'name': name,
            'type': f'json_{value_type}',
            'kind': 'raw_json',
            'status': None,
            'source': selected,
            'pointer': pointer or '/',
            'value': None if isinstance(value, (dict, list)) else value,
            'raw': raw,
        })

        if parent is not None:
            edge_id = f'rawjson:edge:{selected}#{pointer or "/"}'
            edges.append({
                'id': edge_id,
                'dimension': 'containment',
                'source': parent,
                'target': node_id,
                'type': relation or 'contains',
                'raw': {'relation': relation, 'value': relation_data},
            })

        if isinstance(value, dict):
            for key, child in value.items():
                child_pointer = pointer + '/' + _pointer_token(str(key))
                add_node(child, child_pointer, str(key), node_id, 'key', str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                child_pointer = pointer + '/' + str(index)
                add_node(child, child_pointer, f'[{index}]', node_id, 'index', index)

        return node_id

    add_node(data, '', '$', None, None)

    return {
        'valid': True,
        'ruleset': 'RawJSON',
        'source': {
            'repository': snapshot.repo,
            'branch': snapshot.branch,
            'revision': snapshot.revision,
            'files': len(snapshot.files),
            'available_json_files': json_paths,
            'path': selected,
            'json_type': _json_type(data),
        },
        'graph': {'nodes': nodes, 'edges': edges},
        'errors': [],
        'warnings': [],
    }
