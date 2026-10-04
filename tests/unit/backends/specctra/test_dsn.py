# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Specctra design-file writer (capability specctra-dsn, "Design files are written from the model").
Hermetic: every board is built through the model API."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _placed import Part, design_of, mm, pt
from _specctra import DEFAULTS, OUTLINE, Bench, bench, two_pads

from fenolite.backends import registry
from fenolite.backends.base import PadCopper
from fenolite.backends.specctra import dsn
from fenolite.backends.specctra.dsn import (
    DsnDefaults,
    ViaStack,
    format_units,
    rounded_point,
    to_units,
    write_dsn,
)
from fenolite.backends.specctra.lexer import SNode, parse
from fenolite.core.coords import Point
from fenolite.core.errors import SEVERITIES
from fenolite.core.evidence import Level
from fenolite.model.board import Arc, Keepout, Track, Via
from fenolite.model.circuit import NetClass
from fenolite.model.design import Design

DATA = Path(__file__).resolve().parents[3] / "data" / "specctra"


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def _section(text: str, head: str) -> SNode:
    node = parse(text).first(head)
    assert node is not None, head
    return node


def _codes(result: dsn.DsnResult) -> list[str]:
    return [issue.code for issue in result.issues]


def _with_board(b: Bench, **changes: object) -> Bench:
    assert b.design.board is not None
    board = dataclasses.replace(b.design.board, **changes)  # type: ignore[arg-type]
    return dataclasses.replace(b, design=dataclasses.replace(b.design, board=board))


def _net_id(design: Design, name: str) -> str:
    return design.nets_by_name[name].id


# --- the two-pad board ------------------------------------------------------------------------------


def test_two_pads() -> None:
    """Scenario "Two-pad board"."""
    result = two_pads().write()
    assert result.text == (DATA / "two_pads.dsn").read_text(encoding="utf-8")
    tree = parse(result.text)
    assert tree.head == "pcb"
    assert [node.head for node in tree.lists] == [
        "parser",
        "resolution",
        "unit",
        "structure",
        "placement",
        "library",
        "network",
        "wiring",
    ]
    (net,) = _section(result.text, "network").all("net")
    pins = net.first("pins")
    assert net.words == ("A",) and pins is not None and pins.items == ("R1-2", "R2-1")
    library = _section(result.text, "library")
    assert [image.words[0] for image in library.all("image")] == ["R1", "R2"]
    assert result.issues == ()


def test_header_declares_quote_units_and_resolution() -> None:
    tree = parse(two_pads().write().text)
    parser = tree.first("parser")
    assert parser is not None
    assert parser.items[:2] == (SNode("string_quote", ('"',)), SNode("space_in_quoted_tokens", ("on",)))
    assert tree.first("resolution") == SNode("resolution", ("um", "10"))
    assert tree.first("unit") == SNode("unit", ("um",))


def test_structure_of_the_two_pad_board() -> None:
    structure = _section(two_pads().write().text, "structure")
    assert [(la.words[0], la.first("type")) for la in structure.all("layer")] == [
        ("F.Cu", SNode("type", ("signal",))),
        ("B.Cu", SNode("type", ("signal",))),
    ]
    box, ring = structure.all("boundary")
    assert box.items == (SNode("rect", ("pcb", "0", "-20000", "30000", "0")),)
    assert ring.items == (
        SNode("path", ("signal", "0", "0", "0", "30000", "0", "30000", "-20000", "0", "-20000")),
    )
    assert structure.first("via") == SNode("via", ("Via_600_300",))
    assert structure.first("rule") == SNode("rule", (SNode("width", ("250",)), SNode("clearance", ("200",))))


def test_names_map_back_to_the_model() -> None:
    b = two_pads()
    names = b.write().names
    assert b.design.board is not None
    r1, r2 = b.design.board.footprints
    assert names.nets == {"A": "A"} and names.net_ids == {"A": _net_id(b.design, "A")}
    assert names.components == {"R1": r1.id, "R2": r2.id}
    assert names.pins == {f"{pad.ref}-{pad.number}": pad.pad_id for pad in b.pads}
    assert names.layers == {"F.Cu": "F.Cu", "B.Cu": "B.Cu"}
    assert names.vias == {"Via_600_300": ViaStack(mm(0.6), mm(0.3), ("F.Cu", "B.Cu"))}
    assert names.places == {"R1": pt(10, 10), "R2": pt(20, 10)}
    assert names.protected_wires == frozenset() and names.protected_vias == frozenset()


