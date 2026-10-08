# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The test-point report (capability assembly-test-features: "Test-point report rows", "Test-point
coverage", "Assembly and test findings"; change c0118). Hermetic: designs are built through the model API.
Every part, net, position and size here is made up for these tests."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from hypothesis import given
from hypothesis import strategies as st

from fenolite.backends.kicad import frame
from fenolite.core.coords import Point, Size
from fenolite.core.evidence import Level
from fenolite.core.ids import derived_id
from fenolite.exports import testpoints
from fenolite.exports.assembly import DEFAULT, PlacementTemplate, SideNames
from fenolite.exports.codes import ISSUE_CODES
from fenolite.exports.testpoints import access_of, csv_table, findings, report, too_close
from fenolite.model.board import Board, FootprintInstance, Pad, PadFabProperty, Padstack, Side
from fenolite.model.circuit import Circuit, Component, Net
from fenolite.model.design import Design, DesignHeader

MM = 1_000_000
TOP, BOTTOM = ("F.Cu", "F.Mask"), ("B.Cu", "B.Mask")
THROUGH = ("F.Cu", "B.Cu", "F.Mask", "B.Mask")


def _id(prefix: str, name: str) -> str:
    return derived_id(prefix, "test", name)


@dataclass(frozen=True)
class P:
    """One pad of a part: its number, net name, layers and mark, at an offset in millimetres."""

    number: str = "1"
    net: str = ""
    layers: tuple[str, ...] = TOP
    mark: PadFabProperty | None = None
    kind: str = "smd"
    drill: int | None = None
    dx: int = 0
    size: int = MM
    slot: int | None = None


@dataclass(frozen=True)
class Part:
    ref: str
    pads: tuple[P, ...] = (P(),)
    x: int = 0
    y: int = 0
    side: Side = "top"
    lib: str = "Local:Part"
    attributes: tuple[str, ...] = ("smd",)
    component: bool = True
    at: Point | None = None
    """The position in nanometres, when millimetres are too coarse."""


def design_of(*parts: Part) -> Design:
    names = sorted({pad.net for part in parts for pad in part.pads if pad.net})
    nets = {name: Net(id=_id("net", name), name=name) for name in names}
    components = tuple(
        Component(id=_id("cmp", part.ref), ref=part.ref, value="", lib_footprint_ref=part.lib)
        for part in parts
        if part.component
    )
    footprints = tuple(
        FootprintInstance(
            id=_id("fp", part.ref),
            component_id=_id("cmp", part.ref) if part.component else "",
            lib_ref=part.lib,
            position=part.at or Point(part.x * MM, part.y * MM),
            side=part.side,
            attributes=part.attributes,  # type: ignore[arg-type]
            pads=tuple(
                Pad(
                    id=_id("pad", f"{part.ref}:{k}"),
                    number=pad.number,
                    shape="circle",
                    size=Size(pad.size, pad.size),
                    position=Point(pad.dx * MM, 0),
                    kind=pad.kind,  # type: ignore[arg-type]
                    drill=pad.drill,
                    layers=pad.layers,
                    net_id=nets[pad.net].id if pad.net else None,
                    padstack=(
                        Padstack(id=_id("pst", f"{part.ref}:{k}"), hole_shape="slot", hole_length=pad.slot)
                        if pad.slot is not None
                        else None
                    ),
                    fab_property=pad.mark,
                )
                for k, pad in enumerate(part.pads)
            ),
        )
        for part in parts
    )
    header = DesignHeader(id=_id("dsn", "d"), name="tp", schema_version="0", fenolite_version="0")
    board = Board(id=_id("brd", "b"), footprints=footprints)
    return Design(
        header=header, circuit=Circuit(components=components, nets=tuple(nets.values())), board=board
    )


def run(design: Design, side: str = "both") -> testpoints.Report:
    return report(design, frame.board_pads(design), side=side)  # type: ignore[arg-type]


