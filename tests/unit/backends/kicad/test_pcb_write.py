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

from fenolite.backends.kicad import pcb
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
from fenolite.backends.kicad.sexpr import Atom, Node, load, parse, walk
from fenolite.backends.kicad.versions import FileKind, LossyWriteError, load_inventory
from fenolite.core.ids import FENOLITE_NS
from fenolite.model.board import Board, Graphic, Hole, Outline, StackLayer, Stackup, Track
from fenolite.model.circuit import Circuit, Net
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
SKELETON = ROOT / "tests" / "data" / "kicad" / "tokens" / "skeleton.kicad_pcb"
TRACK_ID = "trk_00000000-0000-4000-8000-000000000001"


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
        ),
    )
    root = parse(write_board(empty_design(stackup=stack), target=9).text)
    general = root.find("general")
    assert general is not None and general.find("thickness") == parse("(thickness 1.035)")


def test_four_copper_layers() -> None:
    layers = created_layers(4)
    copper = [
        (layer.name, dict(layer.ext["kicad"].payload)["number"]) for layer in layers if layer.kind == "copper"
    ]
    assert copper == [("F.Cu", "0"), ("In1.Cu", "4"), ("In2.Cu", "6"), ("B.Cu", "2")]
    assert len(created_layers(2)) == 20 and len(layers) == 22
    with pytest.raises(ValueError, match="2 or 4"):
        created_layers(6)  # type: ignore[arg-type]


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
    unknown = sorted(
        (head, child)
        for head, child in created
        if child not in skeleton
        and child not in FLOOR_HEADS
        and inventory.match(FileKind.BOARD, (head, child)) is None
    )
    assert unknown == []
    written = {n.name for _, n in walk(parse(write_board(created_board(), target=9).text))}
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
    assert heads(segment) == list(CANONICAL_ORDER["segment"])
    assert segment.find("net") == parse('(net "GND")')


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
    zone, rule = root.nodes("zone")
    order = CANONICAL_ORDER["zone"]
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
