# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Building a model design into an experimental Altium project (capability altium-build, change c0032).

``build_altium`` runs the build checks of ``ALTIUM_ISSUE_CODES``, gives every component the generic pins
its nets name, validates, writes ``<name>.PrjPcb`` (only when the output folder has none) and
``<name>.SchDoc``, binary by default or ASCII (change c0033), through
``fenolite.backends.altium.project.write_project``, and adds the ``.fenolite/`` layer texts and build
record of c0011 (``lens.build``). A design with an error gives no file. It reads no
library and no Altium or KiCad file: the board, placements, net classes and diff pairs stay in the model
and are reported as not lowered.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Literal

from fenolite.backends.altium import (
    binary,
    hierarchy,
    lower,
    pcbdoc,
    pcblib,
    pcbrecords,
    project,
    rulemap,
    schdot,
    schlib,
)
from fenolite.backends.altium import outjob as job_writer
from fenolite.backends.altium.altsym import DEFAULT_BODIES, AltiumSymbol, SymbolBodies, from_symbol_def
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.cfb import CompoundTooLarge, name_key
from fenolite.backends.altium.hierarchy import ProjectSheets
from fenolite.backends.altium.project import WRITE_KINDS, component_path, split_link, unique_id
from fenolite.backends.altium.read.outjob import OutputGroup, record_fields
from fenolite.backends.altium.symbols import natural_key
from fenolite.backends.kicad import slots as kicad_slots
from fenolite.backends.kicad.embed import footprint_extent
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryResolver
from fenolite.backends.kicad.sexpr import Atom, Node, parse_fragment
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.lens import altium_copper
from fenolite.lens.altium_copper import CopperSource, match_source
from fenolite.lens.build import (
    CACHE_DIR,
    RECORD_FILE,
    RECORD_SCHEMA,
    STAGING_GAP,
    STAGING_OFFSET,
    BuildOutput,
    PlacementRequest,
    UnresolvedLibrariesError,
)
from fenolite.lens.placements import FULL_TURN
from fenolite.model import canonical
from fenolite.model.base import Opaque
from fenolite.model.board import PPM_PER_PERCENT, FootprintInstance, Graphic, Pad
from fenolite.model.circuit import Component, Net, Pin, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef, SymbolDef
from fenolite.model.presentation import PAPER_SIZES, DrawingSheet, SheetFrameRef, TitleBlock

TARGET = "altium"
"""The value of ``build --target`` for this builder, and of ``target`` in its result and record."""
DSL_BACKEND = "dsl"
UPDATE_COMMAND = "Tools » Update From Libraries"
MAX_PIN_TEXT = 255
MODEL_ONLY_INTERFACES: frozenset[str] = frozenset({"diff_pair", "i2c", "spi", "uart", "usb2"})
"""The interface kinds an Altium build keeps in the model and names in one ``altium.not-lowered`` info."""
"""The longest pin name or number a binary pin's short string holds."""
ALTIUM_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "altium.lib-id-form": "error",
        "altium.footprint-form": "error",
        "altium.text-unwritable": "error",
        "altium.name-case-collision": "error",
        "altium.unique-id-collision": "error",
        "altium.schematic-too-large": "error",
        "altium.library-too-large": "error",
        "altium.unknown-pin": "error",
        "altium.pin-pad-map-invalid": "error",
        "altium.symbol-off-grid": "error",
        "altium.pin-text-too-long": "error",
        "altium.symbol-name-collision": "error",
        "altium.pcb-too-large": "error",
        "altium.sheet-name-collision": "error",
        "altium.harness-name": "error",
        "altium.harness-net-shared": "error",
        "altium.harness-power-net": "error",
        "altium.no-footprint": "warning",
        "altium.sheet-custom": "warning",
        "altium.pin-lossy": "warning",
        "altium.footprint-unresolved": "warning",
        "altium.footprint-unsupported": "warning",
        "altium.footprint-name-collision": "warning",
        "altium.sheet-paper": "warning",
        "altium.primitive-dropped": "warning",
        "altium.generic-symbols": "info",
        "altium.bus-flattened": "info",
        "altium.symbol-simplified": "info",
        "altium.section-key": "info",
        "altium.schlib-generic": "info",
        "altium.schlib-not-in-project": "info",
        "altium.not-lowered": "info",
        "altium.project-kept": "info",
        "altium.footprint-extras-dropped": "info",
        "altium.pcbdoc-not-written": "info",
        "altium.pcb-staged": "info",
        "altium.pcb-not-in-project": "info",
        "altium.sheets-not-in-project": "info",
        "altium.outjob-not-listed": "info",
        **altium_copper.COPPER_ISSUE_CODES,
    }
)
"""The closed table of the Altium build's own issue codes (``model.*`` and ``build.layout-exists`` pass
through)."""
ALTIUM_BUILD_EVIDENCE = Evidence.combine(
    Evidence(
        Level.INFERRED,
        hypotheses=(
            "H-A-ECO-NETCLASS",
            "H-A-ECO-PRJ-KEYS",
            "H-A-ECO-ROOMS",
            "H-A-ECO-SUPPLY",
            "H-A-PRJ-KEEP",
            "H-A-PRJ-OPEN",
            "H-A-SCH-ECO",
            "H-A-SCH-LINEEND",
            "H-A-SCH-LINK",
            "H-A-SCH-NC-ERC",
            "H-A-SCH-NC-RECORD",
            "H-A-SCH-NC-VIEWER",
            "H-A-SCH-NETS",
            "H-A-SCH-OPEN",
            "H-A-SCH-RELINK",
            "H-A-SCH-UID",
            "H-A-SCH-UPDATE",
            "H-A-SCHX-BUS",
            "H-A-SCHX-DIR",
            "H-A-SCHX-ECO",
            "H-A-SCHX-GRAPHICS",
            "H-A-SCHX-PINMAP",
            "H-A-SCHX-PINMAP-FORM",
            "H-A-SCHX-READBACK",
            "H-A-SCHX-TEXT",
            "H-A-SCHX-TREE",
        ),
    ),
    binary.EVIDENCE,
    Evidence(
        Level.INFERRED,
        hypotheses=(
            "H-A-SCHLIB-KICAD9",
            "H-A-SCHLIB-MULTIPART",
            "H-A-SCHLIB-PRJ",
            "H-A-SCHLIB-SCHDOC",
            "H-A-SCHLIB-UPDATE",
        ),
    ),
    schlib.EVIDENCE,
    pcbrecords.EVIDENCE,
    hierarchy.EVIDENCE,
    pcbdoc.EVIDENCE,
    pcblib.EVIDENCE,
    rulemap.EVIDENCE,
)
"""``INFERRED`` for every build: author reports cover the files the maintainer opened, never a design, and
the kicad-cli oracle checks only what KiCad's importer reads. It names the rows of both schematic forms
(``binary.EVIDENCE`` holds the ``H-A-SCHBIN-*`` rows) and of the libraries (every ``H-A-SCHLIB-*`` row,
``schlib.EVIDENCE`` holding those of the library file) and of the hierarchy and harnesses
(``hierarchy.EVIDENCE``: every ``H-A-SCH-HIER-*`` and ``H-A-SCH-HARN-*`` row, change c0037), and the rule
rows ``H-A-RULE-*`` of the PCB document (``rulemap.EVIDENCE``, change c0084). The rows of a component body
(``H-A-PCBX-BODY-*``, change c0121) come with ``pcbdoc.EVIDENCE`` and ``pcblib.EVIDENCE``: they are claims
of a build that writes bodies, which is on request only."""
EXPERIMENTAL: Mapping[str, object] = MappingProxyType(
    {
        "name": "altium-schematic-writer",
        "command": "build",
        "option": f"--target {TARGET}",
        "write_kinds": list(WRITE_KINDS),
    }
)
"""The ``capabilities`` entry of this writer, without its evidence (``ALTIUM_BUILD_EVIDENCE``)."""
PCB_WRITE_KINDS: tuple[str, ...] = (project.PCBDOC_KIND, project.PCBLIB_KIND)
"""The write kinds of the PCB writers (change c0035), listed by their own ``capabilities`` entry."""
AUTHORED_FOOTPRINT_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-DSL-FOOTPRINT",))
PCB_BUILD_EVIDENCE = Evidence.combine(pcbrecords.EVIDENCE, pcblib.EVIDENCE, pcbdoc.EVIDENCE, rulemap.EVIDENCE)
"""``INFERRED``: every ``H-A-PCB-*`` row and the rule rows ``H-A-RULE-*`` (change c0084); the kicad-cli
oracles check only what KiCad reads."""
PCB_EXPERIMENTAL: Mapping[str, object] = MappingProxyType(
    {
        "name": "altium-pcb-writer",
        "command": "build",
        "option": f"--target {TARGET}",
        "write_kinds": list(PCB_WRITE_KINDS),
    }
)
"""The ``capabilities`` entry of the PCB writers, without its evidence (``PCB_BUILD_EVIDENCE``)."""


KEPT_PROJECT_CODES = (
    "altium.outjob-not-listed",
    "altium.pcb-not-in-project",
    "altium.project-kept",
    "altium.schlib-not-in-project",
    "altium.sheets-not-in-project",
)
"""The infos about a kept project file: that it is kept, and what it does not list. None of them is given
for a project file that the build writes again (change c0138)."""


UNREAD_PROJECT_HINT = (
    "the kept project file could not be read, so every document of the build is named, whether the file "
    "lists it or not"
)
"""The hint of an info about a kept project file that Fenolite's project reader could not read."""


def not_listed(files: Sequence[str], listed: Collection[str] | None) -> list[str]:
    """The files of ``files`` that a kept project file does not list. ``listed`` holds the document paths
    of the file, case-folded (``kept_documents``); ``None`` stands for a file that was not read, and then
    every file counts as not listed."""
    if listed is None:
        return list(files)
    return [file for file in files if file.casefold() not in listed]


def kept_documents(paths: Sequence[str]) -> frozenset[str]:
    """The document paths of a kept project file as ``not_listed`` compares them: case-folded, with the
    separators of a path written by Altium (a backslash) as forward slashes."""
    return frozenset(path.replace("\\", "/").casefold() for path in paths)


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, ALTIUM_ISSUE_CODES[code], message, where=where, hint=hint)


