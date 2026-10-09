# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sources of a conversion (capability design-conversion, "Conversion sources"; change c0159)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _buildhelp import blink_variant, build
from _convert import BLINK_T9, BLINK_T10, TWO_LAYER

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.projectset import ProjectNotFoundError
from fenolite.convert import convert_project
from fenolite.convert.sources import SourceError, read_source

ROOT = Path(__file__).resolve().parents[3]
ALTIUM_BLINK = ROOT / "tests" / "data" / "altium" / "blink"


def _power_project(tmp_path: Path) -> Path:
    """The blink built from its script with its power class named ``POWER`` (0.5 mm tracks)."""
    import runpy

    script = blink_variant(tmp_path / "script", 'netclass("PWR"', 'netclass("POWER"')
    design = runpy.run_path(str(script))["design"]
    output = build(design, project_dir=script.parent)
    folder = tmp_path / "project"
    folder.mkdir()
    for name, data in output.files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return next(folder.glob("*.kicad_pro"))


def test_net_classes_come_from_the_project(tmp_path: Path) -> None:
    """Scenario "Net classes come from the project": the class of the project file reaches the written PCB
    document with its nets, and the report loses no net class."""
    project = _power_project(tmp_path)
    source = read_source(project)
    assert source.kind == "kicad_pro" and source.backend == "kicad"
    classes = {c.name: c for c in source.design.circuit.netclasses}
    assert "POWER" in classes and classes["POWER"].track_width == 500_000
    conversion = convert_project(project, to="altium", allow_lossy=True)
    row = conversion.report.row("netclass")
    assert row is not None and row.lost == 0 and row.source >= 1
    document = next(name for name in conversion.files if name.endswith(".PcbDoc"))
    back = AltiumBackend().board_from_bytes(conversion.files[document], file=document).design
    power = next(c for c in back.circuit.netclasses if c.name == "POWER")
    members = sorted(net.name for net in back.circuit.nets if net.netclass_id == power.id)
    expected = sorted(
        net.name for net in source.design.circuit.nets if net.netclass_id == classes["POWER"].id
    )
    assert members == expected and members


def test_board_alone_has_no_class() -> None:
    """A board read without its project holds only what the board says."""
    source = read_source(TWO_LAYER)
    assert source.kind == "kicad_pcb" and source.major == 9 and source.format_version == 20241229
    assert not source.design.circuit.netclasses
    assert source.name == "two_layer" and source.root == TWO_LAYER.parent


def test_folder_resolves_as_check_does(tmp_path: Path) -> None:
    folder = tmp_path / "blink"
    shutil.copytree(BLINK_T9, folder)
    source = read_source(folder)
    assert source.kind == "kicad_pro" and source.path.name == "blink.kicad_pcb" and source.major == 9
    assert {"blink.kicad_pro", "blink.kicad_dru"} <= set(source.files)
    assert read_source(BLINK_T10 / "blink.kicad_pro").major == 10


def test_altium_sources() -> None:
    project = read_source(ALTIUM_BLINK / "blink.PrjPcb")
    board = read_source(ALTIUM_BLINK / "blink.PcbDoc")
    folder = read_source(ALTIUM_BLINK)
    assert (project.backend, project.kind) == ("altium", "altium_prjpcb")
    assert (board.backend, board.kind) == ("altium", "altium_pcbdoc")
    assert folder.path.name == "blink.PrjPcb"


def test_unknown_source_refused(tmp_path: Path) -> None:
    """Scenario "Unknown source refused": a text file is no project; a missing path is FEN-3001."""
    notes = tmp_path / "notes.txt"
    notes.write_text("a note\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no KiCad or Altium project") as refused:
        convert_project(notes, to="altium")
    assert isinstance(refused.value, SourceError) and refused.value.cli_code == "FEN-2001"
    with pytest.raises(SourceError, match="holds no KiCad or Altium project"):
        read_source(tmp_path)
    with pytest.raises(ProjectNotFoundError):
        read_source(tmp_path / "missing.kicad_pcb")


def test_two_backends_in_one_folder(tmp_path: Path) -> None:
    shutil.copy(TWO_LAYER, tmp_path / TWO_LAYER.name)
    shutil.copy(ALTIUM_BLINK / "blink.PrjPcb", tmp_path / "blink.PrjPcb")
    with pytest.raises(SourceError, match="two backends"):
        read_source(tmp_path)