def tp(ref: str, net: str = "", layers: tuple[str, ...] = TOP, **more: object) -> Part:
    drill = 500_000 if layers == THROUGH else None
    kind = "thru_hole" if layers == THROUGH else "smd"
    pad = P(net=net, layers=layers, mark="test_point", kind=kind, drill=drill)
    return Part(ref, (pad,), attributes=("exclude_from_pos_files", "exclude_from_bom"), **more)  # type: ignore[arg-type]


def fid(ref: str, side: Side = "top", mark: PadFabProperty = "fiducial_global", **more: object) -> Part:
    layers = TOP if side == "top" else BOTTOM
    pads = (P(number="", layers=layers, mark=mark), P(number="", layers=(layers[1],), size=2 * MM))
    return Part(ref, pads, side=side, attributes=("smd", "exclude_from_bom"), **more)  # type: ignore[arg-type]


FOUR = (
    tp("TP1", "A", TOP, x=10, y=10),
    tp("TP2", "B", BOTTOM, x=20, y=10, side="bottom"),
    tp("TP3", "C", THROUGH, x=30, y=10),
    tp("TP4", "D", ("F.Cu",), x=40, y=10),
)


# --- rows -----------------------------------------------------------------------------------------


def test_access_from_layers() -> None:
    """Scenario "Access from layers"."""
    found = run(design_of(*FOUR))
    assert [row.access for row in found.test_points] == ["top", "bottom", "both", "none"]
    first = found.test_points[0]
    assert (first.ref, first.pad, first.net, first.side) == ("TP1", "1", "A", "top")
    assert (first.position, first.shape, first.size, first.drill) == (
        Point(10 * MM, 10 * MM), "circle", Size(MM, MM), None,
    )  # fmt: skip
    assert found.test_points[2].drill == 500_000 and found.marked == 4


def test_access_rule() -> None:
    assert access_of(()) == "none" and access_of(("F.Mask",)) == "none"
    assert access_of(("F.Cu", "B.Mask")) == "none"  # the opening is on the other side
    assert access_of(("F.Cu", "B.Cu", "F.Mask")) == "top"
    assert access_of(("F.Cu", "In1.Cu", "B.Cu", "F.Mask", "B.Mask", "F.Paste")) == "both"


def test_tooling_holes_among_holes() -> None:
    """Scenario "Tooling holes among holes"; a slot gives its length."""
    hole = P(number="", layers=("F.Cu", "B.Cu", "F.Mask", "B.Mask"), kind="np_thru_hole")
    design = design_of(
        Part("TH1", (P(**{**hole.__dict__, "drill": 3 * MM, "size": 3 * MM}),), x=4, y=4,
             lib="Fenolite_Assembly:ToolingHole_3mm", attributes=("exclude_from_pos_files",)),
        Part("H1", (P(**{**hole.__dict__, "drill": 3_200_000, "size": 3_200_000}),), x=46, y=4,
             lib="Fenolite_Holes:NPTH_3.2mm", attributes=("exclude_from_pos_files",)),
        Part("H2", (P(**{**hole.__dict__, "drill": MM, "size": 3 * MM, "slot": 3 * MM}),), x=25, y=4,
             lib="Local:Slot", component=False),
        Part("J1", (P(net="A", layers=THROUGH, kind="thru_hole", drill=MM, size=2 * MM),)),
    )  # fmt: skip
    found = run(design)
    by_ref = {row.ref: row for row in found.holes}
    assert len(found.holes) == 3 and found.test_points == () and found.fiducials == ()
    assert (by_ref["TH1"].tooling, by_ref["TH1"].drill, by_ref["TH1"].length) == (True, 3 * MM, None)
    assert (by_ref["H1"].tooling, by_ref["H1"].drill) == (False, 3_200_000)
    assert by_ref["TH1"].position == Point(4 * MM, 4 * MM)
    nameless = next(row for row in found.holes if row.ref not in ("TH1", "H1"))
    assert nameless.ref == _id("fp", "H2") and nameless.path == "" and nameless.length == 3 * MM
    assert testpoints.TOOLING_PREFIX == "Fenolite_Assembly:ToolingHole_"


