# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The model difference report (capability verification-loop, "Model difference report"; change c0066)."""

from __future__ import annotations

import dataclasses
import json
import random
import re
from pathlib import Path

from hypothesis import given, settings
from strategies import designs

from fenolite.backends.base import ModelScope
from fenolite.backends.kicad import mod, sch
from fenolite.checks.diff import (
    KIND_CLASSES,
    Change,
    DiffReport,
    diff_designs,
    diff_libraries,
    diff_sheets,
    length_fields,
)
from fenolite.core.coords import Point, Size
from fenolite.core.ids import new_id
from fenolite.model import canonical
from fenolite.model.base import ExtBag
from fenolite.model.board import Board, FootprintInstance, Pad, Text, Track, Via
from fenolite.model.circuit import Circuit, Component, Net, PinRef
from fenolite.model.design import Design
from fenolite.model.library import Library

MM = 1_000_000
DATA = Path(__file__).resolve().parents[2] / "data"
ID = re.compile(r"\b[a-z]{2,3}_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")


def _design(seed: int) -> Design:
    """Two resistors on the nets VIN and GND, two tracks and one via; every id comes from ``seed``."""
    rng = random.Random(seed)
    base = Design.new("bench", seed=seed)
    parts = [Component(id=new_id("cmp", rng), ref=ref, value="10k") for ref in ("R1", "R2")]
    vin = Net(id=new_id("net", rng), name="VIN", members=(PinRef(parts[0].id, "1"),))
    gnd = Net(id=new_id("net", rng), name="GND", members=(PinRef(parts[1].id, "2"), PinRef(parts[0].id, "2")))
    footprints = []
    for index, part in enumerate(parts):
        pads = tuple(
            Pad(
                id=new_id("pad", rng),
                number=number,
                shape="rect",
                size=Size(MM, MM),
                position=Point(x, 0),
                layers=("F.Cu",),
                net_id=net,
            )
            for number, x, net in (("1", -MM, vin.id if index == 0 else None), ("2", MM, gnd.id))
        )
        footprints.append(
            FootprintInstance(
                id=new_id("fp", rng),
                component_id=part.id,
                lib_ref="Lib:R",
                position=Point(10 * MM * (index + 1), 5 * MM),
                pads=pads,
            )
        )
    tracks = tuple(
        Track(
            id=new_id("trk", rng),
            start=Point(0, y),
            end=Point(5 * MM, y),
            width=250_000,
            layer="F.Cu",
            net_id=gnd.id,
        )
        for y in (0, MM)
    )
    via = Via(
        id=new_id("via", rng),
        position=Point(3 * MM, 3 * MM),
        diameter=600_000,
        drill=300_000,
        layers=("F.Cu", "B.Cu"),
        net_id=gnd.id,
    )
    board = Board(id=new_id("brd", rng), footprints=tuple(footprints), tracks=tracks, vias=(via,))
    return dataclasses.replace(base, circuit=Circuit(components=tuple(parts), nets=(vin, gnd)), board=board)


def _with_new_ids(design: Design, seed: int) -> Design:
    """``design`` with every id replaced by a fresh one, through its canonical text."""
    rng = random.Random(seed)
    texts = canonical.dump_texts(design)
    fresh: dict[str, str] = {}

    def swap(match: re.Match[str]) -> str:
        old = match.group(0)
        return fresh.setdefault(old, new_id(old.split("_")[0], rng))

    parts = {
        attr: canonical.loads(ID.sub(swap, texts[name]), cls, file=name)
        for name, attr, cls in canonical.LAYER_FILES
    }
    return Design(**parts)


def _paths(report: DiffReport) -> list[tuple[str, str]]:
    return [(change.path, change.change) for change in report.changes]


def test_equal_designs_with_different_ids() -> None:
    a, b = _design(1), _design(2)
    assert a.circuit.components[0].id != b.circuit.components[0].id
    report = diff_designs(a, b)
    assert report.equal and report.changes == () and report.summary == {}


@settings(max_examples=40, deadline=None)
@given(designs())
def test_a_design_equals_itself_whatever_its_ids(design: Design) -> None:
    assert diff_designs(design, _with_new_ids(design, 7)).equal


