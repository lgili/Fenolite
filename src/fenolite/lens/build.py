# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Building a model design into a self-contained KiCad project (``docs/dsl.md``, "Build").

``build_design`` resolves libraries, fills pins, places and stages parts with their user properties,
checks, writes the triad through ``triad.write_triad``, vendors the placed footprints of every row origin
(or of project rows only) with a per-target ``fp-lib-table``, and adds the ``.fenolite/`` layer texts and
build record. A design with an error gives no file.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Protocol, cast

from fenolite.backends.kicad import copper as copper_mod
from fenolite.backends.kicad import dru, embed, frame, lowering, mod, pcb, pro, sym, versions
from fenolite.backends.kicad.copper import CopperIntentLike, is_copper_uuid, resolve_copper
from fenolite.backends.kicad.embed import PATH_PROPERTY, footprint_extent, place_footprint, with_property
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryResolver, LibRow, LibTable, Location, write_lib_table
from fenolite.backends.kicad.pcb import WRITE_EVIDENCE, read_board, write_board
from fenolite.backends.kicad.sexpr import parse_bytes
from fenolite.backends.kicad.triad import write_triad
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Udeg
from fenolite.lens import preserve
from fenolite.lens.preserve import PRESERVE_ISSUE_CODES, Prepared
from fenolite.model import canonical
from fenolite.model.board import FootprintInstance, Pad, Side
from fenolite.model.circuit import Component, Pin, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef, SymbolDef