def test_one_side() -> None:
    """Scenario "One side": holes are always listed."""
    hole = Part("H1", (P(number="", kind="np_thru_hole", drill=MM, layers=THROUGH),))
    design = design_of(*FOUR, fid("FID1", x=3, y=3), fid("FID2", "bottom", x=47, y=27), hole)
    bottom = run(design, "bottom")
    assert [row.ref for row in bottom.test_points] == ["TP2", "TP3"]
    assert [row.ref for row in bottom.fiducials] == ["FID2"] and len(bottom.holes) == 1
    top = run(design, "top")
    assert [row.ref for row in top.test_points] == ["TP1", "TP3"]
    assert [row.ref for row in top.fiducials] == ["FID1"] and top.marked == 4
    both = run(design)
    assert [row.ref for row in both.fiducials] == ["FID1", "FID2"]


def test_fiducial_rows() -> None:
    design = design_of(fid("FID2", "bottom", "fiducial_local", x=5, y=6), fid("FID1", x=3, y=3))
    first, second = run(design).fiducials
    assert (first.ref, first.side, first.scope, first.size) == ("FID1", "top", "global", Size(MM, MM))
    assert (second.ref, second.side, second.scope) == ("FID2", "bottom", "local")
    assert second.position == Point(5 * MM, 6 * MM)  # the first marked pad, not the mask aperture


def test_natural_order() -> None:
    design = design_of(
        tp("TP10", "A"),
        tp("TP2", "B"),
        Part("J1", (P("10", "C", mark="test_point"), P("2", "D", mark="test_point", dx=2))),
    )
    assert [(row.ref, row.pad) for row in run(design).test_points] == [
        ("J1", "2"), ("J1", "10"), ("TP2", "1"), ("TP10", "1"),
    ]  # fmt: skip


def test_an_empty_design() -> None:
    header = DesignHeader(id=_id("dsn", "d"), name="tp", schema_version="0", fenolite_version="0")
    found = report(Design(header=header, circuit=Circuit()), ())
    assert (found.test_points, found.fiducials, found.holes) == ((), (), ())
    assert found.coverage == testpoints.Coverage("both", 0, 0, ())


# --- coverage -------------------------------------------------------------------------------------


def test_coverage_per_side() -> None:
    """Scenario "Coverage per side"."""
    design = design_of(
        Part("U1", (P("1", "A"), P("2", "A", dx=1), P("3", "B", dx=2), P("4", "B", dx=3), P("5", "B", dx=4),
                    P("6", "C", dx=5), P("7", "D", dx=6), P("8", "", dx=7), P("9", "", dx=8))),
        tp("TP1", "A", TOP, y=5),
        tp("TP2", "C", BOTTOM, y=6, side="bottom"),
    )  # fmt: skip
    both = run(design).coverage
    assert (both.side, both.eligible, both.covered, both.uncovered) == ("both", 3, 2, ("B",))
    top = run(design, "top").coverage
    assert (top.eligible, top.covered, top.uncovered) == (3, 1, ("B", "C"))
    bottom = run(design, "bottom").coverage
    assert (bottom.covered, bottom.uncovered) == (1, ("A", "B"))


def test_a_covered_test_point_covers_no_net() -> None:
    design = design_of(Part("R1", (P("1", "A"),)), tp("TP1", "A", ("F.Cu",)), tp("TP2", "B", THROUGH))
    coverage = run(design).coverage
    assert (coverage.eligible, coverage.covered, coverage.uncovered) == (1, 0, ("A",))


# --- findings -------------------------------------------------------------------------------------


