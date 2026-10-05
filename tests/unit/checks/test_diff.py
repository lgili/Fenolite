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

from fenolite.backends.kicad import mod
from fenolite.checks.diff import Change, DiffReport, diff_designs, diff_libraries
from fenolite.core.coords import Point, Size
from fenolite.core.ids import new_id
from fenolite.model import canonical
from fenolite.model.base import ExtBag
from fenolite.model.board import Board, FootprintInstance, Pad, Track, Via
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
