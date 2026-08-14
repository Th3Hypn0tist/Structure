from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from structure_tree import add_entry, new_tree, validate_tree


def _dir_id(path: str) -> str:
    return "directory:." if not path else f"directory:{path}"


def _file_id(path: str) -> str:
    return f"file:{path}"


def read(snapshot: Any, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Project an arbitrary source directory as explicit filesystem structure.

    The adapter does not inspect file contents for semantic relations. Directory
    containment comes only from the relative paths already present in the
    snapshot. This is a structural source view, not a semantic interpretation.
    """
    tree = new_tree(input_module="directory", source={
        "repository": snapshot.repo,
        "branch": snapshot.branch,
        "revision": snapshot.revision,
        "source_type": "directory",
    })

    add_entry(
        tree,
        entry_id=_dir_id(""),
        name="Directory",
        kind="directory",
        parent_id=None,
        entry_type="directory",
        metadata={"source_role": "filesystem_root", "relative_path": "."},
        provenance={"repository": snapshot.repo, "branch": snapshot.branch, "revision": snapshot.revision},
    )

    directories: set[str] = set()
    for raw_path in snapshot.files:
        path = PurePosixPath(str(raw_path))
        parent = path.parent
        while str(parent) not in {".", ""}:
            directories.add(parent.as_posix())
            parent = parent.parent

    for directory in sorted(directories, key=lambda value: (value.count("/"), value.lower(), value)):
        path = PurePosixPath(directory)
        parent_path = path.parent.as_posix()
        parent_id = _dir_id("") if parent_path == "." else _dir_id(parent_path)
        add_entry(
            tree,
            entry_id=_dir_id(directory),
            name=path.name,
            kind="directory",
            parent_id=parent_id,
            entry_type="directory",
            metadata={"source_role": "filesystem_directory", "relative_path": directory},
            provenance={"repository": snapshot.repo, "branch": snapshot.branch, "revision": snapshot.revision},
        )

    for raw_path, payload in sorted(snapshot.files.items(), key=lambda item: str(item[0]).lower()):
        relative = PurePosixPath(str(raw_path)).as_posix()
        path = PurePosixPath(relative)
        parent_path = path.parent.as_posix()
        parent_id = _dir_id("") if parent_path == "." else _dir_id(parent_path)
        add_entry(
            tree,
            entry_id=_file_id(relative),
            name=path.name,
            kind="file",
            parent_id=parent_id,
            entry_type="file",
            metadata={
                "source_role": "filesystem_file",
                "relative_path": relative,
                "size_bytes": len(payload),
            },
            provenance={"path": relative, "repository": snapshot.repo, "branch": snapshot.branch, "revision": snapshot.revision},
        )

    tree["validation_errors"] = validate_tree(tree)
    tree["valid"] = not tree["validation_errors"]
    tree["projectable"] = tree["valid"]
    tree["source_result"] = {
        "input_format": "directory",
        "structure_source": "relative filesystem paths only",
        "content_semantics": False,
        "path_semantics": False,
        "inference": False,
    }
    return tree


__all__ = ["read"]
