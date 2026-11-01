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


# --- the three-way rule (change c0250, "Placement precedence") -------------------------------------


def _base_of_fresh() -> tuple[str, object]:
    from _buildhelp import build

    from fenolite.lens.edits import read_base

    out = build(blink(), 10, write_base=True)
    return out.files["blink.kicad_pcb"].decode("utf-8"), read_base(
        out.files["fenolite-base.json"].decode("utf-8"), target="kicad"
    )


def _prepared_with_base(d: object, text: str, base: object) -> object:
    from fenolite.dsl import module_moves, moves, net_moves

    return prepare(
        to_model(d),  # type: ignore[arg-type]
        placements(d),  # type: ignore[arg-type]
        ExistingProject(board=text),
        name="blink",
        moves=moves(d),  # type: ignore[arg-type]
        module_moves=module_moves(d),  # type: ignore[arg-type]
        net_moves=net_moves(d),  # type: ignore[arg-type]
        edits={},
        base=base,  # type: ignore[arg-type]
    )


def test_with_a_base_a_changed_place_moves_an_unedited_part() -> None:
    text, base = _base_of_fresh()
    d = blink()
    d.parts["R1"].request = None
    d.parts["R1"].place("35mm", "9mm")
    ready = _prepared_with_base(d, text, base)
    r1 = ready.placements["R1"]  # type: ignore[attr-defined]
    assert r1.at == placements(d)["R1"].at
    assert [(i.code, i.where) for i in ready.issues] == [("edit.code-wins", "R1#position")]  # type: ignore[attr-defined]


def test_with_a_base_the_board_still_wins_over_an_unchanged_place() -> None:
    text, base = _base_of_fresh()
    d = blink()
    ready = _prepared_with_base(d, edit_blink(text), base)
    d1 = ready.placements["D1"]  # type: ignore[attr-defined]
    assert isinstance(d1, KeptPlacement) and d1.at.x == placements(d)["D1"].at.x + D1_SHIFT
    found = sorted((i.code, i.where) for i in ready.issues)  # type: ignore[attr-defined]
    assert found == [("edit.unrecorded", "D1#position"), ("layout.place-overridden", "D1")]


def test_with_a_base_a_hand_move_and_a_script_move_conflict() -> None:
    text, base = _base_of_fresh()
    d = blink()
    d.parts["R1"].request = None
    d.parts["R1"].place("35mm", "9mm")
    ready = _prepared_with_base(d, move_footprint(text, "R1", 0, 2 * MM), base)
    (conflict,) = [i for i in ready.issues if i.code == "sync.conflict"]  # type: ignore[attr-defined]
    assert conflict.where == "R1#position" and conflict.severity == "error"
    r1 = ready.placements["R1"]  # type: ignore[attr-defined]
    assert isinstance(r1, KeptPlacement) and r1.at.y == 111 * MM


def test_without_a_base_entry_one_base_missing() -> None:
    from fenolite.lens.edits import BaseRecord

    text, _ = _base_of_fresh()
    ready = _prepared_with_base(blink(), edit_blink(text), BaseRecord.absent("kicad"))
    missing = [i for i in ready.issues if i.code == "edit.base-missing"]  # type: ignore[attr-defined]
    assert len(missing) == 1 and missing[0].message.startswith("3 part(s)")
    assert "edit.unrecorded" not in [i.code for i in ready.issues]  # type: ignore[attr-defined]
