# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium backend as a ``DocumentValidator`` (capability altium-verification, "Altium backend validates
documents"; change c0044): document sets, the two readings of a project, container round trips and the
written scope."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends import registry
from fenolite.backends.altium.backend import CAPABILITIES, AltiumBackend, document_validator
from fenolite.backends.altium.docset import document_set
from fenolite.backends.altium.roundtrip import RT_A2_SCOPE, STAGE_EVIDENCE, rt_a0, rt_a1
from fenolite.backends.base import DocumentValidator
from fenolite.checks.assignment_compare import board_netlist, compare, model_netlist
from fenolite.core.errors import FormatError

DATA = Path(__file__).resolve().parents[4] / "tests" / "data" / "altium"
BLINK = DATA / "blink"


@pytest.fixture(autouse=True)
def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("the backend ran a subprocess")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_two_readings_of_one_project(tmp_path: Path) -> None:
    root = Path(shutil.copytree(BLINK, tmp_path / "blink"))
    before = _snapshot(root)
    backend = AltiumBackend()
    documents = backend.documents(root / "blink.PrjPcb")
    assert documents == document_set(root / "blink.PrjPcb")
    read = backend.read_documents(documents)
    assert read.errors == {}
    assert read.schematic is not None and read.pcb is not None
    schematic, pcb = read.schematic.design, read.pcb.design
    assert schematic.board is None and len(schematic.circuit.components) == 3
    assert pcb.board is not None and len(pcb.board.footprints) == 3
    assert schematic.header.name == "blink" and pcb.header.name == "blink"
    # Neither side holds content merged from the other: the schematic's pins carry their electrical
    # types, and the PCB side's circuit is synthesised from the pads.
    assert {p.etype for c in pcb.circuit.components for p in c.pins} == {"unspecified"}
    assert all(c.lib_symbol_ref for c in schematic.circuit.components)
    pair = compare(model_netlist(schematic), board_netlist(pcb)[0])
    assert pair.common > 0 and pair.differences == ()
    assert _snapshot(root) == before


def test_readings_of_single_documents() -> None:
    backend = AltiumBackend()
    sheet = backend.read_documents(backend.documents(BLINK / "blink.SchDoc"))
    assert sheet.pcb is None and sheet.schematic is not None and sheet.errors == {}
    assert sheet.schematic.design.header.name == "blink"
    board = backend.read_documents(backend.documents(BLINK / "blink.PcbDoc"))
    assert board.schematic is None and board.pcb is not None
    library = backend.read_documents(backend.documents(BLINK / "blink.PcbLib"))
    assert library.schematic is None and library.pcb is None and library.errors == {}


def test_readings_of_a_hierarchy_join_the_sheets() -> None:
    """Every sheet of the set is one circuit, with the nets of the whole set."""
    backend = AltiumBackend()
    read = backend.read_documents(backend.documents(DATA / "hier" / "altium_hier.PrjPcb"))
    whole = backend.read(DATA / "hier" / "altium_hier.PrjPcb").design
    assert read.pcb is None and read.schematic is not None
    design = read.schematic.design
    assert sorted(c.ref for c in design.circuit.components) == sorted(c.ref for c in whole.circuit.components)
    assert sorted(n.name for n in design.circuit.nets) == sorted(n.name for n in whole.circuit.nets)
    assert len(design.circuit.modules) == len(whole.circuit.modules) > 0


def test_refused_document_recorded(tmp_path: Path) -> None:
    root = Path(shutil.copytree(BLINK, tmp_path / "blink"))
    board = root / "blink.PcbDoc"
    board.write_bytes(board.read_bytes()[:100])
    backend = AltiumBackend()
    read = backend.read_documents(backend.documents(root))
    assert read.pcb is None and read.schematic is not None
    assert list(read.errors) == ["blink.PcbDoc"] and isinstance(read.errors["blink.PcbDoc"], FormatError)


def test_refused_sheet_empties_the_schematic_side(tmp_path: Path) -> None:
    root = Path(shutil.copytree(BLINK, tmp_path / "blink"))
    sheet = root / "blink.SchDoc"
    sheet.write_bytes(sheet.read_bytes()[:100])
    backend = AltiumBackend()
    read = backend.read_documents(backend.documents(root))
    assert read.schematic is None and read.pcb is not None and list(read.errors) == ["blink.SchDoc"]


def test_container_roundtrip_of_each_kind() -> None:
    backend = AltiumBackend()
    board = BLINK / "blink.PcbDoc"
    assert backend.container_roundtrip(board, "RT-A0") == rt_a0(board.read_bytes(), kind="altium_pcbdoc")
    assert backend.container_roundtrip(board, "RT-A1") == rt_a1(board.read_bytes(), kind="altium_pcbdoc")
    project = backend.container_roundtrip(BLINK / "blink.PrjPcb", "RT-A0")
    assert (project.judged, project.reason) == (False, "not-a-container")
    assert backend.container_roundtrip(BLINK / "blink.PrjPcb", "RT-A1").passed
    ascii_sheet = DATA / "sample" / "altium_sample.SchDoc"
    assert backend.container_roundtrip(ascii_sheet, "RT-A0").reason == "not-a-container"
    assert backend.container_roundtrip(ascii_sheet, "RT-A1").streams == 1
    with pytest.raises(ValueError, match="RT-A2"):
        backend.container_roundtrip(board, "RT-A2")  # type: ignore[arg-type]


def test_container_roundtrip_raises_the_readers_error(tmp_path: Path) -> None:
    cut = tmp_path / "blink.PcbLib"
    cut.write_bytes((BLINK / "blink.PcbLib").read_bytes()[:100])
    for level in ("RT-A0", "RT-A1"):
        with pytest.raises(FormatError):
            AltiumBackend().container_roundtrip(cut, level)  # type: ignore[arg-type]


def test_protocol_satisfied() -> None:
    """Scenario "Protocol satisfied": the registered backend narrows to ``DocumentValidator``."""
    backend = registry.for_path(Path("x.PrjPcb"))
    assert isinstance(backend, DocumentValidator) and isinstance(backend, AltiumBackend)
    assert isinstance(document_validator(), AltiumBackend)
    assert not isinstance(registry.for_path(Path("x.kicad_pcb")), DocumentValidator)
    assert backend.written_scope() is RT_A2_SCOPE
    assert backend.stage_evidence() is STAGE_EVIDENCE
    assert backend.capabilities() is CAPABILITIES and CAPABILITIES.operations == ("detect", "read")
