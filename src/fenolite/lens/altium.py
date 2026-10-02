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
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Literal

from fenolite.backends.altium import binary, project, schlib
from fenolite.backends.altium.altsym import AltiumSymbol, from_symbol_def
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.cfb import CompoundTooLarge
from fenolite.backends.altium.layout import SheetPlan
from fenolite.backends.altium.project import WRITE_KINDS, component_path, split_link, unique_id
from fenolite.backends.altium.symbols import natural_key
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryResolver
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.lens.build import CACHE_DIR, RECORD_FILE, RECORD_SCHEMA, BuildOutput, UnresolvedLibrariesError
from fenolite.model import canonical
from fenolite.model.circuit import Component, Net, Pin, PinRef
from fenolite.model.design import Design
from fenolite.model.library import SymbolDef

TARGET = "altium"
"""The value of ``build --target`` for this builder, and of ``target`` in its result and record."""
DSL_BACKEND = "dsl"
UPDATE_COMMAND = "Tools » Update From Libraries"
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
        "altium.no-footprint": "warning",
        "altium.sheet-custom": "warning",
        "altium.pin-lossy": "warning",
        "altium.generic-symbols": "info",
        "altium.symbol-simplified": "info",
        "altium.not-lowered": "info",
        "altium.project-kept": "info",
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
            "H-A-SCH-NETS",
            "H-A-SCH-OPEN",
            "H-A-SCH-RELINK",
            "H-A-SCH-UID",
            "H-A-SCH-UPDATE",
        ),
    ),
    binary.EVIDENCE,
)
"""``INFERRED`` for every build: author reports cover the files the maintainer opened, never a design.
It names the rows of both schematic forms (``binary.EVIDENCE`` holds the ``H-A-SCHBIN-*`` rows)."""
EXPERIMENTAL: Mapping[str, object] = MappingProxyType(
    {
        "name": "altium-schematic-writer",
        "command": "build",
        "option": f"--target {TARGET}",
        "write_kinds": list(WRITE_KINDS),
    }
)
"""The ``capabilities`` entry of this writer, without its evidence (``ALTIUM_BUILD_EVIDENCE``)."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, ALTIUM_ISSUE_CODES[code], message, where=where, hint=hint)


def generic_pins(design: Design) -> Design:
    """``design`` with one passive pin per designator that its nets name on any component of the same lib
    id, in natural order, for every component that holds no pin yet: components sharing a lib id share one
    generic body, which is also their library symbol. A pin's name is its designator and its id is keyed
    ``pin:<path>:<designator>``."""
    lib_of = {c.id: c.lib_symbol_ref for c in design.circuit.components}
    used: dict[str, set[str]] = {lib: set() for lib in lib_of.values()}
    for net in design.circuit.nets:
        for member in net.members:
            if member.component_id in lib_of:
                used[lib_of[member.component_id]].add(member.pin)
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
    """``design`` with the symbol's pins on every component of a KiCad lib id, and net members that name a
    pin name rewritten to every pin number with that name; a member that names neither gives
    ``altium.unknown-pin``."""
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
    circuit = dataclasses.replace(design.circuit, components=tuple(components), nets=tuple(nets))
    return dataclasses.replace(design, circuit=circuit), issues


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


def _check(design: Design, name: str, placed: Sequence[str]) -> list[Issue]:
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
    _case_collisions(issues, "net", [n.name for n in design.circuit.nets])
    _case_collisions(issues, "ref", [c.ref for c in components])
    ids: dict[str, str] = {}
    for component in components:
        uid = unique_id(component.id)
        other = ids.get(uid)
        if other is not None:
            issues.append(
                issue(
                    "altium.unique-id-collision",
                    f"{other} and {component.ref} get the same unique id {uid}",
                    component_path(component),
                )
            )
        ids.setdefault(uid, component.ref)
    issues += _not_lowered(design, placed)
    return issues


def _not_lowered(design: Design, placed: Sequence[str]) -> list[Issue]:
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
    pairs = sorted(i.name for i in design.circuit.interfaces if i.kind == "diff_pair")
    if pairs:
        message = f"diff pairs {', '.join(pairs)} are kept in the model only"
        found.append(issue("altium.not-lowered", message, "interfaces"))
    return found


def _summary(
    design: Design, kept: Sequence[str], plan: SheetPlan | None, form: project.SchematicForm
) -> dict[str, object]:
    labels = sum(1 for s in plan.stubs if s.net.kind == "label") if plan is not None else 0
    ports = sum(1 for s in plan.stubs if s.net.kind == "port") if plan is not None else 0
    return {
        "components": len(design.circuit.components),
        "nets": len(design.circuit.nets),
        "labels": labels,
        "power_ports": ports,
        "sheet": plan.size.name if plan is not None else None,
        "kept": list(kept),
        "schematic_format": form,
        "experimental": True,
    }


def build_altium(
    design: Design,
    *,
    name: str,
    placed: Sequence[str] = (),
    project_exists: bool = False,
    form: project.SchematicForm = project.DEFAULT_FORM,
    resolver: LibraryResolver | None = None,
) -> BuildOutput:
    """Every file of the Altium project of ``design`` as bytes, or no file when an issue is an error.

    ``placed`` are the component paths the script placed; ``project_exists`` tells that
    ``<name>.PrjPcb`` already exists in the output folder, so it is kept and not planned; ``form`` is the
    form of ``<name>.SchDoc`` (``binary`` or ``ascii``). A binary schematic past the compound file's size
    limit is reported as ``altium.schematic-too-large`` and gives no file. ``resolver`` resolves the KiCad
    lib ids (change c0034); a lib id that does not resolve raises ``UnresolvedLibrariesError``.
    """
    evidence = Evidence.combine(ALTIUM_BUILD_EVIDENCE, project.EVIDENCE, schlib.EVIDENCE)
    kept = [f"{name}.PrjPcb"] if project_exists else []
    resolved = resolve_symbols(design, resolver)
    design = _with_symbol_fields(design, resolved)
    issues = _check(design, name, placed)
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
    if any(i.severity == "error" for i in issues):
        return BuildOutput(model, {}, tuple(issues), evidence, _summary(model, kept, None, form))
    count = len(model.circuit.components)
    issues.append(
        issue(
            "altium.generic-symbols",
            f"{count} component(s) got generic bodies with the pins the design uses; "
            f"'{UPDATE_COMMAND}' replaces them with the library symbols",
            f"{name}.SchDoc",
            "use 'Replace selected attributes' with graphical attributes off to keep every connection",
        )
    )
    try:
        files = project.write_project(
            model, name=name, project=not project_exists, issues=issues, form=form, symbols=symbols
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
        return BuildOutput(model, {}, tuple(issues), evidence, _summary(model, kept, None, form))
    except CompoundTooLarge as error:
        issues.append(
            issue(
                "altium.schematic-too-large",
                f"{name}.SchDoc is too large for the binary form: {error}",
                f"{name}.SchDoc",
                "build with --altium-format ascii",
            )
        )
        return BuildOutput(model, {}, tuple(issues), evidence, _summary(model, kept, None, form))
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
    summary = _summary(model, kept, project.plan_sheet(model, name=name), form)
    return BuildOutput(model, dict(sorted(files.items())), tuple(issues), evidence, summary)


__all__ = [
    "ALTIUM_BUILD_EVIDENCE",
    "ALTIUM_ISSUE_CODES",
    "EXPERIMENTAL",
    "TARGET",
    "build_altium",
    "generic_pins",
    "kicad_lib_ids",
    "resolve_symbols",
    "symbol_source",
]
