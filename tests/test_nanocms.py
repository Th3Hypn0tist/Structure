import unittest

from nanocms import DEFAULT_PAGE, navigation, projection, resolve_page, resolve_view


class NanoCMSTests(unittest.TestCase):
    def test_default_page_resolves(self):
        page = resolve_page(None)
        self.assertEqual(page['id'], DEFAULT_PAGE)
        self.assertGreaterEqual(len(page['placements']), 1)

    def test_navigation_order_is_stable(self):
        items = navigation()
        self.assertEqual([item['id'] for item in items], ['canonical', 'raw-json'])

    def test_canonical_context_has_multiple_views(self):
        page = resolve_page('canonical')
        self.assertEqual(
            [p['id'] for p in page['placements']],
            ['view.canonical_structure_map', 'view.semantic_space_3d'],
        )

    def test_canonical_views_share_ruleset_and_context_model(self):
        two_d = resolve_view('canonical', 'view.canonical_structure_map')
        three_d = resolve_view('canonical', 'view.semantic_space_3d')
        self.assertEqual(two_d['ruleset'], 'CanonicalContract')
        self.assertEqual(three_d['ruleset'], 'CanonicalContract')
        self.assertEqual(two_d['context_model'], 'semantic_identity')
        self.assertEqual(three_d['context_model'], 'semantic_identity')
        self.assertEqual(two_d['renderer'], 'svg')
        self.assertEqual(three_d['renderer'], 'javascript_3d')

    def test_raw_json_context_places_raw_json_view(self):
        page = resolve_page('raw-json')
        self.assertEqual(page['placements'][0]['ruleset'], 'RawJSON')
        self.assertEqual(page['placements'][0]['context_model'], 'json_pointer')

    def test_projection_exposes_selected_view_without_changing_page(self):
        cms = projection('canonical', 'view.semantic_space_3d')
        self.assertEqual(cms['selected_page']['id'], 'canonical')
        self.assertEqual(cms['selected_view']['id'], 'view.semantic_space_3d')

    def test_unknown_page_fails(self):
        with self.assertRaises(KeyError):
            resolve_page('missing')

    def test_unknown_view_fails(self):
        with self.assertRaises(KeyError):
            resolve_view('canonical', 'missing')


if __name__ == '__main__':
    unittest.main()
