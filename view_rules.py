from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

VIEW_RULESET_DIR = os.path.join(os.path.dirname(__file__), "rulesets", "view")
MAX_BINDING_DEPTH = 6
MAX_BINDING_NODES = 1500


class ViewRuleError(ValueError):
    pass


def _decode_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _encode_pointer_token(token: str) -> str