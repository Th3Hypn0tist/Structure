from cw14_model import is_v14
from structure_tree import validate_tree

from .cw14 import enrich_v14
from .cw_flow import enrich
from .module import read as _read


def read(snapshot, options=None):
    tree = _read(snapshot, options)
    if is_v14(snapshot):
        tree = enrich_v14(tree, snapshot)
        tree["validation_errors"] = validate_tree(tree)
        tree["valid"] = bool(tree.get("valid")) and not tree["validation_errors"]
        tree["projectable"] = bool(tree.get("projectable")) and not tree.get("errors") and not tree["validation_errors"]
        return tree
    return enrich(tree, snapshot)


__all__ = ["read"]
