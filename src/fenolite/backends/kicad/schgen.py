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
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from fenolite.backends.kicad import netnames, schlayout, schwired, symembed
from fenolite.backends.kicad import sch as sch_format
from fenolite.backends.kicad.libs import LibRow
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.backends.kicad.schlayout import (
    Cluster,
    RefBox,
    RefPin,
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
from fenolite.model.circuit import Component, Net, power_interface_nets
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef, SymbolDef, SymbolPin
from fenolite.model.presentation import SheetFrameRef
from fenolite.model.schematic import (
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
from fenolite.schematic.block_sheets import PortPin, SheetGroup, port_pins, split_merged

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
        "build.block-port-merged": "info",
        "build.schematic-wired-fallback": "info",
    }
)
"""Every code of the generator, the layout, the embedding and the placements file, with its severity."""
LAYOUTS: tuple[str, ...] = ("readable", "grid", "wired")
"""``"readable"`` gives each module a sheet of its own; ``"grid"`` is the one flat sheet of c0061;
``"wired"`` draws each module sheet with wires, power symbols and one label per drawn group (change c0406)."""
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
    def footprint(self) -> FootprintDef | None: ...

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
    power_symbols: int = 0
    fallbacks: int = 0


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
    supply = power_interface_nets(design.circuit)
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


