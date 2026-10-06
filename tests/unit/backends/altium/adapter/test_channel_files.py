# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored two-channel project as files (capability altium-import, "Repeated sheets as channels",
"Channel designators", "Channel nets"; change c0083): ``tests/data/altium/channels/two/`` equals what its
script writes, and reading the folder gives the channels."""

from __future__ import annotations

import shutil
from pathlib import Path

import _altium_channels as two

from fenolite.backends.altium.backend import AltiumBackend

FOLDER = Path(__file__).resolve().parents[4] / "data" / "altium" / "channels" / "two"


def test_files_equal_what_the_script_writes() -> None:
    written = two.files()
    assert sorted(written) == sorted(p.name for p in FOLDER.iterdir() if p.suffix != ".py")
    for name, data in written.items():
        assert (FOLDER / name).read_bytes() == data, name


def test_folder_reads_as_two_channels(tmp_path: Path) -> None:
    """Scenarios "Two channels", "Designators from the naming format" and "Shared and per-channel nets",
    on the files: no PCB document and no annotation file."""
    folder = tmp_path / "two"
    shutil.copytree(FOLDER, folder, ignore=shutil.ignore_patterns("*.py"))
    backend = AltiumBackend()
    read = backend.read_documents(backend.documents(folder))
    assert read.schematic is not None and read.pcb is None
    circuit = read.schematic.design.circuit
    assert sorted(module.path for module in circuit.modules) == ["CH[1]", "CH[2]"]
    assert sorted(c.ref for c in circuit.components) == ["C12_CH1", "C12_CH2", "J1", "R1_CH1", "R1_CH2", "U1"]
    refs = {component.id: component.ref for component in circuit.components}
    nets = {net.name: sorted((refs[m.component_id], m.pin) for m in net.members) for net in circuit.nets}
    assert nets["VCC"] == [("J1", "1"), ("R1_CH1", "1"), ("R1_CH2", "1")]
    assert nets["OUT1"] == [("C12_CH1", "2"), ("U1", "1")] and nets["OUT2"] == [("C12_CH2", "2"), ("U1", "2")]
    assert sorted(name for name in nets if name.startswith("MID")) == ["MID_CH1", "MID_CH2"]
    codes = {issue.code for issue in read.schematic.issues}
    assert "altium.import.channels" in codes
    assert not codes & {"altium.import.repeated-sheet", "altium.import.channel-naming"}