RECORD_FILE = ".fenolite/build.json"
RECORD_SCHEMA = "fenolite.build-record.v0"
CACHE_DIR = ".fenolite"
STAGING_OFFSET = 5_000_000
STAGING_GAP = 2_000_000
DSL_BACKEND = "dsl"
LAYOUT_HINT = (
    "re-run with --discard-layout to replace them (backups are kept), or build into another --out folder"
)
BUILD_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "build.unknown-pin": "error",
        "build.pin-on-two-nets": "error",
        "build.pin-without-pad": "error",
        "build.no-connect-on-net": "error",
        "build.no-footprint": "error",
        "build.no-board": "error",
        "build.name-case-collision": "error",
        "build.layout-exists": "error",
        "build.property-reserved": "error",
        "build.property-invalid": "error",
        "build.property-conflict": "error",
        "build.vendor-unsafe-name": "error",
        "build.pin-ambiguous": "warning",
        "build.unused-pin-without-pad": "warning",
        "build.library-too-new": "warning",
        "build.library-changed": "warning",
        "layout.unplaced": "warning",
        "build.pad-without-pin": "info",
        "build.global-library": "info",
        "build.interface-not-lowered": "info",
        "build.plane-not-lowered": "info",
        **PRESERVE_ISSUE_CODES,
    }
)
BUILD_EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=("H-K-BUILD-TRIAD", "H-K-BUILD-CLASS", "H-K-BUILD-LIBTABLE", "H-K-BUILD-PATHPROP"),
)
"""The blink is proved by the build oracle; arbitrary designs reach forms the oracle has not run."""
PROPERTY_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-VENDOR-PROPS", "H-K-VENDOR-DUPNAME"))
"""Joins the envelope when a user property is written (c0027)."""
VENDOR_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-VENDOR-GLOBAL", "H-K-VENDOR-SHADOW"))
"""Joins the envelope when a footprint of a row whose origin is not ``project`` is vendored (c0027)."""
VENDOR_MODES: tuple[str, ...] = ("all", "project")
"""``vendor="all"`` copies every placed footprint; ``"project"`` only those of project rows (c0011)."""
RESERVED_PROPERTIES: frozenset[str] = frozenset(
    {"Reference", "Value", "Footprint", "Datasheet", "Description"}
)
"""User property names refused after ``str.casefold`` (equal to ``fenolite.dsl.part.RESERVED_PROPERTIES``)."""
RESERVED_PREFIXES: tuple[str, ...] = ("fenolite.", "ki_")
"""User property name prefixes refused after ``str.casefold`` (equal to the DSL's)."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, BUILD_ISSUE_CODES[code], message, where=where, hint=hint)


def plane_issues(planes: Mapping[str, str]) -> list[Issue]:
    """One ``build.plane-not-lowered`` info per internal plane of the script (layer name → net name): the
    KiCad target writes the layer as the signal layer it is, and no plane (change c0038)."""
    return [
        issue(
            "build.plane-not-lowered",
            f"the plane on {layer} (net {net}) is not written: {layer} stays a signal layer of the board",
            layer,
            f"draw a zone on {layer} for the net {net} in KiCad",
        )
        for layer, net in planes.items()
    ]


class PlacementRequest(Protocol):
    """A requested placement (the DSL's ``Placement``), read by attribute."""

    @property
    def at(self) -> Point: ...

    @property
    def rotation(self) -> Udeg: ...

    @property
    def side(self) -> Side: ...

    @property
    def locked(self) -> bool: ...


class UnresolvedLibrariesError(LibraryError):
    """Every library item the build could not resolve (FEN-3001), one ``kicad.lib.*`` issue each."""

    def __init__(self, errors: Sequence[LibraryError]) -> None:
        super().__init__(errors[0].issue)
        self.issues = tuple(e.issue for e in errors)
        more = f" (and {len(errors) - 1} more)" if len(errors) > 1 else ""
        self.args = (f"{errors[0].issue.message}{more}",)


class LayoutExistsError(FenoliteError):
    """Outputs changed since the last build; replacing them would lose work (FEN-7001)."""

    cli_code = "FEN-7001"

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = tuple(issues)
        self.hint = LAYOUT_HINT
        names = ", ".join(i.where for i in self.issues)
        super().__init__(f"files changed since the last build would be replaced: {names}")


@dataclass(frozen=True)
class BuildOutput:
    """``design`` is the model built from the script at the given placements; ``layout`` is the design
    read back from the written board and merged with it, which ``.fenolite/`` caches (c0019)."""

    design: Design
    files: Mapping[str, bytes]
    issues: tuple[Issue, ...]
    evidence: Evidence
    summary: Mapping[str, object]
    layout: Design | None = None


@dataclass
class _Part:
    component: Component
    path: str
    symbol: SymbolDef
    footprint: FootprintDef
    location: Location


def _path(component: Component) -> str:
    return component.properties.get(PATH_PROPERTY, component.ref)


def _resolve(
    design: Design, resolver: LibraryResolver, issues: list[Issue]
) -> tuple[list[_Part], dict[str, str]]:
    errors: list[LibraryError] = []
    libraries: dict[str, str] = {}
    found: list[_Part] = []
    for component in sorted(design.circuit.components, key=_path):
        try:
            symbol = resolver.symbol(component.lib_symbol_ref)
            libraries[component.lib_symbol_ref] = resolver.locate(component.lib_symbol_ref, "symbol").origin
        except LibraryError as error:
            errors.append(error)
            continue
        fp_ref = component.lib_footprint_ref or symbol.properties.get("Footprint", "")
        if not fp_ref:
            issues.append(
                issue(
                    "build.no-footprint",
                    f"{component.ref}: neither the part nor the symbol names a footprint",
                    _path(component),
                )
            )
            continue
        try:
            location = resolver.locate(fp_ref, "footprint")
            footprint = resolver.footprint(fp_ref)
        except LibraryError as error:
            errors.append(error)
            continue
        libraries[fp_ref] = location.origin
        value = component.value or symbol.properties.get("Value", "")
        component = dataclasses.replace(component, lib_footprint_ref=fp_ref, value=value)
        found.append(_Part(component, _path(component), symbol, footprint, location))
    if errors:
        raise UnresolvedLibrariesError(errors)
    return found, dict(sorted(libraries.items()))


def _pins(symbol: SymbolDef, path: str) -> list[Pin]:
    pins: dict[str, Pin] = {}
    for unit in range(1, symbol.unit_count + 1):
        for pin in symbol.pins_of(unit, body_style=1):
            if pin.number not in pins:
                pins[pin.number] = Pin(
                    id=derived_id("pin", DSL_BACKEND, f"pin:{path}:{pin.number}"),
                    number=pin.number,
                    name=pin.name,
                    etype=pin.etype,
                )
    return list(pins.values())


def _targets(designator: str, pins: list[Pin], ref: str, issues: list[Issue]) -> list[str]:
    """The pin numbers a designator names: itself when it is a pin number (the number wins over a name,
    with ``build.pin-ambiguous``), else every pin of that name; none gives ``build.unknown-pin``."""
    if designator in [p.number for p in pins]:
        if any(p.name == designator and p.number != designator for p in pins):
            issues.append(
                issue(
                    "build.pin-ambiguous",
                    f"{ref} {designator}: a pin number that is also another pin's name; the number wins",
                    ref,
                )
            )
        return [designator]
    targets = [p.number for p in pins if p.name == designator]
    if not targets:
        issues.append(
            issue("build.unknown-pin", f"{ref} {designator}: neither a pin number nor a pin name", ref)
        )
    return targets


def _resolve_pins(
    design: Design, parts: list[_Part], issues: list[Issue]
) -> tuple[dict[str, list[Pin]], dict[str, dict[str, str]]]:
    """Pins per component id, and the net id of each connected pin number per component id."""
    pins = {p.component.id: _pins(p.symbol, p.path) for p in parts}
    refs = {p.component.id: p.component.ref for p in parts}
    on_net: dict[str, dict[str, str]] = {cid: {} for cid in pins}
    for net in sorted(design.circuit.nets, key=lambda n: n.name):
        for member in net.members:
            if member.component_id not in pins:
                continue
            ref = refs[member.component_id]
            for number in _targets(member.pin, pins[member.component_id], ref, issues):
                current = on_net[member.component_id].get(number)
                if current is not None and current != net.id:
                    issues.append(issue("build.pin-on-two-nets", f"{ref} pin {number} is on two nets", ref))
                    continue
                on_net[member.component_id][number] = net.id
    return pins, on_net


def _resolve_marks(
    design: Design,
    parts: list[_Part],
    pins: Mapping[str, list[Pin]],
    on_net: Mapping[str, Mapping[str, str]],
    issues: list[Issue],
) -> tuple[PinRef, ...]:
    """The no-connect marks of ``design`` as pin numbers, in ``PinRef`` order without duplicates. A mark
    is resolved like a net member; a marked pin that a net lists gives ``build.no-connect-on-net`` and is
    left out, and a mark on a component the build does not hold is kept for ``Design.validate()``."""
    refs = {p.component.id: p.component.ref for p in parts}
    names = {n.id: n.name for n in design.circuit.nets}
    marks: set[PinRef] = set()
    for mark in sorted(design.circuit.no_connects):
        if mark.component_id not in pins:
            marks.add(mark)
            continue
        ref = refs[mark.component_id]
        for number in _targets(mark.pin, pins[mark.component_id], ref, issues):
            net_id = on_net[mark.component_id].get(number)
            if net_id is not None:
                issues.append(
                    issue(
                        "build.no-connect-on-net",
                        f"{ref} pin {number} is marked as not connected and is on net {names[net_id]}",
                        ref,
                        "remove the mark or take the pin off the net",
                    )
                )
                continue
            marks.add(PinRef(mark.component_id, number))
    return tuple(sorted(marks))


def _case_collisions(design: Design, issues: list[Issue]) -> None:
    for what, names in (
        ("net", [n.name for n in design.circuit.nets]),
        ("class", [c.name for c in design.circuit.netclasses]),
    ):
        seen: dict[str, str] = {}
        for name in sorted(names):
            other = seen.get(name.lower())
            if other is not None and other != name:
                issues.append(
                    issue(
                        "build.name-case-collision",
                        f"{what} names {other!r} and {name!r} differ only in letter case",
                        name,
                    )
                )
            seen.setdefault(name.lower(), name)


def _user_properties(part: _Part, issues: list[Issue]) -> list[tuple[str, str]]:
    """The user properties to append to ``part``'s footprint, in code-point order, after the checks of
    "User properties on built footprints"; a property equal to a library property is not appended."""
    user = {k: v for k, v in part.component.properties.items() if k != PATH_PROPERTY}
    library = {name.casefold(): (name, value) for name, value in part.footprint.properties.items()}
    folded: dict[str, str] = {}
    out: list[tuple[str, str]] = []
    for name in sorted(user):
        value = user[name]
        key = name.casefold()
        reserved = any(r.casefold() == key for r in RESERVED_PROPERTIES) or key.startswith(RESERVED_PREFIXES)
        if reserved:
            issues.append(
                issue(
                    "build.property-reserved",
                    f"{part.path}: property {name!r} has a reserved name",
                    part.path,
                )
            )
            continue
        if not name or name != name.strip() or not name.isprintable() or not value.isprintable():
            issues.append(
                issue(
                    "build.property-invalid",
                    f"{part.path}: property {name!r} must be printable text, "
                    "its name without surrounding spaces",
                    part.path,
                )
            )
            continue
        if key in folded:
            issues.append(
                issue(
                    "build.property-invalid",
                    f"{part.path}: properties {folded[key]!r} and {name!r} differ only in letter case",
                    part.path,
                )
            )
            continue
        folded[key] = name
        own = library.get(key)
        if own is not None:
            if own == (name, value):
                continue
            issues.append(
                issue(
                    "build.property-conflict",
                    f"{part.path}: property {name!r} conflicts with the footprint's {own[0]!r} = {own[1]!r}",
                    part.path,
                )
            )
            continue
        out.append((name, value))
    return out


def _staging(design: Design) -> tuple[int, int]:
    assert design.board is not None and design.board.outline is not None
    points = design.board.outline.points
    return max(p.x for p in points) + STAGING_OFFSET, min(p.y for p in points)


def build_design(
    design: Design,
    placements: Mapping[str, PlacementRequest],
    *,
    name: str,
    copper: Literal[2, 4],
    resolver: LibraryResolver,
    target: int = versions.DEFAULT_TARGET,
    allow_lossy: bool = False,
    vendor: Literal["all", "project"] = "all",
    record: Mapping[str, str] | None = None,
    prepared: Prepared | None = None,
    copper_intents: Sequence[CopperIntentLike] = (),
) -> BuildOutput:
    """Every file of the built project as bytes, or no file when an issue is an error.

    ``vendor`` is ``"all"`` (every placed footprint is copied into ``lib/``) or ``"project"`` (only those
    of project rows); ``record`` holds the hashes of the last build, for ``build.library-changed``.
    ``copper_intents`` are resolved into tracks and vias after the parts are placed, so script copper
    follows a footprint that an existing board placed elsewhere (``docs/copper.md``).
    """
    if vendor not in VENDOR_MODES:  # pyright: ignore[reportUnnecessaryContains]
        raise ValueError(f"unknown vendoring policy {vendor!r}; use one of: {', '.join(VENDOR_MODES)}")
    issues: list[Issue] = [*prepared.issues] if prepared is not None else []
    parts, libraries = _resolve(design, resolver, issues)
    plan = _vendor_plan(parts, vendor, issues)
    pins, on_net = _resolve_pins(design, parts, issues)
    marks = _resolve_marks(design, parts, pins, on_net, issues)
    _case_collisions(design, issues)
    for itf in design.circuit.interfaces:
        if itf.kind == "diff_pair":
            issues.append(
                issue(
                    "build.interface-not-lowered", f"diff pair {itf.name} is kept in the model only", itf.name
                )
            )
    board = design.board
    if board is None or board.outline is None:
        issues.append(issue("build.no-board", "the design has no board(); nothing can be placed", "board"))
        return _refused(design, issues, libraries)
    layers = tuple(
        dataclasses.replace(layer, id=derived_id("lay", DSL_BACKEND, f"layer:{layer.name}"))
        for layer in created_layers(copper)
    )
    copper_names = tuple(layer.name for layer in layers if layer.kind == "copper")
    cursor, top = _staging(design)
    components: list[Component] = []
    footprints: list[FootprintInstance] = []
    placed: list[str] = []
    staged: list[str] = []
    bottom = False
    written_properties = False
    for part in parts:
        extended = with_property(part.footprint, name=PATH_PROPERTY, value=part.path)
        for prop_name, prop_value in _user_properties(part, issues):
            extended = with_property(extended, name=prop_name, value=prop_value)
            written_properties = True
        component = dataclasses.replace(
            part.component,
            pins=tuple(pins[part.component.id]),
            properties=dict(
                sorted(
                    {
                        **extended.properties,
                        "Reference": part.component.ref,
                        "Value": part.component.value,
                    }.items()
                )
            ),
        )
        request = placements.get(part.path)
        if request is None:
            box = footprint_extent(part.footprint)
            at = Point(cursor - box.x0, top - box.y0)
            cursor += (box.x1 - box.x0) + STAGING_GAP
            instance = place_footprint(
                extended, component=component, at=at, key=part.path, copper=copper_names
            )
            staged.append(part.path)
            issues.append(
                issue("layout.unplaced", f"{part.component.ref} was staged beside the outline", part.path)
            )
        else:
            instance = place_footprint(
                extended,
                component=component,
                at=request.at,
                rotation=request.rotation,
                side=request.side,
                locked=request.locked,
                key=part.path,
                copper=copper_names,
            )
            placed.append(part.path)
            bottom = bottom or request.side == "bottom"
        instance = dataclasses.replace(
            instance,
            pads=_pad_nets(instance.pads, pins[part.component.id], on_net[part.component.id], part, issues),
        )
        components.append(component)
        footprints.append(instance)
    nets = tuple(
        dataclasses.replace(
            net,
            members=tuple(
                sorted(
                    PinRef(cid, number)
                    for cid, numbers in on_net.items()
                    for number, nid in numbers.items()
                    if nid == net.id
                )
            ),
        )
        for net in design.circuit.nets
    )
    built = dataclasses.replace(
        design,
        circuit=dataclasses.replace(
            design.circuit, components=tuple(components), nets=nets, no_connects=marks
        ),
        board=dataclasses.replace(board, layers=layers, footprints=tuple(footprints)),
    )
    copper_counts = {"intents": len(copper_intents), "tracks": 0, "vias": 0}
    if copper_intents:
        assert built.board is not None
        built = resolve_copper(built, copper_intents, unplaced=staged, issues=issues)
        assert built.board is not None
        for kind, items in (("tracks", built.board.tracks), ("vias", built.board.vias)):
            copper_counts[kind] = sum(1 for i in items if is_copper_uuid(i.native_ids.get("kicad", "")))
    existing = prepared.existing if prepared is not None else preserve.ExistingProject()
    board_read = prepared is not None and prepared.board is not None
    preserved: dict[str, object] = {}
    target_design = built
    if prepared is not None and prepared.board is not None and prepared.match is not None:
        merged = preserve.merge_layout(built, prepared.board, prepared.match)
        issues += merged.issues
        preserved.update(merged.summary)
        target_design = merged.design
    issues += list(target_design.validate())
    if any(i.severity == "error" for i in issues):
        return _refused(built, issues, libraries)
    texts = write_triad(
        target_design,
        name=name,
        target=target,
        existing_project=existing.project,
        allow_lossy=allow_lossy,
        issues=issues,
    )
    pcb_name, pro_name, dru_name = (f"{name}.kicad_pcb", f"{name}.kicad_pro", f"{name}.kicad_dru")
    if existing.rules is not None:
        texts[dru_name] = preserve.merge_rules(
            texts[dru_name],
            existing.rules,
            target=target,
            file=dru_name,
            allow_lossy=allow_lossy,
            issues=issues,
        )
    if prepared is not None and prepared.board is not None:
        stale, fill_issues = preserve.drop_stale_fills(
            prepared.board, target_design, existing=existing, project=texts[pro_name], rules=texts[dru_name]
        )
        if fill_issues:
            issues += fill_issues
            written = write_board(stale, target=target, allow_lossy=allow_lossy)
            texts[pcb_name] = written.text
        preserved["fills"] = preserve.fill_counts(prepared.board, stale)
    files: dict[str, bytes] = {n: t.encode("utf-8") for n, t in texts.items()}
    readback = read_board(texts[pcb_name], file=pcb_name, issues=[])
    layout = preserve.merge_layout(built, readback, preserve.match_footprints(built, readback)).design
    vendored = _vendor(plan, target, files, record, issues)
    rows = tuple(
        LibRow(nick, "KiCad", f"${{KIPRJMOD}}/lib/{nick}.pretty") for nick in sorted({n for n, _ in vendored})
    )
    files["fp-lib-table"] = write_lib_table(LibTable("footprint", rows), target=target).encode("utf-8")
    record = {path: hashlib.sha256(data).hexdigest() for path, data in sorted(files.items())}
    for file_name, text in canonical.dump_texts(layout).items():
        files[f"{CACHE_DIR}/{file_name}"] = text.encode("utf-8")
    files[RECORD_FILE] = (
        json.dumps(
            {"design": name, "files": record, "schema": RECORD_SCHEMA, "target": target},
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")
    evidence_items = [
        BUILD_EVIDENCE,
        sym.EVIDENCE,
        mod.EVIDENCE,
        WRITE_EVIDENCE,
        pro.EVIDENCE,
        lowering.EVIDENCE,
    ]
    if bottom:
        evidence_items.append(embed.EVIDENCE)
    if written_properties:
        evidence_items.append(PROPERTY_EVIDENCE)
    if any(location.origin != "project" for location in plan.values()):
        evidence_items.append(VENDOR_EVIDENCE)
    if board_read:
        evidence_items += [preserve.EVIDENCE, pcb.EVIDENCE]
    if existing.rules is not None:
        evidence_items.append(dru.EVIDENCE)
    if copper_intents:
        evidence_items += [copper_mod.EVIDENCE, frame.EVIDENCE]
    merged_copper = cast(Mapping[str, int], preserved.get("copper", {}))
    summary: dict[str, object] = {
        "components": len(components),
        "nets": len(nets),
        "placed": placed,
        "staged": staged,
        "vendored": [f"lib/{nick}.pretty/{entry}" for nick, entry in vendored],
        "libraries": libraries,
        "preserved": _preserved(prepared, preserved),
        "copper": {
            **copper_counts,
            **{key: merged_copper.get(key, 0) for key in ("regenerated", "stale", "duplicates")},
        },
    }
    return BuildOutput(
        built, dict(sorted(files.items())), tuple(issues), Evidence.combine(*evidence_items), summary, layout
    )


def _preserved(prepared: Prepared | None, merged: Mapping[str, object]) -> dict[str, object]:
    """``result.preserved`` (``layout-lens``, "Layout preservation evidence")."""
    zero = {"tracks": 0, "arcs": 0, "vias": 0, "zones": 0}
    return {
        "board": prepared is not None and prepared.board is not None,
        "kept": merged.get("kept", []),
        "replaced": merged.get("replaced", []),
        "added": merged.get("added", []),
        "orphans": merged.get("orphans", []),
        "board_only": merged.get("board_only", []),
        "dropped": merged.get("dropped", zero),
        "fills": merged.get("fills", {"kept": 0, "dropped": 0}),
        "aliases": dict(prepared.aliases) if prepared is not None else {},
        "reader_infos": prepared.reader_infos if prepared is not None else 0,
    }


def _refused(design: Design, issues: list[Issue], libraries: Mapping[str, str]) -> BuildOutput:
    summary: dict[str, object] = {
        "components": len(design.circuit.components),
        "nets": len(design.circuit.nets),
        "placed": [],
        "staged": [],
        "vendored": [],
        "libraries": dict(libraries),
        "preserved": _preserved(None, {}),
    }
    return BuildOutput(design, {}, tuple(issues), BUILD_EVIDENCE, summary)


def _pad_nets(
    pads: tuple[Pad, ...], pins: list[Pin], on_net: Mapping[str, str], part: _Part, issues: list[Issue]
) -> tuple[Pad, ...]:
    numbers = {p.number for p in pins}
    pad_numbers = {p.number for p in pads if p.number}
    ref = part.component.ref
    for number in sorted(pad_numbers - numbers):
        issues.append(
            issue("build.pad-without-pin", f"{ref} pad {number} has no pin of its number", part.path)
        )
    for pin in pins:
        if pin.number in pad_numbers:
            continue
        if pin.number in on_net:
            issues.append(
                issue(
                    "build.pin-without-pad", f"{ref} pin {pin.number} is connected but has no pad", part.path
                )
            )
        else:
            issues.append(
                issue("build.unused-pin-without-pad", f"{ref} pin {pin.number} has no pad", part.path)
            )
    return tuple(dataclasses.replace(p, net_id=on_net.get(p.number)) if p.number else p for p in pads)


def _vendor_plan(
    parts: list[_Part], vendor: Literal["all", "project"], issues: list[Issue]
) -> dict[str, Location]:
    """Vendored path → the location it is copied from, with ``build.global-library`` for the footprints
    left out by ``vendor="project"`` and ``build.vendor-unsafe-name`` for unsafe nicknames."""
    plan: dict[str, Location] = {}
    for part in parts:
        location = part.location
        nick, entry = location.row.nickname, location.item_path.name
        if vendor == "project" and location.origin != "project":
            issues.append(
                issue(
                    "build.global-library",
                    f"{location.lib_id} comes from a {location.origin} row and is not vendored",
                    location.lib_id,
                )
            )
            continue
        if any(c in nick for c in "/\\") or not nick.isprintable():
            issues.append(
                issue(
                    "build.vendor-unsafe-name",
                    f"nickname {nick!r} of {location.lib_id} cannot name a folder under lib/",
                    nick,
                )
            )
            continue
        plan.setdefault(f"lib/{nick}.pretty/{entry}", location)
    folded: dict[str, str] = {}
    for path in sorted(plan):
        other = folded.setdefault(path.casefold(), path)
        if other != path:
            issues.append(
                issue(
                    "build.vendor-unsafe-name",
                    f"vendored paths {other!r} and {path!r} differ only in letter case",
                    path,
                )
            )
    return plan


def _vendor(
    plan: Mapping[str, Location],
    target: int,
    files: dict[str, bytes],
    record: Mapping[str, str] | None,
    issues: list[Issue],
) -> list[tuple[str, str]]:
    """Copy each planned footprint byte for byte; report newer formats and changed libraries."""
    vendored: list[tuple[str, str]] = []
    newest = versions.FORMAT_VERSIONS[versions.FileKind.FOOTPRINT][target]
    for path, location in sorted(plan.items()):
        data = location.item_path.read_bytes()
        files[path] = data
        vendored.append((location.row.nickname, location.item_path.name))
        version = versions.detect_version(parse_bytes(data, file=path))
        if version > newest:
            issues.append(
                issue(
                    "build.library-too-new",
                    f"{path} has format version {version}, newer than KiCad {target}.0's {newest}",
                    path,
                )
            )
        recorded = None if record is None else record.get(path)
        if recorded is not None and recorded != hashlib.sha256(data).hexdigest():
            issues.append(
                issue(
                    "build.library-changed",
                    f"{path} differs from the copy of the last build: its library changed",
                    path,
                )
            )
    return sorted(vendored)


# --- edited outputs -------------------------------------------------------------------------------


def read_record(out_dir: Path) -> Mapping[str, str] | None:
    """The hashes of ``.fenolite/build.json``, or ``None`` when it is missing, unreadable or foreign."""
    try:
        data = json.loads((out_dir / RECORD_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    record = cast(dict[str, object], data)
    files = record.get("files")
    if record.get("schema") != RECORD_SCHEMA or not isinstance(files, dict):
        return None
    return {str(k): v for k, v in cast(dict[object, object], files).items() if isinstance(v, str)}


def check_existing(
    out_dir: Path, files: Mapping[str, bytes], *, record: Mapping[str, str] | None, discard_layout: bool
) -> None:
    """Refuse to replace an output changed since Fenolite last wrote it (``LayoutExistsError``)."""
    if discard_layout:
        return
    found: list[Issue] = []
    for rel, data in sorted(files.items()):
        if rel.startswith(f"{CACHE_DIR}/"):
            continue
        path = out_dir / rel
        if not path.is_file():
            continue
        current = path.read_bytes()
        if current == data:
            continue
        if record is not None and record.get(rel) == hashlib.sha256(current).hexdigest():
            continue
        found.append(
            issue("build.layout-exists", f"{path} changed since the last build", str(path), LAYOUT_HINT)
        )
    if found:
        raise LayoutExistsError(found)


__all__ = [
    "BUILD_EVIDENCE",
    "BUILD_ISSUE_CODES",
    "PROPERTY_EVIDENCE",
    "RECORD_FILE",
    "RECORD_SCHEMA",
    "RESERVED_PREFIXES",
    "RESERVED_PROPERTIES",
    "STAGING_GAP",
    "STAGING_OFFSET",
    "VENDOR_EVIDENCE",
    "VENDOR_MODES",
    "BuildOutput",
    "LayoutExistsError",
    "PlacementRequest",
    "UnresolvedLibrariesError",
    "build_design",
    "check_existing",
    "read_record",
]
