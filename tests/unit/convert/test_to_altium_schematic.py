# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic of a KiCad source converted to Altium (capability altium-schematic-writer, "Schematic of a
converted project" and "Positions of a converted schematic"; change c0160, ``H-A-CONV-SCHEMATIC``).

``tests/data/kicad/parity/agree`` holds a board and the schematic it agrees with; Fenolite's own netlist
reads that schematic, so the comparison runs no tool. The demo ``complex_hierarchy`` (three KiCad sheets)
is converted in ``tests/corpus/test_convert_census.py``.
"""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

from fenolite.api import equivalent
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.backends.kicad import parity_inputs
from fenolite.convert import convert_project, to_altium
from fenolite.convert.schematic import sheet_paths

ROOT = Path(__file__).resolve().parents[3]
AGREE = ROOT / "tests" / "data" / "kicad" / "parity" / "agree"
HIER = ROOT / "tests" / "data" / "kicad" / "schematic" / "hier" / "top.kicad_sch"


def _written(folder: Path, tmp: Path) -> Path:
    conversion = convert_project(folder / "blink.kicad_pcb", to="altium", allow_lossy=True)
    tmp.mkdir(parents=True, exist_ok=True)
    for name, data in conversion.files.items():
        (tmp / name).write_bytes(data)
    return tmp


def test_netlist_kept(tmp_path: Path) -> None:
    """The written schematic holds the KiCad schematic's components and netlist: levels 1 and 2 of
    ``equivalent`` against the KiCad schematic report no difference."""
    out = _written(AGREE, tmp_path / "out")
    design = AltiumBackend().read(out / "blink.PrjPcb").design
    result = equivalent(dataclasses.replace(design, board=None), AGREE / "blink.kicad_sch")
    levels = {level.level: level for level in result.report.levels}
    assert set(levels) == {1, 2}
    assert result.report.differences == ()
    assert levels[1].compared == len(design.circuit.components) > 0


def test_symbols_come_from_the_schematic(tmp_path: Path) -> None:
    """The library symbols are the schematic's ``lib_symbols`` drawn from their graphics, and the report
    says that positions and wires are not converted."""
    conversion = convert_project(AGREE / "blink.kicad_pcb", to="altium", allow_lossy=True)
    row = conversion.report.row("schematic")
    assert row is not None and row.changed == 1
    assert [reason.reason for reason in row.reasons] == [to_altium.CONVERTED_SCHEMATIC]
    library = read_schlib(conversion.files["blink.SchLib"], file="blink.SchLib")
    sheets = parity_inputs.read_sheets(AGREE / "blink.kicad_sch")
    names = {symbol.name for sheet in sheets.values() for symbol in sheet.lib_symbols if not symbol.power}
    assert names <= {component.name for component in library.components}


def test_board_alone_keeps_the_generated_sheet(tmp_path: Path) -> None:
    """A board without its schematic keeps the generated sheet of generic symbols."""
    shutil.copy(AGREE / "blink.kicad_pcb", tmp_path / "blink.kicad_pcb")
    conversion = convert_project(tmp_path / "blink.kicad_pcb", to="altium", allow_lossy=True)
    row = conversion.report.row("schematic")
    assert row is not None and [reason.reason for reason in row.reasons] == [to_altium.CHANGES["schematic"]]


def test_sheet_paths_of_a_tree() -> None:
    """Each sheet instance of the tree gets a module path named after its sheet, the root ``""``."""
    sheets = parity_inputs.read_sheets(HIER)
    found = sheet_paths(sheets, HIER.name, HIER.stem)
    assert sorted(found.values())[0] == "" and len(found) == 1 + sum(len(s.sheets) for s in sheets.values())
    assert all(path.count("/") == 0 for path in found.values())
