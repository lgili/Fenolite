# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A free pad that came through an Altium to KiCad conversion is written back as a free pad (capability
altium-pcb-writer, "Free pads of a converted board"; change c0447).

The fixture is the authored Altium sample ``tests/data/altium/routed``, with two footprints added: one in
the form the conversion gives a free pad (link ``routed:FREE_…``, no component, one pad of a net) and one of
the same link form placed for a component with a reference."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fenolite.backends.altium import lower
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.core.libnames import FREE_PAD_PREFIX
from fenolite.model.board import FootprintInstance
from fenolite.model.circuit import Component
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
ROUTED = ROOT / "tests" / "data" / "altium" / "routed" / "routed.PcbDoc"


def _with_free_pads() -> tuple[Design, FootprintInstance, str]:
    """The routed sample with a converted free pad and a component ``R9`` linked like one; the free
    footprint and the name of its pad's net."""
    design = AltiumBackend().read(ROUTED).design
    board = design.board
    assert board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    source = next(fp for fp in board.footprints if any(pad.net_id for pad in fp.pads))
    pad = next(pad for pad in source.pads if pad.net_id)
    free = FootprintInstance(
        id=derived_id("fp", "c0447", "free"),
        component_id="",
        lib_ref=f"routed:{FREE_PAD_PREFIX}fp_1",
        position=Point(source.position.x + 5_000_000, source.position.y),
        pads=(dataclasses.replace(pad, id=derived_id("pad", "c0447", "free"), position=Point(0, 0)),),
    )
    component = Component(
        id=derived_id("cmp", "c0447", "R9"), ref="R9", value="1k", lib_symbol_ref="", lib_footprint_ref=""
    )
    named = dataclasses.replace(
        source,
        id=derived_id("fp", "c0447", "R9"),
        component_id=component.id,
        lib_ref=f"routed:{FREE_PAD_PREFIX}fp_2",
        position=Point(source.position.x, source.position.y + 5_000_000),
        pads=(dataclasses.replace(pad, id=derived_id("pad", "c0447", "R9")),),
        fields=(),
    )
    circuit = dataclasses.replace(design.circuit, components=(*design.circuit.components, component))
    board = dataclasses.replace(board, footprints=(*board.footprints, free, named))
    return dataclasses.replace(design, circuit=circuit, board=board), free, names[pad.net_id or ""]


def test_a_converted_free_pad_is_written_free() -> None:
    """Scenario "A converted free pad": the ``FREE_`` footprint without a reference is one free pad of its
    net, counted changed with ``FREE_PAD_REASON``; the footprint of ``R9`` stays a component."""
    design, free, net = _with_free_pads()
    before = AltiumBackend().read(ROUTED).design
    inputs = lower.from_design(design, issues=[])
    assert inputs.pcb is not None
    assert [(p.pad.id, p.net) for p in inputs.pcb.free_pads] == [(free.pads[0].id, net)]
    assert inputs.changed["footprint"][lower.FREE_PAD_REASON] == (free.id,)
    refs = [c.ref for c in inputs.pcb.components]
    assert "R9" in refs and "" not in refs
    assert len(refs) == len(before.circuit.components) + 1


def test_converted_free_pad_test() -> None:
    """``converted_free_pad`` asks for no reference, one pad and a link item that starts with the prefix."""
    design, free, _ = _with_free_pads()
    assert lower.converted_free_pad(free, "")
    assert not lower.converted_free_pad(free, "R9")
    assert not lower.converted_free_pad(dataclasses.replace(free, lib_ref="routed:fp_1"), "")
    assert not lower.converted_free_pad(dataclasses.replace(free, pads=free.pads * 2), "")
    assert lower.converted_free_pad(dataclasses.replace(free, lib_ref=f"{FREE_PAD_PREFIX}x"), "")
    assert design.board is not None
