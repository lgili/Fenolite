# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The backend protocol: what every file-format backend offers, independent of any one backend.

``checks``, ``placement`` and the CLI reach backends only through this module and
``fenolite.backends.registry``. It imports only ``core`` and ``model``; a backend never imports
another backend.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Literal, Protocol, runtime_checkable

from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, Udeg
from fenolite.model.board import PadKind, Side, ZoneFill
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
class ErcItem:
    """A schematic item an ERC violation names: its uuid, the tool's description, its position on the
    sheet, and ``where``, the location a backend found for it (``REF-PIN``, ``REF`` or a label text)."""

    uuid: str
    description: str
    position: Point
    where: str = ""

    def __post_init__(self) -> None:
        if type(self.position.x) is not int or type(self.position.y) is not int:
            raise TypeError(f"ERC positions are integer nanometres, got {self.position!r}")


@dataclass(frozen=True, slots=True)
class ErcViolation:
    """One violation of an ERC report; ``type`` and ``severity`` are the tool's own strings, ``sheet`` is
    the tool's readable path of the sheet it is listed under and ``sheet_id`` the tool's own identifier of
    that sheet (for KiCad, its path of uuids)."""

    type: str
    description: str
    severity: str
    items: tuple[ErcItem, ...] = ()
    excluded: bool = False
    sheet: str = ""
    sheet_id: str = ""


@dataclass(frozen=True, slots=True)
class ErcReport:
    """An ERC report in report order, sheet by sheet, independent of the tool that wrote it; ``sheets``
    holds the readable path of every sheet the report lists, with or without violations."""

    source: str
    date: str
    kicad_version: str
    coordinate_units: str
    violations: tuple[ErcViolation, ...] = ()
    ignored_checks: tuple[str, ...] = ()
    included_severities: tuple[str, ...] = ()
    sheets: tuple[str, ...] = ()

    def entries(self) -> tuple[tuple[str, str, str, bool, tuple[tuple[str, int, int], ...]], ...]:
        """The violations as a sorted tuple of ``(sheet, type, severity, excluded, items)``, each item as
        its description and position: item uuids, ``where`` and the report order are left out, so two
        runs of a tool can be compared."""
        found = [
            (
                v.sheet,
                v.type,
                v.severity,
                v.excluded,
                tuple(sorted((i.description, i.position.x, i.position.y) for i in v.items)),
            )
            for v in self.violations
        ]
        return tuple(sorted(found))

    def kinds(self) -> tuple[tuple[str, str, str, bool], ...]:
        """The violations as a sorted tuple of ``(sheet, type, severity, excluded)``, one entry per
        violation and no item: what two runs of a tool on one project can be expected to share, because a
        tool may name another of the pins or labels of one violation in each run."""
        return tuple(sorted((v.sheet, v.type, v.severity, v.excluded) for v in self.violations))

    def of_type(self, type: str) -> tuple[ErcViolation, ...]:  # noqa: A002 (the report's own key)
        """The violations of ``type``, in report order."""
        return tuple(v for v in self.violations if v.type == type)


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


MATRIX_OPERATIONS = ("detect", "read", "write", "roundtrip_exact", "roundtrip_modified")
"""The operations of an evidence matrix row, in the order they are listed."""


