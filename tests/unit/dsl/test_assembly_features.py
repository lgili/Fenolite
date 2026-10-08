# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The assembly and test features of a script (capability design-dsl, "Fiducials in the DSL", "Test points
in the DSL" and "Tooling holes in the DSL"; change c0118): the outline of the clear area, and the calls
``Design.fiducial``, ``Design.test_point`` and ``Design.tooling_hole`` with their generated definitions."""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fenolite.core.coords import Point, Size
from fenolite.dsl import Design, DslError, Footprint, Net, Part, assembly, mm, placements, to_model
from fenolite.dsl.assembly import ASSEMBLY_LIBRARY, clear_outline
from fenolite.exports.testpoints import TOOLING_PREFIX
from fenolite.model.circuit import PinRef
from fenolite.model.library import FootprintDef

MM = 1_000_000


def _contains_the_circle(outline: tuple[Point, ...], centre: Point, diameter: int) -> None:
    """Every vertex is outside the circle or on it, and every edge is at a distance of at least
    ``diameter / 2`` from the centre, computed exactly."""
    radius_squared = Fraction(diameter, 2) ** 2
    for a, b in zip(outline, (*outline[1:], outline[0]), strict=True):
        assert Fraction((a.x - centre.x) ** 2 + (a.y - centre.y) ** 2) >= radius_squared
        dx, dy = b.x - a.x, b.y - a.y
        if dx == dy == 0:
            continue  # a diameter of 1 or 2 nm folds two vertices into one
        cross = dx * (centre.y - a.y) - dy * (centre.x - a.x)
        assert Fraction(cross * cross, dx * dx + dy * dy) >= radius_squared
        # the closest point of the edge's line lies on the edge: the octagon is convex around the centre
        along = dx * (centre.x - a.x) + dy * (centre.y - a.y)
        assert 0 <= along <= dx * dx + dy * dy


@given(
    diameter=st.integers(1, 10 * MM),
    x=st.integers(-(10**9), 10**9),
    y=st.integers(-(10**9), 10**9),
)
def test_outline_contains_the_circle(diameter: int, x: int, y: int) -> None:
    outline = clear_outline(x, y, diameter)
    assert len(outline) == 8 and all(type(p.x) is int and type(p.y) is int for p in outline)
    _contains_the_circle(outline, Point(x, y), diameter)


@pytest.mark.parametrize("diameter", [1, 2, 3, 4, 5, 999, MM, 2_200_000, 3_000_001, 10 * MM])
def test_outline_of_small_and_round_diameters(diameter: int) -> None:
    _contains_the_circle(clear_outline(7, -3, diameter), Point(7, -3), diameter)


def test_outline_of_three_millimetres() -> None:
    """Apothem 1.5 mm; the corner offset is ``⌈√2 × 1.5 mm⌉ − 1.5 mm``, rounded up to the nanometre."""
    outline = clear_outline(5 * MM, 5 * MM, 3 * MM)
    a, b = 1_500_000, 621_321
    assert outline[0] == Point(5 * MM + a, 5 * MM - b) and outline[1] == Point(5 * MM + a, 5 * MM + b)
    assert outline[-1] == Point(5 * MM + b, 5 * MM - a)
    assert {abs(p.x - 5 * MM) for p in outline} == {a, b} == {abs(p.y - 5 * MM) for p in outline}
    assert (a + b) ** 2 >= 2 * a * a > (a + b - 1) ** 2


def test_outline_is_at_most_about_eight_percent_wider() -> None:
    for diameter in (MM, 3 * MM, 10 * MM):
        outline = clear_outline(0, 0, diameter)
        furthest = max(Fraction(p.x * p.x + p.y * p.y) for p in outline)
        assert furthest <= (Fraction(diameter, 2) * Fraction(1083, 1000)) ** 2


@pytest.mark.parametrize("diameter", [0, -1, 1.5, True, "3mm"])
def test_outline_refuses_other_diameters(diameter: object) -> None:
    with pytest.raises(ValueError, match="diameter"):
        clear_outline(0, 0, diameter)  # type: ignore[arg-type]


def test_library_name() -> None:
    assert ASSEMBLY_LIBRARY == "Fenolite_Assembly"
    assert TOOLING_PREFIX == f"{ASSEMBLY_LIBRARY}:ToolingHole_"


def test_the_script_calls_stand_on_their_prerequisites() -> None:
    """``fiducial()``, ``test_point()`` and ``tooling_hole()`` are built on ``Design.rule_area`` (c0103) and
    on the generated definitions of ``Design.hole`` (c0102)."""
    for name in ("rule_area", "hole", "fiducial", "test_point", "tooling_hole"):
        assert callable(getattr(Design, name))


# -- the three calls


def _board() -> Design:
    design = Design("features")
    design.board(mm(50), mm(30))
    return design


def _placed(design: Design, ref: str) -> tuple[Point, int, str, bool]:
    found = placements(design)[ref]
    return found.at, found.rotation, found.side, found.locked


def _definition(design: Design, part: Part) -> FootprintDef:
    assert part.footprint is not None
    return design.footprints[part.footprint].definition


def _state(design: Design) -> tuple[object, ...]:
    return (
        tuple(design.parts),
        tuple(design.footprints),
        tuple(design.symbols),
        tuple(design.rule_areas),
        tuple(design.nets),
    )


def test_a_global_fiducial() -> None:
    """Scenario "A global fiducial"."""
    d = _board()
    part = d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))
    assert part.lib_id == "Fenolite_Assembly:Fiducial"
    assert part.footprint == "Fenolite_Assembly:Fiducial_1mm_Mask2mm" and part.value == "Fiducial_1mm_Mask2mm"
    assert _placed(d, "FID1") == (Point(103 * MM, 103 * MM), 0, "top", True)
    definition = _definition(d, part)
    copper, aperture = definition.pads
    assert (copper.number, copper.kind, copper.shape) == ("", "smd", "circle")
    assert copper.size == Size(MM, MM) and copper.layers == ("F.Cu", "F.Mask")
    assert copper.fab_property == "fiducial_global" and copper.position == Point(0, 0)
    assert (aperture.number, aperture.kind, aperture.shape) == ("", "smd", "circle")
    assert aperture.size == Size(2 * MM, 2 * MM) and aperture.layers == ("F.Mask",)
    assert aperture.fab_property is None and copper.id != aperture.id
    assert definition.kind == "smd" and definition.flags == ("exclude_from_bom",)
    (yard,) = definition.graphics
    assert (yard.kind, yard.layer, yard.width) == ("circle", "F.CrtYd", 50_000)
    assert yard.points == (Point(0, 0), Point(MM, 0))
    symbol = d.symbols["Fenolite_Assembly:Fiducial"].definition  # type: ignore[attr-defined]
    assert symbol.pins == () and symbol.reference == "FID" and not symbol.in_bom and symbol.on_board
    area = d.rule_areas["clear_FID1"]
    assert area.layers == ("F.Cu",) and area.forbid == ("tracks", "vias", "pours")
    assert area.outline == (
        (4_000_000, 2_585_786), (4_000_000, 3_414_214), (3_414_214, 4_000_000), (2_585_786, 4_000_000),
        (2_000_000, 3_414_214), (2_000_000, 2_585_786), (2_585_786, 2_000_000), (3_414_214, 2_000_000),
    )  # fmt: skip


def test_a_local_fiducial_on_the_bottom() -> None:
    """Scenario "A local fiducial on the bottom"."""
    d = _board()
    part = d.fiducial(
        "FID4", mm(20), mm(10), copper=mm(0.5), mask=mm(1.5), clear=mm(3), side="bottom", local=True
    )
    assert part.footprint == "Fenolite_Assembly:Fiducial_Local_0.5mm_Mask1.5mm_Clear3mm"
    definition = _definition(d, part)
    assert definition.pads[0].fab_property == "fiducial_local"
    (yard,) = definition.graphics
    assert yard.points == (Point(0, 0), Point(1_500_000, 0))
    assert _placed(d, "FID4")[2:] == ("bottom", True)
    assert d.rule_areas["clear_FID4"].layers == ("B.Cu",)


def test_refused_fiducials() -> None:
    """Scenario "Refused fiducials"."""
    d = _board()
    d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))
    before = _state(d)
    for kwargs, named in (
        ({"copper": mm(0), "mask": mm(1)}, "copper"),
        ({"copper": mm(1), "mask": mm(1)}, "mask"),
        ({"copper": mm(1), "mask": mm(2), "clear": mm(1.5)}, "clear"),
        ({"copper": mm(1), "mask": mm(2), "side": "left"}, "side"),
        ({"copper": mm(1), "mask": mm(2), "local": 1}, "local"),
    ):
        with pytest.raises(DslError, match=named):
            d.fiducial("FID2", mm(9), mm(9), **kwargs)  # type: ignore[arg-type]
    with pytest.raises(DslError, match="FID1"):
        d.fiducial("FID1", mm(9), mm(9), copper=mm(1), mask=mm(2))
    assert _state(d) == before
    assert [p for p in d.parts if p.startswith("FID")] == ["FID1"] and list(d.rule_areas) == ["clear_FID1"]


def test_a_feature_needs_the_board_first() -> None:
    d = Design("early")
    with pytest.raises(DslError, match=r"fiducial\(\): call board\(\) first"):
        d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))
    with pytest.raises(DslError, match=r"test_point\(\): call board\(\) first"):
        d.test_point("TP1", Net("A"), mm(3), mm(3), size=mm(1))
    with pytest.raises(DslError, match=r"tooling_hole\(\): call board\(\) first"):
        d.tooling_hole("TH1", mm(3), mm(3), drill=mm(3))
    assert _state(d) == ((), (), (), (), ())


def test_a_taken_area_name_records_nothing() -> None:
    d = _board()
    d.rule_area("clear_FID1", [(mm(0), mm(0)), (mm(1), mm(0)), (mm(1), mm(1))])
    before = _state(d)
    with pytest.raises(DslError, match="clear_FID1"):
        d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))
    assert _state(d) == before


def test_one_definition_per_lib_id() -> None:
    """Each definition is registered once per lib id; another definition under one of them is refused."""
    d = _board()
    d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))
    d.fiducial("FID2", mm(47), mm(27), copper=mm(1), mask=mm(2), side="bottom")
    assert list(d.footprints) == ["Fenolite_Assembly:Fiducial_1mm_Mask2mm"]
    assert list(d.symbols) == ["Fenolite_Assembly:Fiducial"]
    other = Footprint("Fenolite_Assembly", "TestPoint_Pad_D1mm", kind="smd")
    other.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)))
    d.add_footprint(other)
    before = _state(d)
    with pytest.raises(DslError, match="Fenolite_Assembly:TestPoint_Pad_D1mm"):
        d.test_point("TP1", Net("A"), mm(5), mm(5), size=mm(1))
    assert _state(d) == before
    with pytest.raises(DslError, match="registered twice"):
        d.add_footprint(assembly.fiducial_footprint(MM, 2 * MM, 2 * MM, local=False))


def test_an_smd_test_point_on_a_net() -> None:
    """Scenario "An SMD test point on a net"."""
    d = _board()
    led_a = Net("LED_A")
    d.add(led_a)
    tp = d.test_point("TP1", led_a, mm(30), mm(12), size=mm(1.5))
    assert tp.lib_id == "Fenolite_Assembly:TestPoint"
    assert tp.footprint == "Fenolite_Assembly:TestPoint_Pad_D1.5mm" and tp.value == "TestPoint_Pad_D1.5mm"
    definition = _definition(d, tp)
    (pad,) = definition.pads
    assert (pad.number, pad.kind, pad.shape, pad.size) == ("1", "smd", "circle", Size(1_500_000, 1_500_000))
    assert pad.layers == ("F.Cu", "F.Mask") and pad.fab_property == "test_point" and pad.drill is None
    assert definition.kind == "unspecified"
    assert definition.flags == ("exclude_from_pos_files", "exclude_from_bom")
    (yard,) = definition.graphics
    assert (yard.kind, yard.layer, yard.points) == ("circle", "F.CrtYd", (Point(0, 0), Point(750_000, 0)))
    assert tp.connections == {"1": led_a} and d.nets["LED_A"] is led_a
    assert _placed(d, "TP1") == (Point(130 * MM, 112 * MM), 0, "top", False)
    symbol = d.symbols["Fenolite_Assembly:TestPoint"].definition  # type: ignore[attr-defined]
    assert [(p.number, p.etype) for p in symbol.pins] == [("1", "passive")]
    assert symbol.reference == "TP" and not symbol.in_bom and symbol.on_board
    model = to_model(d)
    (net,) = [n for n in model.circuit.nets if n.name == "LED_A"]
    (component,) = [c for c in model.circuit.components if c.ref == "TP1"]
    assert PinRef(component.id, "1") in net.members


def test_a_through_hole_test_point_on_the_bottom() -> None:
    """Scenario "A through-hole test point on the bottom"."""
    d = _board()
    gnd = Net("GND")
    tp = d.test_point(
        "TP2", gnd, mm(5), mm(25), size=mm(2), shape="rect", drill=mm(1), courtyard=mm(3), side="bottom"
    )
    assert tp.footprint == "Fenolite_Assembly:TestPoint_THTPad_2x2mm_Drill1mm_Courtyard_3mm"
    definition = _definition(d, tp)
    (pad,) = definition.pads
    assert (pad.number, pad.kind, pad.shape, pad.drill) == ("1", "thru_hole", "rect", MM)
    assert pad.layers == ("*.Cu", "*.Mask") and pad.fab_property == "test_point"
    corners = (Point(-1_500_000, -1_500_000), Point(1_500_000, 1_500_000))
    assert [(g.kind, g.layer, g.points) for g in definition.graphics] == [
        ("rect", "F.CrtYd", corners),
        ("rect", "B.CrtYd", corners),
    ]
    assert _placed(d, "TP2")[2:] == ("bottom", False)
    d.test_point("TP3", gnd, mm(9), mm(25), size=mm(2), shape="rect", locked=True)
    assert d.parts["TP3"].footprint == "Fenolite_Assembly:TestPoint_Pad_2x2mm"
    assert _placed(d, "TP3")[3] is True


def test_refused_test_points() -> None:
    """Scenario "Refused test points"."""
    d = _board()
    gnd = Net("GND")
    d.add(gnd)
    before = _state(d)
    for net, kwargs, named in (
        ("GND", {"size": mm(1)}, "net"),
        (gnd, {"size": mm(0)}, "size"),
        (gnd, {"size": mm(1), "shape": "oval"}, "shape"),
        (gnd, {"size": mm(1), "drill": mm(1)}, "drill"),
        (gnd, {"size": mm(1), "courtyard": mm(0.5)}, "courtyard"),
        (gnd, {"size": mm(1), "side": "left"}, "side"),
        (gnd, {"size": mm(1), "locked": "yes"}, "locked"),
        (Net("GND"), {"size": mm(1)}, "GND"),
    ):
        with pytest.raises(DslError, match=named):
            d.test_point("TP3", net, mm(1), mm(1), **kwargs)  # type: ignore[arg-type]
    assert _state(d) == before and "TP3" not in d.parts


def test_a_tooling_hole_with_a_clear_area() -> None:
    """Scenario "A tooling hole with a clear area"."""
    d = _board()
    th = d.tooling_hole("TH1", mm(46), mm(4), drill=mm(3), clear=mm(5))
    assert th.lib_id == "Fenolite_Holes:Hole"
    assert th.footprint == "Fenolite_Assembly:ToolingHole_3mm_Clear5mm"
    assert th.footprint.startswith(TOOLING_PREFIX)
    definition = _definition(d, th)
    (pad,) = definition.pads
    assert (pad.number, pad.kind, pad.shape, pad.size, pad.drill) == (
        "", "np_thru_hole", "circle", Size(3 * MM, 3 * MM), 3 * MM,
    )  # fmt: skip
    assert pad.layers == ("*.Cu", "*.Mask") and pad.fab_property is None
    assert [(g.kind, g.layer, g.points) for g in definition.graphics] == [
        ("circle", "F.CrtYd", (Point(0, 0), Point(2_500_000, 0))),
        ("circle", "B.CrtYd", (Point(0, 0), Point(2_500_000, 0))),
    ]
    assert definition.flags == ("exclude_from_pos_files", "exclude_from_bom")
    assert _placed(d, "TH1") == (Point(146 * MM, 104 * MM), 0, "top", True)
    area = d.rule_areas["clear_TH1"]
    # ``layers=None`` asks for every copper layer; the rule area records them by name (c0103)
    assert area.layers == d.copper_layers and area.forbid == ("tracks", "vias", "pours")
    assert area.outline == tuple((p.x, p.y) for p in clear_outline(46 * MM, 4 * MM, 5 * MM))
    assert d.symbols["Fenolite_Holes:Hole"].definition.pins == ()  # type: ignore[attr-defined]


def test_a_tooling_hole_without_a_clear_area() -> None:
    """Scenario "A tooling hole without a clear area"; it shares the symbol of ``hole()``."""
    d = _board()
    d.hole("H1", mm(4), mm(4), drill=mm(3.2))
    th = d.tooling_hole("TH2", mm(4), mm(26), drill=mm(3))
    assert th.footprint == "Fenolite_Assembly:ToolingHole_3mm"
    yards = [g.points for g in _definition(d, th).graphics]
    assert yards == [(Point(0, 0), Point(1_500_000, 0))] * 2
    assert "clear_TH2" not in d.rule_areas and list(d.symbols) == ["Fenolite_Holes:Hole"]


def test_refused_tooling_holes() -> None:
    """Scenario "Refused tooling holes"."""
    d = _board()
    before = _state(d)
    for kwargs, named in (({"drill": mm(0)}, "drill"), ({"drill": mm(3), "clear": mm(2)}, "clear")):
        with pytest.raises(DslError, match=named):
            d.tooling_hole("TH3", mm(1), mm(1), **kwargs)  # type: ignore[arg-type]
    assert _state(d) == before


def test_a_fiducial_and_a_tooling_hole_refuse_a_second_placement() -> None:
    """Their keep-outs stay where the script drew them: the parts are placed and locked by the call."""
    d = _board()
    for part in (
        d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2)),
        d.tooling_hole("TH1", mm(46), mm(4), drill=mm(3)),
    ):
        with pytest.raises(DslError, match="already placed"):
            part.place(mm(10), mm(10))
