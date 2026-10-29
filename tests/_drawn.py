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
from fenolite.dsl import Design
from fenolite.lens.build import BuildOutput
from fenolite.lens.drawn import read_drawn
from fenolite.model.circuit import Circuit
from fenolite.model.drawn import DrawnSchematic
from fenolite.model.drawn_connect import DrawnNetlist, resolve
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
