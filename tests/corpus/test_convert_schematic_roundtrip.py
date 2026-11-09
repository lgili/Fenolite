# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A drawing converted there and back keeps itself (change c0470, task 5.4; capability design-conversion,
"Sheet carriers" and "Converted drawing verified").

Altium → KiCad → Altium on ``blink`` and the built ``examples/altium_hier_board`` (the way back reads a real
KiCad drawing, so it needs ``kicad-cli`` for the netlist), and the drawing of ``hier`` (no PCB document)
through ``convert/schematic.py`` both ways. Level S finds no difference between the source drawing and the
drawing read back.

KiCad → Altium → KiCad on every public KiCad 10.0.6 demo project with a schematic: ``convert`` both ways, no
unexplained difference either way, and level S between the source drawing and the one read back. A demo
without a board (the simulation demos) goes to Altium with an empty board, which writes no PCB document; its
way back goes through ``convert/schematic.py``, as ``hier``'s does, since ``convert`` takes no project without
a PCB design (change c0364). ``EXCLUDED`` names the demos left out and why."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import _schcorpus
import _schprojects
import pytest
from _corpus import manifest_items, require
from _drawings import BLINK, HIER, altium_drawing, hier_board, paths_of

from fenolite.api import convert
from fenolite.backends.altium import drawn_read
from fenolite.backends.altium.adapter.netlist import SheetInput
from fenolite.backends.altium.altsym import AltiumSymbol, from_symbol_def
from fenolite.backends.altium.read import sch
from fenolite.backends.kicad import drawn as kicad_drawn
from fenolite.backends.kicad import parity_inputs, sym
from fenolite.checks.equivalence.drawn import compare_drawn
from fenolite.convert import schematic as drawing_lib
from fenolite.convert.sources import read_source
from fenolite.core.libnames import library_name
from fenolite.model.circuit import Component

pytestmark = pytest.mark.long_flow


def _write(files: dict[str, bytes], folder: Path) -> None:
    for name, data in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)


@pytest.mark.needs_kicad
@pytest.mark.parametrize("name", ["blink", "altium_hier_board"])
def test_altium_to_kicad_and_back(name: str, tmp_path: Path) -> None:
    project = BLINK if name == "blink" else hier_board(tmp_path / "source")
    there = convert(project, to="kicad", allow_lossy=True)
    assert there.unexplained == ()
    _write(dict(there.conversion.files), tmp_path / "kicad")
    back = convert(next((tmp_path / "kicad").glob("*.kicad_pro")), to="altium", allow_lossy=True)
    assert back.unexplained == ()
    _write(dict(back.conversion.files), tmp_path / "altium")
    source = altium_drawing(project)
    again = altium_drawing(next((tmp_path / "altium").glob("*.PrjPcb")))
    assert [i.message for i in again.issues if i.severity == "error"] == []
    found = compare_drawn(source.drawn, again.drawn, pins_a=source.pins, pins_b=again.pins)
    assert found.differences == ()


def test_hier_drawing_both_ways() -> None:
    """``hier`` has no PCB document: its drawing goes to KiCad with ``write_kicad_drawing`` and back with
    ``write_altium_drawing``, its harness records carried both ways."""
    name = "altium_hier"
    source = read_source(HIER)
    drawing = drawing_lib.drawing_of(source)
    assert drawing is not None
    written = drawing_lib.write_kicad_drawing(drawing, source.design, name, 10)
    back, _, issues = drawing_lib.read_kicad_drawing(written.files, paths_of(source.design.circuit))
    assert [i.message for i in issues if i.severity == "error"] == []
    library = {s.name: s for s in sym.read_symbol_library(written.files[f"lib/{name}.kicad_sym"])}
    components: list[Component] = []
    symbols: dict[str, AltiumSymbol] = {}
    for component in source.design.circuit.components:
        symbol = f"SYM_{library_name(component.ref)}"
        link = f"{name}.SchLib:{symbol}"
        symbols[link] = from_symbol_def(library[symbol], lib_ref=symbol, footprint=None, bodies="graphics")
        components.append(dataclasses.replace(component, lib_symbol_ref=link))
    circuit = dataclasses.replace(source.design.circuit, components=tuple(components))
    design = dataclasses.replace(source.design, circuit=circuit)
    files, written_issues = drawing_lib.write_altium_drawing(back, design, symbols, name)
    assert [i.message for i in written_issues if i.severity == "error"] == []
    sheets = [
        SheetInput(n, "", sch.read_schematic(d, file=n)) for n, d in files.items() if n.endswith(".SchDoc")
    ]
    sheets.sort(key=lambda s: s.file != f"{name}.SchDoc")
    again = drawn_read.extract_with_pins(sheets)
    found = compare_drawn(
        drawing.extracted.drawn, again.drawn, pins_a=drawing.extracted.pins, pins_b=again.pins
    )
    assert found.differences == ()


