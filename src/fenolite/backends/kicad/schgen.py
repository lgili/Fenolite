# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic sheet of a built design (capability ``kicad-schematic``, "Generated sheet content";
change c0061).

One flat sheet: every unit of every part's symbol, a global label of the net at each connected pin, a
no-connect flag at each pin the circuit marks, and a power flag on each supply net that no power output
drives. There is no wire: KiCad joins the pins by the label texts. The sheet is a view of the circuit, so
two calls with equal arguments return equal results, and nothing here reads or writes a file. The facts
it is written from are in ``docs/formats/kicad/schematic.md``; readable drawings are another change.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from fenolite.backends.kicad import netnames, schlayout, symembed
from fenolite.backends.kicad.libs import LibRow
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.backends.kicad.schlayout import SymbolPlacement, UnitBox, UnitPin
from fenolite.backends.kicad.symembed import EmbeddedSymbol
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.model.circuit import Component, Net
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef, SymbolDef, SymbolPin
from fenolite.model.presentation import SheetFrameRef
from fenolite.model.schematic import (
    NetLabel,
    NoConnectFlag,
    SchematicSheet,
    SheetPage,
    SymbolInstance,
    SymbolUse,
)

EVIDENCE = Evidence(
    Level.KICAD_VERIFIED,
    hypotheses=(
        "H-K-SCH-MINIMAL",
        "H-K-SCH-PINFRAME",
        "H-K-SCH-UNCONNECTED",
        "H-K-SCH-SLASH",
        "H-K-SCH-PARITY",
        "H-K-SCH-POWER",
        "H-K-SCH-LIBTABLE",
    ),
)
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.sch.pin-off-grid": "info",
        "kicad.sch.power-pin-shown": "info",
        "kicad.sch.unconnected-name-unproven": "warning",
        "build.schematic-too-large": "error",
        "build.symbol-overlap": "warning",
        "build.symbol-short": "error",
        "build.symbol-placement-unknown": "warning",
        "build.symbol-placement-invalid": "error",
        "build.reserved-library": "error",
        "build.schematic-replaced": "warning",
    }
)
"""Every code of the generator, the layout, the embedding and the placements file, with its severity."""
ID_BACKEND = "fenolite"
"""The namespace of the ids of generated schematic entities (``design-model``)."""
PATH_PROPERTY = "fenolite.path"
FLAG_KEY = "#flag:"
"""The layout key of a power flag is this prefix and its net name; no component path starts with ``#``."""
MANDATORY: tuple[str, ...] = ("Reference", "Value", "Footprint", "Datasheet", "Description")
STEPS: Mapping[int, tuple[int, int]] = MappingProxyType({0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)})


class SchematicPart(Protocol):
    """What the generator reads of one resolved part of a build."""

    @property
    def component(self) -> Component: ...

    @property
    def path(self) -> str: ...

    @property
    def symbol(self) -> SymbolDef: ...

    @property
    def footprint(self) -> FootprintDef: ...

    @property
    def parents(self) -> Sequence[SymbolDef]: ...

    @property
    def symbol_origin(self) -> str: ...


@dataclass(frozen=True)
class GeneratedSchematic:
    """``sheet`` and what the build needs beside it: ``libraries`` maps a nickname to the symbols of its
    project library, ``rows`` are the rows of ``sym-lib-table``, ``pad_nets`` maps (component id, pad
    number) to the net name KiCad gives that unconnected pin, ``paths`` maps a component id to the path
    of its symbol, and ``unvendored`` lists the lib ids that ``vendor="project"`` left without a library."""

    sheet: SchematicSheet
    libraries: Mapping[str, tuple[EmbeddedSymbol, ...]]
    rows: tuple[LibRow, ...]
    pad_nets: Mapping[tuple[str, str], str]
    paths: Mapping[str, str]
    issues: tuple[Issue, ...]
    unvendored: tuple[str, ...] = ()
    power_flags: int = 0


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, ISSUE_CODES[code], message, where=where, hint=hint)


