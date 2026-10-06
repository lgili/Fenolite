# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic sheets of a built design (capability ``kicad-schematic``, "Generated sheet content" and
"Hierarchical sheets of a design"; changes c0061 and c0070).

Every unit of every part's symbol, a global label of the net at each connected pin, a no-connect flag at
each pin the circuit marks, and a power flag on each supply net that no power output drives. KiCad joins
the pins by the label texts, on one sheet and across sheets, so the net names stay those of the circuit.

With the layout ``"readable"`` a module that holds a part, directly or below it, gets a child sheet of its
own under ``sheets/``, and the sheet above it a reference to that file: a box without pins. On each sheet
a 2-pin part that fits beside an IC pin of its net is drawn there, joined to the pin by one straight wire
(``schlayout.snap_satellites``); the wired pair carries one label. With ``"grid"`` everything lies on one
sheet with a label on every pin, as c0061 wrote it. The sheets are a view of the circuit, so two
calls with equal arguments return equal results, and nothing here reads or writes a file. The facts they
are written from are in ``docs/formats/kicad/schematic.md``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from fenolite.backends.kicad import netnames, schlayout, symembed
from fenolite.backends.kicad.libs import LibRow
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.backends.kicad.schlayout import (
    Cluster,
    RefBox,
    SheetLayout,
    SymbolPlacement,
    UnitBox,
    UnitPin,
)
from fenolite.backends.kicad.symembed import EmbeddedSymbol
from fenolite.core.coords import Point, Size
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
    SheetRef,
    SheetUse,
    SymbolInstance,
    SymbolUse,
    Wire,
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
        "H-K-SCH-HIER-FILE",
        "H-K-SCH-HIER-PATH",
        "H-K-SCH-WIRE-END",
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
        "build.sheet-file-collision": "error",
        "build.sheet-stale": "warning",
    }
)
"""Every code of the generator, the layout, the embedding and the placements file, with its severity."""
LAYOUTS: tuple[str, ...] = ("readable", "grid")
"""``"readable"`` gives each module a sheet of its own; ``"grid"`` is the one flat sheet of c0061."""
SHEETS_DIR = "sheets"
"""The folder of the child sheets, beside the root file."""
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
    """``sheet`` (the root) and what the build needs beside it: ``libraries`` maps a nickname to the
    symbols of its project library, ``rows`` are the rows of ``sym-lib-table``, ``pad_nets`` maps
    (component id, pad number) to the net name KiCad gives that unconnected pin, ``paths`` maps a
    component id to the path of its symbol (the footprint ``path``), ``unvendored`` lists the lib ids that
    ``vendor="project"`` left without a library, and ``children`` maps the path of each child sheet, from
    the root file's folder, to that sheet, in page order."""

    sheet: SchematicSheet
    libraries: Mapping[str, tuple[EmbeddedSymbol, ...]]
    rows: tuple[LibRow, ...]
    pad_nets: Mapping[tuple[str, str], str]
    paths: Mapping[str, str]
    issues: tuple[Issue, ...]
    unvendored: tuple[str, ...] = ()
    power_flags: int = 0
    children: Mapping[str, SchematicSheet] = field(default_factory=lambda: MappingProxyType({}))
    satellites: int = 0


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