@dataclass(frozen=True, slots=True)
class MatrixRow:
    """What one backend package does with one file kind, and how well each operation is verified.

    A cell that is ``None`` means that the package does not implement that operation for the kind.
    ``detect``: the package names the kind of a file from its name or its content. ``read``: a reader
    builds a model object from a file of the kind. ``write``: a writer produces a file of the kind from a
    model object that Fenolite created. ``roundtrip_exact``: a file read and written back for the same
    version, unchanged in between, keeps its whole content. ``roundtrip_modified``: a file read, changed
    through the model and written keeps everything the change did not touch, or the write is refused.
    ``experimental`` names the operations that may change in any release.
    """

    backend: str
    kind: str
    detect: Evidence | None = None
    read: Evidence | None = None
    write: Evidence | None = None
    roundtrip_exact: Evidence | None = None
    roundtrip_modified: Evidence | None = None
    experimental: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        where = f"matrix row {self.backend}/{self.kind}"
        if self.roundtrip_exact is not None and self.read is None:
            raise ValueError(f"{where}: roundtrip_exact needs read")
        if self.roundtrip_modified is not None and (self.read is None or self.write is None):
            raise ValueError(f"{where}: roundtrip_modified needs read and write")
        if len(set(self.experimental)) != len(self.experimental):
            raise ValueError(f"{where}: experimental names an operation twice")
        for operation in self.experimental:
            if operation not in MATRIX_OPERATIONS:
                raise ValueError(f"{where}: experimental names {operation!r}, which is not an operation")
            if getattr(self, operation) is None:
                raise ValueError(f"{where}: experimental names {operation!r}, whose cell is not set")

    def cells(self) -> tuple[tuple[str, Evidence], ...]:
        """The cells that are set, as ``(operation, evidence)`` in the order of ``MATRIX_OPERATIONS``."""
        found = ((operation, getattr(self, operation)) for operation in MATRIX_OPERATIONS)
        return tuple((operation, cell) for operation, cell in found if cell is not None)

    def verified_by(self) -> tuple[str, ...]:
        """The hypothesis ids of the cells that are set, each once, sorted."""
        return tuple(sorted({ident for _, cell in self.cells() for ident in cell.hypotheses}))

    def to_json(self) -> dict[str, Any]:
        """A JSON-compatible mapping: the row's names, a label or ``None`` per operation, the ids and the
        experimental operations."""
        row: dict[str, Any] = {"backend": self.backend, "kind": self.kind}
        for operation in MATRIX_OPERATIONS:
            cell: Evidence | None = getattr(self, operation)
            row[operation] = None if cell is None else cell.label()
        row["verified_by"] = list(self.verified_by())
        row["experimental"] = [o for o in MATRIX_OPERATIONS if o in self.experimental]
        return row


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
    state, the files the tool wrote in its copy, and the evidence of the run. ``parity_judged`` is true
    exactly when the run asked the tool to compare the board with its schematic and the tool did so."""

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
    parity_judged: bool = False


class Oracle(Protocol):
    """An external tool that gives DRC verdicts on a project copy set; it never writes under its root and
    reports a timeout as ``outcome == "timeout"``."""

    name: str

    def version(self) -> str: ...

    def drc(self, project: ProjectSet) -> DrcOutcome: ...


UNCONNECTED_ITEMS = "unconnected_items"
"""The key of ``DrcLimits`` that stands for the list of unconnected items of a ``DrcReport``."""


@dataclass(frozen=True, slots=True)
class DrcLimits:
    """Where a DRC tool stops writing its report: the largest number of entries it writes for each named
    type (``per_type``), and for every other type (``others``). ``unconnected_items`` stands for the list
    of unconnected items; every other key is a violation ``type`` in the tool's own spelling. A count that
    reaches its limit is a lower bound."""

    per_type: Mapping[str, int]
    others: int

    def __post_init__(self) -> None:
        for name, value in (("others", self.others), *self.per_type.items()):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:  # pyright: ignore[reportUnnecessaryIsInstance]
                raise ValueError(f"the report limit of {name!r} is not a positive int: {value!r}")
        object.__setattr__(self, "per_type", MappingProxyType(dict(self.per_type)))

    def limit(self, type: str) -> int:  # noqa: A002 (the report's own key)
        """The limit of ``type``: its own, or ``others``."""
        return self.per_type.get(type, self.others)


@runtime_checkable
class LimitedOracle(Protocol):
    """An oracle that says where its DRC report stops. It stands beside ``Oracle``: an oracle that does not
    satisfy it says nothing about limits."""

    def report_limits(self) -> DrcLimits: ...


@dataclass(frozen=True, slots=True)
class ErcOutcome:
    """An oracle's ERC run: the report (``None`` when none was written, ``message`` then being the first
    sanitised line of the tool's output), the files the tool wrote in its copy, and the evidence."""

    report: ErcReport | None
    tool_version: str
    tool_writes: tuple[str, ...] = ()
    outcome: Literal["exit", "timeout"] = "exit"
    returncode: int | None = 0
    message: str = ""
    evidence: Evidence = Evidence()