def library_row(nickname: str) -> LibRow:
    """The ``sym-lib-table`` row of the project library of ``nickname``."""
    return LibRow(nickname, "KiCad", f"${{KIPRJMOD}}/lib/{nickname}.kicad_sym")


def _body(symbol: SymbolDef, pins: Sequence[SymbolPin]) -> tuple[int, int, int, int]:
    """The box of what a unit draws, in the library frame: its graphics and the inner ends of its pins."""
    xs: list[int] = []
    ys: list[int] = []
    for graphic in symbol.graphics:
        points = list(graphic.points)
        if graphic.kind == "circle" and len(points) == 2:
            centre, rim = points
            radius = abs(rim.x - centre.x) + abs(rim.y - centre.y)
            points = [
                Point(centre.x - radius, centre.y - radius),
                Point(centre.x + radius, centre.y + radius),
            ]
        xs += [p.x for p in points]
        ys += [p.y for p in points]
    for pin in pins:
        dx, dy = STEPS[(pin.rotation // 1_000_000) % 360]
        xs.append(pin.position.x + dx * pin.length)
        ys.append(pin.position.y + dy * pin.length)
    if not xs:
        return (0, 0, 0, 0)
    return (min(xs), min(ys), max(xs), max(ys))


def unit_box(path: str, symbol: SymbolDef, unit: int = 1, labels: Mapping[str, str] | None = None) -> UnitBox:
    """What the layout needs of unit ``unit`` of ``symbol`` for the component at ``path``; ``labels`` maps
    a pin number to the label text written at that pin."""
    pins = symbol.pins_of(unit, 1)
    texts = labels or {}
    boxed = tuple(
        UnitPin(pin.number, pin.position, (pin.rotation // 1_000_000) % 360, len(texts.get(pin.number, "")))
        for pin in pins
    )
    return UnitBox(schlayout.unit_key(path, unit), boxed, _body(symbol, pins), symbol.lib_id)


def _needs_flag(design: Design, components: Mapping[str, Component]) -> list[Net]:
    """The nets of power interfaces that no power-output pin of a fitted part drives, by name."""
    supply = {
        net_id for itf in design.circuit.interfaces if itf.kind == "power" for net_id in itf.members.values()
    }
    found: list[Net] = []
    for net in design.circuit.nets:
        if net.id not in supply:
            continue
        driven = False
        for member in net.members:
            component = components.get(member.component_id)
            if component is None or component.dnp:
                continue
            driven = driven or any(p.number == member.pin and p.etype == "power_out" for p in component.pins)
        if not driven:
            found.append(net)
    return sorted(found, key=lambda n: n.name)


def generate_schematic(
    design: Design,
    parts: Sequence[SchematicPart],
    *,
    name: str,
    target: int,
    placements: Mapping[str, SymbolPlacement] | None = None,
    vendor: str = "all",
    allow_lossy: bool = False,
) -> GeneratedSchematic:
    """The sheet of ``design``, whose components ``parts`` resolve to symbols.

    A component of ``design`` without a part gets no symbol, and a part whose component the design does
    not hold is left out. ``placements`` fixes symbol origins (``schlayout.layout_units``); ``vendor``
    is the build's vendoring policy: with ``"project"`` a symbol of a row that is not a project row is
    embedded and gets no project library.
    """
    issues: list[Issue] = []
    root = SchematicSheet(id=derived_id("sch", ID_BACKEND, name), name=name)
    root_path = f"/{kicad_uuid(root)}"
    components = {c.id: c for c in design.circuit.components}
    net_of: dict[tuple[str, str], Net] = {}
    for net in design.circuit.nets:
        for member in net.members:
            net_of[(member.component_id, member.pin)] = net
    marks = {(m.component_id, m.pin) for m in design.circuit.no_connects}

    embedded: dict[tuple[str, tuple[tuple[str, str], ...]], EmbeddedSymbol] = {}
    origins: dict[str, str] = {}
    units: list[UnitBox] = []
    placed: list[tuple[SchematicPart, Component, EmbeddedSymbol, int]] = []
    for part in sorted(parts, key=lambda p: schlayout.natural_key(p.path)):
        component = components.get(part.component.id)
        if component is None:
            continue
        symbol = part.symbol
        if symbol.library == symembed.FLAG_LIBRARY:
            issues.append(
                issue(
                    "build.reserved-library",
                    f"{component.ref}: the library nickname {symembed.FLAG_LIBRARY!r} is kept for Fenolite's "
                    "own symbols",
                    part.path,
                    "give the library another nickname in the symbol table",
                )
            )
            continue
        mapping = tuple(sorted(component.pin_pad_map))
        key = (symbol.lib_id, mapping)
        if key not in embedded:
            embedded[key] = symembed.embed_symbol(
                symbol,
                parents=part.parents,
                target=target,
                pin_numbers=mapping or None,
                allow_lossy=allow_lossy,
                issues=issues,
            )
            origins[embedded[key].lib_id] = part.symbol_origin
        for unit in range(1, symbol.unit_count + 1):
            texts = {
                pin.number: netnames.stored_name(net_of[(component.id, pin.number)].name)
                for pin in symbol.pins_of(unit, 1)
                if (component.id, pin.number) in net_of
            }
            units.append(unit_box(part.path, symbol, unit, texts))
            placed.append((part, component, embedded[key], unit))

    flag_nets = _needs_flag(design, components)
    flag = symembed.power_flag(target) if flag_nets else None
    flag_boxes = [
        UnitBox(
            f"{FLAG_KEY}{net.name}",
            (UnitPin("1", Point(0, 0), 90, len(netnames.stored_name(net.name))),),
            (0, 0, 2_540_000, 2_540_000),
            f"{symembed.FLAG_LIBRARY}:{symembed.FLAG_NAME}",
        )
        for net in flag_nets
    ]
    layout = schlayout.layout_units(units, placements=placements, flags=flag_boxes)
    issues += layout.issues

    symbols: list[SymbolInstance] = []
    labels: list[NetLabel] = []
    flags: list[NoConnectFlag] = []
    pad_nets: dict[tuple[str, str], str] = {}
    paths: dict[str, str] = {}
    order = {unit.key: index for index, unit in enumerate(units)}
    placed.sort(key=lambda item: order[schlayout.unit_key(item[0].path, item[3])])
    labelled: set[tuple[str, str]] = set()
    for part, component, definition, unit in placed:
        place = layout.origins[schlayout.unit_key(part.path, unit)]
        origin = Point(place.x, place.y)
        symbol = part.symbol
        properties = {key: "" for key in MANDATORY} | dict(component.properties)
        properties |= {
            "Reference": component.ref,
            "Value": component.value,
            "Footprint": component.lib_footprint_ref,
        }
        instance = SymbolInstance(
            id=derived_id("sci", ID_BACKEND, f"{name}:{part.path}#{unit}"),
            lib_ref=definition.lib_id,
            position=origin,
            rotation=place.rotation * 1_000_000,
            mirror=place.mirror,  # type: ignore[arg-type]
            unit=unit,
            ref=component.ref,
            value=component.value,
            footprint=component.lib_footprint_ref,
            properties=properties,
            dnp=component.dnp,
            in_bom="exclude_from_bom" not in part.footprint.flags,
            on_board=True,
            uses=(SymbolUse(name, root_path, component.ref, unit),),
        )
        symbols.append(instance)
        paths.setdefault(component.id, f"/{kicad_uuid(instance)}")
        numbers = dict(component.pin_pad_map)
        for pin in symbol.pins_of(unit, 1):
            point = schlayout.pin_point(origin, pin.position, place.rotation, place.mirror)
            pin_key = (component.id, pin.number)
            tag = pin.number if pin_key not in labelled else f"{pin.number}#{unit}"
            labelled.add(pin_key)
            net = net_of.get(pin_key)
            if net is not None:
                angle = schlayout.label_angle((pin.rotation // 1_000_000) % 360, place.rotation, place.mirror)
                labels.append(
                    NetLabel(
                        id=derived_id("lbl", ID_BACKEND, f"{name}:label:{part.path}:{tag}"),
                        kind="global",
                        name=netnames.stored_name(net.name),
                        position=point,
                        rotation=angle * 1_000_000,
                        shape="passive",
                    )
                )
                continue
            if pin_key in marks:
                flags.append(
                    NoConnectFlag(
                        id=derived_id("ncf", ID_BACKEND, f"{name}:nc:{part.path}:{tag}"), position=point
                    )
                )
            pad = numbers.get(pin.number, pin.number)
            if (component.id, pad) in pad_nets:
                continue
            if not netnames.proved(pin.name):
                issues.append(
                    issue(
                        "kicad.sch.unconnected-name-unproven",
                        f"{component.ref} pin {pin.number} ({pin.name!r}): the net name KiCad gives this "
                        "unconnected pin was not measured for every character of its name, so its pad stays "
                        "on no net and KiCad's parity test may report it",
                        part.path,
                    )
                )
                continue
            pad_nets[(component.id, pad)] = netnames.unconnected_name(
                component.ref,
                unit=unit,
                unit_count=symbol.unit_count,
                pin_name=pin.name,
                pad_number=pad,
            )

    for index, net in enumerate(flag_nets, start=1):
        assert flag is not None
        place = layout.origins[f"{FLAG_KEY}{net.name}"]
        origin = Point(place.x, place.y)
        ref = f"{symembed.FLAG_REFERENCE}{index:02d}"
        symbols.append(
            SymbolInstance(
                id=derived_id("sci", ID_BACKEND, f"{name}:flag:{net.name}"),
                lib_ref=flag.lib_id,
                position=origin,
                ref=ref,
                value=symembed.FLAG_NAME,
                properties={key: "" for key in MANDATORY} | {"Reference": ref, "Value": symembed.FLAG_NAME},
                in_bom=False,
                on_board=False,
                uses=(SymbolUse(name, root_path, ref, 1),),
            )
        )
        labels.append(
            NetLabel(
                id=derived_id("lbl", ID_BACKEND, f"{name}:label:flag:{net.name}"),
                kind="global",
                name=netnames.stored_name(net.name),
                position=origin,
                rotation=schlayout.label_angle(90) * 1_000_000,
                shape="passive",
            )
        )

    definitions = sorted(embedded.values(), key=lambda e: e.lib_id)
    libraries: dict[str, list[EmbeddedSymbol]] = {}
    unvendored: list[str] = []
    for definition in definitions:
        if vendor == "project" and origins[definition.lib_id] not in ("project", "authored"):
            unvendored.append(definition.lib_id)
            continue
        libraries.setdefault(definition.nickname, []).append(definition)
    if flag is not None:
        definitions.append(flag)
        libraries[flag.nickname] = [flag]
    board = design.board
    sheet = SchematicSheet(
        id=root.id,
        name=name,
        paper=SheetFrameRef(layout.paper),  # type: ignore[arg-type]
        title_block=board.title_block if board is not None else None,
        lib_symbols=tuple(d.definition for d in definitions),
        symbols=tuple(symbols),
        labels=tuple(labels),
        no_connects=tuple(flags),
        pages=(SheetPage("/", "1"),),
    )
    return GeneratedSchematic(
        sheet,
        MappingProxyType({nick: tuple(found) for nick, found in sorted(libraries.items())}),
        tuple(library_row(nick) for nick in sorted(libraries)),
        MappingProxyType(pad_nets),
        MappingProxyType(paths),
        tuple(issues),
        tuple(unvendored),
        len(flag_nets),
    )


__all__ = [
    "EVIDENCE",
    "FLAG_KEY",
    "ISSUE_CODES",
    "GeneratedSchematic",
    "SchematicPart",
    "generate_schematic",
    "library_row",
    "unit_box",
]
