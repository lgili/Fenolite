# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing of an Altium source survives ``import --to python`` (change c0470, task 6.1; capability
import-python, "Altium import to Python keeps the source drawing")."""

from __future__ import annotations

from pathlib import Path

import pytest
from _drawings import BLINK, altium_drawing

from fenolite.api import run
from fenolite.backends.kicad.drawn import refs_to_paths
from fenolite.checks.equivalence.drawn import compare_drawn
from fenolite.convert import schematic as drawing_lib
from fenolite.importer.source import read_kicad

pytestmark = pytest.mark.long_flow

STAMP = "2026-11-07T00:00:00Z"


def _import(tmp: Path, source: Path) -> None:
    argv = ("import", str(source), "--to", "python", "--out", "code", "--confirm")
    reply = run(*argv, cwd=tmp, timestamp=STAMP)
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))


def _built(tmp: Path) -> dict[str, bytes]:
    reply = run("build", "code/design.py", "--out", "built", "--confirm", cwd=tmp, timestamp=STAMP)
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    assert reply.result["schematic"]["source"] == "drawn"
    folder = tmp / "built"
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def test_flat_project_keeps_its_drawing(tmp_path: Path) -> None:
    """The emitted code loads ``schematic.toml``, and the schematic it builds equals the source drawing
    at level S."""
    _import(tmp_path, BLINK)
    assert (tmp_path / "code" / "schematic.toml").is_file()
    assert 'design.load_schematic("schematic.toml"' in (tmp_path / "code" / "design.py").read_text()
    files = _built(tmp_path)
    project = next((tmp_path / "built").glob("*.kicad_pro"))
    circuit = read_kicad(project).design.circuit
    back, pins, issues = drawing_lib.read_kicad_drawing(files, refs_to_paths(circuit))
    assert [i.message for i in issues if i.severity == "error"] == []
    source = altium_drawing(BLINK)
    found = compare_drawn(source.drawn, back, pins_a=source.pins, pins_b=pins)
    assert found.differences == ()


def test_pcb_document_alone_writes_no_drawing(tmp_path: Path) -> None:
    """A PCB document has no sheets: no ``schematic.toml``, and the build generates its schematic."""
    _import(tmp_path, BLINK.with_suffix(".PcbDoc"))
    assert not (tmp_path / "code" / "schematic.toml").exists()
    assert "load_schematic" not in (tmp_path / "code" / "design.py").read_text()
