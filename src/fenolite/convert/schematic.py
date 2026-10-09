# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic of a KiCad source for its conversion to Altium (capability altium-schematic-writer,
"Schematic of a converted project" and "Positions of a converted schematic"; change c0160,
``H-A-CONV-SCHEMATIC``).

``source_schematic`` reads the root schematic of the board's stem and the sheets its tree names
(``parity_inputs.read_sheets``) and gives the design whose circuit the Altium schematic writer takes: the
board's components (their ids, so the PCB document and the schematic link), each with the symbol its
placed symbol names, the pins of that symbol and the path of its KiCad sheet as a module path, and the
board's nets on those pins. The symbols are drawn from the schematic's own ``lib_symbols``
(``altsym.from_symbol_def``, ``--altium-symbols graphics``), one Altium sheet per KiCad sheet of the tree
(``--altium-sheets modules``). Positions and wires come from the writer's layout. Nothing runs a tool:
the nets are the board's, which a KiCad project holds as its schematic gives them.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends.altium import project
from fenolite.backends.altium.altsym import AltiumSymbol, from_symbol_def
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.kicad import parity_inputs
from fenolite.convert.codes import issue
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.ids import derived_id
from fenolite.model.circuit import Component, Pin
from fenolite.model.design import Design
from fenolite.model.library import SymbolDef
from fenolite.model.schematic import SchematicSheet

SUFFIX = ".kicad_sch"
POWER_PREFIX = "#"
BACKEND = "kicad"
SEPARATOR = "/"
_UNSAFE = re.compile(r"[^A-Za-z0-9_+-]+")


@dataclass(frozen=True, slots=True)
class SourceSchematic:
    """The schematic side of a conversion: the design whose circuit the writer takes, the Altium symbols by
    lib id, the module paths of the KiCad sheets (``""`` for the root; empty when the schematic was not
    read, which the issues say) and the issues of the read."""

    design: Design
    symbols: Mapping[str, AltiumSymbol]
    sheets: tuple[str, ...]
    issues: tuple[Issue, ...] = ()


def root_of(board: Path) -> Path | None:
    """The root schematic of a board: ``<stem>.kicad_sch`` beside it, else ``None``."""
    found = board.with_suffix(SUFFIX)
    return found if found.is_file() else None


def _name(text: str, taken: set[str]) -> str:
    """A module name from a KiCad sheet name: letters, digits, ``_``, ``+`` and ``-`` kept, the rest ``_``,
    and a number added when a sibling holds it already."""
    base = _UNSAFE.sub("_", text).strip("_") or "sheet"
    name, number = base, 2
    while name in taken:
        name, number = f"{base}_{number}", number + 1
    taken.add(name)
    return name


def sheet_paths(sheets: Mapping[str, SchematicSheet], root: str, project_name: str) -> dict[str, str]:
    """KiCad sheet path (``/<root uuid>/<sheet uuid>…``) → module path (sheet names joined by ``/``,
    ``""`` for the root), for every sheet instance of the tree, depth first."""
    top = sheets[root]
    start = f"/{top.native_ids.get(BACKEND, '')}"
    found: dict[str, str] = {start: ""}
    queue: list[tuple[str, str, str]] = [(root, start, "")]
    while queue:
        file, path, module = queue.pop(0)
        sheet = sheets.get(file)
        if sheet is None:
            continue
        taken: set[str] = set()
        for ref in sheet.sheets:
            if not any(use.project == project_name and use.path == path for use in ref.uses):
                continue
            child = f"{path}/{ref.native_ids.get(BACKEND, '')}"
            name = _name(ref.name, taken)
            found[child] = f"{module}{SEPARATOR}{name}" if module else name
            queue.append((Path(ref.file).name, child, found[child]))
    return found


def _definitions(sheets: Mapping[str, SchematicSheet]) -> dict[str, SymbolDef]:
    found: dict[str, SymbolDef] = {}
    for sheet in sheets.values():
        for symbol in sheet.lib_symbols:
            found.setdefault(symbol.lib_id, symbol)
    return found


