# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots and cut-outs converted to Altium and back on the running ``kicad-cli`` (capability
design-conversion, "Slots and cut-outs in a conversion"; hypothesis H-K-CONV-SLOTS; change c0170).

The boards are those of ``_slotsconv``."""

from __future__ import annotations

import tempfile
from pathlib import Path

import _slotsconv as sc
import pytest
from _outlinebench import drc, types
from _probes import run

pytestmark = pytest.mark.needs_kicad


def test_the_round_trip_keeps_every_ring() -> None:
    """The fixture's three inner rings are written as regions and come back as three cut-outs; its holes
    come back as the footprints of ``design.hole``."""
    altium, back = sc.round_trip(sc.major())
    row = altium.report.row("cutout")
    assert row is not None and (row.source, row.lost) == (3, 0)
    row = back.report.row("cutout")
    assert row is not None and (row.source, row.written) == (3, 3)
    names = sorted(name for name in back.files if name.startswith("lib/Fenolite_Holes.pretty/"))
    assert names == [
        "lib/Fenolite_Holes.pretty/NPTH_3.2mm.kicad_mod",
        "lib/Fenolite_Holes.pretty/NPTH_Slot_1x3mm.kicad_mod",
    ]


def test_the_converted_board_has_no_invalid_outline() -> None:
    assert run("convert-slots-drc") == "absent", sc.returned_types()


def test_the_converted_board_drills_what_the_source_drills() -> None:
    assert run("convert-slots-drill") == "equal", sc.drill_pair()


def test_overlapping_altium_cutouts_load_merged() -> None:
    """Scenario "Overlapping Altium cut-outs to KiCad", its KiCad half: the merged ring loads with no
    ``invalid_outline``. The merge needs the ``geo`` extra."""
    pytest.importorskip("pyclipper")
    from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
    from fenolite.convert import convert_project
    from fenolite.core.coords import Point
    from fenolite.model.board import Hole

    mm = 1_000_000
    ring = (Point(0, 0), Point(60 * mm, 0), Point(60 * mm, 40 * mm), Point(0, 40 * mm))
    a = (Point(10 * mm, 10 * mm), Point(20 * mm, 10 * mm), Point(20 * mm, 15 * mm), Point(10 * mm, 15 * mm))
    b = (Point(15 * mm, 12 * mm), Point(25 * mm, 12 * mm), Point(25 * mm, 20 * mm), Point(15 * mm, 20 * mm))
    hole = Hole(
        id="hol_c0170", position=Point(40 * mm, 30 * mm), drill=mm, length=3 * mm, rotation=30_000_000
    )
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "overlap.PcbDoc"
        path.write_bytes(
            write_pcbdoc(PcbDocSpec(outline=ring, cutouts=(a, b), holes=(hole,)), filename=path.name)
        )
        conversion = convert_project(path, to="kicad", kicad_version=sc.major())
    report = drc(dict(conversion.files), conversion.read_back)
    assert report is not None
    assert "invalid_outline" not in types(report), types(report)
