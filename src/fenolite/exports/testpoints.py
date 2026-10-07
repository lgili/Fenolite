# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The test-point report of a board: its test points with net, position and access, its fiducials, its
non-plated holes, and which nets a probe reaches (capability assembly-test-features; user guide
``docs/assembly.md``, "Test points").

A test point is a pad that carries the mark ``test_point`` (``Pad.fab_property``), and a fiducial is a
footprint with a pad marked ``fiducial_global`` or ``fiducial_local``: the report reads marks, never
footprint names, so a board whose test points are unmarked library parts shows none. A tooling hole is a
non-plated hole of a footprint whose library name starts with ``TOOLING_PREFIX``.

Positions are in the board frame, which is the KiCad file frame (X to the right, Y down, integer
nanometres). Distances are compared on squares of integers; no float is used. Fenolite ships no target:
coverage, pitch and fiducial counts are judged only against the values the caller passes.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.outline import BoardOutline
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, format_length
from fenolite.exports import placement
from fenolite.exports.assembly import PlacementTemplate, natural_key
from fenolite.exports.assembly import format_length as template_length
from fenolite.exports.codes import issue
from fenolite.model.board import FootprintInstance, Pad, PadShape, Side
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-TESTPOINT-D356", "H-K-PAD-FABPROP"))
"""``INFERRED`` until both rows are ``KICAD-VERIFIED (9.0.x, 10.0.x)`` in ``docs/hypotheses.md``: the
rows hold on 10.0.6 (recorded probes), and the 9.0.9 run is still to be recorded."""
TOOLING_PREFIX = "Fenolite_Assembly:ToolingHole_"
"""The library name that marks a tooling hole: KiCad has no pad mark for one."""
TEST_POINT = "test_point"
FIDUCIAL_SCOPES = {"fiducial_global": "global", "fiducial_local": "local"}
CSV_HEADER: tuple[str, ...] = (
    "kind", "ref", "pad", "net", "x", "y", "side", "access", "width", "height", "drill",
)  # fmt: skip
"""The fixed columns of the CSV file of ``fenolite testpoints --out``."""

Access = Literal["top", "bottom", "both", "none"]
ReportSide = Literal["top", "bottom", "both"]
Scope = Literal["global", "local"]
_OPEN: tuple[tuple[Side, str, str], ...] = (("top", "F.Cu", "F.Mask"), ("bottom", "B.Cu", "B.Mask"))


@dataclass(frozen=True, slots=True)
class TestPointRow:
    """One pad marked ``test_point``. ``ref`` is the component's reference, or the footprint id when it
    has no component; ``net`` is ``""`` on no net; ``access`` names the sides where a probe reaches it."""

    __test__ = False  # not a pytest class

    ref: str
    path: str
    pad: str
    net: str
    position: Point
    side: Side
    access: Access
    shape: PadShape
    size: Size
    drill: Nm | None


@dataclass(frozen=True, slots=True)
class FiducialRow:
    """One footprint with a fiducial pad: the position and size of its first such pad."""

    ref: str
    path: str
    position: Point
    side: Side
    scope: Scope
    size: Size


@dataclass(frozen=True, slots=True)
class HoleRow:
    """One non-plated hole: its centre, its drill, the slot length or ``None``, and whether its footprint
    is a tooling hole."""

    ref: str
    path: str
    position: Point
    drill: Nm | None
    length: Nm | None
    tooling: bool


@dataclass(frozen=True, slots=True)
class Coverage:
    """How many nets with two pads or more hold a test point that ``side`` reaches."""

    side: ReportSide
    eligible: int
    covered: int
    uncovered: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Report:
    """The rows of one board for one side, in natural order of the reference, then of the pad number."""

    side: ReportSide
    test_points: tuple[TestPointRow, ...]
    fiducials: tuple[FiducialRow, ...]
    holes: tuple[HoleRow, ...]
    coverage: Coverage
    marked: int = 0
    """The pads of the whole board that carry the test-point mark, whatever ``side`` is."""


def access_of(layers: Iterable[str]) -> Access:
    """The sides where a pad with ``layers`` has both its copper layer and its mask layer: a probe reaches
    the pad only there (IPC-D-356's side code less its mask code, ``H-K-TESTPOINT-D356``)."""
    held = set(layers)
    found: list[Side] = [side for side, copper, mask in _OPEN if copper in held and mask in held]
    if len(found) == 2:
        return "both"
    return found[0] if found else "none"


def reaches(access: Access, side: ReportSide) -> bool:
    """True when a probe on ``side`` reaches a pad with ``access``; ``both`` asks for either side."""
    if access == "none":
        return False
    return side == "both" or access in ("both", side)


def _order(ref: str, number: str = "") -> tuple[object, ...]:
    return (natural_key(ref), ref, natural_key(number), number)


