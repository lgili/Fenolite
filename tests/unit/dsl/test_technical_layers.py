# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicit technical rows use only existing model fields (c0324)."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, DslError, mm, to_model
from fenolite.dsl.items import BOARD_LAYER_KINDS
from fenolite.model import canonical


def test_default_none_retains_exact_model_and_explicit_rows_are_canonical() -> None:
    absent, none = Design("same"), Design("same")
    absent.board(mm(20), mm(10))
    none.board(mm(20), mm(10), technical_layers=None)
    assert canonical.dumps(to_model(absent)) == canonical.dumps(to_model(none))
    assert to_model(absent).board.layers == ()
    explicit = Design("short")
    explicit.board(mm(20), mm(10), technical_layers=("Edge.Cuts", "F.SilkS", "Cmts.User"))
    explicit.user_layers(2, names={"User.2": "Authored notes"})
    model = to_model(explicit)
    assert model.board is not None
    assert [(layer.name, layer.kind) for layer in model.board.layers] == [
        ("F.SilkS", "silkscreen"),
        ("Cmts.User", "user"),
        ("Edge.Cuts", "edge"),
        ("User.1", "user"),
        ("User.2", "user"),
    ]
    assert dict(model.board.layers[-1].ext["kicad"].payload)["user_name"] == "Authored notes"
    assert [layer.ordinal for layer in model.board.layers] == list(range(5))


@pytest.mark.parametrize(
    "value",
    [
        "Edge.Cuts",
        True,
        1,
        (),
        ("Eco1.User",),
        ("Edge.Cuts", "Unknown.User"),
        ("Edge.Cuts", "F.Cu"),
        ("Edge.Cuts", "User.1"),
        ("Edge.Cuts", "Edge.Cuts"),
        ("Edge.Cuts", 5),
    ],
)
def test_invalid_selection_is_atomic(value: object) -> None:
    design = Design("invalid")
    with pytest.raises(DslError, match="technical_layers"):
        design.board(mm(20), mm(10), technical_layers=value)  # type: ignore[arg-type]
    assert design.outline_path is None and design.technical_layer_names is None
    design.board(mm(20), mm(10))


def test_closed_names_remain_the_existing_backend_table() -> None:
    from fenolite.backends.kicad.layers import created_layers

    assert tuple(BOARD_LAYER_KINDS) == tuple(
        layer.name for layer in created_layers(2) if layer.kind != "copper"
    )
