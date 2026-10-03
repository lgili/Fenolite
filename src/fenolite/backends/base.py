# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The backend protocol: what every file-format backend offers, independent of any one backend.

``checks``, ``placement`` and the CLI reach backends only through this module and
``fenolite.backends.registry``. It imports only ``core`` and ``model``; a backend never imports
another backend.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol, runtime_checkable

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, Udeg
from fenolite.model.board import PadKind, Side
from fenolite.model.design import Design
from fenolite.model.library import Library

BackendOperation = Literal["detect", "read", "write", "lower", "validate"]
Downgrade = Literal["unsupported", "supported"]


@dataclass(frozen=True, slots=True)
class ReadResult:
    """What ``Backend.read`` returns: a ``Design`` for a board, a ``Library`` for library files."""

    content: Design | Library
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = Evidence()

    @property
    def design(self) -> Design:
        """The content when it is a ``Design``; ``TypeError`` for a library."""
        if not isinstance(self.content, Design):
            raise TypeError(f"read result holds a {type(self.content).__name__}, not a Design")
        return self.content


@dataclass(frozen=True, slots=True)
class WriteResult:
    """What a backend writer returns: the file text and the warnings and infos of the write.

    Errors are raised, never returned, so a caller cannot write a file that lost content silently.
    """

    text: str
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True, slots=True)
class DrcItem:
    """A board item a DRC violation names: its uuid, the tool's description, and a report position."""

    uuid: str
    description: str
    position: Point

    def __post_init__(self) -> None:
        if type(self.position.x) is not int or type(self.position.y) is not int:
            raise TypeError(f"DRC positions are integer nanometres, got {self.position!r}")


@dataclass(frozen=True, slots=True)
class DrcViolation:
    """One violation of a DRC report; ``type`` and ``severity`` are the tool's own strings."""

    type: str
    description: str
    severity: str
    items: tuple[DrcItem, ...] = ()
    excluded: bool = False
    comment: str = ""


@dataclass(frozen=True, slots=True)
class DrcReport:
    """A DRC report in report order, independent of the tool that wrote it."""

    source: str
    date: str
    kicad_version: str
    coordinate_units: str
    violations: tuple[DrcViolation, ...] = ()
    unconnected_items: tuple[DrcViolation, ...] = ()
    schematic_parity: tuple[DrcViolation, ...] = ()
    ignored_checks: tuple[str, ...] = ()
    included_severities: tuple[str, ...] = ()

    def entries(self) -> tuple[tuple[str, str, str, bool, tuple[tuple[str, int, int], ...]], ...]:
        """The violations and unconnected items as a sorted tuple of ``(group, type, severity, excluded,
        items)``, each item as its description and position: item uuids and the report order are left
        out, so two runs of a tool on one file can be compared."""
        groups = (("violations", self.violations), ("unconnected_items", self.unconnected_items))
        found = [
            (
                group,
                v.type,
                v.severity,
                v.excluded,
                tuple(sorted((i.description, i.position.x, i.position.y) for i in v.items)),
            )
            for group, listed in groups
            for v in listed
        ]
        return tuple(sorted(found))

    def of_type(self, type: str) -> tuple[DrcViolation, ...]:  # noqa: A002 (the report's own key)
        """The violations, unconnected items and parity items of ``type``, in report order."""
        groups = (self.violations, self.unconnected_items, self.schematic_parity)
        return tuple(v for group in groups for v in group if v.type == type)


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    """What a backend can do here. ``operations`` lists only what is implemented."""

    name: str
    read_kinds: tuple[str, ...]
    write_kinds: tuple[str, ...] = ()
    targets: tuple[int, ...] = ()
    default_target: int | None = None
    downgrade: Downgrade = "unsupported"
    operations: tuple[BackendOperation, ...] = ("detect", "read")
    evidence: Evidence = Evidence()

    def to_json(self) -> dict[str, Any]:
        """A JSON-compatible mapping with exactly the report's fields."""
        return {
            "name": self.name,
            "read_kinds": list(self.read_kinds),
            "write_kinds": list(self.write_kinds),
            "targets": list(self.targets),
            "default_target": self.default_target,
            "downgrade": self.downgrade,
            "operations": list(self.operations),
            "evidence": {
                "level": self.evidence.level.value,
                "oracle": self.evidence.oracle,
                "hypotheses": list(self.evidence.hypotheses),
            },
        }


SkipReason = Literal[
    "outside-root", "variable", "relative", "missing", "nested-table", "too-large", "reserved-name"
]


@dataclass(frozen=True, slots=True)
class SkippedFile:
    """A file or folder that a project names but that is not copied for an oracle run, and why."""

    name: str
    reason: SkipReason