def report(design: Design, pads: Sequence[BoardPad], *, side: ReportSide = "both") -> Report:
    """The report of ``design``, whose pads in the board frame are ``pads`` (the backend's ``board_pads``)."""
    board = design.board
    footprints: dict[str, FootprintInstance] = {}
    model: dict[str, Pad] = {}
    if board is not None:
        for footprint in board.footprints:
            footprints[footprint.id] = footprint
            for pad in footprint.pads:
                model[pad.id] = pad
    test_points: list[TestPointRow] = []
    fiducials: dict[str, FiducialRow] = {}
    holes: list[HoleRow] = []
    nets: dict[str, int] = {}
    probed: dict[str, set[Access]] = {}
    marked = 0
    for record in pads:
        pad = model.get(record.pad_id)
        if pad is None:
            continue
        ref = record.ref or record.footprint_id
        net = record.net or ""
        if net:
            nets[net] = nets.get(net, 0) + 1
        if pad.fab_property == TEST_POINT:
            marked += 1
            access = access_of(record.layers)
            if net:
                probed.setdefault(net, set()).add(access)
            if side == "both" or reaches(access, side):
                test_points.append(
                    TestPointRow(
                        ref=ref,
                        path=record.path,
                        pad=record.number,
                        net=net,
                        position=record.position,
                        side=record.side,
                        access=access,
                        shape=pad.shape,
                        size=pad.size,
                        drill=pad.drill,
                    )
                )
        scope = FIDUCIAL_SCOPES.get(pad.fab_property or "")
        if scope is not None and record.footprint_id not in fiducials and side in ("both", record.side):
            fiducials[record.footprint_id] = FiducialRow(
                ref=ref,
                path=record.path,
                position=record.position,
                side=record.side,
                scope=scope,  # type: ignore[arg-type]
                size=pad.size,
            )
        if record.kind == "np_thru_hole":
            footprint = footprints.get(record.footprint_id)
            stack = pad.padstack
            holes.append(
                HoleRow(
                    ref=ref,
                    path=record.path,
                    position=record.position,
                    drill=pad.drill if record.drill is None else record.drill,
                    length=stack.hole_length if stack is not None and stack.hole_shape == "slot" else None,
                    tooling=footprint is not None and footprint.lib_ref.startswith(TOOLING_PREFIX),
                )
            )
    eligible = sorted(name for name, count in nets.items() if count >= 2)
    uncovered = tuple(
        name for name in eligible if not any(reaches(access, side) for access in probed.get(name, ()))
    )
    return Report(
        side=side,
        test_points=tuple(sorted(test_points, key=lambda row: _order(row.ref, row.pad))),
        fiducials=tuple(sorted(fiducials.values(), key=lambda row: _order(row.ref))),
        holes=tuple(sorted(holes, key=lambda row: _order(row.ref))),
        coverage=Coverage(side, len(eligible), len(eligible) - len(uncovered), uncovered),
        marked=marked,
    )


def _shares_a_side(a: Access, b: Access) -> bool:
    return any(reaches(a, side) and reaches(b, side) for side in ("top", "bottom"))  # type: ignore[arg-type]


def too_close(a: Point, b: Point, pitch: Nm) -> bool:
    """True when the centres are closer than ``pitch``: compared exactly, on squares of integers."""
    dx, dy = a.x - b.x, a.y - b.y
    return dx * dx + dy * dy < pitch * pitch


def _name(row: TestPointRow) -> str:
    return f"{row.ref}-{row.pad}" if row.pad else row.ref


NONE_HINT = (
    "KiCad's library test points carry no mark; place test points with design.test_point(), or mark an "
    'authored pad with Footprint.pad(fab_property="test_point")'
)


def findings(
    report: Report,
    design: Design,
    *,
    min_coverage: int | None = None,
    min_pitch: Nm | None = None,
    min_fiducials: int | None = None,
) -> tuple[Issue, ...]:
    """What the report says against the caller's values. Without the three values no error is given."""
    found: list[Issue] = []
    if not report.marked:
        found.append(
            issue(
                "testpoint.none",
                "no pad of the board carries the test-point mark, so the report lists no test point",
                where="test_points",
                hint=NONE_HINT,
            )
        )
    for row in report.test_points:
        if not row.net:
            found.append(
                issue(
                    "testpoint.no-net",
                    f"test point {_name(row)} is on no net",
                    where=_name(row),
                    hint="connect the test point to the net it probes, or remove it",
                )
            )
        if row.access == "none":
            found.append(
                issue(
                    "testpoint.covered",
                    f"test point {_name(row)} has no side where its copper lies under a mask opening, "
                    "so a probe does not reach it",
                    where=_name(row),
                    hint="give the pad the mask layer of its copper side: F.Mask with F.Cu, B.Mask with B.Cu",
                )
            )
    coverage = report.coverage
    if min_coverage is not None and coverage.covered * 100 < min_coverage * coverage.eligible:
        missing = ", ".join(coverage.uncovered[:8]) + (", ..." if len(coverage.uncovered) > 8 else "")
        found.append(
            issue(
                "testpoint.coverage-low",
                f"{coverage.covered} of {coverage.eligible} nets with two pads or more hold a test point "
                f"reached from side {coverage.side}; the target is {min_coverage} %",
                where="coverage",
                hint=f"nets without a test point: {missing}",
            )
        )
    if min_pitch is not None:
        rows = report.test_points
        for i, first in enumerate(rows):
            for second in rows[i + 1 :]:
                if _shares_a_side(first.access, second.access) and too_close(
                    first.position, second.position, min_pitch
                ):
                    found.append(
                        issue(
                            "testpoint.too-close",
                            f"test points {_name(first)} and {_name(second)} are closer than "
                            f"{format_length(min_pitch)} centre to centre",
                            where=f"{_name(first)},{_name(second)}",
                            hint="move one of the two, or lower --min-pitch to the pitch of the fixture",
                        )
                    )
    if min_fiducials is not None:
        found.extend(_too_few(report, design, min_fiducials))
    return tuple(found)


