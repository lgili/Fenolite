# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board writer: header, created head set, uuids, outline lowering and child order (capabilities
kicad-file-backend and kicad-slots, change c0017)."""

from __future__ import annotations

import dataclasses
import uuid
from collections import Counter
from pathlib import Path

import pytest
from _boards import FIXTURE, created_board, mm, square

from fenolite.backends.kicad import boarditems, pcb
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import (
    CANONICAL_ORDER,
    CREATED_ROOT_HEADS,
    FLOOR_HEADS,
    POSITIONAL,
    kicad_uuid,
    read_board,
    write_board,
)
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, load, parse, walk
from fenolite.backends.kicad.stackup import ROW_CHILDREN
from fenolite.backends.kicad.versions import FileKind, LossyWriteError, check_emittable, load_inventory
from fenolite.core.coords import Size
from fenolite.core.ids import FENOLITE_NS
from fenolite.model.board import (
    Board,
    Dimension,
    Graphic,
    Hole,
    Keepout,
    Outline,
    StackLayer,
    Stackup,
    Text,
    Track,
)
from fenolite.model.circuit import Circuit, Net
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
SKELETON = ROOT / "tests" / "data" / "kicad" / "tokens" / "skeleton.kicad_pcb"
TRACK_ID = "trk_00000000-0000-4000-8000-000000000001"


def two_dimensions() -> tuple[Dimension, ...]:
    """The dimensions of scenario "Created dimensions": 20 mm aligned, and 25.5 mm measured horizontally
    at two decimals."""
    return (
        Dimension(id="dim_00000000-0000-4000-8000-000000000001", kind="aligned", layer="Dwgs.User",
                  start=mm(10, 3), end=mm(30, 3), offset=-2_000_000),
        Dimension(id="dim_00000000-0000-4000-8000-000000000002", kind="orthogonal", layer="Dwgs.User",
                  start=mm(10, 50), end=mm(35.5, 55), offset=4_000_000, direction="horizontal", precision=2),
    )  # fmt: skip


def heads(node: Node) -> list[str]:
    return [c.name for c in node.children if isinstance(c, Node)]


def empty_design(copper: int = 2, **board: object) -> Design:
    design = Design.new("empty", seed=1)
    assert design.board is not None
    return dataclasses.replace(
        design,
        board=dataclasses.replace(design.board, layers=created_layers(copper), **board),  # type: ignore[arg-type]
    )


def items(root: Node, head: str) -> list[Node]:
    return [n for _, n in walk(root) if n.name == head]


def without_nets(node: Node) -> Node:
    """The tree without ``net`` nodes and without the root's generator atoms."""
    kept: list[Node | Atom] = []
    for child in node.children:
        if isinstance(child, Node):
            if child.name == "net" or (
                node.name == "kicad_pcb" and child.name in ("generator", "generator_version")
            ):
                continue
            kept.append(without_nets(child))
        else:
            kept.append(child)
    return node.with_children(kept)


# -- header


def test_header_for_target_9() -> None:
    root = parse(write_board(created_board(), target=9).text)
    assert root.find("version") == Node(Atom.symbol("version"), (Atom.integer(20241229),))
    assert root.find("generator") == Node(Atom.symbol("generator"), (Atom.string("fenolite"),))
    assert root.find("generator_version") == Node(Atom.symbol("generator_version"), (Atom.string("9.0"),))


def test_header_for_target_10() -> None:
    root = parse(write_board(created_board(), target=10).text)
    assert root.find("version") == Node(Atom.symbol("version"), (Atom.integer(20260206),))
    assert root.find("generator_version") == Node(Atom.symbol("generator_version"), (Atom.string("10.0"),))


def test_deterministic_text() -> None:
    first = write_board(created_board(), target=10)
    assert write_board(created_board(), target=10) == first
    assert first.text.endswith(")\n")


def test_unsupported_target() -> None:
    with pytest.raises(ValueError, match="unsupported target KiCad 8"):
        write_board(created_board(), target=8)


# -- created boards


