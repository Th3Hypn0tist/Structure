from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any


def trace_catalog(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """List explicit flows as trace roots; no causality is inferred from results."""
    return [
        {
            "id": str(flow.get("id")),
            "name": str(flow.get("name") or flow.get("id")),
            "flow_type": flow.get("flow_type"),
            "owner_ref": flow.get("owner_ref"),
        }
        for flow in sorted(
            (flow for flow in tree.get("flows", []) if isinstance(flow, dict) and flow.get("id")),
            key=lambda item: str(item.get("id")),
        )
    ]


def build_trace(tree: dict[str, Any], root_ref: str, *, max_depth: int = 64) -> dict[str, Any]:
    """Reconstruct execution only from explicit Canonical 1.4 flow continuation data."""
    max_depth = max(0, min(512, int(max_depth)))
    flows = [deepcopy(flow) for flow in tree.get("flows", []) if isinstance(flow, dict) and flow.get("id")]
    by_flow = {str(flow["id"]): flow for flow in flows}
    step_owner: dict[str, str] = {}
    by_step: dict[str, dict[str, Any]] = {}
    duplicate_steps: set[str] = set()

    for flow in flows:
        flow_id = str(flow["id"])
        for step in flow.get("steps", []):
            if not isinstance(step, dict) or not step.get("id"):
                continue
            step_id = str(step["id"])
            if step_id in by_step:
                duplicate_steps.add(step_id)
                continue
            by_step[step_id] = step
            step_owner[step_id] = flow_id

    boundaries: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []

    if duplicate_steps:
        for step_id in sorted(duplicate_steps):
            boundaries.append({"type": "ambiguous_step_identity", "ref": step_id})

    root = str(root_ref)
    if root in by_flow:
        start_flow = by_flow[root]
        start_refs = [str(ref) for ref in start_flow.get("entry_refs", [])]
    elif root in by_step:
        start_refs = [root]
    else:
        # An external identity may be an explicit flow entry, but it does not
        # identify an executable first step. Surface it instead of guessing.
        matching = [
            str(flow["id"])
            for flow in flows
            if root in {str(ref) for ref in flow.get("entry_refs", [])}
        ]
        return {
            "root_ref": root,
            "max_depth": max_depth,
            "steps": [],
            "boundaries": [{"type": "external_entry_without_step_ref", "ref": root, "flow_ids": sorted(matching)}],
            "step_count": 0,
            "flow_count": 0,
            "branching": True,
            "causal_source": "behavior.flows[].steps[].next_step_refs/subflow_refs/resume_ref only",
            "inference": False,
        }

    # queue item: step_ref, depth, parent_step_id, call_flow_id, resume_ref
    queue = deque((ref, 0, None, None, None) for ref in start_refs)
    visited: set[tuple[str, str | None, str | None]] = set()
    visited_flows: set[str] = set()

    while queue:
        step_ref, depth, parent_step_id, call_flow_id, pending_resume_ref = queue.popleft()
        if depth > max_depth:
            boundaries.append({"type": "depth_limit", "ref": step_ref, "depth": depth})
            continue
        step = by_step.get(step_ref)
        if step is None:
            boundaries.append({"type": "non_step_entry_or_unresolved_step", "ref": step_ref, "depth": depth})
            continue

        flow_id = step_owner[step_ref]
        visited_flows.add(flow_id)
        visit_key = (step_ref, call_flow_id, pending_resume_ref)
        if visit_key in visited:
            boundaries.append({"type": "cycle_or_revisit", "ref": step_ref, "flow_id": flow_id, "depth": depth})
            continue
        visited.add(visit_key)

        next_refs = [str(ref) for ref in step.get("next_step_refs", [])]
        subflow_refs = [str(ref) for ref in step.get("subflow_refs", [])]
        resume_ref = str(step.get("resume_ref")) if step.get("resume_ref") is not None else None

        steps.append({
            "index": len(steps),
            "depth": depth,
            "flow_id": flow_id,
            "step_id": step_ref,
            "parent_step_id": parent_step_id,
            "called_from_flow_id": call_flow_id,
            "WHO": step.get("actor_ref"),
            "WHAT": {"action_ref": step.get("action_ref"), "data_ref": step.get("data_ref")},
            "WHERE": step.get("target_ref"),
            "WHY": step.get("cause_ref"),
            "condition_ref": step.get("condition_ref"),
            "payload_ref": step.get("payload_ref"),
            "result_refs": deepcopy(step.get("result_refs", [])),
            "error_refs": deepcopy(step.get("error_refs", [])),
            "next_step_refs": next_refs,
            "subflow_refs": subflow_refs,
            "resume_ref": resume_ref,
            "step": deepcopy(step),
        })

        # next_step_refs are the only local step continuation edges.
        for next_ref in next_refs:
            queue.append((next_ref, depth + 1, step_ref, call_flow_id, pending_resume_ref))

        # Each explicit subflow is a branch. Enter only its explicit entry_refs.
        for subflow_id in subflow_refs:
            subflow = by_flow.get(subflow_id)
            if subflow is None:
                boundaries.append({"type": "unresolved_subflow", "ref": subflow_id, "step_id": step_ref, "depth": depth})
                continue
            entries = [str(ref) for ref in subflow.get("entry_refs", [])]
            if not entries:
                boundaries.append({"type": "subflow_without_entry", "ref": subflow_id, "step_id": step_ref, "depth": depth})
                continue
            for entry_ref in entries:
                queue.append((entry_ref, depth + 1, step_ref, flow_id, resume_ref))

        # A leaf reached inside a subflow resumes only through the caller's
        # explicit resume_ref. Result values never create continuation.
        if not next_refs and not subflow_refs and pending_resume_ref is not None:
            queue.append((pending_resume_ref, depth + 1, step_ref, None, None))
        elif not next_refs and not subflow_refs and pending_resume_ref is None:
            boundaries.append({"type": "terminal_step", "ref": step_ref, "flow_id": flow_id, "depth": depth})

    return {
        "root_ref": root,
        "max_depth": max_depth,
        "steps": steps,
        "boundaries": boundaries,
        "step_count": len(steps),
        "flow_count": len(visited_flows),
        "flow_ids": sorted(visited_flows),
        "branching": True,
        "causal_source": "behavior.flows[].steps[].next_step_refs/subflow_refs/resume_ref only",
        "forbidden_causal_sources": [
            "result_refs", "dependencies", "containment", "ownership", "authority",
            "topic membership", "topic inheritance", "topic composition", "generic relations",
            "prose", "layout", "array order",
        ],
        "inference": False,
    }