def _tree(name: str, modules: Sequence[str], blocks: Mapping[str, str] | None = None) -> _Tree:
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
        made_by = (blocks or {}).get(module, "")
        if made_by:
            label = f"{label} ({made_by})"  # a block instance shows its block (change c0251)
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
    other_libraries: Iterable[str] = (),
    groups: Mapping[str, Sequence[SheetGroup]] | None = None,
) -> GeneratedSchematic:
    """The sheets of ``design``, whose components ``parts`` resolve to symbols.

    A component of ``design`` without a part gets no symbol, and a part whose component the design does
    not hold is left out. ``placements`` fixes symbol origins (``schlayout.layout_units``); ``vendor``
    is the build's vendoring policy: with ``"project"`` a symbol of a row that is not a project row is
    embedded and gets no project library. ``layout`` is ``"readable"`` (a sheet per module) or
    ``"grid"`` (one flat sheet, the form of c0061). ``other_libraries`` names the symbol libraries of the
    design that no part may use (the ones it authors): with the libraries of ``parts`` they decide which
    library holds the power flag (``symembed.flag_library``). ``groups`` maps a block instance path to
    its block-local schematic groups (``fenolite.dsl.block_schematics``, change c0269), which order the
    units of its sheet.
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
        mapping = symembed.variant_pairs(component.pin_pad_map)
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

    modules = _modules(item.part.path for item in placed) if layout != "grid" else []
    collisions = _collisions(modules)
    if collisions:
        issues += collisions
        modules = []  # no child sheet: the error refuses the build, and one sheet stays readable
    tree = _tree(name, modules, {m.path: m.block for m in design.circuit.modules if m.block})
    flat = not modules
    by_sheet: dict[str, list[_Unit]] = {module: [] for module in ("", *modules)}
    for item in placed:
        by_sheet["" if flat else module_of(item.part.path)].append(item)

    wired = _WiredDesign.of(design, components) if layout == "wired" else None
    flag_nets = _needs_flag(design, components) if wired is None else wired.flag_nets
    flag = _flag(flag_nets, embedded, other_libraries, target, issues)
    powers = _Powers(
        symembed.flag_library([*(f.nickname for f in embedded.values()), *other_libraries]), target
    )
    if wired is not None:
        _reserve_power_names(embedded, powers.library, issues)
    fixed = dict(placements or {})
    known = {item.box.key for item in placed}
    state = _State(design, name, net_of, {(m.component_id, m.pin) for m in design.circuit.no_connects})
    blocks = _block_sheets(design, modules, by_sheet, net_of, issues)
    for module in blocks.hier:  # the label texts of a block's sheet: its port nets take hierarchical names
        by_sheet[module] = [
            dataclasses.replace(item, box=_relabelled(item, blocks.texts(module, item, net_of)))
            for item in by_sheet[module]
        ]
    block_groups = {path: tuple(found) for path, found in (groups or {}).items() if path in blocks.hier}
    shared = _shared_widths(blocks, by_sheet, block_groups, fixed, net_of, modules)
    sheets: dict[str, SchematicSheet] = {}
    board = design.board
    for module in ("", *modules):
        items = by_sheet[module]
        keys = {item.box.key for item in items}
        # a placement belongs to the sheet of its unit; the root also reports the names of no unit
        here = {k: v for k, v in fixed.items() if k in keys or (not module and k not in known)}
        children = [m for m in modules if module_of(m) == module]
        widths, ref_widths = shared.get(module, ({}, {}))
        refs = [
            RefBox(m, tree.refs[m].name, tree.refs[m].file, blocks.ref_pins(m, module, ref_widths))
            for m in children
        ]
        flags = [_flag_box(net, flag) for net in flag_nets] if not module and flag is not None else []
        boxes = [item.box for item in items]
        clusters: tuple[Cluster, ...] = ()
        local = block_groups.get(module, ())
        if wired is not None:
            drawn = _wired_sheet(
                state,
                wired,
                powers,
                items,
                module,
                blocks,
                refs,
                flag_nets if not module and flag is not None else [],
                [group.members for group in local],
                [k for k in here if k in keys],
                tree.use_paths[module],
                tree.board_paths[module],
                issues,
            )
            if drawn is not None:
                content, paper, origins_here, junctions, values = drawn
                definitions = sorted(
                    {id(i.definition): i.definition for i in items}.values(), key=lambda e: e.lib_id
                )
                embedded_here = [d.definition for d in definitions] + [
                    p.definition for p in powers.used_on(module)
                ]
                embedded_here.sort(key=lambda e: e.lib_id)
                if not module and flag is not None:
                    _wired_flags(
                        state, content, flag, flag_nets, origins_here, tree.use_paths[""], values=values
                    )
                    embedded_here.append(flag.definition)
                placed_refs = tuple(
                    _placed_ref(state, content, blocks, tree.refs[m], box, origins_here, module)
                    for m, box in zip(children, refs, strict=True)
                )
                sheets[module] = SchematicSheet(
                    id=tree.ids[module],
                    name=module.rpartition("/")[2] if module else name,
                    paper=SheetFrameRef(paper),  # type: ignore[arg-type]
                    title_block=board.title_block if board is not None else None,
                    lib_symbols=tuple(embedded_here),
                    symbols=tuple(content.symbols),
                    labels=tuple(content.labels),
                    no_connects=tuple(content.flags),
                    wires=tuple(content.wires),
                    junctions=junctions,
                    sheets=placed_refs,
                    pages=(SheetPage("/", "1"),) if not module else (),
                )
                continue
        if layout != "grid":
            texts = {
                (item.box.key, number): _padded(text, widths.get((item.box.key, number), 0))
                for item in items
                for number, text in blocks.texts(module, item, net_of).items()
            }
            snapped: list[Cluster] = []
            for part_keys in _partition(boxes, local):  # a satellite snaps to an anchor of its own group
                snapped += schlayout.snap_satellites(
                    [box for box in boxes if box.key in part_keys],
                    texts,
                    placements={k: v for k, v in here.items() if k in part_keys},
                )
            clusters = tuple(snapped)
        found = schlayout.layout_units(
            boxes,
            placements=here,
            flags=flags,
            clusters=clusters,
            refs=refs,
            sheet=module or name,
            groups=[(group.members, group.flow) for group in local],
            widths=widths or None,
        )
        issues += [found_issue for found_issue in found.issues if found_issue not in issues]
        content = _content(
            state,
            items,
            found,
            tree.use_paths[module],
            tree.board_paths[module],
            clusters,
            lambda net, module=module: blocks.label(module, net),
        )
        definitions = sorted({id(i.definition): i.definition for i in items}.values(), key=lambda e: e.lib_id)
        embedded_here = [d.definition for d in definitions]
        if not module and flag is not None:
            _flags(state, content, flag, flag_nets, found, tree.use_paths[""])
            embedded_here.append(flag.definition)
        placed_refs = tuple(
            _placed_ref(state, content, blocks, tree.refs[m], box, found.origins, module)
            for m, box in zip(children, refs, strict=True)
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
        libraries.setdefault(flag.nickname, []).append(flag)
    for definition in powers.definitions():
        libraries.setdefault(definition.nickname, []).append(definition)
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
        powers.count,
        state.fallbacks,
    )


# --- block sheets (change c0269) ------------------------------------------------------------------

PAD = "\x00"
"""Pads a label text to the shared width of its pin; no net name holds it."""


@dataclass(frozen=True)
class _Blocks:
    """The block sheets of a design: per block instance on a sheet of its own, the nets that one port
    member binds (net id → member), and the sheet pins of its reference, in written order."""

    hier: Mapping[str, Mapping[str, PortPin]]
    pins: Mapping[str, tuple[PortPin, ...]]
    nets: Mapping[str, Net]

    def label(self, module: str, net: Net) -> tuple[str, str, str]:
        """(kind, text, shape) of a label of ``net`` on the sheet of ``module``: hierarchical with the
        member's sheet name for a net that one port member of a block binds, else global."""
        found = self.hier.get(module, {}).get(net.id)
        if found is None:
            return ("global", netnames.stored_name(net.name), "passive")
        return ("hierarchical", found.name, found.shape)

    def texts(self, module: str, item: _Unit, net_of: Mapping[tuple[str, str], Net]) -> dict[str, str]:
        """Pin number → the label text at that pin of ``item`` on the sheet of ``module``."""
        return {
            pin.number: self.label(module, net_of[(item.component.id, pin.number)])[1]
            for pin in item.part.symbol.pins_of(item.unit, 1)
            if (item.component.id, pin.number) in net_of
        }

    def ref_pins(self, module: str, parent: str, widths: Mapping[tuple[str, str], int]) -> tuple[RefPin, ...]:
        """The pins of the reference of ``module`` on the sheet of ``parent``, with the length of the label
        the parent writes at each (or the shared width of ``widths``, keyed by module and pin name)."""
        return tuple(
            RefPin(
                pin.name,
                "left" if pin.direction == "in" else "right",
                widths.get((module, pin.name), len(self.label(parent, self.nets[pin.net])[1])),
            )
            for pin in self.pins.get(module, ())
        )


