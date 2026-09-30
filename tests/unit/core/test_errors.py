# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import pytest

from fenolite.core.errors import ConsistencyError, FenoliteError, FormatError, Issue


def test_issue_validation() -> None:
    assert Issue(code="model.duplicate-ref", severity="error", message="m").where == ""
    with pytest.raises(ValueError):
        Issue(code="Bad Code", severity="error", message="m")
    with pytest.raises(ValueError):
        Issue(code="a.b", severity="fatal", message="m")  # type: ignore[arg-type]


def test_format_error_location() -> None:
    err = FormatError("expected an integer", file="board.json", locator="/tracks/3/width")
    assert (err.file, err.locator, err.offset) == ("board.json", "/tracks/3/width", None)
    assert str(err) == "board.json:/tracks/3/width: expected an integer"
    assert str(FormatError("bad", offset=12)) == "@12: bad"
    assert isinstance(err, FenoliteError) and issubclass(ConsistencyError, FenoliteError)