def _placements(
    sheets: Mapping[str, SchematicSheet], paths: Mapping[str, str], project_name: str
) -> dict[str, tuple[str, str]]:
    """Reference → (lib id, module path) of every placed symbol of the tree that is no power symbol."""
    found: dict[str, tuple[str, str]] = {}
    for sheet in sheets.values():
        for symbol in sheet.symbols:
            for use in symbol.uses:
                if use.project != project_name or use.path not in paths or use.ref.startswith(POWER_PREFIX):
                    continue
                found.setdefault(use.ref, (symbol.lib_name or symbol.lib_ref, paths[use.path]))
    return found


def _symbol_pins(component: Component, symbol: SymbolDef) -> tuple[Pin, ...]:
    pins: dict[str, Pin] = {}
    for pin in symbol.pins:
        if pin.body_style not in (0, 1) or pin.number in pins or not pin.number:
            continue
        pins[pin.number] = Pin(
            id=derived_id("pin", BACKEND, f"altium-schematic:{component.id}:{pin.number}"),
            number=pin.number,
            name=pin.name if pin.name and pin.name != "~" else pin.number,
            etype=pin.etype,
        )
    return tuple(pins.values())


def source_schematic(design: Design, board: Path) -> SourceSchematic | None:
    """The schematic side of the conversion of ``design``, read from the board's ``<stem>.kicad_sch`` and
    the sheets its tree names; ``None`` without a root schematic or when the tree cannot be read."""
    root = root_of(board)
    if root is None:
        return None
    issues: list[Issue] = []
    try:
        sheets = parity_inputs.read_sheets(root)
    except (FenoliteError, ValueError, OSError) as error:
        message = f"the schematic {root.name} is not read: {error}; the generated sheet is written"
        return SourceSchematic(design, {}, (), (issue("convert.schematic-unread", message, where=root.name),))
    project_name = root.stem
    paths = sheet_paths(sheets, root.name, project_name)
    placed = _placements(sheets, paths, project_name)
    definitions = _definitions(sheets)
    symbols: dict[str, AltiumSymbol] = {}
    components: list[Component] = []
    for component in design.circuit.components:
        found = placed.get(component.ref)
        definition = definitions.get(found[0]) if found is not None else None
        link = project.split_link(found[0]) if found is not None else None
        if found is None or definition is None or link is None or not definition.pins:
            components.append(component)
            continue
        lib_id, module = found
        if text_problem(link[0]) is None and text_problem(link[1]) is None and lib_id not in symbols:
            try:
                symbols[lib_id] = from_symbol_def(
                    definition, lib_ref=link[1], footprint=None, issues=issues, bodies="graphics"
                )
            except ValueError as error:
                issues.append(Issue("altium.symbol-off-grid", "info", str(error), where=lib_id))
        properties = dict(component.properties)
        properties[project.PATH_PROPERTY] = f"{module}{SEPARATOR}{component.ref}" if module else component.ref
        components.append(
            dataclasses.replace(
                component,
                lib_symbol_ref=lib_id,
                pins=_symbol_pins(component, definition),
                properties=properties,
            )
        )
    held = {component.id: {pin.number for pin in component.pins} for component in components}
    nets = tuple(
        dataclasses.replace(
            net,
            members=tuple(
                m for m in net.members if not held.get(m.component_id) or m.pin in held[m.component_id]
            ),
        )
        for net in design.circuit.nets
    )
    marks = tuple(
        m for m in design.circuit.no_connects if not held.get(m.component_id) or m.pin in held[m.component_id]
    )
    circuit = dataclasses.replace(design.circuit, components=tuple(components), nets=nets, no_connects=marks)
    tree = tuple(sorted(set(paths.values())))
    return SourceSchematic(dataclasses.replace(design, circuit=circuit), symbols, tree, tuple(issues))


__all__ = ["SourceSchematic", "root_of", "sheet_paths", "source_schematic"]