def generic_pins(design: Design) -> Design:
    """``design`` with one passive pin per designator that its nets or its no-connect marks name on any
    component of the same lib id, in natural order, for every component that holds no pin yet: components
    sharing a lib id share one generic body, which is also their library symbol. A pin's name is its
    designator and its id is keyed ``pin:<path>:<designator>``."""
    lib_of = {c.id: c.lib_symbol_ref for c in design.circuit.components}
    used: dict[str, set[str]] = {lib: set() for lib in lib_of.values()}
    for net in design.circuit.nets:
        for member in net.members:
            if member.component_id in lib_of:
                used[lib_of[member.component_id]].add(member.pin)
    for mark in design.circuit.no_connects:
        if mark.component_id in lib_of:
            used[lib_of[mark.component_id]].add(mark.pin)
    components: list[Component] = []
    for component in design.circuit.components:
        if not component.pins:
            path = component_path(component)
            pins = tuple(
                Pin(id=derived_id("pin", DSL_BACKEND, f"pin:{path}:{d}"), number=d, name=d, etype="passive")
                for d in sorted(used[component.lib_symbol_ref], key=lambda d: (natural_key(d), d))
            )
            component = dataclasses.replace(component, pins=pins)
        components.append(component)
    circuit = dataclasses.replace(design.circuit, components=tuple(components))
    return dataclasses.replace(design, circuit=circuit)


SymbolSource = Literal["altium", "kicad"]


def symbol_source(lib_id: str) -> SymbolSource:
    """``altium`` for a lib id whose library part ends with ``.SchLib`` in any letter case (an Altium link,
    which gets a generic symbol), ``kicad`` for any other (a KiCad lib id, resolved like c0011)."""
    return "altium" if project.is_altium_link(lib_id) else "kicad"


def kicad_lib_ids(design: Design) -> tuple[str, ...]:
    """The well-formed KiCad lib ids of ``design``, sorted: the symbols the build must resolve."""
    ids = {c.lib_symbol_ref for c in design.circuit.components}
    return tuple(sorted(i for i in ids if split_link(i) is not None and symbol_source(i) == "kicad"))


def resolve_symbols(
    design: Design,
    resolver: LibraryResolver | None,
    authored: Mapping[str, SymbolDef] = MappingProxyType({}),
) -> dict[str, SymbolDef]:
    """Lib id → resolved ``SymbolDef`` of every KiCad lib id; ``UnresolvedLibrariesError`` (FEN-3001)
    with one ``kicad.lib.*`` issue per lib id that does not resolve. A lib id of ``authored`` (a symbol
    the script authored or took from the catalog, change c0086) is that symbol and is not resolved."""
    wanted = kicad_lib_ids(design)
    found: dict[str, SymbolDef] = {lib_id: authored[lib_id] for lib_id in wanted if lib_id in authored}
    wanted = tuple(lib_id for lib_id in wanted if lib_id not in found)
    if not wanted:
        return found
    if resolver is None:
        raise ValueError(f"the KiCad lib ids {', '.join(wanted)} need a library resolver")
    errors: list[LibraryError] = []
    for lib_id in wanted:
        try:
            found[lib_id] = resolver.symbol(lib_id)
        except LibraryError as error:
            errors.append(error)
    if errors:
        raise UnresolvedLibrariesError(errors)
    return found


def _with_symbol_fields(design: Design, symbols: Mapping[str, SymbolDef]) -> Design:
    """Components of KiCad lib ids take the symbol's ``Footprint`` when they name none, and its ``Value``
    when theirs is empty."""
    components: list[Component] = []
    for component in design.circuit.components:
        symbol = symbols.get(component.lib_symbol_ref)
        if symbol is not None:
            component = dataclasses.replace(
                component,
                lib_footprint_ref=component.lib_footprint_ref or symbol.footprint,
                value=component.value or symbol.value,
            )
        components.append(component)
    return dataclasses.replace(
        design, circuit=dataclasses.replace(design.circuit, components=tuple(components))
    )


def symbol_pins(symbol: SymbolDef, path: str) -> tuple[Pin, ...]:
    """One pin per pin number of body style 1 and the common style, over units 1 … n in order, with the
    pin's name and electrical type, ids keyed ``pin:<path>:<number>``."""
    pins: dict[str, Pin] = {}
    for unit in range(1, symbol.unit_count + 1):
        for pin in symbol.pins_of(unit, body_style=1):
            if pin.number not in pins:
                ident = derived_id("pin", DSL_BACKEND, f"pin:{path}:{pin.number}")
                pins[pin.number] = Pin(id=ident, number=pin.number, name=pin.name, etype=pin.etype)
    return tuple(pins.values())


def kicad_pins(design: Design, symbols: Mapping[str, SymbolDef]) -> tuple[Design, list[Issue]]:
    """``design`` with the symbol's pins on every component of a KiCad lib id, and net members and
    no-connect marks that name a pin name rewritten to every pin number with that name; one that names
    neither gives ``altium.unknown-pin``. The marks come back in ``PinRef`` order without duplicates."""
    issues: list[Issue] = []
    components: list[Component] = []
    pins_of: dict[str, tuple[Pin, ...]] = {}
    refs: dict[str, str] = {}
    for component in design.circuit.components:
        symbol = symbols.get(component.lib_symbol_ref)
        if symbol is not None and not component.pins:
            component = dataclasses.replace(component, pins=symbol_pins(symbol, component_path(component)))
            pins_of[component.id] = component.pins
            refs[component.id] = component.ref
        components.append(component)
    nets: list[Net] = []
    for net in design.circuit.nets:
        members: list[PinRef] = []
        for member in net.members:
            pins = pins_of.get(member.component_id)
            if pins is None or member.pin in {p.number for p in pins}:
                members.append(member)
                continue
            numbers = [p.number for p in pins if p.name == member.pin]
            if not numbers:
                issues.append(
                    issue(
                        "altium.unknown-pin",
                        f"{refs[member.component_id]} {member.pin}: neither a pin number nor a pin name of "
                        "its symbol",
                        net.name,
                        "connect the pin by its number",
                    )
                )
                continue
            members += [PinRef(member.component_id, number) for number in numbers]
        unique = tuple(dict.fromkeys(members))
        nets.append(dataclasses.replace(net, members=unique))
    paths = {c.id: component_path(c) for c in components}
    marks: set[PinRef] = set()
    for mark in design.circuit.no_connects:
        pins = pins_of.get(mark.component_id)
        if pins is None or mark.pin in {p.number for p in pins}:
            marks.add(mark)
            continue
        numbers = [p.number for p in pins if p.name == mark.pin]
        if not numbers:
            issues.append(
                issue(
                    "altium.unknown-pin",
                    f"{refs[mark.component_id]} {mark.pin}: neither a pin number nor a pin name of its "
                    "symbol, so it cannot be marked as not connected",
                    paths[mark.component_id],
                    "mark the pin by its number",
                )
            )
            continue
        marks.update(PinRef(mark.component_id, number) for number in numbers)
    circuit = dataclasses.replace(
        design.circuit, components=tuple(components), nets=tuple(nets), no_connects=tuple(sorted(marks))
    )
    return dataclasses.replace(design, circuit=circuit), issues


FootprintSource = Literal["altium", "kicad"]
PAD_DROPPED: Mapping[str, str] = MappingProxyType(
    {
        "solder_mask_margin": "solder mask margin",
        "solder_paste_margin": "solder paste margin",
        "solder_paste_margin_ratio": "solder paste margin ratio",
        "solder_paste_ratio": "solder paste margin ratio",
        "clearance": "clearance",
        "zone_connect": "zone connection",
        "thermal_width": "thermal width",
        "thermal_gap": "thermal gap",
        "thermal_bridge_width": "thermal width",
        "thermal_bridge_angle": "thermal angle",
        "die_length": "die length",
    }
)
"""KiCad pad children Altium's pad record has no field for: left out with ``altium.primitive-dropped``."""
PAD_REFUSED: Mapping[str, str] = MappingProxyType(
    {
        "chamfer_ratio": "has chamfered corners",
        "chamfer": "has chamfered corners",
        "primitives": "has custom primitives",
    }
)
"""KiCad pad children that make a pad unwritable: the footprint is refused."""


def footprint_source(link: str) -> FootprintSource:
    """``altium`` for a footprint link whose library part ends with ``.PcbLib`` in any letter case (the
    user's library: no footprint is written), ``kicad`` for any other (a KiCad footprint id, change c0035)."""
    return "altium" if project.is_altium_footprint(link) else "kicad"


def kicad_footprint_ids(design: Design) -> tuple[str, ...]:
    """The sorted distinct well-formed KiCad footprint links of the components' ``footprint`` fields."""
    links = {c.lib_footprint_ref for c in design.circuit.components if c.lib_footprint_ref}
    return tuple(sorted(i for i in links if split_link(i) is not None and footprint_source(i) == "kicad"))


def _opaque_nodes(entity: FootprintDef | object) -> list[Node]:
    bag = getattr(entity, "ext", {}).get("kicad")
    if bag is None:
        return []
    nodes: list[Node] = []
    for slot in kicad_slots.from_ext(bag):
        if isinstance(slot, Opaque):
            parsed = parse_fragment(slot.fragment)
            if isinstance(parsed, Node):
                nodes.append(parsed)
    return nodes


def _decimal_atom(node: Node) -> Decimal | None:
    atoms: list[Atom] = list(node.atoms())
    if len(atoms) != 1:
        return None
    try:
        return Decimal(atoms[0].value)
    except (InvalidOperation, ValueError):
        return None


def pad_extras(defn: FootprintDef) -> dict[str, pcblib.PadExtras]:
    """Pad id → the KiCad-only facts the model keeps opaque: the corner ratio of a rounded rectangle, a reason
    to refuse (an oval or offset drill, chamfers, custom primitives) and the settings Altium has no field for
    (margins, zone connection, thermal settings). Only this lens reads KiCad fragments (layering)."""
    out: dict[str, pcblib.PadExtras] = {}
    for pad in defn.pads:
        ratio: Decimal | None = None
        refusal: str | None = None
        dropped: list[str] = []
        if pad.padstack is not None and pad.padstack.hole_shape == "slot":
            refusal = "the drill is oval or has an offset"
        for node in _opaque_nodes(pad):
            head = node.name
            if head == "roundrect_rratio":
                ratio = _decimal_atom(node)
            elif head == "drill":
                refusal = refusal or "the drill is oval or has an offset"
            elif head in PAD_REFUSED:
                if head == "chamfer_ratio" and _decimal_atom(node) == 0:
                    continue
                refusal = refusal or PAD_REFUSED[head]
            elif head in PAD_DROPPED and PAD_DROPPED[head] not in dropped:
                if _decimal_atom(node) == 0:
                    continue
                dropped.append(PAD_DROPPED[head])
        out[pad.id] = pcblib.PadExtras(ratio, refusal, tuple(dropped))
    return out


def footprint_texts(defn: FootprintDef) -> int:
    """The number of ``fp_text`` children of a footprint read from a KiCad file (kept opaque)."""
    return sum(1 for node in _opaque_nodes(defn) if node.name == "fp_text")


def _counted(items: Sequence[str]) -> str:
    return ", ".join(f"{count} x {item}" for item, count in sorted(Counter(items).items()))