@dataclass(frozen=True, slots=True)
class ErcRt2Outcome:
    """The ERC reports of a schematic RT2 run: the runs on the project as it is, in run order, the run on
    the backend's re-dump of its sheets (``None`` when it wrote no report), and the numbers of sheet files
    re-dumped and left as they are."""

    before: tuple[ErcReport, ...]
    after: ErcReport | None
    tool_version: str
    outcome: Literal["exit", "timeout"] = "exit"
    returncode: int | None = 0
    message: str = ""
    evidence: Evidence = Evidence()
    redumped: int = 0
    kept: int = 0


@runtime_checkable
class ErcOracle(Protocol):
    """An external tool that gives ERC verdicts on a project copy set; it never writes under its root and
    reports a timeout as ``outcome == "timeout"``."""

    name: str

    def version(self) -> str: ...

    def erc(self, project: ProjectSet) -> ErcOutcome: ...


@dataclass(frozen=True, slots=True)
class ZoneFills:
    """One zone's identity, fill flag and derived polygons in a refill result."""

    zone_id: str
    fills: tuple[ZoneFill, ...]
    filled: bool


@dataclass(frozen=True, slots=True)
class FillOutcome:
    """A refill verdict; ``zones`` is absent when the tool could not supply readable fills."""

    zones: tuple[ZoneFills, ...] | None
    tool_version: str
    outcome: Literal["exit", "timeout"] = "exit"
    returncode: int | None = 0
    message: str = ""
    supported: bool = True
    evidence: Evidence = Evidence()
    stable: bool = True


class FillOracle(Protocol):
    """An oracle that refills a copy of a project board."""

    name: str

    def refill(self, project: ProjectSet) -> FillOutcome: ...


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
    """The net-to-pad assignments of one source (``model``, ``board``, ``export`` or ``schematic``) and its
    coverage."""

    source: str
    assignments: tuple[PadAssignment, ...]
    uncovered: tuple[Uncovered, ...] = ()

    def __post_init__(self) -> None:
        both = sorted({a.element for a in self.assignments} & {u.element for u in self.uncovered})
        if both:
            raise ValueError(f"{self.source}: assigned and uncovered at once: {', '.join(both)}")


@dataclass(frozen=True, slots=True)
class SideComponent:
    """A component as a schematic gives it to the parity comparison: its value, the library id of its
    footprint, the pin numbers of all its units in body style 1, common pins included, and those of the
    flags ``dnp`` and ``exclude_from_bom`` that its symbol has."""

    value: str = ""
    footprint: str = ""
    pins: frozenset[str] = frozenset()
    attributes: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class SchematicSide:
    """The schematic side of a parity comparison (``checks.parity``; change c0072): ``components`` by
    reference, and ``nodes``, the net name of each (reference, pin number) in the backend's stored form.
    A reference that starts with ``#`` is no component. ``fold`` lists the spellings that the backend
    reads as one in a net name, as (text, replacement): both sides are compared after the replacements.
    ``single_prefix`` starts the name of a net that the backend makes for one pin on no net (``""`` when it
    makes none): on the board, further pads of that pin's number are on that name followed by ``_<n>``."""

    components: Mapping[str, SideComponent]
    nodes: Mapping[tuple[str, str], str]
    fold: tuple[tuple[str, str], ...] = ()
    single_prefix: str = ""


@dataclass(frozen=True, slots=True)
class SideOutcome:
    """A schematic side and the evidence of the reading it came from; ``side`` is ``None`` when the
    backend's own reading does not cover the schematic (``message`` says why)."""

    side: SchematicSide | None
    evidence: Evidence = Evidence()
    message: str = ""


@runtime_checkable
class ParityInputs(Protocol):
    """A backend that builds the schematic side of a project for the parity comparison. Without ``nodes``
    the nets come from the backend's own reading of the schematic, and the result is ``None`` when that
    reading does not cover the schematic; with ``nodes`` (an oracle's schematic netlist) they come from
    it. It reads the files of the set and writes nothing."""

    def schematic_side(self, project: ProjectSet, *, nodes: PadNetList | None = None) -> SideOutcome: ...


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
class SchematicNetlistOracle(Protocol):
    """An oracle that exports the netlist of a project's schematic: a ``PadNetList`` of source
    ``schematic`` with one assignment ``REF-PIN`` → net name per pin the tool lists. ``netlist`` is ``None``
    when the tool wrote no export; a timeout is an outcome, not an exception. It never writes under the
    project root (change c0063)."""

    name: str

    def version(self) -> str: ...

    def schematic_netlist(self, project: ProjectSet) -> NetlistOutcome: ...


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
class PlotTable:
    """A table of a plot copy (change c0117): never stored in the model, only written into the copy of a
    board that a drawing is plotted from. ``at`` is its top-left corner; ``cells`` holds one tuple of
    texts per row, each as long as ``column_widths``; a row of ``header`` rows is ruled off below."""

    name: str
    layer: str
    at: Point
    column_widths: tuple[Nm, ...]
    row_heights: tuple[Nm, ...]
    cells: tuple[tuple[str, ...], ...]
    text_size: Nm
    border: bool = True