def test_shared_padstacks() -> None:
    library = _section(two_pads().write().text, "library")
    stacks = [node.words[0] for node in library.all("padstack")]
    assert stacks == ["P1", "Via_600_300"]
    used = {pin.words[0] for image in library.all("image") for pin in image.all("pin")}
    assert used == {"P1"}


def test_components_are_locked_on_the_front() -> None:
    placement = _section(two_pads().write().text, "placement")
    places = [component.first("place") for component in placement.all("component")]
    assert places == [
        SNode("place", ("R1", "10000", "-10000", "front", "0", SNode("lock_type", ("position",)))),
        SNode("place", ("R2", "20000", "-10000", "front", "0", SNode("lock_type", ("position",)))),
    ]


# --- units ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nm", "units", "text"),
    [
        (0, 0, "0"),
        (100, 1, "0.1"),
        (-100, -1, "-0.1"),
        (1_000_000, 10_000, "1000"),
        (10_000_050, 100_000, "10000"),
        (10_000_150, 100_002, "10000.2"),
        (-10_000_050, -100_000, "-10000"),
        (10_000_100, 100_001, "10000.1"),
        (49, 0, "0"),
        (51, 1, "0.1"),
        (-1_234_560, -12_346, "-1234.6"),
    ],
)
def test_units(nm: int, units: int, text: str) -> None:
    assert to_units(nm) == units
    assert format_units(units) == text


def test_rounded_point_is_what_a_reader_gets_back() -> None:
    assert rounded_point(Point(10_000_050, 5_000_049)) == Point(10_000_000, 5_000_000)
    assert rounded_point(Point(-150, 250)) == Point(-200, 200)


def test_y_is_negated_and_rounded() -> None:
    """Scenario "Y is negated and rounded"."""
    result = bench(design_of(Part("R1", "Mini_R_0603", 10.00005, 5, nets={"1": "A"}))).write()
    place = _section(result.text, "placement").all("component")[0].first("place")
    assert place is not None and place.words[:3] == ("R1", "10000", "-5000")
    (rounded,) = [issue for issue in result.issues if issue.code == "specctra.rounded"]
    assert rounded.severity == "info" and "100 nm" in rounded.message
    assert result.names.places["R1"] == Point(10_000_000, 5_000_000)


def test_one_decimal() -> None:
    """Scenario "One decimal"."""
    result = bench(design_of(Part("R1", "Mini_R_0603", 10.0001, 5, nets={"1": "A"}))).write()
    place = _section(result.text, "placement").all("component")[0].first("place")
    assert place is not None and place.words[:3] == ("R1", "10000.1", "-5000")
    assert "specctra.rounded" not in _codes(result)


def test_pin_lands_on_its_own_rounded_position() -> None:
    b = bench(design_of(Part("R1", "Mini_R_0603", 10.00004, 5, nets={"1": "A"})))
    library = _section(b.write().text, "library")
    (image,) = library.all("image")
    for pin, pad in zip(image.all("pin"), b.pads, strict=True):
        dx = round(float(pin.words[2]) * 10)
        dy = round(float(pin.words[3]) * 10)
        assert to_units(10_000_040) + dx == to_units(pad.position.x)
        assert to_units(-5_000_000) + dy == to_units(-pad.position.y)


# --- components and padstacks -----------------------------------------------------------------------


def _padstacks(text: str) -> dict[str, tuple[SNode, ...]]:
    library = _section(text, "library")
    return {
        node.words[0]: tuple(shape.lists[0] for shape in node.all("shape"))
        for node in library.all("padstack")
    }


def _pin_stack(text: str, ref: str, pin: str) -> tuple[SNode, ...]:
    library = _section(text, "library")
    image = next(node for node in library.all("image") if node.words[0] == ref)
    found = next(node for node in image.all("pin") if node.words[1] == pin)
    return _padstacks(text)[found.words[0]]


