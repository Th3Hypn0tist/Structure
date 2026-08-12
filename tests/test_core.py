import json
import unittest

from structureprojector import SourceSnapshot, build_graph, detect_contract, validate_contract


def contract(cid, members=None, containment=None, relations=None, deps=None, status='locked', source_role='definition'):
    return {
        'format': {'contract_format': 'AIGMOS_CANONICAL_CONTRACT', 'format_version': '1.1'},
        'identity': {'id': cid, 'name': cid, 'type': 'test', 'version': '1.0.0'},
        'status': status,
        'source_role': source_role,
        'purpose': 'test',
        'scope': {'owns': [], 'does_not_own': []},
        'members': members or [],
        'structure': {
            'containment': containment or [],
            'relations': relations or [],
            'ownership': [],
            'authority': [],
            'dependencies': deps or [],
        },
        'behavior': {'states': [], 'interfaces': [], 'operations': [], 'events': []},
        'semantics': {},
        'constraints': {'invariants': [], 'hard_gates': []},
        'references': [],
        'prose': {'summary': None, 'notes': []},
    }


def bootstrap():
    return {
        'contract_shape': {
            'required': [
                'format', 'identity', 'status', 'source_role', 'purpose', 'scope',
                'members', 'structure', 'behavior', 'semantics', 'constraints',
                'references', 'prose',
            ],
            'format': {
                'contract_format': 'AIGMOS_CANONICAL_CONTRACT',
                'format_version': '1.1',
            },
            'status': {
                'values': ['unlocked', 'locked', 'superseded', 'deprecated'],
            },
        },
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
            members=[{
                'id': 'child', 'name': 'Child', 'type': 'member',
                'status': 'locked', 'semantics': {},
            }],
            containment=[{
                'id': 'e1', 'parent_ref': 'root', 'child_ref': 'child',
                'relation_type': 'contains',
            }],
        )
        snap = SourceSnapshot(
            'x/y', 'main', 'abc',
            {
                'canonical/json/00_Contract_Format.json': json.dumps(bootstrap()).encode(),
                'canonical/json/x.json': json.dumps(c).encode(),
            },
        )
        result = build_graph(snap)
        self.assertTrue(result['valid'])
        self.assertEqual(result['source']['contract_format'], '1.1')
        self.assertEqual(len(result['graph']['nodes']), 2)
        self.assertEqual(result['graph']['edges'][0]['dimension'], 'containment')

    def test_unresolved_reference_fails_closed(self):
        c = contract('root', deps=[{
            'id': 'd1', 'source_ref': 'root', 'target_ref': 'missing',
            'dependency_type': 'requires', 'required': True,
        }])
        snap = SourceSnapshot(
            'x/y', 'main', 'abc',
            {
                'canonical/json/00_Contract_Format.json': json.dumps(bootstrap()).encode(),
                'canonical/json/x.json': json.dumps(c).encode(),
            },
        )
        result = build_graph(snap)
        self.assertFalse(result['valid'])
        self.assertEqual(result['graph']['nodes'], [])
        self.assertTrue(any(e['id'] == 'CF_UNRESOLVED_REFERENCE' for e in result['errors']))

    def test_superseded_contract_is_not_active_node(self):
        active = contract('active')
        old = contract('old', status='superseded')
        snap = SourceSnapshot(
            'x/y', 'main', 'abc',
            {
                'canonical/json/00_Contract_Format.json': json.dumps(bootstrap()).encode(),
                'canonical/json/active.json': json.dumps(active).encode(),
                'canonical/json/legacy/old.json': json.dumps(old).encode(),
            },
        )
        result = build_graph(snap)
        self.assertTrue(result['valid'])
        self.assertEqual([n['id'] for n in result['graph']['nodes']], ['active'])
        self.assertEqual(result['source']['inactive_contracts'], 1)

    def test_membership_registry_does_not_duplicate_members(self):
        definition = contract('member.one')
        registry = contract(
            'registry',
            members=[{
                'id': 'member.one', 'name': 'Member One', 'type': 'registry_entry',
                'status': 'locked', 'semantics': {},
            }],
            source_role='membership_registry',
        )
        snap = SourceSnapshot(
            'x/y', 'main', 'abc',
            {
                'canonical/json/00_Contract_Format.json': json.dumps(bootstrap()).encode(),
                'canonical/json/member.json': json.dumps(definition).encode(),
                'canonical/json/registry.json': json.dumps(registry).encode(),
            },
        )
        result = build_graph(snap)
        self.assertTrue(result['valid'])
        ids = {n['id'] for n in result['graph']['nodes']}
        self.assertEqual(ids, {'member.one', 'registry'})


if __name__ == '__main__':
    unittest.main()
