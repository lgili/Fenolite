# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the outline, hole and layer tests of change c0102: blink variants as DSL designs, builds that
carry the definitions a script generated, and rebuilds over an existing board text."""

from __future__ import annotations

from _buildhelp import blink_text, build

from fenolite.dsl import Design as DslDesign
from fenolite.dsl import module_moves, moves, net_moves, outline_locked, placements, to_model
from fenolite.lens.build import BuildOutput
from fenolite.lens.preserve import ExistingProject, prepare

BOARD = "design.board(mm(50), mm(30))"
"""The ``board()`` line of the blink example."""
SHAPE = "from fenolite.dsl import shape\n"
ROUNDED = (
    SHAPE
    + "design.board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(2)))\n"
    + "design.cutout(shape.circle(mm(45), mm(5), mm(3.2)))\n"
    + "design.cutout(shape.slot((mm(10), mm(25)), (mm(20), mm(25)), mm(1)))"
)
"""The rounded board with a round cut-out and a slot of "A rounded board with cut-outs"."""
HOLES = (
    'design.hole("H1", mm(4), mm(4), drill=mm(3.2))\n'
    'h2 = design.hole("H2", mm(46), mm(4), drill=mm(3.2), pad=mm(6))\n'
    "connect(gnd, h2[1])\n"
)
"""The two holes of "Holes in a build": one that is not plated and one plated, on ``GND``."""


def variant(new_board: str = BOARD, *, append: str = "", old: str = BOARD) -> DslDesign:
    """The blink with its ``board()`` line replaced by ``new_board`` and ``append`` added at its end."""
    text = blink_text()
    assert old in text, old
    scope: dict[str, object] = {"__name__": "design"}
    exec(compile(text.replace(old, new_board) + "\n" + append, "design.py", "exec"), scope)  # noqa: S102
    design = scope["design"]
    assert isinstance(design, DslDesign)
    return design


def definitions(design: DslDesign) -> dict[str, object]:
    """The authored footprints and symbols of ``design`` as ``build_design`` takes them."""
    return {
        "authored_footprints": {key: fp.definition for key, fp in design.footprints.items()},
        "authored_symbols": {key: symbol.definition for key, symbol in design.symbols.items()},  # type: ignore[attr-defined]
    }


def build_script(design: DslDesign, target: int = 10, **kwargs: object) -> BuildOutput:
    """``build_design`` of ``design`` with its generated definitions and its outline lock."""
    return build(design, target, lock_outline=outline_locked(design), **definitions(design), **kwargs)


def rebuild_script(design: DslDesign, text: str, target: int = 10, **kwargs: object) -> BuildOutput:
    """``build_script`` of ``design`` over the existing board ``text``."""
    ready = prepare(
        to_model(design),
        placements(design),
        ExistingProject(board=text),
        name=design.name,
        moves=moves(design),
        module_moves=module_moves(design),
        net_moves=net_moves(design),
    )
    return build_script(design, target, prepared=ready, placements_override=ready.placements, **kwargs)


def board_text(output: BuildOutput, name: str = "blink") -> str:
    return output.files[f"{name}.kicad_pcb"].decode("utf-8")


def codes(output: BuildOutput) -> list[str]:
    return [found.code for found in output.issues]


__all__ = [
    "BOARD",
    "HOLES",
    "ROUNDED",
    "SHAPE",
    "board_text",
    "build_script",
    "codes",
    "definitions",
    "rebuild_script",
    "variant",
]