def _block_sheets(
    design: Design,
    modules: Sequence[str],
    by_sheet: Mapping[str, Sequence[_Unit]],
    net_of: Mapping[tuple[str, str], Net],
    issues: list[Issue],
) -> _Blocks:
    """The hierarchical nets and sheet pins of the block instances among ``modules`` ("Block sheet pins").
    A net that two members of one block bind keeps its global labels: ``build.block-port-merged``."""
    nets = {net.id: net for net in design.circuit.nets}
    made_by = {m.path for m in design.circuit.modules if m.block}
    ports = port_pins(design.circuit)
    hier: dict[str, Mapping[str, PortPin]] = {}
    for module in modules:
        if module not in made_by:
            continue
        single, merged = split_merged([p for p in ports.get(module, ()) if p.net in nets])
        hier[module] = single
        for net_id, found in sorted(merged.items()):
            names = ", ".join(sorted(pin.name for pin in found))
            issues.append(
                issue(
                    "build.block-port-merged",
                    f"block {module}: the port members {names} bind one net {nets[net_id].name}; it keeps "
                    "global labels on the block's sheet, and those members get no sheet pin",
                    module,
                )
            )
    pins: dict[str, tuple[PortPin, ...]] = {}
    points: dict[str, set[str]] = {}
    for module in reversed(modules):  # depth first reversed: a module after every module below it
        own = {
            net_of[(item.component.id, pin.number)].id
            for item in by_sheet.get(module, ())
            for pin in item.part.symbol.pins_of(item.unit, 1)
            if (item.component.id, pin.number) in net_of
        }
        for child in (m for m in modules if module_of(m) == module):
            own |= {pin.net for pin in pins.get(child, ())}
        points[module] = own
        found = [pin for pin in hier.get(module, {}).values() if pin.net in own]
        left = sorted((p for p in found if p.direction == "in"), key=lambda p: p.name)
        right = sorted((p for p in found if p.direction != "in"), key=lambda p: p.name)
        if left or right:
            pins[module] = (*left, *right)
    return _Blocks(MappingProxyType(hier), MappingProxyType(pins), MappingProxyType(nets))


