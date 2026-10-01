# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Boolean operations on polygon sets through interchangeable backends.

``select_backend()`` returns the first available backend in ``BACKEND_ORDER``. This version ships only
the stdlib ``fallback`` (convex intersection); the change that first needs general booleans or offsets
adds the ``clipper`` and ``shapely`` backends (loaded through ``_extra.load_extra``) in front of it.
"""

from __future__ import annotations

from collections.abc import Callable

from fenolite.geometry.boolean.base import COORD_LIMIT, BooleanBackend, Join, Operand, check_domain
from fenolite.geometry.boolean.fallback import FallbackBackend
from fenolite.geometry.errors import BackendUnavailable

BACKEND_ORDER: tuple[str, ...] = ("fallback",)
_FACTORIES: dict[str, Callable[[], BooleanBackend]] = {"fallback": FallbackBackend}


def select_backend(prefer: str | None = None) -> BooleanBackend:
    """The named backend, or the first available one in ``BACKEND_ORDER``."""
    if prefer is not None:
        if prefer not in _FACTORIES:
            raise ValueError(f"unknown boolean backend {prefer!r}; known: {', '.join(BACKEND_ORDER)}")
        return _FACTORIES[prefer]()
    for name in BACKEND_ORDER:
        try:
            return _FACTORIES[name]()
        except BackendUnavailable:
            continue
    raise AssertionError("the fallback backend is always available")  # pragma: no cover


def available_backends() -> tuple[str, ...]:
    names: list[str] = []
    for name in BACKEND_ORDER:
        try:
            _FACTORIES[name]()
        except BackendUnavailable:
            continue
        names.append(name)
    return tuple(names)


__all__ = [
    "BACKEND_ORDER",
    "COORD_LIMIT",
    "BooleanBackend",
    "FallbackBackend",
    "Join",
    "Operand",
    "available_backends",
    "check_domain",
    "select_backend",
]
