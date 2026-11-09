# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawings of converted projects for the tests of change c0470: the source drawing of an Altium project
(``backends/altium/drawn_read``) and the drawing read back from written KiCad files
(``backends/kicad/drawn.extract_with_pins``), compared at level S."""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Mapping
from pathlib import Path

from fenolite.backends.altium import drawn_read
from fenolite.backends.altium.adapter.netlist import SheetInput
from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.project import read_project
from fenolite.backends.kicad import drawn as kicad_drawn
from fenolite.backends.kicad import parity_inputs
from fenolite.checks.equivalence.drawn import compare_drawn
from fenolite.checks.equivalence.model import LevelResult
from fenolite.model.circuit import Circuit

ROOT = Path(__file__).resolve().parents[1]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
HIER = ROOT / "tests" / "data" / "altium" / "hier" / "altium_hier.PrjPcb"
HIER_BOARD = ROOT / "examples" / "altium_hier_board" / "design.py"
"""The authored hierarchy with a board (change c0037): ``hier`` has no PCB document, so ``convert`` and
``import`` take this project, built for Altium with module sheets."""


def hier_board(folder: Path) -> Path:
    """The Altium project of ``examples/altium_hier_board`` built into ``folder``; returns its ``.PrjPcb``."""
    from fenolite.cli.main import invoke

    argv = ["build", str(HIER_BOARD), "--out", str(folder), "--target", "altium"]
    argv += ["--altium-sheets", "modules", "--confirm", "--seed", "1", "--timestamp", "2026-11-07T00:00:00Z"]
    code, _, error = invoke(argv, cwd=HIER_BOARD.parent)
    assert code == 0, error
    return folder / "altium_hier_board.PrjPcb"


def altium_sheets(project: Path) -> list[SheetInput]:
    """The read schematic documents of an Altium project, in project order."""
    listed = read_project(project.read_bytes(), file=project.name)
    found: list[SheetInput] = []
    for document in listed.documents:
        path = project.parent / document.path.replace("\\", "/")
        if path.suffix.lower() == ".schdoc" and path.is_file():
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            found.append(SheetInput(path.name, digest, sch.read_schematic(data, file=path.name)))
    return found


def altium_drawing(project: Path) -> drawn_read.Extracted:
    return drawn_read.extract_with_pins(altium_sheets(project))


def kicad_drawing(files: Mapping[str, bytes], paths: Mapping[str, str]) -> kicad_drawn.Extracted:
    """The drawing of the written KiCad project ``files``; ``paths`` maps a reference to its component
    path."""
    with tempfile.TemporaryDirectory(prefix="fenolite-c0470-") as folder:
        root = Path(folder)
        for name, data in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        sheet = next(p for p in root.glob("*.kicad_sch"))
        sheets = parity_inputs.read_sheets(sheet)
    first = next(iter(sheets))
    children = {name: value for name, value in sheets.items() if name != first}
    return kicad_drawn.extract_with_pins(sheets[first], children, components=paths, root_file=first)


def paths_of(circuit: Circuit) -> dict[str, str]:
    """Reference → component path: the path an imported component holds, else the KiCad mapping."""
    held = {c.ref: c.path for c in circuit.components if c.ref and c.path}
    return kicad_drawn.refs_to_paths(circuit) | held


def level_s(source: drawn_read.Extracted, written: kicad_drawn.Extracted) -> LevelResult:
    return compare_drawn(source.drawn, written.drawn, pins_a=source.pins, pins_b=written.pins)