def _relabelled(item: _Unit, texts: Mapping[str, str]) -> UnitBox:
    """The box of ``item`` with the label lengths of ``texts``."""
    return unit_box(
        item.part.path,
        item.part.symbol,
        item.unit,
        texts,
        max(len(item.component.ref), len(item.component.value)),
    )


def _padded(text: str, width: int) -> str:
    return text + PAD * (width - len(text))


def _partition(boxes: Sequence[UnitBox], groups: Sequence[SheetGroup]) -> list[set[str]]:
    """The unit keys of each group, then of the units in no group; one set of all keys without groups."""
    if not groups:
        return [{box.key for box in boxes}]
    found: list[set[str]] = []
    left = {box.key for box in boxes}
    for group in groups:
        members = set(group.members)
        keys = {key for key in left if schlayout_path(key) in members}
        found.append(keys)
        left -= keys
    found.append(left)
    return found


def schlayout_path(key: str) -> str:
    """The component path of a unit key (``U1#2`` → ``U1``)."""
    path, sep, unit = key.rpartition("#")
    return path if sep and unit.isdigit() else key


Widths = tuple[dict[tuple[str, str], int], dict[tuple[str, str], int]]


def _shared_widths(
    blocks: _Blocks,
    by_sheet: Mapping[str, Sequence[_Unit]],
    groups: Mapping[str, Sequence[SheetGroup]],
    fixed: Mapping[str, SymbolPlacement],
    net_of: Mapping[tuple[str, str], Net],
    modules: Sequence[str],
) -> dict[str, Widths]:
    """Per block sheet, the label widths it shares with the other instances of its block that hold the
    same units, groups and sheet pins ("Shared arrangement of block sheets"): per (unit key, pin) the
    longest text at that relative pin over those instances, and per (nested module, pin name) the longest
    label at that relative sheet pin. A sheet with a placed unit shares nothing."""
    classes: dict[tuple[object, ...], list[str]] = {}
    for module in blocks.hier:
        items = by_sheet.get(module, ())
        if any(item.box.key in fixed for item in items):
            continue
        cut = len(module) + 1
        children = [m for m in modules if module_of(m) == module]
        signature = (
            tuple(sorted(item.box.key[cut:] for item in items)),
            tuple((g.key, tuple(m[cut:] for m in g.members), g.flow) for g in groups.get(module, ())),
            tuple(pin.name for pin in blocks.pins.get(module, ())),
            tuple((child[cut:], tuple(p.name for p in blocks.pins.get(child, ()))) for child in children),
        )
        classes.setdefault(signature, []).append(module)
    found: dict[str, Widths] = {}
    for members in classes.values():
        if len(members) < 2:
            continue
        units: dict[tuple[str, str], int] = {}
        refs: dict[tuple[str, str], int] = {}
        for module in members:
            cut = len(module) + 1
            for item in by_sheet[module]:
                for number, text in blocks.texts(module, item, net_of).items():
                    key = (item.box.key[cut:], number)
                    units[key] = max(units.get(key, 0), len(text))
            for child in (m for m in modules if module_of(m) == module):
                for pin in blocks.ref_pins(child, module, {}):
                    key = (child[cut:], pin.name)
                    refs[key] = max(refs.get(key, 0), pin.label)
        for module in members:
            found[module] = (
                {(f"{module}/{key}", number): width for (key, number), width in units.items()},
                {(f"{module}/{key}", name): width for (key, name), width in refs.items()},
            )
    return found


