# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad schematic circuits, embedded symbols and sheet paths for conversion (c0160 task 4.1).

Pure conversion uses the existing own-netlist grammar. The API can prepare a circuit with its existing
KiCad exporter when the source exceeds that grammar; this module never runs a tool.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path, PurePosixPath

from fenolite.backends.altium import project
from fenolite.backends.altium.altsym import AltiumSymbol, from_symbol_def
from fenolite.backends.kicad import parity_inputs
from fenolite.backends.kicad.netlist import NO_CONNECT_SUFFIX
from fenolite.convert.sources import SourceError, SourceProject
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.model.circuit import Circuit, Component, Module, Net, Pin, PinRef
from fenolite.model.design import Design
from fenolite.model.library import SymbolDef
from fenolite.model.schematic import SymbolInstance

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-CONV-SCHEMATIC",))


def root_schematic(source: SourceProject) -> Path | None:
    path = source.path.with_suffix(".kicad_sch")
    return path if path.is_file() else None


def inputs(
    source: SourceProject, design: Design
) -> tuple[Design | None, dict[str, AltiumSymbol], tuple[str, ...]]:
    """The separate schematic design and symbols; board geometry and board nets stay with the board."""
    root = root_schematic(source)
    if root is None:
        return None, {}, ()
    sheets = parity_inputs.read_sheets(root)
    if source.schematic is not None:
        circuit = source.schematic.circuit
    else:
        if parity_inputs.grammar_issues(sheets):
            raise SourceError(
                "the source schematic needs an exported netlist",
                where=root.name,
                hint="use fenolite.api.convert or fenolite convert; the pure package runs no tool",
            )
        netlist = parity_inputs.own_netlist(sheets, project=root.stem)
        ids = {
            c.ref: derived_id("cmp", "conversion", f"{root.stem}:{c.ref}")
            for c in netlist.components
            if not c.ref.startswith("#")
        }
        circuit = Circuit(
            components=tuple(
                Component(id=ids[c.ref], ref=c.ref, value=c.value, lib_footprint_ref=c.footprint)
                for c in netlist.components
                if c.ref in ids
            ),
            nets=tuple(
                Net(
                    id=derived_id("net", "conversion", n.name),
                    name=n.name,
                    members=tuple(PinRef(ids[p.ref], p.pin) for p in n.nodes if p.ref in ids),
                )
                for n in netlist.nets
                if len(n.nodes) != 1 or not n.nodes[0].pintype.endswith(NO_CONNECT_SUFFIX)
            ),
            no_connects=tuple(
                dict.fromkeys(
                    PinRef(ids[p.ref], p.pin)
                    for n in netlist.nets
                    for p in n.nodes
                    if p.ref in ids and p.pintype.endswith(NO_CONNECT_SUFFIX)
                )
            ),
        )
    board_ids = {c.ref: c.id for c in design.circuit.components}
    ids = {c.id: board_ids.get(c.ref, c.id) for c in circuit.components}
    paths: dict[str, str] = {}
    root_sheet = next(iter(sheets.values()))
    paths["/" + root_sheet.native_ids.get("kicad", root_sheet.id)] = ""
    queue: list[tuple[str, str, str, tuple[str, ...]]] = [
        (root.name, "", "/" + root_sheet.native_ids.get("kicad", root_sheet.id), ())
    ]
    while queue:
        file, module, native_path, trail = queue.pop(0)
        if file in trail:
            raise SourceError("cyclic schematic hierarchy", where=file)
        for ref in sheets[file].sheets:
            child = (PurePosixPath(file).parent / ref.file).as_posix()
            if child not in sheets:
                raise SourceError("missing schematic sheet", where=child)
            label = ref.name.replace("/", "_") or Path(child).stem
            path = f"{module}/{label}".lstrip("/")
            native = native_path + "/" + ref.native_ids.get("kicad", ref.id)
            paths[native] = path
            queue.append((child, path, native, (*trail, file)))
    symbols_by_ref: dict[str, tuple[SymbolInstance, SymbolDef, str]] = {}
    for file, sheet in sheets.items():
        known = {s.lib_id: s for s in sheet.lib_symbols}
        for instance in sheet.symbols:
            symbol = known.get(instance.lib_name or instance.lib_ref)
            if symbol is None:
                continue
            uses = [(u.ref, paths.get(u.path, ""), u.unit) for u in instance.uses if u.project == root.stem]
            if not uses:
                uses = [(instance.ref, "" if file == root.name else Path(file).stem, instance.unit)]
            for ref, module, unit in uses:
                if ref.startswith("#") or not ref:
                    continue
                held = symbols_by_ref.get(ref)
                if held is None or unit < held[0].unit:
                    symbols_by_ref[ref] = (dataclasses.replace(instance, unit=unit), symbol, module)
    changed: list[str] = []
    parts: list[Component] = []
    symbols: dict[str, AltiumSymbol] = {}
    for component in circuit.components:
        held = symbols_by_ref.get(component.ref)
        if held is None:
            raise SourceError("the schematic component has no embedded symbol", where=component.ref)
        instance, definition, module = held
        # One definition per component avoids collisions between different embedded bodies of one lib id.
        symbol_name = f"PART_{component.ref}"
        link = f"{design.header.name}.SchLib:{symbol_name}"
        ident = ids[component.id]
        pins = tuple(
            Pin(
                id=derived_id("pin", "conversion", f"{ident}:{p.number}"),
                number=p.number,
                name=p.name,
                etype=p.etype,
            )
            for p in definition.pins
            if p.body_style in (0, 1)
        )
        pins = tuple({p.number: p for p in pins}.values())
        value = component.value
        if value.startswith("="):
            value = " " + value
            changed.append(ident)
        parts.append(
            dataclasses.replace(
                component,
                id=ident,
                value=value,
                pins=pins,
                lib_symbol_ref=link,
                properties={
                    **component.properties,
                    project.PATH_PROPERTY: f"{module}/{component.ref}".lstrip("/"),
                },
                dnp=instance.dnp or component.dnp,
            )
        )
        symbols[link] = from_symbol_def(definition, lib_ref=symbol_name, footprint=None, bodies="graphics")
    nets = tuple(
        dataclasses.replace(n, members=tuple(PinRef(ids[m.component_id], m.pin) for m in n.members))
        for n in circuit.nets
    )
    modules = tuple(
        Module(
            id=derived_id("mod", "conversion", path),
            path=path,
            component_ids=tuple(c.id for c in parts if project.component_path(c).rpartition("/")[0] == path),
        )
        for path in sorted(set(paths.values()) - {""})
    )
    return (
        dataclasses.replace(
            design,
            circuit=dataclasses.replace(
                circuit,
                components=tuple(parts),
                nets=nets,
                modules=modules,
                no_connects=tuple(PinRef(ids[m.component_id], m.pin) for m in circuit.no_connects),
            ),
            board=None,
        ),
        symbols,
        tuple(changed),
    )


__all__ = ["EVIDENCE", "inputs", "root_schematic"]
