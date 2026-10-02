# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement precedence at the function level (capability layout-lens, "Placement precedence"; change
c0019): locked place() > existing board > place() > staging, and the off-board rule."""

from __future__ import annotations

from _buildhelp import blink
from _layout_edit import D1_SHIFT, edit_blink, move_footprint
from _preserve_help import board_text, prepared

from fenolite.dsl import placements, to_model
from fenolite.lens.preserve import ExistingProject, KeptPlacement, prepare

MM = 1_000_000


def test_no_board_keeps_the_placements() -> None:
    d = blink()
    requested = placements(d)
    ready = prepare(to_model(d), requested, ExistingProject(), name="blink")
    assert (
        ready.board is None and ready.match is None and ready.placements is requested and ready.issues == ()
    )


def test_the_board_wins_over_place() -> None:
    d = blink()
    ready = prepared(d, board_text(edit=edit_blink))
    d1 = ready.placements["D1"]
    assert isinstance(d1, KeptPlacement) and d1.at.x == placements(d)["D1"].at.x + D1_SHIFT
    assert [i.where for i in ready.issues if i.code == "layout.place-overridden"] == ["D1"]
    (found,) = [i for i in ready.issues if i.code == "layout.place-overridden"]
    assert found.severity == "info" and "--discard-layout" in found.hint


def test_a_locked_place_wins() -> None:
    d = blink()
    ready = prepared(d, board_text(edit=lambda t: move_footprint(t, "U1", 0, 2 * MM)))
    assert ready.placements["U1"] == placements(d)["U1"]
    assert [(i.code, i.severity) for i in ready.issues if i.where == "U1"] == [
        ("layout.place-forced", "warning")
    ]


def test_an_off_board_part_takes_its_place() -> None:
    d = blink()
    off = board_text(edit=lambda t: move_footprint(t, "R1", 40 * MM, 0))
    ready = prepared(d, off)
    assert ready.placements["R1"] == placements(d)["R1"]
    d.parts["R1"].request = None
    assert "R1" not in prepared(d, off).placements


def test_unmatched_part_keeps_its_place() -> None:
    d = blink()
    text = board_text()
    from fenolite.dsl import Part, mm

    r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
    d.add(r2)
    r2.place(mm(5), mm(5))
    ready = prepared(d, text)
    assert ready.placements["R2"] == placements(d)["R2"]


def test_outline_edited_turns_the_rule_off() -> None:
    d = blink()
    text = move_footprint(board_text(), "R1", 40 * MM, 0).replace("(end 150 130)", "(end 151 130)", 1)
    ready = prepared(d, text)
    assert isinstance(ready.placements["R1"], KeptPlacement)
