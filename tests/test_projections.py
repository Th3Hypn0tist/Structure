import math
import unittest

from canonical_projections import PROJECTIONS, build_canonical_projection


GRAPH = {
    "nodes": [
        {"id": "root", "name": "Root", "type": "master", "status": "locked", "source_role": "boundary_master", "source": "root.json", "kind": "contract"},
        {"id": "a", "name": "A", "type": "module", "status": "locked", "source_role": "definition", "source": "a.json", "kind": "contract"},
        {"id": "b", "name": "B", "type": "module", "status": "unlocked", "source_role": "definition", "source": "b.json", "kind": "contract"},
        {"id": "c", "name": "C", "type": "member", "status": "locked", "source_role": "membership_registry", "source": "registry.json", "kind": "registry_member"},
    ],
    "edges": [
        {"id": "e1", "dimension": "containment", "source": "root", "target": "a", "type": "contains"},
        {"id": "e2", "dimension": "dependencies", "source": "a", "target": "b", "type": "requires"},
        {"id": "e3", "dimension": "ownership", "source": "root", "target": "c", "type": "owns"},
        {"id": "e4", "dimension": "authority", "source": "a", "target": "c", "type": "governs"},
        {"id": "e5", "dimension": "relations", "source": "b", "target": "c", "type": "related"},
    ],
}


class ProjectionTests(unittest.TestCase):
    def test_catalog_has_five_2d_and_five_3d(self):
        dims = [item["dimension"] for item in PROJECTIONS.values()]
        self.assertEqual(dims.count("2d"), 5)
        self.assertEqual(dims.count("3d"), 5)

    def test_every_projection_preserves_node_count(self):
        for projection_id in PROJECTIONS:
            with self.subTest(projection_id=projection_id):
                result = build_canonical_projection(GRAPH, projection_id)
                self.assertEqual(result["node_count"], len(GRAPH["nodes"]))

    def test_2d_geometry_is_finite(self):
        for projection_id, meta in PROJECTIONS.items():
            if meta["dimension"] != "2d":
                continue
            result = build_canonical_projection(GRAPH, projection_id)
            if result["kind"] == "matrix":
                self.assertEqual(len(result["order"]), len(GRAPH["nodes"]))
                continue
            for node in result["nodes"]:
                self.assertTrue(math.isfinite(node["x"]))
                self.assertTrue(math.isfinite(node["y"]))

    def test_3d_geometry_is_finite(self):
        for projection_id, meta in PROJECTIONS.items():
            if meta["dimension"] != "3d":
                continue
            result = build_canonical_projection(GRAPH, projection_id)
            for node in result["nodes"]:
                self.assertTrue(math.isfinite(node["x"]))
                self.assertTrue(math.isfinite(node["y"]))
                self.assertTrue(math.isfinite(node["z"]))

    def test_dependency_views_only_render_dependency_edges(self):
        for projection_id in ("dependency_flow_2d", "dependency_tower_3d"):
            result = build_canonical_projection(GRAPH, projection_id)
            self.assertTrue(result["edges"])
            self.assertTrue(all(edge["dimension"] == "dependencies" for edge in result["edges"]))


if __name__ == "__main__":
    unittest.main()