@dataclass(frozen=True, slots=True)
class PlotText:
    """A text of a plot copy, centred on ``at``; a text on a back layer is written mirrored."""

    name: str
    text: str
    layer: str
    at: Point
    size: Nm


@dataclass(frozen=True, slots=True)
class PlotDimension:
    """An orthogonal dimension of a plot copy between ``start`` and ``end``, its line ``offset`` away
    from them (negative: above a horizontal one, left of a vertical one), in millimetres."""

    name: str
    layer: str
    start: Point
    end: Point
    offset: Nm
    direction: Literal["horizontal", "vertical"]
    precision: int
    text_size: Nm


PlotItem = PlotTable | PlotText | PlotDimension


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


@dataclass(frozen=True, slots=True)
class DesignRules:
    """The clearance rules that a project's own files hold, applied to a board design.

    ``design`` is the board design with the net classes, the class of each net and the design rules of
    those files; what a missing or unread file would give keeps the design's own value. ``min_clearance``
    is the board minimum clearance, or ``None``. The two switches say, for the tool version the board is
    judged against, whether a governing custom clearance rule replaces the class clearances and whether
    the board minimum also raises a rule's value. ``opaque_clearance_rules`` counts the clearance rules
    that could not be lifted into the model, and ``unread`` names each file that failed to read, with the
    error's message, in file-name order. ``left_out`` names the copper that the project's files hold in a
    form the model does not carry as copper, as (kind, count, reason) in kind order: ``design`` is then
    without the items that stand for it, and the copper check reports each entry. ``clearance_cells`` counts
    the cells of the clearance matrices of those files (clearances per pair of object kinds): those that a
    rule of ``design`` holds, and those that none holds.
    """

    design: Design
    min_clearance: Nm | None = None
    rules_over_classes: bool = True
    floor_over_rules: bool = False
    opaque_clearance_rules: int = 0
    unread: tuple[tuple[str, str], ...] = ()
    evidence: Evidence = Evidence()
    left_out: tuple[tuple[str, int, str], ...] = ()
    clearance_cells: tuple[int, int] = (0, 0)


@runtime_checkable
class DesignRulesSource(Protocol):
    """A backend that gives the clearance rules of a project's own files. A pure query, not an operation:
    it never raises for a file that fails to read."""

    def design_rules(
        self, design: Design, project: ProjectSet, *, issues: list[Issue] | None = None
    ) -> DesignRules: ...


NIL_UUID = "00000000-0000-0000-0000-000000000000"
"""The uuid that stands for the missing second item of a stored exclusion of one item."""


@dataclass(frozen=True, slots=True)
class StoredExclusion:
    """One DRC exclusion that a project's own files store (change c0114): the tool's check ``type``, the
    stored marker ``position`` in integer nm, the two stored item ``uuids`` in order (the second is
    ``NIL_UUID`` for an entry of one item) and the ``comment`` stored with it."""

    type: str
    position: Point
    uuids: tuple[str, str]
    comment: str = ""


@runtime_checkable
class ExclusionSource(Protocol):
    """A backend that gives the DRC exclusions a project's own files store, so that ``checks`` can say
    which of them the tool still applies. A pure query, not an operation: it never raises for a project
    file that fails to read, and returns ``()`` then."""

    def stored_exclusions(self, project: ProjectSet) -> tuple[StoredExclusion, ...]: ...


