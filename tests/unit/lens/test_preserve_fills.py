# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zone fills and the staleness digests (capability layout-lens, "Zone fills and the staleness digest";
change c0019)."""

from __future__ import annotations

import ast
from pathlib import Path

from _build_preserve_variants import without_r1
from _buildhelp import blink
from _layout_edit import ZONE_UUID, add_filled_zone
from _preserve_help import board_text, merged

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.lens.preserve import ExistingProject, drop_stale_fills, fill_inputs_digest, zone_digest

ROOT = Path(__file__).resolve().parents[3]
RULES = "(version 1)\n"
SAME = ExistingProject(project="{}", rules=RULES)


def filled(target: int = 10) -> str:
    return board_text(target, edit=lambda t: add_filled_zone(t, net="GND", layer="B.Cu"))


def zone(design: object) -> object:
    (z,) = [z for z in design.board.zones if z.native_ids["kicad"] == ZONE_UUID]  # type: ignore[attr-defined]
    return z


def test_digests_ignore_ids_and_formats() -> None:
    nine = read_board(filled(9))
    ten = read_board(write_board(nine, target=10).text)
    assert zone_digest(nine, zone(nine)) == zone_digest(ten, zone(ten))  # type: ignore[arg-type]
    assert fill_inputs_digest(nine, project="{}", rules=None) == fill_inputs_digest(
        ten, project="{}", rules=None
    )


def test_unchanged_layout_keeps_fills() -> None:
    result, board = merged(blink(), filled())
    kept, issues = drop_stale_fills(board, result.design, existing=SAME, project="{}", rules=RULES)
    assert issues == () and len(zone(kept).fills) == 2  # type: ignore[attr-defined]


def test_a_removed_part_drops_fills() -> None:
    result, board = merged(without_r1(blink()), filled())
    stale, issues = drop_stale_fills(board, result.design, existing=SAME, project="{}", rules=RULES)
    assert [i.code for i in issues] == ["zone.fill-stale"] and zone(stale).fills == ()  # type: ignore[attr-defined]


def test_changed_inputs_drop_fills() -> None:
    result, board = merged(blink(), filled())
    stale, issues = drop_stale_fills(
        board,
        result.design,
        existing=ExistingProject(rules="(version 1)\n"),
        project="{}",
        rules="(version 1)\n(rule x (constraint clearance (min 1mm)))\n",
    )
    assert [i.severity for i in issues] == ["warning"] and zone(stale).fills == ()  # type: ignore[attr-defined]


def test_digests_are_text_only() -> None:
    tree = ast.parse((ROOT / "src" / "fenolite" / "lens" / "preserve.py").read_text(encoding="utf-8"))
    assert not any(
        isinstance(n, ast.ImportFrom) and (n.module or "").startswith("fenolite.geometry")
        for n in ast.walk(tree)
    )
