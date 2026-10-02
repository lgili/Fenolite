# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Built boards read back with the same connectivity (capability design-dsl; change c0011), compared by
keys (reference, pad number, net name), because ids differ by design."""

from __future__ import annotations

import pytest
from _buildhelp import blink, build

from fenolite.backends.kicad.pcb import read_board
from fenolite.model.design import Design


def pairs(design: Design) -> dict[str, set[tuple[str, str]]]:
    refs = {c.id: c.ref for c in design.circuit.components}
    out: dict[str, set[tuple[str, str]]] = {}
    assert design.board is not None
    nets = {n.id: n.name for n in design.circuit.nets}
    for fp in design.board.footprints:
        for pad in fp.pads:
            if pad.net_id is not None:
                out.setdefault(nets[pad.net_id], set()).add((refs[fp.component_id], pad.number))
    return out


@pytest.mark.parametrize("target", [9, 10])
def test_blink_reads_back(target: int) -> None:
    out = build(blink(), target)
    back = read_board(out.files["blink.kicad_pcb"].decode("utf-8"))
    assert pairs(back) == pairs(out.design)
    assert pairs(back)["LED_A"] == {("R1", "2"), ("D1", "2")}
    built = {c.ref: c for c in out.design.circuit.components}
    for c in back.circuit.components:
        b = built[c.ref]
        assert (c.value, c.lib_footprint_ref, c.properties, c.path) == (
            b.value,
            b.lib_footprint_ref,
            b.properties,
            "",
        )
    assert back.board is not None and out.design.board is not None
    key = {fp.lib_ref: (fp.position, fp.rotation, fp.side, fp.locked) for fp in out.design.board.footprints}
    assert {fp.lib_ref: (fp.position, fp.rotation, fp.side, fp.locked) for fp in back.board.footprints} == key


def test_staged_parts_read_back() -> None:
    d = blink()
    d.parts["R1"].request = None
    out = build(d)
    back = read_board(out.files["blink.kicad_pcb"].decode("utf-8"))
    built = next(fp for fp in out.design.board.footprints if fp.lib_ref.endswith("R_0603"))  # type: ignore[union-attr]
    r1 = next(fp for fp in back.board.footprints if fp.lib_ref.endswith("R_0603"))  # type: ignore[union-attr]
    assert (r1.position, r1.side, r1.rotation, r1.locked) == (built.position, "top", 0, False)