def _placed_ref(
    state: _State,
    content: _Content,
    blocks: _Blocks,
    ref: SheetRef,
    box: RefBox,
    origins: Mapping[str, SymbolPlacement],
    parent: str,
) -> SheetRef:
    """The reference ``ref`` at its place in ``origins``, with its sheet pins; the label the sheet of
    ``parent`` writes at each pin is added to ``content``, turned away from the box."""
    origin = origins[schlayout.ref_key(box.path)]
    at = Point(origin.x, origin.y)
    if not box.pins:
        return dataclasses.replace(ref, position=at)
    name = state.name
    points = schlayout.ref_pin_points(box)
    pins: list[SheetPin] = []
    for pin in blocks.pins[box.path]:
        offset, side = points[pin.name]
        point = Point(at.x + offset.x, at.y + offset.y)
        angle = 180 if side == "left" else 0
        pins.append(
            SheetPin(
                id=derived_id("shr", ID_BACKEND, f"{name}:sheetpin:{box.path}:{pin.name}"),
                name=pin.name,
                shape=pin.shape,  # type: ignore[arg-type]
                position=point,
                rotation=angle * 1_000_000,
            )
        )
        kind, text, shape = blocks.label(parent, blocks.nets[pin.net])
        tag = "hlabel" if kind == "hierarchical" else "label"
        content.labels.append(
            NetLabel(
                id=derived_id("lbl", ID_BACKEND, f"{name}:{tag}:sheet:{box.path}:{pin.name}"),
                kind=kind,  # type: ignore[arg-type]
                name=text,
                position=point,
                rotation=angle * 1_000_000,
                shape=shape,  # type: ignore[arg-type]
            )
        )
    return dataclasses.replace(
        ref, position=at, size=Size(ref.size.w, schlayout.ref_height(box.pins)), pins=tuple(pins)
    )


def _flag(
    flag_nets: Sequence[Net],
    embedded: Mapping[tuple[str, tuple[tuple[str, str], ...]], EmbeddedSymbol],
    libraries: Iterable[str],
    target: int,
    issues: list[Issue],
) -> EmbeddedSymbol | None:
    """The power flag of a sheet with ``flag_nets``, in the library that holds it (change c0143): a library
    of the design whose name differs from ``fenolite`` in letter case only, else ``fenolite``. A part
    whose symbol has the flag's name in that library is reported, since one library holds one symbol of a
    name."""
    if not flag_nets:
        return None
    library = symembed.flag_library([*(found.nickname for found in embedded.values()), *libraries])
    flag = symembed.power_flag(target, library)
    if any(lib_id == flag.lib_id for lib_id, _ in embedded):
        issues.append(
            issue(
                "build.reserved-library",
                f"{flag.lib_id}: the symbol name {symembed.FLAG_NAME!r} of the library {library!r} is kept "
                "for Fenolite's power flag, which this design needs",
                flag.lib_id,
                "give the symbol another name, or its library another nickname",
            )
        )
    return flag


def _flag_box(net: Net, flag: EmbeddedSymbol) -> UnitBox:
    return UnitBox(
        f"{FLAG_KEY}{net.name}",
        (UnitPin("1", Point(0, 0), 90, len(netnames.stored_name(net.name))),),
        (0, 0, 2_540_000, 2_540_000),
        flag.lib_id,
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
    fallbacks: int = 0


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
    labeller: Callable[[Net], tuple[str, str, str]] | None = None,
) -> _Content:
    """The symbols, labels, no-connect flags and snap wires of the units ``items`` of one sheet, whose
    symbols are used at ``use_path``; ``board_path`` is the prefix of the footprint paths of that sheet.
    A pin that a snap wire of ``clusters`` joins gets no label of its own: the pair has one, at the
    satellite's near pin. ``labeller`` gives the (kind, text, shape) of the label of a net on that sheet;
    without it every label is the net's global label."""
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
            in_bom=component.bom_only
            or (part.footprint is not None and "exclude_from_bom" not in part.footprint.flags),
            on_board=not component.bom_only,
            uses=(SymbolUse(name, use_path, component.ref, unit),),
        )
        content.symbols.append(instance)
        state.paths.setdefault(component.id, f"{board_path}/{kicad_uuid(instance)}")
        numbers = component.pin_pads()
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
                kind, text, shape = (
                    labeller(net)
                    if labeller is not None
                    else ("global", netnames.stored_name(net.name), "passive")
                )
                head = "hlabel" if kind == "hierarchical" else "label"
                content.labels.append(
                    NetLabel(
                        id=derived_id("lbl", ID_BACKEND, f"{name}:{head}:{part.path}:{tag}"),
                        kind=kind,  # type: ignore[arg-type]
                        name=text,
                        position=point,
                        rotation=angle * 1_000_000,
                        shape=shape,  # type: ignore[arg-type]
                    )
                )
                continue
            if pin_key in state.marks:
                content.flags.append(
                    NoConnectFlag(
                        id=derived_id("ncf", ID_BACKEND, f"{name}:nc:{part.path}:{tag}"), position=point
                    )
                )
            # every pad of the pin: a pin bonded to several pads is one net in KiCad, named after one pad
            pads = numbers.get(pin.number, (pin.number,))
            if (component.id, pads[0]) in state.pad_nets:
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
            open_name = netnames.open_name(
                component.ref,
                unit=unit,
                unit_count=symbol.unit_count,
                pin_name=pin.name,
                pads=pads,
                marked=pin_key in state.marks,
            )
            for pad in pads:
                state.pad_nets[(component.id, pad)] = open_name
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
    _wired_flags(state, content, flag, flag_nets, layout.origins, use_path, labelled=True)


