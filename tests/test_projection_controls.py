import unittest

from projection_controls import apply_controls, defaults_for, normalize_values, schema_for


class ProjectionControlTests(unittest.TestCase):
    def test_every_projection_schema_has_unique_control_ids(self):
        projection_ids = [
            'atlas_2d', 'relation_web_2d', 'adjacency_matrix_2d',
            'lifecycle_lanes_2d', 'dependency_flow_2d',
            'semantic_galaxy_3d', 'role_layers_3d', 'dependency_tower_3d',
            'authority_space_3d', 'relation_orbits_3d',
        ]
        for projection_id in projection_ids:
            schema = schema_for(projection_id)
            ids = [item['id'] for item in schema['controls']]
            self.assertEqual(len(ids), len(set(ids)), projection_id)
            self.assertGreater(len(ids), 0, projection_id)

    def test_values_are_clamped(self):
        values = normalize_values('atlas_2d', {'spacing_x': 999, 'node_scale': -9})
        self.assertEqual(values['spacing_x'], 2.5)
        self.assertEqual(values['node_scale'], 0.55)

    def test_defaults_exist(self):
        defaults = defaults_for('semantic_galaxy_3d')
        self.assertEqual(defaults['scale_x'], 1.0)
        self.assertEqual(defaults['perspective'], 1100)

    def test_apply_controls_preserves_projection_identity(self):
        projection = {
            'id': 'atlas_2d', 'title': 'Architecture Atlas', 'dimension': '2d',
            'kind': 'atlas', 'nodes': [{'id': 'a', 'x': 100, 'y': 100, 'width': 200, 'height': 80}],
            'groups': [], 'edges': [], 'bounds': {'width': 1000, 'height': 800},
        }
        result = apply_controls(projection, {'spacing_x': 2, 'node_scale': 1.5})
        self.assertEqual(result['id'], 'atlas_2d')
        self.assertEqual(result['control_schema_version'], 1)
        self.assertEqual(result['control_values']['spacing_x'], 2.0)
        self.assertEqual(result['nodes'][0]['width'], 300.0)
        self.assertEqual(projection['nodes'][0]['width'], 200)


if __name__ == '__main__':
    unittest.main()
