# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A board cut-out that crosses the board shape is a notch of it, and a text's CR LF line breaks are
line feeds (change c0427). The source is the committed ``tests/data/kicad/board/two_layer.kicad_pcb``
with an authored cut-out, written to Altium by Fenolite."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.api import convert, run
from fenolite.backends.altium.adapter.copper import NOTCH_LOCATOR, lines
from fenolite.backends.altium.backend import AltiumBackend

ROOT = Path(__file__).resolve().parents[4]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
ACROSS = "(xy -2 10) (xy 3 10) (xy 3 14) (xy -2 14)"  # over the left edge (x = 0) of the 50 x 30 mm board
INSIDE = "(xy 20 10) (xy 25 10) (xy 25 14) (xy 20 14)"


def _altium(tmp_path: Path, ring: str) -> Path:
    text = BOARD.read_text(encoding="utf-8")
    cut = (
        f'\t(gr_poly (pts {ring}) (stroke (width 0.05) (type solid)) (fill no) (layer "Edge.Cuts") '
        '(uuid "6c1e3d0a-0427-4b01-8000-000000000011"))\n'
    )
    end = text.rindex(")")
    source = tmp_path / "kicad" / "notch.kicad_pcb"
    source.parent.mkdir()
    source.write_text(text[:end] + cut + text[end:], encoding="utf-8")
    conversion = convert(source, to="altium", allow_lossy=True).conversion
    for name, data in conversion.files.items():
        target = tmp_path / "altium" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return tmp_path / "altium" / "notch.PcbDoc"


def test_a_cut_out_across_the_board_edge_is_a_notch(tmp_path: Path) -> None:
    pytest.importorskip("pyclipper")
    read = AltiumBackend().read(_altium(tmp_path, ACROSS))
    board = read.design.board
    assert board is not None
    edges = [g for g in board.graphics if g.layer == "Edge.Cuts"]
    assert {g.kind for g in edges} == {"line"} and len(edges) == 8  # the rectangle with a 3 x 4 mm bite
    assert all(g.provenance is not None and g.provenance.locator.startswith(NOTCH_LOCATOR) for g in edges)
    xs = sorted({p.x for g in edges for p in g.points})
    # the Altium writer moves the board by its origin and rounds to its 0.0001 mil unit
    wanted = (0, 3_000_000, 50_000_000)
    assert len(xs) == 3 and all(abs(x - xs[0] - want) <= 2 for x, want in zip(xs, wanted, strict=True))
    assert [i.code for i in read.issues].count("altium.import.cutout-notch") == 1


def test_a_cut_out_inside_the_board_stays_a_cut_out(tmp_path: Path) -> None:
    pytest.importorskip("pyclipper")
    read = AltiumBackend().read(_altium(tmp_path, INSIDE))
    board = read.design.board
    assert board is not None
    kinds = sorted(g.kind for g in board.graphics if g.layer == "Edge.Cuts")
    assert kinds.count("polygon") == 1
    assert "altium.import.cutout-notch" not in [i.code for i in read.issues]


def test_the_notched_board_imports_as_code(tmp_path: Path) -> None:
    pytest.importorskip("pyclipper")
    document = _altium(tmp_path, ACROSS)
    reply = run("import", str(document), "--to", "python", "--out", "out", "--dry-run", cwd=tmp_path)
    assert reply.exit_code == 0, reply.error
    assert reply.result is not None and reply.result["unexpressed"] == []
    assert reply.result["equivalence"]["equivalent"] is True


def test_a_crlf_line_break_is_a_line_feed() -> None:
    assert lines("TOP\r\nSIDE") == "TOP\nSIDE"
    assert lines("one line") == "one line"
