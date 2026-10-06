# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A model design as the files of an Altium project: ``<name>.PrjPcb``, ``<name>.SchDoc`` in the ASCII or
the binary form, and one ``.SchLib`` per library that the lib ids name (capability
altium-schematic-writer, "Altium writer package", "Binary schematic form" and, change c0034, "Schematic
library file").

``write_project`` takes a design whose components hold their pins (``lens.altium`` gives them), lays the
sheet out and returns the file bytes. It writes no file, starts no process, reads no environment and
resolves no library: ``lens.altium`` passes the resolved symbols in. A design it cannot write raises
``ValueError``; ``lens.altium`` reports the same problems as issues before it calls the writer.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.backends.altium.altsym import AltiumSymbol, from_generic
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.binary import write_schdoc_binary
from fenolite.backends.altium.cfb import CompoundTooLarge, name_key
from fenolite.backends.altium.layout import (
    ClassMark,
    PartSpec,
    PinNet,
    SheetPlan,
    class_mark_point,
    layout_sheet,
)
from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.backends.altium.pcblib import LibFootprint, write_pcblib
from fenolite.backends.altium.prjpcb import write_prjpcb
from fenolite.backends.altium.schdoc import Frame, write_schdoc
from fenolite.backends.altium.schlib import storage_name, write_schlib
from fenolite.backends.altium.symbols import generic_symbol
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.circuit import Component
from fenolite.model.design import Design

PATH_PROPERTY = "fenolite.path"
"""The component property that holds the component path (set by the DSL)."""
_HARNESS = "harness"
"""The kind of the interfaces that ``fenolite.dsl.Harness`` records (``hierarchy.HARNESS_INTERFACE``)."""
UNIQUE_ID_SALT = "fenolite.altium.uniqueid:"
UNIQUE_ID_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXY"
UNIQUE_ID_LENGTH = 8
WRITE_KINDS: tuple[str, ...] = (
    "altium_harness",
    "altium_prjpcb",
    "altium_schdoc_ascii",
    "altium_schdoc_binary",
    "altium_schlib",
)
"""The kinds of the planned writes of an Altium build: the harness definition files (change c0037), the
project file, the schematic sheets in each form and the schematic libraries (change c0034)."""
HARNESS_KIND = "altium_harness"
"""The write kind of a harness definition file, ``<sheet stem>.Harness`` (change c0037)."""
SCHLIB_KIND = "altium_schlib"
PCBLIB_KIND = "altium_pcblib"
"""The write kind of ``<name>.PcbLib`` (change c0035; listed by the ``altium-pcb-writer`` entry, not in
``WRITE_KINDS``)."""
PCBDOC_KIND = "altium_pcbdoc"
"""The write kind of ``<name>.PcbDoc`` (change c0035)."""
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-ECO-NETCLASS",
        "H-A-ECO-PRJ-KEYS",
        "H-A-ECO-ROOMS",
        "H-A-ECO-SUPPLY",
        "H-A-PRJ-OPEN",
        "H-A-SCH-LINEEND",
        "H-A-SCH-LINK",
        "H-A-SCH-NETS",
        "H-A-SCH-OPEN",
        "H-A-SCH-UID",
        "H-A-SCHX-BUS",
        "H-A-SCHX-DIR",
        "H-A-SCHX-ECO",
        "H-A-SCHX-GRAPHICS",
        "H-A-SCHX-READBACK",
        "H-A-SCHX-TEXT",
        "H-A-SCHX-TREE",
    ),
)
"""The writer's format facts are inferred from public sources until the maintainer's author reports. The
``H-A-ECO-*`` rows are those of the change order (change c0048): the net class directives and the class
generation keys of the project file. The ``H-A-SCHX-*`` rows are the writer's own rows of change c0086
(symbol graphics, the sheet tree, directions, buses, text outside ASCII, parameters): its own readback
row and the six rows that only Altium settles (Part Y)."""