def resolve_footprints(
    design: Design,
    resolver: LibraryResolver | None,
    authored: Mapping[str, FootprintDef] = MappingProxyType({}),
    *,
    bodies: pcbdoc.BodyMode = "off",
) -> tuple[dict[str, pcblib.LibFootprint], list[Issue]]:
    """KiCad footprint link → the footprint written into ``<name>.PcbLib``, with the warnings and infos of
    footprints that do not resolve, are refused, collide on a storage name, or lose items. With ``bodies``
    ``extruded`` (change c0121) the component bodies of a definition are written with it."""
    issues: list[Issue] = []
    resolved: dict[str, pcblib.LibFootprint] = {}
    for link in kicad_footprint_ids(design):
        if link in authored:
            reason = ""
            defn = authored[link]
        elif resolver is None:
            reason = "no KiCad library table was given"
            defn = None
        else:
            try:
                defn = resolver.footprint(link)
                reason = ""
            except (LibraryError, FenoliteError) as error:
                defn = None
                code = error.issue.code if isinstance(error, LibraryError) else type(error).__name__
                reason = f"{code}: {error}"
        if defn is None:
            issues.append(
                issue(
                    "altium.footprint-unresolved",
                    f"{link} does not resolve ({reason}); its footprint is not written",
                    link,
                    "add the footprint library to the design folder's fp-lib-table",
                )
            )
            continue
        extras = pad_extras(defn)
        texts = footprint_texts(defn)
        asked = defn.bodies if bodies == "extruded" else ()
        check = pcblib.check_footprint(defn, extras, texts=texts, bodies=asked)
        if check.refusal is None:
            try:
                schlib.storage_name(defn.name)
            except ValueError as error:
                check = pcblib.FootprintCheck(str(error))
        if check.refusal is not None:
            issues.append(
                issue(
                    "altium.footprint-unsupported",
                    f"{link}: {check.refusal}; the footprint is not written",
                    link,
                    "use a footprint with round, rectangular, oval or rounded-rectangle pads and round holes",
                )
            )
            continue
        if check.dropped:
            issues.append(
                issue("altium.primitive-dropped", f"{link}: left out: {_counted(check.dropped)}", link)
            )
        if check.extras:
            issues.append(
                issue(
                    "altium.footprint-extras-dropped",
                    f"{link}: {', '.join(check.extras)} are not written; Altium adds the designator and "
                    "comment when it places the footprint",
                    link,
                )
            )
        resolved[link] = pcblib.LibFootprint(defn, extras, texts, asked)
    by_key: dict[tuple[int, tuple[int, ...]], list[str]] = {}
    for link, footprint in resolved.items():
        by_key.setdefault(name_key(schlib.storage_name(footprint.defn.name)), []).append(link)
    for links in by_key.values():
        if len(links) > 1:
            issues.append(
                issue(
                    "altium.footprint-name-collision",
                    f"the footprint links {', '.join(links)} get one footprint name in the PCB library; "
                    "none of them is written",
                    links[0],
                    "use one footprint library per footprint name",
                )
            )
            for link in links:
                del resolved[link]
    return resolved, issues


def _comment(component: Component) -> str:
    link = split_link(component.lib_symbol_ref)
    return component.value or (link[1] if link is not None else component.ref)


def pin_map_issues(design: Design, footprints: Mapping[str, pcblib.LibFootprint]) -> list[Issue]:
    """One ``altium.pin-pad-map-invalid`` for each pair of a pin-to-pad map that names a pin its component
    does not hold, for each pair that names a pad its resolved footprint does not hold, and for each pad
    that two pins of the component stand for, one of them by its own number (changes c0135 and c0123; the
    script refuses a map that lists one pad for two pins). The KiCad build refuses the same maps, whether
    or not the pins are on one net. The pads of a footprint that is not resolved are not checked. The model
    says ``model.pin-pad-map`` of a pad of two pins; the build says it under its own code as well, as the
    release 0.2.1 does, and reaches this function before it validates the model."""
    issues: list[Issue] = []
    for component in sorted(design.circuit.components, key=component_path):
        if not component.pin_pad_map:
            continue
        pins = {pin.number for pin in component.pins}
        # the pins of a part of an Altium link are the designators its nets use: the symbol is not known,
        # so a mapped pin that no net uses is not a pin "the symbol lacks"
        known_symbol = not project.is_altium_link(component.lib_symbol_ref)
        found = footprints.get(component.lib_footprint_ref)
        pads = {pad.number for pad in found.defn.pads if pad.number} if found is not None else None
        for pin, pad in component.pin_pad_map:
            if pin not in pins and known_symbol:
                text = f"{component.ref}: the pin-to-pad map names the pin {pin}, which the symbol lacks"
                issues.append(issue("altium.pin-pad-map-invalid", text, component_path(component)))
            if pads is not None and pad not in pads:
                text = f"{component.ref}: the pin-to-pad map names the pad {pad}, which the footprint lacks"
                issues.append(issue("altium.pin-pad-map-invalid", text, component_path(component)))
        holders: dict[str, list[str]] = {}
        for number in dict.fromkeys(pin.number for pin in component.pins if pin.number):
            for pad in component.pads_of(number):
                holders.setdefault(pad, []).append(number)
        for pad, found_pins in sorted(holders.items()):
            if len(found_pins) > 1:
                named = " and ".join(found_pins)
                text = f"{component.ref}: the pins {named} both stand for the pad {pad}"
                issues.append(issue("altium.pin-pad-map-invalid", text, component_path(component)))
    return issues


def with_written_values(design: Design) -> Design:
    """``design`` with the value that the documents hold for every component whose value is empty: its
    symbol's name, which both writers write as the comment (a component of Altium cannot be without one).
    The model that a build stores is the model its documents read back to (change c0044, RT-A2)."""
    components = tuple(
        component if component.value else dataclasses.replace(component, value=_comment(component))
        for component in design.circuit.components
    )
    return dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=components))


def _other_side(layer: str) -> str:
    """The layer of the other side: ``F.SilkS`` and ``B.SilkS`` swap (``lower._other_side``)."""
    if layer[:2] in ("F.", "F&"):
        return "B" + layer[1:]
    if layer[:2] in ("B.", "B&"):
        return "F" + layer[1:]
    return layer


def _instance_pad(pad: Pad, *, bottom: bool) -> Pad:
    """A library pad in the pad frame of a footprint instance on its side, computed exactly: on the bottom
    side the position is mirrored about the footprint's X axis, the angle negated and the layers are those
    of the other side (the inverse of ``lower._library_pad``)."""
    if not bottom:
        return pad
    return dataclasses.replace(
        pad,
        position=Point(pad.position.x, -pad.position.y),
        rotation=(-pad.rotation) % FULL_TURN,
        layers=tuple(_other_side(layer) for layer in pad.layers),
    )


def _instance_graphic(graphic: Graphic, *, bottom: bool) -> Graphic:
    """A library graphic in the pad frame of an instance on its side (the inverse of
    ``lower._library_graphic``)."""
    if not bottom:
        return graphic
    return dataclasses.replace(
        graphic,
        points=tuple(Point(p.x, -p.y) for p in graphic.points),
        layer=_other_side(graphic.layer),
    )


def place_footprints(
    design: Design,
    footprints: Mapping[str, pcblib.LibFootprint],
    placements: Mapping[str, PlacementRequest],
    *,
    name: str,
) -> tuple[Design, list[Issue]]:
    """``design`` with one footprint instance on its board per component with a footprint link, in the
    order of the component paths (capability altium-build, "Altium build through the lowering"; change
    c0126), and the infos of the placing. ``design.board`` holds an outline, every link is in
    ``footprints``, and ``name`` is the stem of the written files.

    An instance is placed where ``placements`` says, or staged right of the outline with one
    ``altium.pcb-staged`` info, as the KiCad build stages it. It holds the pads and graphics that
    ``pcblib.check_footprint`` keeps of the library definition, in the pad frame (``_instance_pad``,
    ``_instance_graphic``), with ids derived from the component's id; a rounded pad holds the corner ratio
    that is written, ``PPM_PER_PERCENT`` times ``pcbrecords.corner_percent(ratio)``, and every pad the id of
    the net of its pin through the pin-to-pad map (``altium_copper.pad_net_names``). The component bodies
    of the model's footprints of the component are kept. A comment outside 7-bit ASCII gives one
    ``altium.not-lowered`` info (``lower.written_comment``)."""
    board = design.board
    assert board is not None and board.outline is not None
    issues: list[Issue] = []
    nets = altium_copper.pad_net_names(design)
    net_ids = {net.name: net.id for net in design.circuit.nets}
    outline = board.outline.points
    cursor = max(p.x for p in outline) + STAGING_OFFSET
    top = min(p.y for p in outline)
    staged: list[str] = []
    wide: list[str] = []
    placed: list[FootprintInstance] = []
    for component in sorted(design.circuit.components, key=component_path):
        link = component.lib_footprint_ref
        if not link:
            continue
        footprint = footprints[link]
        request = placements.get(component_path(component))
        if request is None:
            box = footprint_extent(footprint.defn)
            at, rotation, side, locked = Point(cursor - box.x0, top - box.y0), 0, "top", False
            cursor += (box.x1 - box.x0) + STAGING_GAP
            staged.append(component.ref)
        else:
            at, rotation, side, locked = request.at, request.rotation, request.side, request.locked
        if lower.written_comment(component)[1]:
            # the PCB document's texts are 7-bit; the schematic holds the comment (change c0086)
            wide.append(component.ref)
        bottom = side == "bottom"
        check = pcblib.check_footprint(footprint.defn, footprint.extras, texts=footprint.texts)
        by_pad = nets.get(component.id, {})
        pads: list[Pad] = []
        for index, pad in enumerate(check.pads):
            ratio = footprint.extras.get(pad.id, pcblib.PadExtras()).corner_ratio
            corner = None
            if pad.shape == "roundrect" and ratio is not None:
                corner = PPM_PER_PERCENT * pcbrecords.corner_percent(ratio)
            net = by_pad.get(pad.number)
            pads.append(
                dataclasses.replace(
                    _instance_pad(pad, bottom=bottom),
                    id=derived_id("pad", TARGET, f"placed:{component.id}:{index}"),
                    native_ids={},
                    provenance=None,
                    net_id=net_ids.get(net) if net is not None else None,
                    corner_ratio=corner,
                )
            )
        graphics = tuple(
            dataclasses.replace(
                _instance_graphic(graphic, bottom=bottom),
                id=derived_id("gfx", TARGET, f"placed:{component.id}:gfx:{index}"),
                native_ids={},
                provenance=None,
            )
            for index, graphic in enumerate(check.graphics)
        )
        bodies = tuple(
            body for fp in board.footprints if fp.component_id == component.id for body in fp.bodies
        )
        placed.append(
            FootprintInstance(
                id=derived_id("fp", TARGET, f"placed:{component.id}"),
                component_id=component.id,
                lib_ref=link,
                position=at,
                rotation=rotation,
                side=side,  # type: ignore[arg-type]
                locked=locked,
                pads=tuple(pads),
                bodies=bodies,
                graphics=graphics,
            )
        )
    if wide:
        issues.append(
            issue(
                "altium.not-lowered",
                f"the comments of {', '.join(wide)} hold characters outside 7-bit ASCII and are kept in the "
                f"schematic only; {name}.PcbDoc holds the symbol name as their comment",
                "pcb-comments",
            )
        )
    if staged:
        issues.append(
            issue(
                "altium.pcb-staged",
                f"{', '.join(staged)} not placed: staged right of the board outline in {name}.PcbDoc",
                f"{name}.PcbDoc",
                "place the parts in the script, or move them in Altium",
            )
        )
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=tuple(placed))), issues


