# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Arcs of the board outline in the model (capability design-model, "Board outline arcs"; change c0102)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from _buildhelp import blink, build

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import to_model
from fenolite.model import Board, Outline, OutlineArc, canonical
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
V020 = ROOT / "tests" / "data" / "model" / "v0.2.0" / "blink_2layer.board.json"
SENTENCE = "Release 0.2.x cannot read a model document that carries `arcs`"
MM = 1_000_000


def mm(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def arc_outline() -> Outline:
    return Outline(
        id=derived_id("out", "test", "outline"),
        points=(mm(0, 0), mm(10, 0), mm(10, 10), mm(0, 10)),
        cutouts=((mm(6, 5), mm(4, 5)),),
        arcs=(
            OutlineArc(0, 1, Point(11_000_000, 5_000_000)),
            OutlineArc(1, 0, Point(5_000_000, 4_000_000)),
            OutlineArc(1, 1, Point(5_000_000, 6_000_000)),
        ),
    )


def test_an_outline_with_an_arc_round_trips(tmp_path: Path) -> None:
    outline = arc_outline()
    design = dataclasses.replace(
        Design.new("arcs", seed=0), board=Board(id=derived_id("brd", "test", "board"), outline=outline)
    )
    canonical.dump_dir(design, tmp_path)
    loaded = canonical.load_dir(tmp_path)
    assert loaded.board is not None and loaded.board.outline == outline
    arcs = json.loads((tmp_path / "board.json").read_text(encoding="utf-8"))["outline"]["arcs"]
    assert [(a["ring"], a["edge"]) for a in arcs] == [(0, 1), (1, 0), (1, 1)]
    assert arcs[0]["mid"] == {"x": 11_000_000, "y": 5_000_000}


def test_documents_without_arcs_keep_their_bytes() -> None:
    # the board of the script, whose outline is a rectangle, and the board the build records
    script = canonical.dumps(to_model(blink()).board)
    built = build(blink(), 10).files[".fenolite/board.json"].decode("utf-8")
    for text in (script, built):
        assert '"arcs"' not in text
        assert canonical.dumps(canonical.loads(text, Board)) == text
    board = canonical.loads(script, Board)
    assert board.outline is not None and board.outline.arcs == ()


def test_outline_arc_is_a_frozen_value() -> None:
    arc = OutlineArc(1, 0, Point(1, 2))
    with pytest.raises(dataclasses.FrozenInstanceError):
        arc.ring = 2  # type: ignore[misc]
    assert Outline(id=derived_id("out", "test", "o")).arcs == ()


def test_schema_defines_arcs() -> None:
    schema = json.loads((ROOT / "schemas" / "fenolite.model.v0" / "board.json").read_text(encoding="utf-8"))
    text = json.dumps(schema)
    assert '"arcs"' in text and '"OutlineArc"' in text
    arc = schema["$defs"]["OutlineArc"]["properties"]
    assert arc["ring"]["type"] == "integer" and arc["edge"]["type"] == "integer" and "mid" in arc


@pytest.mark.skipif(not V020.is_file(), reason="the 0.2.0 fixture of change c0126 is not on this branch")
def test_a_document_of_v020_still_loads() -> None:
    text = V020.read_text(encoding="utf-8")
    board = canonical.loads(text, Board)
    assert board.outline is not None and board.outline.arcs == ()
    assert canonical.dumps(board) == text


def test_the_sentence_about_older_releases_is_written() -> None:
    model = (ROOT / "docs" / "design-model.md").read_text(encoding="utf-8")
    assert SENTENCE in model
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Release 0.2.x cannot read a model document that carries the new key `arcs`" in changelog
