from __future__ import annotations

import json
from typing import Any

from structure_tree import add_entry, add_flow, validate_tree

ACTIVE_STATUSES = {"unlocked", "locked"}
NON_NODE_SOURCE_ROLES = {"reconciliation", "historical_or_migration", "derived_projection"}
BEHAVIOR_DIMS = ("states", "interfaces", "operations", "events")
FLOW_KINDS = {"read", "write", "create", "update", "delete", "emit", "trigger", "invoke", "send", "receive"}
FLOW_REQUIRED = ("id", "kind", "actor_ref", "action_ref", "target_ref", "cause_ref", "result_refs")


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


def _strict_flows(snapshot: Any) -> bool:
    raw = snapshot.files.get("canonical/json/00_Contract_Format.json")
    if raw is None:
        return False
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return False
    required = (((data.get("contract_shape") or {}).get("behavior") or {}).get("required") or [])
    return isinstance(required, list) and "flows" in required


def enrich(tree: dict[str, Any], snapshot: Any) -> dict[str, Any]:
    """Add explicit behavior identities and CW behavior.flows to a canonical tree."""
    contracts = _contracts(snapshot)
    strict = _strict_flows(snapshot)
    errors = list(tree.get("errors", []))
    ids = {str(entry.get("id")) for entry in tree.get("entries", []) if entry.get("id") is not None}
    operations_with_effects: set[str] = set()
    flow_actions: set[str] = set()

    for path, data in contracts:
        owner_id = str((data.get("identity") or {}).get("id") or "")
        if not owner_id or owner_id not in ids:
            continue
        behavior = data.get("behavior") if isinstance(data.get("behavior"), dict) else {}
        for dimension in BEHAVIOR_DIMS:
            records = behavior.get(dimension)
            if not isinstance(records, list):
                continue
            for index, record in enumerate(records):
                if not isinstance(record, dict) or not record.get("id"):
                    continue
                record_id = str(record["id"])
                if record_id in ids:
                    errors.append({"id": "CF_AMBIGUOUS_IDENTITY", "message": f"Duplicate active behavior identity: {record_id}", "contract": path, "field": f"behavior.{dimension}[{index}].id"})
                    continue
                ids.add(record_id)
                add_entry(
                    tree,
                    entry_id=record_id,
                    name=str(record.get("name") or record_id),
                    kind=f"behavior_{dimension.rstrip('s')}",
                    parent_id=owner_id,
                    entry_type=str(record.get("type") or dimension.rstrip("s")),
                    status=record.get("status"),
                    metadata={"source_role": "behavior", "behavior_dimension": dimension, "behavior_owner": owner_id, "hierarchy_evidence": "behavior ownership", "raw": record},
                    provenance={"path": path, "repository": snapshot.repo, "branch": snapshot.branch, "revision": snapshot.revision},
                )
                if dimension == "operations" and isinstance(record.get("side_effects"), list) and record.get("side_effects"):
                    operations_with_effects.add(record_id)

    for path, data in contracts:
        owner_id = str((data.get("identity") or {}).get("id") or "")
        if not owner_id or owner_id not in ids:
            continue
        behavior = data.get("behavior") if isinstance(data.get("behavior"), dict) else {}
        raw_flows = behavior.get("flows")
        if raw_flows is None:
            if strict:
                errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": "behavior.flows must be an array", "contract": path, "field": "behavior.flows"})
            continue
        if not isinstance(raw_flows, list):
            errors.append({"id": "CF_MISSING_REQUIRED_FIELD", "message": "behavior.flows must be an array", "contract": path, "field": "behavior.flows"})
            continue
        for index, flow in enumerate(raw_flows):
            if not isinstance(flow, dict):
                errors.append({"id": "CW_FLOW_SHAPE", "message": f"behavior.flows[{index}] must be an object", "contract": path})
                continue
            missing = [field for field in FLOW_REQUIRED if field not in flow]
            if missing:
                errors.append({"id": "CW_FLOW_MISSING_REQUIRED_FIELD", "message": f"Flow is missing required fields: {', '.join(missing)}", "contract": path, "field": f"behavior.flows[{index}]"})
                continue
            kind = str(flow.get("kind") or "")
            if kind not in FLOW_KINDS:
                errors.append({"id": "CW_FLOW_KIND", "message": f"Unsupported flow kind {kind!r}", "contract": path, "field": f"behavior.flows[{index}].kind"})
            result_refs = flow.get("result_refs")
            if not isinstance(result_refs, list):
                errors.append({"id": "CW_FLOW_RESULT_REFS_SHAPE", "message": f"Flow {flow.get('id')} result_refs must be an array", "contract": path})
                result_refs = []
            error_refs = flow.get("error_refs", [])
            if not isinstance(error_refs, list):
                errors.append({"id": "CW_FLOW_ERROR_REFS_SHAPE", "message": f"Flow {flow.get('id')} error_refs must be an array", "contract": path})
                error_refs = []
            action_ref = str(flow.get("action_ref") or "")
            flow_actions.add(action_ref)
            add_flow(
                tree,
                flow_id=str(flow.get("id") or ""),
                kind=kind,
                actor_ref=str(flow.get("actor_ref") or ""),
                action_ref=action_ref,
                data_ref=str(flow["data_ref"]) if flow.get("data_ref") is not None else None,
                target_ref=str(flow.get("target_ref") or ""),
                cause_ref=str(flow.get("cause_ref") or ""),
                result_refs=[str(ref) for ref in result_refs],
                condition_ref=str(flow["condition_ref"]) if flow.get("condition_ref") is not None else None,
                payload_ref=str(flow["payload_ref"]) if flow.get("payload_ref") is not None else None,
                error_refs=[str(ref) for ref in error_refs],
                owner_ref=owner_id,
                metadata={"evidence": "behavior.flows[]", "semantic_authority": True, "causal": True, "raw": flow},
                provenance={"path": path, "repository": snapshot.repo, "branch": snapshot.branch, "revision": snapshot.revision},
            )

    if strict:
        for operation_id in sorted(operations_with_effects - flow_actions):
            errors.append({"id": "CW_FLOW_HIDDEN_EFFECT", "message": f"Operation {operation_id} declares side_effects but no explicit behavior.flows record", "operation": operation_id})

    # Optional refs are CW references too; validate them here while StructureTree
    # validates the mandatory WHO/WHAT/WHERE/WHY refs and result_refs.
    for flow in tree.get("flows", []):
        flow_id = str(flow.get("id") or "")
        for field in ("condition_ref", "payload_ref"):
            ref = flow.get(field)
            if ref is not None and ref not in ids:
                errors.append({"id": "CW_FLOW_HIDDEN_REFERENCE", "message": f"Flow {flow_id} has unresolved {field}: {ref}", "flow": flow_id, "field": field})
        for ref in flow.get("error_refs", []):
            if ref not in ids:
                errors.append({"id": "CW_FLOW_HIDDEN_REFERENCE", "message": f"Flow {flow_id} has unresolved error_ref: {ref}", "flow": flow_id, "field": "error_refs"})

    tree["errors"] = errors
    tree["validation_errors"] = validate_tree(tree)
    tree["valid"] = bool(tree.get("valid")) and not errors and not tree["validation_errors"]
    tree.setdefault("source_result", {})["cw_flow_projection"] = {
        "enabled": True,
        "strict_contract_format": strict,
        "source": "behavior.flows[] only",
        "who": "actor_ref",
        "what": ["kind", "action_ref", "data_ref"],
        "where": "target_ref",
        "why": "cause_ref",
        "causality_from_dependencies": False,
        "causality_from_prose": False,
        "causality_from_layout": False,
        "inference": False,
    }
    return tree
