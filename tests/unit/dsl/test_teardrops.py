# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Teardrop settings of vias in the DSL (capability design-dsl, "Teardrop settings of vias in the DSL";
change c0277): ``teardrop()`` and ``teardrop=`` of ``Design.via`` and ``Design.via_table``."""

from __future__ import annotations

import pytest

import fenolite.dsl as dsl
from fenolite.dsl import Design, DslError, Net, ViaIntent, copper, mm, teardrop
from fenolite.model.board import Teardrop


def _design() -> tuple[Design, Net]:
    design = Design("tear")
    design.board(mm(50), mm(30))
    return design, Net("GND")


def test_values_of_teardrop() -> None:
    assert teardrop() == Teardrop()
    assert teardrop(max_length=mm(1), length_ratio=500_000, curved=True) == Teardrop(
        max_length=1_000_000, length_ratio=500_000, curved=True
    )
    assert teardrop(enabled=False) == Teardrop(enabled=False)
    full = teardrop(
        max_length=mm(1), max_width=mm(2), length_ratio=500_000, width_ratio=1_000_000, curved=False,
        filter_ratio=900_000, two_segments=True, prefer_zones=True,
    )  # fmt: skip
    assert (full.max_width, full.width_ratio, full.filter_ratio, full.two_segments) == (
        2_000_000,
        10**6,
        900_000,
        True,
    )
    assert "teardrop" in dsl.__all__


@pytest.mark.parametrize(
    ("arguments", "word"),
    [
        ({"length_ratio": 0.5}, "length_ratio"),
        ({"width_ratio": 1_000_001}, "width_ratio"),
        ({"filter_ratio": -1}, "filter_ratio"),
        ({"length_ratio": True}, "length_ratio"),
        ({"max_length": 1}, "max_length"),
        ({"max_width": mm(0)}, "max_width"),
        ({"curved": "yes"}, "curved"),
        ({"two_segments": 1}, "two_segments"),
        ({"enabled": None}, "enabled"),
    ],
)
def test_refused_values(arguments: dict[str, object], word: str) -> None:
    with pytest.raises(DslError, match=word):
        teardrop(**arguments)


def test_settings_on_a_via_and_a_table() -> None:
    design, gnd = _design()
    settings = teardrop(max_length=mm(1))
    design.via("v", mm(5), mm(5), net=gnd, teardrop=settings)
    design.via("plain", mm(9), mm(5), net=gnd)
    design.via_table(
        "t", net=gnd, diameter=mm(0.6), drill=mm(0.3), rows_nm=((1_000_000, 2_000_000),), teardrop=settings
    )
    intents = {intent.key: intent for intent in copper(design)}
    via = intents["v"]
    assert isinstance(via, ViaIntent) and via.teardrop == settings
    assert intents["plain"].teardrop is None  # type: ignore[union-attr]
    assert intents["t"].teardrop == settings  # type: ignore[union-attr]


def test_refused_teardrop_arguments() -> None:
    design, gnd = _design()
    with pytest.raises(DslError, match="via v: teardrop"):
        design.via("v", mm(1), mm(1), net=gnd, teardrop={"max_length": 1})
    with pytest.raises(DslError, match="via_table t: teardrop"):
        design.via_table("t", net=gnd, diameter=mm(0.6), drill=mm(0.3), rows_nm=((0, 0),), teardrop=True)