@dataclass(frozen=True, slots=True)
class NetLength:
    """The length of one net as a tool counts it, in nm: ``routed`` is the centre-line length of its tracks
    and arcs, ``vias`` the sum of the heights its vias add, ``die`` the sum of the die lengths of its pads;
    ``total`` is their sum, and ``via_count`` counts its vias."""

    net: str
    routed: Nm
    vias: Nm
    die: Nm
    total: Nm
    via_count: int

    def __post_init__(self) -> None:
        if self.total != self.routed + self.vias + self.die:
            raise ValueError(f"the total of net {self.net!r} is not the sum of its parts")


@dataclass(frozen=True, slots=True)
class LengthFacts:
    """The lengths of nets as a tool counts them.

    ``nets`` maps a net name to its length. ``depths`` maps each copper layer to its depth as the tool
    counts it (empty when unknown), ``die`` maps a pad id to its die length (a pad without one has no
    entry). ``major`` names the tool version whose counting the facts follow, ``stackup`` says where the
    depths come from (``none`` when they are unknown), and ``count_vias`` is false when the project counts
    no via height."""

    nets: Mapping[str, NetLength]
    depths: Mapping[str, Nm]
    die: Mapping[str, Nm]
    major: int | None
    stackup: Literal["board", "default", "none"]
    count_vias: bool
    evidence: Evidence

    def __post_init__(self) -> None:
        object.__setattr__(self, "nets", MappingProxyType(dict(self.nets)))
        object.__setattr__(self, "depths", MappingProxyType(dict(self.depths)))
        object.__setattr__(self, "die", MappingProxyType(dict(self.die)))


@runtime_checkable
class LengthSource(Protocol):
    """A backend that gives the length of nets as its tool counts them. A pure query, not an operation: it
    never raises for a project file that fails to read, and appends warnings and infos to ``issues``."""

    def length_facts(
        self,
        design: Design,
        *,
        project: ProjectSet | None = None,
        major: int | None = None,
        nets: Collection[str] | None = None,
        issues: list[Issue] | None = None,
    ) -> LengthFacts: ...


ChangeKind = Literal["added", "removed", "changed"]


@dataclass(frozen=True, slots=True)
class Change:
    """One difference of a comparison: ``a`` and ``b`` hold the compact canonical JSON of each side (``""``
    for none). ``checks.diff`` reports model differences with it, and a backend the differences between the
    records of two files."""

    path: str
    change: ChangeKind
    a: str = ""
    b: str = ""


@dataclass(frozen=True, slots=True)
class DiffReport:
    """Every difference between two models, sorted by path and then by change."""

    equal: bool
    changes: tuple[Change, ...]
    summary: Mapping[str, Mapping[str, int]]

    def to_json(self, limit: int | None = None) -> dict[str, Any]:
        """``equal``, ``summary``, ``differences`` (the first ``limit`` changes, or all), ``total`` and
        ``truncated``."""
        shown = self.changes if limit is None else self.changes[: max(0, limit)]
        return {
            "equal": self.equal,
            "summary": {kind: dict(counts) for kind, counts in self.summary.items()},
            "differences": [dataclasses.asdict(change) for change in shown],
            "total": len(self.changes),
            "truncated": len(shown) < len(self.changes),
        }


DocumentRole = Literal["project", "schematic", "pcb", "symbol-library", "footprint-library", "other"]
ContainerLevel = Literal["RT-A0", "RT-A1"]


def _relative_name(name: str) -> bool:
    rel = PurePosixPath(name)
    return bool(name) and not rel.is_absolute() and ".." not in rel.parts and "\\" not in name


@dataclass(frozen=True, slots=True)
class Document:
    """One document of a set: its POSIX name relative to the set's root, its read kind and its role."""

    name: str
    kind: str
    role: DocumentRole