def test_head_set_of_a_created_board() -> None:
    root = parse(write_board(empty_design(), target=9).text)
    assert heads(root) == [
        "version",
        "generator",
        "generator_version",
        "general",
        "paper",
        "layers",
        "setup",
        "net",
    ]
    assert root.find("general") == parse("(general (thickness 1.6) (legacy_teardrops no))")
    assert root.find("paper") == parse('(paper "A4")')
    assert root.find("setup") == parse("(setup (pad_to_mask_clearance 0))")
    assert root.nodes("net") == (parse('(net 0 "")'),)


def test_no_net_table_for_target_10() -> None:
    root = parse(write_board(empty_design(), target=10).text)
    assert heads(root) == ["version", "generator", "generator_version", "general", "paper", "layers", "setup"]


def test_thickness_from_the_stackup() -> None:
    stack = Stackup(
        id="stk_00000000-0000-4000-8000-000000000001",
        layers=(
            StackLayer(
                id="sly_00000000-0000-4000-8000-000000000001", name="F.Cu", kind="copper", thickness=35_000
            ),
            StackLayer(
                id="sly_00000000-0000-4000-8000-000000000002",
                name="core",
                kind="dielectric",
                thickness=1_000_000,
            ),
            StackLayer(
                id="sly_00000000-0000-4000-8000-000000000003", name="B.Cu", kind="copper", thickness=35_000
            ),
        ),
    )
    root = parse(write_board(empty_design(stackup=stack), target=9).text)
    general = root.find("general")
    assert general is not None and general.find("thickness") == parse("(thickness 1.07)")


def test_four_copper_layers() -> None:
    layers = created_layers(4)
    copper = [
        (layer.name, dict(layer.ext["kicad"].payload)["number"]) for layer in layers if layer.kind == "copper"
    ]
    assert copper == [("F.Cu", "0"), ("In1.Cu", "4"), ("In2.Cu", "6"), ("B.Cu", "2")]
    assert len(created_layers(2)) == 20 and len(layers) == 22
    for count in (3, 10):
        with pytest.raises(ValueError, match="2, 4, 6 or 8"):
            created_layers(count)


def test_created_layers_round_trip() -> None:
    root = parse(write_board(empty_design(4), target=10).text)
    reread = read_board(write_board(empty_design(4), target=10).text)
    assert reread.board is not None
    assert [dataclasses.replace(layer, provenance=None) for layer in reread.board.layers] == list(
        created_layers(4)
    )
    rows = root.find("layers")
    assert rows is not None and rows.children[1] == parse('(4 "In1.Cu" signal)')


def test_created_tokens() -> None:
    """Every created head and field is in the skeleton, in FLOOR_HEADS or in the inventory, and every
    floor name is written by the created test board for target 9."""
    skeleton = {n.name for _, n in walk(load(SKELETON))}
    inventory = load_inventory()
    created = {
        (head, child)
        for head, order in CANONICAL_ORDER.items()
        for child in order
        if child not in POSITIONAL.get(head, ())
    }
    created |= {("kicad_pcb", head) for head in CREATED_ROOT_HEADS}
    created |= {("general", "thickness"), ("general", "legacy_teardrops"), ("setup", "pad_to_mask_clearance")}
    created |= {("setup", "stackup"), ("stackup", "layer"), ("stackup", "copper_finish")}
    created |= {("stackup", "dielectric_constraints"), *(("layer", child) for child in ROW_CHILDREN)}
    unknown = sorted(
        (head, child)
        for head, child in created
        if child not in skeleton
        and child not in FLOOR_HEADS
        and inventory.match(FileKind.BOARD, (head, child)) is None
    )
    assert unknown == []
    created_design = created_board()
    assert created_design.board is not None
    # the created test board holds no dimension: one of each kind is added here (c0103)
    with_dimensions = dataclasses.replace(
        created_design, board=dataclasses.replace(created_design.board, dimensions=two_dimensions())
    )
    written = {n.name for _, n in walk(parse(write_board(with_dimensions, target=9).text))}
    assert set(FLOOR_HEADS) <= written
    assert set(FLOOR_HEADS).isdisjoint(skeleton)


# -- uuids


def test_read_uuids_are_kept() -> None:
    def uuids(root: Node) -> Counter[str]:
        return Counter(n.atoms()[0].value for n in items(root, "uuid"))

    source = load(FIXTURE)
    written = parse(write_board(read_board(FIXTURE), target=9).text)
    assert uuids(written) == uuids(source)


