from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from flow_trace import build_trace


def _entry_index(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("id")): entry
        for entry in tree.get("entries", [])
        if isinstance(entry, dict) and entry.get("id") is not None
    }


def event_catalog(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only explicit behavior Event identities materialized by the reader."""
    out: list[dict[str, Any]] = []
    for entry_id, entry in _entry_index(tree).items():
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        if metadata.get("behavior_dimension") != "events" and entry.get("kind") != "behavior_event":
            continue
        owner_ref = metadata.get("behavior_owner") or entry.get("parent_id")
        out.append({
            "id": entry_id,
            "name": str(entry.get("name") or entry_id),
            "owner_ref": str(owner_ref) if owner_ref is not None else None,
            "status": entry.get("status"),
            "provenance": deepcopy(entry.get("provenance", {})),
        })
    return sorted(out, key=lambda item: ((item.get("owner_ref") or ""), item["name"].lower(), item["id"]))


def _explicit_start_steps(tree: dict[str, Any], event_id: str) -> list[str]:
    """An Event starts a step only when that step explicitly names it as cause_ref."""
    starts: set[str] = set()
    for flow in tree.get("flows", []):
        if not isinstance(flow, dict):
            continue
        for step in flow.get("steps", []):
            if not isinstance(step, dict) or not step.get("id"):
                continue
            if step.get("cause_ref") == event_id:
                starts.add(str(step["id"]))
    return sorted(starts)


def _step_impact_refs(step_record: dict[str, Any], known_ids: set[str]) -> list[str]:
    step = step_record.get("step") if isinstance(step_record.get("step"), dict) else {}
    refs: set[str] = set()
    for field in ("actor_ref", "action_ref", "data_ref", "target_ref", "condition_ref", "payload_ref"):
        ref = step.get(field)
        if isinstance(ref, str) and ref in known_ids:
            refs.add(ref)
    # Results/errors are visible effects of the step, but never continuation edges.
    for field in ("result_refs", "error_refs"):
        for ref in step.get(field, []):
            if isinstance(ref, str) and ref in known_ids:
                refs.add(ref)
    return sorted(refs)


def build_event_impact(tree: dict[str, Any], event_id: str, *, max_depth: int = 64) -> dict[str, Any]:
    entries = _entry_index(tree)
    known_ids = set(entries)
    starts = _explicit_start_steps(tree, event_id)
    waves: dict[int, dict[str, set[str]]] = defaultdict(lambda: {"step_ids": set(), "flow_ids": set(), "refs": set()})
    boundaries: list[dict[str, Any]] = []
    seen_steps: set[tuple[str, str]] = set()

    for start_step_id in starts:
        trace = build_trace(tree, start_step_id, max_depth=max_depth)
        boundaries.extend(deepcopy(trace.get("boundaries", [])))
        for record in trace.get("steps", []):
            if not isinstance(record, dict):
                continue
            step_id = str(record.get("step_id") or "")
            flow_id = str(record.get("flow_id") or "")
            key = (flow_id, step_id)
            if not step_id or key in seen_steps:
                continue
            seen_steps.add(key)
            depth = max(0, int(record.get("depth") or 0))
            wave = waves[depth]
            wave["step_ids"].add(step_id)
            if flow_id:
                wave["flow_ids"].add(flow_id)
            wave["refs"].update(_step_impact_refs(record, known_ids))

    event = entries.get(event_id, {})
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    owner_ref = metadata.get("behavior_owner") or event.get("parent_id")
    return {
        "event_id": event_id,
        "owner_ref": str(owner_ref) if owner_ref is not None else None,
        "start_step_refs": starts,
        "waves": [
            {
                "depth": depth,
                "step_ids": sorted(values["step_ids"]),
                "flow_ids": sorted(values["flow_ids"]),
                "refs": sorted(values["refs"]),
            }
            for depth, values in sorted(waves.items())
        ],
        "boundaries": boundaries,
        "causal_source": "steps[].cause_ref == event_id, then next_step_refs/subflow_refs/resume_ref only",
        "visible_effect_refs": "step actor/action/data/target/condition/payload/result/error refs",
        "forbidden_continuation_sources": [
            "result_refs", "error_refs", "dependencies", "containment", "ownership", "authority",
            "topic membership", "topic inheritance", "topic composition", "generic relations", "array order",
        ],
        "inference": False,
    }


def build_event_surface(tree: dict[str, Any], *, max_depth: int = 64) -> dict[str, Any]:
    events = event_catalog(tree)
    return {
        "events": events,
        "traces": {event["id"]: build_event_impact(tree, event["id"], max_depth=max_depth) for event in events},
        "inference": False,
    }


__all__ = ["event_catalog", "build_event_impact", "build_event_surface"]
