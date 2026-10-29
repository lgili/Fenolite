# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Modules of an import (capability board-to-code, "Modules per sheet"; change c0275). The modules of a
board built by Fenolite come from each footprint's ``fenolite.path``; a part keeps its key with ``name=``."""

from __future__ import annotations

from pathlib import Path

from _importcode import PROJECT, board_only, build, built_board, imported


def test_repeated_module(tmp_path: Path) -> None:
    reply = imported(tmp_path, PROJECT, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["modules"] == ["ch1", "ch2"]
    text = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert (
        'r201 = Part("R201", "Mini:Mini_R_0603", footprint="Mini:Mini_R_0603", value="1k", name="R101")'
        in text
    )
    assert build(tmp_path / "out").exit_code == 0
    design = built_board(tmp_path / "out").design
    paths = {c.ref: c.properties.get("fenolite.path") for c in design.circuit.components}
    assert paths["R101"] == "ch1/R101" and paths["R201"] == "ch2/R101"


def test_single_sheet_writes_no_sheets_folder(tmp_path: Path) -> None:
    reply = imported(tmp_path, board_only(tmp_path), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert not (tmp_path / "out" / "sheets").exists()
