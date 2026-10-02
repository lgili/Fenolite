# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Building a model design into a self-contained KiCad project (``docs/dsl.md``, "Build").

``build_design`` resolves libraries, fills pins, places and stages parts, checks, writes the triad
through ``triad.write_triad``, vendors the project-table footprints with a per-target ``fp-lib-table``,
and adds the ``.fenolite/`` layer texts and build record. A design with an error gives no file.
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

from fenolite.backends.kicad import embed, lowering, mod, pro, sym, versions
from fenolite.backends.kicad.embed import PATH_PROPERTY, footprint_extent, place_footprint, with_property
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryResolver, LibRow, LibTable, Location, write_lib_table
from fenolite.backends.kicad.pcb import WRITE_EVIDENCE
from fenolite.backends.kicad.sexpr import parse_bytes
from fenolite.backends.kicad.triad import write_triad
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Udeg
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
        "build.no-footprint": "error",
        "build.no-board": "error",
        "build.name-case-collision": "error",
        "build.layout-exists": "error",
        "build.pin-ambiguous": "warning",
        "build.unused-pin-without-pad": "warning",
        "build.library-too-new": "warning",
        "layout.unplaced": "warning",
        "build.pad-without-pin": "info",
        "build.global-library": "info",
        "build.interface-not-lowered": "info",
    }
)
BUILD_EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=("H-K-BUILD-TRIAD", "H-K-BUILD-CLASS", "H-K-BUILD-LIBTABLE", "H-K-BUILD-PATHPROP"),
)
"""The blink is proved by the build oracle; arbitrary designs reach forms the oracle has not run."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, BUILD_ISSUE_CODES[code], message, where=where, hint=hint)


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
    design: Design
    files: Mapping[str, bytes]
    issues: tuple[Issue, ...]
    evidence: Evidence
    summary: Mapping[str, object]


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
            numbers = [p.number for p in pins[member.component_id]]
            ref = refs[member.component_id]
            if member.pin in numbers:
                targets = [member.pin]
                if any(p.name == member.pin and p.number != member.pin for p in pins[member.component_id]):
                    issues.append(
                        issue(
                            "build.pin-ambiguous",
                            f"{ref} {member.pin}: a pin number that is also another pin's name; "
                            "the number wins",
                            ref,
                        )
                    )
            else:
                targets = [p.number for p in pins[member.component_id] if p.name == member.pin]
                if not targets:
                    issues.append(
                        issue(
                            "build.unknown-pin",
                            f"{ref} {member.pin}: neither a pin number nor a pin name",
                            ref,
                        )
                    )
                    continue
            for number in targets:
                current = on_net[member.component_id].get(number)
                if current is not None and current != net.id:
                    issues.append(issue("build.pin-on-two-nets", f"{ref} pin {number} is on two nets", ref))
                    continue
                on_net[member.component_id][number] = net.id
    return pins, on_net


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
) -> BuildOutput:
    """Every file of the built project as bytes, or no file when an issue is an error."""
    issues: list[Issue] = []
    parts, libraries = _resolve(design, resolver, issues)
    pins, on_net = _resolve_pins(design, parts, issues)
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
    for part in parts:
        extended = with_property(part.footprint, name=PATH_PROPERTY, value=part.path)
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
        circuit=dataclasses.replace(design.circuit, components=tuple(components), nets=nets),
        board=dataclasses.replace(board, layers=layers, footprints=tuple(footprints)),
    )
    issues += list(built.validate())
    if any(i.severity == "error" for i in issues):
        return _refused(built, issues, libraries)
    files: dict[str, bytes] = {
        n: t.encode("utf-8")
        for n, t in write_triad(
            built, name=name, target=target, allow_lossy=allow_lossy, issues=issues
        ).items()
    }
    vendored = _vendor(parts, target, files, issues)
    rows = tuple(
        LibRow(nick, "KiCad", f"${{KIPRJMOD}}/lib/{nick}.pretty") for nick in sorted({n for n, _ in vendored})
    )
    files["fp-lib-table"] = write_lib_table(LibTable("footprint", rows), target=target).encode("utf-8")
    record = {path: hashlib.sha256(data).hexdigest() for path, data in sorted(files.items())}
    for file_name, text in canonical.dump_texts(built).items():
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
    summary: dict[str, object] = {
        "components": len(components),
        "nets": len(nets),
        "placed": placed,
        "staged": staged,
        "vendored": [f"lib/{nick}.pretty/{entry}" for nick, entry in vendored],
        "libraries": libraries,
    }
    return BuildOutput(
        built, dict(sorted(files.items())), tuple(issues), Evidence.combine(*evidence_items), summary
    )


def _refused(design: Design, issues: list[Issue], libraries: Mapping[str, str]) -> BuildOutput:
    summary: dict[str, object] = {
        "components": len(design.circuit.components),
        "nets": len(design.circuit.nets),
        "placed": [],
        "staged": [],
        "vendored": [],
        "libraries": dict(libraries),
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


def _vendor(
    parts: list[_Part], target: int, files: dict[str, bytes], issues: list[Issue]
) -> list[tuple[str, str]]:
    vendored: list[tuple[str, str]] = []
    newest = versions.FORMAT_VERSIONS[versions.FileKind.FOOTPRINT][target]
    for part in parts:
        location = part.location
        nick, entry = location.row.nickname, location.item_path.name
        if location.origin != "project":
            issues.append(
                issue(
                    "build.global-library",
                    f"{location.lib_id} comes from a {location.origin} row and is not vendored",
                    location.lib_id,
                )
            )
            continue
        path = f"lib/{nick}.pretty/{entry}"
        if path in files:
            continue
        data = location.item_path.read_bytes()
        files[path] = data
        vendored.append((nick, entry))
        version = versions.detect_version(parse_bytes(data, file=path))
        if version > newest:
            issues.append(
                issue(
                    "build.library-too-new",
                    f"{path} has format version {version}, newer than KiCad {target}.0's {newest}",
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
    "RECORD_FILE",
    "RECORD_SCHEMA",
    "STAGING_GAP",
    "STAGING_OFFSET",
    "BuildOutput",
    "LayoutExistsError",
    "PlacementRequest",
    "UnresolvedLibrariesError",
    "build_design",
    "check_existing",
    "read_record",
]
