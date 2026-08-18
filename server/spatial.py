from __future__ import annotations

"""Canonical spatial helpers for Structure.

Entity ``position`` remains the existing three-component CW node position.
``coordinate_space_ref`` is optional. When present it gives that position an
explicit canonical coordinate-space anchor by referencing another Entity.

Coordinate spaces deliberately use the normal CW Entity identity namespace;
there is no parallel coordinate-space object catalog.
"""

from typing import Any


def _position_vector(entity: dict[str, Any]) -> list[float]:
    value = entity.get("position")
    if not (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(component, (int, float)) and not isinstance(component, bool) for component in value)
    ):
        raise ValueError(f"entity {entity.get('id', '<unknown>')}.position must be [x,y,z]")
    return [float(component) for component in value]


def coordinate_space_ref(entity: dict[str, Any]) -> str | None:
    ref = entity.get("coordinate_space_ref")
    if ref is None:
        return None
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError(f"entity {entity.get('id', '<unknown>')}.coordinate_space_ref must be a non-empty Entity ref")
    return ref


def canonical_spatial_position(entity: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical spatial tuple without introducing screen semantics."""
    position = _position_vector(entity)
    return {
        "position": {"x": position[0], "y": position[1], "z": position[2]},
        "coordinate_space_ref": coordinate_space_ref(entity),
    }


def validate_spatial_entities(entities: list[dict[str, Any]]) -> None:
    """Validate explicit coordinate-space references and recursive anchoring.

    A coordinate space is an ordinary Entity. Therefore refs resolve only to
    Entity identities, never Property identities. Parent-space chains may be
    arbitrarily deep but must remain acyclic.
    """
    entity_index: dict[str, dict[str, Any]] = {}
    for entity in entities:
        entity_id = entity.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            continue
        entity_index[entity_id] = entity
        _position_vector(entity)
        coordinate_space_ref(entity)

    for entity_id, entity in entity_index.items():
        ref = coordinate_space_ref(entity)
        if ref is None:
            continue
        if ref not in entity_index:
            raise ValueError(f"entity {entity_id}.coordinate_space_ref does not resolve to Entity: {ref}")
        if ref == entity_id:
            raise ValueError(f"entity {entity_id}.coordinate_space_ref cannot reference itself")

    for start in entity_index:
        seen: set[str] = set()
        current = start
        while True:
            ref = coordinate_space_ref(entity_index[current])
            if ref is None:
                break
            if ref in seen or ref == start:
                chain = " -> ".join([*seen, current, ref])
                raise ValueError(f"coordinate space cycle detected from {start}: {chain}")
            seen.add(current)
            current = ref
