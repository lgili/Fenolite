# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An arc whose three points lie on one line is written to Altium as the straight track it draws, not left
out (change c0435). The source is the committed ``tests/data/kicad/board/two_layer.kicad_pcb`` with its
first track replaced by an authored flat arc over the same two ends."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.altium import lower
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.checks.equivalence import compare_designs
from fenolite.checks.equivalence.model import Tolerances
from fenolite.core.coords import Point
from fenolite.lens.altium import write_model
from fenolite.model.board import Arc

ROOT = Path(__file__).resolve().parents[4]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
SEGMENT = "\t(segment\n\t\t(start 20 14.2)\n\t\t(end 30 14.2)\n"
FLAT = "\t(arc\n\t\t(start 20 14.2)\n\t\t(mid 25 14.2)\n\t\t(end 30 14.2)\n"


def _flat_board(tmp_path: Path) -> Path:
    text = BOARD.read_text(encoding="utf-8")
    assert text.count(SEGMENT) == 1
    board = tmp_path / "flat.kicad_pcb"
    board.write_text(text.replace(SEGMENT, FLAT), encoding="utf-8")
    return board


def test_straight_arc_is_the_track_it_draws() -> None:
    flat = Arc(id="a1", start=Point(0, 0), mid=Point(5, 0), end=Point(10, 0), width=250, layer="F.Cu")
    track = lower.straight_arc(flat)
    assert track is not None and (track.start, track.end, track.width) == (Point(0, 0), Point(10, 0), 250)
    beyond = Arc(id="a2", start=Point(0, 0), mid=Point(15, 0), end=Point(10, 0), width=250, layer="F.Cu")
    bent = Arc(id="a3", start=Point(0, 0), mid=Point(5, 3), end=Point(10, 0), width=250, layer="F.Cu")
    closed = Arc(id="a4", start=Point(0, 0), mid=Point(5, 0), end=Point(0, 0), width=250, layer="F.Cu")
    assert [lower.straight_arc(arc) for arc in (beyond, bent, closed)] == [None, None, None]


def test_a_flat_arc_is_written_as_a_track(tmp_path: Path) -> None:
    first = KicadBackend().read(_flat_board(tmp_path)).design
    assert first.board is not None
    (flat,) = [a for a in first.board.arcs if a.start.y == a.mid.y == a.end.y]
    written = write_model(first)
    assert not [i for i in written.issues if i.severity != "info"]  # no loss: no --allow-lossy needed
    assert written.inputs.changed["arc"][lower.ARC_STRAIGHT] == (flat.id,)
    assert "arc" not in written.inputs.not_lowered
    out = tmp_path / "altium"
    out.mkdir()
    for name, data in written.files.items():
        (out / name).write_bytes(data)
    second = AltiumBackend().read(out / "flat.PcbDoc").design
    assert second.board is not None and len(second.board.arcs) == len(first.board.arcs) - 1
    report = compare_designs(first, second, level=5, tolerances=Tolerances(length_nm=2), frame="relative")
    assert not [d for d in report.differences if d.code == "equiv.route-length"]
