import unittest

from nanocms import DEFAULT_PAGE, navigation, projection, resolve_page


class NanoCMSTests(unittest.TestCase):
    def test_default_page_resolves(self):
        page = resolve_page(None)
        self.assertEqual(page['id'], DEFAULT_PAGE)
        self.assertEqual(len(page['placements']), 1)

    def test_navigation_order_is_stable(self):
        items = navigation()
        self.assertEqual([item['id'] for item in items], ['canonical-structure', 'raw-json'])

    def test_canonical_page_places_canonical_ruleset(self):
        page = resolve_page('canonical-structure')
        self.assertEqual(page['placements'][0]['ruleset'], 'CanonicalContract')
        self.assertEqual(page['placements'][0]['renderer'], 'svg')

    def test_raw_json_page_places_raw_json_ruleset(self):
        page = resolve_page('raw-json')
        self.assertEqual(page['placements'][0]['ruleset'], 'RawJSON')

    def test_projection_exposes_navigation_and_selected_page(self):
        cms = projection('raw-json')
        self.assertEqual(cms['selected_page']['id'], 'raw-json')
        self.assertEqual(len(cms['navigation']), 2)

    def test_unknown_page_fails(self):
        with self.assertRaises(KeyError):
            resolve_page('missing')


if __name__ == '__main__':
    unittest.main()
