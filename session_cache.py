from __future__ import annotations

from copy import deepcopy
import json
from threading import RLock
from typing import Any, Callable

from input_modules.canonical import read as read_canonical
from source_selection import load_source
from structure_tree import tree_to_graph


_LOCK = RLock()
_SOURCE_CACHE: dict[str, dict[str, Any]] = {}


def _source_key(source_spec: dict[str, Any]) -> str:
    return json.dumps(source_spec, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def load_cached_master(item: dict[str, Any], *, refresh: bool = False) -> dict[str, Any]:
    """Load and resolve one source once, then reuse its StructureTree.

    Projection requests must never re-read or re-resolve the source. The only
    refresh boundary is an explicit source selection/reload.
    """
    source_spec = deepcopy(item["source"])
    key = _source_key(source_spec)
    with _LOCK:
        cached = None if refresh else _SOURCE_CACHE.get(key)
        if cached is None:
            snapshot = load_source(source_spec)
            tree = read_canonical(snapshot)
            cached = {
                "snapshot": snapshot,
                "tree": tree,
                "graph": tree_to_graph(tree),
                "semantic_surfaces": {},
                "visual_surfaces": {},
                "source_key": key,
            }
            _SOURCE_CACHE[key] = cached
            cache_hit = False
        else:
            cache_hit = True

    return {
        "id": item["id"],
        "name": item.get("name") or item["id"],
        "source_spec": source_spec,
        "snapshot": cached["snapshot"],
        "tree": cached["tree"],
        "graph": cached["graph"],
        "source_key": key,
        "source_cache_hit": cache_hit,
        "semantic_surfaces": cached["semantic_surfaces"],
        "visual_surfaces": cached["visual_surfaces"],
    }


def cached_semantic_surface(
    master: dict[str, Any],
    key: tuple[Any, ...],
    builder: Callable[[], tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], bool]:
    cache = master["semantic_surfaces"]
    with _LOCK:
        hit = key in cache
        if not hit:
            graph, metadata, depths = builder()
            cache[key] = (deepcopy(graph), deepcopy(metadata), deepcopy(depths))
        graph, metadata, depths = cache[key]
    return deepcopy(graph), deepcopy(metadata), deepcopy(depths), hit


def cached_visual_surface(
    master: dict[str, Any],
    key: tuple[Any, ...],
    builder: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    cache = master["visual_surfaces"]
    with _LOCK:
        hit = key in cache
        if not hit:
            cache[key] = deepcopy(builder())
        projection = cache[key]
    return deepcopy(projection), hit


def cache_stats() -> dict[str, int]:
    with _LOCK:
        return {
            "source_count": len(_SOURCE_CACHE),
            "semantic_surface_count": sum(len(item["semantic_surfaces"]) for item in _SOURCE_CACHE.values()),
            "visual_surface_count": sum(len(item["visual_surfaces"]) for item in _SOURCE_CACHE.values()),
        }


def clear_source_cache(source_spec: dict[str, Any] | None = None) -> None:
    with _LOCK:
        if source_spec is None:
            _SOURCE_CACHE.clear()
        else:
            _SOURCE_CACHE.pop(_source_key(source_spec), None)


__all__ = [
    "load_cached_master",
    "cached_semantic_surface",
    "cached_visual_surface",
    "cache_stats",
    "clear_source_cache",
]
