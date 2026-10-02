# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the function-level preservation tests (change c0019): the blink's model, its built output
and an existing board, read from a (possibly edited) board text."""

from __future__ import annotations

from collections.abc import Callable

from _buildhelp import blink, build

from fenolite.backends.kicad.pcb import read_board
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import moves, placements, to_model
from fenolite.lens.build import BuildOutput
from fenolite.lens.preserve import ExistingProject, Merged, Prepared, merge_layout, prepare
from fenolite.model.design import Design


def fresh(target: int = 10, design: DslDesign | None = None) -> BuildOutput:
    return build(design or blink(), target)


def board_text(target: int = 10, edit: Callable[[str], str] | None = None) -> str:
    text = fresh(target).files["blink.kicad_pcb"].decode("utf-8")
    return edit(text) if edit is not None else text


def prepared(design: DslDesign, text: str, *, target: int = 10) -> Prepared:
    del target
    return prepare(
        to_model(design), placements(design), ExistingProject(board=text), name="blink", moves=moves(design)
    )


def rebuild(design: DslDesign, text: str, target: int = 10) -> BuildOutput:
    """``build_design`` of ``design`` over the existing board ``text``."""
    ready = prepared(design, text, target=target)
    return build(design, target, prepared=ready, placements_override=ready.placements)


def merged(design: DslDesign, text: str, target: int = 10) -> tuple[Merged, Design]:
    """``merge_layout`` of the build at the effective placements with the board read from ``text``."""
    ready = prepared(design, text, target=target)
    output = build(design, target, placements_override=ready.placements)
    assert ready.board is not None and ready.match is not None
    return merge_layout(output.design, ready.board, ready.match), ready.board


def read(text: str) -> Design:
    return read_board(text)


__all__ = ["board_text", "fresh", "merged", "prepared", "read", "rebuild"]
