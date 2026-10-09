# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The layer table of a created board for every count (capability kicad-file-backend, "Created board
header": scenarios "Four copper layers", "Six and eight copper layers" and "Counts outside the table";
change c0100)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad import layers
from fenolite.backends.kicad.layers import (
    CREATED_COPPER_COUNTS,
    CREATED_ROWS,
    created_count,
    created_layers,
    inner_rows,
)
from fenolite.model.board import Layer

Row = tuple[str, str, str, str | None]


def row(layer: Layer) -> Row:
    bag = dict(layer.ext["kicad"].payload)
    return layer.name, bag["number"], bag["type"], bag.get("user_name")


def copper_rows(table: tuple[Layer, ...]) -> list[Row]:
    return [row(layer) for layer in table if layer.kind == "copper"]


def test_counts() -> None:
    assert CREATED_COPPER_COUNTS == (2, 4, 6, 8)
    assert not hasattr(layers, "INNER_ROWS")
    assert inner_rows(2) == ()
    assert inner_rows(4) == ((4, "In1.Cu", "signal", None), (6, "In2.Cu", "signal", None))


def test_two_copper_layers_are_the_recorded_table() -> None:
    table = created_layers(2)
    assert [layer.ordinal for layer in table] == list(range(len(CREATED_ROWS)))
    assert [row(layer) for layer in table] == [
        (name, str(number), row_type, user) for number, name, row_type, user in CREATED_ROWS
    ]


def test_four_copper_layers() -> None:
    """Scenario "Four copper layers"."""
    table = created_layers(4)
    assert [(name, number) for name, number, _, _ in copper_rows(table)] == [
        ("F.Cu", "0"),
        ("In1.Cu", "4"),
        ("In2.Cu", "6"),
        ("B.Cu", "2"),
    ]
    assert len(table) == 22 and [layer.ordinal for layer in table] == list(range(22))


def test_six_and_eight_copper_layers() -> None:
    """Scenario "Six and eight copper layers"."""
    six, eight = created_layers(6), created_layers(8)
    assert copper_rows(six) == [
        ("F.Cu", "0", "signal", None),
        ("In1.Cu", "4", "signal", None),
        ("In2.Cu", "6", "signal", None),
        ("In3.Cu", "8", "signal", None),
        ("In4.Cu", "10", "signal", None),
        ("B.Cu", "2", "signal", None),
    ]
    assert copper_rows(eight) == [
        *copper_rows(six)[:-1],
        ("In5.Cu", "12", "signal", None),
        ("In6.Cu", "14", "signal", None),
        ("B.Cu", "2", "signal", None),
    ]
    two = [row(layer) for layer in created_layers(2)]
    for count, table in ((6, six), (8, eight)):
        rows = [row(layer) for layer in table]
        assert rows[:1] + rows[count - 1 :] == two  # every row outside the inner ones is the two-layer row
        assert [layer.ordinal for layer in table] == list(range(18 + count))
        assert all(layer.kind == "copper" for layer in table[:count])
        assert created_count([name for name, _, _, _ in copper_rows(table)]) == count
        assert len({layer.id for layer in table}) == len(table)


def test_created_count() -> None:
    assert created_count(("F.Cu", "B.Cu")) == 2
    assert created_count(["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]) == 4
    assert created_count(("F.Cu", "In1.Cu", "B.Cu")) is None
    assert created_count(("F.Cu", "In2.Cu", "In1.Cu", "B.Cu")) is None  # table order
    assert created_count(("B.Cu", "F.Cu")) is None
    assert created_count(("F.Cu", *(f"In{k}.Cu" for k in range(1, 9)), "B.Cu")) is None
    assert created_count(()) is None


@pytest.mark.parametrize("count", [0, 3, 10, True, 6.0, "4", None, -2])
def test_counts_outside_the_table(count: object) -> None:
    """Scenario "Counts outside the table"."""
    with pytest.raises(ValueError, match="2, 4, 6 or 8"):
        created_layers(count)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="2, 4, 6 or 8"):
        inner_rows(count)  # type: ignore[arg-type]