def test_the_codes() -> None:
    mine = {
        code: ISSUE_CODES[code] for code in ISSUE_CODES if code.split(".")[0] in ("testpoint", "fiducial")
    }
    assert mine == {
        "testpoint.none": "info",
        "testpoint.no-net": "warning",
        "testpoint.covered": "warning",
        "testpoint.coverage-low": "error",
        "testpoint.too-close": "error",
        "fiducial.too-few": "error",
    }  # fmt: skip
    assert testpoints.EVIDENCE.level is Level.KICAD_VERIFIED  # c0118 task 8.2
    assert testpoints.EVIDENCE.hypotheses == ("H-K-TESTPOINT-D356", "H-K-PAD-FABPROP")


def test_no_values_no_errors() -> None:
    """Scenario "No values, no errors"."""
    design = design_of(
        Part("R1", (P("1", "A"), P("2", "B", dx=2))), tp("TP1", "A"), tp("TP2", "B", ("F.Cu",))
    )
    found = findings(run(design), design)
    assert [(i.code, i.severity, i.where) for i in found] == [("testpoint.covered", "warning", "TP2-1")]
    loose = design_of(tp("TP1"))
    assert [(i.code, i.where) for i in findings(run(loose), loose)] == [("testpoint.no-net", "TP1-1")]


def _spaced() -> Design:
    """Four eligible nets, three with a test point; TP1 and TP2 are 1.9 mm apart; one global fiducial on a
    top side that holds a surface-mount part."""
    return design_of(
        Part("U1", tuple(P(str(k), net, dx=k) for k, net in enumerate("AABBCCDD", start=1)), y=20),
        tp("TP1", "A", x=10, y=10),
        tp("TP2", "B", at=Point(11_900_000, 10 * MM)),
        tp("TP3", "C", x=30, y=10),
        fid("FID1", x=3, y=3),
    )


def test_targets_missed() -> None:
    """Scenario "Targets missed"."""
    design = _spaced()
    found_report = run(design)
    assert (found_report.coverage.eligible, found_report.coverage.covered) == (4, 3)
    found = findings(found_report, design, min_coverage=80, min_pitch=2 * MM, min_fiducials=3)
    assert [(i.code, i.severity) for i in found] == [
        ("testpoint.coverage-low", "error"),
        ("testpoint.too-close", "error"),
        ("fiducial.too-few", "error"),
    ]
    low, near, few = found
    assert "3 of 4" in low.message and "D" in low.hint
    assert "TP1-1" in near.message and "TP2-1" in near.message and near.where == "TP1-1,TP2-1"
    assert few.where == "top" and "top" in few.message
    assert findings(found_report, design, min_coverage=75, min_pitch=1_900_000, min_fiducials=1) == ()


def test_coverage_boundary() -> None:
    design = design_of(Part("U1", (P("1", "A"), P("2", "B", dx=1), P("3", "C", dx=2))), tp("TP1", "A"),
                       tp("TP2", "B"), tp("TP3", "C", ("F.Cu",)))  # fmt: skip
    found = run(design)
    assert (found.coverage.eligible, found.coverage.covered) == (3, 2)

    def codes(value: int) -> list[str]:
        return [i.code for i in findings(found, design, min_coverage=value) if i.severity == "error"]

    assert codes(66) == [] and codes(67) == ["testpoint.coverage-low"] and codes(0) == []
    empty = design_of(Part("R1"))
    assert [i.code for i in findings(run(empty), empty, min_coverage=100)] == ["testpoint.none"]


def test_pitch_needs_a_shared_side() -> None:
    design = design_of(
        tp("TP1", "A", TOP, x=10, y=10),
        tp("TP2", "B", BOTTOM, x=10, y=10, side="bottom"),
        tp("TP3", "C", THROUGH, x=11, y=10),
        tp("TP4", "D", ("F.Cu",), x=10, y=10),
    )
    found = [i for i in findings(run(design), design, min_pitch=2 * MM) if i.code == "testpoint.too-close"]
    assert [i.where for i in found] == ["TP1-1,TP3-1", "TP2-1,TP3-1"]  # one issue per pair


