# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The derived PCB library of a conversion (capability altium-pcb-writer, "Derived PCB library"; change
c0160, ``H-A-CONV-LIBRARY``).

The KiCad sample ``two_layer`` holds ``R1`` (``Fenolite_Test:R_0603``) and ``D1``; the tests add ``R2``, a
copy of ``R1`` elsewhere on the board, with or without a pad moved, and write the design with
``lower.write_design(..., library=True)``, as ``fenolite convert --to altium`` does.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fenolite.backends.altium import lower
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
MOVE = 100_000
"""0.1 mm."""


def _two_layer() -> Design:
    return fpitems.with_footprint_items(KicadBackend().read(TWO_LAYER).design).design


def _with_r2(design: Design, *, moved: bool) -> Design:
    """``design`` with ``R2``: ``R1`` copied 5 mm to the right, its pad ``2`` moved by 0.1 mm when
    ``moved``."""
    board = design.board
    assert board is not None
    r1 = next(c for c in design.circuit.components if c.ref == "R1")
    footprint = next(fp for fp in board.footprints if fp.component_id == r1.id)
    component = dataclasses.replace(
        r1, id=derived_id("cmp", "test", "R2"), ref="R2", native_ids={}, path="R2"
    )
    pads = tuple(
        dataclasses.replace(
            pad,
            id=derived_id("pad", "test", f"R2:{pad.number}"),
            native_ids={},
            net_id=None,
            position=Point(pad.position.x + MOVE, pad.position.y)
            if moved and pad.number == "2"
            else pad.position,
        )
        for pad in footprint.pads
    )
    copy = dataclasses.replace(
        footprint,
        id=derived_id("fp", "test", "R2"),
        native_ids={},
        component_id=component.id,
        position=Point(footprint.position.x + 5_000_000, footprint.position.y),
        pads=pads,
        graphics=tuple(
            dataclasses.replace(g, id=derived_id("gfx", "test", f"R2:{k}"), native_ids={})
            for k, g in enumerate(footprint.graphics)
        ),
        texts=(),
        fields=(),
        bodies=(),
    )
    circuit = dataclasses.replace(design.circuit, components=(*design.circuit.components, component))
    board = dataclasses.replace(board, footprints=(*board.footprints, copy))
    return dataclasses.replace(design, circuit=circuit, board=board)


def test_two_instances_one_edited() -> None:
    """Scenario "Two instances, one edited": the library holds one footprint ``R_0603`` with the pads of
    ``R1``, both components link it, and one footprint is counted ``changed``."""
    design = _with_r2(_two_layer(), moved=True)
    written = lower.write_design(design, allow_lossy=True, library=True)
    library = read_pcblib(written.files["two_layer.PcbLib"], file="two_layer.PcbLib")
    names = [footprint.name for footprint in library.footprints]
    assert sorted(names) == ["LED_THT_3mm", "R_0603"]
    r_0603 = next(footprint for footprint in library.footprints if footprint.name == "R_0603")
    r1 = next(
        fp
        for fp in design.board.footprints
        if fp.id != derived_id("fp", "test", "R2") and "R_0603" in fp.lib_ref
    )  # type: ignore[union-attr]
    xs = sorted(int(pad.x) * 127 // 50 for pad in r_0603.pads)
    # the pads of R1, not the moved pad of R2, within the 2.54 nm of a written unit
    assert all(abs(a - b) <= 3 for a, b in zip(xs, sorted(pad.position.x for pad in r1.pads), strict=True))
    document = read_pcbdoc(written.files["two_layer.PcbDoc"], file="two_layer.PcbDoc")
    links = {c.source_designator: (c.pattern, c.source_footprint_library) for c in document.components}
    assert links["R1"] == links["R2"] == ("R_0603", "two_layer.PcbLib")
    changed = written.inputs.changed["footprint"]
    assert changed == {lower.LIBRARY_CHANGED: (derived_id("fp", "test", "R2"),)}
    assert written.inputs.written["footprint"] == 2


def test_equal_instances_change_nothing() -> None:
    """Two equal instances give one library footprint and no ``changed`` footprint; the project file
    lists the library."""
    written = lower.write_design(_with_r2(_two_layer(), moved=False), allow_lossy=True, library=True)
    assert "footprint" not in written.inputs.changed
    assert b"DocumentPath=two_layer.PcbLib" in written.files["two_layer.PrjPcb"]
    library = read_pcblib(written.files["two_layer.PcbLib"], file="two_layer.PcbLib")
    assert sorted(footprint.name for footprint in library.footprints) == ["LED_THT_3mm", "R_0603"]


def test_reference_order() -> None:
    """The first instance is the first in reference order, digits by value: ``R2`` before ``R10``."""
    assert sorted(["R10", "R2", "C1", "R1"], key=lower.reference_key) == ["C1", "R1", "R2", "R10"]


def test_a_model_write_has_no_library() -> None:
    """Without ``library`` the write of a model is that of before: no ``.PcbLib``."""
    written = lower.write_design(_two_layer(), allow_lossy=True)
    assert not [name for name in written.files if name.endswith(".PcbLib")]
