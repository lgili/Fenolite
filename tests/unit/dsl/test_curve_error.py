# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The public target-project curve approximation setting (c0340)."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, mm, to_model
from fenolite.dsl.errors import DslError


def test_board_curve_error_reaches_exact_model() -> None:
    design = Design("authored_curve_error")
    design.board(mm(30), mm(20), max_curve_error=mm("0.01"))
    board = to_model(design).board
    assert board is not None and board.max_curve_error == 10_000


def test_board_curve_error_default_remains_absent() -> None:
    design = Design("authored_default")
    design.board(mm(30), mm(20))
    board = to_model(design).board
    assert board is not None and board.max_curve_error is None


@pytest.mark.parametrize("value", (True, False, 10_000, 1.5, mm(0), mm(-1), "0.0000001mm"))
def test_bad_board_curve_error_refuses_without_declaring_board(value: object) -> None:
    design = Design("authored_bad_setting")
    with pytest.raises(DslError, match="max_curve_error"):
        design.board(mm(30), mm(20), max_curve_error=value)
    design.board(mm(30), mm(20))
