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
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Literal

from fenolite.backends.altium import binary, hierarchy, pcbdoc, pcblib, pcbrecords, project, schlib
from fenolite.backends.altium.altsym import AltiumSymbol, from_symbol_def
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.cfb import CompoundTooLarge, name_key
from fenolite.backends.altium.hierarchy import ProjectSheets
from fenolite.backends.altium.project import WRITE_KINDS, component_path, split_link, unique_id
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
from fenolite.model import canonical
from fenolite.model.base import Opaque
from fenolite.model.circuit import Component, Net, Pin, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef, SymbolDef

TARGET = "altium"
"""The value of ``build --target`` for this builder, and of ``target`` in its result and record."""
DSL_BACKEND = "dsl"
UPDATE_COMMAND = "Tools » Update From Libraries"
MAX_PIN_TEXT = 255
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
        "altium.primitive-dropped": "warning",
        "altium.generic-symbols": "info",
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
        **altium_copper.COPPER_ISSUE_CODES,
    }
)
"""The closed table of the Altium build's own issue codes (``model.*`` and ``build.layout-exists`` pass
through)."""
ALTIUM_BUILD_EVIDENCE = Evidence.combine(
    Evidence(
        Level.INFERRED,
        hypotheses=(
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
)
"""``INFERRED`` for every build: author reports cover the files the maintainer opened, never a design, and
the kicad-cli oracle checks only what KiCad's importer reads. It names the rows of both schematic forms
(``binary.EVIDENCE`` holds the ``H-A-SCHBIN-*`` rows) and of the libraries (every ``H-A-SCHLIB-*`` row,
``schlib.EVIDENCE`` holding those of the library file) and of the hierarchy and harnesses
(``hierarchy.EVIDENCE``: every ``H-A-SCH-HIER-*`` and ``H-A-SCH-HARN-*`` row, change c0037)."""
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
PCB_BUILD_EVIDENCE = Evidence.combine(pcbrecords.EVIDENCE, pcblib.EVIDENCE, pcbdoc.EVIDENCE)
"""``INFERRED``: every ``H-A-PCB-*`` row; the kicad-cli oracles check only what KiCad reads."""
PCB_EXPERIMENTAL: Mapping[str, object] = MappingProxyType(
    {
        "name": "altium-pcb-writer",
        "command": "build",
        "option": f"--target {TARGET}",
        "write_kinds": list(PCB_WRITE_KINDS),
    }
)
"""The ``capabilities`` entry of the PCB writers, without its evidence (``PCB_BUILD_EVIDENCE``)."""


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


def resolve_symbols(design: Design, resolver: LibraryResolver | None) -> dict[str, SymbolDef]:
    """Lib id → resolved ``SymbolDef`` of every KiCad lib id; ``UnresolvedLibrariesError`` (FEN-3001)
    with one ``kicad.lib.*`` issue per lib id that does not resolve."""
    wanted = kicad_lib_ids(design)
    if not wanted:
        return {}
    if resolver is None:
        raise ValueError(f"the KiCad lib ids {', '.join(wanted)} need a library resolver")
    found: dict[str, SymbolDef] = {}
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
    design: Design, resolver: LibraryResolver | None
) -> tuple[dict[str, pcblib.LibFootprint], list[Issue]]:
    """KiCad footprint link → the footprint written into ``<name>.PcbLib``, with the warnings and infos of
    footprints that do not resolve, are refused, collide on a storage name, or lose items."""
    issues: list[Issue] = []
    resolved: dict[str, pcblib.LibFootprint] = {}
    for link in kicad_footprint_ids(design):
        if resolver is None:
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
        check = pcblib.check_footprint(defn, extras, texts=texts)
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
        resolved[link] = pcblib.LibFootprint(defn, extras, texts)
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


def pcb_document(
    design: Design,
    *,
    name: str,
    footprints: Mapping[str, pcblib.LibFootprint],
    placements: Mapping[str, PlacementRequest],
    sheets: project.SheetMode = project.DEFAULT_SHEETS,
    copper: int = 2,
    planes: Mapping[str, str] | None = None,
    copper_source: altium_copper.CopperSource | None = None,
) -> tuple[pcbdoc.PcbDocSpec | None, list[Issue]]:
    """The PCB document of ``design`` (change c0035, "PCB document output"), or ``None`` with one
    ``altium.pcbdoc-not-written`` info naming the reason; unplaced components are staged right of the
    outline as the KiCad build stages them, with one ``altium.pcb-staged`` info. ``copper`` is the
    script's copper layer count and ``planes`` its internal planes (layer name → net name); the board's
    copper is lowered by ``altium_copper`` (change c0038), and copper that cannot be written gives its
    errors and ``None``. With ``copper_source`` the copper and the placements come from that source, after
    ``altium_copper.match_source`` checked it against the design; none is staged."""
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
    assert board is not None and board.outline is not None
    nets: dict[str, dict[str, str]] = {}
    for net in design.circuit.nets:
        for member in net.members:
            nets.setdefault(member.component_id, {})[member.pin] = net.name
    outline = board.outline.points
    cursor = max(p.x for p in outline) + STAGING_OFFSET
    top = min(p.y for p in outline)
    staged: list[str] = []
    placed: list[pcbdoc.PlacedComponent] = []
    for component in with_links:
        footprint = footprints[component.lib_footprint_ref]
        request = placements.get(component_path(component))
        if request is None:
            box = footprint_extent(footprint.defn)
            at, rotation, side, locked = Point(cursor - box.x0, top - box.y0), 0, "top", False
            cursor += (box.x1 - box.x0) + STAGING_GAP
            staged.append(component.ref)
        else:
            at, rotation, side, locked = request.at, request.rotation, request.side, request.locked
        link = split_link(component.lib_symbol_ref)
        assert link is not None
        module = hierarchy.sheet_of(component) if sheets == "modules" else None
        placed.append(
            pcbdoc.PlacedComponent(
                ref=component.ref,
                unique_id=unique_id(component.id),
                comment=_comment(component),
                footprint=footprint,
                footprint_library=project.pcblib_name(component.lib_footprint_ref, design=name),
                lib_reference=link[1],
                component_library=project.schlib_name(component.lib_symbol_ref, design=name),
                at=at,
                rotation=rotation,
                side=side,  # type: ignore[arg-type]
                locked=locked,
                pad_nets=nets.get(component.id, {}),
                sheet=(unique_id(hierarchy.symbol_key(module)), module) if module is not None else None,
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
    spec = pcbdoc.PcbDocSpec(outline, tuple(placed), tuple(n.name for n in design.circuit.nets))
    plan = altium_copper.lower_copper(
        design, copper=copper, planes=planes, source=copper_source, document=f"{name}.PcbDoc"
    )
    issues += plan.issues
    if plan.failed:
        return None, issues
    return altium_copper.with_copper(spec, plan), issues


def library_symbols(symbols: Mapping[str, SymbolDef], issues: list[Issue]) -> dict[str, AltiumSymbol]:
    """Lib id → the Altium symbol of every resolved KiCad symbol; an off-grid pin gives
    ``altium.symbol-off-grid`` and no symbol."""
    mapped: dict[str, AltiumSymbol] = {}
    for lib_id, symbol in sorted(symbols.items()):
        link = split_link(lib_id)
        assert link is not None
        footprint = split_link(symbol.footprint) if symbol.footprint else None
        try:
            mapped[lib_id] = from_symbol_def(symbol, lib_ref=link[1], footprint=footprint, issues=issues)
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
    if project_exists and libraries:
        found.append(
            issue(
                "altium.schlib-not-in-project",
                f"the kept {name}.PrjPcb does not list {', '.join(libraries)}; add them in Altium "
                "(Project » Add Existing to Project)",
                f"{name}.PrjPcb",
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


def _unwritable(issues: list[Issue], text: str, what: str, where: str, *, parameter: bool = False) -> None:
    problem = text_problem(text, parameter=parameter)
    if problem is not None:
        issues.append(
            issue(
                "altium.text-unwritable",
                f"{what} {text!r} {problem}",
                where,
                "use printable 7-bit ASCII without '|', without surrounding spaces"
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
            _unwritable(issues, component.value or link[1], f"{ref} comment", path, parameter=True)
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
    _case_collisions(issues, "net", [n.name for n in design.circuit.nets])
    _case_collisions(issues, "ref", [c.ref for c in components])
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
    modules = sorted({m for c in design.circuit.components if (m := hierarchy.sheet_of(c)) is not None})
    seen: dict[str, str] = {}
    for module in modules:
        _unwritable(found, module, "module name", module)
        other = seen.setdefault(module.lower(), module)
        if other != module:
            message = (
                f"the modules {other!r} and {module!r} differ only in letter case, so their sheet files "
                "would collide"
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
        message = f"net classes {', '.join(classes)} are kept in the model only"
        found.append(issue("altium.not-lowered", message, "rules"))
    found += altium_copper.board_not_lowered(design.board)
    pairs = sorted(i.name for i in design.circuit.interfaces if i.kind == "diff_pair")
    if pairs:
        message = f"diff pairs {', '.join(pairs)} are kept in the model only"
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
) -> dict[str, object]:
    """The lens summary. ``labels`` and ``power_ports`` count what every sheet holds, the labels of sheet
    entries, ports and harness entries included; ``ports``, ``sheet_entries`` and ``harnesses`` (the harness
    types drawn) are 0 on a single sheet (change c0037)."""
    plans = [sheet.plan for sheet in planned.sheets] if planned is not None else []
    labels = sum(1 for plan in plans for s in (*plan.links, *plan.stubs) if s.net.kind == "label")
    ports = sum(1 for plan in plans for s in plan.stubs if s.net.kind == "port")
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
        "copper": copper,
        "kept": list(kept),
        "schematic_format": form,
        "experimental": True,
    }


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
) -> BuildOutput:
    """Every file of the Altium project of ``design`` as bytes, or no file when an issue is an error.

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
    """
    if sheets not in ("flat", "modules"):
        raise ValueError(f"unknown sheet mode {sheets!r}")
    if copper_source is not None and altium_copper.has_copper(design.board):
        raise ValueError(
            "two copper sources: the design's board holds copper (the model source) and a copper source "
            f"of origin {copper_source.origin} is given; a build takes one"
        )
    evidence = Evidence.combine(ALTIUM_BUILD_EVIDENCE, project.EVIDENCE, schlib.EVIDENCE, PCB_BUILD_EVIDENCE)
    kept = [f"{name}.PrjPcb"] if project_exists else []
    resolved = resolve_symbols(design, resolver)
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
    symbols = library_symbols(resolved, issues)
    model = generic_pins(model)
    issues += list(model.validate())
    if not any(i.severity == "error" for i in issues):
        issues += _library_checks(model, name, symbols, project_exists)
    if any(i.severity == "error" for i in issues):
        return BuildOutput(
            model, {}, tuple(issues), evidence, _summary(model, kept, None, form, sheets=sheets)
        )
    footprints, footprint_issues = resolve_footprints(model, resolver)
    issues += footprint_issues
    written = [footprints[link] for link in sorted(footprints)]
    spec, document_issues = pcb_document(
        model,
        name=name,
        footprints=footprints,
        placements=placements or {},
        copper=copper,
        planes=planes,
        copper_source=copper_source,
        sheets=sheets,
    )
    issues += document_issues
    if any(i.severity == "error" for i in issues):
        return BuildOutput(model, {}, tuple(issues), evidence, _summary(model, kept, None, form))
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
            if not (i.code == "altium.not-lowered" and i.where in ("board", "placements", "rules"))
        ]
    pcb_files = [
        f for f, wanted in ((f"{name}.PcbDoc", spec is not None), (f"{name}.PcbLib", bool(written))) if wanted
    ]
    if project_exists and pcb_files:
        issues.append(
            issue(
                "altium.pcb-not-in-project",
                f"the kept {name}.PrjPcb does not list {', '.join(pcb_files)}; add them in Altium "
                "(Project » Add Existing to Project)",
                f"{name}.PrjPcb",
            )
        )
    planned = hierarchy.plan_sheets(model, name=name, sheets=sheets, form=form, symbols=symbols)
    unlisted = [*(sheet.file for sheet in planned.modules), *sorted(planned.harness_files, key=name_key)]
    if project_exists and unlisted:
        issues.append(
            issue(
                "altium.sheets-not-in-project",
                f"the kept {name}.PrjPcb does not list {', '.join(unlisted)}; add them in Altium "
                "(Project » Add Existing to Project)",
                f"{name}.PrjPcb",
            )
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
            project=not project_exists,
            issues=issues,
            form=form,
            symbols=symbols,
            footprints=written,
            pcb=spec,
            sheets=sheets,
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
    record = {path: hashlib.sha256(data).hexdigest() for path, data in sorted(files.items())}
    for file_name, text in canonical.dump_texts(model).items():
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
    )
    return BuildOutput(model, dict(sorted(files.items())), tuple(issues), evidence, summary)


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
    "pcb_document",
    "kicad_pins",
    "library_symbols",
    "match_source",
    "pad_extras",
    "resolve_footprints",
    "resolve_symbols",
    "symbol_source",
]
