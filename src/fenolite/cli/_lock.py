# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The design lock in ``fenolite build`` (change c0249; capability design-dsl, "Design lock in a build",
and cli-contract, "Frozen builds"): read ``<script stem>.lock`` or ``--lock FILE``, assign the refs, and
plan one write of kind ``lock`` when the canonical text differs from the file's bytes.

A lock exists only for a design with a part without an explicit ref or a take, or one that already has a
lock file, so a design of explicit refs builds as before. The takes of the script are solved here against the
lock's ``[pins]`` section, and their choices joined to the design before it is lowered (change c0257,
``fenolite.cli._pins``). ``--frozen`` refuses any change of the lock's content
(``FEN-7004``) and never writes it. An error finding plans no lock write.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.cli._pins import plan_pins
from fenolite.cli.api import PlannedWrite, Result
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.dsl import Design, moves
from fenolite.dsl.lock import (
    SUFFIX,
    LockFrozenError,
    assign_refs,
    frozen_issues,
    issue,
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
    ``write``, ``result.lock``, the issues, ``result.pins`` and the evidence of the pin choices."""

    refs: dict[str, str] | None
    write: PlannedWrite | None
    summary: dict[str, object] | None
    issues: tuple[Issue, ...]
    pins: tuple[dict[str, object], ...] = ()
    evidence: Evidence | None = None


def lock_location(design: str, lock: str | None, cwd: Path) -> tuple[str, Path]:
    """The lock as the plan names it (relative to the working directory when given so, with forward
    slashes on every system) and its path."""
    path = Path(lock) if lock is not None else Path(design).with_suffix(SUFFIX)
    return path.as_posix(), path if path.is_absolute() else cwd / path


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
    pins = plan_pins(design, found.lock.sections["pins"])
    lock = make_lock(design.name, {**found.lock.sections, "pins": pins.entries})
    found = dataclasses.replace(
        found,
        lock=lock,
        changes=tuple(sorted((*found.changes, *pins.changes), key=lambda change: change.sort_key())),
        issues=(*found.issues, *pins.issues),
    )
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
    return LockPlan(dict(found.refs), write, summary, found.issues, tuple(pins.rows), pins.evidence)


def locked_refs(design: Design, script: Path) -> dict[str, str] | None:
    """The refs the next build gives the parts without an explicit ref, read from the lock beside
    ``script`` without writing it (``fenolite sync``: the code side of ``reference``, change c0250);
    ``None`` without a lock file."""
    path = script.with_suffix(SUFFIX)
    if not path.is_file():
        return None
    old = read_lock(path.read_bytes().decode("utf-8"), file=path.name)
    return dict(assign_refs(design, old, moves=moves(design)).refs)


def with_lock(result: Result, plan: LockPlan) -> Result:
    """``result`` with ``result.lock``, the lock's issues and, unless an error finding refuses the build,
    its planned write."""
    issues = (*plan.issues, *result.issues)
    refused = any(found.severity == "error" for found in issues)
    write = None if refused else plan.write
    summary = plan.summary
    if summary is not None:
        summary = {**summary, "written": write is not None}
    body: dict[str, Any] = {**result.result, "lock": summary, "pins": list(plan.pins)}
    writes = result.writes if write is None else (*result.writes, write)
    evidence = result.evidence if plan.evidence is None else Evidence.combine(result.evidence, plan.evidence)
    return dataclasses.replace(result, result=body, issues=issues, writes=writes, evidence=evidence)


EDITS_FROZEN_HINT = (
    "build without --frozen, run fenolite sync --to-source --confirm to record the edits in edits.toml, "
    "commit it, then build frozen"
)


class EditsFrozenError(LockFrozenError):
    """``build --frozen`` with a ``--take`` or a CAD edit that ``edits.toml`` does not record (change c0250,
    "Frozen builds refuse unrecorded edits"): refused as a change of the lock is (``FEN-7004``)."""

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = tuple(issues)
        self.hint = EDITS_FROZEN_HINT
        count = len(self.issues)
        Exception.__init__(
            self,
            f"under --frozen the build would keep {count} edit{'' if count == 1 else 's'} the source tree "
            "does not record; nothing was written",
        )


def refuse_frozen_edits(*, frozen: bool, takes: Sequence[object], issues: Sequence[Issue]) -> None:
    """Raise ``EditsFrozenError`` under ``frozen`` for each ``--take`` and each ``edit.unrecorded`` of
    ``issues``; each becomes one ``lock.changed`` error naming the take or the property key."""
    if not frozen:
        return
    found = [
        issue(
            "lock.changed",
            f"under --frozen the build would take a side: --take {take}",
            "--take",
            EDITS_FROZEN_HINT,
        )
        for take in takes
    ]
    found += [
        issue(
            "lock.changed",
            f"under --frozen a CAD edit not recorded in edits.toml would be kept: {unrecorded.message}",
            unrecorded.where,
            EDITS_FROZEN_HINT,
        )
        for unrecorded in issues
        if unrecorded.code == "edit.unrecorded"
    ]
    if found:
        raise EditsFrozenError(found)


__all__ = [
    "KIND",
    "EditsFrozenError",
    "LockPlan",
    "lock_location",
    "locked_refs",
    "plan_lock",
    "refuse_frozen_edits",
    "with_lock",
]