def test_bottom_side_pad() -> None:
    """Scenario "Bottom-side pad"."""
    result = bench(design_of(Part("R1", "Mini_R_0603", 10, 10, 90, "bottom", nets={"1": "A"}))).write()
    place = _section(result.text, "placement").all("component")[0].first("place")
    assert place is not None and place.words == ("R1", "10000", "-10000", "front", "0")
    shapes = _pin_stack(result.text, "R1", "1")
    assert {shape.words[0] for shape in shapes} == {"B.Cu"}


def test_through_hole_pad_has_copper_on_every_layer() -> None:
    result = bench(design_of(Part("D1", "Mini_LED_THT_3mm", 10, 10, nets={"1": "A"}), copper=4)).write()
    layers = [la.words[0] for la in _section(result.text, "structure").all("layer")]
    assert len(layers) == 4
    for pin in ("1", "2"):
        assert [shape.words[0] for shape in _pin_stack(result.text, "D1", pin)] == layers
    assert [s.words[0] for s in _padstacks(result.text)["Via_600_300"]] == layers


def test_pad_shapes() -> None:
    """A disc is a circle, an oval a path, a rectangle a polygon and a rounded rectangle its outer hull."""
    b = bench(design_of(Part("P1", "Frame_Shapes", 20, 10, library="Frame", nets={"1": "A"})))
    text = b.write().text
    (circle,) = _pin_stack(text, "P1", "1")
    assert circle == SNode("circle", ("F.Cu", "800"))
    (rect,) = _pin_stack(text, "P1", "2")
    assert rect.head == "polygon" and rect.words[:2] == ("F.Cu", "0") and len(rect.words) == 2 + 8
    (oval,) = _pin_stack(text, "P1", "3")
    assert oval.head == "path" and oval.words[:2] == ("F.Cu", "600") and len(oval.words) == 2 + 4
    (rounded,) = _pin_stack(text, "P1", "4")
    assert rounded.head == "polygon" and rounded.words[1] == "0" and len(rounded.words) > 2 + 8
    custom = _pin_stack(text, "P1", "5")
    assert [shape.head for shape in custom] == ["polygon", "polygon"]


def test_rounded_rectangle_hull_contains_the_copper() -> None:
    b = bench(design_of(Part("P1", "Frame_Shapes", 20, 10, library="Frame")))
    pad = next(p for p in b.pads if p.number == "4")
    (entry,) = pad.copper
    (shape,) = _pin_stack(b.write().text, "P1", "4")
    xs = [float(v) for v in shape.words[2::2]]
    ys = [float(v) for v in shape.words[3::2]]
    half = entry.width / 2 / 1000
    core_x = [(p.x - pad.position.x) / 1000 for p in entry.core]
    core_y = [-(p.y - pad.position.y) / 1000 for p in entry.core]
    assert min(xs) <= min(core_x) - half and max(xs) >= max(core_x) + half
    assert min(ys) <= min(core_y) - half and max(ys) >= max(core_y) + half
    assert max(xs) - (max(core_x) + half) <= 5.2  # the kernel's outer bound: 5 um and the rounding


def test_pads_sharing_a_number_and_a_pad_without_one() -> None:
    """Scenario "Pads sharing a number"."""
    b = bench(design_of(Part("U1", "Mini_Edge_Cases", 10, 10, nets={"1": "A"})))
    result = b.write()
    (image,) = _section(result.text, "library").all("image")
    assert [pin.words[1] for pin in image.all("pin")] == ["@1", "1", "1@2", "2", "3", "4"]
    (net,) = _section(result.text, "network").all("net")
    assert net.first("pins") == SNode("pins", ("U1-1", "U1-1@2"))
    renamed = [issue for issue in result.issues if issue.code == "specctra.renamed"]
    assert [issue.severity for issue in renamed] == ["info", "info"]
    ones = [pad.pad_id for pad in b.pads if pad.number == "1"]
    assert [result.names.pins["U1-1"], result.names.pins["U1-1@2"]] == ones
    assert result.names.pins["U1-@1"] == b.pads[0].pad_id


def test_mounting_hole_is_an_obstacle_on_every_layer() -> None:
    b = bench(design_of(Part("U1", "Mini_Edge_Cases", 10, 10)))
    assert b.pads[0].kind == "np_thru_hole" and b.pads[0].copper == ()
    shapes = _pin_stack(b.write().text, "U1", "@1")
    assert shapes == (SNode("circle", ("F.Cu", "1200")), SNode("circle", ("B.Cu", "1200")))