def _with_plan_copper(design: Design, plan: altium_copper.CopperPlan) -> Design:
    """``design`` whose board holds the copper of ``plan`` (tracks, arcs, vias and zones that the lens
    checked; their ``net_id`` holds a net's name) with the net ids of the design (change c0126): the
    lowering writes it as the copper of any model."""
    board = design.board
    assert board is not None
    ids = {net.name: net.id for net in design.circuit.nets}

    def net(name: str | None) -> str | None:
        return ids.get(name) if name is not None else None

    return dataclasses.replace(
        design,
        board=dataclasses.replace(
            board,
            tracks=tuple(dataclasses.replace(item, net_id=net(item.net_id)) for item in plan.tracks),
            arcs=tuple(dataclasses.replace(item, net_id=net(item.net_id)) for item in plan.arcs),
            vias=tuple(dataclasses.replace(item, net_id=net(item.net_id)) for item in plan.vias),
            zones=tuple(dataclasses.replace(item, net_id=net(item.net_id)) for item in plan.zones),
        ),
    )


def _plan_planes(plan: altium_copper.CopperPlan) -> dict[str, str]:
    """The planes of ``plan``: inner layer name → net name, in stack order."""
    if plan.stack is None:
        return {}
    layers = [
        layer
        for layer, ident in zip(plan.layers, plan.stack.copper, strict=True)
        if ident >= pcbrecords.FIRST_PLANE
    ]
    return dict(zip(layers, plan.stack.plane_nets, strict=True))


def lowered_pcb(
    design: Design,
    *,
    name: str,
    footprints: Mapping[str, pcblib.LibFootprint],
    placements: Mapping[str, PlacementRequest],
    sheets: project.SheetMode = project.DEFAULT_SHEETS,
    copper: int = 2,
    planes: Mapping[str, str] | None = None,
    copper_source: altium_copper.CopperSource | None = None,
    account: dict[str, dict[str, int]] | None = None,
    bodies: pcbdoc.BodyMode = "off",
    body_form: pcbrecords.BodyForm = "saved",
) -> tuple[pcbdoc.PcbDocSpec | None, list[Issue]]:
    """The PCB document of ``design`` through the lowering (capability altium-build, "Altium build through
    the lowering"; change c0126), or ``None`` with one ``altium.pcbdoc-not-written`` info naming the
    reason (change c0035, "PCB document output").

    The lens decides whether a document is planned, matches a copper source, places the footprints
    (``place_footprints``), lowers and checks the copper (``altium_copper.lower_copper``: copper that cannot
    be written gives its errors and ``None``) and puts it into the model's board; ``lower.from_design``
    with ``lower.LowerOptions`` then gives the specification. In the ``modules`` sheet mode (change c0037)
    a component on a module sheet links through the sheet symbol of its module. ``account`` (change
    c0085), when given, receives ``written`` and ``not_lowered`` of ``altium_copper.account``. ``bodies``
    (change c0121) is ``off`` or ``extruded``: with ``extruded`` the extruded component bodies of the
    board's footprints are written in the form ``body_form``, and ``altium_copper.lower_bodies`` reports
    every other body."""
    issues: list[Issue] = []
    board = design.board
    reason = ""
    concerned: list[str] = []
    components = sorted(design.circuit.components, key=component_path)
    with_links = [c for c in components if c.lib_footprint_ref]
    if board is None or board.outline is None or len(board.outline.points) < 3:
        reason = "the design has no board outline"
    elif board.outline.cutouts:
        reason = "the board outline has cutouts, which the document does not write"
    else:
        altium = [c.ref for c in with_links if footprint_source(c.lib_footprint_ref) == "altium"]
        missing = [
            c.ref
            for c in with_links
            if footprint_source(c.lib_footprint_ref) == "kicad" and c.lib_footprint_ref not in footprints
        ]
        if altium:
            reason, concerned = (
                "components link Altium footprint libraries, whose footprints Fenolite does not have",
                altium,
            )
        elif missing:
            reason, concerned = "the footprints of some components are not written", missing
        elif not with_links:
            reason = "no component has a footprint"
    if reason:
        names = f" ({', '.join(concerned)})" if concerned else ""
        issues.append(
            issue(
                "altium.pcbdoc-not-written",
                f"{name}.PcbDoc is not written: {reason}{names}",
                f"{name}.PcbDoc",
                "Altium's change order places the parts from the PCB library",
            )
        )
        if copper_source is not None:
            message = (
                f"{copper_source.label}the copper cannot be written: {name}.PcbDoc is not planned ({reason})"
            )
            issues.append(altium_copper.issue("altium.copper-no-document", message, f"{name}.PcbDoc"))
        return None, issues
    if copper_source is not None:
        placements, source_issues = altium_copper.match_source(
            design, copper_source, footprints, requested=placements
        )
        issues += source_issues
        issues += altium_copper.source_not_lowered(copper_source)
        if any(found.severity == "error" for found in source_issues):
            return None, issues
    placed, place_issues = place_footprints(design, footprints, placements, name=name)
    issues += place_issues
    plan = altium_copper.lower_copper(
        design, copper=copper, planes=planes, source=copper_source, document=f"{name}.PcbDoc"
    )
    issues += plan.issues
    if plan.failed:
        return None, issues
    options = lower.LowerOptions(
        name=name,
        library=footprints,
        sheets=sheets,
        copper=plan.layers,
        planes=_plan_planes(plan),
        body_form=body_form,
    )
    # what the lowering counts is the lens's to report: it checked the copper, the rules and the items
    inputs = lower.from_design(_with_plan_copper(placed, plan), issues=[], options=options, bodies=bodies)
    spec = inputs.pcb
    assert spec is not None
    _placed_bodies, body_counts = altium_copper.lower_bodies(design, spec, bodies, issues)
    plan = dataclasses.replace(plan, counts=MappingProxyType({**plan.counts, "body": body_counts}))
    if account is not None:
        source = copper_source.design if copper_source is not None else None
        account.update(altium_copper.account(design, spec, plan, source))
    return spec, issues


UNMODELLED_GRAPHICS: tuple[str, ...] = ("arc", "bezier", "text", "text_box")
"""The graphic nodes of a KiCad library symbol that ``SymbolGraphic`` does not hold (change c0086)."""


def unmodelled_graphics(symbol: SymbolDef) -> tuple[str, ...]:
    """The kinds of ``UNMODELLED_GRAPHICS`` that the library text of ``symbol`` holds, sorted: the model
    keeps a sub-symbol's text beside its ``graphics``, so a symbol with an arc is known to be drawn
    incompletely by them. A symbol that was not read from a KiCad library holds none."""
    found: set[str] = set()
    for node in _opaque_nodes(symbol):
        if node.name == "symbol":
            found |= {child.name for child in node.nodes() if child.name in UNMODELLED_GRAPHICS}
    return tuple(sorted(found))


def library_symbols(
    symbols: Mapping[str, SymbolDef], issues: list[Issue], bodies: SymbolBodies = DEFAULT_BODIES
) -> dict[str, AltiumSymbol]:
    """Lib id → the Altium symbol of every resolved KiCad symbol, drawn from its own graphics where
    ``altsym.from_symbol_def`` can (change c0086); an off-grid pin gives ``altium.symbol-off-grid`` and no
    symbol."""
    mapped: dict[str, AltiumSymbol] = {}
    for lib_id, symbol in sorted(symbols.items()):
        link = split_link(lib_id)
        assert link is not None
        footprint = split_link(symbol.footprint) if symbol.footprint else None
        try:
            mapped[lib_id] = from_symbol_def(
                symbol,
                lib_ref=link[1],
                footprint=footprint,
                issues=issues,
                unmodelled=unmodelled_graphics(symbol),
                bodies=bodies,
            )
        except ValueError as error:
            issues.append(
                issue(
                    "altium.symbol-off-grid",
                    f"{error}; Altium library pins lie on the 10-mil grid",
                    lib_id,
                    "move the pin onto a 10-mil grid (KiCad's 50-mil grid is on it)",
                )
            )
    return mapped


def _library_checks(
    model: Design,
    name: str,
    symbols: Mapping[str, AltiumSymbol],
    project_exists: bool,
    listed: Collection[str] | None = None,
    unread_hint: str = "",
) -> list[Issue]:
    """The checks of the planned libraries (change c0034): texts and lengths of KiCad symbols, storage
    and file name collisions, section keys, generic stand-in libraries and libraries a kept project file
    does not list."""
    found: list[Issue] = []
    for lib_id, symbol in sorted(symbols.items()):
        if symbol.description:
            _unwritable(found, symbol.description, f"{lib_id} description", lib_id)
        for pin in symbol.pins:
            where = f"{lib_id} pin {pin.designator[:20]}"
            too_long = [t for t in (pin.name, pin.designator) if len(t.encode("utf-8")) > MAX_PIN_TEXT]
            if too_long:
                found.append(
                    issue(
                        "altium.pin-text-too-long",
                        f"{where}: a pin text of {len(too_long[0].encode('utf-8'))} bytes is longer than "
                        f"{MAX_PIN_TEXT} bytes, which needs the PinWideText stream Fenolite does not write",
                        lib_id,
                    )
                )
                continue
            _unwritable(found, pin.designator, f"{where} number", lib_id)
            if pin.name:
                _unwritable(found, pin.name, f"{where} name", lib_id)
    libraries = project.library_symbols(model, name=name, symbols=symbols)
    _case_collision_of_files(found, list(libraries))
    for library, members in libraries.items():
        keys: dict[tuple[int, tuple[int, ...]], str] = {}
        for symbol in members:
            try:
                key_name = schlib.storage_name(symbol.lib_ref)
            except ValueError:
                found.append(
                    issue(
                        "altium.text-unwritable",
                        f"{library}: the lib ref {symbol.lib_ref!r} holds \\, : or !, which no storage name "
                        "may hold",
                        library,
                    )
                )
                continue
            key = name_key(key_name)
            other = keys.get(key)
            if other is not None:
                found.append(
                    issue(
                        "altium.symbol-name-collision",
                        f"{library}: the symbols {other!r} and {symbol.lib_ref!r} get one storage name "
                        f"{key_name!r}",
                        library,
                        "rename one of the symbols; lib ids of one library need distinct names",
                    )
                )
                continue
            keys[key] = symbol.lib_ref
            if key_name != symbol.lib_ref:
                found.append(
                    issue(
                        "altium.section-key",
                        f"{library}: {symbol.lib_ref!r} is longer than 31 characters and is stored under "
                        f"the section key {key_name!r}",
                        library,
                    )
                )
    generic = sorted(
        library
        for library in libraries
        if any(
            project.is_altium_link(c.lib_symbol_ref)
            and project.schlib_name(c.lib_symbol_ref, design=name) == library
            for c in model.circuit.components
        )
    )
    for library in generic:
        found.append(
            issue(
                "altium.schlib-generic",
                f"{library} is written with generic symbols; it stands in for a real library of the same "
                "name, which it does not copy",
                library,
                "keep the real library elsewhere; Fenolite refuses to overwrite an edited library in --out",
            )
        )
    unlisted = not_listed(list(libraries), listed) if project_exists else []
    if unlisted:
        found.append(
            issue(
                "altium.schlib-not-in-project",
                f"the kept {name}.PrjPcb does not list {', '.join(unlisted)}; add them in Altium "
                "(Project » Add Existing to Project)",
                f"{name}.PrjPcb",
                unread_hint,
            )
        )
    return found


