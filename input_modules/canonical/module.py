from __future__ import annotations

from typing import Any

from canonical_graph import build_graph
from structure_tree import add_entry, add_link, new_tree, validate_tree


def read(snapshot: Any, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read Canonical source into neutral StructureTree.

    This module preserves only explicit structure already proven by canonical
    source. It performs no layout, primitive selection, styling or semantic
    inference. `references[]` entries are projected as semantic links because
    the source contract explicitly declares both the owning contract identity
    and target_ref. Membership registries are allowed to provide presentation
    parentage only where membership is explicit and unambiguous. Free-form
    semantics/prose and repository paths are never scanned for relations.
    """
    result = build_graph(snapshot)
    tree = new_tree(input_module="canonical", source=result.get("source", {}))

    graph = result.get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_ids = {str(node.get("id")) for node in nodes if node.get("id") is not None}

    containment_parent: dict[str, str] = {}
    membership_candidates: dict[str, set[str]] = {}
    hierarchy_warnings: list[dict[str, Any]] = []

    # Explicit structure.containment[] is the strongest parent evidence.
    for edge in edges:
        if edge.get("dimension") != "containment" or not edge.get("source") or not edge.get("target"):
            continue
        child_id = str(edge["target"])
        parent_id = str(edge["source"])
        previous = containment_parent.get(child_id)
        if previous is None:
            containment_parent[child_id] = parent_id
        elif previous != parent_id:
            hierarchy_warnings.append({
                "id": "SP_CANONICAL_PARENT_AMBIGUOUS",
                "message": f"Conflicting explicit containment parents for {child_id}: {previous}, {parent_id}",
                "entry": child_id,
                "parents": sorted({previous, parent_id}),
                "evidence": "structure.containment[]",
            })
            containment_parent.pop(child_id, None)

    # Explicit members[] ownership recorded by canonical_graph.
    for node in nodes:
        node_id = str(node.get("id") or "")
        member_of = node.get("member_of")
        if node_id and member_of and str(member_of) in node_ids:
            membership_candidates.setdefault(node_id, set()).add(str(member_of))

    # Membership registries in current canonical commonly declare membership via
    # references[]. The registry identity is a presentation parent for those
    # explicitly referenced members; the semantic relation remains a separate
    # membership link and is not re-labelled as canonical containment.
    for node in nodes:
        registry_id = str(node.get("id") or "")
        if not registry_id or node.get("source_role") != "membership_registry":
            continue
        raw = node.get("raw")
        if not isinstance(raw, dict):
            continue
        references = raw.get("references")
        if not isinstance(references, list):
            continue
        for reference in references:
            if not isinstance(reference, dict) or not reference.get("target_ref"):
                continue
            target_id = str(reference["target_ref"])
            if target_id in node_ids:
                membership_candidates.setdefault(target_id, set()).add(registry_id)

    parent_by_child: dict[str, str] = dict(containment_parent)
    for child_id, candidates in membership_candidates.items():
        if child_id in parent_by_child:
            continue
        if len(candidates) == 1:
            parent_by_child[child_id] = next(iter(candidates))
        elif len(candidates) > 1:
            hierarchy_warnings.append({
                "id": "SP_CANONICAL_PARENT_AMBIGUOUS",
                "message": f"Conflicting explicit membership parents for {child_id}: {', '.join(sorted(candidates))}",
                "entry": child_id,
                "parents": sorted(candidates),
                "evidence": "canonical membership",
            })

    for node in nodes:
        node_id = str(node.get("id"))
        if not node_id:
            continue
        add_entry(
            tree,
            entry_id=node_id,
            name=str(node.get("name") or node_id),
            kind=str(node.get("kind") or "canonical"),
            parent_id=parent_by_child.get(node_id),
            entry_type=node.get("type"),
            status=node.get("status"),
            metadata={
                "source_role": node.get("source_role"),
                "semantics": node.get("semantics", {}),
                "hierarchy_evidence": (
                    "structure.containment[]" if node_id in containment_parent
                    else "canonical membership" if node_id in parent_by_child
                    else None
                ),
            },
            provenance={
                "path": node.get("source"),
                "repository": snapshot.repo,
                "branch": snapshot.branch,
                "revision": snapshot.revision,
            },
        )

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        add_link(
            tree,
            link_id=edge.get("id"),
            source_id=str(source),
            target_id=str(target),
            dimension=str(edge.get("dimension") or "relation"),
            link_type=edge.get("type"),
            metadata={"raw": edge.get("raw"), "evidence": "structure"},
            provenance={
                "repository": snapshot.repo,
                "branch": snapshot.branch,
                "revision": snapshot.revision,
            },
        )

    # Explicit semantic references are first-class projection evidence. The
    # source is the contract identity that owns references[]; target_ref is
    # written explicitly in canonical. Registry references are marked as
    # membership so viewers may distinguish family hierarchy from arbitrary
    # semantic references without changing canonical meaning.
    for node in nodes:
        source_id = str(node.get("id") or "")
        raw = node.get("raw")
        if not source_id or not isinstance(raw, dict):
            continue
        references = raw.get("references")
        if not isinstance(references, list):
            continue
        is_registry = node.get("source_role") == "membership_registry"
        for index, reference in enumerate(references):
            if not isinstance(reference, dict) or not reference.get("target_ref"):
                continue
            target_id = str(reference["target_ref"])
            reference_id = str(reference.get("id") or f"reference:{source_id}:{index}")
            add_link(
                tree,
                link_id=reference_id,
                source_id=source_id,
                target_id=target_id,
                dimension="membership" if is_registry else "semantic",
                link_type=str(reference.get("purpose") or ("membership" if is_registry else "reference")),
                metadata={
                    "raw": reference,
                    "evidence": "membership_registry.references[]" if is_registry else "references[]",
                },
                provenance={
                    "path": node.get("source"),
                    "repository": snapshot.repo,
                    "branch": snapshot.branch,
                    "revision": snapshot.revision,
                },
            )

    tree["errors"] = list(result.get("errors", []))
    tree["warnings"] = list(result.get("warnings", [])) + hierarchy_warnings
    tree["validation_errors"] = validate_tree(tree)
    tree["valid"] = bool(result.get("valid")) and not tree["validation_errors"]
    tree["projectable"] = bool(result.get("projectable"))
    tree["source_result"] = {
        "projection_status": result.get("projection_status"),
        "format": result.get("format"),
        "master": result.get("master"),
        "diagnostics": result.get("diagnostics"),
        "hierarchy_projection": {
            "precedence": ["structure.containment[]", "canonical membership"],
            "path_inference": False,
            "ambiguous_parent_policy": "warn_and_leave_unparented",
        },
        "semantic_reference_projection": {
            "enabled": True,
            "source": "references[] only",
            "dimension": "semantic_or_membership",
            "inference": False,
        },
    }
    return tree
