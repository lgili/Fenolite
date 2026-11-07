# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact target-project geometry configuration, with absent legacy bytes retained (c0340)."""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal
from fractions import Fraction

import _schema
import pytest

from fenolite.core.errors import FormatError
from fenolite.model.board import Board
from fenolite.model.canonical import dumps, loads

IDENT = "brd_00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize("value", (1, 5_000, 10_000, 9_007_199_254_740_993))
def test_explicit_curve_error_is_exact_and_canonically_roundtrips(value: int) -> None:
    board = Board(id=IDENT, max_curve_error=value)
    assert board.max_curve_error == value
    assert loads(dumps(board), Board) == board
    names = [f.name for f in dataclasses.fields(Board)]  # appended fields keep their order (c0445)
    assert names[names.index("max_curve_error") :] == ["max_curve_error", "mask_margin"]
    assert json.loads(dumps(board))["max_curve_error"] == value
    assert not _schema.validate(json.loads(dumps(board)), _schema.load("fenolite.model.v0/board.json"))


def test_absent_curve_error_keeps_exact_legacy_board_bytes() -> None:
    board = Board(id=IDENT)
    assert board.max_curve_error is None
    assert dumps(board) == '{\n  "id": "' + IDENT + '"\n}\n'
    assert loads(dumps(board), Board) == board


@pytest.mark.parametrize(
    "value", (True, False, 0, -1, 1.5, 10_000.0, Decimal(10_000), Fraction(1, 2), "10000")
)
def test_invalid_curve_error_refuses_in_direct_model(value: object) -> None:
    with pytest.raises((TypeError, ValueError), match="max_curve_error"):
        Board(id=IDENT, max_curve_error=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", (True, False, 0, -1, 1.5, 10_000.0, "10000"))
def test_invalid_curve_error_refuses_in_canonical_reader(value: object) -> None:
    with pytest.raises(FormatError):
        loads(json.dumps({"id": IDENT, "max_curve_error": value}), Board, file="authored-board.json")
