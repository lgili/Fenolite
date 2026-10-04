# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Entry-point registry for optional routing plugins."""

from __future__ import annotations

import warnings
from importlib.metadata import EntryPoint, entry_points
from types import MappingProxyType
from typing import cast

from fenolite.routing.protocol import Router

GROUP = "fenolite.routers"
_BUILTINS: dict[str, Router] = {}
_loaded = False
_UNAVAILABLE: dict[str, str] = {}


def register(router: Router) -> None:
    """Register a router instance for tests and embedders; duplicate names are rejected."""
    if router.name in _BUILTINS:
        raise ValueError(f"a router named {router.name!r} is already registered")
    _BUILTINS[router.name] = router


def _entry_points() -> tuple[EntryPoint, ...]:
    discovered = entry_points()
    selected = discovered.select(group=GROUP) if hasattr(discovered, "select") else discovered.get(GROUP, ())
    return tuple(selected)


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    for point in sorted(_entry_points(), key=lambda item: (item.name, item.value)):
        try:
            value = point.load()
            instance = value() if isinstance(value, type) else value
            router = cast(Router, instance)
            name = router.name
            if name in _BUILTINS:
                warnings.warn(
                    f"duplicate router entry point {name!r} from {point.value} ignored", stacklevel=2
                )
                _UNAVAILABLE[point.name] = f"duplicate router name {name!r} from {point.value}"
                continue
            _BUILTINS[name] = router
        except Exception as exc:
            _UNAVAILABLE[point.name] = f"{type(exc).__name__}: {exc}"


def routers() -> MappingProxyType[str, Router]:
    """Return successfully loaded routers, keyed by unique name."""
    _ensure_loaded()
    return MappingProxyType(dict(sorted(_BUILTINS.items())))


def unavailable() -> MappingProxyType[str, str]:
    """Return entry points that failed to load, keyed by their advertised name."""
    _ensure_loaded()
    return MappingProxyType(dict(sorted(_UNAVAILABLE.items())))


__all__ = ["GROUP", "register", "routers", "unavailable"]
