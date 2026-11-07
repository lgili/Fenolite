# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pairing of one design held in two representations (change c0421; capability design-equivalence,
"Level 6 rule pairing", "Level 6 stack-up kinds and layer aliases", "Level 7 representation pairing").

Every pairing rule has its authored negative case next to it: the same pair with a real difference is still
reported. All designs are authored here from the two-layer fixture."""

from __future__ import annotations

import dataclasses
from collections.abc import Collection

from _cases import two_layer, with_footprint

from fenolite.checks.equivalence import Tolerances, compare_designs
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.geometry.bands import segment_band
from fenolite.model.base import ExtBag
from fenolite.model.board import (
    Arc,
    Board,
    FootprintField,
    FootprintInstance,
    Graphic,
    Hole,
    Keepout,
    Layer,
    LayerKind,
    Pad,
    StackKind,
    StackLayer,
    Stackup,
    Track,
)
from fenolite.model.circuit import Component, NetClass
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

MM = 1_000_000


def board(design: Design) -> Board:
    assert design.board is not None
    return design.board


def with_board(design: Design, **changes: object) -> Design:
    return dataclasses.replace(design, board=dataclasses.replace(board(design), **changes))


def kinds(
    a: Design,
    b: Design,
    *,
    level: int = 7,
    across: bool = False,
    keepout_layers: tuple[Collection[str], Collection[str]] = ((), ()),
) -> list[tuple[str, str]]:
    report = compare_designs(a, b, level=level, across=across, keepout_layers=keepout_layers)
    return sorted((d.kind, d.where) for level_result in report.levels for d in level_result.differences)


def of_kind(
    a: Design,
    b: Design,
    kind: str,
    *,
    level: int = 7,
    across: bool = False,
    keepout_layers: tuple[Collection[str], Collection[str]] = ((), ()),
) -> list[str]:
    found = kinds(a, b, level=level, across=across, keepout_layers=keepout_layers)
    return [where for held, where in found if held == kind]


# --- level 6: rules ------------------------------------------------------------------------------------


def with_rules(design: Design, *rules: Rule) -> Design:
    return dataclasses.replace(design, rules=RuleSet(id=derived_id("rst", "c0421", design.header.name),
                                                     rules=rules))  # fmt: skip


def rule(name: str, priority: int = 3, minimum: int = MM // 5) -> Rule:
    return Rule(
        id=derived_id("rul", "c0421", f"{name}-{priority}-{minimum}"),
        name=name,
        kind="clearance",
        selector_a=Selector("net", "GND"),
        min=minimum,
        priority=priority,
    )


def test_a_rule_pairs_with_the_name_a_conversion_writes_for_it() -> None:
    a = with_rules(two_layer(), rule("GND Clearance"))
    b = with_rules(two_layer(), rule("fenolite_3_gnd_clearance"))
    assert of_kind(a, b, "rule-missing", level=6) == []
    assert of_kind(a, b, "rule-field", level=6) == []


def test_a_written_name_with_another_priority_does_not_pair() -> None:
    a = with_rules(two_layer(), rule("GND Clearance"))
    b = with_rules(two_layer(), rule("fenolite_4_gnd_clearance", priority=4))
    assert of_kind(a, b, "rule-missing", level=6) == ["GND Clearance", "fenolite_4_gnd_clearance"]


def test_a_written_pair_still_reports_its_fields() -> None:
    a = with_rules(two_layer(), rule("GND Clearance"))
    b = with_rules(two_layer(), rule("fenolite_3_gnd_clearance", minimum=MM // 4))
    assert of_kind(a, b, "rule-missing", level=6) == []
    assert of_kind(a, b, "rule-field", level=6) == ["GND Clearance"]


# --- level 6: stack-up ---------------------------------------------------------------------------------


STACK: tuple[tuple[str, StackKind, int], ...] = (
    ("F.Mask", "soldermask", 10_000),
    ("F.Cu", "copper", 35_000),
    ("core", "dielectric", 1_500_000),
    ("B.Cu", "copper", 35_000),
    ("B.Mask", "soldermask", 10_000),
)


def stacked(*kinds_held: str) -> Design:
    layers = [
        StackLayer(id=derived_id("sly", "c0421", name), name=name, kind=kind, thickness=thickness)
        for name, kind, thickness in STACK
        if kind in kinds_held
    ]
    return with_board(two_layer(), stackup=Stackup(id="stk-c0421", layers=tuple(layers)))


def test_a_stackup_kind_one_backend_leaves_out_is_not_missing_across_backends() -> None:
    a, b = stacked("soldermask", "copper", "dielectric"), stacked("copper", "dielectric")
    assert of_kind(a, b, "stackup-missing", level=6, across=True) == []


def test_the_left_out_kind_is_still_missing_between_sides_of_one_backend() -> None:
    a, b = stacked("soldermask", "copper", "dielectric"), stacked("copper", "dielectric")
    assert of_kind(a, b, "stackup-missing", level=6) == ["B.Mask", "F.Mask"]


def test_a_missing_dielectric_is_missing_across_backends() -> None:
    a, b = stacked("soldermask", "copper", "dielectric"), stacked("copper")
    assert "core" in of_kind(a, b, "stackup-missing", level=6, across=True)


# --- level 6: layers -----------------------------------------------------------------------------------


def with_layer(design: Design, name: str, kind: LayerKind, user_name: str = "") -> Design:
    bag = {"kicad": ExtBag(payload=(("user_name", user_name),))} if user_name else {}
    ordinal = len(board(design).layers)
    layer = Layer(id=derived_id("lay", "c0421", name), name=name, kind=kind, ordinal=ordinal, ext=bag)
    return with_board(design, layers=(*board(design).layers, layer))


def drawn_on(design: Design, layer: str) -> Design:
    line = Graphic(id=derived_id("gfx", "c0421", layer), kind="line", layer=layer,
                   points=(Point(1 * MM, 1 * MM), Point(4 * MM, 1 * MM)), width=MM // 10)  # fmt: skip
    return with_board(design, graphics=(*board(design).graphics, line))


def test_a_layer_pairs_with_the_layer_its_user_name_names() -> None:
    a = drawn_on(with_layer(two_layer(), "Mech.1", "mechanical"), "Mech.1")
    b = drawn_on(with_layer(two_layer(), "User.1", "user", user_name="Mech.1"), "User.1")
    assert of_kind(a, b, "layer-missing") == []
    assert of_kind(a, b, "graphic-missing") == []


def test_a_user_name_naming_another_layer_does_not_pair() -> None:
    a = drawn_on(with_layer(two_layer(), "Mech.1", "mechanical"), "Mech.1")
    b = drawn_on(with_layer(two_layer(), "User.1", "user", user_name="Mech.2"), "User.1")
    assert of_kind(a, b, "layer-missing") == ["mechanical:Mech.1", "user:User.1"]
    assert len(of_kind(a, b, "graphic-missing")) == 2


def test_a_mechanical_and_a_user_layer_are_one_kind_only_across_backends() -> None:
    a = with_layer(two_layer(), "Mech.1", "mechanical")
    b = with_layer(two_layer(), "User.1", "user", user_name="Mech.1")
    assert of_kind(a, b, "layer-field", level=6, across=True) == []
    assert of_kind(a, b, "layer-field", level=6) == ["Mech.1"]


def test_an_unused_layer_on_one_side_is_no_difference_across_backends() -> None:
    a, b = two_layer(), with_layer(two_layer(), "Eco1.User", "user")
    assert of_kind(a, b, "layer-missing", level=6, across=True) == []
    assert of_kind(a, b, "layer-missing", level=6) == ["user:Eco1.User"]


def test_a_used_layer_on_one_side_is_missing_across_backends() -> None:
    a, b = two_layer(), drawn_on(with_layer(two_layer(), "Eco1.User", "user"), "Eco1.User")
    assert of_kind(a, b, "layer-missing", level=6, across=True) == ["user:Eco1.User"]


def test_a_copper_layer_on_one_side_is_missing_across_backends() -> None:
    a, b = two_layer(), with_layer(two_layer(), "In1.Cu", "copper")
    assert of_kind(a, b, "layer-missing", level=6, across=True) == ["copper:In1.Cu"]


def test_only_the_copper_order_is_compared_across_backends() -> None:
    a = two_layer()
    layers = board(a).layers
    moved = tuple(dataclasses.replace(layer, ordinal=-1) if layer.name == "Edge.Cuts" else layer
                  for layer in layers)  # fmt: skip
    b = with_board(a, layers=moved)
    assert of_kind(a, b, "layer-field", level=6, across=True) == []
    assert of_kind(a, b, "layer-field", level=6) == ["layers"]
    swapped = tuple(dataclasses.replace(layer, ordinal=1 - layer.ordinal) if layer.kind == "copper" else layer
                    for layer in layers)  # fmt: skip
    assert of_kind(a, with_board(a, layers=swapped), "layer-field", level=6, across=True) == ["layers"]


def test_a_keepout_layer_on_its_side_only_is_not_missing() -> None:
    a, b = with_layer(two_layer(), "Altium.KeepOut", "user"), two_layer()
    a = drawn_on(a, "Altium.KeepOut")
    assert of_kind(a, b, "layer-missing", level=6, keepout_layers=({"Altium.KeepOut"}, ())) == []
    assert of_kind(a, b, "layer-missing", level=6) == ["user:Altium.KeepOut"]


# --- level 6: net classes ------------------------------------------------------------------------------


def classed(design: Design, *classes: NetClass, member: str | None = None) -> Design:
    nets = design.circuit.nets
    if member is not None:
        wanted = next(c.id for c in classes if c.name == member)
        nets = (dataclasses.replace(nets[0], netclass_id=wanted), *nets[1:])
    circuit = dataclasses.replace(design.circuit, netclasses=classes, nets=nets)
    return dataclasses.replace(design, circuit=circuit)


def netclass(name: str, clearance: int | None = None, track_width: int | None = None) -> NetClass:
    seed = f"{name}-{clearance}-{track_width}"
    return NetClass(
        id=derived_id("cls", "c0421", seed), name=name, clearance=clearance, track_width=track_width
    )


def test_a_class_without_nets_on_one_side_is_no_difference_across_backends() -> None:
    power = netclass("PWR", clearance=MM // 4)
    a = classed(two_layer(), power, member="PWR")
    b = classed(two_layer(), power, netclass("Default", clearance=MM // 5), member="PWR")
    assert of_kind(a, b, "netclass-missing", level=6, across=True) == []
    assert of_kind(a, b, "netclass-missing", level=6) == ["Default"]


def test_a_class_with_nets_on_one_side_is_missing_across_backends() -> None:
    a = two_layer()
    b = classed(two_layer(), netclass("PWR", clearance=MM // 4), member="PWR")
    assert of_kind(a, b, "netclass-missing", level=6, across=True) == ["PWR"]


def test_a_class_field_one_side_leaves_unset_is_not_compared_across_backends() -> None:
    a = classed(two_layer(), netclass("PWR", clearance=MM // 4), member="PWR")
    b = classed(two_layer(), netclass("PWR", clearance=MM // 4, track_width=MM // 2), member="PWR")
    assert of_kind(a, b, "netclass-field", level=6, across=True) == []
    assert of_kind(a, b, "netclass-field", level=6) == ["PWR"]


def test_a_class_field_both_sides_state_is_compared_across_backends() -> None:
    a = classed(two_layer(), netclass("PWR", clearance=MM // 4), member="PWR")
    b = classed(two_layer(), netclass("PWR", clearance=MM // 5), member="PWR")
    assert of_kind(a, b, "netclass-field", level=6, across=True) == ["PWR"]


# --- level 7: Edge.Cuts rings --------------------------------------------------------------------------


def edge_polygon(design: Design, moved: int = 0) -> Design:
    """``design`` with its ``Edge.Cuts`` lines drawn as one polygon, the first vertex moved by ``moved``."""
    lines = [g for g in board(design).graphics if g.layer == "Edge.Cuts"]
    points = [line.points[0] for line in lines]
    points[0] = Point(points[0].x + moved, points[0].y)
    polygon = Graphic(id="gfx-edge-ring", kind="polygon", layer="Edge.Cuts", points=tuple(points),
                      width=lines[0].width)  # fmt: skip
    rest = tuple(g for g in board(design).graphics if g.layer != "Edge.Cuts")
    return with_board(design, graphics=(*rest, polygon))


def test_the_edge_lines_pair_with_one_polygon_of_the_same_ring() -> None:
    a = two_layer()
    assert of_kind(a, edge_polygon(a), "graphic-missing") == []


def test_an_edge_polygon_with_a_moved_vertex_does_not_pair() -> None:
    a = two_layer()
    found = of_kind(a, edge_polygon(a, moved=MM // 10), "graphic-missing")
    assert len(found) == 2 and all("Edge.Cuts" in where for where in found)


# --- level 7: keep-out drawings ------------------------------------------------------------------------

START, END = Point(10 * MM, 5 * MM), Point(20 * MM, 5 * MM)


def drawn_keepout(width: int) -> Design:
    design = with_layer(two_layer(), "Altium.KeepOut", "user")
    line = Graphic(id="gfx-keepout", kind="line", layer="Altium.KeepOut", points=(START, END), width=width)
    return with_board(design, graphics=(*board(design).graphics, line))


def keepout_area(width: int, *, no_vias: bool = True) -> Design:
    design = two_layer()
    area = Keepout(id="kpt-band", outline=segment_band(START, END, width), layers=("B.Cu", "F.Cu"),
                   no_tracks=True, no_vias=no_vias, no_pads=True, no_copper_pour=True)  # fmt: skip
    return with_board(design, keepouts=(*board(design).keepouts, area))


KEEP = ({"Altium.KeepOut"}, ())


def test_a_keepout_drawing_pairs_with_the_rule_area_of_its_band() -> None:
    found = kinds(drawn_keepout(MM // 2), keepout_area(MM // 2), keepout_layers=KEEP)
    assert [k for k in found if k[0] in ("keepout-missing", "keepout-field", "graphic-missing")] == []


def test_a_rule_area_of_another_width_does_not_pair() -> None:
    found = of_kind(drawn_keepout(MM // 2), keepout_area(MM), "keepout-missing", keepout_layers=KEEP)
    assert len(found) == 2


def test_a_paired_rule_area_that_keeps_out_less_is_reported() -> None:
    found = of_kind(drawn_keepout(MM // 2), keepout_area(MM // 2, no_vias=False), "keepout-field",
                    keepout_layers=KEEP)  # fmt: skip
    assert len(found) == 1


def test_a_drawing_on_a_layer_not_named_a_keepout_layer_stays_a_graphic() -> None:
    found = kinds(drawn_keepout(MM // 2), keepout_area(MM // 2))
    assert [k for k, _ in found if k in ("keepout-missing", "graphic-missing")] == [
        "graphic-missing",
        "keepout-missing",
    ]


# --- level 7 (and 1 to 3): mounting holes --------------------------------------------------------------

AT = Point(30 * MM, 15 * MM)


def with_hole(design: Design, drill: int = 3_200_000) -> Design:
    return with_board(design, holes=(*board(design).holes, Hole(id="hol-c0421", position=AT, drill=drill)))


def with_hole_footprint(design: Design, drill: int = 3_200_000, ref: str = "") -> Design:
    component = Component(id="cmp-hole-c0421", ref=ref, value="")
    pad = Pad(id="pad-hole-c0421", number="", shape="circle", size=Size(drill, drill), position=Point(0, 0),
              kind="np_thru_hole", drill=drill, layers=("F.Cu", "B.Cu", "F.Mask", "B.Mask"))  # fmt: skip
    attributes = ("board_only", "exclude_from_pos_files", "exclude_from_bom")
    placed = FootprintInstance(id="fp-hole-c0421", component_id=component.id, lib_ref="Fenolite_Holes:NPTH",
                               position=AT, pads=(pad,), attributes=attributes)  # fmt: skip
    circuit = dataclasses.replace(design.circuit, components=(*design.circuit.components, component))
    design = dataclasses.replace(design, circuit=circuit)
    return with_board(design, footprints=(*board(design).footprints, placed))


def test_a_board_hole_pairs_with_a_board_only_npth_footprint() -> None:
    assert kinds(with_hole(two_layer()), with_hole_footprint(two_layer())) == []
    assert kinds(with_hole_footprint(two_layer()), with_hole(two_layer())) == []


def test_a_hole_footprint_of_another_drill_stays_a_footprint() -> None:
    found = kinds(with_hole(two_layer()), with_hole_footprint(two_layer(), drill=3_000_000))
    assert ("hole-missing", "board:holes:30000000,15000000") in found
    assert ("ref-ambiguous", "") in found  # the footprint is still compared as a component


def test_a_hole_footprint_with_a_reference_stays_a_footprint() -> None:
    found = kinds(with_hole(two_layer()), with_hole_footprint(two_layer(), ref="H1"))
    assert ("hole-missing", "board:holes:30000000,15000000") in found


# --- level 7: fields -----------------------------------------------------------------------------------


def with_field(design: Design, ref: str, name: str, visible: bool) -> Design:
    field = FootprintField(id=derived_id("fld", "c0421", f"{ref}-{name}"), name=name, position=Point(0, MM),
                           layer="F.Fab", size=Size(MM, MM), visible=visible)  # fmt: skip
    return with_footprint(design, ref, lambda f: dataclasses.replace(f, fields=(*f.fields, field)))


def test_a_hidden_field_on_one_side_is_no_difference_across_backends() -> None:
    a, b = two_layer(), with_field(two_layer(), "R1", "MPN", visible=False)
    assert of_kind(a, b, "field-pose", across=True) == []
    assert of_kind(a, b, "field-pose") == ["R1:MPN"]


def test_a_visible_field_on_one_side_is_a_difference_across_backends() -> None:
    a, b = two_layer(), with_field(two_layer(), "R1", "MPN", visible=True)
    assert of_kind(a, b, "field-pose", across=True) == ["R1:MPN"]


# --- level 5 (strict): an arc written as a track ---------------------------------------------------------

ARC_START, ARC_END = Point(5 * MM, 20 * MM), Point(5 * MM + 800, 20 * MM)


def routed_track(design: Design) -> Design:
    track = Track(id="trk-c0421", start=ARC_START, end=ARC_END, width=MM // 4, layer="F.Cu")
    return with_board(design, tracks=(*board(design).tracks, track))


def routed_arc(design: Design, bulge: int) -> Design:
    """An arc from ``ARC_START`` to ``ARC_END`` whose mid lies ``bulge`` nm off their chord."""
    mid = Point((ARC_START.x + ARC_END.x) // 2, ARC_START.y + bulge)
    arc = Arc(id="arc-c0421", start=ARC_START, mid=mid, end=ARC_END, width=MM // 4, layer="F.Cu")
    return with_board(design, arcs=(*board(design).arcs, arc))


def strict_kinds(a: Design, b: Design, length_nm: int = 0) -> list[str]:
    report = compare_designs(a, b, level=5, strict=True, tolerances=Tolerances(length_nm=length_nm))
    return sorted(d.kind for d in report.levels[-1].differences if d.kind in ("arc-missing", "track-missing"))


def test_a_straight_arc_is_the_track_it_draws() -> None:
    a, b = routed_track(two_layer()), routed_arc(two_layer(), bulge=0)
    assert strict_kinds(a, b) == [] and strict_kinds(b, a) == []


def test_a_sub_micron_arc_pairs_with_its_track_within_the_tolerance() -> None:
    a, b = routed_track(two_layer()), routed_arc(two_layer(), bulge=300)
    assert strict_kinds(a, b, length_nm=1000) == []
    assert strict_kinds(b, a, length_nm=1000) == []


def test_a_bulging_arc_is_not_the_track_without_the_tolerance() -> None:
    a, b = routed_track(two_layer()), routed_arc(two_layer(), bulge=300)
    assert strict_kinds(a, b) == ["arc-missing", "track-missing"]


def test_an_arc_bulging_beyond_the_tolerance_is_not_the_track() -> None:
    a, b = routed_track(two_layer()), routed_arc(two_layer(), bulge=2000)
    assert strict_kinds(a, b, length_nm=1000) == ["arc-missing", "track-missing"]


def test_a_paired_arc_still_reports_its_width() -> None:
    a = routed_track(two_layer())
    b = routed_arc(two_layer(), bulge=0)
    wider = with_board(b, arcs=tuple(dataclasses.replace(arc, width=MM // 2) for arc in board(b).arcs))
    report = compare_designs(a, wider, level=5, strict=True)
    assert [d.kind for d in report.levels[-1].differences if d.kind.startswith("track-")] == ["track-width"]


def test_a_hole_footprint_is_no_component_at_level_1() -> None:
    report = compare_designs(with_hole(two_layer()), with_hole_footprint(two_layer()), level=1)
    assert report.levels[0].differences == ()
    report = compare_designs(
        with_hole(two_layer()), with_hole_footprint(two_layer(), drill=3_000_000), level=1
    )
    assert report.levels[0].differences != () or report.levels[0].notices != ()


# --- level 7: parameters placed as fields --------------------------------------------------------------


def with_parameter(design: Design, ref: str, name: str, value: str) -> Design:
    components = tuple(
        dataclasses.replace(c, properties={**c.properties, name: value}) if c.ref == ref else c
        for c in design.circuit.components
    )
    return dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=components))


def test_a_field_the_other_side_holds_as_a_parameter_is_no_difference_across_backends() -> None:
    a = with_parameter(two_layer(), "R1", "MPN", "RC0402")
    b = with_parameter(with_field(two_layer(), "R1", "MPN", visible=True), "R1", "MPN", "RC0402")
    assert of_kind(a, b, "field-pose", across=True) == []
    assert of_kind(b, a, "field-pose", across=True) == []
    assert of_kind(a, b, "field-pose") == ["R1:MPN"]


def test_a_field_of_another_parameter_value_is_a_difference_across_backends() -> None:
    a = with_parameter(two_layer(), "R1", "MPN", "RC0402")
    b = with_parameter(with_field(two_layer(), "R1", "MPN", visible=True), "R1", "MPN", "RC0603")
    assert of_kind(a, b, "field-pose", across=True) == ["R1:MPN"]


def test_a_field_no_parameter_names_is_a_difference_across_backends() -> None:
    a = with_parameter(two_layer(), "R1", "Tolerance", "1%")
    b = with_field(two_layer(), "R1", "MPN", visible=True)
    assert of_kind(a, b, "field-pose", across=True) == ["R1:MPN"]


# --- level 6: stack-up name case -----------------------------------------------------------------------


def renamed_dielectric(design: Design, name: str) -> Design:
    stack = board(design).stackup
    assert stack is not None
    layers = tuple(dataclasses.replace(layer, name=name) if layer.kind == "dielectric" else layer
                   for layer in stack.layers)  # fmt: skip
    return with_board(design, stackup=dataclasses.replace(stack, layers=layers))


def test_a_stackup_name_in_another_letter_case_is_one_layer_across_backends() -> None:
    a = renamed_dielectric(stacked("copper", "dielectric"), "Dielectric 1")
    b = renamed_dielectric(stacked("copper", "dielectric"), "dielectric 1")
    assert of_kind(a, b, "stackup-missing", level=6, across=True) == []
    assert of_kind(a, b, "stackup-missing", level=6) == ["Dielectric 1", "dielectric 1"]


def test_another_stackup_name_is_missing_across_backends() -> None:
    a = renamed_dielectric(stacked("copper", "dielectric"), "Dielectric 1")
    b = renamed_dielectric(stacked("copper", "dielectric"), "Dielectric 2")
    assert of_kind(a, b, "stackup-missing", level=6, across=True) == ["dielectric 1", "dielectric 2"]


# --- level 6: declared format limits -------------------------------------------------------------------


def kept(found: Rule) -> Rule:
    return dataclasses.replace(found, ext={"altium": ExtBag(payload=(("kept_record", "1"),))})


def test_a_kept_rule_the_other_side_cannot_hold_is_a_declared_limit() -> None:
    a = with_rules(two_layer(), rule("GND Clearance"), kept(rule("Room Rule")))
    b = with_rules(two_layer(), rule("GND Clearance"))
    report = compare_designs(a, b, level=6)
    level = report.levels[-1]
    assert [d.kind for d in level.differences] == []
    assert [(e.difference.kind, e.difference.where, e.rule_id) for e in level.excluded] == [
        ("rule-missing", "Room Rule", "declared-limit")
    ]
    assert report.equivalent


def test_an_unmarked_rule_on_one_side_stays_missing() -> None:
    a = with_rules(two_layer(), rule("GND Clearance"), rule("Room Rule"))
    b = with_rules(two_layer(), rule("GND Clearance"))
    assert of_kind(a, b, "rule-missing", level=6) == ["Room Rule"]


def test_a_kept_rule_the_other_side_holds_is_still_compared() -> None:
    a = with_rules(two_layer(), kept(rule("GND Clearance")))
    b = with_rules(two_layer(), rule("GND Clearance", minimum=MM // 4))
    assert of_kind(a, b, "rule-field", level=6) == ["GND Clearance"]