@dataclass(frozen=True, slots=True)
class DocumentSet:
    """The documents an input names (a document alone, or a project's documents), sorted by name.

    ``project`` and ``board`` are names of ``documents`` or ``None``; ``missing`` holds, sorted, the names
    that the project file lists and that do not exist.
    """

    root: Path
    project: str | None
    board: str | None
    documents: tuple[Document, ...]
    missing: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        names = [document.name for document in self.documents]
        for name in (*names, *self.missing):
            if not _relative_name(name):
                raise ValueError(f"document name {name!r} is not a relative POSIX name")
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ValueError(f"document names are repeated: {', '.join(repeated)}")
        if names != sorted(names):
            raise ValueError("documents must be sorted by name")
        if list(self.missing) != sorted(self.missing):
            raise ValueError("missing names must be sorted")
        for what, name in (("project", self.project), ("board", self.board)):
            if name is not None and name not in names:
                raise ValueError(f"the {what} {name!r} is not one of the documents")

    def named(self, name: str) -> Document:
        """The document ``name``; ``KeyError`` when the set does not hold it."""
        for document in self.documents:
            if document.name == name:
                return document
        raise KeyError(name)

    def of_role(self, role: DocumentRole) -> tuple[Document, ...]:
        return tuple(document for document in self.documents if document.role == role)


@dataclass(frozen=True, slots=True)
class ProjectRead:
    """Two readings of one document set, apart: every schematic document as one design, and the document
    ``board``. A side without a document, or whose reading was refused, is ``None``; ``errors`` maps a
    document name to the error that refused it."""

    schematic: ReadResult | None
    pcb: ReadResult | None
    errors: Mapping[str, FormatError] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class ContainerRoundTrip:
    """The verdict of one container round-trip level on one file.

    ``different`` holds the paths of the streams that differ and ``difference`` locates the first one. A
    level that cannot be judged has ``judged`` false and a ``reason``: it is neither a pass nor a failure.
    """

    level: ContainerLevel
    judged: bool
    passed: bool
    streams: int = 0
    different: tuple[str, ...] = ()
    records: int = 0
    bytes_equal: int = 0
    opaque_count: int = 0
    difference: str = ""
    reason: str = ""
    evidence: Evidence = Evidence()
    """The backend's evidence for this verdict: its reader's level and the hypotheses the level rests on."""

    def __post_init__(self) -> None:
        if self.passed != (self.judged and not self.different):
            raise ValueError("ContainerRoundTrip.passed must equal judged and not different")
        if bool(self.reason) == self.judged:
            raise ValueError("ContainerRoundTrip.reason is non-empty exactly when judged is false")
        if bool(self.difference) != bool(self.different):
            raise ValueError("ContainerRoundTrip.difference is empty exactly when different is empty")


@dataclass(frozen=True, slots=True)
class ModelScope:
    """The model fields, per entity kind, that a comparison covers, and the tolerance for lengths (nm)."""

    fields: Mapping[str, tuple[str, ...]]
    length_tolerance: int = 0

    def __post_init__(self) -> None:
        if type(self.length_tolerance) is not int or self.length_tolerance < 0:
            raise ValueError(f"length_tolerance is a non-negative int, got {self.length_tolerance!r}")


@runtime_checkable
class DocumentValidator(Protocol):
    """A backend whose input is a set of documents: it names them, reads the schematic side and the PCB side
    apart, judges the container round trip of one file, and states what its writers write.

    ``documents`` decides from the path, the project file and at most the first eight bytes of each
    document. No method writes a file. ``container_roundtrip`` raises the reader's ``FormatError`` for a
    file it cannot read and returns ``judged=False`` with a reason for a level it cannot judge.
    ``stage_evidence`` maps a check stage name to the evidence the backend adds to it (the hypotheses its
    readings rest on for that stage), so that ``checks`` names no hypothesis of a backend.
    """

    name: str

    def documents(self, path: Path) -> DocumentSet: ...

    def read_documents(self, documents: DocumentSet) -> ProjectRead: ...

    def container_roundtrip(self, path: Path, level: ContainerLevel) -> ContainerRoundTrip: ...

    def written_scope(self) -> ModelScope: ...

    def stage_evidence(self) -> Mapping[str, Evidence]: ...


@runtime_checkable
class DocumentParity(Protocol):
    """A document backend that builds the schematic side of the parity comparison (``checks.parity``) from
    the two readings of a set that ``DocumentValidator.read_documents`` gave: ``schematic`` is the design
    of the schematic documents and ``board`` the design of the PCB document. It reads no file and runs no
    tool; ``side`` is ``None`` when the schematic reading gives no side (``message`` says why)."""

    def parity_side(self, schematic: Design, board: Design) -> SideOutcome: ...


