# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored dated parent/blank native child controls; no source corpus or baseline refresh."""

from __future__ import annotations

from pathlib import Path

import pytest
from _drawn_titles import DATE, dated_parent_blank_child
from _fidelity import ALL_LEVELS, roundtrip, snapshot

from fenolite.lens.drawn import read_drawn


@pytest.mark.parametrize("target", (9, 10))
def test_native_blank_child_does_not_inherit_dated_board(target: int, tmp_path: Path) -> None:
    original = dated_parent_blank_child(tmp_path / "original", target)
    before = snapshot(original)
    output = tmp_path / "roundtrip"
    reply = roundtrip(original, output)
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert reply.result["equivalent"] is True
    assert reply.result["accepted"] == reply.result["differences"] == []
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"])
    drawing = read_drawn((output / "code/schematic.toml").read_text())
    root_sheet = drawing.sheet(drawing.root)
    assert root_sheet is not None and root_sheet.title_block == (("date", DATE),)
    children = [sheet for sheet in drawing.sheets if sheet.key != drawing.root]
    assert children and all(sheet.title_block == (("title", ""),) for sheet in children)
    assert snapshot(original) == before
