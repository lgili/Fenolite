# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The design lock in ``fenolite build`` (change c0249; capability design-dsl, "Design lock in a build",
and cli-contract, "Frozen builds"): read ``<script stem>.lock`` or ``--lock FILE``, assign the refs, and
plan one write of kind ``lock`` when the canonical text differs from the file's bytes.

A lock exists only for a design with a part without an explicit ref, or one that already has a lock file,
so a design of explicit refs builds as before. ``--frozen`` refuses any change of the lock's content
(``FEN-7004``) and never writes it. An error finding plans no lock write.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.cli.api import PlannedWrite, Result
from fenolite.core.errors import Issue
from fenolite.dsl import Design, moves
from fenolite.dsl.lock import (
    SUFFIX,
    LockFrozenError,
    assign_refs,
    frozen_issues,
    lock_text,
    make_lock,
    needs_lock,
    read_lock,
)

KIND = "lock"
"""The kind of the planned write of the lock."""


@dataclass(frozen=True)
class LockPlan:
    """The lock of one build: the ``refs`` to lower with (``None``: the design needs no lock), the planned
    ``write``, ``result.lock`` and the issues."""

    refs: dict[str, str] | None
    write: PlannedWrite | None
    summary: dict[str, object] | None
    issues: tuple[Issue, ...]


def lock_location(design: str, lock: str | None, cwd: Path) -> tuple[str, Path]:
    """The lock as the plan names it (relative to the working directory when given so) and its path."""
    given = lock if lock is not None else str(Path(design).with_suffix(SUFFIX))
    path = Path(given)
    return given, path if path.is_absolute() else cwd / path


def _shown(path: Path, script: Path) -> str:
    """``result.lock.file``: relative to the script folder when inside it, else the file name only."""
    folder = Path(os.path.abspath(script)).parent
    full = Path(os.path.abspath(path))
    try:
        return full.relative_to(folder).as_posix()
    except ValueError:
        return full.name


def plan_lock(design: Design, *, script: Path, given: str, path: Path, frozen: bool) -> LockPlan:
    """The lock plan of ``design``, built from the script at ``script`` with the lock at ``path``.

    Raises ``FormatError`` for a malformed lock, ``LockVersionError`` for a newer one, ``DslError`` for
    bad aliases, and ``LockFrozenError`` under ``frozen`` when the content would change."""
    shown = _shown(path, script)
    exists = path.is_file()
    data = path.read_bytes() if exists else b""
    if not exists and not needs_lock(design):
        return LockPlan(None, None, None, ())
    old = read_lock(data.decode("utf-8"), file=shown) if exists else make_lock(design.name)
    found = assign_refs(design, old, moves=moves(design))
    if frozen:
        if found.lock != old or not exists:
            changes = found.changes or ()
            raise LockFrozenError(frozen_issues(changes))
        write = None
    else:
        text = lock_text(found.lock).encode("utf-8")
        write = None if exists and text == data else PlannedWrite(path=given, data=text, kind=KIND)
    summary: dict[str, object] = {
        "file": shown,
        "exists": exists,
        "written": write is not None,
        "frozen": frozen,
        "changes": [change.as_json() for change in found.changes],
    }
    return LockPlan(dict(found.refs), write, summary, found.issues)


def with_lock(result: Result, plan: LockPlan) -> Result:
    """``result`` with ``result.lock``, the lock's issues and, unless an error finding refuses the build,
    its planned write."""
    issues = (*plan.issues, *result.issues)
    refused = any(found.severity == "error" for found in issues)
    write = None if refused else plan.write
    summary = plan.summary
    if summary is not None:
        summary = {**summary, "written": write is not None}
    body: dict[str, Any] = {**result.result, "lock": summary}
    writes = result.writes if write is None else (*result.writes, write)
    return dataclasses.replace(result, result=body, issues=issues, writes=writes)


__all__ = ["KIND", "LockPlan", "lock_location", "plan_lock", "with_lock"]