def unit_box(
    path: str, symbol: SymbolDef, unit: int = 1, labels: Mapping[str, str] | None = None, text: int = 0
) -> UnitBox:
    """What the layout needs of unit ``unit`` of ``symbol`` for the component at ``path``; ``labels`` maps
    a pin number to the label text written at that pin, and ``text`` is the length of the longer of the
    component's Reference and Value."""
    pins = symbol.pins_of(unit, 1)
    texts = labels or {}
    boxed = tuple(
        UnitPin(pin.number, pin.position, (pin.rotation // 1_000_000) % 360, len(texts.get(pin.number, "")))
        for pin in pins
    )
    return UnitBox(schlayout.unit_key(path, unit), boxed, _body(symbol, pins), symbol.lib_id, text)


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


def sheet_file(module_path: str) -> str:
    """The file of the child sheet of the module at ``module_path``, from the root file's folder: every
    child lies in ``sheets/``, named by its module path with ``.`` between the segments."""
    return f"{SHEETS_DIR}/{module_path.replace('/', '.')}.kicad_sch"


def module_of(path: str) -> str:
    """The path of the module that holds the component at ``path``; ``""`` outside every module."""
    return path.rpartition("/")[0]


def _module_key(path: str) -> tuple[object, ...]:
    """Depth-first order of module paths: a module before its sub-modules, siblings in natural order."""
    return tuple(schlayout.natural_key(segment) for segment in path.split("/"))


def _modules(paths: Iterable[str]) -> list[str]:
    """Every module that holds one of the component ``paths``, directly or below it, depth first."""
    found: set[str] = set()
    for path in paths:
        module = module_of(path)
        while module:
            found.add(module)
            module = module_of(module)
    return sorted(found, key=_module_key)


def _collisions(modules: Sequence[str]) -> list[Issue]:
    """``build.sheet-file-collision`` for each pair of modules whose sheet files are one file, on a file
    system that folds letter case too."""
    files: dict[str, str] = {}
    found: list[Issue] = []
    for module in modules:
        file = sheet_file(module)
        other = files.setdefault(file.casefold(), module)
        if other != module:
            found.append(
                issue(
                    "build.sheet-file-collision",
                    f"the modules {other} and {module} both give the sheet file {file}",
                    module,
                    "rename one of the two modules",
                )
            )
    return found


@dataclass(frozen=True)
class _Unit:
    """One unit of a part that gets a symbol: what the sheet content is made from."""

    part: SchematicPart
    component: Component
    definition: EmbeddedSymbol
    unit: int
    box: UnitBox


@dataclass(frozen=True)
class _Tree:
    """The sheets of a design: per module path (``""`` is the root) the sheet id, the use path of its
    symbols and the prefix of their footprint paths; per module its reference, without a position yet."""

    ids: Mapping[str, str]
    use_paths: Mapping[str, str]
    board_paths: Mapping[str, str]
    refs: Mapping[str, SheetRef]
    pages: Mapping[str, str]


def _tree(name: str, modules: Sequence[str]) -> _Tree:
    root_id = derived_id("sch", ID_BACKEND, name)
    root_uuid = kicad_uuid(SchematicSheet(id=root_id, name=name))
    ids = {"": root_id}
    use_paths = {"": f"/{root_uuid}"}
    board_paths = {"": ""}
    refs: dict[str, SheetRef] = {}
    pages = {"": "1"}
    for number, module in enumerate(modules, start=2):  # depth first: a parent comes before its children
        parent = module_of(module)
        label = module.rpartition("/")[2]
        file = sheet_file(module)
        ref = SheetRef(
            id=derived_id("shr", ID_BACKEND, f"{name}:sheet:{module}"),
            name=label,
            # the root names its children from its own folder, a child names its own from sheets/
            file=file if not parent else file.partition("/")[2],
            position=Point(0, 0),
            size=Size(schlayout.sheet_ref_size(label), schlayout.REF_HEIGHT),
            uses=(SheetUse(name, use_paths[parent], str(number)),),
        )
        refs[module] = ref
        ids[module] = derived_id("sch", ID_BACKEND, f"{name}:{module}")
        use_paths[module] = f"{use_paths[parent]}/{kicad_uuid(ref)}"
        board_paths[module] = f"{board_paths[parent]}/{kicad_uuid(ref)}"
        pages[module] = str(number)
    return _Tree(ids, use_paths, board_paths, refs, pages)


def generate_schematic(
    design: Design,
    parts: Sequence[SchematicPart],
    *,
    name: str,
    target: int,
    placements: Mapping[str, SymbolPlacement] | None = None,
    vendor: str = "all",
    allow_lossy: bool = False,
    layout: str = "readable",
) -> GeneratedSchematic:
    """The sheets of ``design``, whose components ``parts`` resolve to symbols.

    A component of ``design`` without a part gets no symbol, and a part whose component the design does
    not hold is left out. ``placements`` fixes symbol origins (``schlayout.layout_units``); ``vendor``
    is the build's vendoring policy: with ``"project"`` a symbol of a row that is not a project row is
    embedded and gets no project library. ``layout`` is ``"readable"`` (a sheet per module) or
    ``"grid"`` (one flat sheet, the form of c0061).
    """
    if layout not in LAYOUTS:
        raise ValueError(f"unknown schematic layout {layout!r}; use one of: {', '.join(LAYOUTS)}")
    issues: list[Issue] = []
    components = {c.id: c for c in design.circuit.components}
    net_of: dict[tuple[str, str], Net] = {}
    for net in design.circuit.nets:
        for member in net.members:
            net_of[(member.component_id, member.pin)] = net

    embedded: dict[tuple[str, tuple[tuple[str, str], ...]], EmbeddedSymbol] = {}
    origins: dict[str, str] = {}
    placed: list[_Unit] = []
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
            box = unit_box(part.path, symbol, unit, texts, max(len(component.ref), len(component.value)))
            placed.append(_Unit(part, component, embedded[key], unit, box))

    modules = _modules(item.part.path for item in placed) if layout == "readable" else []
    collisions = _collisions(modules)
    if collisions:
        issues += collisions
        modules = []  # no child sheet: the error refuses the build, and one sheet stays readable
    tree = _tree(name, modules)
    flat = not modules
    by_sheet: dict[str, list[_Unit]] = {module: [] for module in ("", *modules)}
    for item in placed:
        by_sheet["" if flat else module_of(item.part.path)].append(item)

    flag_nets = _needs_flag(design, components)
    flag = symembed.power_flag(target) if flag_nets else None
    fixed = dict(placements or {})
    known = {item.box.key for item in placed}
    state = _State(design, name, net_of, {(m.component_id, m.pin) for m in design.circuit.no_connects})
    sheets: dict[str, SchematicSheet] = {}
    board = design.board
    for module in ("", *modules):
        items = by_sheet[module]
        keys = {item.box.key for item in items}
        # a placement belongs to the sheet of its unit; the root also reports the names of no unit
        here = {k: v for k, v in fixed.items() if k in keys or (not module and k not in known)}
        children = [m for m in modules if module_of(m) == module]
        refs = [RefBox(m, tree.refs[m].name, tree.refs[m].file) for m in children]
        flags = [_flag_box(net) for net in flag_nets] if not module else []
        boxes = [item.box for item in items]
        clusters: tuple[Cluster, ...] = ()
        if layout == "readable":
            texts = {
                (item.box.key, pin.number): netnames.stored_name(net_of[(item.component.id, pin.number)].name)
                for item in items
                for pin in item.part.symbol.pins_of(item.unit, 1)
                if (item.component.id, pin.number) in net_of
            }
            clusters = schlayout.snap_satellites(
                boxes, texts, placements={k: v for k, v in here.items() if k in keys}
            )
        found = schlayout.layout_units(
            boxes, placements=here, flags=flags, clusters=clusters, refs=refs, sheet=module or name
        )
        issues += [found_issue for found_issue in found.issues if found_issue not in issues]
        content = _content(state, items, found, tree.use_paths[module], tree.board_paths[module], clusters)
        definitions = sorted({id(i.definition): i.definition for i in items}.values(), key=lambda e: e.lib_id)
        embedded_here = [d.definition for d in definitions]
        if not module and flag is not None:
            _flags(state, content, flag, flag_nets, found, tree.use_paths[""])
            embedded_here.append(flag.definition)
        placed_refs = tuple(
            dataclasses.replace(
                tree.refs[m],
                position=Point(found.origins[schlayout.ref_key(m)].x, found.origins[schlayout.ref_key(m)].y),
            )
            for m in children
        )
        sheets[module] = SchematicSheet(
            id=tree.ids[module],
            name=module.rpartition("/")[2] if module else name,
            paper=SheetFrameRef(found.paper),  # type: ignore[arg-type]
            title_block=board.title_block if board is not None else None,
            lib_symbols=tuple(embedded_here),
            symbols=tuple(content.symbols),
            labels=tuple(content.labels),
            no_connects=tuple(content.flags),
            wires=tuple(content.wires),
            sheets=placed_refs,
            pages=(SheetPage("/", "1"),) if not module else (),
        )
    issues += state.issues

    definitions = sorted(embedded.values(), key=lambda e: e.lib_id)
    libraries: dict[str, list[EmbeddedSymbol]] = {}
    unvendored: list[str] = []
    for definition in definitions:
        if vendor == "project" and origins[definition.lib_id] not in ("project", "authored"):
            unvendored.append(definition.lib_id)
            continue
        libraries.setdefault(definition.nickname, []).append(definition)
    if flag is not None:
        libraries[flag.nickname] = [flag]
    return GeneratedSchematic(
        sheets[""],
        MappingProxyType({nick: tuple(found) for nick, found in sorted(libraries.items())}),
        tuple(library_row(nick) for nick in sorted(libraries)),
        MappingProxyType(state.pad_nets),
        MappingProxyType(state.paths),
        tuple(issues),
        tuple(unvendored),
        len(flag_nets),
        MappingProxyType({sheet_file(module): sheets[module] for module in modules}),
        state.satellites,
    )


def _flag_box(net: Net) -> UnitBox:
    return UnitBox(
        f"{FLAG_KEY}{net.name}",
        (UnitPin("1", Point(0, 0), 90, len(netnames.stored_name(net.name))),),
        (0, 0, 2_540_000, 2_540_000),
        f"{symembed.FLAG_LIBRARY}:{symembed.FLAG_NAME}",
    )


@dataclass
class _State:
    """What the sheets of one design share: the circuit, and what the board takes from the symbols."""

    design: Design
    name: str
    net_of: Mapping[tuple[str, str], Net]
    marks: set[tuple[str, str]]
    pad_nets: dict[tuple[str, str], str] = field(default_factory=lambda: {})
    paths: dict[str, str] = field(default_factory=lambda: {})
    labelled: set[tuple[str, str]] = field(default_factory=lambda: set())
    issues: list[Issue] = field(default_factory=lambda: [])
    satellites: int = 0


@dataclass
class _Content:
    """The entities of one sheet, in the order they are written."""

    symbols: list[SymbolInstance] = field(default_factory=lambda: [])
    labels: list[NetLabel] = field(default_factory=lambda: [])
    flags: list[NoConnectFlag] = field(default_factory=lambda: [])
    wires: list[Wire] = field(default_factory=lambda: [])


def _content(
    state: _State,
    items: Sequence[_Unit],
    layout: SheetLayout,
    use_path: str,
    board_path: str,
    clusters: Sequence[Cluster] = (),
) -> _Content:
    """The symbols, labels, no-connect flags and snap wires of the units ``items`` of one sheet, whose
    symbols are used at ``use_path``; ``board_path`` is the prefix of the footprint paths of that sheet.
    A pin that a snap wire of ``clusters`` joins gets no label of its own: the pair has one, at the
    satellite's near pin."""
    name = state.name
    content = _Content()
    paths = {item.box.key: item.part.path for item in items}
    wired: set[tuple[str, str]] = set()
    pair: dict[tuple[str, str], tuple[Point, int]] = {}
    for cluster in clusters:
        anchor = layout.origins[cluster.anchor]
        for wire in cluster.wires:
            wired.add((cluster.anchor, wire.anchor_pin))
            content.wires.append(
                Wire(
                    id=derived_id("wir", ID_BACKEND, f"{name}:wire:{paths[wire.satellite]}"),
                    start=Point(anchor.x + wire.start.x, anchor.y + wire.start.y),
                    end=Point(anchor.x + wire.end.x, anchor.y + wire.end.y),
                )
            )
        for label in cluster.labels:
            at = Point(anchor.x + label.at.x, anchor.y + label.at.y)
            pair[(label.satellite, label.pin)] = (at, label.angle)
        state.satellites += len(cluster.satellites)
    for item in items:
        part, component, unit = item.part, item.component, item.unit
        place = layout.origins[item.box.key]
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
            lib_ref=item.definition.lib_id,
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
            uses=(SymbolUse(name, use_path, component.ref, unit),),
        )
        content.symbols.append(instance)
        state.paths.setdefault(component.id, f"{board_path}/{kicad_uuid(instance)}")
        numbers = dict(component.pin_pad_map)
        for pin in symbol.pins_of(unit, 1):
            point = schlayout.pin_point(origin, pin.position, place.rotation, place.mirror)
            pin_key = (component.id, pin.number)
            tag = pin.number if pin_key not in state.labelled else f"{pin.number}#{unit}"
            state.labelled.add(pin_key)
            net = state.net_of.get(pin_key)
            if net is not None and (item.box.key, pin.number) in wired:
                continue  # the anchor's end of a snap wire: the label of the pair is at the other end
            if net is not None:
                angle = schlayout.label_angle((pin.rotation // 1_000_000) % 360, place.rotation, place.mirror)
                if (item.box.key, pin.number) in pair:
                    at, angle = pair[(item.box.key, pin.number)]
                    assert at == point, "the label of a pair lies on the satellite's near pin"
                content.labels.append(
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
            if pin_key in state.marks:
                content.flags.append(
                    NoConnectFlag(
                        id=derived_id("ncf", ID_BACKEND, f"{name}:nc:{part.path}:{tag}"), position=point
                    )
                )
            pad = numbers.get(pin.number, pin.number)
            if (component.id, pad) in state.pad_nets:
                continue
            if not netnames.proved(pin.name):
                state.issues.append(
                    issue(
                        "kicad.sch.unconnected-name-unproven",
                        f"{component.ref} pin {pin.number} ({pin.name!r}): the net name KiCad gives this "
                        "unconnected pin was not measured for every character of its name, so its pad stays "
                        "on no net and KiCad's parity test may report it",
                        part.path,
                    )
                )
                continue
            state.pad_nets[(component.id, pad)] = netnames.unconnected_name(
                component.ref,
                unit=unit,
                unit_count=symbol.unit_count,
                pin_name=pin.name,
                pad_number=pad,
            )
    return content


def _flags(
    state: _State,
    content: _Content,
    flag: EmbeddedSymbol,
    flag_nets: Sequence[Net],
    layout: SheetLayout,
    use_path: str,
) -> None:
    """One power flag and its label per net of ``flag_nets``, added to the root sheet's ``content``."""
    name = state.name
    for index, net in enumerate(flag_nets, start=1):
        place = layout.origins[f"{FLAG_KEY}{net.name}"]
        origin = Point(place.x, place.y)
        ref = f"{symembed.FLAG_REFERENCE}{index:02d}"
        content.symbols.append(
            SymbolInstance(
                id=derived_id("sci", ID_BACKEND, f"{name}:flag:{net.name}"),
                lib_ref=flag.lib_id,
                position=origin,
                ref=ref,
                value=symembed.FLAG_NAME,
                properties={key: "" for key in MANDATORY} | {"Reference": ref, "Value": symembed.FLAG_NAME},
                in_bom=False,
                on_board=False,
                uses=(SymbolUse(name, use_path, ref, 1),),
            )
        )
        content.labels.append(
            NetLabel(
                id=derived_id("lbl", ID_BACKEND, f"{name}:label:flag:{net.name}"),
                kind="global",
                name=netnames.stored_name(net.name),
                position=origin,
                rotation=schlayout.label_angle(90) * 1_000_000,
                shape="passive",
            )
        )


__all__ = [
    "EVIDENCE",
    "FLAG_KEY",
    "ISSUE_CODES",
    "LAYOUTS",
    "SHEETS_DIR",
    "GeneratedSchematic",
    "SchematicPart",
    "generate_schematic",
    "library_row",
    "module_of",
    "sheet_file",
    "unit_box",
]
