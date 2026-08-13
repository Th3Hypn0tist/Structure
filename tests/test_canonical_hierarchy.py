import unittest
from types import SimpleNamespace
from unittest.mock import patch

from input_modules.canonical.module import read
from projection_instances import _projection_hierarchy_depths


class CanonicalHierarchyTests(unittest.TestCase):
    def _snapshot(self):
        return SimpleNamespace(
            repo='example/repo',
            branch='main',
            revision='a' * 40,
        )

    def test_membership_registry_reference_becomes_presentation_parent(self):
        graph_result = {
            'valid': True,
            'projectable': True,
            'projection_status': 'valid',
            'source': {},
            'graph': {
                'nodes': [
                    {
                        'id': 'Registry',
                        'name': 'Registry',
                        'kind': 'contract',
                        'source_role': 'membership_registry',
                        'raw': {
                            'references': [
                                {'id': 'r1', 'target_ref': 'Child', 'purpose': 'membership'}
                            ]
                        },
                    },
                    {
                        'id': 'Child',
                        'name': 'Child',
                        'kind': 'contract',
                        'source_role': 'definition',
                        'raw': {'references': []},
                    },
                ],
                'edges': [],
            },
            'errors': [],
            'warnings': [],
        }
        with patch('input_modules.canonical.module.build_graph', return_value=graph_result):
            tree = read(self._snapshot())

        entries = {entry['id']: entry for entry in tree['entries']}
        self.assertIsNone(entries['Registry']['parent_id'])
        self.assertEqual(entries['Child']['parent_id'], 'Registry')
        self.assertEqual(entries['Child']['metadata']['hierarchy_evidence'], 'canonical membership')

        depths = _projection_hierarchy_depths(tree, {'Registry', 'Child'})
        self.assertEqual(depths['Registry'], 0)
        self.assertEqual(depths['Child'], 1)

        membership_links = [link for link in tree['links'] if link['dimension'] == 'membership']
        self.assertEqual(len(membership_links), 1)
        self.assertEqual(membership_links[0]['source_id'], 'Registry')
        self.assertEqual(membership_links[0]['target_id'], 'Child')

    def test_explicit_containment_has_precedence_over_membership(self):
        graph_result = {
            'valid': True,
            'projectable': True,
            'projection_status': 'valid',
            'source': {},
            'graph': {
                'nodes': [
                    {'id': 'Container', 'name': 'Container', 'kind': 'contract', 'source_role': 'definition', 'raw': {'references': []}},
                    {
                        'id': 'Registry',
                        'name': 'Registry',
                        'kind': 'contract',
                        'source_role': 'membership_registry',
                        'raw': {'references': [{'target_ref': 'Child'}]},
                    },
                    {'id': 'Child', 'name': 'Child', 'kind': 'contract', 'source_role': 'definition', 'raw': {'references': []}},
                ],
                'edges': [
                    {'id': 'c1', 'dimension': 'containment', 'source': 'Container', 'target': 'Child', 'type': 'containment', 'raw': {}},
                ],
            },
            'errors': [],
            'warnings': [],
        }
        with patch('input_modules.canonical.module.build_graph', return_value=graph_result):
            tree = read(self._snapshot())

        entries = {entry['id']: entry for entry in tree['entries']}
        self.assertEqual(entries['Child']['parent_id'], 'Container')
        self.assertEqual(entries['Child']['metadata']['hierarchy_evidence'], 'structure.containment[]')

    def test_ambiguous_membership_does_not_guess_parent(self):
        graph_result = {
            'valid': True,
            'projectable': True,
            'projection_status': 'valid',
            'source': {},
            'graph': {
                'nodes': [
                    {
                        'id': 'RegistryA', 'name': 'RegistryA', 'kind': 'contract', 'source_role': 'membership_registry',
                        'raw': {'references': [{'target_ref': 'Child'}]},
                    },
                    {
                        'id': 'RegistryB', 'name': 'RegistryB', 'kind': 'contract', 'source_role': 'membership_registry',
                        'raw': {'references': [{'target_ref': 'Child'}]},
                    },
                    {'id': 'Child', 'name': 'Child', 'kind': 'contract', 'source_role': 'definition', 'raw': {'references': []}},
                ],
                'edges': [],
            },
            'errors': [],
            'warnings': [],
        }
        with patch('input_modules.canonical.module.build_graph', return_value=graph_result):
            tree = read(self._snapshot())

        entries = {entry['id']: entry for entry in tree['entries']}
        self.assertIsNone(entries['Child']['parent_id'])
        self.assertTrue(any(w['id'] == 'SP_CANONICAL_PARENT_AMBIGUOUS' for w in tree['warnings']))


if __name__ == '__main__':
    unittest.main()