def test_hyphen_in_a_pin_number_and_in_a_reference() -> None:
    b = two_pads()
    pads = tuple(
        dataclasses.replace(pad, number="A-1", ref="R-1") if pad.ref == "R1" and pad.number == "2" else pad
        for pad in b.pads
    )
    pads = tuple(dataclasses.replace(pad, ref="R-1") if pad.ref == "R1" else pad for pad in pads)
    result = b.write(pads=pads)
    (net,) = _section(result.text, "network").all("net")
    assert net.first("pins") == SNode("pins", ("R_1-A_1", "R2-1"))
    assert _codes(result).count("specctra.renamed") == 2


def test_footprints_without_a_reference_or_sharing_one() -> None:
    b = two_pads()
    pads = tuple(dataclasses.replace(pad, ref="" if pad.ref == "R1" else "X") for pad in b.pads)
    more = bench(design_of(Part("X", "Mini_R_0603", 15, 15)))
    assert b.design.board is not None and more.design.board is not None
    extra = dataclasses.replace(more.design.board.footprints[0], id=_id("fp", 77))
    board = dataclasses.replace(b.design.board, footprints=(*b.design.board.footprints, extra))
    design = dataclasses.replace(b.design, board=board)
    pads += tuple(dataclasses.replace(pad, footprint_id=extra.id) for pad in more.pads)
    result = write_dsn(design, pads=pads, outline=b.outline, selected=("A",), defaults=DEFAULTS)
    assert list(result.names.components) == ["FP1", "X", "X@2"]
    assert _codes(result).count("specctra.renamed") == 2


def test_pad_shape_table() -> None:
    """Each form of a copper entry, with hand-made entries on one pad."""
    b = two_pads()
    origin = b.pads[0].position

    def at(dx: int, dy: int) -> Point:
        return Point(origin.x + dx, origin.y + dy)

    notch = (at(0, 0), at(1000_000, 0), at(1000_000, 1000_000), at(500_000, 200_000), at(0, 1000_000))
    entries = (
        PadCopper("F.Cu", (at(0, 0),), 400_000),
        PadCopper("F.Cu", (at(0, 0), at(300_000, 0), at(300_000, -300_000)), 200_000),
        PadCopper("F.Cu", (at(-100_000, -100_000), at(100_000, -100_000), at(0, 100_000)), 0, filled=True),
        PadCopper("F.Cu", notch, 200_000, filled=True),
        PadCopper("F.Cu", (at(0, 0), at(300_000, 0)), 0),
        PadCopper("F.SilkS", (at(0, 0),), 400_000),
        PadCopper("B.Cu", (at(100_000, 0),), 400_000, exact=False),
    )
    pads = (dataclasses.replace(b.pads[0], copper=entries), *b.pads[1:])
    result = b.write(pads=pads)
    assert _pin_stack(result.text, "R1", "1") == (
        SNode("circle", ("F.Cu", "400")),
        SNode("path", ("F.Cu", "200", "0", "0", "300", "0", "300", "300")),
        SNode("polygon", ("F.Cu", "0", "-100", "100", "100", "100", "0", "-100")),
        SNode("rect", ("F.Cu", "-100", "-1100", "1100", "100")),
        SNode("circle", ("B.Cu", "400", "100", "0")),
    )
    warnings = [issue for issue in result.issues if issue.code == "specctra.pad-approximated"]
    assert len(warnings) == 2 and {issue.severity for issue in warnings} == {"warning"}
    assert {issue.where for issue in warnings} == {"R1-1"}


def test_pad_without_copper_on_a_copper_layer_is_left_out() -> None:
    b = two_pads()
    pads = tuple(
        dataclasses.replace(pad, copper=()) if (pad.ref, pad.number) == ("R1", "2") else pad for pad in b.pads
    )
    result = b.write(pads=pads)
    (image, _other) = _section(result.text, "library").all("image")
    assert [pin.words[1] for pin in image.all("pin")] == ["1"]
    (net,) = _section(result.text, "network").all("net")
    assert net.first("pins") == SNode("pins", ("R2-1",))
    assert "R1-2" not in result.names.pins


