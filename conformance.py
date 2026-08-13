from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

REPORT_FORMAT = "STRUCTUREPROJECTOR_CONFORMANCE_REPORT"
REPORT_VERSION = "1.0"
PROFILE_FORMAT = "STRUCTUREPROJECTOR_CONFORMANCE_MAPPING_PROFILE"
PROFILE_VERSION = "1.0"

STATUSES = {
    "MATCHED",
    "MISSING_IMPLEMENTATION",
    "UNSPECIFIED_IMPLEMENTATION",
    "MISMATCH",
    "UNRESOLVED",
}


def _entries(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("id")): entry
        for entry in tree.get("entries", [])
        if isinstance(entry.get("id"), str) and entry.get("id")
    }


def _links(tree: dict[str, Any]) -> list[dict[str, Any]]:
    return [link for link in tree.get("links", []) if isinstance(link, dict)]


def _link_key(link: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(link.get("source_id") or ""),
        str(link.get("target_id") or ""),
        str(link.get("dimension") or ""),
        str(link.get("type") or ""),
    )


def validate_mapping_profile(profile: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if profile.get("format") != PROFILE_FORMAT:
        errors.append({"id": "SP_CONFORMANCE_PROFILE_FORMAT", "message": f"Expected {PROFILE_FORMAT}"})
    if str(profile.get("version")) != PROFILE_VERSION:
        errors.append({"id": "SP_CONFORMANCE_PROFILE_VERSION", "message": f"Expected version {PROFILE_VERSION}"})

    for field in ("node_mappings", "relation_rules"):
        if not isinstance(profile.get(field), list):
            errors.append({"id": "SP_CONFORMANCE_PROFILE_FIELD", "message": f"{field} must be an array"})

    mapping_ids: set[str] = set()
    expected_ids: set[str] = set()
    observed_ids: set[str] = set()
    for mapping in profile.get("node_mappings", []):
        if not isinstance(mapping, dict):
            errors.append({"id": "SP_CONFORMANCE_NODE_MAPPING", "message": "node_mappings entries must be objects"})
            continue
        mapping_id = mapping.get("id")
        expected_id = mapping.get("expected_id")
        observed_id = mapping.get("observed_id")
        evidence = mapping.get("evidence")
        if not all(isinstance(value, str) and value for value in (mapping_id, expected_id, observed_id)):
            errors.append({"id": "SP_CONFORMANCE_NODE_MAPPING_FIELDS", "message": "node mapping requires id, expected_id and observed_id"})
            continue
        if mapping_id in mapping_ids:
            errors.append({"id": "SP_CONFORMANCE_DUPLICATE_MAPPING_ID", "message": f"Duplicate node mapping id: {mapping_id}"})
        mapping_ids.add(mapping_id)
        if expected_id in expected_ids:
            errors.append({"id": "SP_CONFORMANCE_DUPLICATE_EXPECTED_MAPPING", "message": f"Expected entry mapped more than once: {expected_id}"})
        expected_ids.add(expected_id)
        if observed_id in observed_ids:
            errors.append({"id": "SP_CONFORMANCE_DUPLICATE_OBSERVED_MAPPING", "message": f"Observed entry mapped more than once: {observed_id}"})
        observed_ids.add(observed_id)
        if not isinstance(evidence, dict) or not evidence.get("kind") or not evidence.get("source"):
            errors.append({"id": "SP_CONFORMANCE_MAPPING_EVIDENCE", "message": f"Mapping {mapping_id} requires evidence.kind and evidence.source"})

    for rule in profile.get("relation_rules", []):
        if not isinstance(rule, dict):
            errors.append({"id": "SP_CONFORMANCE_RELATION_RULE", "message": "relation_rules entries must be objects"})
            continue
        if not all(rule.get(field) for field in ("id", "expected_dimension", "observed_dimensions", "evidence")):
            errors.append({"id": "SP_CONFORMANCE_RELATION_RULE_FIELDS", "message": "relation rule requires id, expected_dimension, observed_dimensions and evidence"})
            continue
        if not isinstance(rule.get("observed_dimensions"), list) or not rule["observed_dimensions"]:
            errors.append({"id": "SP_CONFORMANCE_RELATION_RULE_DIMENSIONS", "message": f"Rule {rule.get('id')} observed_dimensions must be non-empty"})
        direction = rule.get("direction", "same")
        if direction not in {"same", "either"}:
            errors.append({"id": "SP_CONFORMANCE_RELATION_RULE_DIRECTION", "message": f"Rule {rule.get('id')} direction must be same or either"})
        evidence = rule.get("evidence")
        if not isinstance(evidence, dict) or not evidence.get("kind") or not evidence.get("source"):
            errors.append({"id": "SP_CONFORMANCE_RULE_EVIDENCE", "message": f"Rule {rule.get('id')} requires evidence.kind and evidence.source"})

    direct = profile.get("explicit_relation_mappings", [])
    if direct is not None and not isinstance(direct, list):
        errors.append({"id": "SP_CONFORMANCE_EXPLICIT_RELATION_MAPPINGS", "message": "explicit_relation_mappings must be an array when present"})
    return errors


def _rule_for_expected_link(link: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    dimension = str(link.get("dimension") or "")
    link_type = str(link.get("type") or "")
    matches = []
    for rule in rules:
        if str(rule.get("expected_dimension") or "") != dimension:
            continue
        expected_types = rule.get("expected_types")
        if isinstance(expected_types, list) and expected_types and link_type not in {str(v) for v in expected_types}:
            continue
        matches.append(rule)
    if not matches:
        return None
    return sorted(matches, key=lambda rule: str(rule.get("id") or ""))[0]


def _observed_link_matches(
    expected_link: dict[str, Any],
    observed_link: dict[str, Any],
    expected_to_observed: dict[str, str],
    rule: dict[str, Any],
) -> bool:
    expected_source = str(expected_link.get("source_id") or "")
    expected_target = str(expected_link.get("target_id") or "")
    observed_source = expected_to_observed.get(expected_source)
    observed_target = expected_to_observed.get(expected_target)
    if not observed_source or not observed_target:
        return False

    allowed_dimensions = {str(value) for value in rule.get("observed_dimensions", [])}
    if str(observed_link.get("dimension") or "") not in allowed_dimensions:
        return False
    allowed_types = rule.get("observed_types")
    if isinstance(allowed_types, list) and allowed_types:
        if str(observed_link.get("type") or "") not in {str(value) for value in allowed_types}:
            return False

    source = str(observed_link.get("source_id") or "")
    target = str(observed_link.get("target_id") or "")
    if source == observed_source and target == observed_target:
        return True
    return rule.get("direction", "same") == "either" and source == observed_target and target == observed_source


def compare(
    expected_tree: dict[str, Any],
    observed_tree: dict[str, Any],
    mapping_profile: dict[str, Any],
) -> dict[str, Any]:
    """Compare expected Canonical and observed implementation trees.

    The function is deliberately non-inferential: the only bridge between
    expected and observed identities is the explicit mapping profile.
    """
    profile_errors = validate_mapping_profile(mapping_profile)
    expected_entries = _entries(expected_tree)
    observed_entries = _entries(observed_tree)
    expected_links = _links(expected_tree)
    observed_links = _links(observed_tree)

    node_results: list[dict[str, Any]] = []
    relation_results: list[dict[str, Any]] = []
    errors = list(profile_errors)
    warnings: list[dict[str, Any]] = []

    expected_to_observed: dict[str, str] = {}
    observed_to_expected: dict[str, str] = {}
    mapping_by_expected: dict[str, dict[str, Any]] = {}

    if not profile_errors:
        for mapping in mapping_profile.get("node_mappings", []):
            expected_id = str(mapping["expected_id"])
            observed_id = str(mapping["observed_id"])
            expected_to_observed[expected_id] = observed_id
            observed_to_expected[observed_id] = expected_id
            mapping_by_expected[expected_id] = mapping

    for expected_id, expected_entry in sorted(expected_entries.items()):
        mapping = mapping_by_expected.get(expected_id)
        if mapping is None:
            status = "UNRESOLVED"
            observed_id = None
            reason = "No explicit node mapping exists."
        else:
            observed_id = str(mapping["observed_id"])
            if observed_id in observed_entries:
                status = "MATCHED"
                reason = "Explicit node mapping resolves to an observed entry."
            else:
                status = "MISSING_IMPLEMENTATION"
                reason = "Explicit node mapping requires an observed entry that is absent."
        node_results.append({
            "expected_id": expected_id,
            "observed_id": observed_id,
            "status": status,
            "reason": reason,
            "expected_provenance": deepcopy(expected_entry.get("provenance", {})),
            "observed_provenance": deepcopy(observed_entries.get(observed_id, {}).get("provenance", {})) if observed_id else {},
            "mapping_evidence": deepcopy(mapping.get("evidence", {})) if mapping else {},
        })

    unmapped_observed_nodes = []
    for observed_id, observed_entry in sorted(observed_entries.items()):
        if observed_id in observed_to_expected:
            continue
        unmapped_observed_nodes.append({
            "observed_id": observed_id,
            "status": "UNSPECIFIED_IMPLEMENTATION",
            "reason": "Observed entry has no explicit mapping to Canonical.",
            "observed_provenance": deepcopy(observed_entry.get("provenance", {})),
        })

    expected_link_by_id = {
        str(link.get("id")): link for link in expected_links if link.get("id") is not None
    }
    observed_link_by_id = {
        str(link.get("id")): link for link in observed_links if link.get("id") is not None
    }
    direct_by_expected = {
        str(item.get("expected_link_id")): item
        for item in mapping_profile.get("explicit_relation_mappings", []) or []
        if isinstance(item, dict) and item.get("expected_link_id")
    }
    consumed_observed_links: set[str] = set()

    for index, expected_link in enumerate(expected_links):
        expected_link_id = str(expected_link.get("id") or f"expected-link-{index}")
        source_id = str(expected_link.get("source_id") or "")
        target_id = str(expected_link.get("target_id") or "")
        direct = direct_by_expected.get(expected_link_id)

        if direct is not None:
            observed_link_id = str(direct.get("observed_link_id") or "")
            observed_link = observed_link_by_id.get(observed_link_id)
            if observed_link is None:
                status = "MISSING_IMPLEMENTATION"
                reason = "Explicit relation mapping requires an observed relation that is absent."
            else:
                mapped_source = expected_to_observed.get(source_id)
                mapped_target = expected_to_observed.get(target_id)
                same_endpoints = mapped_source == str(observed_link.get("source_id") or "") and mapped_target == str(observed_link.get("target_id") or "")
                status = "MATCHED" if same_endpoints else "MISMATCH"
                reason = "Explicit relation mapping endpoint check matched." if same_endpoints else "Explicit relation mapping points to contradictory observed endpoints."
                consumed_observed_links.add(observed_link_id)
            relation_results.append({
                "expected_link_id": expected_link_id,
                "observed_link_id": observed_link_id or None,
                "status": status,
                "reason": reason,
                "mapping_evidence": deepcopy(direct.get("evidence", {})),
            })
            continue

        if source_id not in expected_to_observed or target_id not in expected_to_observed:
            relation_results.append({
                "expected_link_id": expected_link_id,
                "observed_link_id": None,
                "status": "UNRESOLVED",
                "reason": "Expected relation endpoints are not both explicitly mapped.",
                "mapping_evidence": {},
            })
            continue

        rule = _rule_for_expected_link(expected_link, mapping_profile.get("relation_rules", []))
        if rule is None:
            relation_results.append({
                "expected_link_id": expected_link_id,
                "observed_link_id": None,
                "status": "UNRESOLVED",
                "reason": "No explicit relation rule applies to this Canonical relation.",
                "mapping_evidence": {},
            })
            continue

        matches = [link for link in observed_links if _observed_link_matches(expected_link, link, expected_to_observed, rule)]
        if matches:
            observed_link = sorted(matches, key=lambda link: str(link.get("id") or _link_key(link)))[0]
            observed_link_id = str(observed_link.get("id") or "")
            if observed_link_id:
                consumed_observed_links.add(observed_link_id)
            relation_results.append({
                "expected_link_id": expected_link_id,
                "observed_link_id": observed_link_id or None,
                "status": "MATCHED",
                "reason": "Observed relation satisfies explicit relation rule.",
                "mapping_evidence": deepcopy(rule.get("evidence", {})),
            })
        else:
            relation_results.append({
                "expected_link_id": expected_link_id,
                "observed_link_id": None,
                "status": "MISSING_IMPLEMENTATION",
                "reason": "Explicit relation rule requires a mapped observed relation that is absent.",
                "mapping_evidence": deepcopy(rule.get("evidence", {})),
            })

    unmapped_observed_relations = []
    for index, observed_link in enumerate(observed_links):
        observed_link_id = str(observed_link.get("id") or f"observed-link-{index}")
        if observed_link_id in consumed_observed_links:
            continue
        unmapped_observed_relations.append({
            "observed_link_id": observed_link_id,
            "status": "UNSPECIFIED_IMPLEMENTATION",
            "reason": "Observed relation is not consumed by an explicit Canonical relation mapping/rule.",
            "observed_provenance": deepcopy(observed_link.get("provenance", {})),
        })

    counts = Counter(item["status"] for item in node_results)
    counts.update(item["status"] for item in relation_results)
    counts.update(item["status"] for item in unmapped_observed_nodes)
    counts.update(item["status"] for item in unmapped_observed_relations)

    summary = {
        "matched": counts["MATCHED"],
        "missing_implementation": counts["MISSING_IMPLEMENTATION"],
        "unspecified_implementation": counts["UNSPECIFIED_IMPLEMENTATION"],
        "mismatch": counts["MISMATCH"],
        "unresolved": counts["UNRESOLVED"],
    }

    return {
        "format": REPORT_FORMAT,
        "version": REPORT_VERSION,
        "valid": not errors,
        "expected": {
            "format": expected_tree.get("format"),
            "version": expected_tree.get("version"),
            "input_module": expected_tree.get("input_module"),
            "source": deepcopy(expected_tree.get("source", {})),
        },
        "observed": {
            "format": observed_tree.get("format"),
            "version": observed_tree.get("version"),
            "input_module": observed_tree.get("input_module"),
            "source": deepcopy(observed_tree.get("source", {})),
        },
        "mapping_profile": {
            "format": mapping_profile.get("format"),
            "version": mapping_profile.get("version"),
        },
        "summary": summary,
        "nodes": node_results,
        "relations": relation_results,
        "unmapped_observed_nodes": unmapped_observed_nodes,
        "unmapped_observed_relations": unmapped_observed_relations,
        "errors": errors,
        "warnings": warnings,
    }