PowerStyle = Literal["ground", "bar"]
SchematicForm = Literal["binary", "ascii"]
"""The two forms of ``<name>.SchDoc``: a compound file of framed records, or text lines."""
DEFAULT_FORM: SchematicForm = "binary"
"""The one default of the schematic form for the writer, the lens and the CLI (change c0033)."""
SheetMode = Literal["flat", "modules"]
"""How the schematic is split into sheets (change c0037): one sheet, or a top sheet with one sheet per
top-level module."""
DEFAULT_SHEETS: SheetMode = "flat"
"""The one default of the sheet mode for the writer, the lens and the CLI: the verified single sheet."""
SCHDOC_KINDS: dict[SchematicForm, str] = {"binary": "altium_schdoc_binary", "ascii": "altium_schdoc_ascii"}
"""The write kind of ``<name>.SchDoc`` by form: both forms share the extension."""


class LibraryTooLarge(CompoundTooLarge):
    """A schematic library is past the compound file's size limit; ``library`` names it."""

    def __init__(self, library: str, error: CompoundTooLarge) -> None:
        super().__init__(f"{library}: {error}")
        self.library = library


class PcbTooLarge(CompoundTooLarge):
    """A PCB library or document is past the compound file's size limit; ``file`` names it (change c0035)."""

    def __init__(self, file: str, error: CompoundTooLarge) -> None:
        super().__init__(f"{file}: {error}")
        self.file = file


def split_link(text: str) -> tuple[str, str] | None:
    """``<library>:<name>`` split at the first ``:``, or ``None`` when a part is missing."""
    library, colon, name = text.partition(":")
    if not colon or not library or not name:
        return None
    return library, name


SCHLIB_SUFFIX = ".schlib"
"""A lib id whose library part ends with this, in any letter case, is an Altium link."""
_PREFIX = re.compile(r"[A-Za-z]*")


def is_altium_link(lib_id: str) -> bool:
    """True when the library part of ``lib_id`` ends with ``.SchLib`` in any letter case."""
    link = split_link(lib_id)
    return link is not None and link[0].lower().endswith(SCHLIB_SUFFIX)


def schlib_name(lib_id: str, *, design: str) -> str:
    """The library file of ``lib_id``: its library part for an Altium link, ``<design>.SchLib`` for a
    KiCad lib id (all KiCad symbols of a design share one library)."""
    link = split_link(lib_id)
    if link is None:
        raise ValueError(f"lib_id {lib_id!r} is not <library>:<name>")
    return link[0] if is_altium_link(lib_id) else f"{design}.SchLib"


PCBLIB_SUFFIX = ".pcblib"
"""A footprint link whose library part ends with this, in any letter case, is an Altium link."""


def is_altium_footprint(link: str) -> bool:
    """True when the library part of the footprint link ``link`` ends with ``.PcbLib`` in any letter case."""
    parts = split_link(link)
    return parts is not None and parts[0].lower().endswith(PCBLIB_SUFFIX)


def pcblib_name(link: str, *, design: str) -> str:
    """The PCB library file of a footprint link: its library part for an Altium link, ``<design>.PcbLib`` for
    a KiCad footprint link (all KiCad footprints of a design share one library, change c0035)."""
    parts = split_link(link)
    if parts is None:
        raise ValueError(f"footprint {link!r} is not <library>:<name>")
    return parts[0] if is_altium_footprint(link) else f"{design}.PcbLib"


def unique_id(key: str) -> str:
    """Eight letters from ``A`` to ``Y``: the SHA-256 of ``fenolite.altium.uniqueid:<key>`` as a big-endian
    integer, written as its eight lowest base-25 digits, least significant first."""
    value = int.from_bytes(hashlib.sha256((UNIQUE_ID_SALT + key).encode("utf-8")).digest(), "big")
    letters: list[str] = []
    for _ in range(UNIQUE_ID_LENGTH):
        value, digit = divmod(value, len(UNIQUE_ID_LETTERS))
        letters.append(UNIQUE_ID_LETTERS[digit])
    return "".join(letters)


