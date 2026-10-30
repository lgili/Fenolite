# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Picks in ``fenolite build`` and ``fenolite pick`` (change c0254; ``docs/picking.md``, "Resolution in a
build").

``picking`` installs the resolver of the lock's ``picks`` section (``fenolite.dsl.lock.picks_resolver``)
while the lock is planned: it reads the rows (the design's records, ``devices/`` beside the script and the
shipped families), resolves every query part with ``fenolite.pick.resolve``, gives each picked part its
device, and returns the new entries and their changes to the lock. A pick changes the lock only through the
lock's planned write; ``--frozen`` refuses any change as change c0249 specifies.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
from collections.abc import Generator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from fenolite.dsl import Design
from fenolite.dsl.lock import LockChange, LockValue, SectionResult, picks_resolver
from fenolite.dsl.query import apply_device
from fenolite.pick.lockpicks import entries, tables
from fenolite.pick.resolve import Resolution, resolve
from fenolite.pick.rows import PROPOSED_DIR, SHIPPED, Row, all_rows


@dataclass
class PickRun:
    """What one resolution gave: the ``resolution`` (``None`` when the design has no query part and the
    lock holds no pick) and the rows it read."""

    script: Path
    update: frozenset[str] = frozenset()
    resolution: Resolution | None = None
    rows: tuple[Row, ...] = ()
    files: list[str] = field(default_factory=lambda: [])

    def summary(self) -> dict[str, object]:
        """``result.picks`` and ``result.generators``."""
        found = self.resolution
        if found is None:
            return {"picks": [], "generators": []}
        return {
            "picks": [pick.as_json() for pick in found.picks],
            "generators": [dict(item) for item in found.generators],
        }


def query_parts(design: Design) -> dict[str, object]:
    """Path → effective query of every query part of ``design``, in path order."""
    return {path: part.query for path, part in sorted(design.parts.items()) if part.call_query is not None}


def proposed_files(script: Path) -> list[Path]:
    """The proposed rows beside ``script`` (``devices/proposed/*.toml``), inputs of a build that
    reads them."""
    folder = Path(os.path.abspath(script)).parent / "devices" / PROPOSED_DIR
    return sorted(folder.glob("*.toml"), key=lambda path: path.name) if folder.is_dir() else []


def _resolver(run: PickRun):  # noqa: ANN202 - the lock's Resolver
    def section(design: Design, kept: Mapping[str, LockValue]) -> SectionResult:
        queries = {path: query for path, query in query_parts(design).items() if query is not None}
        locked = entries(kept)
        if not queries and not locked:
            return SectionResult(entries=MappingProxyType({}))
        if not run.rows:
            folder = Path(os.path.abspath(run.script)).parent
            run.rows = all_rows(
                folder,
                tuple(design.device_records.values()),
                queries=tuple(queries.values()),  # pyright: ignore[reportArgumentType]
                devices=tuple(entry.device for entry in locked.values()),
            )
        found = resolve(queries, locked, run.rows, update=run.update)  # pyright: ignore[reportArgumentType]
        run.resolution = found
        for pick in found.picks:
            if pick.row is not None:
                origin = "builtin" if pick.row.origin == SHIPPED else "authored"
                apply_device(design.parts[pick.path], pick.row.record, origin)
        changes = tuple(
            LockChange("picks", path, before, after, reason) for path, before, after, reason in found.changes
        )
        return SectionResult(
            entries=MappingProxyType(dict(tables(found.entries))), changes=changes, issues=found.issues
        )

    return section


@contextlib.contextmanager
def picking(script: Path, update: frozenset[str] = frozenset()) -> Generator[PickRun]:
    """Resolve the ``picks`` section with the rows beside ``script`` while the block plans the lock."""
    run = PickRun(script, update)
    with picks_resolver(_resolver(run)):
        yield run


def file_digests(paths: list[Path]) -> dict[str, str]:
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


__all__ = ["PickRun", "file_digests", "picking", "proposed_files", "query_parts"]
