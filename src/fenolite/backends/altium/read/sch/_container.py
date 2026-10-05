# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The only module of the schematic reader that touches the compound-file reader ``read.cfb`` (c0039)."""

# evidence: see read.sch

from __future__ import annotations

from fenolite.backends.altium.read import cfb
from fenolite.core.errors import Issue

CompoundFile = cfb.CompoundFile
CompoundError = cfb.CompoundError


def is_compound(data: bytes) -> bool:
    return cfb.is_compound(data)


def open_container(data: bytes, *, file: str, issues: list[Issue]) -> cfb.CompoundFile:
    """The compound file of ``data``; its notes are added to ``issues``. A ``CompoundError`` passes on
    unchanged."""
    compound = cfb.open_compound(data, file=file)
    issues.extend(compound.notes)
    return compound


def root_streams(compound: cfb.CompoundFile) -> dict[str, str]:
    """Upper-cased name to the exact path of every stream directly under the root."""
    return {node.name.upper(): node.path for node in compound.children("") if node.kind == "stream"}


def root_storages(compound: cfb.CompoundFile) -> tuple[str, ...]:
    """The paths of the storages directly under the root, in directory order."""
    return tuple(node.path for node in compound.children("") if node.kind == "storage")


def storage_streams(compound: cfb.CompoundFile, path: str) -> tuple[tuple[str, str], ...]:
    """``(name, path)`` of every stream of the storage ``path``, in directory order; streams of nested
    storages follow with their full path as name."""
    out: list[tuple[str, str]] = []
    pending = [path]
    while pending:
        current = pending.pop(0)
        for node in compound.children(current):
            if node.kind == "stream":
                name = node.name if current == path else node.path[len(path) + 1 :]
                out.append((name, node.path))
            else:
                pending.append(node.path)
    return tuple(out)


__all__ = ["CompoundError", "CompoundFile", "is_compound", "open_container", "root_storages", "root_streams"]
