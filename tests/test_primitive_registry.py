import pytest

from primitive_registry import PrimitiveRegistryError, load_registry, resolve_primitive, validate_registry


def test_registry_has_shared_box_geometry():
    registry = load_registry()
    assert registry["version"] == "1.1"
    assert validate_registry(registry) == []
    box = registry["primitives"]["box"]
    assert box["render_mode"] == "instanced_mesh"
    assert box["geometry"]["shape"] == "unit_box"


def test_missing_ref_uses_declared_fallback_only():
    primitive_ref, definition = resolve_primitive(None)
    assert primitive_ref == "box"
    assert definition["geometry"]["shape"] == "unit_box"


def test_unknown_explicit_ref_is_rejected():
    with pytest.raises(PrimitiveRegistryError):
        resolve_primitive("not-a-real-primitive")