# --- outline and keep-outs ----------------------------------------------------------------------


def test_cut_out_and_keep_outs() -> None:
    hole = (pt(12, 4), pt(16, 4), pt(16, 6), pt(12, 6))
    area = (pt(2, 2), pt(4, 2), pt(4, 4))
    b = bench(two_pads().design, cutouts=(hole,))
    keepouts = (
        Keepout(id=_id("kpo", 1), outline=area, layers=("F.Cu",), no_tracks=True, no_vias=True),
        Keepout(id=_id("kpo", 2), outline=area, layers=(), no_tracks=True),
        Keepout(id=_id("kpo", 3), outline=area, layers=("*.Cu",), no_vias=True),
        Keepout(id=_id("kpo", 4), outline=area, layers=("F.Cu",), no_copper_pour=True),
        Keepout(id=_id("kpo", 5), outline=area[:2], layers=("F.Cu",), no_tracks=True),
    )
    structure = _section(_with_board(b, keepouts=keepouts).write().text, "structure")
    flat = ("2000", "-2000", "4000", "-2000", "4000", "-4000")
    assert structure.all("keepout") == (
        SNode(
            "keepout",
            (
                SNode(
                    "polygon",
                    ("signal", "0", "12000", "-4000", "16000", "-4000", "16000", "-6000", "12000", "-6000"),
                ),
            ),
        ),
        SNode("keepout", (SNode("polygon", ("F.Cu", "0", *flat)),)),
    )
    assert structure.all("wire_keepout") == (
        SNode("wire_keepout", (SNode("polygon", ("F.Cu", "0", *flat)),)),
        SNode("wire_keepout", (SNode("polygon", ("B.Cu", "0", *flat)),)),
    )
    assert structure.all("via_keepout") == (
        SNode("via_keepout", (SNode("polygon", ("F.Cu", "0", *flat)),)),
        SNode("via_keepout", (SNode("polygon", ("B.Cu", "0", *flat)),)),
    )
    heads = [node.head for node in structure.lists]
    assert heads.index("boundary") < heads.index("keepout") < heads.index("via") < heads.index("rule")


def test_boundary_box_of_a_ring_that_is_not_a_rectangle() -> None:
    ring = (pt(1, 1), pt(9, 2), pt(5, 8))
    structure = _section(two_pads().write(outline=(ring,)).text, "structure")
    box, path = structure.all("boundary")
    assert box.items == (SNode("rect", ("pcb", "1000", "-8000", "9000", "-1000")),)
    assert path.items[0] == SNode("path", ("signal", "0", "1000", "-1000", "9000", "-2000", "5000", "-8000"))


# --- network ----------------------------------------------------------------------------------------


def _classed() -> Bench:
    power = NetClass(
        id=_id("cls", 1),
        name="Power",
        clearance=mm(0.3),
        track_width=mm(0.5),
        via_diameter=mm(0.8),
        via_drill=mm(0.4),
    )
    plain = NetClass(id=_id("cls", 2), name="Plain")
    unused = NetClass(id=_id("cls", 3), name="Unused", track_width=mm(1))
    design = design_of(
        Part("R1", "Mini_R_0603", 10, 10, nets={"1": "VCC", "2": "A"}),
        Part("R2", "Mini_R_0603", 20, 10, nets={"1": "A", "2": "B"}),
        Part("R3", "Mini_R_0603", 20, 15, nets={"1": "VCC", "2": "B"}),
        classes=(power, plain, unused),
        class_of={"VCC": "Power", "B": "Plain"},
        extra_nets=("LONELY",),
    )
    return bench(design, selected=("VCC", "A"))


def test_nets_and_classes() -> None:
    result = _classed().write()
    network = _section(result.text, "network")
    assert [net.words[0] for net in network.all("net")] == ["A", "B", "VCC"]
    plain, power = network.all("class")
    assert power == SNode(
        "class",
        (
            "Power",
            "VCC",
            SNode("circuit", (SNode("use_via", ("Via_800_400",)),)),
            SNode("rule", (SNode("width", ("500",)), SNode("clearance", ("300",)))),
        ),
    )
    assert plain == SNode(
        "class", ("Plain", "B", SNode("rule", (SNode("width", ("250",)), SNode("clearance", ("200",)))))
    )
    structure = _section(result.text, "structure")
    assert structure.first("via") == SNode("via", ("Via_600_300", "Via_800_400"))
    assert set(result.names.vias) == {"Via_600_300", "Via_800_400"}
    assert result.names.vias["Via_800_400"] == ViaStack(mm(0.8), mm(0.4), ("F.Cu", "B.Cu"))
    assert "LONELY" not in result.names.nets.values()


