from __future__ import annotations

import json
from typing import Any

from structureprojector import ProjectorError, SourceSnapshot

FORMAT_MAGIC = "AIGMOS_CANONICAL_CONTRACT"
BOOTSTRAP_PATH = "canonical/json/00_Contract_Format.json"
MASTER_PATH = "canonical/json/01_Master.json"
CANONICAL_ROOT = "canonical/json/"
ACTIVE_STATUSES = {"unlocked", "locked"}
INACTIVE_STATUSES = {"superseded", "deprecated"}
NON_NODE_SOURCE_ROLES = {
    "reconciliation",
    "historical_or_migration",
    "derived_projection",
}
STRUCTURE_DIMS = ("containment", "relations", "ownership", "authority", "dependencies")
BEHAVIOR_DIMS = ("states", "interfaces", "operations", "events")


class CanonicalGraphError(ValueError):
    pass


def _json_file(snapshot: SourceSnapshot, path: str) -> dict[str, Any]:
    raw = snapshot.files.get(path)
    if raw is None:
        raise ProjectorError("SP_CANONICAL_BOOTSTRAP_MISSING", f"Required canonical bootstrap is missing: {path}", path=path)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectorError("SP_CANONICAL_BOOTSTRAP_INVALID", f"Required canonical bootstrap is invalid JSON: {path}", path=path) from exc
    if not isinstance(data, dict):
        raise ProjectorError("SP_CANONICAL_BOOTSTRAP_INVALID", f"Required canonical bootstrap must be a JSON object: {path}", path=path)
    return data


def load_contract_format(snapshot: SourceSnapshot) -> dict[str, Any]:
    data = _json_file(snapshot, BOOTSTRAP_PATH)
    shape = data.get("contract_shape")
    if not isinstance(shape, dict):
        raise ProjectorError("SP_CONTRACT_FORMAT_INVALID", "Contract Format bootstrap has no contract_shape object", path=BOOTSTRAP_PATH)
    fmt = shape.get("format")
    if not isinstance(fmt, dict):
        raise ProjectorError("SP_CONTRACT_FORMAT_INVALID", "Contract Format bootstrap has no contract_shape.format object", path=BOOTSTRAP_PATH)
    version = fmt.get("format_version")
    required = shape.get("required")
    status_values = (shape.get("status") or {}).get("values") if isinstance(shape.get("status"), dict) else None
    if not isinstance(version, str) or not version:
        raise ProjectorError("SP_CONTRACT_FORMAT_INVALID", "Contract Format bootstrap does not declare format_version", path=BOOTSTRAP_PATH)
    if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
        raise ProjectorError("SP_CONTRACT_FORMAT_INVALID", "Contract Format bootstrap does not declare required fields", path=BOOTSTRAP_PATH)
    return {
        "version": version,
        "required": required,
        "status_values": status_values if isinstance(status_values, list) else [],
        "raw": data,
    }


def load_master(snapshot: SourceSnapshot) -> dict[str, Any]:
    data = _json_file(snapshot, MASTER_PATH)
    if data.get("format", {}).get("contract_format") != FORMAT_MAGIC:
        raise ProjectorError("SP_MASTER_FORMAT_INVALID", "Canonical master is not an AIGMOS_CANONICAL_CONTRACT", path=MASTER_PATH)
    return data


def detect_contract(data: Any) -> bool:
    return isinstance(data, dict) and data.get("format", {}).get("contract_format") == FORMAT_MAGIC