def test_created_track_uuid() -> None:
    design = empty_design()
    assert design.board is not None
    track = Track(id=TRACK_ID, start=mm(1, 1), end=mm(2, 1), width=250_000, layer="F.Cu")
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=(track,)))
    (segment,) = parse(write_board(design, target=10).text).nodes("segment")
    expected = str(uuid.uuid5(FENOLITE_NS, f"kicad-out:{TRACK_ID}"))
    assert segment.find("uuid") == Node(Atom.symbol("uuid"), (Atom.string(expected),))
    assert kicad_uuid(track) == expected


def test_kicad_uuid_rules() -> None:
    track = Track(
        id=TRACK_ID, start=mm(1, 1), end=mm(2, 1), width=1, layer="F.Cu", native_ids={"kicad": "abc"}
    )
    assert kicad_uuid(track) == "abc"
    assert kicad_uuid(track, "part") == str(uuid.uuid5(FENOLITE_NS, f"kicad-out:{TRACK_ID}:part"))


# -- outline


def outline_design(*graphics: Graphic, cutouts: tuple[tuple[object, ...], ...] = ()) -> Design:
    outline = Outline(
        id="out_00000000-0000-4000-8000-000000000001", points=square(0, 0, 50, 30), cutouts=cutouts
    )  # type: ignore[arg-type]
    return empty_design(outline=outline, graphics=graphics)


def test_rectangle_outline() -> None:
    root = parse(write_board(outline_design(), target=9).text)
    lines = root.nodes("gr_line")
    assert len(lines) == 4
    assert all(line.find("layer") == parse('(layer "Edge.Cuts")') for line in lines)
    assert lines[-1].find("end") == parse("(end 0 0)") and lines[0].find("start") == parse("(start 0 0)")
    assert lines[0].find("stroke") == parse("(stroke (width 0.1) (type solid))")
    assert heads(lines[0]) == ["start", "end", "stroke", "layer", "uuid"]
    expected = str(uuid.uuid5(FENOLITE_NS, "kicad-out:out_00000000-0000-4000-8000-000000000001:outline:0:0"))
    assert lines[0].find("uuid") == Node(Atom.symbol("uuid"), (Atom.string(expected),))


def test_cutouts_are_closed() -> None:
    root = parse(write_board(outline_design(cutouts=(square(10, 10, 20, 20),)), target=9).text)
    lines = root.nodes("gr_line")
    assert len(lines) == 8 and lines[-1].find("end") == parse("(end 10 10)")


def test_no_outline_no_lines() -> None:
    assert parse(write_board(empty_design(), target=9).text).nodes("gr_line") == ()
    empty = Outline(id="out_00000000-0000-4000-8000-000000000001")
    assert parse(write_board(empty_design(outline=empty), target=9).text).nodes("gr_line") == ()


def test_outline_and_edge_graphics() -> None:
    edge = Graphic(
        id="gfx_00000000-0000-4000-8000-000000000001",
        kind="line",
        layer="Edge.Cuts",
        points=(mm(0, 0), mm(1, 0)),
    )
    with pytest.raises(LossyWriteError) as info:
        write_board(outline_design(edge), target=9)
    assert [i.code for i in info.value.issues] == ["kicad.board.outline-conflict"]
    assert info.value.droppable is False and "--allow-lossy" not in info.value.hint


def test_outline_set_on_a_read_board() -> None:
    design = read_board(SKELETON)
    assert design.board is not None
    outline = Outline(id="out_00000000-0000-4000-8000-000000000001", points=square(0, 0, 50, 30))
    with_rect = dataclasses.replace(design, board=dataclasses.replace(design.board, outline=outline))
    with pytest.raises(LossyWriteError) as info:
        write_board(with_rect, target=9)
    assert [i.code for i in info.value.issues] == ["kicad.board.outline-conflict"]
    graphics = tuple(g for g in design.board.graphics if g.layer != "Edge.Cuts")
    without = dataclasses.replace(
        design, board=dataclasses.replace(design.board, outline=outline, graphics=graphics)
    )
    root = parse(write_board(without, target=9).text)
    assert len([g for g in root.nodes("gr_line") if g.find("layer") == parse('(layer "Edge.Cuts")')]) == 4
    assert root.nodes("gr_rect") == ()