def test_fiducials_per_side() -> None:
    def few(design: Design, side: str = "both", minimum: int = 2) -> list[str]:
        found = findings(run(design, side), design, min_fiducials=minimum)
        return [i.where for i in found if i.code == "fiducial.too-few"]

    top_only = design_of(Part("R1"), fid("FID1"), fid("FID2", "bottom"))
    assert few(top_only) == ["top"]  # the bottom side holds no part to assemble
    both = design_of(Part("R1"), Part("C1", side="bottom"), fid("FID1"), fid("FID2", x=40))
    assert few(both) == ["bottom"] and few(both, "top") == [] and few(both, "bottom") == ["bottom"]
    local = design_of(Part("R1"), fid("FID1"), fid("FID2", mark="fiducial_local", x=40))
    assert few(local) == ["top"]  # local fiducials do not count
    idle = design_of(Part("R1", attributes=("smd", "dnp")), Part("J1", attributes=("through_hole",)))
    assert few(idle) == []  # nothing to place by machine
    assert few(design_of(Part("R1")), minimum=1) == ["top"]


@given(
    ax=st.integers(-(10**9), 10**9),
    ay=st.integers(-(10**9), 10**9),
    bx=st.integers(-(10**9), 10**9),
    by=st.integers(-(10**9), 10**9),
    pitch=st.integers(1, 2 * 10**9),
)
def test_the_pitch_rule_is_exact(ax: int, ay: int, bx: int, by: int, pitch: int) -> None:
    """Against a brute-force comparison of the squared distance in ``Fraction``."""
    squared = Fraction(ax - bx) ** 2 + Fraction(ay - by) ** 2
    assert too_close(Point(ax, ay), Point(bx, by), pitch) is (squared < Fraction(pitch) ** 2)


@given(pitch=st.integers(1, 10**9), dx=st.integers(0, 10**9))
def test_the_pitch_itself_is_not_too_close(pitch: int, dx: int) -> None:
    assert too_close(Point(0, 0), Point(dx, 0), pitch) is (dx < pitch)
    assert not too_close(Point(0, 0), Point(pitch, 0), pitch)


def test_unmarked_board() -> None:
    """Scenario "Unmarked board": library test points carry no mark."""
    design = design_of(
        Part("TP1", (P(net="A"),), lib="TestPoint:TestPoint_Pad_D1.5mm"), Part("R1", (P(net="A"),))
    )
    found = findings(run(design), design)
    assert [(i.code, i.severity) for i in found] == [("testpoint.none", "info")]
    assert (
        "design.test_point()" in found[0].hint
        and "KiCad's library test points carry no mark" in found[0].hint
    )
    assert 'Footprint.pad(fab_property="test_point")' in found[0].hint


# --- the CSV --------------------------------------------------------------------------------------


def test_csv_rows() -> None:
    hole = P(number="", kind="np_thru_hole", drill=3 * MM, size=3 * MM, layers=THROUGH)
    design = design_of(
        tp("TP1", "A", THROUGH, x=10, y=20),
        fid("FID1", "bottom", x=3, y=3),
        Part("TH1", (hole,), x=46, y=4, lib="Fenolite_Assembly:ToolingHole_3mm"),
        Part("H1", (hole,), x=4, y=4, lib="Fenolite_Holes:NPTH_3mm"),
    )
    rows = csv_table(run(design), DEFAULT.placement)
    assert len(testpoints.CSV_HEADER) == 11 and all(len(row) == 11 for row in rows)
    assert rows == (
        ("test_point", "TP1", "1", "A", "10.0000", "-20.0000", "top", "both", "1.0000", "1.0000", "0.5000"),
        ("fiducial", "FID1", "", "", "3.0000", "-3.0000", "bottom", "", "1.0000", "1.0000", ""),
        ("hole", "H1", "", "", "4.0000", "-4.0000", "", "", "", "", "3.0000"),
        ("tooling_hole", "TH1", "", "", "46.0000", "-4.0000", "", "", "", "", "3.0000"),
    )
    named = PlacementTemplate(units="mil", decimals=0, y_axis="down", sides=SideNames("T", "B"))
    assert csv_table(run(design), named)[1][4:7] == ("118", "118", "B")
