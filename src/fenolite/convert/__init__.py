# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Conversion of a project from one backend to another, with a report of what is kept, changed or lost
(capability design-conversion; change c0159).

``convert_project`` reads a source project (``sources.read_source``), picks the registered direction for
its backend and the target, and returns the target project's files in memory with a ``ConversionReport``.
It writes no file and runs no tool. A loss of a ``refuse`` kind needs ``allow_lossy``, else
``LossyConversionError`` (``FEN-7001``). The verification of a conversion, which reads the written files
back and compares them with the source, is ``fenolite.api.convert``: this package may not import
``checks`` (layering: ``model``, ``geometry``, ``backends*``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal

from fenolite.convert import to_altium, to_kicad
from fenolite.convert.codes import ISSUE_CODES, issue
from fenolite.convert.direction import BODIES, TARGETS, Direction, Options, Target, TargetLimitError
from fenolite.convert.report import ConversionReport, ReportRow
from fenolite.convert.sources import SourceError, SourceProject, read_source
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CONV-LEDGER",))
"""The report and its verification: mechanical, and ``H-G-CONV-LEDGER`` over the KiCad demo boards."""
DIRECTIONS: dict[tuple[str, str], Direction] = {
    (direction.source, direction.target): direction for direction in (to_altium.DIRECTION, to_kicad.DIRECTION)
}
"""The registered directions by ``(source backend, target backend)``. Changes c0161 and c0162 add theirs."""
PROFILES_FILE = "profiles.toml"


def profiles_text() -> str:
    """The text of the verification profiles of the directions (``data/profiles.toml``), in the exclusion
    format of ``checks.equivalence``, which ``fenolite.api.convert`` loads."""
    return resources.files("fenolite.convert").joinpath("data", PROFILES_FILE).read_text(encoding="utf-8")


class LossyConversionError(FenoliteError):
    """A conversion would lose items of a ``refuse`` kind and ``allow_lossy`` was not given: ``issues``
    holds one ``convert.lossy`` per such kind, with the kind as ``where`` and the counts per reason."""

    cli_code = "FEN-7001"

    def __init__(self, issues: tuple[Issue, ...], report: ConversionReport) -> None:
        self.issues = issues
        self.report = report
        self.hint = "re-run with --allow-lossy to accept the loss; result.report of that run lists it"
        kinds = ", ".join(found.where for found in issues)
        super().__init__(f"the conversion would lose items of the source ({kinds})")


@dataclass(frozen=True, slots=True)
class Conversion:
    """A conversion in memory: the target project's files by name, the report, the source as read, the
    target backend, the evidence, the issues (the source's read, the writer's and the ``convert.*``
    ones), the direction, the design that was written, and the file the target backend reads back."""

    files: Mapping[str, bytes]
    report: ConversionReport
    source: SourceProject
    target: str
    evidence: Evidence
    issues: tuple[Issue, ...]
    direction: Direction
    design: Design
    read_back: str


def _per_reason(row: ReportRow, outcome: Literal["changed", "lost"]) -> str:
    return "; ".join(f"{r.count} {r.reason}" for r in row.reasons if r.outcome == outcome)


def lossy_issue(row: ReportRow) -> Issue:
    """The ``convert.lossy`` warning of a ``refuse`` kind with losses."""
    message = f"{row.lost} of {row.source} {row.kind} item(s) of the source are not converted: "
    return issue("convert.lossy", message + _per_reason(row, "lost"), where=row.kind)


def changed_issue(row: ReportRow) -> Issue:
    """The ``convert.changed`` info of a kind with changes."""
    message = f"{row.changed} {row.kind} item(s) are converted in another form: "
    return issue("convert.changed", message + _per_reason(row, "changed"), where=row.kind)


def direction_for(backend: str, to: str) -> Direction:
    """The registered direction from ``backend`` to ``to``; ``SourceError`` (a ``ValueError``) for a pair
    without one."""
    if to not in TARGETS:
        raise SourceError(f"--to is one of {', '.join(TARGETS)}, got {to!r}", where="--to")
    found = DIRECTIONS.get((backend, to))
    if found is None:
        registered = ", ".join(f"{a} to {b}" for a, b in sorted(DIRECTIONS))
        raise SourceError(
            f"no conversion from {backend} to {to} is registered (convert.direction-unsupported)",
            where="--to",
            hint=f"the registered directions are: {registered}",
        )
    return found


def convert_project(
    source: Path | str,
    *,
    to: Target,
    kicad_version: int = 10,
    allow_lossy: bool = False,
    bodies: str = "extruded",
    name: str | None = None,
) -> Conversion:
    """The target project of ``source`` in memory, with its report (capability design-conversion,
    "Conversion package"). ``to`` is ``kicad`` or ``altium``; ``kicad_version`` the major of a KiCad
    target; ``bodies`` what an Altium target does with component bodies (``extruded`` or ``off``);
    ``name`` the stem of the written files. ``LossyConversionError`` for a loss of a ``refuse`` kind
    without ``allow_lossy``; ``SourceError`` (a ``ValueError``) for a source that is no project or a pair
    of backends without a direction; ``TargetLimitError`` when the target writer cannot hold the design."""
    if bodies not in BODIES:
        raise ValueError(f"bodies is one of {', '.join(BODIES)}, got {bodies!r}")
    read = read_source(Path(source))
    direction = direction_for(read.backend, to)
    written = direction.write(read, Options(kicad_version=kicad_version, bodies=bodies, name=name))
    report = written.report
    lossy = tuple(lossy_issue(row) for row in report.rows if row.kind in report.refused)
    if lossy and not allow_lossy:
        raise LossyConversionError(lossy, report)
    changed = tuple(changed_issue(row) for row in report.rows if row.changed)
    return Conversion(
        files=written.files,
        report=report,
        source=read,
        target=to,
        evidence=Evidence.combine(read.evidence, direction.evidence, EVIDENCE),
        issues=(*read.issues, *written.issues, *lossy, *changed),
        direction=direction,
        design=written.design,
        read_back=written.read_back,
    )


__all__ = [
    "DIRECTIONS",
    "EVIDENCE",
    "ISSUE_CODES",
    "PROFILES_FILE",
    "Conversion",
    "ConversionReport",
    "Direction",
    "LossyConversionError",
    "SourceError",
    "SourceProject",
    "TargetLimitError",
    "changed_issue",
    "convert_project",
    "direction_for",
    "lossy_issue",
    "profiles_text",
]
