# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic circuit, embedded graphics and hierarchy preserved in conversion (c0160 task 4.1)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _schbuild import built_nested, write_files

from fenolite.api import equivalent
from fenolite.convert import convert_project


def test_netlist_and_sheet_tree_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    write_files(built_nested(), source)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("pure conversion runs no tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    conversion = convert_project(source / "nested.kicad_pro", to="altium", allow_lossy=True)
    assert len([f for f in conversion.files if f.endswith(".SchDoc")]) == 4
    assert "nested.PcbLib" in conversion.files
    row = conversion.report.row("schematic")
    assert row is not None and row.changed == 1 and row.lost == 0
    assert row.reasons[0].reason == "positions and wires are not converted"
    target = tmp_path / "target"
    target.mkdir()
    for name, data in conversion.files.items():
        (target / name).write_bytes(data)
    compared = equivalent(source / "nested.kicad_sch", target / "nested.PrjPcb", level=2)
    assert compared.report.differences == ()
