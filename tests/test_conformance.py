from conformance import compare


def tree(entries, links=None, input_module="test"):
    return {
        "format": "STRUCTUREPROJECTOR_STRUCTURE_TREE",
        "version": "1.0",
        "input_module": input_module,
        "source": {"revision": "test"},
        "entries": entries,
        "links": links or [],
    }


def entry(entry_id):
    return {"id": entry_id, "name": entry_id, "kind": "test", "type": None, "parent_id": None, "status": None, "metadata": {}, "provenance": {"path": entry_id}}


def profile(node_mappings=None, relation_rules=None, explicit_relation_mappings=None):
    return {
        "format": "STRUCTUREPROJECTOR_CONFORMANCE_MAPPING_PROFILE",
        "version": "1.0",
        "node_mappings": node_mappings or [],
        "relation_rules": relation_rules or [],
        "explicit_relation_mappings": explicit_relation_mappings or [],
    }


def evidence():
    return {"kind": "mapping_contract", "source": "test-profile"}


def test_unmapped_expected_is_unresolved_not_missing():
    report = compare(tree([entry("IAM")]), tree([]), profile())
    assert report["nodes"][0]["status"] == "UNRESOLVED"
    assert report["summary"]["missing_implementation"] == 0
    assert report["summary"]["unresolved"] == 1


def test_explicit_mapping_to_absent_observed_is_missing():
    report = compare(
        tree([entry("IAM")]),
        tree([]),
        profile(node_mappings=[{
            "id": "map-iam",
            "expected_id": "IAM",
            "observed_id": "py:iam",
            "evidence": evidence(),
        }]),
    )
    assert report["nodes"][0]["status"] == "MISSING_IMPLEMENTATION"


def test_unmapped_observed_is_unspecified():
    report = compare(tree([]), tree([entry("py:extra")]), profile())
    assert report["unmapped_observed_nodes"][0]["status"] == "UNSPECIFIED_IMPLEMENTATION"


def test_relation_rule_matches_only_explicitly_mapped_endpoints():
    expected = tree(
        [entry("IAM"), entry("AccessCore")],
        [{"id": "e1", "source_id": "IAM", "target_id": "AccessCore", "dimension": "dependencies", "type": "depends_on", "provenance": {}}],
        input_module="canonical",
    )
    observed = tree(
        [entry("py:iam"), entry("py:ac")],
        [{"id": "o1", "source_id": "py:iam", "target_id": "py:ac", "dimension": "imports", "type": "import", "provenance": {}}],
        input_module="python",
    )
    report = compare(expected, observed, profile(
        node_mappings=[
            {"id": "m1", "expected_id": "IAM", "observed_id": "py:iam", "evidence": evidence()},
            {"id": "m2", "expected_id": "AccessCore", "observed_id": "py:ac", "evidence": evidence()},
        ],
        relation_rules=[{
            "id": "r1",
            "expected_dimension": "dependencies",
            "observed_dimensions": ["imports"],
            "observed_types": ["import"],
            "direction": "same",
            "evidence": evidence(),
        }],
    ))
    assert report["relations"][0]["status"] == "MATCHED"


def test_relation_without_rule_is_unresolved():
    expected = tree(
        [entry("IAM"), entry("AccessCore")],
        [{"id": "e1", "source_id": "IAM", "target_id": "AccessCore", "dimension": "dependencies", "type": "depends_on", "provenance": {}}],
    )
    observed = tree([entry("py:iam"), entry("py:ac")])
    report = compare(expected, observed, profile(node_mappings=[
        {"id": "m1", "expected_id": "IAM", "observed_id": "py:iam", "evidence": evidence()},
        {"id": "m2", "expected_id": "AccessCore", "observed_id": "py:ac", "evidence": evidence()},
    ]))
    assert report["relations"][0]["status"] == "UNRESOLVED"
    assert report["summary"]["missing_implementation"] == 0


def test_explicit_relation_mapping_with_wrong_endpoints_is_mismatch():
    expected = tree(
        [entry("IAM"), entry("AccessCore")],
        [{"id": "e1", "source_id": "IAM", "target_id": "AccessCore", "dimension": "dependencies", "type": "depends_on", "provenance": {}}],
    )
    observed = tree(
        [entry("py:iam"), entry("py:ac")],
        [{"id": "o1", "source_id": "py:ac", "target_id": "py:iam", "dimension": "imports", "type": "import", "provenance": {}}],
    )
    report = compare(expected, observed, profile(
        node_mappings=[
            {"id": "m1", "expected_id": "IAM", "observed_id": "py:iam", "evidence": evidence()},
            {"id": "m2", "expected_id": "AccessCore", "observed_id": "py:ac", "evidence": evidence()},
        ],
        explicit_relation_mappings=[{
            "id": "rm1",
            "expected_link_id": "e1",
            "observed_link_id": "o1",
            "evidence": evidence(),
        }],
    ))
    assert report["relations"][0]["status"] == "MISMATCH"
