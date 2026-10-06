# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Signed bodies keep legacy compatibility and schema/canonical integer semantics."""

from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Board, ComponentBody, FootprintInstance
from fenolite.model.canonical import dumps, loads
from fenolite.model.design import Design


def body(**values: object) -> ComponentBody:
    return ComponentBody(id=derived_id("bdy", "fenolite", "authored"), kind="extruded", height=300, **values)  # type: ignore[arg-type]


def issues(value: ComponentBody) -> list[str]:
    design = Design.new("signed", seed=9)
    assert design.board
    fp = FootprintInstance(
        id=derived_id("fp", "fenolite", "authored"),
        component_id="",
        lib_ref="",
        position=Point(0, 0),
        bodies=(value,),
    )
    return [i.code for i in replace(design, board=replace(design.board, footprints=(fp,))).validate()]


def test_signed_interval_survives_canonical_and_negative_native_standoff() -> None:
    value = body(standoff=-200, z_min=-200, z_max=300)
    assert issues(value) == []
    assert loads(dumps(value), ComponentBody) == value
    assert '"z_min": -200' in dumps(value)


@pytest.mark.parametrize("low,high", [(None, 300), (-2, None), (20, 10)])
def test_partial_or_reversed_interval_is_invalid(low: int | None, high: int | None) -> None:
    assert issues(body(z_min=low, z_max=high)) == ["model.body-volume"]


def test_legacy_validation_and_output_remain_unchanged() -> None:
    assert issues(body(standoff=-1)) == ["model.body-height"]
    assert issues(body(standoff=400)) == ["model.body-height"]
    value = body()
    assert '"z_min"' not in dumps(value)
    assert loads(dumps(value), ComponentBody) == value


def test_unknown_source_projection_preserves_unordered_heights() -> None:
    value = body(standoff=400, projection_unknown=True)
    assert issues(value) == []
    assert loads(dumps(value), ComponentBody) == value


def test_unknown_projection_does_not_allow_invalid_explicit_interval() -> None:
    assert issues(body(z_min=20, z_max=10, projection_unknown=True)) == ["model.body-volume"]


def test_v020_body_document_keeps_defaults_bytes_and_legacy_validation() -> None:
    path = Path(__file__).resolve().parents[2] / "data/model/v0.2.0/body_legacy.board.json"
    text = path.read_text(encoding="utf-8")
    board = loads(text, Board)
    (value,) = board.footprints[0].bodies
    assert value.z_min is value.z_max is None
    assert value.projection_unknown is False
    assert dumps(board) == text
    assert issues(value) == ["model.body-height"]
