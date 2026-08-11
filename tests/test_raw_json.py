import json
import unittest

from raw_json_mapper import build_raw_json_graph
from structureprojector import SourceSnapshot


class RawJSONTests(unittest.TestCase):
    def snapshot(self, payloads):
        files = {path: json.dumps(value).encode('utf-8') for path, value in payloads.items()}
        return SourceSnapshot('x/y', 'main', 'abc123', files)

    def test_maps_object_array_and_values(self):
        snap = self.snapshot({'x.json': {'service': {'ports': [80, 443], 'enabled': True}}})
        result = build_raw_json_graph(snap, 'x.json')
        self.assertTrue(result['valid'])
        nodes = {n['pointer']: n for n in result['graph']['nodes']}
        self.assertEqual(nodes['/']['type'], 'json_object')
        self.assertEqual(nodes['/service']['type'], 'json_object')
        self.assertEqual(nodes['/service/ports']['type'], 'json_array')
        self.assertEqual(nodes['/service/ports/0']['value'], 80)
        self.assertEqual(nodes['/service/enabled']['value'], True)

    def test_json_pointer_escaping(self):
        snap = self.snapshot({'x.json': {'a/b': {'x~y': 1}}})
        result = build_raw_json_graph(snap, 'x.json')
        pointers = {n['pointer'] for n in result['graph']['nodes']}
        self.assertIn('/a~1b/x~0y', pointers)

    def test_file_selection(self):
        snap = self.snapshot({'a.json': {'a': 1}, 'b.json': {'b': 2}})
        result = build_raw_json_graph(snap, 'b.json')
        self.assertTrue(result['valid'])
        self.assertEqual(result['source']['path'], 'b.json')
        self.assertEqual(result['source']['available_json_files'], ['a.json', 'b.json'])

    def test_missing_path_is_structured_error(self):
        snap = self.snapshot({'a.json': {'a': 1}})
        result = build_raw_json_graph(snap, 'missing.json')
        self.assertFalse(result['valid'])
        self.assertEqual(result['errors'][0]['id'], 'RAWJSON_PATH_NOT_FOUND')


if __name__ == '__main__':
    unittest.main()