def _too_few(report: Report, design: Design, minimum: int) -> list[Issue]:
    board = design.board
    footprints = () if board is None else board.footprints
    found: list[Issue] = []
    sides: tuple[Side, ...] = ("top", "bottom") if report.side == "both" else (report.side,)
    for side in sides:
        assembled = any(
            footprint.side == side
            and "smd" in footprint.attributes
            and "dnp" not in footprint.attributes
            and not placement.is_fiducial(footprint)
            for footprint in footprints
        )
        count = sum(1 for row in report.fiducials if row.side == side and row.scope == "global")
        if assembled and count < minimum:
            found.append(
                issue(
                    "fiducial.too-few",
                    f"the {side} side holds surface-mount parts and {count} global fiducial(s); "
                    f"the target is {minimum}",
                    where=side,
                    hint="add fiducials with design.fiducial(), or lower --min-fiducials",
                )
            )
    return found


def _cells(
    kind: str,
    ref: str,
    position: Point,
    origin: Point,
    template: PlacementTemplate,
    *,
    pad: str = "",
    net: str = "",
    side: Side | None = None,
    access: str = "",
    size: Size | None = None,
    drill: Nm | None = None,
) -> tuple[str, ...]:
    def length(value: Nm | None) -> str:
        return "" if value is None else template_length(value, template.units, template.decimals)

    y = position.y - origin.y
    names = {"top": template.sides.top, "bottom": template.sides.bottom}
    return (
        kind,
        ref,
        pad,
        net,
        length(position.x - origin.x),
        length(-y if template.y_axis == "up" else y),
        "" if side is None else names[side],
        access,
        length(None if size is None else size.w),
        length(None if size is None else size.h),
        length(drill),
    )


def csv_table(
    report: Report,
    template: PlacementTemplate,
    *,
    outline: BoardOutline | None = None,
    issues: list[Issue] | None = None,
) -> tuple[tuple[str, ...], ...]:
    """The rows of the CSV file under ``CSV_HEADER``: test points, then fiducials, then holes, with
    positions and sizes in the origin, Y axis, units and decimals of the template's placement table and
    sides by its side names. With ``origin = "outline"`` and no closed outline there is no row, and
    ``pnp.no-outline`` is appended to ``issues`` (or raised when ``issues`` is ``None``)."""
    origin = placement.origin_of(template, outline)
    if origin is None:
        found = placement.no_outline_issue(outline)
        if issues is None:
            raise placement.NoOutlineError(found)
        issues.append(found)
        return ()
    rows: list[tuple[str, ...]] = []
    for point in report.test_points:
        rows.append(
            _cells(
                "test_point",
                point.ref,
                point.position,
                origin,
                template,
                pad=point.pad,
                net=point.net,
                side=point.side,
                access=point.access,
                size=point.size,
                drill=point.drill,
            )  # fmt: skip
        )
    for fiducial in report.fiducials:
        rows.append(
            _cells(
                "fiducial",
                fiducial.ref,
                fiducial.position,
                origin,
                template,
                side=fiducial.side,
                size=fiducial.size,
            )  # fmt: skip
        )
    for hole in report.holes:
        kind = "tooling_hole" if hole.tooling else "hole"
        rows.append(_cells(kind, hole.ref, hole.position, origin, template, drill=hole.drill))
    return tuple(rows)


__all__ = [
    "CSV_HEADER",
    "EVIDENCE",
    "NONE_HINT",
    "TOOLING_PREFIX",
    "Coverage",
    "FiducialRow",
    "HoleRow",
    "Report",
    "TestPointRow",
    "access_of",
    "csv_table",
    "findings",
    "reaches",
    "report",
    "too_close",
]
