# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What an analysis returns: rows of measured values, the issues, counts and the evidence (capability
board-analyses, "Analysis package and report" and "Measures"; user guide ``docs/analyses.md``).

Every length is an ``int`` of nanometres, every current an ``int`` of milliamperes, every temperature an
``int`` of millikelvin. A distance is a ``Measure``: an interval ``low ≤ d ≤ high`` with the layer, the
points of the path and the two items. Fenolite measures; a finding exists only against a requirement of
the user, and ``judge`` is the one rule for it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, format_length
from fenolite.model.findings import Findings

EVIDENCE = Evidence(
    Level.INFERRED, hypotheses=("H-G-AN-EDGE", "H-G-AN-FIT", "H-G-AN-GAP", "H-G-AN-PATH", "H-G-AN-VIA")
)
"""``INFERRED`` until an independent tool computes the same quantities: hand-computed cases and KiCad
brackets do not raise it."""
LOWERING = ("analysis.input-missing", "analysis.item-unsupported")
"""A report that holds one of these left something out, so its evidence is ``UNVERIFIED``."""
NO_NET = ""


@dataclass(frozen=True, slots=True)
class Measure:
    """A distance as an interval of nanometres: ``low ≤ d ≤ high``. ``layer`` names the layer, or the two
    faces joined by ``/``; ``points`` are the points of the path in order; ``items`` are the two copper
    items. ``bounded`` is true when a search stopped at its limit: ``low`` is then the limit and ``high``
    is ``None``."""

    low: Nm
    high: Nm | None
    layer: str
    points: tuple[Point, ...]
    items: tuple[str, str]
    bounded: bool = False


@dataclass(frozen=True, slots=True)
class CurrentRow:
    """The capacity of one track, arc or via. ``width`` is ``None`` for a via, whose ``thickness`` is the
    plating and whose ``layer`` names its two layers joined by ``/``."""

    kind: Literal["track", "arc", "via"]
    where: str
    entity_id: str
    net: str
    layer: str
    at: Point
    width: Nm | None
    thickness: Nm
    area_nm2: int
    external: bool
    temp_rise_mk: int
    capacity_ma: int
    in_range: bool


@dataclass(frozen=True, slots=True)
class DistanceRow:
    """The distances of one pair of nets, the names in sorted order: the gap on each copper layer that
    carries both, the clearance through air and the creepage along the surface."""

    net_a: str
    net_b: str
    gaps: tuple[Measure, ...] = ()
    clearance: Measure | None = None
    creepage: Measure | None = None


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    """Rows, issues, counts and evidence of one analysis. Rows are sorted by net names, layer and
    ``where``; issues by code, ``where`` and message."""

    rows: tuple[CurrentRow | DistanceRow, ...] = ()
    issues: tuple[Issue, ...] = ()
    summary: Mapping[str, object] = field(default_factory=lambda: {})
    evidence: Evidence = EVIDENCE

    def findings(self) -> Findings:
        """The issues as a findings layer, for a caller that attaches them to ``Design.findings``."""
        return Findings(issues=self.issues)


def judge(measure: Measure, required: Nm) -> Literal["error", "warning"] | None:
    """A requirement against an interval: ``high < r`` is an error, ``low < r ≤ high`` a warning (the
    measure does not decide), ``low ≥ r`` nothing. A bounded measure is judged by ``low`` alone."""
    if measure.high is None:
        return "warning" if measure.low < required else None
    if measure.high < required:
        return "error"
    return "warning" if measure.low < required else None


def sorted_issues(issues: Iterable[Issue]) -> tuple[Issue, ...]:
    return tuple(sorted(issues, key=lambda found: (found.code, found.where, found.message)))


def report_evidence(issues: Iterable[Issue], *inputs: Evidence) -> Evidence:
    """``EVIDENCE`` combined with the evidence of the inputs; ``UNVERIFIED`` when something was left out."""
    combined = Evidence.combine(EVIDENCE, *inputs)
    if any(found.code in LOWERING for found in issues):
        return Evidence(Level.UNVERIFIED, hypotheses=combined.hypotheses)
    return combined


def mm(value: int) -> str:
    """Nanometres as exact millimetres, without the unit."""
    return format_length(value)[:-2]


def point_text(at: Point) -> str:
    return f"({mm(at.x)}, {mm(at.y)}) mm"


__all__ = [
    "EVIDENCE",
    "LOWERING",
    "NO_NET",
    "AnalysisReport",
    "CurrentRow",
    "DistanceRow",
    "Measure",
    "judge",
    "mm",
    "point_text",
    "report_evidence",
    "sorted_issues",
]
