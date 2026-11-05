# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The footprint texts of an Altium to KiCad conversion against ``kicad-cli`` (capability design-conversion,
"Footprint texts of an imported footprint"; change c0422; hypothesis ``H-K-PCB-FPGFX``). The source is the
authored document of ``tests/_fpcontent.py``. The converted board loads on the running major, and a 10.0
re-save (``pcb upgrade --force``, from 10.0 only) keeps every ``fp_text user`` with its string, layer, angle
and mirror (``board.md``, ``H-K-FIELD-RESAVE``: a re-save keeps visible user texts)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _fpcontent import TEXTS, altium_document, converted
from _kicad import loads, run
from _resources import kicad_cli_major

from fenolite.backends.kicad import load

pytestmark = pytest.mark.needs_kicad


def _texts(board: Path) -> list[tuple[str, str, str, bool]]:
    """``(string, layer, at, mirrored)`` of every ``fp_text`` of the board, sorted."""
    found: list[tuple[str, str, str, bool]] = []
    for footprint in load(board).nodes("footprint"):
        for text in footprint.nodes("fp_text"):
            layer, at, effects = text.find("layer"), text.find("at"), text.find("effects")
            assert layer is not None and at is not None and effects is not None
            justify = effects.find("justify")
            mirrored = justify is not None and "mirror" in [a.value for a in justify.atoms()]
            place = " ".join(a.value for a in at.atoms())
            found.append((text.atoms()[1].value, layer.atoms()[0].value, place, mirrored))
    return sorted(found)


def _converted(tmp_path: Path) -> Path:
    major = kicad_cli_major() or 10
    return converted(altium_document(tmp_path / "src"), tmp_path / "out", kicad_version=major)


def test_the_converted_board_loads_with_its_footprint_texts(tmp_path: Path) -> None:
    board = _converted(tmp_path)
    texts = _texts(board)
    assert len(texts) == TEXTS
    assert [t[3] for t in texts if t[1].startswith("B.")] == [True]
    assert loads(board)


@pytest.mark.kicad_min_major(10)
def test_a_resave_keeps_the_footprint_texts(tmp_path: Path) -> None:
    board = _converted(tmp_path)
    before = _texts(board)
    run("pcb", "upgrade", "--force", board)
    assert _texts(board) == before
