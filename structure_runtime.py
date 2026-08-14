from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


APP_HOST = os.getenv("STRUCTURE_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("STRUCTURE_PORT", "6969"))
SUGGESTED_SOURCE_REPO = os.getenv("STRUCTURE_SOURCE_REPO", "Th3Hypn0tist/AIGMos-CW")
USER_AGENT = "Structure/0.32"


class StructureError(Exception):
    def __init__(self, error_id: str, message: str, *, path: str | None = None):
        super().__init__(message)
        self.error_id = error_id
        self.message = message
        self.path = path

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.error_id, "message": self.message}
        if self.path:
            result["path"] = self.path
        return result

    def to_dict(self) -> dict[str, Any]:
        return self.as_dict()


@dataclass(frozen=True)
class SourceSnapshot:
    repo: str
    branch: str
    revision: str
    files: dict[str, bytes]


__all__ = [
    "APP_HOST",
    "APP_PORT",
    "SUGGESTED_SOURCE_REPO",
    "USER_AGENT",
    "StructureError",
    "SourceSnapshot",
]
