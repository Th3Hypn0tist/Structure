from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


_LIBRARY_PATH = Path(__file__).resolve().parent / "effects" / "3d" / "library.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("structureprojector_effects3d_library", _LIBRARY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load 3D effect library: {_LIBRARY_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_effects(projection: dict[str, Any], supplied: dict[str, Any] | None = None) -> dict[str, Any]:
    return _load().apply_universal_effects(projection, supplied)


def manifest() -> dict[str, Any]:
    return _load().library_manifest()


def defaults() -> dict[str, Any]:
    return _load().universal_defaults()


def controls() -> list[dict[str, Any]]:
    return _load().universal_controls()


def presets() -> dict[str, dict[str, Any]]:
    return _load().group_presets()
