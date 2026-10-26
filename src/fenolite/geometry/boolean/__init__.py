# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Boolean operations on polygon sets through interchangeable backends.

``BACKEND_ORDER`` is ``("fallback", "clipper")``: the stdlib ``fallback`` (convex intersection) and the
``clipper`` backend of the ``geo`` extra (union; change c0167), loaded through ``_extra.load_extra`` only
when it is made. ``select_backend()`` returns the first available backend; with ``operation=`` the first
available one that gives that operation, else ``BackendUnavailable`` naming the extra.
"""

from __future__ import annotations

from collections.abc import Callable

from fenolite.geometry.boolean.base import COORD_LIMIT, BooleanBackend, Join, Operand, check_domain
from fenolite.geometry.boolean.clipper import ClipperBackend
from fenolite.geometry.boolean.fallback import FallbackBackend
from fenolite.geometry.errors import BackendUnavailable, backend_unavailable

BACKEND_ORDER: tuple[str, ...] = ("fallback", "clipper")
_FACTORIES: dict[str, Callable[[], BooleanBackend]] = {"fallback": FallbackBackend, "clipper": ClipperBackend}


def select_backend(prefer: str | None = None, *, operation: str | None = None) -> BooleanBackend:
    """The named backend, or the first available one in ``BACKEND_ORDER``; with ``operation``, the first
    available one whose ``operations`` holds it (``BackendUnavailable`` naming the ``geo`` extra when none
    does)."""
    if prefer is not None:
        if prefer not in _FACTORIES:
            raise ValueError(f"unknown boolean backend {prefer!r}; known: {', '.join(BACKEND_ORDER)}")
        return _FACTORIES[prefer]()
    for name in BACKEND_ORDER:
        try:
            backend = _FACTORIES[name]()
        except BackendUnavailable:
            continue
        if operation is None or operation in backend.operations:
            return backend
    if operation is not None:
        raise backend_unavailable(f"no installed boolean backend gives {operation!r}", where=operation)
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
    "ClipperBackend",
    "FallbackBackend",
    "Join",
    "Operand",
    "available_backends",
    "check_domain",
    "select_backend",
]
