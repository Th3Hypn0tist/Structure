from scene_composer import compose_scene
from scene_contract import validate_scene


def _tree():
    return {
        "format": "STRUCTUREPROJECTOR_STRUCTURE_TREE",
        "version": "1.0",
        "input_module": "test",
        "source": {"revision": "abc"},
        "roots": ["A", "B"],
        "entries": [
            {"id": "A", "name": "A", "kind": "test", "type": "module", "parent_id": None, "status": None, "metadata": {}, "provenance": {}},
            {"id": "B", "name": "B", "kind": "test", "type": "module", "parent_id": None, "status": None, "metadata": {}, "provenance": {}},
        ],
        "links": [
            {
                "id": "dep:A->B",
                "source_id": "A",
                "target_id": "B",
                "dimension": "dependencies",
                "type": "depends_on",
                "metadata": {},
                "provenance": {"path": "contract.json"},
            }
        ],
        "errors": [],
        "warnings": [],
    }


def _projection(pid, nodes):
    return {
        "id": pid,
        "title": pid,
        "nodes": [
            {"id": node_id, "name": node_id, "x": i * 100, "y": 0, "z": 0}
            for i, node_id in enumerate(nodes)
        ],
        "edges": [],
        "groups": [],
    }


def test_projection_is_one_scene_object_with_nodes():
    scene = compose_scene([_projection("one", ["A", "B"])], _tree())
    assert len(scene["objects"]) == 1
    assert scene["objects"][0]["id"] == "projection:one"
    assert {n["id"] for n in scene["objects"][0]["nodes"]} == {"A", "B"}
    assert validate_scene(scene) == []


def test_explicit_link_can_cross_projection_objects():
    scene = compose_scene(
        [_projection("left", ["A"]), _projection("right", ["B"])],
        _tree(),
    )
    cross = [c for c in scene["connections"] if c.get("scope") == "cross_projection"]
    assert len(cross) == 1
    connection = cross[0]
    assert connection["channel"] == "dependencies"
    assert connection["type"] == "depends_on"
    assert connection["from"] == {"object": "projection:left", "node": "A", "anchor": "center"}
    assert connection["to"] == {"object": "projection:right", "node": "B", "anchor": "center"}
    assert connection["provenance"] == {"path": "contract.json"}
    assert validate_scene(scene) == []


def test_no_cross_projection_connection_is_inferred_without_tree_link():
    tree = _tree()
    tree["links"] = []
    scene = compose_scene(
        [_projection("left", ["A"]), _projection("right", ["B"])],
        tree,
    )
    assert [c for c in scene["connections"] if c.get("scope") == "cross_projection"] == []
    assert validate_scene(scene) == []
