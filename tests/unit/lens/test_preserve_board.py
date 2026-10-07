# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board content outside the design is kept, at the function level (capability layout-lens; change
c0019)."""

from __future__ import annotations

from _buildhelp import blink
from _preserve_help import board_text, fresh, merged

from fenolite.backends.kicad.boarditems import is_item_uuid
from fenolite.backends.kicad.slots import from_ext
from fenolite.dsl import Design, mm
from fenolite.lens.preserve import fill_inputs_digest


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


# --- board items declared in the script (change c0103) -------------------------------------------------


def _with_items() -> Design:
    d = blink()
    d.rule_area(
        "ANT", [(mm(40), mm(0)), (mm(50), mm(0)), (mm(50), mm(4)), (mm(40), mm(4))], forbid=("tracks",)
    )
    d.text("rev", "REV A", (mm(2), mm(2)))
    d.line("mark", (mm(1), mm(29)), (mm(9), mm(29)), layer="F.Fab", width=mm(0.1))
    d.dimension("width", (mm(0), mm(0)), (mm(40), mm(0)), offset=mm(-3))
    return d


def test_script_board_items_are_regenerated_in_a_merge() -> None:
    """The existing copies of the script's items are dropped and the built ones follow what is kept; an
    unchanged rule area leaves the fill digest as it was."""
    text = fresh(10, _with_items()).files["blink.kicad_pcb"].decode("utf-8")
    result, board = merged(_with_items(), text)
    merged_board = result.design.board
    assert merged_board is not None and board.board is not None
    assert result.summary["board_items"] == {"regenerated": 0, "stale": 0}
    assert not [i for i in result.issues if i.code.startswith("kicad.board-item.")]
    assert [k.name for k in merged_board.keepouts] == ["ANT"]
    assert [t.text for t in merged_board.texts] == ["REV A"] and len(merged_board.dimensions) == 1
    scripted = [g for g in merged_board.graphics if is_item_uuid(g.native_ids.get("kicad", ""))]
    assert len(scripted) == 1 and scripted[0].provenance is None  # the built copy, not the read one
    kept = [g for g in merged_board.graphics if not is_item_uuid(g.native_ids.get("kicad", ""))]
    assert kept == [g for g in board.board.graphics if not is_item_uuid(g.native_ids.get("kicad", ""))]
    assert merged_board.graphics[-1] is scripted[0]
    same = fill_inputs_digest(result.design, project=None, rules=None)
    assert same == fill_inputs_digest(board, project=None, rules=None)


def test_script_board_items_removed_from_the_script_are_stale() -> None:
    text = fresh(10, _with_items()).files["blink.kicad_pcb"].decode("utf-8")
    result, board = merged(blink(), text)
    merged_board = result.design.board
    assert merged_board is not None
    assert result.summary["board_items"] == {"regenerated": 0, "stale": 4}
    stale = [i for i in result.issues if i.code == "kicad.board-item.stale"]
    assert len(stale) == 4 and all(i.severity == "warning" for i in stale)
    assert merged_board.keepouts == () and merged_board.texts == () and merged_board.dimensions == ()
    assert not [g for g in merged_board.graphics if is_item_uuid(g.native_ids.get("kicad", ""))]
    # a rule area that the script removed changes what a fill depends on
    changed = fill_inputs_digest(result.design, project=None, rules=None)
    assert changed != fill_inputs_digest(board, project=None, rules=None)
