from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.abstractions import ABSTRACTION_VERSION, AbstractionLibrary


class AbstractionLibraryTests(unittest.TestCase):
    def _abstraction(self):
        return {
            "version": ABSTRACTION_VERSION,
            "id": "AUTHENTICATION",
            "name": "Authentication",
            "entities": [{"id": "AUTH", "name": "Auth", "position": [0, 0, 0], "properties": []}],
            "rulesets": [],
            "color_spaces": [],
        }

    def test_publish_and_get_are_source_preserving(self):
        with tempfile.TemporaryDirectory() as directory:
            library = AbstractionLibrary(str(Path(directory) / "abstractions"))
            source = self._abstraction()
            library.publish(source)
            self.assertEqual(library.get("AUTHENTICATION"), source)

    def test_publish_does_not_overwrite_existing_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            library = AbstractionLibrary(str(Path(directory) / "abstractions"))
            library.publish(self._abstraction())
            with self.assertRaises(FileExistsError):
                library.publish(self._abstraction())

    def test_library_does_not_migrate_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            library = AbstractionLibrary(str(Path(directory) / "abstractions"))
            abstraction = self._abstraction()
            abstraction["version"] = "0.9.0"
            with self.assertRaisesRegex(ValueError, "exactly"):
                library.publish(abstraction)

    def test_unknown_fields_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            library = AbstractionLibrary(str(Path(directory) / "abstractions"))
            abstraction = self._abstraction()
            abstraction["camera"] = {"position": [0, 0, 0]}
            with self.assertRaisesRegex(ValueError, "unsupported fields"):
                library.publish(abstraction)


if __name__ == "__main__":
    unittest.main()