def validate_contract(path: str, data: dict[str, Any], format_spec: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    def err(error_id: str, message: str, field: str | None = None) -> None:
        item: dict[str, Any] = {"id": error_id, "contract": path, "message": message}
        if field:
            item["field"] = field
        errors.append(item)

    for field in format_spec["required"]:
        if field not in data:
            err("CF_MISSING_REQUIRED_FIELD", f"Missing required top-level field: {field}", field)

    fmt = data.get("format") if isinstance(data.get("format"), dict) else {}
    if fmt.get("contract_format") != FORMAT_MAGIC:
        err("CF_UNSUPPORTED_FORMAT", "Unsupported contract format", "format.contract_format")
    if fmt.get("format_version") != format_spec["version"]:
        err("CF_UNSUPPORTED_FORMAT_VERSION", f"Expected format version {format_spec['version']}", "format.format_version")

    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    for field in ("id", "name", "type", "version"):
        if not identity.get(field):
            err("CF_MISSING_REQUIRED_FIELD", f"Missing identity.{field}", f"identity.{field}")

    allowed_statuses = format_spec.get("status_values") or []
    if allowed_statuses and data.get("status") not in allowed_statuses:
        err("CF_INVALID_STATUS", f"Unsupported lifecycle status: {data.get('status')!r}", "status")

    scope = data.get("scope") if isinstance(data.get("scope"), dict) else {}
    for field in ("owns", "does_not_own"):
        if not isinstance(scope.get(field), list):
            err("CF_MISSING_REQUIRED_FIELD", f"scope.{field} must be an array", f"scope.{field}")

    if not isinstance(data.get("members"), list):
        err("CF_MISSING_REQUIRED_FIELD", "members must be an array", "members")

    structure = data.get("structure") if isinstance(data.get("structure"), dict) else {}
    for field in STRUCTURE_DIMS:
        if not isinstance(structure.get(field), list):
            err("CF_MISSING_REQUIRED_FIELD", f"structure.{field} must be an array", f"structure.{field}")

    behavior = data.get("behavior") if isinstance(data.get("behavior"), dict) else {}
    for field in BEHAVIOR_DIMS:
        if not isinstance(behavior.get(field), list):
            err("CF_MISSING_REQUIRED_FIELD", f"behavior.{field} must be an array", f"behavior.{field}")

    if not isinstance(data.get("semantics"), dict):
        err("CF_MISSING_REQUIRED_FIELD", "semantics must be an object", "semantics")

    constraints = data.get("constraints") if isinstance(data.get("constraints"), dict) else {}
    for field in ("invariants", "hard_gates"):
        if not isinstance(constraints.get(field), list):
            err("CF_MISSING_REQUIRED_FIELD", f"constraints.{field} must be an array", f"constraints.{field}")

    if not isinstance(data.get("references"), list):
        err("CF_MISSING_REQUIRED_FIELD", "references must be an array", "references")
    if not isinstance(data.get("prose"), dict):
        err("CF_MISSING_REQUIRED_FIELD", "prose must be an object", "prose")
    return errors


def _load_contracts(snapshot: SourceSnapshot, format_spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    contracts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for path in sorted(snapshot.files):
        content = snapshot.files[path]
        inventory.append({"path": path, "size": len(content), "type": "file"})
        if path == BOOTSTRAP_PATH or not path.startswith(CANONICAL_ROOT) or not path.lower().endswith(".json"):
            continue
        try:
            data = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not detect_contract(data):
            continue
        lifecycle_active = data.get("status") in ACTIVE_STATUSES
        architecture_active = lifecycle_active and data.get("source_role") not in NON_NODE_SOURCE_ROLES
        if lifecycle_active:
            errors.extend(validate_contract(path, data, format_spec))
        contracts.append({
            "path": path,
            "data": data,
            "lifecycle_active": lifecycle_active,
            "architecture_active": architecture_active,
        })
    return contracts, errors, inventory


def _node_from_contract(path: str, data: dict[str, Any]) -> dict[str, Any]:
    identity = data["identity"]
    return {
        "id": identity["id"],
        "name": identity.get("name") or identity["id"],
        "type": identity.get("type"),
        "version": identity.get("version"),
        "status": data.get("status"),
        "source_role": data.get("source_role"),
        "source": path,
        "kind": "contract",
        "semantics": data.get("semantics", {}),
        "raw": data,
    }


def _node_from_member(path: str, member: dict[str, Any], *, registry: bool) -> dict[str, Any]:
    return {
        "id": member["id"],
        "name": member.get("name") or member["id"],
        "type": member.get("type"),
        "status": member.get("status"),
        "source_role": "membership_registry" if registry else "member",
        "source": path,
        "kind": "registry_member" if registry else "member",
        "semantics": member.get("semantics", {}),
        "raw": member,
    }


def build_graph(snapshot: SourceSnapshot) -> dict[str, Any]:
    format_spec = load_contract_format(snapshot)
    master = load_master(snapshot)
    contracts, errors, inventory = _load_contracts(snapshot, format_spec)
    architecture_contracts = [c for c in contracts if c["architecture_active"]]

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    refs_to_check: list[tuple[str, str, str]] = []
    registry_members: list[tuple[str, dict[str, Any]]] = []

    for item in architecture_contracts:
        path, data = item["path"], item["data"]
        role = data.get("source_role")
        root_id = (data.get("identity") or {}).get("id")
        if root_id:
            if root_id in nodes:
                errors.append({"id": "CF_AMBIGUOUS_IDENTITY", "message": f"Duplicate active identity: {root_id}", "contract": path})
            else:
                nodes[root_id] = _node_from_contract(path, data)

        for member in data.get("members", []):
            if not isinstance(member, dict) or not member.get("id"):
                continue
            if role == "membership_registry":
                registry_members.append((path, member))
                continue
            member_id = member["id"]
            if member_id in nodes:
                errors.append({"id": "CF_AMBIGUOUS_IDENTITY", "message": f"Duplicate active identity: {member_id}", "contract": path})
            else:
                nodes[member_id] = _node_from_member(path, member, registry=False)

    for path, member in registry_members:
        member_id = member["id"]
        if member_id not in nodes:
            nodes[member_id] = _node_from_member(path, member, registry=True)

    def add_edge(dimension: str, edge: dict[str, Any], source_key: str, target_key: str) -> None:
        source = edge.get(source_key)
        target = edge.get(target_key)
        if not source or not target:
            return
        normalized = {
            "id": edge.get("id"),
            "dimension": dimension,
            "source": source,
            "target": target,
            "type": edge.get("relation_type") or edge.get("ownership_type") or edge.get("authority_type") or edge.get("dependency_type") or dimension,
            "raw": edge,
        }
        edges.append(normalized)
        refs_to_check.append((str(source), str(normalized["id"] or dimension), "source"))
        refs_to_check.append((str(target), str(normalized["id"] or dimension), "target"))

    for item in architecture_contracts:
        data = item["data"]
        structure = data.get("structure", {})
        for edge in structure.get("containment", []):
            add_edge("containment", edge, "parent_ref", "child_ref")
        for edge in structure.get("relations", []):
            add_edge("relations", edge, "source_ref", "target_ref")
        for edge in structure.get("ownership", []):
            add_edge("ownership", edge, "owner_ref", "target_ref")
        for edge in structure.get("authority", []):
            add_edge("authority", edge, "authority_ref", "target_ref")
        for edge in structure.get("dependencies", []):
            add_edge("dependencies", edge, "source_ref", "target_ref")
        for ref in data.get("references", []):
            if isinstance(ref, dict) and ref.get("target_ref"):
                refs_to_check.append((str(ref["target_ref"]), str(ref.get("id") or "reference"), "target_ref"))

    unresolved_refs: list[dict[str, Any]] = []
    for target_ref, owner, role in refs_to_check:
        if target_ref not in nodes:
            error = {
                "id": "CF_UNRESOLVED_REFERENCE",
                "message": f"Unresolved active reference {target_ref} in {owner} ({role})",
            }
            errors.append(error)
            unresolved_refs.append(error)

    validation_valid = not errors
    lifecycle_active_count = sum(1 for c in contracts if c["lifecycle_active"])
    excluded_non_node_count = sum(1 for c in contracts if c["lifecycle_active"] and not c["architecture_active"])

    # Projection availability is intentionally separate from package validation.
    # Every node and edge below originates from explicit active canonical data.
    # Validation errors remain visible and MUST NOT be silently reinterpreted,
    # but they also MUST NOT erase already-proven structure from a read-only
    # projector. Edges with unresolved endpoints remain in the diagnostic graph;
    # renderers naturally draw only edges whose endpoints are present.
    projectable = bool(nodes)

    return {
        "valid": validation_valid,
        "projectable": projectable,
        "projection_status": "valid" if validation_valid else "degraded",
        "source": {
            "repository": snapshot.repo,
            "branch": snapshot.branch,
            "revision": snapshot.revision,
            "files": len(snapshot.files),
            "canonical_root": CANONICAL_ROOT,
            "contract_format": format_spec["version"],
            "contracts": len(contracts),
            "lifecycle_active_contracts": lifecycle_active_count,
            "architecture_contracts": len(architecture_contracts),
            "excluded_non_node_contracts": excluded_non_node_count,
            "inactive_contracts": len(contracts) - lifecycle_active_count,
        },
        "format": {
            "path": BOOTSTRAP_PATH,
            "version": format_spec["version"],
            "required_top": format_spec["required"],
        },
        "master": {
            "path": MASTER_PATH,
            "identity": master.get("identity", {}).get("id"),
            "status": master.get("status"),
        },
        "inventory": inventory,
        "graph": {
            "nodes": list(nodes.values()),
            "edges": edges,
        },
        "diagnostics": {
            "validation_error_count": len(errors),
            "unresolved_reference_count": len(unresolved_refs),
        },
        "errors": errors,
    }
