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
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.cli._pins import plan_pins
from fenolite.cli.api import PlannedWrite, Result
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence
from fenolite.dsl import Design, moves
from fenolite.dsl.lock import (
    SUFFIX,
    Lock,
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


class LibraryItemMissing(FenoliteError):
    """A ``[library.items]`` entry of the lock whose folder is missing (``FEN-6004``, change c0279): the
    build writes nothing; ``fenolite get --locked`` restores the folder."""

    cli_code = "FEN-6004"

    def __init__(self, issues: tuple[Issue, ...], script: str) -> None:
        self.issues = issues
        self.hint = f"fenolite get --locked {script} --dry-run"
        count = len(issues)
        super().__init__(
            f"{count} library item{'' if count == 1 else 's'} pinned by the design lock "
            f"{'is' if count == 1 else 'are'} missing; nothing was written"
        )


def check_library(lock: Lock, script: Path, shown: str) -> None:
    """Raise ``LibraryItemMissing`` when a vendored item of the lock's ``library`` section has no folder
    beside the script. The build reads the section and never hashes the folders (``get --status`` does)."""
    from fenolite.library.codes import issue as library_issue

    folder = Path(os.path.abspath(script)).parent
    missing = tuple(
        library_issue(
            "library.item-missing",
            f"{key} is pinned by the lock, but its folder {entry['path']} is missing",
            where=key,
            hint=f"fenolite get --locked {shown} --dry-run",
        )
        for key, entry in sorted(lock.sections.get("library", {}).items())
        if isinstance(entry, Mapping) and not (folder / str(entry["path"])).is_dir()
    )
    if missing:
        raise LibraryItemMissing(missing, shown)


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


def plan_lock(
    design: Design, *, script: Path, given: str, path: Path, frozen: bool, named: str | None = None
) -> LockPlan:
    """The lock plan of ``design``, built from the script at ``script`` with the lock at ``path``.

    Raises ``FormatError`` for a malformed lock, ``LockVersionError`` for a newer one, ``DslError`` for
    bad aliases, and ``LockFrozenError`` under ``frozen`` when the content would change. A lock entry of a
    vendored library item whose folder is missing raises ``LibraryItemMissing`` (``named``: the script as the
    command line gave it, for the hint)."""
    shown = _shown(path, script)
    exists = path.is_file()
    data = path.read_bytes() if exists else b""
    if not exists and not needs_lock(design):
        return LockPlan(None, None, None, ())
    old = read_lock(data.decode("utf-8"), file=shown) if exists else make_lock(design.name)
    check_library(old, script, named or Path(script).name)
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


__all__ = [
    "KIND",
    "LibraryItemMissing",
    "LockPlan",
    "check_library",
    "lock_location",
    "plan_lock",
    "with_lock",
]
