import json
from types import SimpleNamespace

from flow_trace import build_trace
from input_modules.canonical.cw14 import enrich_v14
from projection_instances import projection_base_ids, topic_catalog


def _step(step_id, *, actor="A", action="A", target="B", result_refs=None, next_refs=None):
    return {
        "id": step_id,
        "actor_ref": actor,
        "action_ref": action,
        "data_ref": None,
        "target_ref": target,
        "cause_ref": None,
        "condition_ref": None,
        "payload_ref": None,
        "result_refs": list(result_refs or []),
        "error_refs": [],
        "next_step_refs": list(next_refs or []),
        "subflow_refs": [],
        "resume_ref": None,
    }


def _contract(identity_id, *, topics=None, flows=None, semantics=None):
    return {
        "format": {"contract_format": "AIGMOS_CANONICAL_CONTRACT", "format_version": "1.4"},
        "identity": {"id": identity_id, "name": identity_id, "type": "test", "version": "1"},
        "status": "unlocked",
        "source_role": "definition",
        "purpose": "test",
        "scope": {"owns": [], "does_not_own": []},
        "members": [],
        "structure": {"containment": [], "relations": [], "ownership": [], "authority": [], "dependencies": []},
        "topics": list(topics or []),
        "behavior": {"states": [], "interfaces": [], "operations": [], "events": [], "flows": list(flows or [])},
        "semantics": dict(semantics or {}),
        "constraints": {"invariants": [], "hard_gates": []},
        "references": [],
        "prose": {"summary": "", "notes": []},
    }


def _topic(topic_id, *, parents=None, composed=None, members=None, flows=None, children=None):
    return {
        "id": topic_id,
        "name": topic_id,
        "purpose": "test topic",
        "parent_topic_refs": list(parents or []),
        "composed_topic_refs": list(composed or []),
        "member_refs": list(members or []),
        "relation_refs": [],
        "operation_refs": [],
        "event_refs": [],
        "flow_refs": list(flows or []),
        "child_topics": list(children or []),
        "metadata": {},
    }


def _snapshot():
    flow = {
        "id": "FLOW_MECHANISM",
        "owner_ref": "A",
        "name": "Mechanism",
        "flow_type": "test",
        "entry_refs": ["STEP_1"],
        "exit_refs": ["STEP_2"],
        "steps": [
            _step("STEP_1", result_refs=["C"], next_refs=["STEP_2"]),
            _step("STEP_2"),
        ],
        "metadata": {},
    }
    child = _topic("TOPIC_CHILD", parents=["TOPIC_PARENT"], members=["B"])
    parent = _topic("TOPIC_PARENT", members=["A"], children=[child])
    mechanism = _topic("TOPIC_MECHANISM", composed=["TOPIC_PARENT"], flows=["FLOW_MECHANISM"])
    format_root = {
        "version": "1.4.0",
        "bootstrap": {"order": ["00_Contract_Format.json", "01_Master.json", "canonical tree recursively from Master"]},
        "contract_shape": {"format": {"format_version": "1.4"}},
    }
    files = {
        "canonical/json/00_Contract_Format.json": json.dumps(format_root).encode(),
        "canonical/json/10_A.json": json.dumps(_contract("A", topics=[parent, mechanism], flows=[flow])).encode(),
        "canonical/json/20_B.json": json.dumps(_contract("B")).encode(),
        "canonical/json/30_C.json": json.dumps(_contract("C", semantics={"outsider": True, "outsider_reason": "awaiting_topic_classification"})).encode(),
    }
    return SimpleNamespace(files=files, repo="test/repo", branch="main", revision="abc")


def _tree():
    return {
        "entries": [
            {"id": "A", "name": "A", "parent_id": None, "metadata": {}, "provenance": {}},
            {"id": "B", "name": "B", "parent_id": None, "metadata": {}, "provenance": {}},
            {"id": "C", "name": "C", "parent_id": None, "metadata": {}, "provenance": {}},
        ],
        "links": [],
        "flows": [],
        "errors": [],
        "warnings": [],
        "valid": True,
        "projectable": True,
        "source_result": {},
    }


def test_topic_inheritance_composition_and_outsider_are_explicit():
    tree = enrich_v14(_tree(), _snapshot())
    assert tree["errors"] == []
    topics = {topic["id"]: topic for topic in tree["topics"]}

    assert topics["TOPIC_CHILD"]["resolved_ancestor_topic_refs"] == ["TOPIC_PARENT"]
    assert set(topics["TOPIC_PARENT"]["resolved_grouping_member_refs"]) == {"A", "B"}
    assert topics["TOPIC_CHILD"]["resolved_grouping_member_refs"] == ["B"]

    assert topics["TOPIC_MECHANISM"]["resolved_component_topic_refs"] == ["TOPIC_PARENT"]
    assert set(topics["TOPIC_MECHANISM"]["composed_trace_surface"]["member_refs"]) == {"A"}
    assert tree["outsiders"]["C"]["outsider_reason"] == "awaiting_topic_classification"


def test_projector_uses_canonical_topic_surfaces_without_profile_guessing():
    tree = enrich_v14(_tree(), _snapshot())
    catalog = {item["id"]: item for item in topic_catalog(tree)}
    assert "TOPIC_MECHANISM" in catalog
    assert catalog["TOPIC_MECHANISM"]["canonical_topic"] is True
    assert catalog["TOPIC_MECHANISM"]["semantic_authority"] is False

    base = projection_base_ids(tree, "TOPIC_MECHANISM")
    assert "A" in base
    assert "B" in base
    # Outsider means Topic classification is unresolved; it does not hide an
    # identity that is explicitly referenced by the mechanism's flow surface.
    assert "C" in base


def test_trace_uses_next_step_refs_not_result_refs():
    tree = enrich_v14(_tree(), _snapshot())
    trace = build_trace(tree, "FLOW_MECHANISM")
    assert [step["step_id"] for step in trace["steps"]] == ["STEP_1", "STEP_2"]
    assert trace["steps"][0]["result_refs"] == ["C"]
    assert trace["causal_source"] == "behavior.flows[].steps[].next_step_refs/subflow_refs/resume_ref only"
    assert "result_refs" in trace["forbidden_causal_sources"]
