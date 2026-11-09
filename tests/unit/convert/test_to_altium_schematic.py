# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic circuit, embedded graphics and hierarchy preserved in conversion (c0160 task 4.1)."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from _schbuild import built_nested, write_files

from fenolite.api import equivalent
from fenolite.api.sides import read_schematic
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.convert import convert_project, read_source
from fenolite.convert.direction import TargetLimitError
from fenolite.model.design import Design


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
    # the drawing of the source sheets is converted (change c0470): the schematic is written unchanged
    assert row is not None and row.changed == 0 and row.lost == 0
    assert conversion.report.row("sheet") is not None
    target = tmp_path / "target"
    target.mkdir()
    for name, data in conversion.files.items():
        (target / name).write_bytes(data)
    compared = equivalent(source / "nested.kicad_sch", target / "nested.PrjPcb", level=2)
    assert compared.report.differences == ()


@pytest.mark.parametrize("prepared", [False, True])
def test_no_connect_marks_survive_conversion(tmp_path: Path, prepared: bool) -> None:
    source = tmp_path / "source"
    source.mkdir()
    write_files(built_nested(), source)
    project = read_source(source / "nested.kicad_pro")
    if prepared:
        project = replace(project, schematic=read_schematic(source / "nested.kicad_sch").design)
    conversion = convert_project(project, to="altium", allow_lossy=True)
    target = tmp_path / "target"
    target.mkdir()
    for name, data in conversion.files.items():
        (target / name).write_bytes(data)
    backend = AltiumBackend()
    schematic = backend.read_documents(backend.documents(target / "nested.PrjPcb")).schematic
    assert schematic is not None
    readback = schematic.content
    assert isinstance(readback, Design)
    refs = {c.id: c.ref for c in readback.circuit.components}
    marked = {(refs[m.component_id], m.pin) for m in readback.circuit.no_connects}
    expected = {("U1", str(pin)) for pin in range(1, 33) if pin not in (1, 2, 9, 10)}
    assert marked == expected
    connected = {(refs[m.component_id], m.pin) for n in readback.circuit.nets for m in n.members}
    assert not marked & connected
    assert equivalent(source / "nested.kicad_sch", target / "nested.PrjPcb", level=2).equivalent


def test_off_grid_symbol_pin_refused_as_target_limit(tmp_path: Path) -> None:
    """A pin length off whole mils and off Altium's 127/50 nm step is a target limit (FEN-7001), not an
    internal error (c0160); one on whole mils off the 10-mil grid is written with its ``_FRAC`` keys and
    ``PinFrac`` entry (c0470)."""
    source = tmp_path / "source"
    source.mkdir()
    write_files(built_nested(), source)
    sch = source / "nested.kicad_sch"
    text = sch.read_text(encoding="utf-8")
    assert "(length 2.54)" in text
    sch.write_text(text.replace("(length 2.54)", "(length 1.9)", 1), encoding="utf-8")
    with pytest.raises(
        TargetLimitError,
        match=r"pin 1 x: -?\d+ nm is not a whole number of mils nor a length of Altium's 127/50 nm step",
    ) as raised:
        convert_project(source / "nested.kicad_pro", to="altium", allow_lossy=True)
    assert raised.value.cli_code == "FEN-7001"
    assert "whole mils" in raised.value.hint
    sch.write_text(text.replace("(length 2.54)", "(length 1.905)", 1), encoding="utf-8")
    written = convert_project(source / "nested.kicad_pro", to="altium", allow_lossy=True).files
    assert any(b"PINLENGTH_FRAC=50000" in data for name, data in written.items() if name.endswith(".SchDoc"))