def _case_collision_of_files(issues: list[Issue], names: Sequence[str]) -> None:
    seen: dict[str, str] = {}
    for library in sorted(names):
        other = seen.get(library.lower())
        if other is not None:
            issues.append(
                issue(
                    "altium.symbol-name-collision",
                    f"the library files {other!r} and {library!r} differ only in letter case",
                    library,
                    "name one library file the same way in every lib id",
                )
            )
        seen.setdefault(library.lower(), library)


def _unwritable(
    issues: list[Issue],
    text: str,
    what: str,
    where: str,
    *,
    parameter: bool = False,
    form: project.SchematicForm = "ascii",
) -> None:
    """``altium.text-unwritable`` when ``text`` cannot be written. ``form`` is ``"binary"`` only for a
    text that the binary form carries with its ``%UTF8%`` twin, a comment or a parameter value of a build
    in that form (change c0086, "Text outside ASCII"); every other text is 7-bit."""
    problem = text_problem(text, form=form, parameter=parameter)
    if problem is not None:
        allowed = "Windows-1252 text" if form == "binary" else "printable 7-bit ASCII"
        issues.append(
            issue(
                "altium.text-unwritable",
                f"{what} {text!r} {problem}",
                where,
                f"use {allowed} without '|', without surrounding spaces"
                + (" and not starting with '='" if parameter else ""),
            )
        )


def _case_collisions(issues: list[Issue], what: str, names: Sequence[str]) -> None:
    seen: dict[str, str] = {}
    for name in sorted(set(names)):
        other = seen.get(name.lower())
        if other is not None:
            issues.append(
                issue(
                    "altium.name-case-collision",
                    f"{what} names {other!r} and {name!r} differ only in letter case",
                    name,
                )
            )
        else:
            seen[name.lower()] = name


def _check(
    design: Design,
    name: str,
    placed: Sequence[str],
    sheets: project.SheetMode = project.DEFAULT_SHEETS,
    form: project.SchematicForm = project.DEFAULT_FORM,
) -> list[Issue]:
    """The build checks of the closed table, before any pin is set."""
    issues: list[Issue] = []
    _unwritable(issues, name, "design name", name)
    components = sorted(design.circuit.components, key=component_path)
    by_id = {c.id: c for c in components}
    skipped: list[str] = []
    for component in components:
        path, ref = component_path(component), component.ref
        _unwritable(issues, ref, "ref", path)
        link = split_link(component.lib_symbol_ref)
        if link is None:
            issues.append(
                issue(
                    "altium.lib-id-form",
                    f"{ref}: lib_id {component.lib_symbol_ref!r} is not <library>:<name>",
                    path,
                    "name the schematic library file and the symbol, e.g. 'MyParts.SchLib:RES'",
                )
            )
        else:
            _unwritable(issues, link[0], f"{ref} symbol library", path)
            _unwritable(issues, link[1], f"{ref} symbol name", path)
            comment = component.value or link[1]
            _unwritable(issues, comment, f"{ref} comment", path, parameter=True, form=form)
        skipped += [f"{ref} {key!r} ({why})" for key, why in project.parameters_of(component, form=form)[1]]
        footprint = component.lib_footprint_ref
        if not footprint:
            issues.append(
                issue(
                    "altium.no-footprint",
                    f"{ref} names no footprint; the engineering change order cannot place it",
                    path,
                    "give the part footprint='<library>.PcbLib:<name>'",
                )
            )
        elif (fp_link := split_link(footprint)) is None:
            issues.append(
                issue(
                    "altium.footprint-form",
                    f"{ref}: footprint {footprint!r} is not <library>:<name>",
                    path,
                    "name the PCB library file and the footprint, e.g. 'MyParts.PcbLib:R0603'",
                )
            )
        else:
            _unwritable(issues, fp_link[0], f"{ref} footprint library", path)
            _unwritable(issues, fp_link[1], f"{ref} footprint name", path)
            for _pin, pad in component.pin_pad_map:
                _unwritable(issues, pad, f"{ref} pad name", path)  # written into the map records
    for net in sorted(design.circuit.nets, key=lambda n: n.name):
        _unwritable(issues, net.name, "net name", net.name)
        for member in net.members:
            component = by_id.get(member.component_id)
            ref = component.ref if component is not None else member.component_id
            _unwritable(issues, member.pin, f"{ref} pin designator", net.name)
    for mark in design.circuit.no_connects:
        component = by_id.get(mark.component_id)
        ref = component.ref if component is not None else mark.component_id
        where = component_path(component) if component is not None else mark.component_id
        _unwritable(issues, mark.pin, f"{ref} pin designator", where)
    for item in sorted(design.circuit.netclasses, key=lambda c: c.name):
        # the schematic holds the name as the text of a ClassName parameter (change c0048)
        _unwritable(issues, item.name, "net class name", item.name, parameter=True)
    _case_collisions(issues, "net", [n.name for n in design.circuit.nets])
    _case_collisions(issues, "ref", [c.ref for c in components])
    if skipped:
        message = (
            f"the properties {'; '.join(skipped)} are kept in the model only: no parameter can hold them"
        )
        issues.append(issue("altium.not-lowered", message, "parameters"))
    for bus, reason in project.lowered_buses(design)[1]:
        message = f"the bus {bus} is drawn as its nets: {reason}"
        hint = "name its nets <stem><n> with consecutive integers to draw it as a bus"
        issues.append(issue("altium.bus-flattened", message, bus, hint))
    issues += _hierarchy_checks(design)
    ids: dict[str, str] = {}
    keyed = [(c.id, c.ref, component_path(c)) for c in components]
    if not any(i.severity == "error" for i in issues):
        for module, found in hierarchy.crossings(design, form=form).items():
            keyed.append((hierarchy.symbol_key(module), f"the sheet symbol {module}", module))
            keyed += [
                (hierarchy.port_key(module, c.name), f"the port {c.name} of {module}", module) for c in found
            ]
    for key, what, where in keyed:
        uid = unique_id(key)
        other = ids.get(uid)
        if other is not None:
            issues.append(
                issue("altium.unique-id-collision", f"{other} and {what} get the same unique id {uid}", where)
            )
        ids.setdefault(uid, what)
    issues += _not_lowered(design, placed, sheets, form)
    return issues


def _hierarchy_checks(design: Design) -> list[Issue]:
    """The checks of "Hierarchy issue codes" (change c0037), reported in both sheet modes so a design is
    refused before its mode is switched: module names whose sheet files would collide, harness names a
    definition file cannot hold, a net in two harnesses, and a power net in a harness."""
    found: list[Issue] = []
    seen: dict[str, str] = {}
    for module in hierarchy.sheet_tree(design):
        _unwritable(found, module, "module name", module)
        # the sheet file is named by the module path with "." between its segments (change c0086)
        other = seen.setdefault(hierarchy.sheet_stem(module).lower(), module)
        if other != module:
            message = (
                f"the modules {other!r} and {module!r} give one sheet file name, or names that differ only "
                "in letter case, so their sheet files would collide"
            )
            found.append(issue("altium.sheet-name-collision", message, module, "rename one of the modules"))
    names = {net.id: net.name for net in design.circuit.nets}
    net_names = {net.name.lower(): net.name for net in design.circuit.nets}
    power = set(project.power_styles(design))
    types: dict[str, str] = {}
    owners: dict[str, list[str]] = {}
    for interface in hierarchy.harness_interfaces(design):
        kind = interface.name
        _harness_text(found, kind, "harness type name", kind)
        other = types.setdefault(kind.lower(), kind)
        if other != kind:
            message = f"the harness type names {other!r} and {kind!r} differ only in letter case"
            found.append(issue("altium.harness-name", message, kind))
        net = net_names.get(kind.lower())
        if net is not None:
            message = (
                f"the harness type name {kind!r} equals the net name {net!r}; a port and a sheet entry are "
                "named after each"
            )
            found.append(issue("altium.harness-name", message, kind, "rename the harness or the net"))
        entries: dict[str, str] = {}
        for entry, net_id in sorted(interface.members.items()):
            _harness_text(found, entry, f"harness {kind} entry name", kind)
            before = entries.setdefault(entry.lower(), entry)
            if before != entry:
                message = (
                    f"harness {kind}: the entry names {before!r} and {entry!r} differ only in letter case"
                )
                found.append(issue("altium.harness-name", message, kind))
            owners.setdefault(net_id, []).append(kind)
            if net_id in power:
                message = (
                    f"harness {kind}: the entry {entry} is on {names.get(net_id, net_id)}, a net of a power "
                    "interface; power nets join through global power ports and travel in no harness"
                )
                hint = "take the net out of the harness"
                found.append(issue("altium.harness-power-net", message, kind, hint))
    for net_id, kinds in sorted(owners.items(), key=lambda item: names.get(item[0], item[0])):
        if len(kinds) > 1:
            net = names.get(net_id, net_id)
            where = " and ".join(dict.fromkeys(kinds))
            twice = "twice in the harness" if len(set(kinds)) == 1 else "in the harnesses"
            message = f"the net {net} is {twice} {where}; a net travels in one harness entry"
            hint = "keep the net in one harness, under one entry"
            found.append(issue("altium.harness-net-shared", message, net, hint))
    return found


def _harness_text(issues: list[Issue], text: str, what: str, where: str) -> None:
    """A harness type or entry name: ``altium.text-unwritable`` when no record can hold it, else
    ``altium.harness-name`` when it holds a separator of the harness definition file."""
    if text_problem(text) is not None:
        _unwritable(issues, text, what, where)
    elif any(separator in text for separator in hierarchy.HARNESS_SEPARATORS):
        message = (
            f"{what} {text!r} holds '=', ',' or ';', which separate the fields of a harness definition file"
        )
        issues.append(issue("altium.harness-name", message, where, "use a name without '=', ',' and ';'"))