@settings(max_examples=40, deadline=None)
@given(designs())
def test_adding_an_entity_is_one_added_and_one_removed(design: Design) -> None:
    assert design.board is not None
    via = Via(
        id=new_id("via", random.Random(3)),
        position=Point(123, 456),
        diameter=700_001,
        drill=300_000,
        layers=("F.Cu", "B.Cu"),
    )
    more = dataclasses.replace(
        design, board=dataclasses.replace(design.board, vias=(*design.board.vias, via))
    )
    assert _paths(diff_designs(design, more)) == [("/via/0", "added")]
    assert _paths(diff_designs(more, design)) == [("/via/0", "removed")]


def test_one_change_per_kind() -> None:
    a = _design(1)
    b = _design(1)
    assert b.board is not None
    r1, r2 = b.circuit.components
    vin, gnd = b.circuit.nets
    circuit = dataclasses.replace(
        b.circuit,
        components=(dataclasses.replace(r1, value="22k"), r2),
        nets=(dataclasses.replace(vin, members=(*vin.members, PinRef(r2.id, "1"))), gnd),
    )
    extra = dataclasses.replace(b.board.vias[0], id=new_id("via", random.Random(9)), position=Point(9, 9))
    board = dataclasses.replace(b.board, tracks=b.board.tracks[1:], vias=(*b.board.vias, extra))
    report = diff_designs(a, dataclasses.replace(b, circuit=circuit, board=board))
    assert _paths(report) == [
        ("/component/R1/value", "changed"),
        ("/net/VIN/members", "changed"),
        ("/track/0", "removed"),
        ("/via/0", "added"),
    ]
    value = report.changes[0]
    assert (value.a, value.b) == ('"10k"', '"22k"')
    assert json.loads(report.changes[1].b) == ["R1-1", "R2-1"]
    assert report.summary == {
        "component": {"added": 0, "removed": 0, "changed": 1},
        "net": {"added": 0, "removed": 0, "changed": 1},
        "track": {"added": 0, "removed": 1, "changed": 0},
        "via": {"added": 1, "removed": 0, "changed": 0},
    }
    assert not report.equal


def test_moved_footprint_is_one_change() -> None:
    a = _design(1)
    assert a.board is not None
    first = a.board.footprints[0]
    moved = dataclasses.replace(first, position=Point(first.position.x + MM, first.position.y))
    b = dataclasses.replace(
        a, board=dataclasses.replace(a.board, footprints=(moved, *a.board.footprints[1:]))
    )
    report = diff_designs(a, b)
    before, after = '{"x":10000000,"y":5000000}', '{"x":11000000,"y":5000000}'
    assert report.changes == (Change("/footprint/R1/position", "changed", before, after),)


def test_renamed_net() -> None:
    a = _design(1)
    vin, gnd = a.circuit.nets
    b = dataclasses.replace(
        a, circuit=dataclasses.replace(a.circuit, nets=(dataclasses.replace(vin, name="VBUS"), gnd))
    )
    assert _paths(diff_designs(a, b)) == [
        ("/net/VBUS", "added"),
        ("/net/VIN", "removed"),
        ("/pad/R1-1/net_id", "changed"),
    ]


def test_unnamed_net_is_keyed_by_its_members() -> None:
    a = _design(1)
    vin, gnd = a.circuit.nets
    b = dataclasses.replace(
        a, circuit=dataclasses.replace(a.circuit, nets=(dataclasses.replace(vin, name=""), gnd))
    )
    assert ("/net/R1-1", "added") in _paths(diff_designs(a, b))


def test_a_key_with_a_slash_is_escaped() -> None:
    a = _design(1)
    vin, gnd = a.circuit.nets
    one = dataclasses.replace(
        a, circuit=dataclasses.replace(a.circuit, nets=(dataclasses.replace(vin, name="/a~b"), gnd))
    )
    assert ("/net/~1a~0b", "added") in _paths(diff_designs(a, one))


def test_repeated_pad_numbers_are_numbered() -> None:
    a = _design(1)
    assert a.board is not None
    first = a.board.footprints[0]
    twin = dataclasses.replace(first.pads[1], id=new_id("pad", random.Random(5)), position=Point(0, MM))
    more = dataclasses.replace(first, pads=(*first.pads, twin))
    b = dataclasses.replace(a, board=dataclasses.replace(a.board, footprints=(more, a.board.footprints[1])))
    assert _paths(diff_designs(a, b)) == [("/pad/R1-2#1", "added")]


