# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board texts, drawings and dimensions in KiCad (``H-K-BOARD-TEXT``, ``H-K-DIM``; capability
kicad-oracle, "Board texts and dimensions are probed"; change c0103)."""

from __future__ import annotations

import _itemcases as ic
import pytest
from _probes import major, run

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import FileKind, check_emittable

pytestmark = pytest.mark.needs_kicad


def test_text_load() -> None:
    """Scenario "Texts on both majors": every layer and justification loads, and no violation names one."""
    bench, texts, report = ic.texts_run()
    assert report is not None and len(texts) == len(ic.TEXT_LAYERS) * len(ic.JUSTIFY)
    assert run("text-board-load") == "absent"


def test_text_height() -> None:
    assert run("text-height") == "present"


def test_text_on_copper_shorts() -> None:
    """Why a text is refused on copper: KiCad reports it as a short."""
    assert run("text-copper-short") == "present"


def test_graphic_on_copper_is_silent() -> None:
    """Why a drawing is refused on copper: KiCad does not report a copper line across a track."""
    assert run("graphic-copper-silent") == "absent"


def test_dimension_load() -> None:
    """Scenario "Dimensions on both majors"."""
    design = ic.dimensions_design()
    text = write_board(design, target=major()).text
    assert check_emittable(parse(text), FileKind.BOARD, major()) == ()
    read = read_board(text)
    assert read.board is not None and len(read.board.dimensions) == 4
    assert run("dim-load") == "present"


def test_dimension_text_is_recomputed() -> None:
    assert run("dim-recompute") == "equal"


def test_dimension_resave_text() -> None:
    if major() < 10:
        pytest.skip("pcb upgrade exists from 10.0")
    assert run("dim-resave-text") == "equal"
