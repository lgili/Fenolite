# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tree sample of change c0086 (``tests/data/altium/tree/design.py``): the design, its model with the
bus ``D`` that the DSL cannot declare, its build, and its nets written out by hand from the script."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.sch import SchDocument, read_schematic
from fenolite.catalog import get_symbol
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput
from fenolite.model.circuit import Bus, BusMember
from fenolite.model.design import Design as ModelDesign
from fenolite.model.library import SymbolDef

ROOT = Path(__file__).resolve().parents[1]
TREE_DIR = ROOT / "tests" / "data" / "altium" / "tree"
TREE = TREE_DIR / "design.py"
TREE_NETS: dict[str, set[tuple[str, str]]] = {
    "VIN": {("J1", "1"), ("U2", "1")},
    "GND": {("J1", "2"), ("U1", "5"), ("U2", "2"), ("C1", "2"), ("U3", "5"), ("Q1", "3")},
    "VREG": {("U2", "3"), ("L1", "1")},
    "+3V3": {("L1", "2"), ("C1", "1"), ("U1", "4"), ("U3", "4")},
    "SENSE_IN": {("J1", "3"), ("U3", "2")},
    "SENSE": {("U3", "1"), ("U3", "3"), ("U1", "2")},
    "REF": {("J1", "4"), ("U1", "3")},
    "ALARM": {("U1", "1"), ("Q1", "1")},
    "LED_K": {("Q1", "2"), ("D1", "2"), ("D2", "2"), ("D3", "2"), ("D4", "2")},
    "D0": {("J2", "1"), ("D1", "1")},
    "D1": {("J2", "2"), ("D2", "1")},
    "D2": {("J2", "3"), ("D3", "1")},
    "D3": {("J2", "4"), ("D4", "1")},
}
"""The sample's thirteen nets as (ref, pin) pairs, written out by hand from the script."""
TREE_FILES = (
    "tree.PrjPcb",
    "tree.SchDoc",
    "tree.SchLib",
    "tree_io.SchDoc",
    "tree_io.leds.SchDoc",
    "tree_power.SchDoc",
)
"""The files of a ``modules`` build of the sample, without ``.fenolite/``."""
ASCII_TEXTS = (("Indutância 10 µH", "Inductor 10 uH"), ("tolerância ±10 %", "tolerance 10 %"))
"""The two texts outside 7-bit ASCII and what the ASCII variant of the sample holds instead."""


def tree(*replacements: tuple[str, str], append: str = "") -> Design:
    """The design of the sample script, with each ``(old, new)`` of ``replacements`` applied to its text
    and ``append`` added to it."""
    source = TREE.read_text(encoding="utf-8")
    for old, new in replacements:
        assert old in source, old
        source = source.replace(old, new)
    namespace: dict[str, object] = {}
    exec(compile(source + append, str(TREE), "exec"), namespace)  # noqa: S102
    design = namespace["design"]
    assert isinstance(design, Design)
    return design


def with_bus(model: ModelDesign, name: str, nets: tuple[str, ...]) -> ModelDesign:
    """``model`` with a bus ``name`` of the nets named ``nets``, in that order."""
    ids = {net.name: net.id for net in model.circuit.nets}
    bus = Bus(
        id=derived_id("bus", "dsl", f"bus:{name}"),
        name=name,
        members=tuple(BusMember(index, ids[net]) for index, net in enumerate(nets)),
    )
    circuit = dataclasses.replace(model.circuit, buses=(*model.circuit.buses, bus))
    return dataclasses.replace(model, circuit=circuit)


def tree_model(*replacements: tuple[str, str], append: str = "") -> ModelDesign:
    """The model of the sample with its bus ``D`` of ``D0`` to ``D3``."""
    return with_bus(to_model(tree(*replacements, append=append)), "D", ("D0", "D1", "D2", "D3"))


def catalog_symbols(model: ModelDesign) -> dict[str, SymbolDef]:
    """Lib id → catalog symbol of every component of ``model``."""
    return {
        lib_id: get_symbol(lib_id) for lib_id in sorted({c.lib_symbol_ref for c in model.circuit.components})
    }


def tree_build(
    model: ModelDesign | None = None,
    *,
    form: str = "binary",
    sheets: str = "modules",
    directions: bool = True,
    **kwargs: object,
) -> BuildOutput:
    """A build of the sample (or of ``model``, a variant of it) with its catalog symbols; ``kwargs`` are
    further arguments of ``build_altium``, such as ``drawing_sheet``."""
    if model is None:
        model = tree_model(*(ASCII_TEXTS if form == "ascii" else ()))
    return build_altium(
        model,
        name="tree",
        form=form,  # type: ignore[arg-type]
        sheets=sheets,  # type: ignore[arg-type]
        directions=directions,
        authored_symbols=catalog_symbols(model),
        symbol_bodies="graphics",
        **kwargs,  # type: ignore[arg-type]
    )


def project_files(output: BuildOutput) -> dict[str, bytes]:
    """The files of a build without the ``.fenolite/`` folder."""
    return {name: data for name, data in output.files.items() if not name.startswith(".fenolite/")}


def documents(output: BuildOutput) -> dict[str, SchDocument]:
    """The schematic sheets of a build, read with the product reader, by file name."""
    return {
        name: read_schematic(data, file=name)
        for name, data in project_files(output).items()
        if name.endswith(".SchDoc")
    }


def read_back(folder: Path, output: BuildOutput) -> ModelDesign:
    """The design that Fenolite's importer reads from the project of a build written under ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    files = project_files(output)
    (project,) = [name for name in files if name.endswith(".PrjPcb")]
    for name, data in files.items():
        (folder / name).write_bytes(data)
    return AltiumBackend().read(folder / project).design


def nets_of(design: ModelDesign) -> dict[str, set[tuple[str, str]]]:
    refs = {c.id: c.ref for c in design.circuit.components}
    return {n.name: {(refs[m.component_id], m.pin) for m in n.members} for n in design.circuit.nets}
