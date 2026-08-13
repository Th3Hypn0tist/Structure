from projection_instances import style_catalog


def _by_id():
    return {item['id']: item for item in style_catalog()}


def test_dual_dimension_projection_styles_remain_available():
    styles = _by_id()
    for style_id in ('atlas', 'map', 'matrix', 'lifecycle_lanes', 'dependency_flow'):
        assert style_id in styles
        assert styles[style_id]['dimensions'] == ['2d', '3d']
        assert '2d' in styles[style_id]['variants']
        assert '3d' in styles[style_id]['variants']


def test_3d_only_projection_styles_remain_available():
    styles = _by_id()
    for style_id in (
        'galaxy',
        'role_layers',
        'dependency_tower',
        'authority_space',
        'relation_orbits',
        'relation_shells',
        'structure_spine',
    ):
        assert style_id in styles
        assert styles[style_id]['dimensions'] == ['3d']
        assert '3d' in styles[style_id]['variants']


def test_2d_only_structure_reveal_styles_remain_available():
    styles = _by_id()
    for style_id in ('hierarchy_tree', 'relation_generations', 'component_islands'):
        assert style_id in styles
        assert styles[style_id]['dimensions'] == ['2d']
        assert '2d' in styles[style_id]['variants']
