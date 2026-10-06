# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Symbol graphics written by Fenolite against ``kicad-cli sym upgrade`` (capability
altium-schematic-writer, "Symbol graphics in libraries and bodies"; change c0086).

The round trip is: catalog symbols → ``from_symbol_def`` → ``write_schlib`` → ``kicad-cli sym upgrade``
(KiCad's Altium importer, S-0153) → ``backends.kicad.sym.read_symbol_library`` → compare the graphics
with the model's. A pass checks only what KiCad's importer reads of a library; it settles no Altium-only
fact.

``kicad-cli`` reads a schematic library (``sym upgrade``, used here) and no schematic document: on
10.0.6 ``sch export netlist``, ``sch upgrade`` and ``sch erc`` each answer ``Failed to load schematic``
(exit 3) for a ``.SchDoc`` (S-0020), so the sheet tree, the netlist and the bus members of a built
project have no command-line oracle: task 5.2 of the change keeps that part open. On kicad-cli 9 a
library that does not convert is expected to fail (``H-A-SCHLIB-KICAD9``).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from functools import cache
from pathlib import Path

import pytest
from _altium_tree import project_files, tree_build
from _resources import kicad_cli, kicad_cli_major

from fenolite.backends.altium.altsym import from_symbol_def
from fenolite.backends.altium.schlib import write_schlib
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.catalog import get_symbol, list_entries
from fenolite.model.library import SymbolDef

pytestmark = pytest.mark.needs_kicad

Shape = tuple[str, tuple[tuple[int, int], ...], bool]
OFF_GRID = ("Fenolite:Potentiometer", "Fenolite:Terminal_1Pin")
"""Catalog symbols with a pin off the 10-mil grid, which the writer refuses (``altium.symbol-off-grid``)."""


def convert(data: bytes) -> dict[str, SymbolDef]:
    """``kicad-cli sym upgrade`` on ``data``, with an empty configuration folder; the symbols by name."""
    cli = kicad_cli()
    assert cli is not None
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source, target = root / "lib.SchLib", root / "out.kicad_sym"
        source.write_bytes(data)
        env = {**os.environ, "KICAD_CONFIG_HOME": str(root / "config")}
        proc = subprocess.run(
            [cli, "sym", "upgrade", str(source), "-o", str(target)],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            check=False,
        )
        if proc.returncode != 0 and kicad_cli_major() == 9:
            pytest.xfail(f"kicad-cli 9 does not convert the library: exit {proc.returncode}")
        assert proc.returncode == 0, (proc.stdout + proc.stderr).strip()
        return {symbol.name: symbol for symbol in read_symbol_library(target, library="out")}


def shapes(symbol: SymbolDef) -> list[Shape]:
    """The graphics of a symbol in an order-free form: a rectangle by its two extreme corners, every
    other kind by its points as given."""
    found: list[Shape] = []
    for graphic in symbol.graphics:
        points = tuple((p.x, p.y) for p in graphic.points)
        if graphic.kind == "rect":
            xs, ys = [x for x, _ in points], [y for _, y in points]
            points = ((min(xs), min(ys)), (max(xs), max(ys)))
        found.append((graphic.kind, points, graphic.filled))
    return sorted(found)


def near(mine: list[Shape], theirs: list[Shape]) -> bool:
    """``mine`` (read by KiCad) against ``theirs`` (the model): equal kinds, each coordinate within 1 µm
    (KiCad writes the library in millimetres with three decimals; one ``_FRAC`` step is 2.54 nm), and no
    line, rectangle or polygon filled that the model leaves open. Two things KiCad 10.0.6 does are not
    compared: it gives some filled shapes the fill type ``color`` with the record's area colour instead of
    ``background`` (Fenolite's KiCad reader calls only ``background`` and ``outline`` filled), and it
    reads every circle as filled, an ellipse record without ``ISSOLID`` too
    (``schematic-library.md``, "Oracle observations")."""
    mine = sorted(mine, key=lambda shape: shape[:2])
    theirs = sorted(theirs, key=lambda shape: shape[:2])
    if [(k, len(p)) for k, p, _ in mine] != [(k, len(p)) for k, p, _ in theirs]:
        return False
    for (kind, _, read), (_, _, model) in zip(mine, theirs, strict=True):
        if read and not model and kind != "circle":
            return False
    return all(
        abs(a - b) <= 1_000
        for (_, first, _), (_, second, _) in zip(mine, theirs, strict=True)
        for p, q in zip(first, second, strict=True)
        for a, b in zip(p, q, strict=True)
    )


@cache
def catalog() -> dict[str, SymbolDef]:
    return {
        entry.lib_id.partition(":")[2]: get_symbol(entry.lib_id)
        for entry in list_entries(kind="symbol")
        if entry.lib_id not in OFF_GRID
    }


def test_catalog_graphics_are_what_kicad_reads() -> None:
    """Every graphic kind the writer draws (line, rectangle, polygon, circle), filled or not, on and off
    the 10-mil grid: KiCad's importer reads each catalog symbol's graphics as the model holds them."""
    symbols = [from_symbol_def(symbol, lib_ref=name, footprint=None) for name, symbol in catalog().items()]
    assert all(symbol.drawn for symbol in symbols)
    read = convert(write_schlib(symbols, library="catalog.SchLib"))
    assert sorted(read) == sorted(catalog())
    kinds: set[str] = set()
    for name, symbol in catalog().items():
        assert near(shapes(read[name]), shapes(symbol)), name
        assert len(read[name].pins) == len(symbol.pins), name
        kinds |= {graphic.kind for graphic in symbol.graphics}
    assert kinds == {"circle", "line", "polygon", "rect"}


def test_library_of_the_tree_sample() -> None:
    """The committed sample's library: its eight symbols convert, each with the graphics of its catalog
    symbol and no rectangle that the catalog symbol does not hold."""
    read = convert(project_files(tree_build())["tree.SchLib"])
    assert len(read) == 8
    for name, symbol in read.items():
        assert near(shapes(symbol), shapes(catalog()[name])), name


def test_generic_bodies_stay_one_rectangle() -> None:
    symbol = catalog()["Resistor"]
    written = from_symbol_def(symbol, lib_ref="Resistor", footprint=None, bodies="generic")
    (read,) = convert(write_schlib([written], library="generic.SchLib")).values()
    assert [graphic.kind for graphic in read.graphics] == ["rect"]
