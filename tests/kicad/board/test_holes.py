# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Holes on the running ``kicad-cli`` (capability kicad-oracle, "Outline shapes and holes pass the oracle";
hypotheses H-K-HOLE-FOOTPRINT, H-K-HOLE-COURTYARD and H-K-HOLE-SYMBOL; change c0102).

The board is that of ``_holebench``: each probe records the board built with authored footprints, and the
same holes declared with ``design.hole()`` must give the same outcome."""

from __future__ import annotations

import _holebench as hb
import pytest
from _probes import run

from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad


def test_root_pad_does_not_load() -> None:
    assert run("hole-root-pad") == "reject", "KiCad loads a pad outside every footprint"


def test_drill_files() -> None:
    assert run("hole-drill") == "equal", "the holes are not drilled as declared"
    assert hb.drill("script") == "equal", "the holes of design.hole() are drilled differently"


def test_pos_file_lists_no_hole() -> None:
    assert run("hole-pos") == "absent", "a hole is in the position file"
    assert hb.position_file("script") == "absent", "a hole of design.hole() is in the position file"


def test_facts_of_the_test_file() -> None:
    """IPC-D-356 gives one ``367`` record per pad that is not plated: five on this board."""
    for form in hb.FORMS:
        assert hb.test_records(form) == 5, form


@pytest.mark.parametrize("side", ["top", "bottom", "clear"])
def test_courtyard_on_both_sides(side: str) -> None:
    wanted = "absent" if side == "clear" else "present"
    assert run(f"hole-courtyard-{side}") == wanted
    assert hb.courtyard(side, "script") == wanted, "the courtyards of design.hole() are judged differently"


def test_symbol_library_loads() -> None:
    assert run("hole-symbol-load") == "equal", "KiCad does not export the two hole symbols"
    assert hb.symbol_load("script") == "equal"


def test_the_two_forms_hold_the_same_holes() -> None:
    def pads(form: str) -> list[tuple[str, str, object, object]]:
        board = read_board(hb.board_of(form))
        assert board.board is not None
        refs = {c.id: c.ref for c in board.circuit.components}
        return sorted(
            (refs[fp.component_id], pad.kind, pad.size, pad.drill)
            for fp in board.board.footprints
            if refs[fp.component_id].startswith("H")
            for pad in fp.pads
        )

    assert pads("authored") == pads("script") and len(pads("script")) == 6