@dataclass(frozen=True, slots=True)
class ModelRoundTrip:
    """The verdict of a model round trip of a set of documents (change c0090; for Altium, RT-A3): the
    documents are read, the model is written as new documents, and those are read again.

    ``judged`` is false, with a ``reason``, when the trip could not run. ``equal`` tells that the two
    readings are equal inside ``scope``; ``differences`` are the located differences. ``unwritten`` counts,
    per kind, what the first reading holds and the written documents do not; it never changes ``equal``.
    ``written`` counts the model items that were written, per kind, and ``files`` names the written
    files. Nothing of the trip stays on disk."""

    judged: bool
    equal: bool
    differences: tuple[Change, ...] = ()
    unwritten: Mapping[str, int] = field(default_factory=lambda: {})
    written: Mapping[str, int] = field(default_factory=lambda: {})
    files: tuple[str, ...] = ()
    reason: str = ""
    evidence: Evidence = Evidence()


class ModelCompare(Protocol):
    """How two designs are compared under a scope (``checks.diff.diff_designs``): a backend imports no
    check, so the caller hands the comparison in."""

    def __call__(self, a: Design, b: Design, scope: ModelScope, /) -> DiffReport: ...


@runtime_checkable
class ModelWriter(Protocol):
    """A document backend that writes a model as documents (change c0090). ``in_model_frame`` gives a
    reading of documents that were written from ``model`` in the frame of ``model``: a writer may place
    the board elsewhere in its document. ``model_roundtrip`` reads the document at ``path``, writes the
    model and reads the result."""

    def in_model_frame(self, model: Design, reading: Design) -> Design: ...

    def model_roundtrip(self, path: Path, *, compare: ModelCompare) -> ModelRoundTrip: ...


@runtime_checkable
class BodyComparer(Protocol):
    """A model writer that can write component bodies on request (change c0121). ``body_differences``
    gives the differences of the kind ``body`` between ``model``, the model a build stored, and
    ``reading``, the model of the documents it wrote, each a ``Change`` whose path starts with ``/body/``,
    and the evidence of that comparison.
    The stored model holds exactly the bodies that were written, so the caller compares bodies exactly
    when it holds one; the kind is no part of ``written_scope()``."""

    def body_differences(self, model: Design, reading: Design) -> tuple[tuple[Change, ...], Evidence]: ...


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
    "NIL_UUID",
    "Backend",
    "BackendOperation",
    "BoardFrame",
    "BoardPad",
    "BodyComparer",
    "CanaryState",
    "CapabilityReport",
    "Change",
    "ChangeKind",
    "ContainerLevel",
    "ContainerRoundTrip",
    "DesignRules",
    "ExclusionSource",
    "StoredExclusion",
    "DesignRulesSource",
    "DiffReport",
    "Document",
    "DocumentParity",
    "DocumentRole",
    "DocumentSet",
    "DocumentValidator",
    "Downgrade",
    "DrcItem",
    "DrcLimits",
    "DrcOutcome",
    "DrcReport",
    "DrcViolation",
    "ErcItem",
    "ErcOracle",
    "ErcOutcome",
    "ErcReport",
    "ErcRt2Outcome",
    "ErcViolation",
    "FillOracle",
    "FillOutcome",
    "LengthFacts",
    "LengthSource",
    "LimitedOracle",
    "MATRIX_OPERATIONS",
    "MatrixRow",
    "ModelCompare",
    "ModelRoundTrip",
    "ModelWriter",
    "ModelScope",
    "NetLength",
    "NetlistOracle",
    "NetlistOutcome",
    "Oracle",
    "PadAssignment",
    "PadCopper",
    "PadNetList",
    "ParityInputs",
    "PlacedExtent",
    "PlotDimension",
    "PlotItem",
    "PlotOutcome",
    "PlotTable",
    "PlotText",
    "PlotView",
    "Plotter",
    "ProjectRead",
    "ProjectSet",
    "ReadResult",
    "RoundTrip",
    "RoundTripOracle",
    "SchematicNetlistOracle",
    "SchematicSide",
    "SideComponent",
    "SideOutcome",
    "Rt2Outcome",
    "SkipReason",
    "SkippedFile",
    "UNCONNECTED_ITEMS",
    "Uncovered",
    "Validation",
    "Validator",
    "WriteResult",
    "ZoneFills",
]
