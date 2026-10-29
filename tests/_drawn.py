# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the drawn schematic tests (change c0276): the authored fixtures of ``tests/data/drawn/`` and
``examples/drawn/``, built hermetically, and their sheets read back, extracted and resolved."""

from __future__ import annotations

import runpy
from pathlib import Path

from _buildhelp import build as build_design_of

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad import sch
from fenolite.backends.kicad.schlayout import pin_point
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.dsl import Design, to_model
from fenolite.lens.build import BuildOutput
from fenolite.lens.drawn import read_drawn
from fenolite.model.circuit import Circuit
from fenolite.model.drawn import DrawnSchematic
from fenolite.model.drawn_connect import DrawnNetlist, PinKey, PinPoint, component_path, resolve
from fenolite.model.library import SymbolDef
from fenolite.model.schematic import SchematicSheet

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "data" / "drawn"
EXAMPLE = ROOT / "examples" / "drawn"
NAMES = ("flat", "full", "hier", "bus", "repeat")
"""The authored fixtures, each a folder with ``design.py``, ``schematic.toml`` and library tables."""


def folder(name: str) -> Path:
    """The folder of fixture ``name``; ``example`` is ``examples/drawn``."""
    return EXAMPLE if name == "example" else FIXTURES / name


def design(name: str) -> Design:
    found = runpy.run_path(str(folder(name) / "design.py"))["design"]
    assert isinstance(found, Design)
    return found


def text(name: str) -> str:
    return (folder(name) / "schematic.toml").read_text(encoding="utf-8")


def drawn(name: str) -> DrawnSchematic:
    return read_drawn(text(name), file="schematic.toml")


def build(name: str, target: int = 10, value: DrawnSchematic | None = None, **kwargs: object) -> BuildOutput:
    """The build of fixture ``name`` with its drawn schematic (or ``value``), hermetic: the project tables of
    the fixture's folder only."""
    return build_design_of(
        design(name),
        target,
        project_dir=folder(name),
        drawn=value if value is not None else drawn(name),
        drawn_file="schematic.toml",
        **kwargs,
    )


def sheets(output: BuildOutput) -> tuple[SchematicSheet, dict[str, SchematicSheet]]:
    """The root and the child sheets that ``output`` plans, read back."""
    texts = {p: d.decode("utf-8") for p, d in output.files.items() if p.endswith(".kicad_sch")}
    root_file = root_name(output)
    root = sch.read_schematic(texts[root_file], file=root_file)
    children = {p: sch.read_schematic(t, file=p) for p, t in texts.items() if p != root_file}
    return root, children


def library() -> dict[str, SymbolDef]:
    """The authored mini library by lib id (``Mini:<name>``)."""
    text = (ROOT / "tests" / "data" / "libs" / "Mini_v9.kicad_sym").read_text(encoding="utf-8")
    return {f"Mini:{symbol.name}": symbol for symbol in read_symbol_library(text, library="Mini")}


def pins(value: DrawnSchematic, name: str) -> dict[PinKey, tuple[PinPoint, ...]]:
    """The pin points of every drawn item of ``value``, from the mini library and the components of fixture
    ``name``: no build, no file but the library."""
    symbols = library()
    components = {component_path(c): c for c in to_model(design(name)).circuit.components}
    found: dict[PinKey, tuple[PinPoint, ...]] = {}
    for instance in value.walk()[0]:
        sheet = value.sheet(instance.sheet)
        assert sheet is not None
        for k, symbol in enumerate(sheet.symbols):
            component = components.get(instance.component(symbol.part))
            if component is None or (sheet.key, "symbol", k) in found:
                continue
            definition = symbols[component.lib_symbol_ref]
            found[(sheet.key, "symbol", k)] = tuple(
                PinPoint(
                    pin.number,
                    pin_point(symbol.at, pin.position, symbol.rotation // 1_000_000, symbol.mirror),
                    pin.etype,
                    pin.hidden,
                    pin.name,
                )  # fmt: skip
                for pin in definition.pins_of(symbol.unit, 1)
            )
        for k, power in enumerate(sheet.powers):
            definition = symbols[power.symbol]
            found[(sheet.key, "power", k)] = tuple(
                PinPoint(
                    pin.number,
                    pin_point(power.at, pin.position, power.rotation // 1_000_000),
                    pin.etype,
                    pin.hidden,
                    pin.name,
                )  # fmt: skip
                for pin in definition.pins_of(1, 1)
            )
    return found


def netlist(name: str, value: DrawnSchematic | None = None) -> DrawnNetlist:
    """The nets of fixture ``name`` (or of ``value`` with the components of ``name``), from the file alone."""
    found = value if value is not None else drawn(name)
    return resolve(found, pins(found, name), design_name=name)


def circuit(name: str) -> Circuit:
    return to_model(design(name)).circuit


def root_name(output: BuildOutput) -> str:
    """The root schematic file of ``output``."""
    return next(p for p in output.files if p.endswith(".kicad_sch") and "/" not in p)


def resolved(output: BuildOutput) -> tuple[DrawnSchematic, DrawnNetlist, Circuit]:
    """The drawn schematic that ``output``'s sheets give back, its nets and the circuit of the build."""
    root, children = sheets(output)
    circuit = output.design.circuit
    found = kdrawn.extract_with_pins(
        root, children, components=kdrawn.refs_to_paths(circuit), root_file=root_name(output)
    )
    return found.drawn, resolve(found.drawn, found.pins), circuit


__all__ = [
    "EXAMPLE",
    "FIXTURES",
    "NAMES",
    "build",
    "design",
    "drawn",
    "folder",
    "resolved",
    "root_name",
    "sheets",
    "text",
]