def power_styles(design: Design) -> dict[str, PowerStyle]:
    """Net id → port style of every net of a ``power`` interface: ``ground`` for a net that is only ever
    the ``lv`` member, ``bar`` otherwise."""
    roles: dict[str, set[str]] = {}
    for interface in design.circuit.interfaces:
        if interface.kind != "power":
            continue
        for role, net_id in interface.members.items():
            roles.setdefault(net_id, set()).add(role)
    return {net_id: "ground" if found == {"lv"} else "bar" for net_id, found in sorted(roles.items())}


def component_path(component: Component) -> str:
    """The component path: the ``fenolite.path`` property, else the model path, else the ref."""
    return component.properties.get(PATH_PROPERTY) or component.path or component.ref


def _text(text: str, what: str, *, parameter: bool = False, form: SchematicForm = "ascii") -> str:
    problem = text_problem(text, form=form, parameter=parameter)
    if problem is not None:
        raise ValueError(f"{what} {text!r} {problem}")
    return text


RESERVED_PARAMETERS: frozenset[str] = frozenset({"comment", "designator", "footprint", "reference", "value"})
"""Property names, in lower case, that are no parameter of a component: the writer already writes the
designator, the comment and the footprint link as records of their own (change c0086)."""
INTERNAL_PROPERTY_PREFIX = "fenolite."
"""Properties that Fenolite keeps for itself, such as ``fenolite.path``, are no parameter either."""


