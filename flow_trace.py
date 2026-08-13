from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from typing import Any


def trace_catalog(tree: dict[str, Any]) -> list[dict[str, Any]]:
    refs: set[str] = set()
    for flow in tree.get("flows", []):
        cause = flow.get("cause_ref")
        if isinstance(cause, str) and cause:
            refs.add(cause)
    entries = {str(e.get("id")): e for e in tree.get("entries", []) if e.get("id") is not None}
    return [{"id": ref, "name": str(entries.get(ref, {}).get("name") or ref)} for ref in sorted(refs)]


def build_trace(tree: dict[str, Any], root_ref: str, *, max_depth: int = 64) -> dict[str, Any]:
    """Reconstruct a causal trace from explicit CW behavior.flows only."""
    max_depth = max(0, min(512, int(max_depth)))
    flows = [deepcopy(flow) for flow in tree.get("flows", []) if isinstance(flow, dict)]
    by_cause: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for flow in flows:
        cause = flow.get("cause_ref")
        if isinstance(cause, str) and cause:
            by_cause[cause].append(flow)
    for values in by_cause.values():
        values.sort(key=lambda item: str(item.get("id") or ""))

    steps: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    queue = deque([(str(root_ref), 0, None)])
    visited_flows: set[str] = set()

    while queue:
        cause_ref, depth, parent_flow_id = queue.popleft()
        if depth > max_depth:
            boundaries.append({"type": "depth_limit", "ref": cause_ref, "depth": depth})
            continue
        matching = by_cause.get(cause_ref, [])
        if not matching:
            boundaries.append({"type": "terminal", "ref": cause_ref, "depth": depth})
            continue
        for flow in matching:
            flow_id = str(flow.get("id") or "")
            if flow_id in visited_flows:
                boundaries.append({"type": "cycle_or_revisit", "ref": cause_ref, "flow_id": flow_id, "depth": depth})
                continue
            visited_flows.add(flow_id)
            result_refs = [str(ref) for ref in flow.get("result_refs", [])]
            steps.append({
                "index": len(steps),
                "depth": depth,
                "parent_flow_id": parent_flow_id,
                "flow_id": flow_id,
                "kind": flow.get("kind"),
                "WHO": flow.get("actor_ref"),
                "WHAT": {"action_ref": flow.get("action_ref"), "data_ref": flow.get("data_ref"), "kind": flow.get("kind")},
                "WHERE": flow.get("target_ref"),
                "WHY": flow.get("cause_ref"),
                "result_refs": result_refs,
                "flow": flow,
            })
            if not result_refs:
                boundaries.append({"type": "terminal_flow", "flow_id": flow_id, "depth": depth})
            for result_ref in result_refs:
                queue.append((result_ref, depth + 1, flow_id))

    return {
        "root_ref": str(root_ref),
        "max_depth": max_depth,
        "steps": steps,
        "boundaries": boundaries,
        "flow_count": len(steps),
        "branching": True,
        "causal_source": "behavior.flows[] only",
        "forbidden_causal_sources": ["dependencies", "containment", "ownership", "authority", "membership", "generic relations", "prose", "layout", "array order"],
        "inference": False,
    }
