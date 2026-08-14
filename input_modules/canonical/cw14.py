from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

from cw14_model import (
    bootstrap_identity_ids,
    explicit_outsiders,
    is_v14,
    materialize_behavior_identities,
    materialize_flows,
    materialize_topics,
)


def _cycle_errors(adjacency: dict[str, list[str]], *, error_id: str, relation: str) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(topic_id: str, stack: list[str]) -> None:
        if topic_id in visiting:
            try:
                start = stack.index(topic_id)
                cycle = stack[start:] + [topic_id]
            except ValueError:
                cycle = stack + [topic_id]
            errors.append({
                "id": error_id,
                "message": f"Topic {relation} cycle: {' -> '.join(cycle)}",
                "topic": topic_id,
                "cycle": cycle,
            })
            return
        if topic_id in visited:
            return
        visiting.add(topic_id)
        stack.append(topic_id)
        for target in adjacency.get(topic_id, []):
            visit(target, stack)
        stack.pop()
        visiting.remove(topic_id)
        visited.add(topic_id)

    for topic_id in sorted(adjacency):
        visit(topic_id, [])
    return errors


def _topic_resolution(tree: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    topics = [topic for topic in tree.get("topics", []) if isinstance(topic, dict)]
    topic_ids = [str(topic.get("id") or "") for topic in topics if topic.get("id")]
    counts = Counter(topic_ids)
    by_id = {str(topic.get("id")): topic for topic in topics if topic.get("id")}

    for topic_id, count in sorted(counts.items()):
        if count > 1:
            errors.append({"id": "CF_AMBIGUOUS_IDENTITY", "message": f"Topic identity {topic_id} has {count} active definitions", "topic": topic_id})

    parent_graph: dict[str, list[str]] = {}
    composition_graph: dict[str, list[str]] = {}
    for topic in topics:
        topic_id = str(topic.get("id") or "")
        parent_graph[topic_id] = [str(ref) for ref in topic.get("parent_topic_refs", [])]
        composition_graph[topic_id] = [str(ref) for ref in topic.get("composed_topic_refs", [])]

    errors.extend(_cycle_errors(parent_graph, error_id="CF_TOPIC_INHERITANCE_CYCLE", relation="inheritance"))
    errors.extend(_cycle_errors(composition_graph, error_id="CF_TOPIC_COMPOSITION_CYCLE", relation="composition"))

    ancestor_cache: dict[str, set[str]] = {}
    component_cache: dict[str, set[str]] = {}

    def ancestors(topic_id: str, stack: set[str] | None = None) -> set[str]:
        if topic_id in ancestor_cache:
            return set(ancestor_cache[topic_id])
        stack = set(stack or set())
        if topic_id in stack:
            return set()
        stack.add(topic_id)
        result: set[str] = set()
        for parent_id in parent_graph.get(topic_id, []):
            if parent_id not in by_id:
                continue
            result.add(parent_id)
            result.update(ancestors(parent_id, stack))
        ancestor_cache[topic_id] = set(result)
        return result

    def components(topic_id: str, stack: set[str] | None = None) -> set[str]:
        if topic_id in component_cache:
            return set(component_cache[topic_id])
        stack = set(stack or set())
        if topic_id in stack:
            return set()
        stack.add(topic_id)
        result: set[str] = set()
        for component_id in composition_graph.get(topic_id, []):
            if component_id not in by_id:
                continue
            result.add(component_id)
            result.update(components(component_id, stack))
        component_cache[topic_id] = set(result)
        return result

    direct_memberships: dict[str, set[str]] = {}
    inherited_memberships: dict[str, set[str]] = {}
    for topic in topics:
        topic_id = str(topic.get("id") or "")
        direct = set(str(ref) for ref in topic.get("member_refs", []))
        direct.update(str(ref) for ref in topic.get("operation_refs", []))
        direct.update(str(ref) for ref in topic.get("event_refs", []))
        direct_memberships[topic_id] = direct
        inherited_memberships[topic_id] = set(direct)

    # A member of a child Topic is also a grouping member of every explicitly
    # inherited ancestor Topic. No semantic structure or authority is copied.
    for topic_id, members in direct_memberships.items():
        for ancestor_id in ancestors(topic_id):
            inherited_memberships.setdefault(ancestor_id, set()).update(members)

    resolved_topics: list[dict[str, Any]] = []
    for topic in topics:
        topic_id = str(topic.get("id") or "")
        ancestor_ids = sorted(ancestors(topic_id))
        component_ids = sorted(components(topic_id))
        composed_trace = {
            "member_refs": set(),
            "relation_refs": set(),
            "operation_refs": set(),
            "event_refs": set(),
            "flow_refs": set(),
        }
        for component_id in component_ids:
            component = by_id.get(component_id) or {}
            composed_trace["member_refs"].update(str(ref) for ref in component.get("member_refs", []))
            composed_trace["relation_refs"].update(str(ref) for ref in component.get("relation_refs", []))
            composed_trace["operation_refs"].update(str(ref) for ref in component.get("operation_refs", []))
            composed_trace["event_refs"].update(str(ref) for ref in component.get("event_refs", []))
            composed_trace["flow_refs"].update(str(ref) for ref in component.get("flow_refs", []))

        resolved = deepcopy(topic)
        resolved["resolved_ancestor_topic_refs"] = ancestor_ids
        resolved["resolved_component_topic_refs"] = component_ids
        resolved["resolved_grouping_member_refs"] = sorted(inherited_memberships.get(topic_id, set()))
        resolved["composed_trace_surface"] = {key: sorted(values) for key, values in composed_trace.items()}
        resolved["topic_semantic_authority"] = False
        resolved["topic_implies_structure"] = False
        resolved["topic_implies_causality"] = False
        resolved_topics.append(resolved)

    return {
        "topics": resolved_topics,
        "by_id": by_id,
        "topic_ids": set(by_id),
        "direct_memberships": direct_memberships,
        "inherited_memberships": inherited_memberships,
    }, errors


def _reference_and_coverage_errors(tree: dict[str, Any], snapshot: Any, resolution: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    ids = [str(entry.get("id")) for entry in tree.get("entries", []) if entry.get("id") is not None]
    counts = Counter(ids)
    active_ids = set(ids)
    links = [link for link in tree.get("links", []) if isinstance(link, dict)]
    relation_ids = {str(link.get("id")) for link in links if link.get("id")}

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
    topic_ids: set[str] = resolution["topic_ids"]

    def require(ref: Any, *, source: str, field: str, allow_none: bool = False, domains: set[str] | None = None, missing_id: str = "CF_UNRESOLVED_REFERENCE") -> None:
        if ref is None and allow_none:
            return
        if not isinstance(ref, str) or not ref:
            if allow_none:
                return
            errors.append({"id": missing_id, "message": f"{source} has empty {field}", "source": source, "field": field})
            return
        target_space = domains if domains is not None else semantic_refs
        if ref not in target_space:
            errors.append({"id": missing_id, "message": f"{source} unresolved {field}: {ref}", "source": source, "field": field})

    for topic in tree.get("topics", []):
        topic_id = str(topic.get("id") or "")
        require(topic.get("owner_ref"), source=topic_id, field="owner_ref", domains=active_ids)
        if topic.get("container_topic_ref") is not None:
            require(topic.get("container_topic_ref"), source=topic_id, field="container_topic_ref", domains=topic_ids)
        for ref in topic.get("parent_topic_refs", []):
            require(ref, source=topic_id, field="parent_topic_refs", domains=topic_ids)
        for ref in topic.get("composed_topic_refs", []):
            require(ref, source=topic_id, field="composed_topic_refs", domains=topic_ids, missing_id="CF_TOPIC_COMPOSITION_UNRESOLVED")
        for field, domain in (
            ("member_refs", active_ids),
            ("relation_refs", relation_ids),
            ("operation_refs", active_ids),
            ("event_refs", active_ids),
            ("flow_refs", flow_ids),
            ("child_topic_refs", topic_ids),
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
            for field in ("actor_ref", "action_ref", "data_ref", "target_ref", "cause_ref", "condition_ref", "payload_ref"):
                require(step.get(field), source=step_id, field=field, allow_none=True)
            require(step.get("resume_ref"), source=step_id, field="resume_ref", allow_none=True, domains=local_steps)
            for field in ("result_refs", "error_refs"):
                for ref in step.get(field, []):
                    require(ref, source=step_id, field=field)
            for ref in step.get("next_step_refs", []):
                require(ref, source=step_id, field="next_step_refs", domains=local_steps)
            for ref in step.get("subflow_refs", []):
                require(ref, source=step_id, field="subflow_refs", domains=flow_ids)

    bootstrap_ids = bootstrap_identity_ids(snapshot)
    outsiders = explicit_outsiders(snapshot)
    covered: set[str] = set()
    for members in resolution["inherited_memberships"].values():
        covered.update(members)

    for identity_id, outsider in sorted(outsiders.items()):
        if outsider.get("outsider") and not str(outsider.get("outsider_reason") or "").strip():
            errors.append({"id": "CF_OUTSIDER_REASON_MISSING", "message": f"Outsider {identity_id} has no outsider_reason", "identity": identity_id})
        if outsider.get("outsider") and identity_id in covered:
            errors.append({"id": "CF_OUTSIDER_WITH_TOPIC_MEMBERSHIP", "message": f"Identity {identity_id} is marked Outsider but has Topic membership", "identity": identity_id})

    for identity_id in sorted(active_ids - bootstrap_ids):
        outsider = outsiders.get(identity_id) or {}
        if identity_id not in covered and not (outsider.get("outsider") is True and str(outsider.get("outsider_reason") or "").strip()):
            errors.append({"id": "CF_TOPIC_MEMBERSHIP_MISSING", "message": f"Active identity {identity_id} has no direct or inherited Topic membership and no explicit Outsider classification", "identity": identity_id})

    tree["outsiders"] = {
        identity_id: deepcopy(value)
        for identity_id, value in sorted(outsiders.items())
        if value.get("outsider") is True
    }
    return errors


def enrich_v14(tree: dict[str, Any], snapshot: Any) -> dict[str, Any]:
    if not is_v14(snapshot):
        raise ValueError("enrich_v14 requires Canonical Contract Format 1.4")

    errors = list(tree.get("errors", []))
    errors.extend(materialize_behavior_identities(tree, snapshot))
    errors.extend(materialize_topics(tree, snapshot))
    errors.extend(materialize_flows(tree, snapshot))

    resolution, topic_errors = _topic_resolution(tree)
    errors.extend(topic_errors)
    errors.extend(_reference_and_coverage_errors(tree, snapshot, resolution))
    tree["topics"] = resolution["topics"]

    tree["errors"] = errors
    tree["validation_errors"] = []
    tree["valid"] = bool(tree.get("valid")) and not errors
    tree.setdefault("source_result", {})["canonical_contract_format_1_4"] = {
        "enabled": True,
        "format_revision": "1.4.0-compatible",
        "topics_source": "contract.topics[] recursively",
        "topic_inheritance_source": "parent_topic_refs only",
        "topic_composition_source": "composed_topic_refs only",
        "outsider_source": "explicit structured semantics only",
        "behavior_source": "behavior.states/interfaces/operations/events/flows",
        "causality_source": "behavior.flows[].steps[] only",
        "topic_membership_semantic_authority": False,
        "topic_membership_implies_structure": False,
        "topic_membership_implies_causality": False,
        "composition_copies_semantics": False,
        "path_inference": False,
        "software_specific_heuristics": False,
        "inference": False,
    }
    return tree
