from __future__ import annotations

from collections import Counter
from typing import Any

from cw14_model import (
    bootstrap_identity_ids,
    is_v14,
    materialize_behavior_identities,
    materialize_flows,
    materialize_topics,
)


def _reference_errors(tree: dict[str, Any], snapshot: Any) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    ids = [str(entry.get("id")) for entry in tree.get("entries", []) if entry.get("id") is not None]
    counts = Counter(ids)
    active_ids = set(ids)

    for identity_id, count in counts.items():
        if count > 1:
            errors.append({"id": "CF_AMBIGUOUS_IDENTITY", "message": f"Identity {identity_id} has {count} active definitions"})

    flow_ids = {str(flow.get("id")) for flow in tree.get("flows", []) if flow.get("id")}
    step_ids: set[str] = set()
    duplicate_steps: set[str] = set()
    for flow in tree.get("flows", []):
        for step in flow.get("steps", []):
            step_id = str(step.get("id") or "")
            if not step_id:
                continue
            if step_id in step_ids:
                duplicate_steps.add(step_id)
            step_ids.add(step_id)
    for step_id in sorted(duplicate_steps):
        errors.append({"id": "CF_AMBIGUOUS_IDENTITY", "message": f"Flow step identity {step_id} is duplicated"})

    semantic_refs = active_ids | flow_ids | step_ids

    def require(ref: Any, *, source: str, field: str, allow_none: bool = False, domains: set[str] | None = None) -> None:
        if ref is None and allow_none:
            return
        if not isinstance(ref, str) or not ref:
            if allow_none:
                return
            errors.append({"id": "CF_UNRESOLVED_REFERENCE", "message": f"{source} has empty {field}", "source": source, "field": field})
            return
        target_space = domains if domains is not None else semantic_refs
        if ref not in target_space:
            errors.append({"id": "CF_UNRESOLVED_REFERENCE", "message": f"{source} unresolved {field}: {ref}", "source": source, "field": field})

    for topic in tree.get("topics", []):
        topic_id = str(topic.get("id") or "")
        require(topic.get("owner_ref"), source=topic_id, field="owner_ref", domains=active_ids)
        if topic.get("parent_topic_ref") is not None:
            require(topic.get("parent_topic_ref"), source=topic_id, field="parent_topic_ref", domains={str(x.get("id")) for x in tree.get("topics", [])})
        for field, domain in (
            ("member_refs", active_ids),
            ("operation_refs", active_ids),
            ("event_refs", active_ids),
            ("flow_refs", flow_ids),
            ("child_topic_refs", {str(x.get("id")) for x in tree.get("topics", [])}),
        ):
            for ref in topic.get(field, []):
                require(ref, source=topic_id, field=field, domains=domain)

    for flow in tree.get("flows", []):
        flow_id = str(flow.get("id") or "")
        require(flow.get("owner_ref"), source=flow_id, field="owner_ref", domains=active_ids)
        for ref in flow.get("entry_refs", []):
            require(ref, source=flow_id, field="entry_refs", domains=step_ids | active_ids)
        for ref in flow.get("exit_refs", []):
            require(ref, source=flow_id, field="exit_refs", domains=step_ids | active_ids)
        local_steps = {str(step.get("id")) for step in flow.get("steps", []) if step.get("id")}
        for step in flow.get("steps", []):
            step_id = str(step.get("id") or "")
            for field in ("actor_ref", "action_ref", "data_ref", "target_ref", "cause_ref", "condition_ref", "payload_ref", "resume_ref"):
                require(step.get(field), source=step_id, field=field, allow_none=True)
            for field in ("result_refs", "error_refs"):
                for ref in step.get(field, []):
                    require(ref, source=step_id, field=field)
            for ref in step.get("next_step_refs", []):
                require(ref, source=step_id, field="next_step_refs", domains=local_steps)
            for ref in step.get("subflow_refs", []):
                require(ref, source=step_id, field="subflow_refs", domains=flow_ids)

    bootstrap_ids = bootstrap_identity_ids(snapshot)
    covered: set[str] = set()
    for topic in tree.get("topics", []):
        covered.update(str(ref) for ref in topic.get("member_refs", []))
        covered.update(str(ref) for ref in topic.get("operation_refs", []))
        covered.update(str(ref) for ref in topic.get("event_refs", []))
    for identity_id in sorted(active_ids - bootstrap_ids - covered):
        errors.append({"id": "CF_TOPIC_MEMBERSHIP_MISSING", "message": f"Active identity {identity_id} is not reachable through any Topic grouping", "identity": identity_id})

    return errors


def enrich_v14(tree: dict[str, Any], snapshot: Any) -> dict[str, Any]:
    if not is_v14(snapshot):
        raise ValueError("enrich_v14 requires Canonical Contract Format 1.4")

    errors = list(tree.get("errors", []))
    errors.extend(materialize_behavior_identities(tree, snapshot))
    errors.extend(materialize_topics(tree, snapshot))
    errors.extend(materialize_flows(tree, snapshot))
    errors.extend(_reference_errors(tree, snapshot))

    tree["errors"] = errors
    tree["validation_errors"] = []
    tree["valid"] = bool(tree.get("valid")) and not errors
    tree.setdefault("source_result", {})["canonical_contract_format_1_4"] = {
        "enabled": True,
        "topics_source": "contract.topics[] recursively",
        "behavior_source": "behavior.states/interfaces/operations/events/flows",
        "causality_source": "behavior.flows[].steps[] only",
        "topic_membership_semantic_authority": False,
        "topic_membership_implies_structure": False,
        "topic_membership_implies_causality": False,
        "path_inference": False,
        "software_specific_heuristics": False,
        "inference": False,
    }
    return tree
