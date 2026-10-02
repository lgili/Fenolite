# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The layout against the written board, by keys (change c0019, task 9.2): references, component paths,
positions, rotations, sides, locks and properties; and each pin's net against the nets of its numbered
pads, board-only footprints included (the agreement that c0020's netlist pair relies on)."""

from __future__ import annotations

import pytest
from _board_only import add_h1
from _buildhelp import (
    blink,
    build,  # noqa: I001
)
from _layout_edit import edit_blink
from _preserve_help import board_text, prepared

from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.pcb import read_board
from fenolite.model.design import Design


def by_ref(design: Design) -> dict[str, tuple[object, ...]]:
    assert design.board is not None
    comps = {c.id: c for c in design.circuit.components}
    return {
        comps[fp.component_id].ref: (
            comps[fp.component_id].properties.get(PATH_PROPERTY),
            fp.position,
            fp.rotation,
            fp.side,
            fp.locked,
            dict(comps[fp.component_id].properties),
        )
        for fp in design.board.footprints
    }


def pin_nets(design: Design) -> dict[str, str]:
    refs = {c.id: c.ref for c in design.circuit.components}
    return {f"{refs[m.component_id]}-{m.pin}": n.name for n in design.circuit.nets for m in n.members}


def pad_nets(design: Design) -> dict[str, str]:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    names = {n.id: n.name for n in design.circuit.nets}
    return {
        f"{refs[fp.component_id]}-{p.number}": names[p.net_id]
        for fp in design.board.footprints
        for p in fp.pads
        if p.number and p.net_id
    }


@pytest.mark.parametrize("target", [9, 10])
def test_layout_against_the_written_board(target: int) -> None:
    d = blink()
    text = add_h1("H1")(board_text(target, edit=edit_blink))
    ready = prepared(d, text, target=target)
    output = build(d, target, prepared=ready, placements_override=ready.placements)
    assert output.layout is not None
    back = read_board(output.files["blink.kicad_pcb"].decode("utf-8"))
    assert by_ref(output.layout) == by_ref(back)
    assert "H1" in by_ref(back)
    assert pin_nets(output.layout) == pad_nets(output.layout)
    assert pin_nets(output.layout)["H1-1"] == "GND"
