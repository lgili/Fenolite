# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored outline strokes (c0317): DSL validation, model defaults and native root-edge writing."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.dsl import Design, DslError, arc_to, mm, to_model
from fenolite.dsl.units import Length
from fenolite.model import Outline, canonical


def curved(width: object = None) -> Design:
    design = Design("strokes")
    design.board(
        outline=(
            (mm(0), mm(0)),
            (mm(30), mm(0)),
            arc_to((mm(33), mm(12)), (mm(30), mm(24))),
            (mm(0), mm(24)),
        ),
        outline_width=width,
    )
    design.cutout(((mm(5), mm(5)), (mm(9), mm(5)), (mm(9), mm(9)), (mm(5), mm(9))))
    design.slot(mm(18), mm(12), length=mm(6), width=mm(2), name="opening")
    return design


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("width", [mm("0.23"), mm(0)])
def test_generated_line_arc_cutout_and_slot_widths(target: int, width: Length) -> None:
    model = to_model(curved(width))
    assert model.board is not None and model.board.outline is not None
    assert model.board.outline.stroke_width == width.nm
    first = write_board(model, target=target)
    assert first.text == write_board(model, target=target).text
    assert not [issue for issue in first.issues if issue.severity == "error"]
    native = read_board(first.text).board
    assert native is not None
    edges = [g for g in native.graphics if g.layer == "Edge.Cuts"]
    assert {g.kind for g in edges} == {"line", "arc"}
    assert len(edges) == 12 and {g.width for g in edges} == {width.nm}


def test_outline_width_default_and_explicit_zero_round_trip() -> None:
    model = to_model(curved()).board
    assert model is not None and model.outline is not None
    text = canonical.dumps(model.outline)
    assert '"stroke_width"' not in text
    assert canonical.loads(text, Outline) == model.outline
    zero = dataclasses.replace(model.outline, stroke_width=0)
    assert canonical.loads(canonical.dumps(zero), Outline).stroke_width == 0
    assert '"stroke_width": 0' in canonical.dumps(zero)


@pytest.mark.parametrize("value", [mm(-1), 1, True, 0.23, "bad"])
def test_invalid_width_leaves_declaration_unchanged(value: object) -> None:
    design = Design("invalid")
    with pytest.raises(DslError, match="outline_width"):
        design.board(mm(30), mm(24), outline_width=value)
    assert design.outline_path is None and design.outline_width is None
    design.board(mm(30), mm(24))


@pytest.mark.parametrize("value", [-1, True, 0.23])
def test_model_refuses_invalid_stroke_width(value: object) -> None:
    outline = to_model(curved()).board.outline  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="stroke_width"):
        dataclasses.replace(outline, stroke_width=value)  # type: ignore[arg-type]


def test_explicit_width_changes_on_rebuild_and_then_stays_stable(tmp_path: Path) -> None:
    script = blink_variant(
        tmp_path / "source",
        "design.board(mm(50), mm(30))",
        'design.board(mm(50), mm(30), outline_width=mm("0.23"))',
    )
    args = (str(script), "--out", "built", "--confirm")
    first = run("build", *args, cwd=tmp_path, timestamp="2026-11-01T00:00:00Z")
    assert first.exit_code == 0, first.error
    script.write_text(
        script.read_text(encoding="utf-8").replace('mm("0.23")', 'mm("0.31")'), encoding="utf-8"
    )
    changed = run("build", *args, cwd=tmp_path, timestamp="2026-11-01T00:00:00Z")
    assert changed.exit_code == 0, changed.error
    board_path = tmp_path / "built/blink.kicad_pcb"
    native = read_board(board_path).board
    assert native is not None
    assert {g.width for g in native.graphics if g.layer == "Edge.Cuts"} == {310_000}
    before = board_path.read_bytes()
    again = run("build", *args, cwd=tmp_path, timestamp="2026-11-01T00:00:00Z")
    assert again.exit_code == 0, again.error
    assert board_path.read_bytes() == before