@dataclass(frozen=True, slots=True)
class ProjectSet:
    """The closed set of project files an oracle sees: POSIX names relative to ``root`` → source paths.

    ``board`` is one of the names; ``has_project`` and ``has_rules`` say whether the board's project and
    rules files are among them.
    """

    root: Path
    board: str
    files: Mapping[str, Path]
    skipped: tuple[SkippedFile, ...] = ()
    has_project: bool = False
    has_rules: bool = False

    def __post_init__(self) -> None:
        for name in self.files:
            rel = PurePosixPath(name)
            if not name or rel.is_absolute() or ".." in rel.parts or "\\" in name or rel.as_posix() != name:
                raise ValueError(f"project file name {name!r} is not a relative POSIX name")
        if self.board not in self.files:
            raise ValueError(f"the board {self.board!r} is not one of the project files")


@dataclass(frozen=True, slots=True)
class RoundTrip:
    """A same-version rebuild verdict: ``passed`` is the conjunction of the three equalities.

    ``difference`` locates the first failing part (a tree locator, ``model`` or ``opaque``), ``""`` when
    it passed.
    """

    level: Literal["RT1"]
    passed: bool
    tree_equal: bool
    model_equal: bool
    opaque_equal: bool
    opaque_count: int
    difference: str = ""

    def __post_init__(self) -> None:
        if self.passed != (self.tree_equal and self.model_equal and self.opaque_equal):
            raise ValueError("RoundTrip.passed must equal tree_equal and model_equal and opaque_equal")


@dataclass(frozen=True, slots=True)
class Validation:
    """What ``Validator.validate`` returns: the read and its round-trip verdict."""

    read: ReadResult
    roundtrip: RoundTrip


@runtime_checkable
class Validator(Protocol):
    """A backend that validates a file: reads it and checks its round trip.

    ``validate`` raises the reader's ``FormatError`` (subclasses included) for a file it cannot read, and
    ``ValueError`` naming the kind for a kind it cannot validate.
    """

    name: str

    def validate(self, path: Path, *, issues: list[Issue] | None = None) -> Validation: ...


CanaryState = Literal["fired", "absent", "inconclusive", "not-applicable"]


@dataclass(frozen=True, slots=True)
class DrcOutcome:
    """An oracle's DRC run: the report (``None`` when none was written, canary items removed), the canary
    state, the files the tool wrote in its copy, and the evidence of the run."""

    report: DrcReport | None
    tool_version: str
    canary: CanaryState
    canary_reason: str = ""
    canary_removed: int = 0
    tool_writes: tuple[str, ...] = ()
    outcome: Literal["exit", "timeout"] = "exit"
    returncode: int | None = 0
    message: str = ""
    evidence: Evidence = Evidence()


class Oracle(Protocol):
    """An external tool that gives DRC verdicts on a project copy set; it never writes under its root and
    reports a timeout as ``outcome == "timeout"``."""

    name: str

    def version(self) -> str: ...

    def drc(self, project: ProjectSet) -> DrcOutcome: ...


@dataclass(frozen=True, slots=True)
class PadAssignment:
    """An element ``REF-PIN`` and the source's own label for its net (``""`` for no net)."""

    element: str
    net: str


@dataclass(frozen=True, slots=True)
class Uncovered:
    """An element a source names but does not assign, with the source's reason."""

    element: str
    reason: str


@dataclass(frozen=True, slots=True)
class PadNetList:
    """The net-to-pad assignments of one source (``model``, ``board`` or ``export``) and its coverage."""

    source: str
    assignments: tuple[PadAssignment, ...]
    uncovered: tuple[Uncovered, ...] = ()

    def __post_init__(self) -> None:
        both = sorted({a.element for a in self.assignments} & {u.element for u in self.uncovered})
        if both:
            raise ValueError(f"{self.source}: assigned and uncovered at once: {', '.join(both)}")


@dataclass(frozen=True, slots=True)
class NetlistOutcome:
    """An oracle's netlist export: the list (``None`` when the tool wrote none) and the run's evidence."""

    netlist: PadNetList | None
    tool_version: str
    outcome: Literal["exit", "timeout"] = "exit"
    returncode: int | None = 0
    message: str = ""
    evidence: Evidence = Evidence()


@dataclass(frozen=True, slots=True)
class PlotView:
    """A review view an oracle plotted: its name, its size in bytes and a SHA-256 that two plots of one
    board share (the oracle leaves a date the tool stamps out of it). No bytes leave the oracle."""

    name: str
    bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class PlotOutcome:
    """An oracle's plot of a project: the views it produced, the names of those it could not produce
    (``message`` says why), and the evidence of the run."""

    views: tuple[PlotView, ...]
    tool_version: str
    failed: tuple[str, ...] = ()
    message: str = ""
    evidence: Evidence = Evidence()


@dataclass(frozen=True, slots=True)
class Rt2Outcome:
    """The DRC reports of an RT2 run: the runs on the original in run order (two, more when the oracle
    repeated them, fewer when a run wrote no report), the first run on the re-dump, and ``repeats``, the
    further runs on the re-dump. An oracle repeats both sides when the first re-dump report differs from
    the original, so that a caller can tell a difference from a tool that does not repeat its own report.
    ``normalised`` when both files were re-saved by the tool first."""

    before: tuple[DrcReport, ...]
    after: DrcReport | None
    normalised: bool
    tool_version: str
    outcome: Literal["exit", "timeout"] = "exit"
    returncode: int | None = 0
    message: str = ""
    evidence: Evidence = Evidence()
    repeats: tuple[DrcReport, ...] = ()


