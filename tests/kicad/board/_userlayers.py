# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""User layers on the running ``kicad-cli`` (hypothesis H-K-BOARD-USERLAYERS; change c0161, task 1.2).

A board of the two-copper table with ``User.1`` … ``User.<n>`` (``layers.user_rows``), one line on each
user layer, is written for the running major. ``n`` is ``layers.USER_LAYERS[major]``: the board must load
(``pcb export svg``), and the SVG of its last user layer, without the drawing sheet, must hold the one line
on it, where a control board without the line holds none. A board of ``n + 1`` user layers, numbered by the
same rule, is the negative control: KiCad refuses to load it.

The probe ``pcb-copper-32`` does the same for the copper rows of ``layers.board_rows``: a table of
``MAX_COPPER`` copper layers (``In30.Cu`` is 62) with a line on its last inner layer loads and draws the
line. It has no negative control: a table of 34 by the same rule loads too on both majors (measured on
2026-10-09), so 32 is Fenolite's bound, the most signal layers an Altium board holds, not KiCad's.
"""

from __future__ import annotations

import dataclasses
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.layers import (
    CREATED_ROWS,
    MAX_COPPER,
    USER_FIRST_NUMBER,
    USER_LAYERS,
    Row,
    board_rows,
    layers_of_rows,
    user_rows,
)
from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Graphic
from fenolite.model.design import Design

LINE_WIDTH = 100_000


def copper_rows(copper: int) -> tuple[Row, ...]:
    """The rows of ``board_rows(copper)``; a count above ``MAX_COPPER`` by the same rule, outside
    ``board_rows``, which refuses it."""
    if copper <= MAX_COPPER:
        return board_rows(copper)
    inner = tuple((2 * k + 2, f"In{k}.Cu", "signal", None) for k in range(1, copper - 1))
    return (*CREATED_ROWS[:1], *inner, *CREATED_ROWS[1:])


def board(count: int, target: int, *, lines: bool = True, copper: int = 2) -> str:
    """The text of the probe board of ``count`` user layers and ``copper`` copper layers for ``target``,
    with a line on each user layer and on the last inner copper layer. A count above the recorded one is
    numbered by the same rule, ``39 + 2(n − 1)``, outside ``user_rows``, which refuses it."""
    most = USER_LAYERS[target]
    rows = list(
        user_rows(min(count, most), target=target, names=[f"Mechanical {n}" for n in range(1, count + 1)])
    )
    rows += [(USER_FIRST_NUMBER + 2 * (n - 1), f"User.{n}", "user", None) for n in range(most + 1, count + 1)]
    design = Design.new("user-layers", seed=0)
    assert design.board is not None
    graphics = tuple(
        Graphic(
            id=derived_id("gfx", "fenolite", f"user-layer-line:{n}"),
            kind="line",
            layer=f"User.{n}",
            points=(Point(0, n * 1_000_000), Point(10_000_000, n * 1_000_000)),
            width=LINE_WIDTH,
        )
        for n in range(1, count + 1)
        if lines
    )
    if lines and copper > 2:
        inner = f"In{copper - 2}.Cu"
        graphics += (
            Graphic(
                id=derived_id("gfx", "fenolite", f"copper-layer-line:{inner}"),
                kind="line",
                layer=inner,
                points=(Point(0, 0), Point(10_000_000, 0)),
                width=LINE_WIDTH,
            ),
        )
    made = dataclasses.replace(
        design.board, layers=layers_of_rows((*copper_rows(copper), *rows)), graphics=graphics
    )
    return write_board(dataclasses.replace(design, board=made), target=target).text


@dataclass(frozen=True)
class Run:
    """What ``kicad-cli`` did with one probe board: whether it loaded, and the paths of the SVG of the
    layer asked (``None`` without one)."""

    loaded: bool
    paths: int | None
    message: str


def svg_run(runner: KicadCli, text: str, layer: str) -> Run:
    """``pcb export svg`` of ``layer`` alone, without the drawing sheet."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "user-layers.kicad_pcb"
        path.write_text(text, encoding="utf-8")
        args = [
            "pcb",
            "export",
            "svg",
            "-l",
            layer,
            "--exclude-drawing-sheet",
            "--mode-single",
            "-o",
            "out.svg",
        ]
        run = runner.run([*args, path.name], files={path.name: path})
    svg = run.outputs.get("out.svg")
    loaded = run.outcome == "exit" and run.returncode == 0 and svg is not None
    paths = len(re.findall(rb"<path", svg)) if svg is not None else None
    return Run(loaded, paths, run.stderr.strip())


def outcome(runner: Callable[[], KicadCli], major: int) -> str:
    """``equal`` when the board of ``USER_LAYERS[major]`` user layers loads with its line on the last
    one, the control without lines draws nothing there, and one user layer more is refused; else
    ``different``."""
    most = USER_LAYERS[major]
    cli = runner()
    full = svg_run(cli, board(most, major), f"User.{most}")
    empty = svg_run(cli, board(most, major, lines=False), f"User.{most}")
    beyond = svg_run(cli, board(most + 1, major), f"User.{most + 1}")
    print(f"t{major}: {most} user layers {full}; without lines {empty}; {most + 1} user layers {beyond}")
    if full.loaded and full.paths == 1 and empty.loaded and empty.paths == 0 and not beyond.loaded:
        return "equal"
    return "different"


def copper_outcome(runner: Callable[[], KicadCli], major: int) -> str:
    """``equal`` when the table of ``MAX_COPPER`` copper layers loads with its line on the last inner
    layer; else ``different``."""
    last = f"In{MAX_COPPER - 2}.Cu"
    full = svg_run(runner(), board(0, major, copper=MAX_COPPER), last)
    print(f"t{major}: {MAX_COPPER} copper layers {full}")
    return "equal" if full.loaded and full.paths == 1 else "different"


def user_layer_probes(
    runner: Callable[[], KicadCli], major: Callable[[], int]
) -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """The probes ``pcb-user-layers`` and ``pcb-copper-32`` of both majors."""
    return {
        "pcb-user-layers": (lambda: outcome(runner, major()), (9, 10)),
        "pcb-copper-32": (lambda: copper_outcome(runner, major()), (9, 10)),
    }


__all__ = ["Run", "board", "copper_outcome", "copper_rows", "outcome", "svg_run", "user_layer_probes"]
