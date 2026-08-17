from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from cw_oracle import data_property, entity_record, mount_property, type_property, workspace_fixture
from server.abstractions import ABSTRACTION_VERSION, AbstractionLibrary


class AbstractionLibraryTests(unittest.TestCase):
    def abstraction(self):
        workspace = workspace_fixture()
        return {
            "version": ABSTRACTION_VERSION,
            "id": "AUTHENTICATION",
            "name": "Authentication",
            "entities": [entity_record("AUTH", properties=[type_property(), data_property()])],
            "rulesets": copy.deepcopy(workspace["rulesets"]),
            "color_spaces": copy.deepcopy(workspace["color_spaces"]),
        }

    def test_publish_get_is_byte_semantic_source_preserving(self):
        with tempfile.TemporaryDirectory() as directory:
            library = AbstractionLibrary(str(Path(directory) / "abstractions"))
            source = self.abstraction()
            library.publish(copy.deepcopy(source))
            self.assertEqual(library.get("AUTHENTICATION"), source)

    def test_publish_rejects_invalid_canonical_semantics(self):
        abstraction = self.abstraction()
        abstraction["entities"][0]["properties"][1]["ruleset_ref"] = "RULESET_EVENT"
        with tempfile.TemporaryDirectory() as directory:
            library = AbstractionLibrary(str(Path(directory) / "abstractions"))
            with self.assertRaisesRegex(ValueError, "does not match ruleset"):
                library.publish(abstraction)

    def test_publish_rejects_view_runtime_authority(self):
        for field, value in {
            "camera": {"position": [0, 0, 0]},
            "settings": {},
            "view": {},
            "runtime": {},
        }.items():
            abstraction = self.abstraction()
            abstraction[field] = value
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                library = AbstractionLibrary(str(Path(directory) / "abstractions"))
                with self.assertRaisesRegex(ValueError, "unsupported fields"):
                    library.publish(abstraction)

    def test_publish_does_not_overwrite_stable_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            library = AbstractionLibrary(str(Path(directory) / "abstractions"))
            library.publish(self.abstraction())
            with self.assertRaises(FileExistsError):
                library.publish(self.abstraction())

    def test_library_does_not_silently_migrate_versions(self):
        abstraction = self.abstraction()
        abstraction["version"] = "0.9.0"
        with tempfile.TemporaryDirectory() as directory:
            library = AbstractionLibrary(str(Path(directory) / "abstractions"))
            with self.assertRaisesRegex(ValueError, "exactly"):
                library.publish(abstraction)

    def test_mount_contract_is_reference_to_abstraction_identity(self):
        mount = mount_property(abstraction_ref="AUTHENTICATION")
        self.assertEqual(mount["value"]["abstraction_ref"], "AUTHENTICATION")
        self.assertEqual(set(mount["value"]), {"abstraction_ref", "properties"})
        self.assertNotIn("entities", mount["value"])

    def test_library_listing_validates_every_published_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "abstractions"
            library = AbstractionLibrary(str(path))
            library.publish(self.abstraction())
            items = library.list()
            self.assertEqual(items, [{"id": "AUTHENTICATION", "name": "Authentication", "version": ABSTRACTION_VERSION}])


if __name__ == "__main__":
    unittest.main()
