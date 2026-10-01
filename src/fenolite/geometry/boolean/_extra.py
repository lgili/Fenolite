# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The single loader of the optional ``geo`` extra.

This is the only module of the stdlib-only packages (``core``, ``model``, ``geometry``, ``dsl``) that
may call ``importlib.import_module``, and only for the import names in ``GEO_MODULES``, which must
equal the packages of the ``geo`` extra in ``pyproject.toml`` (``tests/unit/test_import_graph.py``).
"""

from __future__ import annotations

import importlib
from types import ModuleType

from fenolite.geometry.errors import backend_unavailable

GEO_MODULES: tuple[str, ...] = ("pyclipper", "shapely")


def load_extra(name: str) -> ModuleType:
    """Import ``name`` from the ``geo`` extra; ``BackendUnavailable`` when it is not installed."""
    if name not in GEO_MODULES:
        raise ValueError(f"{name!r} is not in GEO_MODULES {GEO_MODULES}")
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise backend_unavailable(f"optional package {name!r} is not installed", where=name) from exc


__all__ = ["GEO_MODULES", "load_extra"]