# -- slot source


def test_created_track_in_canonical_order() -> None:
    design = empty_design()
    assert design.board is not None
    net = Net(id="net_00000000-0000-4000-8000-000000000001", name="GND")
    track = Track(id=TRACK_ID, start=mm(1, 1), end=mm(2, 1), width=250_000, layer="F.Cu", net_id=net.id)
    design = dataclasses.replace(
        design, circuit=Circuit(nets=(net,)), board=dataclasses.replace(design.board, tracks=(track,))
    )
    (segment,) = parse(write_board(design, target=10).text).nodes("segment")
    assert heads(segment) == [name for name in CANONICAL_ORDER["segment"] if name != "locked"]
    assert segment.find("net") == parse('(net "GND")')
    locked = dataclasses.replace(design, board=dataclasses.replace(
        design.board, tracks=(dataclasses.replace(track, locked=True),)))  # fmt: skip
    (segment,) = parse(write_board(locked, target=10).text).nodes("segment")
    assert heads(segment) == list(CANONICAL_ORDER["segment"])


def test_read_entity_keeps_its_order() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    track = design.board.tracks[0]
    design = design.replace_entity(dataclasses.replace(track, width=300_000))
    source, written = load(FIXTURE), parse(write_board(design, target=9).text)
    before, after = source.nodes("segment")[0], written.nodes("segment")[0]
    assert heads(after) == heads(before) and after.find("width") == parse("(width 0.3)")
    changed = written.with_children([c for c in written.children if c is not after])
    original = source.with_children([c for c in source.children if c is not before])
    assert without_nets(changed) == without_nets(original)


def test_created_zone_fill_and_rule_area() -> None:
    root = parse(write_board(created_board(), target=10).text)
    zone, hatched, rule = root.nodes("zone")
    order = CANONICAL_ORDER["zone"]
    assert heads(hatched) == [h for h in order if h in heads(hatched)] and "locked" in heads(hatched)
    assert heads(zone) == [h for h in order if h in heads(zone)] and "filled_polygon" in heads(zone)
    (fill,) = zone.nodes("filled_polygon")
    assert heads(fill) == ["layer", "island", "pts"] and fill.find("island") == parse("(island yes)")
    keepout = rule.find("keepout")
    assert keepout is not None and heads(keepout) == list(CANONICAL_ORDER["keepout"])
    assert heads(rule) == [h for h in order if h in heads(rule)] and rule.find("net") is None


def test_field_without_canonical_position(monkeypatch: pytest.MonkeyPatch) -> None:
    order = dict(CANONICAL_ORDER)
    order["segment"] = tuple(h for h in order["segment"] if h != "width")
    monkeypatch.setattr(pcb, "CANONICAL_ORDER", order)
    with pytest.raises(ValueError, match=r"segment: field 'width'"):
        write_board(created_board(), target=10)


def test_head_without_canonical_order(monkeypatch: pytest.MonkeyPatch) -> None:
    order = {head: value for head, value in CANONICAL_ORDER.items() if head != "via"}
    monkeypatch.setattr(pcb, "CANONICAL_ORDER", order)
    with pytest.raises(ValueError, match="no canonical order for head 'via'"):
        write_board(created_board(), target=10)


def test_created_footprint_properties() -> None:
    root = parse(write_board(created_board(), target=9).text)
    (footprint,) = root.nodes("footprint")
    assert heads(footprint)[:4] == ["locked", "layer", "uuid", "at"]
    names = [p.children[0] for p in footprint.nodes("property")]
    assert names == [Atom.string("Reference"), Atom.string("Value")]
    reread = read_board(write_board(created_board(), target=9).text)
    assert [(c.ref, c.value, c.path) for c in reread.circuit.components] == [("U1", "TEST", "/u1")]


def test_bottom_text_is_mirrored() -> None:
    root = parse(write_board(created_board(), target=9).text)
    (text,) = root.nodes("gr_text")
    effects = text.find("effects")
    assert effects is not None and effects.find("justify") == parse("(justify mirror)")