def test_board_values_are_fields_of_the_design() -> None:
    a = _design(1)
    assert a.board is not None
    from fenolite.model.presentation import TitleBlock

    b = dataclasses.replace(a, board=dataclasses.replace(a.board, title_block=TitleBlock(title="T")))
    assert _paths(diff_designs(a, b)) == [("/design/title_block", "changed")]
    renamed = dataclasses.replace(a, header=dataclasses.replace(a.header, name="other"))
    assert diff_designs(a, renamed).equal


def test_libraries() -> None:
    footprint = mod.read_footprint(DATA / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod", library="Mini")
    pad = footprint.pads[0]
    wider = dataclasses.replace(pad, size=Size(pad.size.w + 100_000, pad.size.h))
    a = Library(name="Mini", footprints=(footprint,))
    b = Library(name="Mini", footprints=(dataclasses.replace(footprint, pads=(wider, *footprint.pads[1:])),))
    report = diff_libraries(a, b)
    assert _paths(report) == [(f"/pad/Mini:Mini_R_0603-{pad.number}/size", "changed")]
    assert _paths(diff_libraries(a, Library(name="Mini")))[0] == (
        "/footprint_def/Mini:Mini_R_0603",
        "removed",
    )


def test_opaque_content_only_with_ext() -> None:
    a = _design(1)
    assert a.board is not None
    track = a.board.tracks[0]
    marked = dataclasses.replace(track, ext={"kicad": ExtBag(None, (("locked", "(locked yes)"),))})
    part = a.circuit.components[0]
    tagged = dataclasses.replace(part, ext={"kicad": ExtBag("20241229", (("x", "(x 1)"),))})
    b = dataclasses.replace(
        a,
        circuit=dataclasses.replace(a.circuit, components=(tagged, a.circuit.components[1])),
        board=dataclasses.replace(a.board, tracks=(marked, a.board.tracks[1])),
    )
    assert diff_designs(a, b).equal
    report = diff_designs(a, b, ext=True)
    assert _paths(report) == [
        ("/component/R1/ext", "changed"),
        ("/track/0", "added"),
        ("/track/0", "removed"),
    ]
    assert len(json.loads(report.changes[0].b)) == 64


def test_to_json_limits_the_list() -> None:
    a = _design(1)
    assert a.board is not None
    b = dataclasses.replace(a, board=dataclasses.replace(a.board, tracks=(), vias=()))
    report = diff_designs(a, b)
    whole = report.to_json(None)
    assert whole["total"] == 3 and len(whole["differences"]) == 3 and whole["truncated"] is False
    page = report.to_json(2)
    assert len(page["differences"]) == 2 and page["total"] == 3 and page["truncated"] is True
    assert set(page["differences"][0]) == {"path", "change", "a", "b"}
    assert page["summary"] == {
        "track": {"added": 0, "removed": 2, "changed": 0},
        "via": {"added": 0, "removed": 1, "changed": 0},
    }


# --- sheets (task 2.1b, after the schematic reader of c0060) ---------------------------------------

FLAT = DATA / "kicad" / "schematic" / "flat.kicad_sch"


def _flat(*edits: tuple[str, str]) -> str:
    text = FLAT.read_text(encoding="utf-8")
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text


def test_sheets_moved_symbol_and_removed_label() -> None:
    a = sch.read_schematic(_flat(), file="flat.kicad_sch")
    assert diff_sheets(a, sch.read_schematic(_flat(), file="other.kicad_sch")).equal
    moved = sch.read_schematic(
        _flat(("\t\t(at 100 50 0)\n\t\t(unit 1)", "\t\t(at 102.54 50 0)\n\t\t(unit 1)"))
    )
    removed = dataclasses.replace(moved, labels=moved.labels[:-1])
    assert len(removed.labels) == len(moved.labels) - 1
    report = diff_sheets(a, removed)
    assert _paths(report) == [("/label/0", "removed"), ("/symbol/R1#1/position", "changed")]
    assert json.loads(report.changes[1].b) == {"x": 102_540_000, "y": 50_000_000}
    assert report.summary == {
        "label": {"added": 0, "removed": 1, "changed": 0},
        "symbol": {"added": 0, "removed": 0, "changed": 1},
    }


def test_sheets_opaque_content_only_with_ext() -> None:
    a = sch.read_schematic(_flat())
    wire = "\t(wire\n\t\t(pts\n\t\t\t(xy 1 1) (xy 2 1)\n\t\t)\n\t)\n\t(junction\n"
    b = sch.read_schematic(_flat(("\t(junction\n", wire)))
    assert diff_sheets(a, b).equal
    assert _paths(diff_sheets(a, b, ext=True)) == [("/sheet/ext", "changed")]


def test_sheets_keys_of_symbols_sheet_references_and_embedded_symbols() -> None:
    a = sch.read_schematic(_flat())
    first = a.symbols[0]
    renamed = dataclasses.replace(a, symbols=(dataclasses.replace(first, ref="R9"), *a.symbols[1:]))
    assert _paths(diff_sheets(a, renamed))[:2] == [("/symbol/R1#1", "removed"), ("/symbol/R9#1", "added")]
    fewer = dataclasses.replace(a, lib_symbols=a.lib_symbols[1:], no_connects=())
    paths = _paths(diff_sheets(a, fewer))
    assert (f"/lib_symbol/{a.lib_symbols[0].lib_id}", "removed") in paths
    assert sum(1 for path, _ in paths if path.startswith("/no_connect_flag/")) == len(a.no_connects)
    root = sch.read_schematic(DATA / "kicad" / "schematic" / "hier" / "top.kicad_sch")
    assert root.sheets
    gone = dataclasses.replace(root, sheets=root.sheets[1:], pages=())
    paths = _paths(diff_sheets(root, gone))
    assert (f"/sheet_ref/{root.sheets[0].name}", "removed") in paths and ("/sheet/pages", "changed") in paths


# --- scope and tolerance (capability verification-loop, "Model difference scope"; change c0044) -----------


def _moved(design: Design, *, track: int, footprint: int) -> Design:
    """``design`` with the end of its first track moved by ``track`` nm and its first footprint by
    ``footprint`` nm."""
    assert design.board is not None
    first, *tracks = design.board.tracks
    one, *footprints = design.board.footprints
    board = dataclasses.replace(
        design.board,
        tracks=(dataclasses.replace(first, end=Point(first.end.x + track, first.end.y)), *tracks),
        footprints=(
            dataclasses.replace(one, position=Point(one.position.x, one.position.y - footprint)),
            *footprints,
        ),
    )
    return dataclasses.replace(design, board=board)


def test_tolerance_on_lengths() -> None:
    a = _design(1)
    b = _moved(a, track=2, footprint=3)
    scope = ModelScope(
        {"track": ("start", "end", "width", "layer"), "footprint": ("position",)}, length_tolerance=2
    )
    report = diff_designs(a, b, scope=scope)
    assert _paths(report) == [("/footprint/R1/position", "changed")]
    assert json.loads(report.changes[0].b) == {"x": 10 * MM, "y": 5 * MM - 3}
    exact = ModelScope(scope.fields)
    assert _paths(diff_designs(a, b, scope=exact)) == [
        ("/footprint/R1/position", "changed"),
        ("/track/0", "added"),
        ("/track/0", "removed"),
    ]
    assert diff_designs(a, _moved(a, track=-2, footprint=2), scope=scope).equal
    assert _paths(diff_designs(a, _moved(a, track=3, footprint=0), scope=scope)) == [
        ("/track/0", "added"),
        ("/track/0", "removed"),
    ]


def test_tolerance_is_for_lengths_only() -> None:
    """A layer, a net or a rotation is never close: only fields typed as lengths take the tolerance."""
    a = _design(1)
    assert a.board is not None
    first, *tracks = a.board.tracks
    one, *footprints = a.board.footprints
    turned = dataclasses.replace(
        a.board,
        tracks=(dataclasses.replace(first, layer="B.Cu"), *tracks),
        footprints=(dataclasses.replace(one, rotation=1), *footprints),
    )
    scope = ModelScope(
        {"track": ("start", "end", "layer"), "footprint": ("rotation",)}, length_tolerance=1000
    )
    assert _paths(diff_designs(a, dataclasses.replace(a, board=turned), scope=scope)) == [
        ("/footprint/R1/rotation", "changed"),
        ("/track/0", "added"),
        ("/track/0", "removed"),
    ]
    assert length_fields("track") == {"start", "end", "width"}
    assert length_fields("via") == {"position", "diameter", "drill"}
    assert length_fields("pad") >= {"size", "position", "drill"} and "rotation" not in length_fields("pad")
    assert length_fields("zone") >= {"outline"} and length_fields("no_connect") == frozenset()
    assert set(KIND_CLASSES) == set(_ALL_KINDS)


_ALL_KINDS = (
    "component", "net", "netclass", "interface", "module", "layer", "footprint", "pad", "track", "arc", "via",
    "zone", "keepout", "text", "graphic", "hole", "rule", "stack_layer",
)  # fmt: skip


def test_content_kinds_match_in_canonical_order_under_a_tolerance() -> None:
    """Each entity of ``a`` takes the first unmatched entity of ``b`` that is close, and matches once."""
    a = _design(1)
    assert a.board is not None
    track = a.board.tracks[0]

    def at(x: int, ident: int) -> Track:
        return dataclasses.replace(track, id=new_id("trk", random.Random(ident)), end=Point(x, 0))

    left = dataclasses.replace(a, board=dataclasses.replace(a.board, tracks=(at(100, 1), at(102, 2))))
    right = dataclasses.replace(
        a, board=dataclasses.replace(a.board, tracks=(at(101, 3), at(101, 4), at(500, 5)))
    )
    scope = ModelScope({"track": ("start", "end")}, length_tolerance=2)
    report = diff_designs(left, right, scope=scope)
    assert _paths(report) == [("/track/0", "added")]
    assert json.loads(report.changes[0].b) == {"end": {"x": 500, "y": 0}, "start": {"x": 0, "y": 0}}
    assert _paths(diff_designs(right, left, scope=scope)) == [("/track/0", "removed")]


def test_scope_hides_other_kinds_and_fields() -> None:
    a = _design(1)
    assert a.board is not None
    text = Text(
        id="txt_1", text="REV A", position=Point(0, 0), layer="F.SilkS", size=Size(MM, MM), thickness=1
    )
    b = dataclasses.replace(a, board=dataclasses.replace(a.board, texts=(text,)))
    assert not diff_designs(a, b).equal
    assert diff_designs(a, b, scope=ModelScope({"component": ("ref", "value")})).equal
    r1, r2 = a.circuit.components
    changed = dataclasses.replace(r1, value="22k", properties={"MPN": "X"})
    c = dataclasses.replace(a, circuit=dataclasses.replace(a.circuit, components=(changed, r2)))
    assert _paths(diff_designs(a, c)) == [
        ("/component/R1/properties", "changed"),
        ("/component/R1/value", "changed"),
    ]
    assert _paths(diff_designs(a, c, scope=ModelScope({"component": ("value",)}))) == [
        ("/component/R1/value", "changed")
    ]
    assert diff_designs(a, c, scope=ModelScope({})).equal


def test_scope_compares_the_presence_of_keys() -> None:
    a = _design(1)
    r1 = a.circuit.components[0]
    marked = dataclasses.replace(a, circuit=dataclasses.replace(a.circuit, no_connects=(PinRef(r1.id, "9"),)))
    scope = ModelScope({"no_connect": (), "component": ()})
    assert _paths(diff_designs(a, marked, scope=scope)) == [("/no_connect/R1-9", "added")]
    fewer = dataclasses.replace(
        a, circuit=dataclasses.replace(a.circuit, components=a.circuit.components[:1])
    )
    report = diff_designs(a, fewer, scope=scope)
    assert _paths(report) == [("/component/R2", "removed")] and report.changes[0].a == "{}"


def test_scope_keeps_equal_designs_equal_whatever_the_ids() -> None:
    scope = ModelScope(
        {kind: tuple(f.name for f in dataclasses.fields(cls)) for kind, cls in KIND_CLASSES.items()}, 2
    )
    assert diff_designs(_design(1), _design(2), scope=scope).equal
