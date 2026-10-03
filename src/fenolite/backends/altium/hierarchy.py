# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A design split into the sheets of a hierarchical Altium project (change c0037, capability
altium-schematic-writer, "Sheets of a hierarchical project").

With the sheet mode ``modules`` the top sheet holds the parts outside any module and one sheet symbol per
top-level module, and each top-level module gets its own sheet; deeper modules are flattened into the sheet
of their top-level module. A net **crosses** a module when it has pins on that module's sheet and on
another sheet: it then gets a port on the module's sheet and a sheet entry of the same name on the sheet
symbol. Nets of a ``power`` interface never cross, because their power ports are global. In the binary
form a ``harness`` interface whose nets cross a module crosses it as one port and one sheet entry, each with
a harness block (``layout.HarnessBlock``). The facts are in
``docs/formats/altium/schematic-ascii.md`` ("Sheet symbols, sheet entries and ports") and
``docs/formats/altium/project.md``; the split itself is a Fenolite choice.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fenolite.backends.altium.altsym import AltiumSymbol
from fenolite.backends.altium.layout import Crossing, PartSpec, SheetPlan, SymbolSpec, layout_sheet
from fenolite.backends.altium.project import (
    SchematicForm,
    SheetMode,
    component_path,
    part_specs,
    plan_sheet,
    power_styles,
    unique_id,
)
from fenolite.core.evidence import Evidence, Level
from fenolite.model.circuit import Component, Interface
from fenolite.model.design import Design

EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-SCH-HARN-FILE",
        "H-A-SCH-HARN-NETS",
        "H-A-SCH-HARN-OPEN",
        "H-A-SCH-HARN-UNUSED",
        "H-A-SCH-HIER-COMPILE",
        "H-A-SCH-HIER-ECO",
        "H-A-SCH-HIER-NAMES",
        "H-A-SCH-HIER-OPEN",
        "H-A-SCH-HIER-PRJ",
    ),
)
"""The hierarchy and harness facts are inferred from public sources until the maintainer's report of Part
H (``docs/evidence/altium-schematic.md``); no oracle reads a schematic document."""
SHEET_SUFFIX = ".SchDoc"
PATH_SEPARATOR = "/"


@dataclass(frozen=True)
class SheetFile:
    """One schematic sheet: its file name beside the project, its layout and, for a module sheet, the
    module name and the unique id of its sheet symbol on the top sheet."""

    file: str
    plan: SheetPlan
    module: str | None = None
    symbol_id: str | None = None


@dataclass(frozen=True)
class ProjectSheets:
    """The sheets of a project: the top sheet first, then the module sheets in module-name order."""

    mode: SheetMode
    sheets: tuple[SheetFile, ...]

    @property
    def top(self) -> SheetFile:
        return self.sheets[0]

    @property
    def modules(self) -> tuple[SheetFile, ...]:
        return self.sheets[1:]


def sheet_of(component: Component) -> str | None:
    """The module whose sheet holds ``component``: the first segment of its component path when the path
    holds a ``/``, and ``None`` (the top sheet) otherwise."""
    head, slash, _rest = component_path(component).partition(PATH_SEPARATOR)
    return head if slash else None


def sheet_file(name: str, module: str | None = None) -> str:
    """``<name>.SchDoc`` for the top sheet, ``<name>_<module>.SchDoc`` for a module's sheet."""
    return f"{name}{SHEET_SUFFIX}" if module is None else f"{name}_{module}{SHEET_SUFFIX}"


def symbol_id(module: str) -> str:
    """The unique id of the sheet symbol of ``module``."""
    return unique_id(f"sheet:{module}")


def port_id(module: str, name: str) -> str:
    """The unique id of the port ``name`` on the sheet of ``module``."""
    return unique_id(f"port:{module}:{name}")


def _form(form: str) -> None:
    if form not in ("binary", "ascii"):
        raise ValueError(f"unknown schematic form {form!r}")


HARNESS_KIND = "harness"
"""The kind of the model interfaces that ``fenolite.dsl.Harness`` records."""


