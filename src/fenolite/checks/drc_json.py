# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DRC violations as located issues (capability verification-loop, "DRC findings as issues").

Every violation and unconnected item of a DRC report becomes one issue. Its code names the tool's check
(``<oracle>.drc.<type>``), its severity follows the report, and its location comes from the native ids of
the re-read board: ``REF-PIN`` for a numbered pad, ``REF`` for a footprint, the file locator for any other
item, and the report position when the uuid names no item or several. A location is never guessed, so a
wrong ``REF-PIN`` cannot appear. ``checks`` names no backend: the ids sit under the oracle's own name.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.checks.codes import issue, oracle_code
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.model.base import Entity
from fenolite.model.design import Design

RESERVED_SUFFIXES = ("rules-not-loaded", "rules-unchecked")
"""The rules-verdict suffixes; a DRC type that would give one of them becomes ``type-<suffix>``."""
_OUTSIDE = re.compile(r"[^a-z0-9-]")
_RUNS = re.compile(r"-{2,}")
NM_PER_MM = 1_000_000


def type_code(oracle: str, type: str) -> str:  # noqa: A002 (the report's own key)
    """``<oracle>.drc.<suffix>``: the type in lower case, every character outside ``[a-z0-9-]`` as ``-``,
    runs of ``-`` collapsed and the ends trimmed; ``unknown`` when nothing remains."""
    suffix = _RUNS.sub("-", _OUTSIDE.sub("-", type.lower())).strip("-") or "unknown"
    if suffix in RESERVED_SUFFIXES:
        suffix = f"type-{suffix}"
    return oracle_code(oracle, suffix)


def issue_severity(violation: DrcViolation) -> Severity:
    """``info`` for an excluded entry; the report's ``error`` or ``warning``; ``error`` for anything else."""
    if violation.excluded:
        return "info"
    return "warning" if violation.severity == "warning" else "error"


def format_position(point: Point) -> str:
    """``@<x>,<y>`` in millimetres as exact decimals without trailing zeros (``12500000`` nm: ``12.5``)."""

    def mm(value: int) -> str:
        whole, rest = divmod(abs(value), NM_PER_MM)
        digits = f"{rest:06d}".rstrip("0")
        return ("-" if value < 0 else "") + str(whole) + (f".{digits}" if digits else "")

    return f"@{mm(point.x)},{mm(point.y)}"


def item_locations(design: Design | None, oracle: str) -> Mapping[str, str]:
    """``native id → location`` for every entity of the board that ``oracle`` names by exactly one id."""
    board = None if design is None else design.board
    if design is None or board is None:
        return {}
    refs = {c.id: c.ref for c in design.circuit.components}
    found: list[tuple[str, str]] = []

    def add(entity: Entity, location: str) -> None:
        native = entity.native_ids.get(oracle)
        if native and location:
            found.append((native.lower(), location))

    def located(entities: Iterable[Entity]) -> None:
        for entity in entities:
            add(entity, entity.provenance.locator if entity.provenance is not None else "")

    for fp in board.footprints:
        ref = refs.get(fp.component_id, "")
        add(fp, ref)
        for pad in fp.pads:
            add(pad, f"{ref}-{pad.number}" if pad.number and ref else ref)
    for group in (
        board.tracks,
        board.arcs,
        board.vias,
        board.zones,
        board.keepouts,
        board.graphics,
        board.texts,
    ):
        located(group)
    counts = Counter(native for native, _ in found)
    return {native: location for native, location in found if counts[native] == 1}


def sanitise(text: str, *, source: str) -> str:
    """``text`` with the parent folder of ``source`` (the board path as the tool saw it) as ``<tmp>`` and
    the home directory as ``~``."""
    pure = PureWindowsPath(source) if "\\" in source else PurePosixPath(source)
    parent = str(pure.parent)
    if parent not in ("", ".", "/"):
        text = text.replace(parent, "<tmp>")
    home = str(Path.home())
    if home and home != "/":
        text = text.replace(home, "~")
    return text


def _entries(report: DrcReport) -> tuple[DrcViolation, ...]:
    return (*report.violations, *report.unconnected_items)


def finding_types(report: DrcReport, *, oracle: str) -> dict[str, str]:
    """Each emitted code mapped to the tool's raw type, sorted by code."""
    return dict(sorted({type_code(oracle, v.type): v.type for v in _entries(report)}.items()))


def finding_issues(report: DrcReport, *, oracle: str, design: Design | None) -> tuple[Issue, ...]:
    """One issue per violation and unconnected item of ``report``; ``schematic_parity`` is not mapped."""
    locations = item_locations(design, oracle)
    issues: list[Issue] = []
    for violation in _entries(report):
        where = ", ".join(
            locations.get(item.uuid.lower()) or format_position(item.position) for item in violation.items
        )
        message = sanitise(f"{violation.type}: {violation.description}", source=report.source)
        issues.append(
            issue(type_code(oracle, violation.type), message, severity=issue_severity(violation), where=where)
        )
    return tuple(issues)


__all__ = [
    "RESERVED_SUFFIXES",
    "finding_issues",
    "finding_types",
    "format_position",
    "issue_severity",
    "item_locations",
    "sanitise",
    "type_code",
]