def test_board_required() -> None:
    design = dataclasses.replace(created_board(), board=None)
    with pytest.raises(ValueError, match="no board"):
        write_board(design)
    holes = dataclasses.replace(created_board())
    assert holes.board is not None
    board: Board = holes.board
    hole = Hole(id="hol_00000000-0000-4000-8000-000000000001", position=mm(1, 1), drill=1_000_000)
    with pytest.raises(ValueError, match="holes"):
        write_board(dataclasses.replace(holes, board=dataclasses.replace(board, holes=(hole,))))


# -- unknown child (kicad-slots "Opaque child unchanged on a same-target write")

DIMENSION = ROOT / "tests" / "data" / "kicad" / "board" / "dimension.kicad_pcb"


def moved_dimension_design() -> Design:
    design = read_board(DIMENSION)
    assert design.board is not None
    track = design.board.tracks[0]
    return design.replace_entity(dataclasses.replace(track, start=mm(6, 10)))


def test_dimension_unchanged_on_a_same_target_write() -> None:
    source = load(DIMENSION)
    written = parse(write_board(moved_dimension_design(), target=9).text)
    index = next(i for i, c in enumerate(source.children) if isinstance(c, Node) and c.name == "dimension")
    assert written.children[index] == source.children[index]
    assert written.nodes("segment")[0].find("start") == parse("(start 6 10)")


# --- board items of a script: names, justification and dimensions (change c0103) -----------------------

MILLI = 1_000_000


def flat(text: str) -> str:
    """The board on one line, as the compact print writes it."""
    return dumps(parse(text), style="compact")


@pytest.mark.parametrize("target", [9, 10])
def test_created_rule_area_with_a_name(target: int) -> None:
    """Scenario "Created rule area with a name"."""
    area = Keepout(id="kpo_00000000-0000-4000-8000-000000000001", outline=square(40, 5, 45, 10),
                   layers=("F.Cu",), no_tracks=True, name="ANT")  # fmt: skip
    design = boarditems.mark_items(empty_design(keepouts=(area,)))
    text = write_board(design, target=target).text
    native = boarditems.item_uuid(area.id)
    assert f'(uuid "{native}") (name "ANT")' in flat(text)
    (read,) = read_board(text).board.keepouts  # type: ignore[union-attr]
    assert read.name == "ANT" and read.no_tracks and read.native_ids["kicad"] == native
    unnamed = write_board(empty_design(keepouts=(dataclasses.replace(area, name=""),)), target=target).text
    assert "(name" not in unnamed


def test_justified_text_is_written() -> None:
    """Scenario "Justified text"."""
    texts = (
        Text(id="txt_00000000-0000-4000-8000-000000000001", text="L", position=mm(5, 40), layer="F.SilkS",
             size=pcb.TEXT_SIZE, thickness=pcb.TEXT_THICKNESS, h_justify="left", v_justify="bottom"),
        Text(id="txt_00000000-0000-4000-8000-000000000002", text="R", position=mm(5, 44), layer="B.SilkS",
             size=pcb.TEXT_SIZE, thickness=pcb.TEXT_THICKNESS, h_justify="right"),
        Text(id="txt_00000000-0000-4000-8000-000000000003", text="C", position=mm(5, 48), layer="F.SilkS",
             size=pcb.TEXT_SIZE, thickness=pcb.TEXT_THICKNESS),
    )  # fmt: skip
    text = write_board(empty_design(texts=texts), target=10).text
    assert "(justify left bottom)" in flat(text) and "(justify right mirror)" in flat(text)
    assert flat(text).count("(justify") == 2
    read = read_board(text).board
    assert read is not None
    assert [(t.h_justify, t.v_justify) for t in read.texts] == [
        ("left", "bottom"), ("right", "center"), ("center", "center")
    ]  # fmt: skip


