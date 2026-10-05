# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The backend registry. The built-in backends, Altium and KiCad, are registered on the first call to any
function, and their modules are imported only then, so importing the CLI stays cheap. The Altium backend's
module imports no reader, adapter or writer until it reads a file (change c0043)."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.base import Backend

_BACKENDS: dict[str, Backend] = {}
_loaded = False


def _ensure_builtins() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    from fenolite.backends.altium.backend import AltiumBackend
    from fenolite.backends.kicad.backend import KicadBackend

    if "altium" not in _BACKENDS:
        _BACKENDS["altium"] = AltiumBackend()
    if "kicad" not in _BACKENDS:
        _BACKENDS["kicad"] = KicadBackend()


def register(backend: Backend) -> None:
    """Add a backend; a name that is already registered raises ``ValueError``."""
    _ensure_builtins()
    if backend.name in _BACKENDS:
        raise ValueError(f"a backend named {backend.name!r} is already registered")
    _BACKENDS[backend.name] = backend


def get(name: str) -> Backend:
    """The backend called ``name``; ``KeyError`` naming the known backends otherwise."""
    _ensure_builtins()
    try:
        return _BACKENDS[name]
    except KeyError:
        known = ", ".join(sorted(_BACKENDS)) or "none"
        raise KeyError(f"no backend named {name!r} (known: {known})") from None


def all_backends() -> tuple[Backend, ...]:
    """Every registered backend, sorted by name."""
    _ensure_builtins()
    return tuple(_BACKENDS[name] for name in sorted(_BACKENDS))


def for_path(path: Path) -> Backend | None:
    """The first backend, by name, whose ``detect`` accepts ``path``; ``None`` when none does."""
    for backend in all_backends():
        if backend.detect(path):
            return backend
    return None


__all__ = ["all_backends", "for_path", "get", "register"]
