from __future__ import annotations

import ast
import unittest
from pathlib import Path

from cw_oracle import CW_REQUIREMENTS

ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / "tests" / "modules"

# Requirement -> one or more executable test method names. The meta-test below
# verifies both complete requirement coverage and that every referenced test
# method actually exists in the suite.
CW_TEST_COVERAGE = {
    "CW-001": {"test_canonical_identity_namespace_is_shared_by_entities_and_properties", "test_property_identity_must_be_globally_unique"},
    "CW-002": {"test_unresolved_type_is_incomplete_not_invalid_and_is_never_inferred", "test_save_validation_does_not_infer_or_enrich_semantics"},
    "CW-003": {"test_every_non_link_property_has_explicit_type_discriminator", "test_ruleset_ref_is_authoritative_and_must_match_property_type"},
    "CW-004": {"test_cw_ruleset_catalog_covers_every_locked_property_primitive", "test_every_cw_property_primitive_has_explicit_normal_authoring_path"},
    "CW-005": {"test_link_endpoints_must_resolve_to_canonical_identity", "test_function_refs_resolve_or_fail_loudly"},
    "CW-006": {"test_directed_semantics_have_one_authoritative_representation"},
    "CW-007": {"test_cw_link_catalog_covers_every_locked_link_semantic", "test_link_ruleset_roles_match_cw_contract"},
    "CW-008": {"test_event_effect_and_effect_target_directions_are_enforced", "test_all_event_input_family_links_target_an_event", "test_event_output_origin_is_event"},
    "CW-009": {"test_function_io_refs_are_canonical_refs_not_embedded_copies"},
    "CW-010": {"test_mount_is_reference_composition_not_source_copy", "test_mount_contract_is_reference_to_abstraction_identity"},
    "CW-011": {"test_ruleset_color_spaces_are_resolvable_and_bounded", "test_color_space_requires_complete_bounded_rgb_triplets", "test_link_ruleset_requires_explicit_semantic_roles"},
    "CW-012": {"test_existing_property_may_be_incomplete_only_by_absence_not_by_malformed_claim", "test_name_only_entity_is_valid_incomplete_structure"},
    "CW-013": {"test_workspace_round_trip_preserves_canonical_semantics_exactly", "test_workspace_round_trip_is_source_preserving"},
    "CW-014": {"test_semantic_export_boundary_excludes_view_and_runtime_authority", "test_semantic_export_boundary_is_entities_rulesets_colors_only"},
    "CW-015": {"test_abstraction_round_trip_preserves_semantic_source_exactly", "test_publish_rejects_view_runtime_authority"},
    "CW-016": {"test_event_and_props_projection_are_derived_from_property_types_only", "test_projection_visibility_filters_view_without_rewriting_canonical_properties"},
    "CW-017": {"test_projection_can_aggregate_visual_links_without_collapsing_canonical_contracts", "test_generic_visual_aggregation_key_retains_link_type"},
    "CW-018": {"test_event_and_props_projection_are_derived_from_property_types_only", "test_projection_derives_props_and_events_from_canonical_property_type"},
    "CW-019": {"test_scene_semantic_objects_are_world_space_not_dom_instances"},
    "CW-020": {"test_event_io_is_one_tiny_shared_point_pair_per_entity_layout"},
    "CW-021": {"test_event_playback_state_is_runtime_not_server_semantics"},
    "CW-022": {"test_event_trace_is_derived_only_from_canonical_links"},
    "CW-023": {"test_event_trace_is_derived_only_from_canonical_links"},
    "CW-024": {"test_switching_projection_ruleset_does_not_change_canonical_entities", "test_projection_visibility_filters_view_without_rewriting_canonical_properties"},
    "CW-025": {"test_human_machine_contract_sync_requires_same_human_revision", "test_synchronized_machine_contract_may_match_current_human_revision"},
    "CW-026": {"test_legacy_entity_type_field_fails_loudly", "test_old_workspace_version_is_not_silently_migrated", "test_no_silent_client_or_server_semantic_compatibility_layer"},
    "CW-027": {"test_every_local_static_dependency_loaded_by_html_is_served"},
    "CW-028": {"test_every_cw_property_primitive_has_explicit_normal_authoring_path", "test_no_authoring_feature_requires_raw_json_as_only_semantic_editor"},
    "CW-029": {"test_event_editor_writes_canonical_properties_and_links", "test_event_effect_authoring_uses_ruleset_roles_not_hardcoded_endpoint_guessing"},
    "CW-030": {"test_client_canonical_index_reads_entities_and_properties_without_parallel_model", "test_semantic_export_boundary_is_entities_rulesets_colors_only"},
    "CW-031": {"test_coordinate_space_ref_resolves_to_entity_and_preserves_xyz", "test_coordinate_space_ref_must_resolve_to_entity_not_property", "test_coordinate_space_ref_rejects_self_reference_and_cycles", "test_recursive_coordinate_spaces_support_nested_site_building_abstraction", "test_workspace_validation_enforces_spatial_contract"},
}


def discovered_test_methods() -> set[str]:
    methods: set[str] = set()
    for path in TEST_ROOT.glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                methods.add(node.name)
    return methods


class CWCoverageTests(unittest.TestCase):
    def test_every_registered_cw_requirement_has_executable_coverage(self):
        self.assertEqual(set(CW_TEST_COVERAGE), set(CW_REQUIREMENTS))
        empty = sorted(requirement for requirement, methods in CW_TEST_COVERAGE.items() if not methods)
        self.assertFalse(empty, f"CW requirements without tests: {empty}")

    def test_coverage_manifest_references_real_test_methods(self):
        actual = discovered_test_methods()
        missing = {
            requirement: sorted(method for method in methods if method not in actual)
            for requirement, methods in CW_TEST_COVERAGE.items()
            if any(method not in actual for method in methods)
        }
        self.assertFalse(missing, f"CW coverage manifest references missing test methods: {missing}")

    def test_requirement_descriptions_are_stable_human_readable_contracts(self):
        for requirement, description in CW_REQUIREMENTS.items():
            with self.subTest(requirement=requirement):
                self.assertRegex(requirement, r"^CW-\d{3}$")
                self.assertIsInstance(description, str)
                self.assertGreaterEqual(len(description.strip()), 20)


if __name__ == "__main__":
    unittest.main()
