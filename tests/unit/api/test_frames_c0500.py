# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Frames and units of a board, and islands from Python (capability python-api, "Frames and units" and
"Islands from Python"; change c0500). The boards are authored for Fenolite: the Part J kit board and the
committed KiCad sample."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite import api
from fenolite.backends.altium import edit
from fenolite.core.coords import Point
from tests.unit.backends.altium.edit.conftest import OPEN
from tests.unit.backends.altium.test_part_j import build_board

ROOT = Path(__file__).resolve().parents[3]
KICAD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


@pytest.fixture(scope="module")
def board(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The Part J kit board (``ORIGINX=ORIGINY=1000mil``), read only here."""
    folder = tmp_path_factory.mktemp("kit") / "board"
    build_board(folder)
    return folder / "edit.PcbDoc"


def test_altium_point_in_every_frame(board: Path) -> None:
    """Scenario "A point of an Altium document": the kit board holds ``ORIGINX=ORIGINY=1000mil``."""
    frame = api.board_frame(board)
    assert frame.y_up and frame.origin == Point(25_400_000, -25_400_000)
    model = frame.from_native(12_000_000, 15_000_000)
    assert model == Point(30_480_000, -38_100_000)
    assert frame.to_board(model) == Point(5_080_000, 12_700_000)
    assert frame.from_board(frame.to_board(model)) == model
    assert frame.to_native(model) == (12_000_000, 15_000_000)


def test_units_are_those_of_core() -> None:
    assert api.altium_to_nm(10_000) == 25_400 and api.nm_to_altium(25_400) == 10_000
    assert api.parse_length("1mm") == 1_000_000 and api.format_length(1_000_000, "mm") == "1mm"


def test_kicad_board_frame_is_the_model_frame() -> None:
    """Scenario "A KiCad board"."""
    frame = api.board_frame(KICAD)
    assert frame.to_board(Point(1, 2)) == Point(1, 2) and not frame.y_up
    with pytest.raises(api.SideUsageError):
        frame.from_native(0, 0)


def test_edit_session_names_each_free_track_by_to_board(board: Path, tmp_path: Path) -> None:
    """Scenario "The edit session's frame": every free track, named by ``to_board`` of its model ends, is
    matched by the session to exactly one record (a width change stated with its old width commits)."""
    read = api.read_board(board)
    frame = api.board_frame(read)
    assert read.design.board is not None
    names = {n.id: n.name for n in read.design.circuit.nets}
    free = [t for t in read.design.board.tracks if t.net_id in names]
    assert free
    for n, track in enumerate(free):
        start, end = frame.to_board(track.start), frame.to_board(track.end)
        item = edit.Track((start.x, start.y), (end.x, end.y), names[track.net_id])
        session = edit.open(board, gates=OPEN)
        assert isinstance(session, edit.Session)
        receipt = session.set_property(item, "width", track.width + 2_540, old=track.width).commit(
            tmp_path / f"t{n}.PcbDoc", backup=False
        )
        assert receipt.written, (track.id, receipt.issues)


def test_islands_agree_with_connectivity(board: Path) -> None:
    """``islands`` gives the islands ``connectivity`` counts, with members; an unknown name raises."""
    found = api.islands(board)
    report = api.connectivity(board)
    for net in report.nets:
        assert [i.pads for i in found[net.name]] == list(net.pads)
        assert all(i.members for i in found[net.name])
    with pytest.raises(KeyError, match="nothing-here"):
        api.islands(board, without=["nothing-here"])
