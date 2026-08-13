from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

DEFAULT_PROFILE_PATH = os.getenv(
    "STRUCTURE_TOPIC_PROFILE",
    os.path.join("profiles", "AIGMos_Structure_Projector_Topic_Profile_v1.0.json"),
)


def load_topic_profile(base_dir: str, path: str | None = None) -> dict[str, Any] | None:
    relative = path or DEFAULT_PROFILE_PATH
    absolute = relative if os.path.isabs(relative) else os.path.join(base_dir, relative)
    if not os.path.exists(absolute):
        return None
    with open(absolute, "r", encoding="utf-8") as handle:
        profile = json.load(handle)
    if not isinstance(profile, dict) or profile.get("profile_type") != "structure_projector_topic_profile":
        raise ValueError(f"Invalid Structure topic profile: {relative}")
    topics = profile.get("topics")
    if not isinstance(topics, list):
        raise ValueError(f"Structure topic profile topics must be an array: {relative}")
    return profile


def attach_topic_profile(tree: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any]:
    if profile is None:
        tree.pop("topic_profile", None)
        return tree
    tree["topic_profile"] = deepcopy(profile)
    return tree


def _entries(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("id")): entry
        for entry in tree.get("entries", [])
        if entry.get("id") is not None
    }


def resolve_topic_profile(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve profile selectors without inventing semantic membership.

    `include[]` is software-profile evidence. A selector resolves only when it is
    an exact canonical identity id or an exact, unambiguous canonical display
    name. Parent/children/category/layout fields are navigation/presentation only.
    """
    profile = tree.get("topic_profile")
    if not isinstance(profile, dict):
        return []
    entries = _entries(tree)
    by_name: dict[str, list[str]] = {}
    for entry_id, entry in entries.items():
        name = str(entry.get("name") or "")
        if name:
            by_name.setdefault(name, []).append(entry_id)

    result: list[dict[str, Any]] = []
    for raw_topic in profile.get("topics", []):
        if not isinstance(raw_topic, dict) or not raw_topic.get("id"):
            continue
        resolved: set[str] = set()
        unresolved: list[str] = []
        ambiguous: dict[str, list[str]] = {}
        for selector in raw_topic.get("include", []):
            if not isinstance(selector, str) or not selector:
                continue
            if selector in entries:
                resolved.add(selector)
                continue
            matches = sorted(by_name.get(selector, []))
            if len(matches) == 1:
                resolved.add(matches[0])
            elif len(matches) > 1:
                ambiguous[selector] = matches
            else:
                unresolved.append(selector)
        result.append({
            "id": str(raw_topic["id"]),
            "label": str(raw_topic.get("label") or raw_topic["id"]),
            "category": raw_topic.get("category"),
            "parent": raw_topic.get("parent"),
            "children": deepcopy(raw_topic.get("children", [])),
            "aliases": deepcopy(raw_topic.get("aliases", [])),
            "layout_hint": deepcopy(raw_topic.get("layout_hint")),
            "resolved_identity_ids": sorted(resolved),
            "resolved_identity_count": len(resolved),
            "unresolved_selectors": unresolved,
            "ambiguous_selectors": ambiguous,
            "profile_membership_semantic_authority": False,
            "resolution_rule": "exact canonical id or exact unambiguous canonical display name only",
        })
    return result


def profile_catalog(tree: dict[str, Any]) -> dict[str, Any] | None:
    profile = tree.get("topic_profile")
    if not isinstance(profile, dict):
        return None
    return {
        "name": profile.get("name"),
        "version": profile.get("version"),
        "software": profile.get("software"),
        "topics": resolve_topic_profile(tree),
        "lenses": deepcopy(profile.get("lenses", [])),
        "integration_surfaces": deepcopy(profile.get("integration_surfaces", [])),
        "flow_projection": deepcopy(profile.get("flow_projection", {})),
        "projector_rules": deepcopy(profile.get("projector_rules", [])),
    }
