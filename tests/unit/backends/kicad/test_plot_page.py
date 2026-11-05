# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The page of an SVG plot (capability manufacturing-exports, "Board-area render page"; change c0409, B11).
A board whose outline reaches outside its drawing page, such as one at an Altium origin with negative Y, is
plotted on its board area alone (``--exclude-drawing-sheet --page-size-mode 2``); ``render --page`` chooses.
The boards are authored here; the render runs against the fake ``kicad-cli``."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from _checkcli import hide_kicad, run
from _fakecli import calls, fake_kicad_cli
from _projects import authored_project

from fenolite.backends.kicad.plot import BOARD_PAGE, VIEWS, board_page, svg_arguments


def _board(paper: str, *shapes: str) -> str:
    return f"(kicad_pcb (version 20241229) (generator test) (paper {paper})\n" + "\n".join(shapes) + ")\n"


def _rect(x1: float, y1: float, x2: float, y2: float) -> str:
    return f'(gr_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.1)) (layer "Edge.Cuts"))'


def test_board_page_flags() -> None:
    sheet = svg_arguments(VIEWS["front.svg"])
    board = svg_arguments(VIEWS["back.svg"], "board")
    assert not set(BOARD_PAGE) & set(sheet)
    assert board[board.index("--exclude-drawing-sheet") :][:3] == list(BOARD_PAGE)
    assert board[-2:] == ["-o", "render/back.svg"]


@pytest.mark.parametrize(
    ("text", "page"),
    [
        (_board('"A4"', _rect(10, 10, 60, 40)), "sheet"),
        (_board('"A4"', _rect(10, -50, 60, -10)), "board"),
        (_board('"A4"', _rect(250, 10, 290, 40)), "sheet"),
        (_board('"A4" portrait', _rect(250, 10, 290, 40)), "board"),
        (_board('"User" 100 80', _rect(10, 10, 120, 40)), "board"),
        (_board('"A4"', '(gr_circle (center 5 100) (end 15 100) (layer "Edge.Cuts"))'), "board"),
        (_board('"A4"', '(gr_line (start -5 10) (end 20 10) (layer "F.SilkS"))'), "sheet"),
        (_board('"A4"'), "sheet"),
        ("not a board", "sheet"),
    ],
)
def test_board_page(text: str, page: str) -> None:
    assert board_page(text) == page


def _move_outline(board: Path) -> None:
    """Shrink the board's page to 10 mm by 10 mm, so its outline reaches outside it."""
    text = board.read_text(encoding="utf-8")
    shrunk, count = re.subn(r'\(paper "[^"]+"[^)]*\)', '(paper "User" 10 10)', text)
    assert count == 1
    board.write_text(shrunk, encoding="utf-8")


@pytest.mark.parametrize(("moved", "option", "flags"), [(False, (), False), (True, (), True),
                                                       (True, ("--page", "sheet"), False),
                                                       (False, ("--page", "board"), True)])  # fmt: skip
def test_render_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, moved: bool, option: tuple[str, ...], flags: bool
) -> None:
    hide_kicad(monkeypatch, tmp_path)
    root = authored_project(tmp_path, major=10)
    board = next(root.glob("*.kicad_pcb"))
    if moved:
        _move_outline(board)
        assert board_page(board.read_text(encoding="utf-8")) == "board"
    else:
        assert board_page(board.read_text(encoding="utf-8")) == "sheet"
    fake = fake_kicad_cli(tmp_path / "bin")
    work = tmp_path / "work"
    work.mkdir()
    code, env, _, _ = run(monkeypatch, work, "render", str(root), "--out", "r", "--svg", *option,
                          "--kicad-cli", str(fake), "--confirm")  # fmt: skip
    assert code == 0, env
    assert env["result"]["svg_page"] == ("board" if flags else "sheet")
    svg = [c["args"] for c in calls(fake) if c["args"][:3] == ["pcb", "export", "svg"]]
    assert len(svg) == 2 and all(("--exclude-drawing-sheet" in a) == flags for a in svg)
    assert all(("--page-size-mode" in a) == flags for a in svg)