def parameters_of(
    component: Component, *, form: SchematicForm = "ascii"
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """The properties of ``component`` that become hidden parameters, as (name, value) in code-point
    order of the names, and those that cannot be written, as (name, reason) (change c0086, "Component
    parameters"). A property is a parameter when it has a value and is neither Fenolite's own
    (``fenolite.*``) nor a name of ``RESERVED_PARAMETERS`` in any letter case. It cannot be written when
    its name is not 7-bit text, when ``form`` cannot carry its value (``ascii.text_problem``), or when
    its name differs only in letter case from a parameter before it: a build keeps such a property in the
    model and reports it, since a property is no part of the circuit."""
    kept: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, value in sorted(component.properties.items()):
        if not value or key.startswith(INTERNAL_PROPERTY_PREFIX) or key.lower() in RESERVED_PARAMETERS:
            continue
        name_problem = text_problem(key)
        value_problem = text_problem(value, form=form, parameter=True)
        if name_problem is not None:
            skipped.append((key, f"its name {name_problem}"))
        elif value_problem is not None:
            skipped.append((key, f"its value {value_problem}"))
        elif key.lower() in seen:
            skipped.append((key, "its name differs only in letter case from another parameter"))
        else:
            seen.add(key.lower())
            kept.append((key, value))
    return kept, skipped


@dataclass(frozen=True)
class BusPlan:
    """A bus of the model that is drawn as a bus (change c0086, "Bus records"): the model's ``name``, the
    bus identifier ``label`` (``<stem>[<first>..<last>]``) and its member nets in member order, by name
    and by id."""

    name: str
    label: str
    members: tuple[str, ...]
    net_ids: tuple[str, ...]


_MEMBER = re.compile(r"(.*?)([0-9]+)")


def bus_identifier(names: Sequence[str]) -> str | None:
    """``<stem>[<first>..<last>]`` when ``names`` are one stem followed by consecutive integers, rising
    or falling, written without leading zeros; ``None`` otherwise, and for fewer than two names
    (``docs/formats/altium/connectivity.md``, "Buses and harnesses")."""
    parsed: list[tuple[str, int]] = []
    for name in names:
        match = _MEMBER.fullmatch(name)
        if match is None or not match.group(1) or str(int(match.group(2))) != match.group(2):
            return None
        parsed.append((match.group(1), int(match.group(2))))
    if len(parsed) < 2 or len({stem for stem, _ in parsed}) != 1:
        return None
    numbers = [number for _, number in parsed]
    step = numbers[1] - numbers[0]
    if step not in (1, -1) or any(b - a != step for a, b in zip(numbers, numbers[1:], strict=False)):
        return None
    return f"{parsed[0][0]}[{numbers[0]}..{numbers[-1]}]"


def lowered_buses(design: Design) -> tuple[list[BusPlan], list[tuple[str, str]]]:
    """The buses of ``design`` that are drawn as buses, in code-point order of their names, and the others
    as (bus name, reason), which are drawn as their nets and reported as ``altium.bus-flattened``. A bus
    is drawn when its member nets have a bus identifier (``bus_identifier``), none of them is a net of a
    ``power`` or a ``harness`` interface (those join through power ports and travel in their harness),
    and none is a member of a bus drawn before it."""
    names = {net.id: net.name for net in design.circuit.nets}
    special = {
        net_id: interface.kind
        for interface in design.circuit.interfaces
        if interface.kind in ("power", _HARNESS)
        for net_id in interface.members.values()
    }
    taken: dict[str, str] = {}
    drawn: list[BusPlan] = []
    flattened: list[tuple[str, str]] = []
    for bus in sorted(design.circuit.buses, key=lambda b: b.name):
        ids = tuple(member.net_id for member in bus.members)
        members = tuple(names.get(net_id, "") for net_id in ids)
        label = bus_identifier(members) if all(members) else None
        clash = next((net_id for net_id in ids if net_id in special or net_id in taken), None)
        if label is None:
            flattened.append((bus.name, "its member nets are not one stem followed by consecutive integers"))
        elif clash is not None and clash in special:
            flattened.append((bus.name, f"its net {names[clash]} is a net of a {special[clash]} interface"))
        elif clash is not None:
            flattened.append((bus.name, f"its net {names[clash]} is drawn in the bus {taken[clash]}"))
        else:
            drawn.append(BusPlan(bus.name, label, members, ids))
            taken.update(dict.fromkeys(ids, bus.name))
    return drawn, flattened


def _link(text: str, what: str) -> tuple[str, str]:
    link = split_link(text)
    if link is None:
        raise ValueError(f"{what} {text!r} is not <library>:<name>")
    return _text(link[0], f"{what} library"), _text(link[1], f"{what} name")


def part_specs(
    design: Design,
    *,
    name: str = "",
    symbols: Mapping[str, AltiumSymbol] | None = None,
    form: SchematicForm = "ascii",
) -> list[PartSpec]:
    """One ``PartSpec`` per component, in component-path order, its body the library symbol of its lib id
    (``symbols`` first, generic otherwise). ``name`` is the design name, which gives the library file of
    KiCad lib ids (``schlib_name``). ``Circuit.no_connects`` fills ``PartSpec.no_connects``; a mark on an
    unknown component, on a pin the component does not hold or on a pin that a net lists raises
    ``ValueError``. ``form`` is the schematic form that will carry the comment and the parameter values
    (change c0086): the binary form also takes the characters of its code page."""
    bodies = {**generic_symbols(design), **(symbols or {})}
    styles = power_styles(design)
    components = {c.id: c for c in design.circuit.components}
    joins: dict[str, dict[str, PinNet]] = {cid: {} for cid in components}
    for net in sorted(design.circuit.nets, key=lambda n: n.name):
        _text(net.name, "net name")
        style = styles.get(net.id)
        how = PinNet(net.name, "label") if style is None else PinNet(net.name, "port", style)
        for member in net.members:
            component = components.get(member.component_id)
            if component is None:
                raise ValueError(f"net {net.name}: unknown component {member.component_id}")
            if member.pin not in {p.number for p in component.pins}:
                raise ValueError(f"net {net.name}: {component.ref} holds no pin {member.pin!r}")
            current = joins[component.id].get(member.pin)
            if current is not None and current.net != net.name:
                raise ValueError(
                    f"{component.ref} pin {member.pin} is on the nets {current.net} and {net.name}"
                )
            joins[component.id][member.pin] = how
    marks: dict[str, set[str]] = {cid: set() for cid in components}
    for mark in design.circuit.no_connects:
        component = components.get(mark.component_id)
        if component is None:
            raise ValueError(f"no-connect mark: unknown component {mark.component_id}")
        if mark.pin not in {p.number for p in component.pins}:
            raise ValueError(f"no-connect mark: {component.ref} holds no pin {mark.pin!r}")
        joined = joins[component.id].get(mark.pin)
        if joined is not None:
            raise ValueError(
                f"{component.ref} pin {mark.pin} is marked as not connected and is on net {joined.net}"
            )
        marks[component.id].add(mark.pin)
    specs: list[PartSpec] = []
    for component in sorted(design.circuit.components, key=component_path):
        library, symbol = _link(component.lib_symbol_ref, f"{component.ref} lib_id")
        if name and not is_altium_link(component.lib_symbol_ref):
            library = schlib_name(component.lib_symbol_ref, design=name)
        footprint = (
            _link(component.lib_footprint_ref, f"{component.ref} footprint")
            if component.lib_footprint_ref
            else None
        )
        if footprint is not None and name:
            footprint = (pcblib_name(component.lib_footprint_ref, design=name), footprint[1])
        body = bodies[component.lib_symbol_ref]
        for pin in body.pins:
            _text(pin.designator, f"{component.ref} pin designator")
            _text(pin.name or pin.designator, f"{component.ref} pin name")
        specs.append(
            PartSpec(
                key=component_path(component),
                ref=_text(component.ref, "ref"),
                comment=_text(
                    component.value or symbol, f"{component.ref} comment", parameter=True, form=form
                ),
                library=library,
                symbol=symbol,
                footprint=footprint,
                unique_id=unique_id(component.id),
                body=body,
                nets=joins[component.id],
                part_ids=tuple(unique_id(f"{component.id}#{k}") for k in range(2, body.parts + 1)),
                no_connects=frozenset(marks[component.id]),
                parameters=tuple(
                    (key, value, unique_id(f"{component.id}:parameter:{key}"))
                    for key, value in parameters_of(component, form=form)[0]
                ),
            )
        )
    ids = [s.part_id(k) for s in specs for k in range(1, s.body.parts + 1)]
    if len(set(ids)) != len(ids):
        raise ValueError("two components share a unique id")
    return specs


def prefix_of(ref: str) -> str:
    """The leading letters of a ref (``R`` of ``R12``), or ``U`` when it has none."""
    match = _PREFIX.match(ref)
    return match.group(0) if match and match.group(0) else "U"


def generic_symbols(design: Design) -> dict[str, AltiumSymbol]:
    """Lib id → its generic library symbol, built from the pins of the components of that lib id (which
    ``lens.altium.generic_pins`` makes equal): prefix of the first ref in component-path order, the parts'
    common footprint or none, the symbol name as comment."""
    by_lib: dict[str, list[Component]] = {}
    for component in sorted(design.circuit.components, key=component_path):
        by_lib.setdefault(component.lib_symbol_ref, []).append(component)
    symbols: dict[str, AltiumSymbol] = {}
    for lib_id, components in sorted(by_lib.items()):
        _library, name = _link(lib_id, f"{components[0].ref} lib_id")
        pins = [(p.number, p.name or p.number) for p in components[0].pins]
        footprints = {c.lib_footprint_ref for c in components}
        footprint = None
        if len(footprints) == 1 and (only := footprints.pop()):
            footprint = _link(only, f"{components[0].ref} footprint")
        symbols[lib_id] = from_generic(
            generic_symbol(pins),
            lib_ref=name,
            prefix=prefix_of(components[0].ref),
            comment=name,
            footprint=footprint,
        )
    return symbols


def net_class_names(design: Design) -> dict[str, str]:
    """Net name → the name of its net class, for every net whose ``netclass_id`` names a net class of
    ``design``, in code-point order of the net names (change c0048)."""
    names = {item.id: item.name for item in design.circuit.netclasses}
    return {
        net.name: names[net.netclass_id]
        for net in sorted(design.circuit.nets, key=lambda n: n.name)
        if net.netclass_id is not None and net.netclass_id in names
    }


def class_marks(plan: SheetPlan, classes: Mapping[str, str], sheet: str) -> tuple[ClassMark, ...]:
    """The net class directives of the sheet ``plan``, whose file name is ``sheet`` (change c0048, "Net
    class directives on the sheet"): one per net of ``classes`` (net name → class name) that has a stub on
    the sheet, in code-point order of the net names, at a point inside the first stub of that net in write
    order (``plan.links``, then ``plan.stubs``). ``ValueError`` for a class name that a parameter text
    cannot hold."""
    first: dict[str, tuple[tuple[int, int], bool]] = {}
    for stub in (*plan.links, *plan.stubs):
        if stub.net.net in classes and stub.net.net not in first:
            first[stub.net.net] = (class_mark_point(stub), stub.vertical)
    marks: list[ClassMark] = []
    for net in sorted(first):
        name = _text(classes[net], "net class name", parameter=True)
        at, vertical = first[net]
        key = f"netclass:{sheet}:{net}"
        marks.append(ClassMark(net, name, at, vertical, unique_id(key), unique_id(f"{key}:name")))
    return tuple(marks)


def with_class_marks(plan: SheetPlan, classes: Mapping[str, str], sheet: str) -> SheetPlan:
    """``plan`` with the net class directives of ``class_marks``; ``plan`` itself when it gets none."""
    marks = class_marks(plan, classes, sheet) if classes else ()
    return dataclasses.replace(plan, class_marks=marks) if marks else plan


def plan_sheet(
    design: Design,
    *,
    name: str = "",
    symbols: Mapping[str, AltiumSymbol] | None = None,
    form: SchematicForm = "ascii",
) -> SheetPlan:
    """The sheet layout of ``design``: sheet size, placed components, stubs, the bus blocks of its lowered
    buses (change c0086) and the net class directives of the single sheet ``<name>.SchDoc`` (change
    c0048)."""
    specs = part_specs(design, name=name, symbols=symbols, form=form)
    here = {net.net for spec in specs for net in spec.nets.values()}
    buses = [(bus.label, bus.members) for bus in lowered_buses(design)[0] if here & set(bus.members)]
    plan = layout_sheet(specs, buses=buses)
    return with_class_marks(plan, net_class_names(design), f"{name}.SchDoc")


def library_symbols(
    design: Design, *, name: str, symbols: Mapping[str, AltiumSymbol] | None = None
) -> dict[str, list[AltiumSymbol]]:
    """Library file → its symbols, one per lib id of the design (``symbols`` first, generic otherwise),
    with the library files in the MS-CFB order of their names."""
    generic = generic_symbols(design)
    given = symbols or {}
    libraries: dict[str, list[AltiumSymbol]] = {}
    for lib_id in sorted({c.lib_symbol_ref for c in design.circuit.components}):
        library = schlib_name(lib_id, design=name)
        libraries.setdefault(library, []).append(given.get(lib_id) or generic[lib_id])
    return {key: libraries[key] for key in sorted(libraries, key=name_key)}


def write_project(
    design: Design,
    *,
    name: str,
    project: bool = True,
    issues: list[Issue] | None = None,
    form: SchematicForm = DEFAULT_FORM,
    symbols: Mapping[str, AltiumSymbol] | None = None,
    footprints: Sequence[LibFootprint] = (),
    pcb: PcbDocSpec | None = None,
    sheets: SheetMode = DEFAULT_SHEETS,
    outjob: bytes | None = None,
    frames: Mapping[str, Frame] | None = None,
    directions: bool = True,
) -> dict[str, bytes]:
    """``<name>.SchDoc`` in ``form``, one ``<library>.SchLib`` per library that the lib ids name and, when
    ``project`` is true, ``<name>.PrjPcb`` listing them, as bytes; no file is written. ``symbols`` maps a
    lib id to its library symbol; a lib id missing from it gets its generic symbol. The binary form and
    every library raise ``cfb.CompoundTooLarge`` past the compound file's size limit. ``footprints`` (change
    c0035) are written into ``<name>.PcbLib`` when not empty, and ``pcb`` into ``<name>.PcbDoc``; the
    project file lists both; their size limit raises ``PcbTooLarge``. With ``sheets="modules"`` (change
    c0037) ``<name>.SchDoc`` is the top sheet, each top-level module gets ``<name>_<module>.SchDoc``, each
    sheet with a harness block gets ``<sheet stem>.Harness``, and the project file lists them all; the
    libraries do not depend on the mode. A design with a net class (change c0048) gets the net class
    directives on every sheet and the ``[PrjClassGen]`` section in the project file. ``outjob`` (change
    c0087) are the bytes of ``<name>.OutJob``, which the project file then lists; ``frames`` maps a sheet
    file to the drawing sheet drawn on it. Without both, every file keeps its bytes."""
    from fenolite.backends.altium.hierarchy import plan_sheets, write_harness

    if form not in ("binary", "ascii"):
        raise ValueError(f"unknown schematic form {form!r}")
    _text(name, "design name")
    planned = plan_sheets(design, name=name, sheets=sheets, form=form, symbols=symbols, directions=directions)
    for sheet in planned.sheets:
        size = sheet.plan.size
        if size.style is None and issues is not None:
            issues.append(
                Issue(
                    "altium.sheet-custom",
                    "warning",
                    f"the layout does not fit an A0 sheet; a custom sheet of {size.width} x "
                    f"{size.height} mil is written",
                    where=sheet.file,
                )
            )
    harness_files = planned.harness_files
    libraries = library_symbols(design, name=name, symbols=symbols)
    files: dict[str, bytes] = {}
    listed = list(libraries)
    if footprints:
        listed.append(f"{name}.PcbLib")
    if project:
        files[f"{name}.PrjPcb"] = write_prjpcb(
            schematic=f"{name}.SchDoc",
            pcb=f"{name}.PcbDoc" if pcb is not None else None,
            libraries=tuple(listed),
            sheets=tuple(sheet.file for sheet in planned.modules),
            harnesses=tuple(harness_files),
            net_classes=bool(design.circuit.netclasses),
            outjob=f"{name}.OutJob" if outjob is not None else None,
        )
    for sheet in planned.sheets:
        frame = (frames or {}).get(sheet.file)
        if form == "binary":
            files[sheet.file] = write_schdoc_binary(sheet.plan, frame)
        else:
            files[sheet.file] = write_schdoc(sheet.plan, frame)
    for harness, types in harness_files.items():
        files[harness] = write_harness(types)
    for library, found in libraries.items():
        try:
            files[library] = write_schlib(found, library=library)
        except LibraryTooLarge:
            raise
        except CompoundTooLarge as error:
            raise LibraryTooLarge(library, error) from error
    if footprints:
        try:
            files[f"{name}.PcbLib"] = write_pcblib(footprints, filename=f"{name}.PcbLib")
        except CompoundTooLarge as error:
            raise PcbTooLarge(f"{name}.PcbLib", error) from error
    if pcb is not None:
        try:
            files[f"{name}.PcbDoc"] = write_pcbdoc(pcb, filename=f"{name}.PcbDoc")
        except CompoundTooLarge as error:
            raise PcbTooLarge(f"{name}.PcbDoc", error) from error
    if outjob is not None:
        files[f"{name}.OutJob"] = outjob
    return files


__all__ = [
    "DEFAULT_FORM",
    "DEFAULT_SHEETS",
    "EVIDENCE",
    "HARNESS_KIND",
    "LibraryTooLarge",
    "PCBDOC_KIND",
    "PCBLIB_KIND",
    "PcbTooLarge",
    "PATH_PROPERTY",
    "WRITE_KINDS",
    "SCHDOC_KINDS",
    "SCHLIB_KIND",
    "SchematicForm",
    "SheetMode",
    "class_marks",
    "component_path",
    "generic_symbols",
    "library_symbols",
    "net_class_names",
    "is_altium_footprint",
    "is_altium_link",
    "pcblib_name",
    "prefix_of",
    "schlib_name",
    "storage_name",
    "part_specs",
    "plan_sheet",
    "power_styles",
    "split_link",
    "unique_id",
    "with_class_marks",
    "write_project",
]