def lowered_harnesses(design: Design, sheets: project.SheetMode, form: project.SchematicForm) -> set[str]:
    """The names of the ``harness`` interfaces the build draws: those that cross a module, in the
    ``modules`` mode and the binary form (change c0037)."""
    if sheets != "modules" or form != "binary":
        return set()
    found = hierarchy.crossings(design, form=form)
    return {c.name for module in found.values() for c in module if c.harness}


def _not_lowered(
    design: Design,
    placed: Sequence[str],
    sheets: project.SheetMode = project.DEFAULT_SHEETS,
    form: project.SchematicForm = project.DEFAULT_FORM,
) -> list[Issue]:
    """One info per kind of design item the Altium files have no place for."""
    found: list[Issue] = []
    if design.board is not None and design.board.outline is not None:
        found.append(issue("altium.not-lowered", "the board outline is kept in the model only", "board"))
    if placed:
        found.append(
            issue(
                "altium.not-lowered",
                f"placements of {', '.join(placed)} are kept in the model only; "
                "Altium's change order places the parts",
                "placements",
            )
        )
    classes = sorted(c.name for c in design.circuit.netclasses)
    if classes:
        message = (
            f"the rule values of the net classes {', '.join(classes)} are kept in the model only; the "
            "schematic declares their nets"
        )
        found.append(issue("altium.not-lowered", message, "rules"))
    found += altium_copper.board_not_lowered(design.board)
    kept = sorted((i.name, i.kind) for i in design.circuit.interfaces if i.kind in MODEL_ONLY_INTERFACES)
    if kept:
        if all(kind == "diff_pair" for _, kind in kept):
            message = f"diff pairs {', '.join(name for name, _ in kept)} are kept in the model only"
        else:  # change c0073: the typed buses are named with their kind
            named = ", ".join(f"{name} ({kind})" for name, kind in kept)
            message = f"interfaces {named} are kept in the model only; their nets are written as plain nets"
        found.append(issue("altium.not-lowered", message, "interfaces"))
    drawn = lowered_harnesses(design, sheets, form)
    harnesses = [i.name for i in hierarchy.harness_interfaces(design) if i.name not in drawn]
    if harnesses:
        if sheets != "modules":
            why, hint = "the schematic is one sheet", "build with --altium-sheets modules to draw them"
        elif form != "binary":
            why, hint = "the ASCII form writes no harness", "build with --altium-format binary to draw them"
        else:
            why, hint = "none of their nets leaves a module's sheet", ""
        message = (
            f"harnesses {', '.join(harnesses)} are kept in the model only ({why}); their nets are written "
            "as plain nets"
        )
        found.append(issue("altium.not-lowered", message, "harnesses", hint))
    return found


SHEET_PARAMETERS: tuple[tuple[str, str], ...] = (
    ("title", "Title"),
    ("revision", "Revision"),
    ("date", "Date"),
    ("organization", "Organization"),
    ("doc_id", "DocumentNumber"),
    ("responsible", "DrawnBy"),
    ("approver", "ApprovedBy"),
)
"""Title-block field → the sheet parameter that holds it (change c0087): the special strings of
``schdot.SPECIAL_STRINGS``."""
SHEET_NUMBER, SHEET_TOTAL = "SheetNumber", "SheetTotal"
GROWN_PAPERS: tuple[str, ...] = ("A4", "A3", "A2", "A1", "A0")
"""The papers a drawing sheet grows to when the layout does not fit the paper of ``sheet()``."""
SHOWN_PAPERS = frozenset({"A0", "A1", "A2", "A3", "A4", "A5"})
"""The paper names shown as they are; any other page shows ``User``, as KiCad does."""
NM_PER_MIL = 25_400


def sheet_page(ref: SheetFrameRef | None, area: tuple[int, int]) -> tuple[str, int, int, bool]:
    """The page of a schematic document whose layout takes ``area`` (width, height in nm): its shown paper
    name, its width and height, and whether it is another page than ``ref`` asks for. The page is the
    paper of ``sheet()`` (A4 landscape without one) when the layout fits it, otherwise the smallest of
    ``GROWN_PAPERS`` in that orientation that holds the layout, otherwise the layout's own area."""
    ref = ref or SheetFrameRef()

    def oriented(paper: str) -> tuple[int, int]:
        short, long = PAPER_SIZES[paper]
        return (short, long) if ref.portrait else (long, short)

    def fits(size: tuple[int, int]) -> bool:
        return area[0] <= size[0] and area[1] <= size[1]

    if ref.paper == "custom" and ref.width is not None and ref.height is not None:
        wanted, shown = (ref.width, ref.height), "User"
    else:
        wanted = oriented(ref.paper if ref.paper in PAPER_SIZES else "A4")
        shown = ref.paper if ref.paper in SHOWN_PAPERS else "User"
    if fits(wanted):
        return shown, wanted[0], wanted[1], False
    for paper in GROWN_PAPERS:
        if fits(oriented(paper)):
            return paper, *oriented(paper), True
    return "User", area[0], area[1], True


def sheet_parameters(
    block: TitleBlock | None, number: int, total: int, issues: list[Issue]
) -> list[tuple[str, str]]:
    """The sheet parameters of schematic document ``number`` of ``total`` (change c0087): the fields of the
    title block that are not empty, the sheet number and count, and the variables in code-point order. A
    value a record cannot hold, and a variable with the name of a written parameter, give
    ``altium.text-unwritable``."""
    block = block or TitleBlock()
    found = [(name, getattr(block, field)) for field, name in SHEET_PARAMETERS if getattr(block, field)]
    found += [(SHEET_NUMBER, str(number)), (SHEET_TOTAL, str(total))]
    taken = {name.casefold() for _field, name in SHEET_PARAMETERS} | {
        SHEET_NUMBER.casefold(),
        SHEET_TOTAL.casefold(),
    }
    for name, value in sorted(block.params.items()):
        if name.casefold() in taken:
            issues.append(
                issue(
                    "altium.text-unwritable",
                    f"the title-block variable {name} has the name of a sheet parameter the build writes",
                    "title_block",
                    "rename the variable",
                )
            )
        elif value:
            found.append((name, value))
        taken.add(name.casefold())
    for name, value in found:
        problem = text_problem(value, parameter=True)
        if problem is not None:
            issues.append(
                issue(
                    "altium.text-unwritable",
                    f"the sheet parameter {name} {value!r} {problem}",
                    "title_block",
                )
            )
    return found


def sheet_frames(
    design: Design,
    planned: ProjectSheets,
    drawing_sheet: DrawingSheet,
    issues: list[Issue],
    *,
    allow_lossy: bool = False,
) -> tuple[dict[str, schdot.SheetFrame], dict[str, object]]:
    """The drawing sheet of every planned schematic document (change c0087, "Drawing sheet in an Altium
    build"): sheet file → its ``schdot.SheetFrame``, and ``summary["drawing_sheet"]``. The issues of the
    sheet writer are reported once, for the first document; ``schdot`` raises ``SheetLossError`` for a
    loss without ``allow_lossy``. With an error among ``issues`` no frame is returned."""
    board = design.board
    ref = board.sheet if board is not None else None
    block = board.title_block if board is not None else None
    wanted = sheet_page(ref, (0, 0))
    frames: dict[str, schdot.SheetFrame] = {}
    pages: list[dict[str, object]] = []
    total = len(planned.sheets)
    before = len(issues)
    for number, sheet in enumerate(planned.sheets, start=1):
        size = sheet.plan.size
        shown, width, height, other = sheet_page(ref, (size.width * NM_PER_MIL, size.height * NM_PER_MIL))
        if other:
            issues.append(
                issue(
                    "altium.sheet-paper",
                    f"the layout of {sheet.file} ({size.width} x {size.height} mil) does not fit the "
                    f"{wanted[0]} page of sheet() ({wanted[1]} x {wanted[2]} nm); the drawing sheet is "
                    f"drawn on a {shown} page of {width} x {height} nm",
                    sheet.file,
                    "name a larger paper in sheet(), or split the design into module sheets",
                )
            )
        parameters = sheet_parameters(block, number, total, issues if number == 1 else [])
        if any(found.severity == "error" for found in issues[before:]):
            return {}, {}
        made = schdot.sheet_frame(
            drawing_sheet,
            width=width,
            height=height,
            paper=shown,
            parameters=parameters,
            allow_lossy=allow_lossy,
        )
        if number == 1:
            for found in made.issues:
                where = f"drawing_sheet.{found.where}" if found.where else "drawing_sheet"
                issues.append(dataclasses.replace(found, where=where))
        frames[sheet.file] = made.frame
        pages.append({"file": sheet.file, "paper": shown, "width": width, "height": height})
    return frames, {"items": len(drawing_sheet.items), "pages": pages}


def _gerber_summary(groups: Sequence[OutputGroup]) -> dict[str, object] | None:
    """``summary["outjob"]["gerber"]`` (change c0138), read from the record the job holds: the unit, the
    decimals, the plotted layers in the order of ``Plot.Set`` by long id and name, and ``outline``, which
    says that the set holds no plot of the board outline and why. ``None`` for a job without a Gerber
    record."""
    setting = job_writer.gerber_setting(groups)
    if setting is None:
        return None
    fields = dict(record_fields(setting.item))
    plotted = job_writer.plotted_layers(setting.item)
    return {
        "unit": fields["GerberUnit"],
        "decimals": int(fields["NumberOfDecimals"]),
        "layers": [{"id": layer, "name": job_writer.layer_name(layer)} for layer in plotted],
        "outline": {"plotted": False, "reason": job_writer.OUTLINE_REASON},
    }


def outjob_summary(name: str, groups: Sequence[OutputGroup], defaults: Sequence[str]) -> dict[str, object]:
    """``summary["outjob"]`` (changes c0087 and c0138): the job's file, its containers, its outputs, what
    its Gerber record holds (``gerber``) and the options of the preset that it does not carry."""
    media = [medium for group in groups for medium in group.media]
    names = {medium.index: medium.name for medium in media}
    return {
        "file": f"{name}.OutJob",
        "media": [{"name": medium.name, "type": medium.type} for medium in media],
        "outputs": [
            {
                "kind": job_writer.kind_of(output),
                "type": output.type,
                "name": output.name,
                "category": output.category,
                "document": output.document_path,
                "enabled": output.enabled,
                "medium": names[output.enabled_media[0]] if output.enabled_media else None,
            }
            for group in groups
            for output in group.outputs
        ],
        "gerber": _gerber_summary(groups),
        "defaults": list(defaults),
    }