def _wired_flags(
    state: _State,
    content: _Content,
    flag: EmbeddedSymbol,
    flag_nets: Sequence[Net],
    origins: Mapping[str, SymbolPlacement],
    use_path: str,
    *,
    labelled: bool = False,
    values: Mapping[str, Point] | None = None,
) -> None:
    """One power flag per net of ``flag_nets`` at its place in ``origins``, with a label of its net when
    ``labelled`` (a wired sheet joins the flag to a power symbol by a wire instead, and ``values`` gives
    where it writes each flag's Value, by net name)."""
    name = state.name
    for index, net in enumerate(flag_nets, start=1):
        place = origins[f"{FLAG_KEY}{net.name}"]
        value_at = (values or {}).get(net.name)
        ext = (
            {
                sch_format.DRAWN_EXT: sch_format.field_pose_ext(
                    (
                        sch_format.FieldPose("Reference", Point(place.x, place.y), 0, "", True),
                        sch_format.FieldPose("Value", value_at, 0, ""),
                    )
                )
            }
            if value_at is not None
            else {}
        )
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
                ext=ext,
            )
        )
        if not labelled:
            continue
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


# --- wired sheets (change c0406) --------------------------------------------------------------------


@dataclass(frozen=True)
class _WiredDesign:
    """What every wired sheet of a design shares: the role of each net (design D2 of change c0406), the
    nets of bus interfaces, the nets by id, and the supply nets that need a power flag."""

    roles: Mapping[str, str]
    buses: frozenset[str]
    nets: Mapping[str, Net]
    flag_nets: list[Net]

    @staticmethod
    def of(design: Design, components: Mapping[str, Component]) -> _WiredDesign:
        circuit = design.circuit
        declared: dict[str, str] = {}
        buses: set[str] = set()
        for interface in circuit.interfaces:
            for role, net_id in interface.members.items():
                if interface.kind == "ground" or (
                    interface.kind == "power" and schwired.name_role(role.upper()) == "ground"
                ):
                    declared[net_id] = "ground"
                elif interface.kind == "power":
                    declared.setdefault(net_id, "power")
                elif interface.kind in schwired.BUS_KINDS:
                    buses.add(net_id)
        roles: dict[str, str] = {}
        flag_nets: list[Net] = []
        for net in circuit.nets:
            power_pin = False
            driven = False
            fitted = False
            for member in net.members:
                component = components.get(member.component_id)
                if component is None or component.dnp:
                    continue
                fitted = True
                for pin in component.pins:
                    if pin.number == member.pin:
                        power_pin = power_pin or pin.etype in ("power_in", "power_out")
                        driven = driven or pin.etype == "power_out"
            role = schwired.net_role(
                netnames.stored_name(net.name), power_pin=power_pin, declared=declared.get(net.id, "")
            )
            roles[net.id] = role
            if schwired.is_supply(role) and fitted and not driven:
                flag_nets.append(net)
        return _WiredDesign(
            MappingProxyType(roles),
            frozenset(buses),
            MappingProxyType({net.id: net for net in circuit.nets}),
            sorted(flag_nets, key=lambda n: n.name),
        )