# --- the public KiCad demo projects (task 5.4) ----------------------------------------------------------

EXCLUDED = {
    "kicad-demo-10-0-6-sch-003": "cm5_minima holds a BOM-only symbol, which no Altium writer holds (c0334)",
}
"""The demo projects left out, with the reason; a project below Fenolite's read floor is not a root here."""
OPEN: dict[str, str] = {}
"""The demo projects whose way there and back is open work: each fails until its task lands."""
DEMOS = tuple(row for row in _schprojects.roots(10) if _schprojects.readable(row, 10))
_DEMO_PARAMS = tuple(
    pytest.param(row, id=row.id, marks=pytest.mark.xfail(reason=OPEN[row.id], strict=True))
    if row.id in OPEN
    else pytest.param(row, id=row.id)
    for row in DEMOS
)


def _kicad_drawing(project: Path) -> kicad_drawn.Extracted:
    """The drawing of a KiCad project, its parts named as its conversion names them."""
    from dataclasses import replace

    from fenolite.api.sides import read_schematic

    read = read_source(project)
    root = drawing_lib.root_schematic(read)
    assert root is not None
    read = replace(read, schematic=read_schematic(root).design)
    design, _, _ = drawing_lib.inputs(read, read.design)
    assert design is not None
    sheets = parity_inputs.read_sheets(root)
    first = next(iter(sheets))
    children = {key: value for key, value in sheets.items() if key != first}
    paths = kicad_drawn.refs_to_paths(design.circuit)
    return kicad_drawn.extract_with_pins(sheets[first], children, components=paths, root_file=first)


@pytest.mark.needs_corpus
@pytest.mark.needs_kicad
@pytest.mark.slow
@pytest.mark.parametrize("row", _DEMO_PARAMS)
def test_kicad_demo_there_and_back(row: _schcorpus.SchRow, tmp_path: Path) -> None:
    if row.id in EXCLUDED:
        pytest.skip(EXCLUDED[row.id])
    require(next(item for item in manifest_items("sch") if item.id == row.id))
    folder = _schprojects.project_folder(tmp_path / "source", row, 10)
    assert folder is not None
    project = folder / f"{Path(row.path).stem}.kicad_pro"
    there = convert(project, to="altium", allow_lossy=True, pour="outline")
    assert there.unexplained == ()
    assert there.conversion.report.row("sheet") is not None, "the source drawing was not written"
    _write(dict(there.conversion.files), tmp_path / "altium")
    altium = next((tmp_path / "altium").glob("*.PrjPcb"))
    source = _kicad_drawing(project)
    if any(name.endswith(".PcbDoc") for name in there.conversion.files):
        back = convert(altium, to="kicad", allow_lossy=True)
        assert back.unexplained == ()
        _write(dict(back.conversion.files), tmp_path / "kicad")
        again = _kicad_drawing(next((tmp_path / "kicad").glob("*.kicad_pro")))
        drawn, pins = again.drawn, again.pins
    else:  # no PCB document: the drawing comes back through convert/schematic.py
        read = read_source(altium)
        drawing = drawing_lib.drawing_of(read)
        assert drawing is not None
        written = drawing_lib.write_kicad_drawing(drawing, read.design, "back", 10)
        _, renamed = drawing_lib.refolded(drawing.extracted)
        paths = {ref: renamed.get(path, path) for ref, path in paths_of(read.design.circuit).items()}
        drawn, pins, issues = drawing_lib.read_kicad_drawing(written.files, paths, "back.kicad_sch")
        assert [i.message for i in issues if i.severity == "error"] == []
    found = compare_drawn(source.drawn, drawn, pins_a=source.pins, pins_b=pins)
    assert found.differences == ()