def _summary(
    design: Design,
    kept: Sequence[str],
    planned: ProjectSheets | None,
    form: project.SchematicForm,
    libraries: Mapping[str, Sequence[AltiumSymbol]] | None = None,
    footprints: int = 0,
    pcb_document: str | None = None,
    pcb_library: str = "",
    sheets: project.SheetMode = project.DEFAULT_SHEETS,
    copper: Mapping[str, object] | None = None,
    pcb: Mapping[str, object] | None = None,
    outjob: Mapping[str, object] | None = None,
    drawing_sheet: Mapping[str, object] | None = None,
    rules: Mapping[str, object] | None = None,
    directions: bool = True,
    symbol_bodies: SymbolBodies = DEFAULT_BODIES,
) -> dict[str, object]:
    """The lens summary. ``labels`` and ``power_ports`` count what every sheet holds, the labels of sheet
    entries, ports and harness entries included; ``ports``, ``sheet_entries`` and ``harnesses`` (the harness
    types drawn) are 0 on a single sheet (change c0037). ``schematic`` (change c0086) counts the sheets,
    the library symbols drawn from their own graphics and those drawn as rectangles, the bus blocks, the
    hidden parameters and the ports and sheet entries that carry a direction; it is ``None`` for a refused
    build."""
    plans = [sheet.plan for sheet in planned.sheets] if planned is not None else []
    labels = sum(1 for plan in plans for s in (*plan.links, *plan.stubs) if s.net.kind == "label")
    ports = sum(1 for plan in plans for s in plan.stubs if s.net.kind == "port")
    members = [symbol for symbols in (libraries or {}).values() for symbol in symbols]
    crossed = [
        item.crossing
        for plan in plans
        for item in (*(e for symbol in plan.symbols for e in symbol.entries), *plan.ports)
    ]
    schematic: dict[str, object] | None = None
    if planned is not None:
        schematic = {
            "sheets": len(plans),
            "symbols": symbol_bodies,
            "symbols_drawn": sum(1 for symbol in members if symbol.drawn),
            "symbols_simplified": sum(1 for symbol in members if not symbol.drawn),
            "buses": sum(len(plan.bus_blocks) for plan in plans),
            "parameters": sum(
                len(part.spec.parameters) for plan in plans for part in plan.parts if part.part == 1
            ),
            "directions": "on" if directions else "off",
            "directed": sum(1 for crossing in crossed if crossing.io != "unspecified"),
        }
    found = list(libraries or {})
    if footprints:
        found = sorted([*found, pcb_library], key=name_key)
    return {
        "components": len(design.circuit.components),
        "nets": len(design.circuit.nets),
        "labels": labels,
        "power_ports": ports,
        "no_connects": sum(len(plan.no_connects) for plan in plans),
        "sheet": planned.top.plan.size.name if planned is not None else None,
        "libraries": found,
        "symbols": sum(len(symbols) for symbols in (libraries or {}).values()),
        "footprints": footprints,
        "pcb_document": pcb_document,
        "sheet_mode": sheets,
        "sheets": [sheet.file for sheet in planned.sheets] if planned is not None else [],
        "ports": sum(len(plan.ports) for plan in plans),
        "sheet_entries": sum(len(symbol.entries) for plan in plans for symbol in plan.symbols),
        "harnesses": len({block.name for plan in plans for block in plan.harnesses}),
        "schematic": schematic,
        "copper": copper,
        "pcb": pcb,
        "outjob": outjob,
        "drawing_sheet": drawing_sheet,
        "rules": rules,
        "kept": list(kept),
        "schematic_format": form,
        "experimental": True,
    }


def refused_altium(
    design: Design,
    *,
    name: str,
    issues: Sequence[Issue],
    project_exists: bool = False,
    form: project.SchematicForm = project.DEFAULT_FORM,
    sheets: project.SheetMode = project.DEFAULT_SHEETS,
) -> BuildOutput:
    """The output of an Altium build that was refused before ``build_altium`` ran (change c0053, "Script
    copper in an Altium build": the script's copper intents did not resolve): no file, ``issues`` and the
    summary of a refused build, whose ``copper`` and ``pcb_document`` are ``None``."""
    evidence = Evidence.combine(ALTIUM_BUILD_EVIDENCE, project.EVIDENCE, schlib.EVIDENCE, PCB_BUILD_EVIDENCE)
    kept = [f"{name}.PrjPcb"] if project_exists else []
    return BuildOutput(design, {}, tuple(issues), evidence, _summary(design, kept, None, form, sheets=sheets))