def test_unselected_nets_are_still_declared() -> None:
    result = _classed().write(selected=())
    network = _section(result.text, "network")
    assert [net.words[0] for net in network.all("net")] == ["A", "B", "VCC"]
    assert _section(result.text, "structure").first("via") == SNode("via", ("Via_600_300",))
    assert all(node.first("circuit") is None for node in network.all("class"))


def test_renamed_and_quoted_net_names() -> None:
    """A name with a blank is quoted; a name with the quote character gets a generated name."""
    design = design_of(
        Part("R1", "Mini_R_0603", 10, 10, nets={"1": 'A"B', "2": "N (1)"}),
        Part("R2", "Mini_R_0603", 20, 10, nets={"1": 'A"B', "2": "N (1)"}),
    )
    result = bench(design, selected=('A"B',)).write()
    assert '(net "N (1)"' in result.text
    network = _section(result.text, "network")
    assert [net.words[0] for net in network.all("net")] == ["NET1", "N (1)"]
    assert result.names.nets == {"NET1": 'A"B', "N (1)": "N (1)"}
    (renamed,) = [issue for issue in result.issues if issue.code == "specctra.renamed"]
    assert renamed.severity == "info" and renamed.where == 'A"B' and "NET1" in renamed.message


# --- wiring -------------------------------------------------------------------------------------


def _wired() -> Bench:
    b = two_pads()
    net = _net_id(b.design, "A")
    tracks = (
        Track(id=_id("trk", 1), start=pt(10.8, 10), end=pt(15, 10), width=mm(0.25), layer="F.Cu", net_id=net),
        Track(id=_id("trk", 2), start=pt(1, 1), end=pt(2, 1), width=mm(0.2), layer="B.Cu"),
        Track(id=_id("trk", 3), start=pt(1, 1), end=pt(2, 1), width=mm(0.2), layer="F.SilkS"),
    )
    vias = (
        Via(
            id=_id("via", 1),
            position=pt(15, 10),
            diameter=mm(0.6),
            drill=mm(0.3),
            layers=("F.Cu", "B.Cu"),
            net_id=net,
        ),
    )
    return _with_board(b, tracks=tracks, vias=vias)


def test_existing_copper_is_protected() -> None:
    """Scenario "Existing copper is protected"."""
    result = _wired().write()
    wiring = _section(result.text, "wiring")
    protect = SNode("type", ("protect",))
    assert wiring.items == (
        SNode(
            "wire",
            (
                SNode("path", ("F.Cu", "250", "10800", "-10000", "15000", "-10000")),
                SNode("net", ("A",)),
                protect,
            ),
        ),
        SNode("wire", (SNode("path", ("B.Cu", "200", "1000", "-1000", "2000", "-1000")), protect)),
        SNode("via", ("Via_600_300", "15000", "-10000", SNode("net", ("A",)), protect)),
    )
    assert result.names.protected_wires == frozenset(
        {("A", "F.Cu", mm(0.25), pt(10.8, 10), pt(15, 10)), ("", "B.Cu", mm(0.2), pt(1, 1), pt(2, 1))}
    )
    assert result.names.protected_vias == frozenset({("A", pt(15, 10))})


def test_arc_is_one_protected_wire_within_the_error_bound() -> None:
    b = two_pads()
    arc = Arc(
        id=_id("arc", 1),
        start=pt(5, 5),
        mid=pt(6, 4),
        end=pt(7, 5),
        width=mm(0.25),
        layer="F.Cu",
        net_id=_net_id(b.design, "A"),
    )
    result = _with_board(b, arcs=(arc,)).write()
    (wire,) = _section(result.text, "wiring").all("wire")
    path = wire.first("path")
    assert path is not None and wire.first("type") == SNode("type", ("protect",))
    numbers = [float(v) for v in path.words[2:]]
    points = list(zip(numbers[0::2], numbers[1::2], strict=True))
    assert points[0] == (5000.0, -5000.0) and points[-1] == (7000.0, -5000.0) and len(points) > 4
    for x, y in points:
        radius = ((x - 6000.0) ** 2 + (y + 5000.0) ** 2) ** 0.5
        assert abs(radius - 1000.0) <= 0.2  # on the circle within the rounding
    assert len(result.names.protected_wires) == len(points) - 1


