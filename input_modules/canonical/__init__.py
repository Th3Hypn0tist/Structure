from .cw_flow import enrich
from .module import read as _read


def read(snapshot, options=None):
    return enrich(_read(snapshot, options), snapshot)


__all__ = ["read"]
