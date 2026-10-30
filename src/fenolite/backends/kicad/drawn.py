# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawn schematics for KiCad: lowering a ``DrawnSchematic`` to created sheets, and extracting one from read
sheets (capability ``drawn-schematic``, "Drawn sheets lowered for KiCad", "Drawn content of read KiCad
sheets", "Opaque items of read sheets" and "Freezing a generated schematic"; capability ``kicad-schematic``,
"Drawn sheets written" and "Repeated sheets written"; change c0276; ``docs/drawn-schematic.md``).

``lower_drawn`` returns a ``GeneratedSchematic`` as ``schgen.generate_schematic`` does, so every later step
of a build is unchanged: symbols posed as drawn, references, values and footprints from code, power symbols
from their library, one file per drawn sheet (a repeated sheet is written once, with one instance path per
reference) and the board's footprint paths through the sheet uuids of each instance.

``extract`` turns read sheets back into a ``DrawnSchematic`` with the pin points of every drawn item, so
``drawn_connect.resolve`` can give its nets: modelled items directly, the opaque ``wire``, ``bus``,
``bus_entry``, ``junction`` and ``bus_alias`` slots parsed (``sch.opaque_drawing``), ``#`` power symbols as
power items, and every other root slot verbatim as an opaque item. Nothing here reads or writes a file or
runs a tool.
"""

from __future__ import annotations

import posixpath
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from fenolite.backends.kicad import netnames, sch, schlayout, symembed
from fenolite.backends.kicad._fpmap import node, point_node
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.backends.kicad.schgen import (
    ID_BACKEND,
    MANDATORY,
    SHEETS_DIR,
    GeneratedSchematic,
    SchematicPart,
    library_row,
)
from fenolite.backends.kicad.sexpr import Atom, dumps
from fenolite.backends.kicad.symembed import EmbeddedSymbol
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.model.circuit import Circuit, Component, Net
from fenolite.model.design import Design
from fenolite.model.drawn import (
    ROTATIONS,
    DrawnBusAlias,
    DrawnBusEntry,
    DrawnField,
    DrawnInstance,
    DrawnJunction,
    DrawnLabel,
    DrawnOpaque,
    DrawnPin,
    DrawnPower,
    DrawnSchematic,
    DrawnSheet,
    DrawnSheetRef,
    DrawnSymbol,
    title_pairs,
)
from fenolite.model.drawn_connect import (
    DrawnNetlist,
    PinKey,
    PinPoint,
    UnitInfo,
    component_path,
    coverage,
    instances,
    issue,
    natural,
    resolve,
)
from fenolite.model.library import SymbolDef
from fenolite.model.presentation import SheetFrameRef, TitleBlock
from fenolite.model.schematic import (
    BusAlias,
    BusEntry,
    BusWire,
    Junction,
    NetLabel,
    NoConnectFlag,
    SchematicSheet,
    SheetPage,
    SheetPin,
    SheetRef,
    SheetUse,
    SymbolInstance,
    SymbolUse,
    Wire,
)

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-DRAWN-CONNECT", "H-K-DRAWN-WRITE"))
"""``INFERRED`` until the KiCad CI job measures ``H-K-DRAWN-CONNECT`` and ``H-K-DRAWN-WRITE``."""
ROOT_KEY = "root"
"""The key extraction gives the root sheet."""
POWER_REFERENCE = "#PWR"
HEADER_HEADS: frozenset[str] = frozenset(
    {
        "version", "generator", "generator_version", "embedded_fonts", "uuid", "paper", "title_block",
        "lib_symbols", "sheet_instances", "symbol_instances",
    }
)  # fmt: skip
"""Root heads the writer writes itself: extraction never keeps them as opaque items."""
VISIBLE_FIELDS: frozenset[str] = frozenset({"Reference", "Value"})
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


@dataclass(frozen=True)
class PowerSymbol:
    """A power symbol a drawing names, resolved by the build: its definition, the symbols it extends and
    the origin of its library row (``project``, ``authored`` or another)."""

    symbol: SymbolDef
    parents: tuple[SymbolDef, ...] = ()
    origin: str = "project"


@dataclass(frozen=True)
class Extracted:
    """A drawn schematic extracted from read sheets, the pin points of its items and the issues."""

    drawn: DrawnSchematic
    pins: Mapping[PinKey, tuple[PinPoint, ...]]
    issues: tuple[Issue, ...] = ()


# --- lowering --------------------------------------------------------------------------------------


def _norm(path: str) -> str:
    return posixpath.normpath(path.replace("\\", "/"))


@dataclass
class _Files:
    """Where each drawn sheet is written and how each reference names its file."""

    by_key: dict[str, str] = field(default_factory=lambda: {})
    issues: list[Issue] = field(default_factory=lambda: [])


def _files(drawn: DrawnSchematic, found: Sequence[DrawnInstance], root_file: str) -> _Files:
    files = _Files({drawn.root: root_file})
    for instance in found[1:]:
        ref = instance.ref
        assert ref is not None and instance.parent is not None
        holder = files.by_key.get(found[instance.parent].sheet, root_file)
        folder = posixpath.dirname(holder)
        wanted = (
            _norm(posixpath.join(folder, ref.file)) if ref.file else f"{SHEETS_DIR}/{ref.sheet}.kicad_sch"
        )
        if wanted.startswith("../") or wanted == ".." or posixpath.isabs(wanted):
            files.issues.append(
                issue(
                    "drawn.sheet-unknown",
                    f"the reference {ref.key} names the file {ref.file!r}, outside the project folder",
                    ref.key,
                )
            )
            continue
        known = files.by_key.setdefault(ref.sheet, wanted)
        if known != wanted:
            files.issues.append(
                issue(
                    "drawn.sheet-unknown",
                    f"the sheet {ref.sheet} is named as {known} and as {wanted} by its references",
                    ref.key,
                    "give every reference of a repeated sheet the same file, or leave file out",
                )
            )
    return files


def _ref_text(holder_file: str, child_file: str) -> str:
    """The ``Sheetfile`` of a reference in ``holder_file`` to ``child_file`` (both from the root's folder)."""
    return posixpath.relpath(child_file, posixpath.dirname(holder_file) or ".")


@dataclass
class _Lowering:
    design: Design
    name: str
    target: int
    allow_lossy: bool
    issues: list[Issue]
    embedded: dict[tuple[str, tuple[tuple[str, str], ...]], EmbeddedSymbol] = field(
        default_factory=lambda: {}
    )
    origins: dict[str, str] = field(default_factory=lambda: {})

    def embed(
        self,
        symbol: SymbolDef,
        parents: Sequence[SymbolDef],
        mapping: tuple[tuple[str, str], ...],
        origin: str,
    ) -> EmbeddedSymbol:
        key = (symbol.lib_id, mapping)
        if key not in self.embedded:
            self.embedded[key] = symembed.embed_symbol(
                symbol,
                parents=parents,
                target=self.target,
                pin_numbers=mapping or None,
                allow_lossy=self.allow_lossy,
                issues=self.issues,
            )
            self.origins[self.embedded[key].lib_id] = origin
        return self.embedded[key]


def _field_ext(fields: Sequence[DrawnField]) -> dict[str, object]:
    poses = [sch.FieldPose(f.name, f.at, f.rotation, f.justify, f.hide) for f in fields]
    return {sch.DRAWN_EXT: sch.field_pose_ext(poses)} if poses else {}


def _segment_fragment(start: Point, end: Point, uuid: str, head: str = "wire") -> str:
    return dumps(
        node(
            head,
            node("pts", point_node("xy", start), point_node("xy", end)),
            node("stroke", node("width", Atom.from_nm(0)), node("type", Atom.symbol("default"))),
            node("uuid", Atom.string(uuid)),
        ),
        style="compact",
    )


def _power_definition(
    state: _Lowering, power: DrawnPower, symbols: Mapping[str, PowerSymbol], where: str
) -> EmbeddedSymbol | None:
    library, _, symbol_name = power.symbol.partition(":")
    if symbol_name == symembed.FLAG_NAME and library.casefold() == symembed.FLAG_LIBRARY:
        flag = symembed.power_flag(state.target, library)
        state.embedded.setdefault((flag.lib_id, ()), flag)
        state.origins[flag.lib_id] = "authored"
        return state.embedded[(flag.lib_id, ())]
    found = symbols.get(power.symbol)
    if found is None:
        state.issues.append(
            issue(
                "drawn.part-unknown",
                f"the power symbol {power.symbol} of {power.net} on {where} is in no symbol library "
                "of the design",
                where,
                "add its library to sym-lib-table, or name a power symbol the libraries hold",
            )
        )
        return None
    return state.embed(found.symbol, found.parents, (), found.origin)


def lower_drawn(
    drawn: DrawnSchematic,
    design: Design,
    parts: Sequence[SchematicPart],
    *,
    name: str,
    target: int,
    vendor: str = "all",
    allow_lossy: bool = False,
    power_symbols: Mapping[str, PowerSymbol] = MappingProxyType({}),
) -> GeneratedSchematic:
    """The created sheets of ``drawn`` for ``design``, whose components ``parts`` resolve to symbols, in the
    form ``schgen.generate_schematic`` returns. ``power_symbols`` holds the resolved power symbols the
    drawing names. Coverage errors (``drawn_connect.coverage``) and unknown sheets are in ``issues``; the
    build refuses on them."""
    issues: list[Issue] = []
    found, walk_issues = instances(drawn)
    issues += walk_issues
    state = _Lowering(design, name, target, allow_lossy, issues)
    circuit = design.circuit
    components = {c.id: c for c in circuit.components}
    by_path: dict[str, tuple[SchematicPart, Component]] = {}
    for part in sorted(parts, key=lambda p: natural(p.path)):
        component = components.get(part.component.id)
        if component is not None:
            by_path[part.path] = (part, component)
    net_of: dict[tuple[str, str], Net] = {}
    for net in circuit.nets:
        for member in net.members:
            net_of[(member.component_id, member.pin)] = net
    marks = {(m.component_id, m.pin) for m in circuit.no_connects}
    units = {
        path: UnitInfo(
            part.symbol.unit_count,
            frozenset(
                u
                for u in range(1, part.symbol.unit_count + 1)
                if any((component.id, pin.number) in net_of for pin in part.symbol.pins_of(u, 1))
            ),
        )
        for path, (part, component) in by_path.items()
    }
    issues += coverage(drawn, circuit, units)
    if any(sheet.generated for sheet in drawn.sheets):
        issues.append(
            issue(
                "drawn.sheet-unknown",
                "a generated sheet inside a drawing needs the block sheets of change c0269, which "
                "this version "
                "does not hold",
                next(sheet.key for sheet in drawn.sheets if sheet.generated),
                "draw the sheet, or build with the generated schematic",
            )
        )
    root_file = f"{name}.kicad_sch"
    files = _files(drawn, found, root_file)
    issues += files.issues
    by_sheet: dict[str, list[int]] = defaultdict(list)
    for index, instance in enumerate(found):
        by_sheet[instance.sheet].append(index)
    # sheet reference entities: one per (holder sheet, reference), uuids as the generator's where possible
    modules = [instance.module for instance in found]
    ref_ids: dict[tuple[str, str], str] = {}
    for instance in found[1:]:
        assert instance.ref is not None and instance.parent is not None
        holder = found[instance.parent]
        key = (holder.sheet, instance.ref.key)
        if key in ref_ids:
            continue
        unique = (
            len(by_sheet[holder.sheet]) == 1
            and instance.module != holder.module
            and modules.count(instance.module) == 1
        )
        native = (
            f"{name}:sheet:{instance.module}" if unique else f"{name}:drawn:{holder.sheet}:{instance.ref.key}"
        )
        ref_ids[key] = derived_id("shr", ID_BACKEND, native)
    sheet_ids = {drawn.root: derived_id("sch", ID_BACKEND, name)}
    for sheet in drawn.sheets:
        sheet_ids.setdefault(sheet.key, derived_id("sch", ID_BACKEND, f"{name}:drawn:{sheet.key}"))
    root_uuid = kicad_uuid(SchematicSheet(id=sheet_ids[drawn.root], name=name))
    use_paths: list[str] = []
    board_paths: list[str] = []
    for instance in found:
        if instance.parent is None or instance.ref is None:
            use_paths.append(f"/{root_uuid}")
            board_paths.append("")
            continue
        holder = found[instance.parent]
        ref_uuid = kicad_uuid(SheetRef(id=ref_ids[(holder.sheet, instance.ref.key)], name="", file="",
                                       position=Point(0, 0), size=Size(1, 1)))  # fmt: skip
        use_paths.append(f"{use_paths[instance.parent]}/{ref_uuid}")
        board_paths.append(f"{board_paths[instance.parent]}/{ref_uuid}")
    pad_nets: dict[tuple[str, str], str] = {}
    paths: dict[str, tuple[int, str]] = {}
    board = design.board
    sheets: dict[str, SchematicSheet] = {}
    power_count = 0
    flag_count = 0
    for key, indices in by_sheet.items():
        sheet = drawn.sheet(key)
        if sheet is None or sheet.generated:
            continue
        file = files.by_key.get(key)
        if file is None:
            continue
        used: dict[str, EmbeddedSymbol] = {}
        symbols: list[SymbolInstance] = []
        for symbol in sheet.symbols:
            shown = [(i, found[i].component(symbol.part)) for i in indices]
            known = [(i, by_path[p]) for i, p in shown if p in by_path]
            if not known:
                continue
            first_part, first = known[0][1]
            mapping = symembed.variant_pairs(first.pin_pad_map)
            definition = state.embed(first_part.symbol, first_part.parents, mapping, first_part.symbol_origin)
            used[definition.lib_id] = definition
            properties = {k: "" for k in MANDATORY} | dict(first.properties)
            properties |= {"Reference": first.ref, "Value": first.value, "Footprint": first.lib_footprint_ref}
            instance = SymbolInstance(
                id=derived_id("sci", ID_BACKEND, f"{name}:{first_part.path}#{symbol.unit}"),
                lib_ref=definition.lib_id,
                position=symbol.at,
                rotation=symbol.rotation,
                mirror=symbol.mirror,  # type: ignore[arg-type]
                unit=symbol.unit,
                ref=first.ref,
                value=first.value,
                footprint=first.lib_footprint_ref,
                properties=properties,
                dnp=first.dnp,
                in_bom="exclude_from_bom" not in first_part.footprint.flags,
                on_board=True,
                uses=tuple(SymbolUse(name, use_paths[i], c.ref, symbol.unit) for i, (_, c) in known),
                ext=_field_ext(symbol.fields),  # type: ignore[arg-type]
            )
            symbols.append(instance)
            for i, (part, component) in known:
                candidate = (symbol.unit, f"{board_paths[i]}/{kicad_uuid(instance)}")
                if component.id not in paths or candidate < paths[component.id]:
                    paths[component.id] = candidate
                _open_pins(state, part, component, symbol.unit, net_of, marks, pad_nets)
        for k, power in enumerate(sheet.powers):
            definition = _power_definition(state, power, power_symbols, key)
            if definition is None:
                continue
            used[definition.lib_id] = definition
            flag = (
                definition.name == symembed.FLAG_NAME
                and definition.nickname.casefold() == symembed.FLAG_LIBRARY
            )
            refs: list[str] = []
            for _ in indices:
                if flag:
                    flag_count += 1
                    refs.append(f"{symembed.FLAG_REFERENCE}{flag_count:02d}")
                else:
                    power_count += 1
                    refs.append(f"{POWER_REFERENCE}{power_count:02d}")
            symbols.append(
                SymbolInstance(
                    id=derived_id("sci", ID_BACKEND, f"{name}:power:{key}:{k}"),
                    lib_ref=definition.lib_id,
                    position=power.at,
                    rotation=power.rotation,
                    ref=refs[0],
                    value=power.net,
                    properties={k2: "" for k2 in MANDATORY} | {"Reference": refs[0], "Value": power.net},
                    in_bom=False,
                    on_board=False,
                    uses=tuple(SymbolUse(name, use_paths[i], refs[j], 1) for j, i in enumerate(indices)),
                    ext=_field_ext(power.fields),  # type: ignore[arg-type]
                )
            )
        block = board.title_block if board is not None else None
        sheets[key] = _sheet(state, drawn, sheet, key, file, symbols, used, indices, found, files, ref_ids,
                             use_paths, sheet_ids[key], block)  # fmt: skip
    libraries: dict[str, list[EmbeddedSymbol]] = {}
    unvendored: list[str] = []
    for definition in sorted(state.embedded.values(), key=lambda e: e.lib_id):
        if vendor == "project" and state.origins.get(definition.lib_id) not in ("project", "authored"):
            unvendored.append(definition.lib_id)
            continue
        libraries.setdefault(definition.nickname, []).append(definition)
    root = sheets.get(drawn.root) or SchematicSheet(
        id=sheet_ids[drawn.root], name=name, pages=(SheetPage("/", "1"),)
    )
    children = {files.by_key[k]: s for k, s in sheets.items() if k != drawn.root}
    return GeneratedSchematic(
        root,
        MappingProxyType({nick: tuple(defs) for nick, defs in sorted(libraries.items())}),
        tuple(library_row(nick) for nick in sorted(libraries)),
        MappingProxyType(dict(sorted(pad_nets.items()))),
        MappingProxyType({cid: path for cid, (_, path) in sorted(paths.items())}),
        tuple(issues),
        tuple(unvendored),
        0,
        MappingProxyType(children),
        0,
    )


def _open_pins(
    state: _Lowering,
    part: SchematicPart,
    component: Component,
    unit: int,
    net_of: Mapping[tuple[str, str], Net],
    marks: set[tuple[str, str]],
    pad_nets: dict[tuple[str, str], str],
) -> None:
    """The names KiCad gives the open pins of one drawn unit, as the generator names them."""
    numbers = component.pin_pads()
    symbol = part.symbol
    for pin in symbol.pins_of(unit, 1):
        key = (component.id, pin.number)
        if key in net_of:
            continue
        pads = numbers.get(pin.number, (pin.number,))
        if (component.id, pads[0]) in pad_nets:
            continue
        if not netnames.proved(pin.name):
            state.issues.append(
                Issue(
                    "kicad.sch.unconnected-name-unproven",
                    "warning",
                    f"{component.ref} pin {pin.number} ({pin.name!r}): the net name KiCad gives this "
                    "unconnected "
                    "pin was not measured for every character of its name, so its pad stays on no net",
                    where=part.path,
                )
            )
            continue
        name = netnames.open_name(
            component.ref,
            unit=unit,
            unit_count=symbol.unit_count,
            pin_name=pin.name,
            pads=pads,
            marked=key in marks,
        )
        for pad in pads:
            pad_nets[(component.id, pad)] = name


def split_at(start: Point, end: Point, points: Sequence[Point]) -> list[tuple[Point, Point]]:
    """The segment from ``start`` to ``end`` cut at every one of ``points`` that lies strictly inside it, in
    order; ``[]`` for a segment of zero length. KiCad's editor keeps a wire cut at each junction on it, and
    9.0.9 loses a corner of a wire whose inside holds a junction (measured with ``kicad-cli`` 9.0.9 and
    10.0.6, change c0276): the writer cuts, which joins nothing that the junction did not join."""
    if start == end:
        return []
    cross = [
        p
        for p in points
        if p not in (start, end)
        and (end.x - start.x) * (p.y - start.y) == (end.y - start.y) * (p.x - start.x)
        and min(start.x, end.x) <= p.x <= max(start.x, end.x)
        and min(start.y, end.y) <= p.y <= max(start.y, end.y)
    ]
    ordered = sorted(set(cross), key=lambda p: abs(p.x - start.x) + abs(p.y - start.y))
    stops = [start, *ordered, end]
    return [(stops[n], stops[n + 1]) for n in range(len(stops) - 1)]


def _sheet(
    state: _Lowering,
    drawn: DrawnSchematic,
    sheet: DrawnSheet,
    key: str,
    file: str,
    symbols: list[SymbolInstance],
    used: Mapping[str, EmbeddedSymbol],
    indices: Sequence[int],
    found: Sequence[DrawnInstance],
    files: _Files,
    ref_ids: Mapping[tuple[str, str], str],
    use_paths: Sequence[str],
    sheet_id: str,
    board_block: TitleBlock | None,
) -> SchematicSheet:
    name = state.name
    base = f"{name}:drawn:{key}"
    wires: list[Wire] = []
    slanted: list[str] = []
    dots = [junction.at for junction in sheet.junctions]
    # a wire is cut at its junctions, a bus at its junctions and bus entry ends: the form KiCad's editor
    # keeps, which 9.0.9 needs to join them
    entries = [*dots, *(entry.at for entry in sheet.bus_entries), *(entry.end for entry in sheet.bus_entries)]
    for i, polyline in enumerate(sheet.wires):
        for j in range(len(polyline) - 1):
            for k, (start, end) in enumerate(split_at(polyline[j], polyline[j + 1], dots)):
                ident = derived_id("wir", ID_BACKEND, f"{base}:wire:{i}:{j}" + (f":{k}" if k else ""))
                if start.x == end.x or start.y == end.y:
                    wires.append(Wire(id=ident, start=start, end=end))
                else:
                    slanted.append(
                        _segment_fragment(start, end, kicad_uuid(Junction(id=ident, position=start)))
                    )
    buses = [
        BusWire(
            id=derived_id("bus", ID_BACKEND, f"{base}:bus:{i}:{j}" + (f":{k}" if k else "")), start=a, end=b
        )
        for i, polyline in enumerate(sheet.buses)
        for j in range(len(polyline) - 1)
        for k, (a, b) in enumerate(split_at(polyline[j], polyline[j + 1], entries))
    ]
    refs: list[SheetRef] = []
    for k, ref in enumerate(sheet.sheet_refs):
        child_file = files.by_key.get(ref.sheet)
        ref_id = ref_ids.get((key, ref.key))
        if child_file is None or ref_id is None:
            continue
        uses = tuple(SheetUse(name, use_paths[i], ref.page) for i in indices)
        refs.append(
            SheetRef(
                id=ref_id,
                name=ref.name,
                file=ref.file or _ref_text(file, child_file),
                position=ref.at,
                size=ref.size,
                uses=uses,
                pins=tuple(
                    SheetPin(
                        id=derived_id("shr", ID_BACKEND, f"{base}:ref:{k}:pin:{p}"),
                        name=pin.name,
                        shape=pin.shape,  # type: ignore[arg-type]
                        position=pin.at,
                        rotation=pin.rotation,
                    )
                    for p, pin in enumerate(ref.pins)
                ),
            )
        )
    block = sheet.block() or board_block
    opaque = [*slanted, *(item.kicad for item in sheet.opaques)]
    return SchematicSheet(
        id=sheet_id,
        name=name if key == drawn.root else key,
        paper=SheetFrameRef(sheet.paper),  # type: ignore[arg-type]
        title_block=block,
        lib_symbols=tuple(d.definition for d in sorted(used.values(), key=lambda e: e.lib_id)),
        symbols=tuple(symbols),
        labels=tuple(
            NetLabel(
                id=derived_id("lbl", ID_BACKEND, f"{base}:label:{i}"),
                kind=label.kind,
                name=label.text,
                position=label.at,
                rotation=label.rotation,
                shape=label.shape,
            )
            for i, label in enumerate(sheet.labels)
        ),
        no_connects=tuple(
            NoConnectFlag(id=derived_id("ncf", ID_BACKEND, f"{base}:nc:{i}"), position=at)
            for i, at in enumerate(sheet.no_connects)
        ),
        wires=tuple(wires),
        sheets=tuple(refs),
        pages=(SheetPage("/", "1"),) if key == drawn.root else (),
        junctions=tuple(
            Junction(
                id=derived_id("wir", ID_BACKEND, f"{base}:junction:{i}"), position=j.at, diameter=j.diameter
            )
            for i, j in enumerate(sheet.junctions)
        ),
        buses=tuple(buses),
        bus_entries=tuple(
            BusEntry(id=derived_id("bus", ID_BACKEND, f"{base}:entry:{i}"), position=e.at, size=e.size)
            for i, e in enumerate(sheet.bus_entries)
        ),
        bus_aliases=tuple(
            BusAlias(id=derived_id("bus", ID_BACKEND, f"{base}:alias:{i}"), name=a.name, members=a.members)
            for i, a in enumerate(sheet.bus_aliases)
        ),
        ext={sch.DRAWN_EXT: sch.opaque_ext(opaque)} if opaque else {},
    )


# --- extraction -----------------------------------------------------------------------------------


@dataclass
class _ReadInstance:
    file: str
    sheet: SchematicSheet
    use_path: str
    parent: int | None = None
    ref: SheetRef | None = None
    module: str = ""
    refs: dict[int, str] = field(default_factory=lambda: {})
    """Symbol index → the reference of its use at this instance's path."""


def _definition(sheet: SchematicSheet, symbol: SymbolInstance) -> SymbolDef | None:
    wanted = symbol.lib_name or symbol.lib_ref
    for definition in sheet.lib_symbols:
        full = f"{definition.library}:{definition.name}" if definition.library else definition.name
        if full == wanted:
            return None if definition.extends else definition
    return None


def _key(text: str, taken: set[str]) -> str:
    base = _UNSAFE.sub("_", text) or "sheet"
    if not re.match(r"[A-Za-z_]", base):
        base = f"_{base}"
    key = base
    number = 2
    while key in taken:
        key = f"{base}_{number}"
        number += 1
    taken.add(key)
    return key


def _module_of(path: str) -> str:
    return path.rpartition("/")[0]


def _common(modules: Sequence[str]) -> str:
    split = [m.split("/") if m else [] for m in modules]
    common: list[str] = []
    for parts in zip(*split, strict=False):
        if all(p == parts[0] for p in parts):
            common.append(parts[0])
        else:
            break
    return "/".join(common)


def _relative(path: str, module: str) -> str | None:
    if not module:
        return path
    return path[len(module) + 1 :] if path.startswith(f"{module}/") else None


def _fields(symbol: SymbolInstance, *, power: bool = False) -> tuple[DrawnField, ...]:
    found: list[DrawnField] = []
    for pose in sch.symbol_field_poses(symbol):
        if pose.name not in VISIBLE_FIELDS and pose.hide:
            continue
        if power and pose.name == "Reference" and pose.hide:
            continue
        if pose.rotation not in (0, 90_000_000):
            continue
        found.append(DrawnField(pose.name, pose.at, pose.rotation, pose.justify, pose.hide))
    return tuple(found)


def _pins_of(
    definition: SymbolDef, unit: int, body_style: int, at: Point, rotation: int, mirror: str
) -> tuple[PinPoint, ...]:
    return tuple(
        PinPoint(
            pin.number,
            schlayout.pin_point(at, pin.position, rotation // 1_000_000, mirror),
            pin.etype,
            pin.hidden,
            pin.name,
        )
        for pin in definition.pins_of(unit, body_style)
    )


def extract(
    root: SchematicSheet,
    children: Mapping[str, SchematicSheet],
    *,
    components: Mapping[str, str],
    root_file: str = "",
) -> tuple[DrawnSchematic, tuple[Issue, ...]]:
    """The drawn schematic of read sheets: ``root`` and ``children`` (file, from the root file's folder, to
    sheet, as ``sch.sheet_files`` lists them), with ``components`` mapping a reference to its component
    path. Returns the value and the issues (``drawn.part-unknown`` for a symbol of no component, kept as an
    opaque item, and ``kicad.sch.inexact-length`` for a slot kept verbatim)."""
    found = extract_with_pins(root, children, components=components, root_file=root_file)
    return found.drawn, found.issues


def extract_with_pins(
    root: SchematicSheet,
    children: Mapping[str, SchematicSheet],
    *,
    components: Mapping[str, str],
    root_file: str = "",
) -> Extracted:
    """``extract`` with the pin points of every drawn symbol and power symbol (``drawn_connect.resolve``)."""
    issues: list[Issue] = []
    root_name = root_file or f"{root.name}.kicad_sch"
    uuid = root.native_ids.get("kicad", "")
    walk = [_ReadInstance(root_name, root, f"/{uuid}")]
    queue = [0]
    while queue:
        index = queue.pop(0)
        holder = walk[index]
        trail: list[str] = []
        cursor: int | None = index
        while cursor is not None:
            trail.append(walk[cursor].file)
            cursor = walk[cursor].parent
        for ref in holder.sheet.sheets:
            file = _norm(posixpath.join(posixpath.dirname(holder.file), ref.file)) if ref.file else ""
            child = children.get(file)
            if child is None or file in trail:
                issues.append(
                    issue(
                        "drawn.sheet-unknown",
                        f"the sheet reference {ref.name!r} of {holder.file} names {ref.file!r}, which "
                        "is not read"
                        if child is None
                        else f"the sheet reference {ref.name!r} of {holder.file} names its own file {file}",
                        f"{holder.file}:{ref.name}",
                    )
                )
                continue
            ref_uuid = ref.native_ids.get("kicad", "")
            walk.append(_ReadInstance(file, child, f"{holder.use_path}/{ref_uuid}", index, ref))
            queue.append(len(walk) - 1)
    # references and modules per instance
    for instance in walk:
        absolute: list[str] = []
        for k, symbol in enumerate(instance.sheet.symbols):
            use = next((u for u in symbol.uses if u.path == instance.use_path), None)
            ref = use.ref if use is not None else symbol.ref
            instance.refs[k] = ref
            if ref in components:
                absolute.append(_module_of(components[ref]))
        if absolute:
            instance.module = _common(absolute)
        elif instance.parent is not None:
            instance.module = walk[instance.parent].module
    # sheet keys, one per file
    taken: set[str] = {ROOT_KEY}
    keys: dict[str, str] = {root_name: ROOT_KEY}
    for instance in walk[1:]:
        if instance.file not in keys:
            stem = posixpath.basename(instance.file).removesuffix(".kicad_sch")
            keys[instance.file] = _key(stem, taken)
    by_file: dict[str, list[int]] = defaultdict(list)
    for index, instance in enumerate(walk):
        by_file[instance.file].append(index)
    pins: dict[PinKey, tuple[PinPoint, ...]] = {}
    sheets: list[DrawnSheet] = []
    for file, indices in by_file.items():
        key = keys[file]
        first = walk[indices[0]]
        sheet = first.sheet
        symbols: list[DrawnSymbol] = []
        powers: list[DrawnPower] = []
        opaques: list[DrawnOpaque] = []
        for k, symbol in enumerate(sheet.symbols):
            ref = first.refs.get(k, symbol.ref)
            definition = _definition(sheet, symbol)
            if ref.startswith("#") and definition is not None and definition.power and not symbol.mirror:
                pins[(key, "power", len(powers))] = _pins_of(
                    definition, symbol.unit, symbol.body_style, symbol.position, symbol.rotation, ""
                )
                powers.append(
                    DrawnPower(
                        symbol.lib_name or symbol.lib_ref,
                        symbol.value,
                        symbol.position,
                        symbol.rotation,
                        _fields(symbol, power=True),
                    )  # fmt: skip
                )
                continue
            parts: list[str] = []
            for index in indices:
                instance = walk[index]
                path = components.get(instance.refs.get(k, ""))
                relative = _relative(path, instance.module) if path is not None else None
                if relative is not None:
                    parts.append(relative)
            if not parts or len(parts) != len(indices) or len(set(parts)) != 1:
                shown = ref or symbol.lib_ref
                issues.append(
                    issue(
                        "drawn.part-unknown",
                        f"the symbol {shown} on {file} stands for no component of the code; it is kept as an "
                        "opaque item",
                        f"{file}:{shown}",
                    )
                )
                opaques.append(DrawnOpaque(dumps(sch._entity_node(symbol), style="compact")))  # pyright: ignore[reportPrivateUsage]
                continue
            if definition is not None:
                pins[(key, "symbol", len(symbols))] = _pins_of(
                    definition,
                    symbol.unit,
                    symbol.body_style,
                    symbol.position,
                    symbol.rotation,
                    symbol.mirror,
                )
            symbols.append(
                DrawnSymbol(
                    parts[0], symbol.unit, symbol.position, symbol.rotation, symbol.mirror, _fields(symbol)
                )
            )
        labels: list[DrawnLabel] = []
        for label in sheet.labels:
            if label.rotation not in ROTATIONS:
                opaques.append(DrawnOpaque(dumps(sch._entity_node(label), style="compact")))  # pyright: ignore[reportPrivateUsage]
                continue
            shape = "" if label.kind == "local" else (label.shape or "passive")
            labels.append(DrawnLabel(label.kind, label.name, label.position, label.rotation, shape))  # type: ignore[arg-type]
        refs: list[DrawnSheetRef] = []
        ref_keys: set[str] = set()
        for ref in sheet.sheets:
            child_file = _norm(posixpath.join(posixpath.dirname(file), ref.file)) if ref.file else ""
            if child_file not in keys:
                continue
            child_index = next(
                (i for i, inst in enumerate(walk) if inst.parent == indices[0] and inst.ref is ref), None
            )
            module = ""
            if child_index is not None:
                relative = (
                    _relative(walk[child_index].module, first.module) if walk[child_index].module else ""
                )
                module = relative if relative is not None else walk[child_index].module
            use = next((u for u in ref.uses if u.path == first.use_path), ref.uses[0] if ref.uses else None)
            pins_found = tuple(
                DrawnPin(pin_name, shape or "passive", at, rotation)  # type: ignore[arg-type]
                for pin_name, shape, at, rotation in sch.opaque_sheet_pins(ref)
                if rotation in ROTATIONS
            )
            refs.append(
                DrawnSheetRef(
                    _key(ref.name or "sheet", ref_keys),
                    keys[child_file],
                    module,
                    ref.name or keys[child_file],
                    ref.position,
                    ref.size,
                    use.page if use is not None else "",
                    ref.file,
                    pins_found,
                )
            )
        drawing = sch.opaque_drawing(sheet)
        for head in drawing.inexact:
            issues.append(
                Issue(
                    "kicad.sch.inexact-length",
                    sch.ISSUE_CODES["kicad.sch.inexact-length"],
                    f"a {head} of {file} has a number that is not whole nanometres; it is kept as an "
                    "opaque item",
                    where=file,
                )
            )
        for slot in drawing.rest:
            match = re.match(r"\(([^\s()\"]+)", slot.fragment)
            head = match.group(1) if match is not None else ""
            if head in HEADER_HEADS:
                continue
            opaques.append(DrawnOpaque(slot.fragment))
        paper = sheet.paper.paper if sheet.paper.paper != "custom" else "A4"
        sheets.append(
            DrawnSheet(
                key,
                paper,
                title_pairs(sheet.title_block),
                False,
                tuple(symbols),
                tuple(powers),
                drawing.wires,
                drawing.buses,
                tuple(DrawnBusEntry(at, size) for at, size in drawing.bus_entries),
                tuple(DrawnJunction(at, diameter) for at, diameter in drawing.junctions),
                tuple(flag.position for flag in sheet.no_connects),
                tuple(labels),
                tuple(DrawnBusAlias(n, m) for n, m in drawing.bus_aliases),
                tuple(refs),
                tuple(opaques),
            )
        )
    return Extracted(DrawnSchematic(ROOT_KEY, tuple(sheets)), MappingProxyType(pins), tuple(issues))


def refs_to_paths(circuit: Circuit) -> dict[str, str]:
    """Reference → component path of every component of ``circuit``."""
    return {c.ref: component_path(c) for c in circuit.components if c.ref}


def resolve_sheets(
    root: SchematicSheet,
    children: Mapping[str, SchematicSheet],
    *,
    circuit: Circuit,
    name: str,
    root_file: str = "",
) -> tuple[DrawnSchematic, DrawnNetlist, tuple[Issue, ...]]:
    """The drawn schematic of read sheets, its nets and the issues of extraction and resolution."""
    found = extract_with_pins(root, children, components=refs_to_paths(circuit), root_file=root_file)
    netlist = resolve(found.drawn, found.pins, design_name=name)
    return found.drawn, netlist, (*found.issues, *netlist.issues)


def drawn_counts(drawn: DrawnSchematic) -> dict[str, int]:
    """The counts ``result.schematic.drawn`` reports: wire segments, junctions, labels, bus segments and
    opaque items over every sheet."""
    return {
        "wires": sum(len(sheet.segments()) for sheet in drawn.sheets),
        "junctions": sum(len(sheet.junctions) for sheet in drawn.sheets),
        "labels": sum(len(sheet.labels) for sheet in drawn.sheets),
        "buses": sum(len(sheet.bus_segments()) for sheet in drawn.sheets),
        "opaque": sum(len(sheet.opaques) for sheet in drawn.sheets),
    }


__all__ = [
    "EVIDENCE",
    "HEADER_HEADS",
    "ROOT_KEY",
    "Extracted",
    "PowerSymbol",
    "drawn_counts",
    "extract",
    "extract_with_pins",
    "lower_drawn",
    "refs_to_paths",
    "resolve_sheets",
]