@dataclass
class _Powers:
    """The power symbols of a design: their library, target, the definitions used and on which sheets, and
    the number of instances so far (their references count over the whole design)."""

    library: str
    target: int
    count: int = 0
    made: dict[str, EmbeddedSymbol] = field(default_factory=lambda: {})
    sheets: dict[str, set[str]] = field(default_factory=lambda: {})

    def symbol(self, kind: str, module: str) -> EmbeddedSymbol:
        if kind not in self.made:
            self.made[kind] = symembed.power_symbol(kind, self.target, self.library)
        self.sheets.setdefault(module, set()).add(kind)
        return self.made[kind]

    def used_on(self, module: str) -> list[EmbeddedSymbol]:
        return sorted((self.made[k] for k in self.sheets.get(module, ())), key=lambda e: e.lib_id)

    def definitions(self) -> list[EmbeddedSymbol]:
        return sorted(self.made.values(), key=lambda e: e.lib_id)

    def instance(
        self, name: str, module: str, use_path: str, power: schwired.WPower, value: str
    ) -> SymbolInstance:
        definition = self.symbol(power.kind, module)
        self.count += 1
        ref = f"{symembed.POWER_REFERENCE}{self.count:03d}"
        angle = 90_000_000 if power.rotation % 180 else 0
        poses = (
            sch_format.FieldPose("Reference", power.at, 0, "", True),
            sch_format.FieldPose("Value", power.value_at, angle, ""),
        )
        return SymbolInstance(
            id=derived_id("sci", ID_BACKEND, f"{name}:power:{module}:{power.at.x},{power.at.y}"),
            lib_ref=definition.lib_id,
            position=power.at,
            rotation=power.rotation * 1_000_000,
            ref=ref,
            value=value,
            properties={key: "" for key in MANDATORY} | {"Reference": ref, "Value": value},
            in_bom=False,
            on_board=False,
            uses=(SymbolUse(name, use_path, ref, 1),),
            ext={sch_format.DRAWN_EXT: sch_format.field_pose_ext(poses)},
        )


def _reserve_power_names(
    embedded: Mapping[tuple[str, tuple[tuple[str, str], ...]], EmbeddedSymbol],
    library: str,
    issues: list[Issue],
) -> None:
    """``build.reserved-library`` for a part whose symbol has the name of a power symbol in its library."""
    for name in symembed.POWER_NAMES.values():
        lib_id = f"{library}:{name}"
        if any(found == lib_id for found, _ in embedded):
            issues.append(
                issue(
                    "build.reserved-library",
                    f"{lib_id}: the symbol name {name!r} of the library {library!r} is kept for Fenolite's "
                    "power symbols, which a wired sheet draws",
                    lib_id,
                    "give the symbol another name, or its library another nickname",
                )
            )