def test_via_between_inner_layers_gets_its_own_padstack() -> None:
    b = bench(design_of(Part("R1", "Mini_R_0603", 10, 10, nets={"1": "A"}), copper=4))
    assert b.design.board is not None
    copper = [la.name for la in b.design.board.layers if la.kind == "copper"]
    via = Via(
        id=_id("via", 1),
        position=pt(5, 5),
        diameter=mm(0.6),
        drill=mm(0.3),
        layers=(copper[0], copper[1]),
        via_type="blind",
    )
    result = _with_board(b, vias=(via,)).write()
    assert _section(result.text, "wiring").all("via")[0].words[0] == "Via_600_300_L1_L2"
    assert [s.words[0] for s in _padstacks(result.text)["Via_600_300_L1_L2"]] == copper[:2]
    assert result.names.vias["Via_600_300_L1_L2"].layers == (copper[0], copper[1])


# --- determinism, refusals and the package ----------------------------------------------------------


def test_determinism() -> None:
    first = _classed().write()
    second = _classed().write(selected=("A", "VCC", "A"))
    assert first.text == second.text and first.names == second.names and first.issues == second.issues
    assert _wired().write().text == _wired().write().text


def test_refusals() -> None:
    b = two_pads()
    with pytest.raises(ValueError, match="no board"):
        write_dsn(
            dataclasses.replace(b.design, board=None),
            pads=(),
            outline=(OUTLINE,),
            selected=(),
            defaults=DEFAULTS,
        )
    with pytest.raises(ValueError, match="outline"):
        b.write(outline=())
    with pytest.raises(ValueError, match="outline"):
        b.write(outline=((pt(0, 0), pt(1, 1)),))
    with pytest.raises(ValueError, match="no copper layer"):
        _with_board(b, layers=()).write()
    with pytest.raises(ValueError, match="footprint the board lacks"):
        b.write(pads=(dataclasses.replace(b.pads[0], footprint_id=_id("fp", 99)),))


@pytest.mark.parametrize(
    "fields",
    [
        {"width": 0},
        {"clearance": -1},
        {"via_drill": mm(0.6)},
        {"via_diameter": 0.5},
    ],
)
def test_defaults_are_checked(fields: dict[str, int]) -> None:
    values = {
        "width": mm(0.25),
        "clearance": mm(0.2),
        "via_diameter": mm(0.6),
        "via_drill": mm(0.3),
        **fields,
    }
    with pytest.raises(ValueError):
        DsnDefaults(**values)


def test_issue_codes() -> None:
    """Requirement "Specctra issue codes and facts"."""
    assert dsn.ISSUE_CODES == {
        "specctra.unknown-padstack": "error",
        "specctra.session-moved": "error",
        "specctra.pad-approximated": "warning",
        "specctra.rounded": "info",
        "specctra.renamed": "info",
        "specctra.unknown-list": "info",
    }
    assert set(dsn.ISSUE_CODES.values()) <= set(SEVERITIES)


def test_evidence_stays_inferred_until_the_probes_run() -> None:
    assert dsn.EVIDENCE.level is Level.INFERRED
    assert dsn.EVIDENCE.hypotheses == ("H-G-DSN-ACCEPT", "H-G-DSN-PROTECT", "H-G-DSN-UNITS")


def test_not_a_registered_backend() -> None:
    """Scenario "Not a registered backend"."""
    assert "specctra" not in {backend.name for backend in registry.all_backends()}


def test_package_holds_its_provenance_and_nothing_of_the_reference() -> None:
    package = Path(dsn.__file__).resolve().parent
    text = (package / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "S-0224" in text and "ADR-0006" in text
    assert sorted(p.name for p in package.glob("*.pdf")) == []
