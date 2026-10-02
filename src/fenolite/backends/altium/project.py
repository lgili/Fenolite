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

import hashlib
import re
from collections.abc import Mapping
from typing import Literal

from fenolite.backends.altium.altsym import AltiumSymbol, from_generic
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.binary import write_schdoc_binary
from fenolite.backends.altium.cfb import CompoundTooLarge, name_key
from fenolite.backends.altium.layout import PartSpec, PinNet, SheetPlan, layout_sheet
from fenolite.backends.altium.prjpcb import write_prjpcb
from fenolite.backends.altium.schdoc import write_schdoc
from fenolite.backends.altium.schlib import storage_name, write_schlib
from fenolite.backends.altium.symbols import generic_symbol
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.circuit import Component
from fenolite.model.design import Design

PATH_PROPERTY = "fenolite.path"
"""The component property that holds the component path (set by the DSL)."""
UNIQUE_ID_SALT = "fenolite.altium.uniqueid:"
UNIQUE_ID_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXY"
UNIQUE_ID_LENGTH = 8
WRITE_KINDS: tuple[str, ...] = (
    "altium_prjpcb",
    "altium_schdoc_ascii",
    "altium_schdoc_binary",
    "altium_schlib",
)
"""The kinds of the planned writes of an Altium build: the project file, the schematic in each form and
the schematic libraries (change c0034)."""
SCHLIB_KIND = "altium_schlib"
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-PRJ-OPEN",
        "H-A-SCH-LINEEND",
        "H-A-SCH-LINK",
        "H-A-SCH-NETS",
        "H-A-SCH-OPEN",
        "H-A-SCH-UID",
    ),
)
"""The writer's format facts are inferred from public sources until the maintainer's author reports."""

PowerStyle = Literal["ground", "bar"]
SchematicForm = Literal["binary", "ascii"]
"""The two forms of ``<name>.SchDoc``: a compound file of framed records, or text lines."""
DEFAULT_FORM: SchematicForm = "binary"
"""The one default of the schematic form for the writer, the lens and the CLI (change c0033)."""
SCHDOC_KINDS: dict[SchematicForm, str] = {"binary": "altium_schdoc_binary", "ascii": "altium_schdoc_ascii"}
"""The write kind of ``<name>.SchDoc`` by form: both forms share the extension."""


class LibraryTooLarge(CompoundTooLarge):
    """A schematic library is past the compound file's size limit; ``library`` names it."""

    def __init__(self, library: str, error: CompoundTooLarge) -> None:
        super().__init__(f"{library}: {error}")
        self.library = library


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


def _text(text: str, what: str, *, parameter: bool = False) -> str:
    problem = text_problem(text, parameter=parameter)
    if problem is not None:
        raise ValueError(f"{what} {text!r} {problem}")
    return text


def _link(text: str, what: str) -> tuple[str, str]:
    link = split_link(text)
    if link is None:
        raise ValueError(f"{what} {text!r} is not <library>:<name>")
    return _text(link[0], f"{what} library"), _text(link[1], f"{what} name")


def part_specs(design: Design, *, name: str = "") -> list[PartSpec]:
    """One ``PartSpec`` per component, in component-path order. ``name`` is the design name, which gives
    the library file of KiCad lib ids (``schlib_name``)."""
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
        pins = [
            (
                _text(p.number, f"{component.ref} pin designator"),
                _text(p.name or p.number, f"{component.ref} pin name"),
            )
            for p in component.pins
        ]
        specs.append(
            PartSpec(
                key=component_path(component),
                ref=_text(component.ref, "ref"),
                comment=_text(component.value or symbol, f"{component.ref} comment", parameter=True),
                library=library,
                symbol=symbol,
                footprint=footprint,
                unique_id=unique_id(component.id),
                body=generic_symbol(pins),
                nets=joins[component.id],
            )
        )
    ids = [s.unique_id for s in specs]
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


def plan_sheet(design: Design, *, name: str = "") -> SheetPlan:
    """The sheet layout of ``design``: sheet size, placed components and stubs."""
    return layout_sheet(part_specs(design, name=name))


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
) -> dict[str, bytes]:
    """``<name>.SchDoc`` in ``form``, one ``<library>.SchLib`` per library that the lib ids name and, when
    ``project`` is true, ``<name>.PrjPcb`` listing them, as bytes; no file is written. ``symbols`` maps a
    lib id to its library symbol; a lib id missing from it gets its generic symbol. The binary form and
    every library raise ``cfb.CompoundTooLarge`` past the compound file's size limit."""
    if form not in ("binary", "ascii"):
        raise ValueError(f"unknown schematic form {form!r}")
    _text(name, "design name")
    plan = plan_sheet(design, name=name)
    if plan.size.style is None and issues is not None:
        issues.append(
            Issue(
                "altium.sheet-custom",
                "warning",
                f"the layout does not fit an A0 sheet; a custom sheet of {plan.size.width} x "
                f"{plan.size.height} mil is written",
                where=f"{name}.SchDoc",
            )
        )
    libraries = library_symbols(design, name=name, symbols=symbols)
    files: dict[str, bytes] = {}
    if project:
        files[f"{name}.PrjPcb"] = write_prjpcb(schematic=f"{name}.SchDoc", libraries=tuple(libraries))
    files[f"{name}.SchDoc"] = write_schdoc_binary(plan) if form == "binary" else write_schdoc(plan)
    for library, found in libraries.items():
        try:
            files[library] = write_schlib(found, library=library)
        except LibraryTooLarge:
            raise
        except CompoundTooLarge as error:
            raise LibraryTooLarge(library, error) from error
    return files


__all__ = [
    "DEFAULT_FORM",
    "EVIDENCE",
    "LibraryTooLarge",
    "PATH_PROPERTY",
    "WRITE_KINDS",
    "SCHDOC_KINDS",
    "SCHLIB_KIND",
    "SchematicForm",
    "component_path",
    "generic_symbols",
    "library_symbols",
    "is_altium_link",
    "prefix_of",
    "schlib_name",
    "storage_name",
    "part_specs",
    "plan_sheet",
    "power_styles",
    "split_link",
    "unique_id",
    "write_project",
]
