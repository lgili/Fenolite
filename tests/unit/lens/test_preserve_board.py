# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board content outside the design is kept, at the function level (capability layout-lens; change
c0019)."""

from __future__ import annotations

from _buildhelp import blink
from _preserve_help import board_text, merged

from fenolite.backends.kicad.slots import from_ext


def test_root_slots_and_layers_kept() -> None:
    text = board_text().replace("(pad_to_mask_clearance 0)", "(pad_to_mask_clearance 0.05)")
    result, board = merged(blink(), text)
    assert result.design.board is not None and board.board is not None
    assert from_ext(result.design.board.ext["kicad"]) == from_ext(board.board.ext["kicad"])
    assert result.design.board.layers == board.board.layers
    assert result.design.board.outline is None and result.design.board.graphics == board.board.graphics
    assert "layout.outline-kept" not in [i.code for i in result.issues]


def test_outline_without_edge_content_comes_from_the_design() -> None:
    text = "\n".join(line for line in board_text().split("\n"))
    from fenolite.backends.kicad.sexpr import Node, dumps, parse

    root = parse(text)
    stripped = root.with_children(
        [
            c
            for c in root.children
            if not (isinstance(c, Node) and c.name == "gr_line" and "Edge.Cuts" in dumps(c))
        ]
    )
    result, _ = merged(blink(), dumps(stripped, style="kicad"))
    assert result.design.board is not None and result.design.board.outline is not None


def test_edge_edited_is_kept() -> None:
    result, _ = merged(blink(), board_text().replace("(end 150 130)", "(end 151 130)", 1))
    assert [i.severity for i in result.issues if i.code == "layout.outline-kept"] == ["warning"]


def test_copper_mismatch() -> None:
    d = blink()
    d.copper = 4
    result, _ = merged(d, board_text())
    assert [(i.code, i.severity) for i in result.issues] == [("layout.copper-mismatch", "error")]