def build_altium(
    design: Design,
    *,
    name: str,
    placed: Sequence[str] = (),
    placements: Mapping[str, PlacementRequest] | None = None,
    project_exists: bool = False,
    form: project.SchematicForm = project.DEFAULT_FORM,
    resolver: LibraryResolver | None = None,
    sheets: project.SheetMode = project.DEFAULT_SHEETS,
    copper: int = 2,
    planes: Mapping[str, str] | None = None,
    copper_source: altium_copper.CopperSource | None = None,
    authored_footprints: Mapping[str, FootprintDef] = MappingProxyType({}),
    outjob: bool = False,
    outjob_preset: job_writer.PresetOptions | None = None,
    outjob_listed: bool = False,
    project_digest: str | None = None,
    project_listed: Collection[str] | None = None,
    project_unreadable: bool = False,
    drawing_sheet: DrawingSheet | None = None,
    allow_lossy: bool = False,
    directions: bool = True,
    authored_symbols: Mapping[str, SymbolDef] = MappingProxyType({}),
    symbol_bodies: SymbolBodies = DEFAULT_BODIES,
    bodies: str = "off",
    body_form: pcbrecords.BodyForm = "saved",
) -> BuildOutput:
    """Every file of the Altium project of ``design`` as bytes, or no file when an issue is an error.

    ``bodies`` (change c0121, ``--altium-bodies``) is ``off`` (the default: no component body is written and
    every file is the file of earlier changes) or ``extruded``: the extruded component bodies of the
    board's footprints are written into the PCB document and those of the footprint definitions into the
    PCB library; a body that names a 3D model, has no outline or no height above its standoff is reported.
    Another value raises ``ValueError``. The default stays ``off`` until step X8 of the author report is
    in: two keys of a written body are stand-ins (``H-A-PCBX-BODY-OPEN``). ``body_form`` is ``saved``;
    ``short`` exists for the second file set of that step and no command selects it.

    ``directions`` (change c0086, ``--altium-directions``) false writes every port and sheet entry
    without an I/O type. ``authored_symbols`` (change c0086) maps a lib id to a symbol the script authored
    or took from the catalog: it is written like a resolved KiCad symbol, and no library is read for it.
    ``symbol_bodies`` (change c0086, ``--altium-symbols``) is ``graphics`` (the default: a resolved symbol
    is drawn from its own graphics) or ``generic`` (one rectangle per part, the bytes of earlier changes).

    ``placed`` are the component paths the script placed; ``project_exists`` tells that
    ``<name>.PrjPcb`` already exists in the output folder, so it is kept and not planned; ``form`` is the
    form of ``<name>.SchDoc`` (``binary`` or ``ascii``). A binary schematic past the compound file's size
    limit is reported as ``altium.schematic-too-large`` and gives no file. ``resolver`` resolves the KiCad
    lib ids (change c0034); a lib id that does not resolve raises ``UnresolvedLibrariesError``. ``sheets``
    (change c0037) is ``flat`` for one sheet or ``modules`` for a top sheet with one sheet per top-level
    module, their harness definition files and a project file that lists them.
    ``copper`` is the script's copper layer count (2 or 4) and ``planes`` its internal planes (inner layer
    name → net name); the copper of ``design.board`` is written into the PCB document (change c0038), and
    copper that cannot be written exactly gives an error and no file. ``copper_source`` gives the copper
    and the placements from outside the model (the script's resolved copper, or a routed KiCad board); a
    build takes one source, so a source given with copper in ``design.board`` raises ``ValueError``.
    With ``outjob`` (change c0087) a build that writes a PCB document also writes ``<name>.OutJob``, the
    job of ``outjob.from_preset(outjob_preset, name=name, copper=<the document's stack>)`` (change
    c0138: its Gerber output holds the settings record for the layers of that board), and lists it in the
    project file;
    ``outjob_listed`` tells that a kept project file already lists it. ``project_digest`` (change c0138)
    is the SHA-256 of the existing project file when the state of the output folder records exactly it, so
    that the file is as a build wrote it, and ``None`` for a file that was changed since or has no record:
    a project file of the first kind that does not list the job is written again, as a build into an
    empty folder writes it, and is then no kept file. A kept file whose ``project_digest`` is given stays
    in the state the build writes, with that digest; a kept file that was changed or had no record is not
    in it. ``project_listed`` are the document paths the existing project file lists (``kept_documents``
    of what Fenolite's project reader read): the infos about a kept project file then name only the
    documents it really lacks, and none when it lists them all. Without it (``None``) every document is
    named, as before; ``project_unreadable`` says that the file was there and could not be read, which
    the infos then say in their hint.
    ``drawing_sheet`` is drawn on
    every schematic document, with the title block of ``design.board`` as sheet parameters; a part of
    it that the Altium form cannot carry raises ``read.sheet.SheetLossError`` unless ``allow_lossy``.
    """
    if sheets not in ("flat", "modules"):
        raise ValueError(f"unknown sheet mode {sheets!r}")
    body_mode = pcbdoc.body_mode(bodies)
    if copper_source is not None and altium_copper.has_copper(design.board):
        raise ValueError(
            "two copper sources: the design's board holds copper (the model source) and a copper source "
            f"of origin {copper_source.origin} is given; a build takes one"
        )
    evidence = Evidence.combine(ALTIUM_BUILD_EVIDENCE, project.EVIDENCE, schlib.EVIDENCE, PCB_BUILD_EVIDENCE)
    if authored_footprints:
        evidence = Evidence.combine(evidence, AUTHORED_FOOTPRINT_EVIDENCE)
    kept = [f"{name}.PrjPcb"] if project_exists else []
    unread_hint = UNREAD_PROJECT_HINT if project_exists and project_unreadable else ""
    resolved = resolve_symbols(design, resolver, authored_symbols)
    design = _with_symbol_fields(design, resolved)
    issues = _check(design, name, placed, sheets, form)
    if project_exists:
        issues.append(
            issue(
                "altium.project-kept",
                f"{name}.PrjPcb exists and is kept (Altium rewrites it when documents are added); "
                "delete it to write a new one",
                f"{name}.PrjPcb",
            )
        )
    model, pin_issues = kicad_pins(design, resolved)
    issues += pin_issues
    symbols = library_symbols(resolved, issues, symbol_bodies)
    model = with_written_values(generic_pins(model))
    validation = list(model.validate())
    if any(found.code == "model.pin-pad-map" for found in validation):
        # A pad that two pins stand for: the build says it under its own code, as the release 0.2.1
        # does, before the model's finding ends the build. Both findings are reported, as in a KiCad build.
        early, _unused = resolve_footprints(model, resolver, authored_footprints, bodies=body_mode)
        issues += pin_map_issues(model, early)
    issues += validation
    if not any(i.severity == "error" for i in issues):
        issues += _library_checks(model, name, symbols, project_exists, project_listed, unread_hint)
    if any(i.severity == "error" for i in issues):
        return BuildOutput(
            model, {}, tuple(issues), evidence, _summary(model, kept, None, form, sheets=sheets)
        )
    footprints, footprint_issues = resolve_footprints(model, resolver, authored_footprints, bodies=body_mode)
    issues += footprint_issues
    issues += pin_map_issues(model, footprints)
    if any(i.severity == "error" for i in issues):
        return BuildOutput(
            model, {}, tuple(issues), evidence, _summary(model, kept, None, form, sheets=sheets)
        )
    written = [footprints[link] for link in sorted(footprints)]
    pcb_account: dict[str, dict[str, int]] = {}
    spec, document_issues = lowered_pcb(
        model,
        name=name,
        footprints=footprints,
        placements=placements or {},
        copper=copper,
        planes=planes,
        copper_source=copper_source,
        sheets=sheets,
        account=pcb_account,
        bodies=body_mode,
        body_form=body_form,
    )
    issues += document_issues
    if any(i.severity == "error" for i in issues):
        return BuildOutput(
            model, {}, tuple(issues), evidence, _summary(model, kept, None, form, sheets=sheets)
        )
    rules_info, rule_issues = altium_copper.rules_report(
        model, document=f"{name}.PcbDoc" if spec is not None else None
    )
    issues += rule_issues
    copper_info = None
    if spec is not None:
        if copper_source is not None:
            from_board = copper_source.origin == "board"
            copper_info = altium_copper.copper_summary(
                spec,
                source=copper_source.origin,
                where=copper_source.where if from_board else None,
                placed=len(spec.components) if from_board else 0,
            )
        else:
            source = "model" if altium_copper.has_copper(model.board) else "none"
            copper_info = altium_copper.copper_summary(spec, source=source)
    if spec is not None:
        issues = [
            i
            for i in issues
            if not (
                i.code == "altium.not-lowered"
                and i.where in ("board", "placements", "rules", *altium_copper.BOARD_WHERES)
            )
        ]
    pcb_files = [
        f for f, wanted in ((f"{name}.PcbDoc", spec is not None), (f"{name}.PcbLib", bool(written))) if wanted
    ]
    pcb_unlisted = not_listed(pcb_files, project_listed) if project_exists else []
    if pcb_unlisted:
        issues.append(
            issue(
                "altium.pcb-not-in-project",
                f"the kept {name}.PrjPcb does not list {', '.join(pcb_unlisted)}; add them in Altium "
                "(Project » Add Existing to Project)",
                f"{name}.PrjPcb",
                unread_hint,
            )
        )
    planned = hierarchy.plan_sheets(
        model, name=name, sheets=sheets, form=form, symbols=symbols, directions=directions
    )
    unlisted = [*(sheet.file for sheet in planned.modules), *sorted(planned.harness_files, key=name_key)]
    unlisted = not_listed(unlisted, project_listed) if project_exists else []
    if unlisted:
        issues.append(
            issue(
                "altium.sheets-not-in-project",
                f"the kept {name}.PrjPcb does not list {', '.join(unlisted)}; add them in Altium "
                "(Project » Add Existing to Project)",
                f"{name}.PrjPcb",
                unread_hint,
            )
        )
    if spec is not None and any(any(pcbdoc.via_tenting(via, spec.via_protection)) for via in spec.vias):
        evidence = Evidence.combine(evidence, pcbrecords.VIA_TENTING_EVIDENCE)  # a tenting flag is set
    job: tuple[OutputGroup, ...] | None = None
    job_info: dict[str, object] | None = None
    relist = False
    if outjob and spec is not None:
        job = job_writer.from_preset(outjob_preset, name=name, copper=pcbdoc.document_stack(spec).copper)
        job_info = outjob_summary(name, job, job_writer.unmapped(outjob_preset))
        evidence = Evidence.combine(evidence, job_writer.EVIDENCE)
        if project_listed is not None and f"{name}.OutJob".casefold() in project_listed:
            outjob_listed = True
        if project_exists and not outjob_listed:
            issues.append(
                issue(
                    "altium.outjob-not-listed",
                    f"the kept {name}.PrjPcb does not list {name}.OutJob; add it in Altium "
                    "(Project » Add Existing to Project)",
                    f"{name}.PrjPcb",
                    f"or delete {name}.PrjPcb and build again: a new project file lists the job. The build "
                    "adds the job itself only to a project file that is as a build wrote it",
                )
            )
        # change c0138: a project file that is as a build wrote it and lacks the job is written again
        relist = project_exists and not outjob_listed and project_digest is not None
    frames: dict[str, schdot.SheetFrame] = {}
    sheet_info: dict[str, object] | None = None
    if drawing_sheet is not None:
        evidence = Evidence.combine(evidence, schdot.EVIDENCE)
        frames, sheet_info = sheet_frames(model, planned, drawing_sheet, issues, allow_lossy=allow_lossy)
        if not frames:
            return BuildOutput(
                model, {}, tuple(issues), evidence, _summary(model, kept, None, form, sheets=sheets)
            )
    count = sum(1 for c in model.circuit.components if symbol_source(c.lib_symbol_ref) == "altium")
    if count:
        issues.append(
            issue(
                "altium.generic-symbols",
                f"{count} component(s) of Altium links got generic bodies with the pins the design uses, "
                f"as in the generated libraries; with the real libraries, '{UPDATE_COMMAND}' replaces them",
                f"{name}.SchDoc",
                "use 'Replace selected attributes' with graphical attributes off to keep every connection",
            )
        )
    try:
        files = project.write_project(
            model,
            name=name,
            project=not project_exists or relist,
            issues=issues,
            form=form,
            symbols=symbols,
            footprints=written,
            pcb=spec,
            sheets=sheets,
            outjob=job_writer.write_outjob(job) if job is not None else None,
            frames=frames,
            directions=directions,
        )
    except project.PcbTooLarge as error:
        issues.append(
            issue(
                "altium.pcb-too-large",
                f"{error.file} is too large for a compound file without DIFAT sectors: {error}",
                error.file,
                "build fewer footprints into one design",
            )
        )
        return BuildOutput(
            model, {}, tuple(issues), evidence, _summary(model, kept, None, form, sheets=sheets)
        )
    except project.LibraryTooLarge as error:
        issues.append(
            issue(
                "altium.library-too-large",
                f"{error.library} is too large for a compound file without DIFAT sectors: {error}",
                error.library,
                "split the design's symbols over fewer or smaller libraries",
            )
        )
        return BuildOutput(
            model, {}, tuple(issues), evidence, _summary(model, kept, None, form, sheets=sheets)
        )
    except CompoundTooLarge as error:
        issues.append(
            issue(
                "altium.schematic-too-large",
                f"{name}.SchDoc is too large for the binary form: {error}",
                f"{name}.SchDoc",
                "build with --altium-format ascii",
            )
        )
        return BuildOutput(
            model, {}, tuple(issues), evidence, _summary(model, kept, None, form, sheets=sheets)
        )
    if relist:
        # the project file is written, so it is not kept and nothing is left for the user to add to it
        kept = []
        issues = [
            found
            for found in issues
            if not (found.code in KEPT_PROJECT_CODES and found.where == f"{name}.PrjPcb")
        ]
    record = {path: hashlib.sha256(data).hexdigest() for path, data in sorted(files.items())}
    if kept and project_digest is not None:
        # A kept project file that is still as a build wrote it stays in the state, so that a later build
        # knows it as built (change c0138). ``project_digest`` is None for a file that was changed or had
        # no record: recording such a file would turn an edited file into one "as built".
        record = dict(sorted({**record, f"{name}.PrjPcb": project_digest}.items()))
    stored = model
    if spec is not None and model.board is not None:
        # the stored model holds the board that was written (change c0090, "RT-A2 on a written model")
        stored = dataclasses.replace(model, board=lower.stored_board(model, spec))
    for file_name, text in canonical.dump_texts(stored).items():
        files[f"{CACHE_DIR}/{file_name}"] = text.encode("utf-8")
    files[RECORD_FILE] = (
        json.dumps(
            {"design": name, "files": record, "schema": RECORD_SCHEMA, "target": TARGET},
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")
    libraries = project.library_symbols(model, name=name, symbols=symbols)
    summary = _summary(
        model,
        kept,
        planned,
        form,
        libraries,
        footprints=len(written),
        pcb_library=f"{name}.PcbLib",
        pcb_document=f"{name}.PcbDoc" if spec is not None else None,
        sheets=sheets,
        copper=copper_info,
        pcb={**pcb_account, "bodies": body_mode} if spec is not None else None,
        outjob=job_info,
        drawing_sheet=sheet_info,
        rules=rules_info,
        directions=directions,
        symbol_bodies=symbol_bodies,
    )
    return BuildOutput(model, dict(sorted(files.items())), tuple(issues), evidence, summary, layout=stored)


def write_model(design: Design, *, allow_lossy: bool = False, bodies: str = "off") -> lower.ProjectWrite:
    """The Altium project of ``design``, written from the model alone (``backends.altium.lower.write_design``,
    change c0090): the write of a design that was read from a KiCad board. Such a design keeps the drawings
    of its footprints and the corner ratios of its pads in KiCad's own slots, which a backend does not
    read, so the design is projected first (``backends.kicad.fpitems.with_footprint_items``, change c0126):
    the written footprints then hold their silkscreen and their rounded pads. ``AltiumBackend.write`` is
    the same write without the projection, for a design that carries its items (one read from an Altium
    document) or holds none."""
    from fenolite.backends.kicad import fpitems

    projected = fpitems.with_footprint_items(design).design
    return lower.write_design(projected, allow_lossy=allow_lossy, bodies=bodies)


__all__ = [
    "ALTIUM_BUILD_EVIDENCE",
    "ALTIUM_ISSUE_CODES",
    "EXPERIMENTAL",
    "CopperSource",
    "PCB_BUILD_EVIDENCE",
    "PCB_EXPERIMENTAL",
    "PCB_WRITE_KINDS",
    "TARGET",
    "build_altium",
    "footprint_source",
    "footprint_texts",
    "generic_pins",
    "kicad_footprint_ids",
    "kicad_lib_ids",
    "lowered_pcb",
    "place_footprints",
    "kicad_pins",
    "library_symbols",
    "match_source",
    "kept_documents",
    "not_listed",
    "outjob_summary",
    "pad_extras",
    "refused_altium",
    "resolve_footprints",
    "resolve_symbols",
    "sheet_frames",
    "sheet_page",
    "sheet_parameters",
    "symbol_source",
    "write_model",
]
