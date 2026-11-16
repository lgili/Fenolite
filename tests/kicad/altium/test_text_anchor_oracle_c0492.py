# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The anchor of an Altium stroke text against ``kicad-cli pcb import altium`` (change c0492, task 1.1;
hypothesis ``H-A-IMP-TEXT-ANCHOR``). The authored document of design D1 (``_textanchor``) is read by
Fenolite and imported by KiCad; the ink box of each designator, footprint text and free text is compared.
``pcb import`` exists from 10.0 only (S-0166). A pass checks what KiCad's importer reads."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from _pcbxcases import import_document
from _resources import kicad_cli_major
from _textanchor import STROKE, anchor_design, document, ink

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad import fpitems

pytestmark = pytest.mark.needs_kicad


def _kicad_ink(data: bytes) -> dict[str, tuple[int, int, int, int]]:
    found = import_document(data, "anchor.PcbDoc")
    assert found.code == 0, found.output
    assert found.text.count("(justify left bottom") >= 18, "every text keeps the lower-left anchor"
    return ink(fpitems.with_footprint_items(found.board).design)


def _within(mine: dict[str, tuple[int, int, int, int]], theirs: dict[str, tuple[int, int, int, int]]) -> None:
    assert set(mine) == set(theirs) and len(mine) == 18
    worst = {name: max(abs(a - b) for a, b in zip(mine[name], theirs[name], strict=True)) for name in mine}
    # KiCad 10.0.6 puts a 1 mm text 0.1225 mm along its height from Fenolite's reading: below one stroke
    assert max(worst.values()) <= STROKE, worst


def test_the_import_reads_the_anchor_kicad_reads() -> None:
    """Designators, footprint texts and free texts at 0°, 90°, 180° and 270° on both sides, mirrored on the
    bottom: Fenolite's reading, justified left and bottom, draws its ink where KiCad's import does."""
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    data = document(anchor_design())
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "anchor.PcbDoc"
        path.write_bytes(data)
        mine = AltiumBackend().read(path).design
    assert mine.board is not None
    items = [*mine.board.texts, *(t for fp in mine.board.footprints for t in (*fp.fields, *fp.texts))]
    assert {(t.h_justify, t.v_justify) for t in items} == {("left", "bottom")}
    _within(ink(mine), _kicad_ink(data))


def test_a_centred_text_is_written_at_its_corner() -> None:
    """Design D3: the same texts centred are written at the corner that puts KiCad's ink where the model's
    is, within one stroke width."""
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    design = anchor_design(("center", "center"))
    _within(ink(design), _kicad_ink(document(design)))