def harness_interfaces(design: Design) -> list[Interface]:
    """The ``harness`` interfaces of ``design``, in code-point order of their names."""
    found = [i for i in design.circuit.interfaces if i.kind == HARNESS_KIND]
    return sorted(found, key=lambda i: i.name)


def crossings(design: Design, *, form: SchematicForm) -> dict[str, tuple[Crossing, ...]]:
    """Top-level module → its crossings, in code-point order of their names; every top-level module of the
    design has an entry, in module-name order. A net that is not a member of a ``power`` interface crosses a
    module when the module's sheet and another sheet each hold one of its pins. In the binary form a
    ``harness`` interface crosses a module when one of its member nets does: those nets then travel in the
    harness and get no port of their own there. In the ASCII form no harness crosses."""
    _form(form)
    sheets = {c.id: sheet_of(c) for c in design.circuit.components}
    modules = sorted({module for module in sheets.values() if module is not None})
    power = set(power_styles(design))
    names = {net.id: net.name for net in design.circuit.nets}
    crossing: dict[str, set[str]] = {module: set() for module in modules}
    for net in design.circuit.nets:
        if net.id in power:
            continue
        on = {sheets[m.component_id] for m in net.members if m.component_id in sheets}
        if len(on) < 2:
            continue
        for module in on:
            if module is not None:
                crossing[module].add(net.id)
    harnesses = harness_interfaces(design) if form == "binary" else []
    owner: dict[str, str] = {}
    for interface in harnesses:
        for _entry, net_id in sorted(interface.members.items()):
            owner.setdefault(net_id, interface.id)
    found: dict[str, tuple[Crossing, ...]] = {}
    for module in modules:
        carried: set[str] = set()
        here: list[Crossing] = []
        for interface in harnesses:
            mine = {
                n for n in interface.members.values() if n in crossing[module] and owner[n] == interface.id
            }
            if not mine:
                continue
            carried |= mine
            entries = tuple(
                (entry, names[net_id] if net_id in mine else None)
                for entry, net_id in sorted(interface.members.items())
            )
            here.append(Crossing(interface.name, port_id(module, interface.name), entries))
        here += [
            Crossing(names[net_id], port_id(module, names[net_id])) for net_id in crossing[module] - carried
        ]
        found[module] = tuple(sorted(here, key=lambda c: c.name))
    return found


def plan_sheets(
    design: Design,
    *,
    name: str,
    sheets: SheetMode,
    form: SchematicForm,
    symbols: Mapping[str, AltiumSymbol] | None = None,
) -> ProjectSheets:
    """The sheets of ``design``: the single sheet of ``project.plan_sheet`` for ``flat``; for ``modules``
    the top sheet ``<name>.SchDoc`` and one ``<name>_<module>.SchDoc`` per top-level module. A design
    without a module gives the same top sheet in both modes."""
    _form(form)
    if sheets == "flat":
        return ProjectSheets(
            "flat", (SheetFile(sheet_file(name), plan_sheet(design, name=name, symbols=symbols)),)
        )
    if sheets != "modules":
        raise ValueError(f"unknown sheet mode {sheets!r}")
    crossing = crossings(design, form=form)
    by_sheet: dict[str | None, list[PartSpec]] = {None: [], **{module: [] for module in crossing}}
    for spec in part_specs(design, name=name, symbols=symbols):
        head, slash, _rest = spec.key.partition(PATH_SEPARATOR)
        by_sheet[head if slash else None].append(spec)
    specs = [
        SymbolSpec(module, sheet_file(name, module), symbol_id(module), found)
        for module, found in crossing.items()
    ]
    planned = [SheetFile(sheet_file(name), layout_sheet(by_sheet[None], symbols=specs))]
    for module, found in crossing.items():
        plan = layout_sheet(by_sheet[module], ports=found)
        planned.append(SheetFile(sheet_file(name, module), plan, module, symbol_id(module)))
    return ProjectSheets("modules", tuple(planned))


__all__ = [
    "EVIDENCE",
    "HARNESS_KIND",
    "ProjectSheets",
    "SheetFile",
    "crossings",
    "harness_interfaces",
    "plan_sheets",
    "port_id",
    "sheet_file",
    "sheet_of",
    "symbol_id",
]
