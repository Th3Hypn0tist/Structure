from cw14_model import is_v14

from .cw14 import enrich_v14
from .cw_flow import enrich
from .module import read as _read


def read(snapshot, options=None):
    tree = _read(snapshot, options)
    if is_v14(snapshot):
        return enrich_v14(tree, snapshot)
    return enrich(tree, snapshot)


__all__ = ["read"]