@runtime_checkable
class NetlistOracle(Protocol):
    """An oracle that exports the netlist of a project's board; it never writes under the project root."""

    name: str

    def version(self) -> str: ...

    def netlist(self, project: ProjectSet, *, board: Design) -> NetlistOutcome: ...


@runtime_checkable
class RoundTripOracle(Protocol):
    """An oracle that runs DRC on a board and on the backend's re-dump of it (RT2)."""

    name: str

    def version(self) -> str: ...

    def rt2(self, project: ProjectSet) -> Rt2Outcome: ...


@runtime_checkable
class Plotter(Protocol):
    """An external tool that plots review views of a project copy set; it never writes under its root."""

    name: str

    def plot(self, project: ProjectSet) -> PlotOutcome: ...


@dataclass(frozen=True, slots=True)
class PadCopper:
    """The copper of a pad on one copper layer: the points within ``width / 2`` of ``core``, boundary
    included.

    The core is one point (a disc of diameter ``width``), two or more points with ``filled`` false (an
    open polyline; a closed outline repeats its first point), or three or more points with ``filled`` true
    (the region a ring in the normal form encloses). ``exact`` is false for a conservative superset.
    """

    layer: str
    core: tuple[Point, ...]
    width: Nm
    filled: bool = False
    exact: bool = True

    def __post_init__(self) -> None:
        if not self.core:
            raise ValueError("a copper entry needs a core of at least one point")
        if self.width < 0:
            raise ValueError(f"a copper entry cannot have the negative width {self.width}")
        if len(self.core) == 1 and self.width == 0:
            raise ValueError("a copper entry of one point needs a width above 0")
        if self.filled and len(self.core) < 3:
            raise ValueError("a filled copper entry needs a ring of at least three points")


@dataclass(frozen=True, slots=True)
class BoardPad:
    """A pad in the board frame: where it is, how it is turned, its layers and net, its copper entries
    per copper layer, and its drilled hole (a point, or the two ends of a slot) with the drill size."""

    footprint_id: str
    ref: str
    path: str
    pad_id: str
    number: str
    kind: PadKind
    position: Point
    rotation: Udeg
    side: Side
    layers: tuple[str, ...]
    net_id: str | None
    net: str | None
    copper: tuple[PadCopper, ...] = ()
    hole: tuple[Point, ...] = ()
    drill: Nm | None = None


@dataclass(frozen=True, slots=True)
class PlacedExtent:
    """The courtyard of a placed footprint in the board frame: the rings of its front and back faces, where
    they come from, and whether they are exact. Each ring is in the normal form."""

    footprint_id: str
    side: Side
    front: tuple[tuple[Point, ...], ...] = ()
    back: tuple[tuple[Point, ...], ...] = ()
    source: Literal["courtyard", "definition", "pads", "none"] = "none"
    exact: bool = True

    @property
    def own(self) -> tuple[tuple[Point, ...], ...]:
        """The face of the footprint's own side: ``front`` on the top, ``back`` on the bottom."""
        return self.front if self.side == "top" else self.back


@runtime_checkable
class BoardFrame(Protocol):
    """A backend that gives the board-frame geometry of a design: every pad, and every footprint's
    courtyard. Both are pure queries."""

    def board_pads(self, design: Design, *, issues: list[Issue] | None = None) -> tuple[BoardPad, ...]: ...

    def placed_extents(
        self, design: Design, *, issues: list[Issue] | None = None
    ) -> tuple[PlacedExtent, ...]: ...


class Backend(Protocol):
    """A file-format backend.

    ``detect`` decides from the path alone, without reading the file. ``read`` appends warnings and
    infos to ``issues`` when a list is given and raises errors as exceptions that carry a registered
    ``cli_code`` or are ``FormatError``s.
    """

    name: str

    def detect(self, path: Path) -> bool: ...

    def read(self, path: Path, *, issues: list[Issue] | None = None) -> ReadResult: ...

    def capabilities(self) -> CapabilityReport: ...


__all__ = [
    "Backend",
    "BackendOperation",
    "BoardFrame",
    "BoardPad",
    "CanaryState",
    "CapabilityReport",
    "Downgrade",
    "DrcItem",
    "DrcOutcome",
    "DrcReport",
    "DrcViolation",
    "NetlistOracle",
    "NetlistOutcome",
    "Oracle",
    "PadAssignment",
    "PadCopper",
    "PadNetList",
    "PlacedExtent",
    "PlotOutcome",
    "PlotView",
    "Plotter",
    "ProjectSet",
    "ReadResult",
    "RoundTrip",
    "RoundTripOracle",
    "Rt2Outcome",
    "SkipReason",
    "SkippedFile",
    "Uncovered",
    "Validation",
    "Validator",
    "WriteResult",
]