def _wired_sheet(
    state: _State,
    wired: _WiredDesign,
    powers: _Powers,
    items: Sequence[_Unit],
    module: str,
    blocks: _Blocks,
    refs: Sequence[RefBox],
    flag_nets: Sequence[Net],
    groups: Sequence[Sequence[str]],
    placed_keys: Sequence[str],
    use_path: str,
    board_path: str,
    issues: list[Issue],
) -> tuple[_Content, str, dict[str, SymbolPlacement], tuple[Junction, ...], dict[str, Point]] | None:
    """The content of the wired sheet of ``module`` ("Wired sheet layout"), its paper, its placements
    (units, sheet references and flags) and its junctions; ``None`` after a fallback to ``"readable"``
    ("Wired layout fallbacks")."""
    where = module or state.name
    if placed_keys:
        issues.append(
            issue(
                "build.schematic-wired-fallback",
                f"sheet {where}: {len(placed_keys)} unit(s) are placed by the placements file, so the sheet "
                "is drawn with the readable layout",
                where,
                "remove the placements of this sheet to draw it with wires",
            )
        )
        return None
    units: list[schwired.WUnit] = []
    nets: dict[tuple[str, str], schwired.WNet] = {}
    marks: set[tuple[str, str]] = set()
    for item in items:
        symbol = item.part.symbol
        pins = symbol.pins_of(item.unit, 1)
        units.append(
            schwired.WUnit(
                item.box.key,
                tuple(
                    schwired.WPin(p.number, p.name, p.position, (p.rotation // 1_000_000) % 360, p.etype)
                    for p in pins
                ),
                _body(symbol, pins),
                max(len(item.component.ref) + (1 if symbol.unit_count > 1 else 0), len(item.component.value)),
                symbol.unit_count == 1,
            )
        )
        for pin in pins:
            key = (item.component.id, pin.number)
            net = state.net_of.get(key)
            if net is not None:
                kind, text, _ = blocks.label(module, net)
                role = wired.roles[net.id] if kind == "global" else "signal"
                nets[(item.box.key, pin.number)] = schwired.WNet(
                    net.id, text, role, net.id in wired.buses, netnames.stored_name(net.name)
                )
            elif key in state.marks:
                marks.add((item.box.key, pin.number))
    flags = [
        schwired.WNet(
            net.id, netnames.stored_name(net.name), wired.roles[net.id], False, netnames.stored_name(net.name)
        )
        for net in flag_nets
    ]
    found = schwired.layout_sheet(units, nets, marks=marks, refs=refs, flags=flags, groups=groups)
    if not found.fits:
        issues.append(
            issue(
                "build.schematic-wired-fallback",
                f"sheet {where}: the wired drawing fits no paper up to A0, so the sheet is drawn with the "
                "readable layout",
                where,
                "split the module into sub-modules so that each sheet holds fewer parts",
            )
        )
        return None
    state.fallbacks += found.fallbacks
    name = state.name
    origins = dict(found.origins)
    values: dict[str, Point] = {}
    for flag_at in found.flags:
        origins[f"{FLAG_KEY}{wired.nets[flag_at.net].name}"] = SymbolPlacement(flag_at.at.x, flag_at.at.y)
        values[wired.nets[flag_at.net].name] = flag_at.value_at
    content = _content(
        state, items, SheetLayout(found.paper, MappingProxyType(origins), {}), use_path, board_path
    )
    content.labels.clear()  # a wired sheet names each drawn group once (below)
    posed: list[SymbolInstance] = []
    for item, symbol in zip(items, content.symbols, strict=True):
        pose = found.fields.get(item.box.key)
        if pose is None:
            posed.append(symbol)
            continue
        angle = pose.angle * 1_000_000
        poses = (
            sch_format.FieldPose("Reference", pose.reference, angle, ""),
            sch_format.FieldPose("Value", pose.value, angle, ""),
        )
        posed.append(
            dataclasses.replace(symbol, ext={sch_format.DRAWN_EXT: sch_format.field_pose_ext(poses)})
        )
    for power in found.powers:
        posed.append(
            powers.instance(name, module, use_path, power, netnames.stored_name(wired.nets[power.net].name))
        )
    content.symbols = posed
    for label in found.labels:
        kind, text, shape = blocks.label(module, wired.nets[label.net])
        head = "hlabel" if kind == "hierarchical" else "label"
        net_name = wired.nets[label.net].name
        content.labels.append(
            NetLabel(
                id=derived_id("lbl", ID_BACKEND, f"{name}:{head}:net:{module}:{net_name}:{label.group}"),
                kind=kind,  # type: ignore[arg-type]
                name=text,
                position=label.at,
                rotation=label.angle * 1_000_000,
                shape=shape,  # type: ignore[arg-type]
            )
        )
    content.wires = [
        Wire(
            id=derived_id("wir", ID_BACKEND, f"{name}:wire:{module}:{a.x},{a.y}:{b.x},{b.y}"), start=a, end=b
        )
        for a, b in found.wires
    ]
    junctions = tuple(
        Junction(id=derived_id("wir", ID_BACKEND, f"{name}:junction:{module}:{p.x},{p.y}"), position=p)
        for p in found.junctions
    )
    return content, found.paper, origins, junctions, values


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
