# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Blind and buried vias of the Altium PCB document (capability altium-pcb-writer, "Blind and buried via
records"; change c0085)."""

from __future__ import annotations

import dataclasses

import pytest
from _altium_board6 import LAYERS, at, bare_spec, imported_point, near, read_back

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.pcbdoc import write_pcbdoc
from fenolite.model.board import Via


def via(key: str, x: float, layers: tuple[str, ...], kind: str = "through", **changes: object) -> Via:
    fields: dict[str, object] = {
        "id": f"via_{key}",
        "position": at(x, 10),
        "diameter": 600_000,
        "drill": 300_000,
        "layers": layers,
        "via_type": kind,
    }
    return Via(**{**fields, **changes})  # type: ignore[arg-type]


THREE = (
    via("a", 10, ("F.Cu", "B.Cu")),
    via("b", 12, ("F.Cu", "In1.Cu"), "blind"),
    via("c", 14, ("In1.Cu", "In2.Cu"), "buried"),
)


def test_three_spans() -> None:
    """Scenario "Three spans": the three vias have their spans and the board record three drill pairs."""
    document, design = read_back(bare_spec(copper_layers=LAYERS, vias=THREE))
    assert [(v.start_layer, v.end_layer) for v in document.vias] == [(1, 32), (1, 2), (2, 3)]
    assert document.board.layer_pairs == (("TOP", "BOTTOM"), ("TOP", "MID1"), ("MID1", "MID2"))
    assert design.board is not None
    found = {(v.layers, v.via_type) for v in design.board.vias}
    assert found == {(v.layers, v.via_type) for v in THREE}
    for wanted in THREE:
        (read,) = [v for v in design.board.vias if v.layers == wanted.layers]
        assert near(read.position, imported_point(wanted.position))
        assert abs(read.diameter - wanted.diameter) <= 2 and abs(read.drill - wanted.drill) <= 2


def test_one_drill_pair_per_distinct_span() -> None:
    vias = (*THREE, via("d", 16, ("In1.Cu", "F.Cu"), "blind"), via("e", 18, ("In4.Cu", "B.Cu"), "blind"))
    document, _ = read_back(bare_spec(copper_layers=LAYERS, vias=vias))
    assert document.board.layer_pairs == (
        ("TOP", "BOTTOM"), ("TOP", "MID1"), ("MID1", "MID2"), ("MID4", "BOTTOM"),
    )  # fmt: skip
    assert [(v.start_layer, v.end_layer) for v in document.vias].count((1, 2)) == 2  # upper layer first


def test_a_through_via_keeps_its_bytes() -> None:
    """A through via is written as before change c0085, and a document of through vias has one pair."""
    assert pcbrecords.via_record(1, 2, 3, 4) == pcbrecords.via_record(1, 2, 3, 4, start=1, end=32)
    body = pcbrecords.via_record(1, 2, 60, 30, start=2, end=39)[5:]
    assert (body[29], body[30], len(body)) == (2, 39, pcbrecords.VIA_SIZE)
    document, _ = read_back(bare_spec(copper_layers=LAYERS, vias=THREE[:1]))
    assert document.board.layer_pairs == (("TOP", "BOTTOM"),)
    assert b"LAYERPAIR1" not in document.board.raw


def test_a_via_may_end_on_a_plane() -> None:
    stack_ids = pcbrecords.copper_stack(LAYERS, ("In2.Cu",))
    from fenolite.backends.altium.libboard import StackSpec

    spec = bare_spec(
        copper_layers=LAYERS,
        stack=StackSpec.default(stack_ids, ("GND",)),
        nets=("GND",),
        vias=(via("p", 10, ("In1.Cu", "In2.Cu"), "buried", net_id="GND"),),
    )
    document, _ = read_back(spec)
    assert [(v.start_layer, v.end_layer) for v in document.vias] == [(2, 39)]
    assert document.board.layer_pairs[1] == ("MID1", "PLANE1")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"via_type": "micro", "layers": ("F.Cu", "In1.Cu")}, "via_bad: a micro via is not written"),
        ({"layers": ("F.Cu", "In9.Cu")}, "via_bad: the via spans F.Cu, In9.Cu"),
        ({"layers": ("F.Cu",)}, "via_bad: the via spans F.Cu, not two copper layers"),
    ],
)
def test_vias_the_writer_refuses(changes: dict[str, object], message: str) -> None:
    bad = dataclasses.replace(via("bad", 10, ("F.Cu", "B.Cu")), **changes)
    with pytest.raises(ValueError, match=message):
        write_pcbdoc(bare_spec(copper_layers=LAYERS, vias=(bad,)))
    with pytest.raises(ValueError, match="layer 33 is not a copper layer"):
        pcbrecords.via_record(0, 0, 60, 30, start=1, end=33)