@pytest.mark.parametrize("target", [9, 10])
def test_created_dimension_nodes(target: int) -> None:
    """Scenario "Created dimensions": the children, their order and the cache text."""
    design = boarditems.mark_items(empty_design(dimensions=two_dimensions()))
    text = write_board(design, target=target).text
    root = parse(text)
    first, second = items(root, "dimension")
    common = ["type", "layer", "uuid", "pts", "height"]
    assert heads(first) == [*common, "format", "style", "gr_text"]
    assert heads(second) == [*common, "orientation", "format", "style", "gr_text"]
    one = flat(text)
    native = boarditems.item_uuid(two_dimensions()[0].id)
    assert "(type aligned)" in one and "(height -2)" in one and "(units 2)" in one and "(precision 4)" in one
    assert f'(gr_text "20.0000 mm" (at 20 3 0) (layer "Dwgs.User") (uuid "{native}")' in one
    assert "(orientation 0)" in one and '(gr_text "25.50 mm" (at 22.75 52.5 0)' in one
    assert '(format (prefix "") (suffix "") (units 2) (units_format 1) (precision 4))' in one
    assert (
        "(style (thickness 0.1) (arrow_length 1.27) (text_position_mode 0) (arrow_direction outward)"
        " (extension_height 0.58642) (extension_offset 0.5) (keep_text_aligned yes))"
    ) in one
    assert "(effects (font (size 1 1) (thickness 0.15)))" in one
    read = read_board(text).board
    assert read is not None
    for found, made in zip(read.dimensions, two_dimensions(), strict=True):
        assert (found.kind, found.layer, found.start, found.end, found.offset, found.direction) == (
            made.kind, made.layer, made.start, made.end, made.offset, made.direction
        )  # fmt: skip
        assert (found.units, found.precision) == (made.units, made.precision)
    # a board read with dimensions is written back as read
    assert parse(write_board(read_board(text), target=target).text) == root


def test_dimension_follows_gr_text_in_the_root() -> None:
    order = list(CANONICAL_ORDER["kicad_pcb"])
    assert order.index("dimension") == order.index("gr_text") + 1


def test_dimension_cache_value() -> None:
    """Scenario "Cache value of an oblique dimension", and rounding half away from zero."""
    oblique = Dimension(id="dim_00000000-0000-4000-8000-000000000009", kind="aligned", layer="Dwgs.User",
                        start=mm(0, 0), end=mm(1, 1), offset=0)  # fmt: skip
    assert pcb.dimension_value(oblique) == "1.4142 mm"
    assert pcb.dimension_value(dataclasses.replace(oblique, units="in")) == "0.0557 in"
    assert pcb.dimension_value(dataclasses.replace(oblique, precision=0)) == "1 mm"
    half = dataclasses.replace(oblique, end=mm(0.25, 0), precision=1)
    assert pcb.dimension_value(half) == "0.3 mm"
    vertical = dataclasses.replace(
        oblique, kind="orthogonal", direction="vertical", end=mm(7, -3), precision=2
    )
    assert pcb.dimension_value(vertical) == "3.00 mm"
    assert pcb.dimension_value(dataclasses.replace(vertical, direction="horizontal")) == "7.00 mm"


def test_dimension_defaults_and_given_values() -> None:
    made = dataclasses.replace(
        two_dimensions()[0], size=Size(2 * MILLI, 2 * MILLI), thickness=300_000, width=250_000
    )
    one = flat(write_board(empty_design(dimensions=(made,)), target=10).text)
    assert "(style (thickness 0.25)" in one and "(effects (font (size 2 2) (thickness 0.3)))" in one


@pytest.mark.parametrize("target", [9, 10])
def test_emit_check_is_clean_for_board_items(target: int) -> None:
    """Scenario "Emit check is clean for both targets"."""
    area = Keepout(id="kpo_00000000-0000-4000-8000-000000000001", outline=square(40, 5, 45, 10),
                   layers=("F.Cu",), no_vias=True, name="ANT")  # fmt: skip
    label = Text(id="txt_00000000-0000-4000-8000-000000000001", text="L", position=mm(5, 40),
                 layer="F.SilkS", size=pcb.TEXT_SIZE, thickness=pcb.TEXT_THICKNESS, h_justify="left",
                 v_justify="top")  # fmt: skip
    design = empty_design(keepouts=(area,), texts=(label,), dimensions=two_dimensions())
    text = write_board(design, target=target).text
    assert check_emittable(parse(text), FileKind.BOARD, target) == ()
