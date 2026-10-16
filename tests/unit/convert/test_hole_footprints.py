# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Imported board holes back as the board-only footprints of a conversion to KiCad (capability
design-conversion; change c0168, Decision 6: ``convert.to_kicad.hole_footprints``)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.convert.report import census
from fenolite.convert.to_kicad import hole_footprints
from fenolite.core.ids import derived_id
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
SLOTS = ROOT / "tests" / "data" / "slots" / "slots_altium.PcbDoc"
BOARD6 = ROOT / "tests" / "data" / "altium" / "board6" / "board6.PcbDoc"


def _import(path: Path) -> Design:
    data = path.read_bytes()
    return import_board(read_pcbdoc(data), file=path.name, sha256=hashlib.sha256(data).hexdigest())


def test_each_hole_is_the_footprint_the_import_made_before() -> None:
    design = _import(SLOTS)
    assert design.board is not None and len(design.board.holes) == 4 and not design.board.footprints
    back = hole_footprints(design)
    assert back.board is not None and not back.board.holes
    footprints = back.board.footprints
    assert [fp.native_ids["altium"] for fp in footprints] == [f"fp:pad#{i}" for i in range(4)]
    for fp in footprints:
        assert fp.id == derived_id("fp", "altium", fp.native_ids["altium"])
        assert fp.attributes == ("board_only",) and fp.lib_ref == "" and fp.rotation == 0
        (pad,) = fp.pads
        assert pad.number == "" and pad.kind == "np_thru_hole" and pad.layers == ("F.Cu", "B.Cu")
        assert pad.native_ids["altium"].startswith("pad:") and pad.id == derived_id(
            "pad", "altium", pad.native_ids["altium"]
        )
    slots = [fp.pads[0] for fp in footprints if fp.pads[0].shape == "oval"]
    assert sorted(p.rotation for p in slots) == [0, 30_000_000, 90_000_000]
    assert all(p.padstack is not None and p.padstack.hole_shape == "slot" for p in slots)
    assert [c.native_ids["altium"] for c in back.circuit.components] == [f"cmp:fp:pad#{i}" for i in range(4)]
    counts = census(back)
    assert (counts["footprint"], counts["pad"]) == (4, 4)


def test_the_holes_of_a_six_layer_board_take_its_copper_layers() -> None:
    back = hole_footprints(_import(BOARD6))
    assert back.board is not None and not back.board.holes
    (fp,) = [fp for fp in back.board.footprints if fp.attributes == ("board_only",)]
    assert fp.pads[0].layers == ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")


def test_a_design_without_holes_is_returned_as_it_is() -> None:
    design = _import(BOARD6)
    plain = hole_footprints(design)
    assert hole_footprints(plain) is plain
