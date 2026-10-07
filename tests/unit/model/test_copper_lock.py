# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``locked`` on tracks, arcs and vias (change c0108; capability design-model, "Copper locks in the board
model")."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model import canonical
from fenolite.model.board import Arc, Board, Track, Via

ROOT = Path(__file__).resolve().parents[3]
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
OLD_FIXTURE = ROOT / "tests" / "data" / "model" / "v0.2.0" / "blink_2layer.board.json"
SCHEMA = ROOT / "schemas" / "fenolite.model.v0" / "board.json"
TRACK = Track(id="trk_1", start=Point(0, 0), end=Point(1_000_000, 0), width=250_000, layer="F.Cu")
ARC = Arc(id="arc_1", start=Point(0, 0), mid=Point(500_000, 500_000), end=Point(1_000_000, 0),
          width=250_000, layer="F.Cu")  # fmt: skip
VIA = Via(id="via_1", position=Point(0, 0), diameter=600_000, drill=300_000, layers=("F.Cu", "B.Cu"))


def test_copper_lock_default_is_unlocked() -> None:
    """Scenario "Default is unlocked"; ``locked`` is the last field of each of the three."""
    for item in (TRACK, ARC, VIA):
        assert item.locked is False
        assert dataclasses.replace(item, locked=True) != item
        assert dataclasses.fields(item)[-1].name == "locked"


def test_copper_lock_is_written_only_when_true() -> None:
    """A design without a locked item serialises to the bytes it had: the key is absent."""
    board = Board(id="brd_1", tracks=(TRACK,), arcs=(ARC,), vias=(VIA,))
    text = canonical.dumps(board)
    assert '"locked"' not in text
    locked = dataclasses.replace(
        board,
        tracks=(dataclasses.replace(TRACK, locked=True),),
        arcs=(dataclasses.replace(ARC, locked=True),),
        vias=(dataclasses.replace(VIA, locked=True),),
    )
    assert (
        canonical.dumps(locked).count('"locked":true') + canonical.dumps(locked).count('"locked": true') == 3
    )
    assert canonical.loads(canonical.dumps(locked), Board) == locked
    assert canonical.loads(text, Board) == board


def test_copper_lock_old_documents_still_load() -> None:
    """Scenario "Old documents still load": a document without the key, here the board of the authored
    fixture written without a lock, loads with every item unlocked and keeps its bytes."""
    design = read_board(TWO_LAYER)
    assert design.board is not None and design.board.tracks and design.board.arcs and design.board.vias
    text = canonical.dumps(design.board)
    assert '"locked"' not in text.replace('"locked":false', "")
    loaded = canonical.loads(text, Board)
    assert all(not item.locked for item in (*loaded.tracks, *loaded.arcs, *loaded.vias))
    assert canonical.dumps(loaded) == text


def test_copper_lock_fixture_of_0_2_0_keeps_its_bytes() -> None:
    """Scenario "A design without locks keeps its bytes", on the fixture of change c0126. That change is
    not on this base: the test runs once its fixture exists."""
    if not OLD_FIXTURE.is_file():
        pytest.skip("tests/data/model/v0.2.0/blink_2layer.board.json comes with change c0126")
    text = OLD_FIXTURE.read_text(encoding="utf-8")
    assert canonical.dumps(canonical.loads(text, Board)) == text


def test_copper_lock_in_the_schema() -> None:
    """Scenario "Schemas regenerated": the three definitions list ``locked`` as a boolean."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for name in ("Track", "Arc", "Via"):
        assert schema["$defs"][name]["properties"]["locked"]["type"] == "boolean", name


def test_copper_lock_sentence_in_the_design_model_page() -> None:
    page = (ROOT / "docs" / "design-model.md").read_text(encoding="utf-8")
    assert "cannot read a model document that carries the key `locked`" in " ".join(page.split())
