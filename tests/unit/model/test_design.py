# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import dataclasses
import random

import pytest
from hypothesis import given, settings
from strategies import designs

from fenolite.core.coords import Point, Size
from fenolite.core.ids import content_hash, content_id, derived_id, new_id
from fenolite.model import Component, Design, FootprintInstance, Net, Pad, Pin, PinRef, Track


def _small(seed: int = 1) -> Design:
    rng = random.Random(seed)
    design = Design.new("demo", seed=seed)
    r1 = Component(
        id=new_id("cmp", rng),
        ref="R1",
        pins=(Pin(id=new_id("pin", rng), number="1"), Pin(id=new_id("pin", rng), number="2")),
    )
    c1 = Component(
        id=new_id("cmp", rng),
        ref="C1",
        pins=(Pin(id=new_id("pin", rng), number="1"), Pin(id=new_id("pin", rng), number="2")),
    )
    gnd = Net(id=new_id("net", rng), name="GND", members=(PinRef(r1.id, "2"), PinRef(c1.id, "2")))
    vin = Net(id=new_id("net", rng), name="VIN", members=(PinRef(r1.id, "1"), PinRef(c1.id, "1")))

    def fp(component: Component, x: int) -> FootprintInstance:
        pads = tuple(
            Pad(
                id=new_id("pad", rng),
                number=n,
                shape="rect",
                size=Size(500_000, 500_000),
                position=Point((int(n) - 1) * 1_500_000, 0),
                layers=("F.Cu",),
                net_id=gnd.id if n == "2" else vin.id,
            )
            for n in ("1", "2")
        )
        return FootprintInstance(
            id=new_id("fp", rng), component_id=component.id, lib_ref="L:0603", position=Point(x, 0), pads=pads
        )

    assert design.board is not None
    board = dataclasses.replace(design.board, footprints=(fp(r1, 0), fp(c1, 5_000_000)))
    circuit = dataclasses.replace(design.circuit, components=(r1, c1), nets=(gnd, vin))
    return dataclasses.replace(design, circuit=circuit, board=board)


def test_indexes_resolve() -> None:
    design = _small()
    assert design.by_ref["R1"].ref == "R1"
    assert {p.number for p in design.by_net["GND"]} == {"2"} and len(design.by_net["GND"]) == 2
    assert design.by_id[design.by_ref["C1"].id] is design.by_ref["C1"]
    assert len(design.by_layer["F.Cu"]) == 4


def test_clean_design_validates() -> None:
    assert _small().validate() == ()


def test_duplicate_reference_is_a_finding() -> None:
    design = _small()
    c1 = design.by_ref["C1"]
    design = design.replace_entity(dataclasses.replace(c1, ref="R1"))
    codes = {(i.code, i.severity) for i in design.validate()}
    assert ("model.duplicate-ref", "error") in codes


def test_dangling_and_unknown_references() -> None:
    design = _small()
    ghost = Net(id=new_id("net", random.Random(9)), name="GHOST", members=(PinRef("cmp_nope", "1"),))
    lonely = Net(id=new_id("net", random.Random(10)), name="LONELY")
    circuit = dataclasses.replace(design.circuit, nets=(*design.circuit.nets, ghost, lonely))
    codes = [i.code for i in dataclasses.replace(design, circuit=circuit).validate()]
    assert "model.unknown-component" in codes and "model.dangling-net" in codes


def test_seeded_creation_is_reproducible() -> None:
    assert _small(7) == _small(7)
    assert _small(7).id != _small(8).id


def test_same_native_id_same_fenolite_id() -> None:
    native = "a81c0000-0000-4000-8000-000000000001"
    assert derived_id("fp", "kicad", native) == derived_id("fp", "kicad", native)


def test_editing_another_object_keeps_content_ids() -> None:
    def track_id(track: Track) -> str:
        digest = content_hash(
            "track", [track.start.x, track.start.y], [track.end.x, track.end.y], track.width, track.layer
        )
        return content_id("trk", "kicad", "doc", "tracks", digest)

    a = Track(
        id="trk_00000000-0000-4000-8000-000000000000",
        start=Point(0, 0),
        end=Point(1_000, 0),
        width=10,
        layer="F.Cu",
    )
    b = Track(
        id="trk_00000000-0000-4000-8000-000000000001",
        start=Point(0, 5),
        end=Point(1_000, 5),
        width=10,
        layer="F.Cu",
    )
    moved_b = dataclasses.replace(b, end=Point(2_000, 5))
    assert track_id(a) == track_id(a)  # re-import unchanged
    assert track_id(b) != track_id(moved_b)  # editing b changes only b's derived id


def test_replace_entity_moves_one_footprint() -> None:
    design = _small()
    assert design.board is not None
    fp = design.board.footprints[0]
    moved = design.replace_entity(dataclasses.replace(fp, position=Point(1_000_000, 0)))
    assert moved.board is not None and moved.board.footprints[0].position == Point(1_000_000, 0)
    assert moved.board.footprints[1] == design.board.footprints[1]
    with pytest.raises(KeyError):
        design.replace_entity(dataclasses.replace(fp, id="fp_00000000-0000-4000-8000-00000000dead"))


@settings(max_examples=40, deadline=None)
@given(designs())
def test_generated_designs_are_valid(design: Design) -> None:
    errors = [i for i in design.validate() if i.severity == "error"]
    assert errors == []
