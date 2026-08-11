import json
import unittest

from structureprojector import SourceSnapshot, build_graph, detect_contract, validate_contract


def contract(cid, members=None, containment=None, relations=None, deps=None):
    return {
        'format': {'contract_format': 'AIGMOS_CANONICAL_CONTRACT', 'format_version': '1.0'},
        'identity': {'id': cid, 'name': cid, 'type': 'test', 'version': '1.0.0'},
        'status': 'locked', 'source_role': 'definition', 'purpose': 'test',
        'scope': {'owns': [], 'does_not_own': []},
        'members': members or [],
        'structure': {
            'containment': containment or [], 'relations': relations or [],
            'ownership': [], 'authority': [], 'dependencies': deps or []
        },
        'behavior': {'states': [], 'interfaces': [], 'operations': [], 'events': []},
        'constraints': {'invariants': [], 'hard_gates': []},
        'references': [], 'prose': {'summary': None, 'notes': []}
    }


class CoreTests(unittest.TestCase):
    def test_detect(self):
        self.assertTrue(detect_contract(contract('a')))
        self.assertFalse(detect_contract({'hello': 'world'}))

    def test_valid_contract_shape(self):
        self.assertEqual(validate_contract('x.json', contract('a')), [])

    def test_graph_and_edges(self):
        c = contract(
            'root',
            members=[{'id': 'child', 'name': 'Child', 'type': 'member', 'status': 'active'}],
            containment=[{'id': 'e1', 'parent_ref': 'root', 'child_ref': 'child', 'relation_type': 'contains'}],
        )
        snap = SourceSnapshot('x/y', 'main', 'abc', {'canonical/json/x.json': json.dumps(c).encode()})
        result = build_graph(snap)
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['graph']['nodes']), 2)
        self.assertEqual(result['graph']['edges'][0]['dimension'], 'containment')

    def test_unresolved_reference_fails_closed(self):
        c = contract('root', deps=[{
            'id': 'd1', 'source_ref': 'root', 'target_ref': 'missing',
            'dependency_type': 'requires', 'required': True
        }])
        snap = SourceSnapshot('x/y', 'main', 'abc', {'x.json': json.dumps(c).encode()})
        result = build_graph(snap)
        self.assertFalse(result['valid'])
        self.assertEqual(result['graph']['nodes'], [])
        self.assertTrue(any(e['id'] == 'CF_UNRESOLVED_REFERENCE' for e in result['errors']))


if __name__ == '__main__':
    unittest.main()
