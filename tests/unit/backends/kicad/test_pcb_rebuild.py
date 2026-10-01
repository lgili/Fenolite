# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Same-version rebuild, the emitters and opaque counts (capability kicad-file-backend, change c0009)."""

from __future__ import annotations

import dataclasses
import hashlib

import pytest
from _boards import FIXTURE, SCENARIOS, rt1_problems, uid

from fenolite.backends.kicad.pcb import (
    EmitContext,
    ModelSource,
    model_source,
    opaque_count,
    opaque_digests,
    read_board,
    rebuild_board,
)
from fenolite.backends.kicad.sexpr import dumps, parse, tree_equal
from fenolite.core.coords import Point
from fenolite.model.board import Track


def rt1(text: str) -> None:
    assert rt1_problems(text) == []


def test_rt1_authored_board() -> None:
    rt1(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_rt1_scenarios(name: str) -> None:
    rt1(SCENARIOS[name])


def test_created_entity_refused() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    extra = Track(id="trk_" + uid(77), start=Point(0, 0), end=Point(1, 0), width=1, layer="F.Cu")
    board = dataclasses.replace(design.board, tracks=(*design.board.tracks, extra))
    with pytest.raises(ValueError, match=extra.id):
        rebuild_board(dataclasses.replace(design, board=board))


def test_collection_order_does_not_matter() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    board = dataclasses.replace(
        design.board,
        tracks=tuple(reversed(design.board.tracks)),
        graphics=tuple(reversed(design.board.graphics)),
    )
    rebuilt = rebuild_board(dataclasses.replace(design, board=board))
    assert tree_equal(rebuilt, parse(FIXTURE.read_text(encoding="utf-8")))


def test_model_values_are_emitted() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    track = design.board.tracks[0]
    moved = dataclasses.replace(track, end=Point(31_000_000, 14_200_000))
    rebuilt = rebuild_board(design.replace_entity(moved))
    assert "(end 31 14.2)" in dumps(rebuilt, style="compact")


def test_model_source_holds_only_slotted_fields() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    graphic = design.board.graphics[0]
    source = model_source(graphic, EmitContext.of(design))
    assert isinstance(source, ModelSource)
    assert set(source.fields()) == {"points", "layer", "native_ids"}
    assert [n.name for n in source.items("points")] == ["start", "end"]  # type: ignore[union-attr]


def test_count_follows_the_slots() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    group = f'(group "" (uuid "{uid(88)}") (members))'
    root = parse(text)
    with_group = dumps(dataclasses.replace(root, children=(*root.children, parse(group))))
    first, second = read_board(text), read_board(with_group)
    assert opaque_count(second) == opaque_count(first) + 1
    digest = hashlib.sha256(group.encode("utf-8")).hexdigest()
    assert opaque_digests(second)[digest] == opaque_digests(first)[digest] + 1
