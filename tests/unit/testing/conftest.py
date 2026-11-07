# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored test circuits, requiring only the installed catalog."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = """from fenolite.dsl import Design, Part, Net, connect, mm
design = Design("testing")
design.board(mm(30), mm(20))
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1000")
r2 = Part("R2", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="2000")
design.add(r1, r2)
connect(Net("GND"), r1[1], r2[1])
r1.place(mm(5), mm(5))
r2.place(mm(15), mm(5))
"""


@pytest.fixture
def script(tmp_path: Path, monkeypatch):
    def refuse(*a, **kw):
        raise AssertionError("external tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    path = tmp_path / "design.py"
    path.write_text(SCRIPT)
    return path
