from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

ACTIVE_STATUSES = {"unlocked", "locked"}
NON_NODE_SOURCE_ROLES = {"reconciliation", "historical_or_migration", "derived_projection"}
BEHAVIOR_DIMS = ("states", "interfaces", "operations", "events")
FLOW_REQUIRED = ("id", "owner_ref", "name", "flow_type", "entry_refs", "exit_refs", "steps", "metadata")
FLOW_STEP_REQUIRED = (
    "id", "actor_ref", "action_ref", "data_ref", "target_ref", "cause_ref",
    "condition_ref", "payload_ref", "result_refs", "error_refs", "next_step_refs",
    "subflow_refs", "resume_ref",
)
TOPIC_REQUIRED = (
    "id", "name", "purpose", "parent_topic_refs", "composed_topic_refs",
    "member_refs", "relation_refs", "operation_refs", "event_refs", "flow_refs",
    "child_topics", "metadata",
)


def _contracts(snapshot: Any) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(snapshot.files):
        if not path.startswith("canonical/json/") or not path.endswith(".json") or path.endswith("00_Contract_Format.json"):
            continue
        try:
            data = json.loads(snapshot.files[path].decode("utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("format", {}).get("contract_format") != "AIGMOS_CANONICAL_CONTRACT":
            continue
        if data.get("status") not in ACTIVE_STATUSES or data.get("source_role") in NON_NODE_SOURCE_ROLES:
            continue
        out.append((path, data))
    return out


def format_contract(snapshot: Any) -> dict[str, Any] | None:
    raw = snapshot.files.get("canonical/json/00_Contract_Format.json")
    if raw is None:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def is_v14(snapshot: Any) -> bool:
    fmt = format_contract(snapshot) or {}
    version = str(((fmt.get("contract_shape") or {}).get("format") or {}).get("format_version") or "")
    return version == "1.4" or str(fmt.get("version") or "").startswith("1.4")


def materialize_behavior_identities(tree: dict[str, Any], snapshot: Any) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    ids = {str(entry.get("id")) for entry in tree.get("entries", []) if entry.get("id") is not None}
    for path, data in _contracts(snapshot):
        owner_id = str((data.get("identity") or {}).get("id") or "")
        if not owner_id or owner_id not in ids:
            continue
        behavior = data.get("behavior") if isinstance(data.get("behavior"), dict) else {}
        for dimension in BEHAVIOR_DIMS:
            records = behavior.get(dimension)
            if not isinstance(records, list):
                if is_v14(snapshot):
                    errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": f"behavior.{dimension} must be an array", "contract": path, "field": f"behavior.{dimension}"})
                continue
            for index, record in enumerate(records):
                if not isinstance(record, dict) or not record.get("id"):
                    errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": f"behavior.{dimension}[{index}] requires id", "contract": path})
                    continue
                record_id = str(record["id"])
                if record_id in ids:
                    errors.append({"id": "CF_AMBIGUOUS_IDENTITY", "message": f"Duplicate active behavior identity: {record_id}", "contract": path})
                    continue
                ids.add(record_id)
                tree["entries"].append({
                    "id": record_id,
                    "name": str(record.get("name") or record_id),
                    "kind": f"behavior_{dimension.rstrip('s')}",
                    "type": str(record.get("type") or dimension.rstrip("s")),
                    "parent_id": owner_id,
                    "status": record.get("status"),
                    "metadata": {
                        "source_role": "behavior",
                        "behavior_dimension": dimension,
                        "behavior_owner": owner_id,
                        "hierarchy_evidence": "behavior ownership",
                        "raw": deepcopy(record),
                    },
                    "provenance": {
                        "path": path,
                        "repository": snapshot.repo,
                        "branch": snapshot.branch,
                        "revision": snapshot.revision,
                    },
                })
    return errors


def _string_refs(raw: Any) -> list[str]:
    return [str(value) for value in raw] if isinstance(raw, list) and all(isinstance(value, str) for value in raw) else []


def _flatten_topic(
    *,
    raw: dict[str, Any],
    owner_ref: str,
    container_topic_ref: str | None,
    path: str,
    snapshot: Any,
    out: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> None:
    missing = [field for field in TOPIC_REQUIRED if field not in raw]
    topic_id = str(raw.get("id") or "")
    if missing:
        errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": f"Topic {topic_id or '<unknown>'} missing: {', '.join(missing)}", "contract": path})

    for field in (
        "parent_topic_refs", "composed_topic_refs", "member_refs", "relation_refs",
        "operation_refs", "event_refs", "flow_refs", "child_topics",
    ):
        if field in raw and not isinstance(raw.get(field), list):
            errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": f"Topic {topic_id or '<unknown>'} {field} must be an array", "contract": path, "field": field})

    child_topics = raw.get("child_topics") if isinstance(raw.get("child_topics"), list) else []
    child_ids = [str(child.get("id")) for child in child_topics if isinstance(child, dict) and child.get("id")]
    out.append({
        "id": topic_id,
        "name": str(raw.get("name") or topic_id),
        "purpose": str(raw.get("purpose") or ""),
        "owner_ref": owner_ref,
        "container_topic_ref": container_topic_ref,
        "parent_topic_refs": _string_refs(raw.get("parent_topic_refs")),
        "composed_topic_refs": _string_refs(raw.get("composed_topic_refs")),
        "member_refs": _string_refs(raw.get("member_refs")),
        "relation_refs": _string_refs(raw.get("relation_refs")),
        "operation_refs": _string_refs(raw.get("operation_refs")),
        "event_refs": _string_refs(raw.get("event_refs")),
        "flow_refs": _string_refs(raw.get("flow_refs")),
        "child_topic_refs": child_ids,
        "metadata": deepcopy(raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}),
        "provenance": {"path": path, "repository": snapshot.repo, "branch": snapshot.branch, "revision": snapshot.revision},
    })
    for child in child_topics:
        if isinstance(child, dict):
            _flatten_topic(
                raw=child,
                owner_ref=owner_ref,
                container_topic_ref=topic_id or None,
                path=path,
                snapshot=snapshot,
                out=out,
                errors=errors,
            )
        else:
            errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": f"Topic {topic_id or '<unknown>'} child_topics contains a non-object item", "contract": path})


def materialize_topics(tree: dict[str, Any], snapshot: Any) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []
    for path, data in _contracts(snapshot):
        owner_ref = str((data.get("identity") or {}).get("id") or "")
        raw_topics = data.get("topics")
        if raw_topics is None:
            if is_v14(snapshot):
                errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": "topics must be an array", "contract": path, "field": "topics"})
            continue
        if not isinstance(raw_topics, list):
            errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": "topics must be an array", "contract": path, "field": "topics"})
            continue
        for topic in raw_topics:
            if isinstance(topic, dict):
                _flatten_topic(raw=topic, owner_ref=owner_ref, container_topic_ref=None, path=path, snapshot=snapshot, out=topics, errors=errors)
            else:
                errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": "Topic must be an object", "contract": path})
    tree["topics"] = topics
    return errors


def materialize_flows(tree: dict[str, Any], snapshot: Any) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    flows: list[dict[str, Any]] = []
    for path, data in _contracts(snapshot):
        owner_id = str((data.get("identity") or {}).get("id") or "")
        behavior = data.get("behavior") if isinstance(data.get("behavior"), dict) else {}
        raw_flows = behavior.get("flows")
        if raw_flows is None:
            if is_v14(snapshot):
                errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": "behavior.flows must be an array", "contract": path, "field": "behavior.flows"})
            continue
        if not isinstance(raw_flows, list):
            errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": "behavior.flows must be an array", "contract": path, "field": "behavior.flows"})
            continue
        for raw in raw_flows:
            if not isinstance(raw, dict):
                errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": "Flow must be an object", "contract": path})
                continue
            missing = [field for field in FLOW_REQUIRED if field not in raw]
            flow_id = str(raw.get("id") or "")
            if missing:
                errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": f"Flow {flow_id or '<unknown>'} missing: {', '.join(missing)}", "contract": path})
            steps: list[dict[str, Any]] = []
            raw_steps = raw.get("steps") if isinstance(raw.get("steps"), list) else []
            for raw_step in raw_steps:
                if not isinstance(raw_step, dict):
                    errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": f"Flow {flow_id} contains a non-object step", "contract": path})
                    continue
                step_missing = [field for field in FLOW_STEP_REQUIRED if field not in raw_step]
                if step_missing:
                    errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": f"Flow step {raw_step.get('id') or '<unknown>'} missing: {', '.join(step_missing)}", "contract": path, "flow": flow_id})
                step = {field: deepcopy(raw_step.get(field)) for field in FLOW_STEP_REQUIRED}
                for field in ("result_refs", "error_refs", "next_step_refs", "subflow_refs"):
                    if not isinstance(step.get(field), list):
                        errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": f"Flow step {raw_step.get('id') or '<unknown>'} {field} must be an array", "contract": path, "flow": flow_id})
                        step[field] = []
                    else:
                        step[field] = [str(value) for value in step[field] if isinstance(value, str)]
                for field in ("id", "actor_ref", "action_ref", "data_ref", "target_ref", "cause_ref", "condition_ref", "payload_ref", "resume_ref"):
                    if step.get(field) is not None:
                        step[field] = str(step[field])
                steps.append(step)
            flows.append({
                "id": flow_id,
                "owner_ref": str(raw.get("owner_ref") or owner_id),
                "name": str(raw.get("name") or flow_id),
                "flow_type": str(raw.get("flow_type") or ""),
                "entry_refs": _string_refs(raw.get("entry_refs")),
                "exit_refs": _string_refs(raw.get("exit_refs")),
                "steps": steps,
                "metadata": deepcopy(raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}),
                "provenance": {"path": path, "repository": snapshot.repo, "branch": snapshot.branch, "revision": snapshot.revision},
            })
    tree["flows"] = flows
    return errors


def explicit_outsiders(snapshot: Any) -> dict[str, dict[str, Any]]:
    """Read Outsider only from the identity's own structured semantics."""
    result: dict[str, dict[str, Any]] = {}
    for path, data in _contracts(snapshot):
        root_id = str((data.get("identity") or {}).get("id") or "")
        root_semantics = data.get("semantics") if isinstance(data.get("semantics"), dict) else {}
        if root_id and ("outsider" in root_semantics or "outsider_reason" in root_semantics):
            result[root_id] = {
                "outsider": root_semantics.get("outsider") is True,
                "outsider_reason": root_semantics.get("outsider_reason"),
                "provenance": {"path": path, "field": "semantics"},
            }
        if data.get("source_role") == "membership_registry":
            continue
        for member in data.get("members", []):
            if not isinstance(member, dict) or not member.get("id"):
                continue
            semantics = member.get("semantics") if isinstance(member.get("semantics"), dict) else {}
            if "outsider" in semantics or "outsider_reason" in semantics:
                result[str(member["id"])] = {
                    "outsider": semantics.get("outsider") is True,
                    "outsider_reason": semantics.get("outsider_reason"),
                    "provenance": {"path": path, "field": f"members[{member['id']}].semantics"},
                }
    return result


def bootstrap_identity_ids(snapshot: Any) -> set[str]:
    fmt = format_contract(snapshot) or {}
    order = ((fmt.get("bootstrap") or {}).get("order") or [])
    paths = {str(value) for value in order if isinstance(value, str) and value.endswith(".json")}
    ids: set[str] = set()
    for relative in paths:
        candidates = [relative, f"canonical/json/{relative}"]
        raw = next((snapshot.files.get(path) for path in candidates if snapshot.files.get(path) is not None), None)
        if raw is None:
            continue
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            identity_id = (data.get("identity") or {}).get("id")
            if identity_id:
                ids.add(str(identity_id))
    return ids
