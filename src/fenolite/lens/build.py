# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Building a model design into a self-contained KiCad project (``docs/dsl.md``, "Build").

``build_design`` resolves libraries, fills pins, places and stages parts with their user properties
and the script's field placements,
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
from typing import Literal, Protocol, TypeGuard, cast

from fenolite.backends.kicad import (
    boarditems,
    dru,
    embed,
    frame,
    lowering,
    mod,
    netnames,
    pcb,
    pro,
    rulemap,
    sch,
    sch_netlist,
    schgen,
    sym,
    symembed,
    versions,
    wks,
)
from fenolite.backends.kicad import copper as copper_mod
from fenolite.backends.kicad import lengths as lengths_mod
from fenolite.backends.kicad import meander as meander_mod
from fenolite.backends.kicad import stackup as stacklib
from fenolite.backends.kicad import via_protection as vialib
from fenolite.backends.kicad.copper import CopperIntentLike, is_copper_uuid, resolve_copper
from fenolite.backends.kicad.embed import (
    MANDATORY_FIELDS,
    PATH_PROPERTY,
    footprint_extent,
    place_footprint,
    uuid_locators,
    with_property,
)
from fenolite.backends.kicad.layers import created_layers, with_plane_types
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryResolver, LibRow, LibTable, Location, write_lib_table
from fenolite.backends.kicad.meander import MeanderIntentLike
from fenolite.backends.kicad.outline import (
    BoardOutline,
    board_outline,
    check_outline,
    outline_box,
    outline_case,
)
from fenolite.backends.kicad.pcb import WRITE_EVIDENCE, read_board, write_board
from fenolite.backends.kicad.schgen import GeneratedSchematic
from fenolite.backends.kicad.schlayout import SymbolPlacement
from fenolite.backends.kicad.sexpr import parse_bytes
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.zones import PadZoneRequestLike, apply_pad_connections, keep_pad_connections
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm, Udeg
from fenolite.lens import preserve
from fenolite.lens.fields import FieldRequestLike, apply_requests, merge_fields
from fenolite.lens.moved import identity_map
from fenolite.lens.preserve import PRESERVE_ISSUE_CODES, Prepared
from fenolite.model import canonical, pairs
from fenolite.model.board import ComponentBody, FootprintInstance, Pad, Side, ViaProtection
from fenolite.model.circuit import Component, Interface, Net, Pin, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef, SymbolDef
from fenolite.model.presentation import DrawingSheet
from fenolite.model.rules import Rule, RuleSubject, Selector
from fenolite.model.schematic import SchematicSheet

RECORD_FILE = ".fenolite/build.json"
SHEET_SUFFIX = ".kicad_wks"
"""The drawing sheet of a build is ``<name>.kicad_wks``, beside the project file."""
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
        "build.pin-pad-map-invalid": "error",
        "build.no-connect-on-net": "error",
        "build.no-footprint": "error",
        "build.no-board": "error",
        "build.name-case-collision": "error",
        "build.layout-exists": "error",
        "build.property-reserved": "error",
        "build.property-invalid": "error",
        "build.property-conflict": "error",
        "build.vendor-unsafe-name": "error",
        "build.schematic-netlist-differs": "error",
        "build.area-unknown": "error",
        "build.pin-ambiguous": "warning",
        "build.unused-pin-without-pad": "warning",
        "build.library-too-new": "warning",
        "build.library-changed": "warning",
        "build.diff-pair-name": "warning",
        "build.diff-pair-gap-shadowed": "warning",
        "build.i2c-pullup-missing": "warning",
        "build.pad-map-default": "warning",
        "layout.unplaced": "warning",
        "build.pad-without-pin": "info",
        "build.global-library": "info",
        "build.field-added": "info",
        "build.interface-not-lowered": "info",
        "build.plane-zone-missing": "warning",
        **{code: severity for code, severity in schgen.ISSUE_CODES.items() if code.startswith("build.")},
        **PRESERVE_ISSUE_CODES,
    }
)
BUILD_EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=("H-K-BUILD-TRIAD", "H-K-BUILD-CLASS", "H-K-BUILD-LIBTABLE", "H-K-BUILD-PATHPROP"),
)
AUTHORING_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-DSL-FOOTPRINT",))
"""The blink is proved by the build oracle; arbitrary designs reach forms the oracle has not run."""
PROPERTY_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-VENDOR-PROPS", "H-K-VENDOR-DUPNAME"))
"""Joins the envelope when a user property is written (c0027)."""
VENDOR_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-VENDOR-GLOBAL", "H-K-VENDOR-SHADOW"))
"""Joins the envelope when a footprint of a row whose origin is not ``project`` is vendored (c0027)."""
SCHEMATIC_MODES: tuple[str, ...] = ("write", "skip")
"""``schematic="write"`` adds the schematic, its symbol libraries and ``sym-lib-table``; ``"skip"`` gives
the files of a build without them (c0061)."""
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


def plane_issues(planes: Mapping[str, str], design: Design) -> list[Issue]:
    """One ``build.plane-zone-missing`` warning per internal plane of the script (layer name → net name)
    whose net has no zone on its layer in ``design``, the design the board is written from (the script's
    zones and those of the existing board). The KiCad target gives the layer the row type ``power`` and
    writes no copper for the plane: the zone is the copper (change c0107). The hint names the script call
    that draws it (change c0100)."""
    board = design.board
    by_id = {net.id: net.name for net in design.circuit.nets}
    covered = {
        (layer, by_id.get(zone.net_id or ""))
        for zone in (board.zones if board is not None else ())
        for layer in zone.layers
    }
    return [
        issue(
            "build.plane-zone-missing",
            f"the plane on {layer} (net {net}) has no copper: no zone of {net} lies on {layer}; "
            f"the layer is written as a plane layer (type power) all the same",
            layer,
            f'draw that copper in the script: design.zone(<the net {net}>, layers=("{layer}",))',
        )
        for layer, net in planes.items()
        if (layer, net) not in covered
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
    schematic: GeneratedSchematic | None = None
    """The generated sheet and what the board takes from it (unconnected-pad names, symbol paths), or
    ``None`` when the schematic is skipped or no file is returned (c0061)."""


@dataclass
class _Part:
    component: Component
    path: str
    symbol: SymbolDef
    footprint: FootprintDef
    location: Location | None
    parents: tuple[SymbolDef, ...] = ()
    """The symbols ``symbol`` extends, as their library holds them (the schematic embeds a flat copy)."""
    symbol_origin: str = "project"
    """The origin of the row that resolved the symbol, or ``authored``."""


def _path(component: Component) -> str:
    return component.properties.get(PATH_PROPERTY, component.ref)


def _resolve(
    design: Design,
    resolver: LibraryResolver,
    issues: list[Issue],
    authored: Mapping[str, FootprintDef] = MappingProxyType({}),
    authored_symbols: Mapping[str, SymbolDef] = MappingProxyType({}),
) -> tuple[list[_Part], dict[str, str]]:
    errors: list[LibraryError] = []
    libraries: dict[str, str] = {}
    found: list[_Part] = []
    for component in sorted(design.circuit.components, key=_path):
        parents: tuple[SymbolDef, ...] = ()
        try:
            if component.lib_symbol_ref in authored_symbols:
                symbol = authored_symbols[component.lib_symbol_ref]
                libraries[component.lib_symbol_ref] = "authored"
            else:
                chain = resolver.symbol_chain(component.lib_symbol_ref)
                symbol, parents = sym.resolve_extends(chain)[0], chain[1:]
                libraries[component.lib_symbol_ref] = resolver.locate(
                    component.lib_symbol_ref, "symbol"
                ).origin
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
        if fp_ref in authored:
            location = None
            footprint = mod.prepare_authored_definition(authored[fp_ref])
            libraries[fp_ref] = "authored"
        else:
            try:
                location = resolver.locate(fp_ref, "footprint")
                footprint = resolver.footprint(fp_ref)
            except LibraryError as error:
                errors.append(error)
                continue
            libraries[fp_ref] = location.origin
        value = component.value or symbol.properties.get("Value", "")
        component = dataclasses.replace(component, lib_footprint_ref=fp_ref, value=value)
        origin = libraries[component.lib_symbol_ref]
        found.append(_Part(component, _path(component), symbol, footprint, location, parents, origin))
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


PAIR_WORDS: Mapping[str, str] = MappingProxyType({"diff_pair": "diff pair", "usb2": "USB 2.0 pair"})
"""Pair interface kind (``model.pairs.PAIR_ROLES``) → the words of its messages."""


def is_pair(first: str, second: str) -> bool:
    """Whether KiCad takes the two net names as one differential pair, the positive one first
    (``model.pairs.pair_base``, ``H-K-DIFFPAIR-NAMES-2``): equal except for a polarity character, ``P``
    then ``N`` or ``+`` then ``-``, which only digits and ``_`` may follow; letter case counts."""
    return pairs.pair_base(first, second) is not None


def pair_hint(first: str, second: str) -> str:
    """The names to use instead of a pair that ``is_pair`` refuses."""
    split = pairs.split_pair_name(first)
    if split is not None and split.polarity in pairs.POSITIVE:
        return f"name the second net {pairs.coupled_name(first)}: KiCad pairs it with {first}, not {second}"
    return (
        f"name the nets {first}_P and {first}_N: KiCad pairs names that hold P and N, or + and -, "
        "followed by nothing but digits and underscores"
    )


def _leaves(selector: Selector | None, op: str) -> list[Selector]:
    if selector is None:
        return []
    if selector.items:
        return [leaf for item in selector.items for leaf in _leaves(item, op)]
    return [selector] if selector.op == op else []


def _fold(selector: Selector) -> Selector:
    """``selector`` as the copper check compares it (``checks.clearance``, which this package may not
    import): every leaf value without letter case, a ``diff_pair`` leaf with it."""
    if selector.items:
        return dataclasses.replace(selector, items=tuple(_fold(item) for item in selector.items))
    if selector.op in ("all", "diff_pair"):
        return selector
    return dataclasses.replace(selector, value=selector.value.casefold())


def _selects(rule: Rule, a: RuleSubject, b: RuleSubject) -> bool:
    """Whether a rule holds between two track subjects, as the copper check decides it."""
    if rule.layers and a.layer not in {layer.casefold() for layer in rule.layers}:
        return False
    first = _fold(rule.selector_a)
    if rule.selector_b is None:
        return first.matches(a) or first.matches(b)
    second = _fold(rule.selector_b)
    return (first.matches(a) and second.matches(b)) or (first.matches(b) and second.matches(a))


def pair_gap_issue(
    design: Design, itf: Interface, first: Net, second: Net, base: str, *, target: int, layers: Sequence[str]
) -> Issue | None:
    """``build.diff-pair-gap-shadowed`` for one pair whose nets share a class with a pair gap ``g``, when
    KiCad would report two tracks of the pair ``g`` apart (``H-K-PRO-PAIR``): the clearance in force
    between them on a copper layer is above ``g`` (the value of the copper check, "Clearance in force"
    and "Clearance between the nets of a differential pair", with the switches of ``target``), or the board
    minimum clearance that the build writes is above ``g`` and no ``diff_pair_gap`` rule selects the pair."""
    classes = {c.id: c for c in design.circuit.netclasses}
    cls = classes.get(first.netclass_id or "")
    if cls is None or first.netclass_id != second.netclass_id or cls.diff_pair_gap is None:
        return None
    gap = cls.diff_pair_gap
    ruleset = design.rules
    ordered = rulemap.rule_order(ruleset.rules if ruleset is not None else ())
    floor = lowering.lower_minimums(ruleset, target=target, current={}).get("min_clearance")
    over_classes = target in lowering.RULES_OVER_CLASSES
    over_rules = target in lowering.FLOOR_OVER_RULES.get("min_clearance", frozenset())
    words = PAIR_WORDS[itf.kind]
    hint = (
        "design.rules.pair(…, clearance=…, gap_min=…) writes a clearance rule and a gap rule for the "
        "pair, after the rules that shadow its class gap"
    )

    def text(nm: int) -> str:
        return lowering.millimetres(nm).text

    def found(what: str) -> Issue:
        return issue(
            "build.diff-pair-gap-shadowed",
            f"{words} {itf.name}: the nets {first.name} and {second.name} are in the class {cls.name}, "
            f"whose pair gap is {text(gap)} mm, but {what}; KiCad reports two tracks of the pair laid "
            "at that gap",
            itf.name,
            hint,
        )

    # the class value inside the pair: the pair gap where it is below the class clearance
    inside = cls.clearance if cls.clearance is not None and cls.clearance <= gap else gap
    for layer in layers:
        a, b = (
            RuleSubject(
                "track",
                net=net.name.casefold(),
                netclass=cls.name.casefold(),
                layer=layer.casefold(),
                diff_pair=base,
            )
            for net in (first, second)
        )
        governing = next(
            (
                rule
                for rule in reversed(ordered)
                if rule.kind == "clearance" and rule.min is not None and _selects(rule, a, b)
            ),
            None,
        )
        if governing is None or governing.severity == "ignore" or governing.min is None:
            continue
        if not over_classes and inside > governing.min:
            continue
        if governing.min > gap and not (over_rules and floor is not None and floor > governing.min):
            return found(
                f"the clearance rule {governing.name!r} ({text(governing.min)} mm) governs between them"
            )
    if floor is not None and floor > gap:
        subjects = [
            RuleSubject("track", net=net.name.casefold(), netclass=cls.name.casefold(), diff_pair=base)
            for net in (first, second)
        ]
        gap_rule = any(
            rule.kind == "diff_pair_gap" and any(_fold(rule.selector_a).matches(x) for x in subjects)
            for rule in ordered
        )
        if not gap_rule:
            return found(
                f"the board minimum clearance that the build writes is {text(floor)} mm and no "
                "diff_pair_gap rule selects the pair"
            )
    return None


def interface_checks(
    design: Design,
    pins: Mapping[str, Sequence[Pin]],
    on_net: Mapping[str, Mapping[str, str]],
    *,
    target: int = versions.DEFAULT_TARGET,
    layers: Sequence[str] = ("F.Cu", "B.Cu"),
) -> list[Issue]:
    """What a build says about the interfaces of ``design`` (changes c0073 and c0104): one info per pair
    that no rule selects, ``build.diff-pair-name`` for a pair whose names KiCad does not pair,
    ``build.diff-pair-gap-shadowed`` for a pair KiCad would report at its class gap, and
    ``build.i2c-pullup-missing`` for an I2C line without a two-pin part to the ``hv`` net of a ``power``
    interface. ``pins`` and ``on_net`` are those of ``_resolve_pins``; ``layers`` are the copper layers of
    the board. Nothing is changed."""
    found: list[Issue] = []
    nets = {net.id: net for net in design.circuit.nets}
    names = {net.id: net.name for net in design.circuit.nets}
    rules = design.rules.rules if design.rules is not None else ()
    pair_leaves = [
        leaf
        for rule in rules
        for leaf in (*_leaves(rule.selector_a, "diff_pair"), *_leaves(rule.selector_b, "diff_pair"))
    ]
    supplies = {i.members["hv"] for i in design.circuit.interfaces if i.kind == "power" and "hv" in i.members}
    for itf in design.circuit.interfaces:
        if itf.kind in pairs.PAIR_ROLES:
            words = PAIR_WORDS[itf.kind]
            ids = pairs.pair_nets(itf)
            first, second = (nets.get(ids[0]), nets.get(ids[1])) if ids is not None else (None, None)
            base = (
                pairs.pair_base(first.name, second.name) if first is not None and second is not None else None
            )
            if base is None or not any(pairs.base_matches(base, leaf.value) for leaf in pair_leaves):
                found.append(
                    issue(
                        "build.interface-not-lowered",
                        f"{words} {itf.name} is kept in the model only: no rule of the design selects it, "
                        "so KiCad knows the pair by its net names only",
                        itf.name,
                    )
                )
            if first is not None and second is not None and base is None:
                found.append(
                    issue(
                        "build.diff-pair-name",
                        f"{words} {itf.name}: KiCad does not take the nets {first.name} and {second.name} "
                        "as a differential pair, so its pair router and inDiffPair() do not find them",
                        itf.name,
                        pair_hint(first.name, second.name),
                    )
                )
            if first is not None and second is not None and base is not None:
                shadowed = pair_gap_issue(design, itf, first, second, base, target=target, layers=layers)
                if shadowed is not None:
                    found.append(shadowed)
        elif itf.kind == "i2c":
            for line in ("sda", "scl"):
                net_id = itf.members.get(line)
                if net_id is None or _pulled_up(net_id, supplies, pins, on_net):
                    continue
                found.append(
                    issue(
                        "build.i2c-pullup-missing",
                        f"I2C interface {itf.name}: the line {line} (net {names.get(net_id, net_id)}) has no "
                        "pull-up to the hv net of a power interface",
                        itf.name,
                        "add a resistor from the line to the supply, or ignore this when the pull-up is on "
                        "another board; a pull-up of more than two pins is not recognised",
                    )
                )
    return found


def _pulled_up(
    net_id: str,
    supplies: set[str],
    pins: Mapping[str, Sequence[Pin]],
    on_net: Mapping[str, Mapping[str, str]],
) -> bool:
    for component_id, connected in on_net.items():
        if len(pins.get(component_id, ())) != 2 or len(connected) != 2:
            continue
        one, other = connected.values()
        if (one == net_id and other in supplies) or (other == net_id and one in supplies):
            return True
    return False


def _staging(design: Design) -> tuple[int, int]:
    """Where the staging row starts: right of the box of the outline, arcs included, at its top."""
    box = outline_box(design)
    assert box is not None
    return box[2] + STAGING_OFFSET, box[1]


def height_body(path: str, height: Nm) -> ComponentBody:
    """The body of a part whose script states its height (change c0140): extruded, standoff 0, no outline
    and no signed bounds; ``outward_height`` reads ``height`` as its top."""
    return ComponentBody(
        id=derived_id("bdy", DSL_BACKEND, f"height:{path}"), kind="extruded", height=height, name="height"
    )


def build_design(
    design: Design,
    placements: Mapping[str, PlacementRequest],
    *,
    name: str,
    copper: int,
    resolver: LibraryResolver,
    target: int = versions.DEFAULT_TARGET,
    allow_lossy: bool = False,
    vendor: Literal["all", "project"] = "all",
    record: Mapping[str, str] | None = None,
    prepared: Prepared | None = None,
    copper_intents: Sequence[CopperIntentLike] = (),
    meanders: Sequence[MeanderIntentLike] = (),
    fields: Mapping[str, Sequence[FieldRequestLike]] = MappingProxyType({}),
    pad_zones: Mapping[str, Sequence[PadZoneRequestLike]] = MappingProxyType({}),
    authored_footprints: Mapping[str, FootprintDef] = MappingProxyType({}),
    authored_symbols: Mapping[str, SymbolDef] = MappingProxyType({}),
    source_sha256: str | None = None,
    drawing_sheet: DrawingSheet | None = None,
    schematic: Literal["write", "skip"] = "write",
    symbol_placements: Mapping[str, SymbolPlacement] | None = None,
    schematic_layout: Literal["readable", "grid"] = "readable",
    lock_stackup: bool = False,
    lock_via_protection: bool = False,
    planes: Mapping[str, str] | None = None,
    lock_outline: bool = False,
    heights: Mapping[str, Nm] | None = None,
) -> BuildOutput:
    """Every file of the built project as bytes, or no file when an issue is an error.

    The outline of the model is judged first (``outline.check_outline``): rings that cross or touch stop
    the build. ``lock_outline`` is ``board(..., locked=True)`` of the script: with an existing board, the
    script's outline then replaces an outline edited in KiCad (``docs/lens.md``, "Outline changes").

    ``planes`` are the script's internal planes (layer name → net name). Each plane layer gets the KiCad
    row type ``power`` in the written board, after the merge with an existing board; every other copper
    layer keeps the type of the board it is written from, so a type set in KiCad stays (``docs/lens.md``,
    "Plane layers across rebuilds"; change c0107). The copper of a plane is the script's zone.

    ``Board.stackup`` of ``design`` is the script's stack-up. Against an existing board it is decided by
    ``stackup.merge_stackup``: the board's wins unless ``lock_stackup`` is set (``docs/lens.md``,
    "Stack-up across rebuilds"); ``summary["stackup"]`` says whose stack-up the written board holds.

    ``Board.via_protection`` of ``design`` is the script's default via protection. Against an existing
    board it is decided by ``via_protection.merge_default``: the board's wins unless ``lock_via_protection``
    is set (``docs/lens.md``, "Via protection across rebuilds"). A default of covering, plugging, capping
    or filling that vias take from the board only gives ``kicad.via.protection-not-exported``.

    ``source_sha256`` is the hash of the ``placements.toml`` that was read, recorded in
    ``.fenolite/build.json`` so a later check can tell that the layout's source changed.
    ``drawing_sheet`` is the sheet that the script names (``design.sheet(drawing_sheet=…)``), read by the
    caller: it is written as ``<name>.kicad_wks``, the file the project names as its frame.

    ``vendor`` is ``"all"`` (every placed footprint is copied into ``lib/``) or ``"project"`` (only those
    of project rows); ``record`` holds the hashes of the last build, for ``build.library-changed``.
    ``copper_intents`` are resolved into tracks and vias after the parts are placed, so script copper
    follows a footprint that an existing board placed elsewhere (``docs/copper.md``).
    ``meanders`` are resolved right after them (``meander.resolve_meanders``): each replaces one straight
    segment of a script track by a meander that brings the track to its target length, counted as KiCad
    ``target`` counts it; an error of a meander is an error of the build.
    ``fields`` maps a component path to the field placement requests of its part, applied to the placed or
    staged footprint (``docs/dsl.md``, "Field placement"); a footprint without the field raises
    ``FormatError``.
    ``pad_zones`` maps a component path to the pad zone connection requests of its part, applied to the
    built copy of its footprint; with an existing board a setting made in KiCad wins over an unlocked
    request on a kept footprint (``docs/lens.md``, "Pad zone connections").
    ``schematic`` is ``"write"`` (the project gets ``<name>.kicad_sch``, its symbol libraries and
    ``sym-lib-table``, and the board follows the sheet: ``docs/schematic.md``) or ``"skip"``;
    ``symbol_placements`` fixes symbol origins on the sheet (``lens.schplacements``).
    ``schematic_layout`` is ``"readable"`` (a sheet per module under ``sheets/``, and 2-pin parts beside
    the IC pins they connect to) or ``"grid"`` (the one flat sheet of v0.2a).
    ``heights`` maps a component path to the height its script states (``Part(height=…)``, change c0140):
    the footprint of that path gets one extruded body of that height (``height_body``), after the bodies
    of its definition. No KiCad file holds a body; ``.fenolite/board.json`` keeps it, also through a
    rebuild. A path that names no footprint is ignored.
    """
    if vendor not in VENDOR_MODES:  # pyright: ignore[reportUnnecessaryContains]
        raise ValueError(f"unknown vendoring policy {vendor!r}; use one of: {', '.join(VENDOR_MODES)}")
    if schematic not in SCHEMATIC_MODES:  # pyright: ignore[reportUnnecessaryContains]
        raise ValueError(f"unknown schematic mode {schematic!r}; use one of: {', '.join(SCHEMATIC_MODES)}")
    if schematic_layout not in schgen.LAYOUTS:
        raise ValueError(
            f"unknown schematic layout {schematic_layout!r}; use one of: {', '.join(schgen.LAYOUTS)}"
        )
    issues: list[Issue] = [*prepared.issues] if prepared is not None else []
    parts, libraries = _resolve(design, resolver, issues, authored_footprints, authored_symbols)
    plan = _vendor_plan(parts, vendor, issues)
    pins, on_net = _resolve_pins(design, parts, issues)
    marks = _resolve_marks(design, parts, pins, on_net, issues)
    _case_collisions(design, issues)
    issues += interface_checks(
        design,
        pins,
        on_net,
        target=target,
        layers=tuple(x.name for x in created_layers(copper) if x.kind == "copper"),
    )
    board = design.board
    if board is None or board.outline is None:
        issues.append(issue("build.no-board", "the design has no board(); nothing can be placed", "board"))
        return _refused(design, issues, libraries)
    issues += check_outline(design)
    if any(found.code == "kicad.outline.invalid" for found in issues):
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
    alias_matches = (
        {m.path for m in prepared.match.matches.values() if m.key == "alias"}
        if prepared is not None and prepared.match is not None
        else set[str]()
    )
    identities: dict[str, Mapping[str, str]] = {}
    lacking: set[str] = set()
    for part in parts:
        missing = [name for name in MANDATORY_FIELDS if name not in part.footprint.properties]
        if missing and part.footprint.lib_id not in lacking:
            # a library footprint of another origin: ``place_footprint`` adds the fields (c0077)
            lacking.add(part.footprint.lib_id)
            issues.append(
                issue(
                    "build.field-added",
                    f"{part.footprint.lib_id} has no {' and no '.join(missing)} field: each footprint "
                    "placed from it gets one at the default placement",
                    part.footprint.lib_id,
                    "add the property to the library footprint, or move the field with Part.field",
                )
            )
        extended = with_property(part.footprint, name=PATH_PROPERTY, value=part.path)
        user_locators: list[str] = []
        for prop_name, prop_value in _user_properties(part, issues):
            extended = with_property(extended, name=prop_name, value=prop_value)
            user_locators.append(f"/footprint/property:{prop_name}")
            written_properties = True
        if prepared is not None and part.path in alias_matches:
            # the uuids a footprint kept through an alias takes under its new path (c0069)
            identities[part.path] = identity_map(
                prepared.aliases[part.path], part.path, (*uuid_locators(extended), *user_locators)
            )
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
        instance = apply_requests(instance, fields.get(part.path, ()))
        stated = (heights or {}).get(part.path)
        if stated is not None:
            instance = dataclasses.replace(
                instance, bodies=(*instance.bodies, height_body(part.path, stated))
            )
        instance = apply_pad_connections(
            instance, pad_zones.get(part.path, ()), where=part.path, issues=issues
        )
        instance = dataclasses.replace(
            instance,
            pads=_pad_nets(
                instance.pads,
                pins[part.component.id],
                on_net[part.component.id],
                part,
                issues,
                part.component.pin_pads(),
            ),
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
    # the rule areas and drawings of the script get their marked uuids before copper resolves (c0103)
    built = boarditems.mark_items(built)
    board_items = {
        "rule_areas": len(board.keepouts),
        "texts": len(board.texts),
        "graphics": len(board.graphics),
        "dimensions": len(board.dimensions),
    }
    copper_counts = {"intents": len(copper_intents), "tracks": 0, "arcs": 0, "vias": 0}
    if copper_intents:
        assert built.board is not None
        held = prepared.board if prepared is not None else None
        project_text = prepared.existing.project if prepared is not None else None
        project_data = (
            pro.read_project_text(project_text) if project_text is not None else pro.template(target)
        )
        built = resolve_copper(
            built,
            copper_intents,
            unplaced=staged,
            issues=issues,
            # a rebuild keeps the rule areas and the edge of the existing board: stitch vias avoid those;
            # the script's own areas are in ``built``, and their copies on the board are regenerated
            keepouts=[
                area
                for area in (held.board.keepouts if held is not None and held.board is not None else ())
                if not boarditems.is_item_uuid(area.native_ids.get("kicad", ""))
            ],
            outline=_kept_outline(held, built, lock_outline),
            edge_floor=pro.project_minimums(project_data).get("min_copper_edge_clearance", 0),
        )
        assert built.board is not None
        created = (("tracks", built.board.tracks), ("arcs", built.board.arcs), ("vias", built.board.vias))
        for kind, items in created:
            copper_counts[kind] = sum(1 for i in items if is_copper_uuid(i.native_ids.get("kicad", "")))
    if meanders:
        built = meander_mod.resolve_meanders(built, meanders, major=target, issues=issues)
        assert built.board is not None
        copper_counts["meanders"] = meander_mod.changed(built, meanders)
        copper_counts["tracks"] = sum(
            1 for i in built.board.tracks if is_copper_uuid(i.native_ids.get("kicad", ""))
        )
    existing = prepared.existing if prepared is not None else preserve.ExistingProject()
    board_read = prepared is not None and prepared.board is not None
    preserved: dict[str, object] = {}
    target_design = built
    if prepared is not None and prepared.board is not None and prepared.match is not None:
        merged = preserve.merge_layout(
            built,
            prepared.board,
            prepared.match,
            net_aliases=prepared.net_aliases,
            identities=identities,
            lock_outline=lock_outline,
        )
        issues += merged.issues
        preserved.update(merged.summary)
        decided = merge_fields(merged, prepared.board, prepared.match, fields)
        preserved["fields"] = decided.summary
        target_design, preserved["pad_zones"] = _keep_pad_zones(
            decided.design, cast(Sequence[str], merged.summary.get("kept", ())), pad_zones, issues
        )
    stack_source: stacklib.StackupSource | None = None
    if target_design.board is not None:
        scripted = built.board.stackup if built.board is not None else None
        if board_read:
            decided_stack = stacklib.merge_stackup(
                scripted, target_design.board.stackup, layers=target_design.board.layers, locked=lock_stackup
            )
            issues += decided_stack.issues
            stack_source = decided_stack.source
            if decided_stack.stackup is not target_design.board.stackup:
                target_design = dataclasses.replace(
                    target_design,
                    board=dataclasses.replace(target_design.board, stackup=decided_stack.stackup),
                )
        elif scripted is not None:
            stack_source = "script"
    scripted_default = built.board.via_protection if built.board is not None else None
    if target_design.board is not None:
        if board_read:
            decided_default = vialib.merge_default(
                scripted_default, target_design.board.via_protection, locked=lock_via_protection
            )
            issues += decided_default.issues
            if decided_default.default != target_design.board.via_protection:
                target_design = dataclasses.replace(
                    target_design,
                    board=dataclasses.replace(target_design.board, via_protection=decided_default.default),
                )
        unexported = vialib.not_exported(target_design)
        if unexported is not None:
            issues.append(unexported)
    if planes and target_design.board is not None:
        # after the merge: the table may be the existing board's, whose other types are kept
        held_copper = {layer.name for layer in target_design.board.layers if layer.kind == "copper"}
        typed = with_plane_types(
            target_design.board.layers, tuple(name for name in planes if name in held_copper)
        )
        if typed != target_design.board.layers:
            target_design = dataclasses.replace(
                target_design, board=dataclasses.replace(target_design.board, layers=typed)
            )
    for rule_name, value in boarditems.unknown_areas(target_design):
        issues.append(
            issue(
                "build.area-unknown",
                f"rule {rule_name!r} selects the area {value!r}, and the board holds no rule area of that "
                "name: KiCad would load the rule and select nothing",
                rule_name,
                "declare the area with design.rule_area() or remove the selector",
            )
        )
    issues += list(target_design.validate())
    if any(i.severity == "error" for i in issues):
        return _refused(built, issues, libraries)
    generated: GeneratedSchematic | None = None
    symbol_files: dict[str, list[symembed.EmbeddedSymbol]] = {}
    if schematic == "write":
        generated = schgen.generate_schematic(
            target_design,
            parts,
            name=name,
            target=target,
            placements=symbol_placements,
            vendor=vendor,
            allow_lossy=allow_lossy,
            layout=schematic_layout,
            other_libraries=sorted({definition.library for definition in authored_symbols.values()}),
        )
        issues += generated.issues
        symbol_files = _symbol_libraries(generated, authored_symbols, target, allow_lossy, issues)
        if any(i.severity == "error" for i in issues):
            return _refused(built, issues, libraries)
        differs = schematic_netlist_issue(target_design, generated, name)
        if differs is not None:
            issues.append(differs)
            return _refused(built, issues, libraries)
        target_design = lower_for_schematic(target_design, generated)
    texts = write_triad(
        target_design,
        name=name,
        target=target,
        existing_project=existing.project,
        renamed_nets=tuple(prepared.net_aliases.values()) if prepared is not None else (),
        # the drawing sheet of design.sheet() frames the schematic the build writes, too (c0074)
        schematic=schematic == "write",
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
            prepared.board,
            target_design,
            existing=existing,
            project=texts[pro_name],
            rules=texts[dru_name],
            net_aliases=prepared.net_aliases,
        )
        if fill_issues:
            issues += fill_issues
            written = write_board(stale, target=target, allow_lossy=allow_lossy)
            texts[pcb_name] = written.text
        preserved["fills"] = preserve.fill_counts(prepared.board, stale)
    files: dict[str, bytes] = {n: t.encode("utf-8") for n, t in texts.items()}
    if drawing_sheet is not None:
        written_sheet = wks.write_drawing_sheet(drawing_sheet, target=target, allow_lossy=allow_lossy)
        issues += written_sheet.issues
        files[f"{name}{SHEET_SUFFIX}"] = written_sheet.text.encode("utf-8")
    readback = read_board(texts[pcb_name], file=pcb_name, issues=[])
    layout = preserve.merge_layout(
        built, readback, preserve.match_footprints(built, readback), lock_outline=lock_outline
    ).design
    vendored = _vendor(plan, target, files, record, issues)
    authored_ids = {part.footprint.lib_id for part in parts if part.location is None}
    for lib_id in sorted(authored_ids):
        definition = authored_footprints[lib_id]
        path = f"lib/{definition.library}.pretty/{definition.name}.kicad_mod"
        files[path] = mod.write_footprint(definition, target=target, allow_lossy=allow_lossy).encode("utf-8")
        vendored.append((definition.library, f"{definition.name}.kicad_mod"))
    vendored.sort()
    rows = tuple(
        LibRow(nick, "KiCad", f"${{KIPRJMOD}}/lib/{nick}.pretty") for nick in sorted({n for n, _ in vendored})
    )
    files["fp-lib-table"] = write_lib_table(LibTable("footprint", rows), target=target).encode("utf-8")
    if generated is not None:
        written = sch.write_schematic(generated.sheet, target=target, allow_lossy=allow_lossy)
        issues += written.issues
        files[f"{name}.kicad_sch"] = written.text.encode("utf-8")
        for path, child in generated.children.items():
            written = sch.write_schematic(child, target=target, allow_lossy=allow_lossy)
            issues += [found for found in written.issues if found not in issues]
            files[path] = written.text.encode("utf-8")
        issues += stale_sheets(record, files)
        for nickname, found in sorted(symbol_files.items()):
            path = f"lib/{nickname}.kicad_sym"
            files[path] = symembed.write_symbol_library(found, target=target).encode("utf-8")
            known = None if record is None else record.get(path)
            if known is not None and known != hashlib.sha256(files[path]).hexdigest():
                issues.append(
                    issue(
                        "build.library-changed",
                        f"{path} differs from the copy of the last build: its library changed",
                        path,
                    )
                )
        files["sym-lib-table"] = write_lib_table(
            LibTable("symbol", tuple(schgen.library_row(nick) for nick in sorted(symbol_files))),
            target=target,
        ).encode("utf-8")
    elif authored_symbols:
        symbol_rows: list[LibRow] = []
        by_library: dict[str, list[SymbolDef]] = {}
        for definition in authored_symbols.values():
            by_library.setdefault(definition.library, []).append(definition)
        for nickname, definitions in sorted(by_library.items()):
            if not nickname or "/" in nickname or "\\" in nickname or nickname in (".", ".."):
                issues.append(
                    issue(
                        "build.vendor-unsafe-name",
                        f"unsafe authored symbol library name {nickname!r}",
                        nickname,
                    )
                )
                continue
            files[f"lib/{nickname}.kicad_sym"] = sym.write_symbol_library(definitions, target=target).encode(
                "utf-8"
            )
            symbol_rows.append(LibRow(nickname, "KiCad", f"${{KIPRJMOD}}/lib/{nickname}.kicad_sym"))
        files["sym-lib-table"] = write_lib_table(
            LibTable("symbol", tuple(symbol_rows)), target=target
        ).encode("utf-8")
    record = {path: hashlib.sha256(data).hexdigest() for path, data in sorted(files.items())}
    for file_name, text in canonical.dump_texts(layout).items():
        files[f"{CACHE_DIR}/{file_name}"] = text.encode("utf-8")
    recorded: dict[str, object] = {"design": name, "files": record, "schema": RECORD_SCHEMA, "target": target}
    if source_sha256 is not None:
        recorded["source"] = {"placements.toml": source_sha256}
    files[RECORD_FILE] = (
        json.dumps(
            recorded,
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
    if authored_ids:
        evidence_items.append(mod.AUTHORING_EVIDENCE)
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
    if any(board_items.values()):
        evidence_items.append(boarditems.EVIDENCE)  # the script declares rule areas or drawings
    if meanders:
        evidence_items += [meander_mod.EVIDENCE, lengths_mod.EVIDENCE]
    written_stack = target_design.board.stackup if target_design.board is not None else None
    if written_stack is not None:
        evidence_items.append(stacklib.EVIDENCE)
    if scripted_default is not None or any(
        via.protection != ViaProtection() for via in (built.board.vias if built.board is not None else ())
    ):
        evidence_items.append(vialib.EVIDENCE)  # the script states a via protection
    if generated is not None:
        evidence_items += [schgen.EVIDENCE, sch.WRITE_EVIDENCE]
        # a design with a pin bonded to several pads rests on what KiCad does with stacked pins (c0123);
        # a design of one pad per pin adds nothing, so its envelope is the one it was
        evidence_items += sch_netlist.stack_evidence((generated.sheet, *generated.children.values()))
    merged_copper = cast(Mapping[str, int], preserved.get("copper", {}))
    summary: dict[str, object] = {
        "components": len(components),
        "nets": len(nets),
        "placed": placed,
        "staged": staged,
        "vendored": [f"lib/{nick}.pretty/{entry}" for nick, entry in vendored],
        "libraries": libraries,
        "preserved": _preserved(prepared, preserved),
        "board_items": board_items,
        "stackup": None
        if written_stack is None
        else {
            "source": stack_source,
            "thickness": written_stack.thickness(),
            "copper": sum(1 for entry in written_stack.layers if entry.kind == "copper"),
        },
        "copper": {
            **copper_counts,
            **{key: merged_copper.get(key, 0) for key in ("regenerated", "stale", "duplicates")},
        },
        "schematic": None
        if generated is None
        else {
            "file": f"{name}.kicad_sch",
            "paper": generated.sheet.paper.paper,
            "sheets": 1 + len(generated.children),
            "files": list(generated.children),
            "symbols": sum(len(sheet.symbols) for sheet in _sheets(generated)),
            "labels": sum(len(sheet.labels) for sheet in _sheets(generated)),
            "no_connects": sum(len(sheet.no_connects) for sheet in _sheets(generated)),
            "wires": sum(len(sheet.wires) for sheet in _sheets(generated)),
            "satellites": generated.satellites,
            "power_flags": generated.power_flags,
            "libraries": [f"lib/{nick}.kicad_sym" for nick in sorted(symbol_files)],
            "unconnected_pads": len(generated.pad_nets),
        },
    }
    return BuildOutput(
        built,
        dict(sorted(files.items())),
        tuple(issues),
        Evidence.combine(*evidence_items),
        summary,
        layout,
        generated,
    )


def _sheets(generated: GeneratedSchematic) -> tuple[SchematicSheet, ...]:
    """The root sheet and the child sheets of a generated schematic, in page order."""
    return (generated.sheet, *generated.children.values())


def stale_sheets(record: Mapping[str, str] | None, files: Mapping[str, bytes]) -> list[Issue]:
    """One ``build.sheet-stale`` warning per child sheet that the last build recorded and this build does
    not plan (capability design-dsl, "Hierarchical sheets in a build"; change c0070). The file is left
    where it is: a build deletes nothing. No file is read; the next record no longer lists it."""
    prefix = f"{schgen.SHEETS_DIR}/"
    found: list[Issue] = []
    for path in sorted(record or ()):
        if path.startswith(prefix) and path.endswith(".kicad_sch") and path not in files:
            found.append(
                issue(
                    "build.sheet-stale",
                    f"{path} was a sheet of the last build and is none of this design: no sheet names it "
                    "any more, and the file is left in place",
                    path,
                    "delete the file when you no longer need it",
                )
            )
    return found


def _keep_pad_zones(
    design: Design,
    kept_paths: Sequence[str],
    requests: Mapping[str, Sequence[PadZoneRequestLike]],
    issues: list[Issue],
) -> tuple[Design, dict[str, list[str]]]:
    """The merged layout with the pad zone connections of its kept footprints decided, and
    ``result.preserved.pad_zones`` (``layout-lens``, "Pad zone connections across rebuilds").

    Only kept footprints are touched: a re-placed or new footprint is the built copy, which already holds
    every request. An unknown pad that the built copy reported already is not reported again."""
    summary: dict[str, list[str]] = {"kept": [], "forced": []}
    if design.board is None or not requests:
        return design, summary
    components = preserve.component_paths(design)
    changed: dict[str, FootprintInstance] = {}
    current = {fp.component_id: fp for fp in design.board.footprints}
    seen = {(i.code, i.where, i.message) for i in issues}
    for path in sorted(set(kept_paths) & set(requests)):
        component = components.get(path)
        instance = current.get(component.id) if component is not None else None
        if instance is None:
            continue
        found: list[Issue] = []
        decided = keep_pad_connections(instance, requests[path], where=path, issues=found)
        for item in found:
            if item.code == "kicad.pad.zone-overridden":
                summary["kept"].append(item.where)
            elif item.code == "kicad.pad.zone-forced":
                summary["forced"].append(item.where)
            if (item.code, item.where, item.message) not in seen:
                issues.append(item)
        if decided is not instance:
            changed[instance.component_id] = decided
    if changed:
        footprints = tuple(changed.get(fp.component_id, fp) for fp in design.board.footprints)
        design = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=footprints))
    return design, {key: sorted(set(values)) for key, values in summary.items()}


def _kept_outline(existing: Design | None, built: Design, lock_outline: bool = False) -> BoardOutline:
    """The outline a build writes: the edge content of the existing board when it has any and the lens
    keeps it, else the design's outline (also when ``outline.merge_outline`` replaces the board's)."""
    if existing is not None and outline_case(built, existing, locked=lock_outline) not in (
        "replaced",
        "forced",
        "resigned",
    ):
        held = board_outline(existing)
        if held.problem != "no-edge-content":
            return held
    return board_outline(built)


def board_read(prepared: Prepared | None) -> TypeGuard[Prepared]:
    return prepared is not None and prepared.board is not None


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
        "fields": merged.get("fields", {"kept": [], "forced": [], "carried": []}),
        "pad_zones": merged.get("pad_zones", {"kept": [], "forced": []}),
        "board_items": merged.get("board_items", {"regenerated": 0, "stale": 0}),
        "aliases": dict(prepared.aliases) if prepared is not None else {},
        "module_aliases": dict(prepared.module_aliases) if board_read(prepared) else {},
        "net_aliases": dict(prepared.net_aliases) if board_read(prepared) else {},
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
        "stackup": None,
        "schematic": None,
    }
    return BuildOutput(design, {}, tuple(issues), BUILD_EVIDENCE, summary)


def _symbol_libraries(
    generated: GeneratedSchematic,
    authored: Mapping[str, SymbolDef],
    target: int,
    allow_lossy: bool,
    issues: list[Issue],
) -> dict[str, list[symembed.EmbeddedSymbol]]:
    """The symbols of each project library a build with a schematic writes: the embedded definitions of
    the nickname and, for a nickname the design authors, every authored symbol of it. Reports the symbols
    that ``vendor="project"`` leaves without a library, unsafe nicknames and the reserved nickname."""
    libraries = {nick: list(found) for nick, found in generated.libraries.items()}
    for lib_id in generated.unvendored:
        issues.append(
            issue(
                "build.global-library",
                f"symbol {lib_id} does not come from a project row: it is embedded in the schematic and "
                "gets no project library",
                lib_id,
            )
        )
    for lib_id, definition in sorted(authored.items()):
        if definition.library == symembed.FLAG_LIBRARY:
            issues.append(
                issue(
                    "build.reserved-library",
                    f"{lib_id}: the library nickname {symembed.FLAG_LIBRARY!r} is kept for Fenolite's own "
                    "symbols",
                    lib_id,
                    "author the symbol under another nickname",
                )
            )
            continue
        held = libraries.setdefault(definition.library, [])
        if (
            generated.power_flags
            and symembed.is_power_flag(lib_id)
            and all(found.code != "build.reserved-library" or found.where != lib_id for found in issues)
        ):
            # the flag of this sheet lies in this library under this name (change c0143)
            issues.append(
                issue(
                    "build.reserved-library",
                    f"{lib_id}: the symbol name {symembed.FLAG_NAME!r} of the library {definition.library!r} "
                    "is kept for Fenolite's power flag, which this design needs",
                    lib_id,
                    "give the symbol another name, or its library another nickname",
                )
            )
            continue
        if all(found.lib_id != definition.lib_id for found in held):
            held.append(
                symembed.embed_symbol(definition, target=target, allow_lossy=allow_lossy, issues=issues)
            )
    folded: dict[str, str] = {}
    for nickname in sorted(libraries):
        if (
            not nickname
            or any(c in nickname for c in "/\\")
            or not nickname.isprintable()
            or nickname in (".", "..")
        ):
            issues.append(
                issue(
                    "build.vendor-unsafe-name",
                    f"nickname {nickname!r} cannot name a symbol library file under lib/",
                    nickname,
                )
            )
            continue
        other = folded.setdefault(nickname.casefold(), nickname)
        if other != nickname:
            issues.append(
                issue(
                    "build.vendor-unsafe-name",
                    f"symbol libraries {other!r} and {nickname!r} differ only in letter case",
                    nickname,
                )
            )
    return libraries


GUARD_CODE = "build.schematic-netlist-differs"
GUARD_HINT = (
    "this is a defect of the schematic generator: report it with the script, and build with "
    "--schematic skip meanwhile"
)


def schematic_netlist_issue(design: Design, generated: GeneratedSchematic, name: str) -> Issue | None:
    """``build.schematic-netlist-differs`` when the generated sheet does not mean the circuit, else ``None``
    (capability design-dsl, "Schematic netlist guard in a build"; change c0063).

    The sheet is read by ``sch_netlist.own_netlist``, without any tool, and compared with ``design``: a
    member of a net whose component has a symbol (``generated.paths``) must be on the net of that stored
    name, a pin whose pad ``generated.pad_nets`` names must be on the net of that name, and every other
    pin of the sheet must be alone on its net. The circuit of a rebuild can hold pads that are no pin of
    a symbol, so the sheet lists the pins. Elements are ``REF-PAD``. Pin types, net classes and values
    are not compared. The issue names the first difference by net and element, in sorted order.
    """
    try:
        own = sch_netlist.own_netlist(generated.sheet, project=name, children=generated.children)
    except sch_netlist.NetlistUnsupportedError as error:
        reasons = "; ".join(found.message for found in error.issues)
        return issue(
            GUARD_CODE,
            f"the generated schematic is outside what Fenolite reads back ({reasons}), so it is not "
            "proved to mean the circuit; nothing is written",
            f"{name}.kicad_sch",
            GUARD_HINT,
        )
    refs = {c.id: c.ref for c in design.circuit.components}
    by_id = {c.id: c for c in design.circuit.components}
    expected: dict[str, str] = {}
    differences: list[tuple[str, str, str]] = []
    stored_as: dict[str, str] = {}
    for net in design.circuit.nets:
        stored = netnames.stored_name(net.name)
        for member in net.members:
            if member.component_id not in generated.paths:
                continue  # a footprint kept from the board has no symbol: the sheet says nothing of it
            component = by_id.get(member.component_id)
            for pad in component.pads_of(member.pin) if component is not None else (member.pin,):
                element = f"{refs.get(member.component_id, '')}-{pad}"
                other = stored_as.setdefault(stored, net.name)
                if other != net.name:
                    text = f"the nets {other} and {net.name} of the circuit are one net on the sheet"
                    differences.append((stored, element, text))
                known = expected.setdefault(element, stored)
                if known != stored:
                    text = f"the circuit has {element} on {known} and on {stored}"
                    differences.append((stored, element, text))
    for (component_id, pad), net_name in generated.pad_nets.items():
        expected.setdefault(f"{refs.get(component_id, '')}-{pad}", net_name)
    found = {node.element: net for net in own.nets for node in net.nodes}
    for element in expected.keys() | found.keys():
        wanted, net = expected.get(element), found.get(element)
        if net is None:
            text = f"the circuit has {element} on {wanted}, and the sheet has no such pin"
            differences.append((wanted or "", element, text))
        elif wanted is None:  # a pin the circuit leaves open, whose name KiCad derives: alone on its net
            if len(net.nodes) > 1:
                text = f"the sheet has {element} on {net.name}, and the circuit has it on no net"
                differences.append((net.name, element, text))
        elif net.name != wanted:
            text = f"the sheet has {element} on {net.name}, and the circuit has it on {wanted}"
            differences.append((wanted, element, text))
    if not differences:
        return None
    differences.sort()
    net_name, element, text = differences[0]
    more = f" (and {len(differences) - 1} more)" if len(differences) > 1 else ""
    return issue(
        GUARD_CODE,
        f"the generated schematic does not mean the circuit: net {net_name or '(none)'}, {element}: "
        f"{text}{more}; nothing is written",
        element,
        GUARD_HINT,
    )


def lower_for_schematic(design: Design, generated: GeneratedSchematic) -> Design:
    """The design that is written beside a generated schematic, so that KiCad's parity test and its
    "Update PCB from Schematic" find the board in agreement with the sheet (``docs/schematic.md``).

    Each pad of an unconnected pin gets a net of the name KiCad derives for that pin, and each component
    gets the path of its symbol: ``/<symbol uuid>`` on the root sheet, and the uuids of the sheet
    references from the top down before it on a child sheet (``H-K-SCH-HIER-PATH``). Nothing else
    changes; the stored layout and the model never hold these
    nets. Applying the function twice gives the result of applying it once.
    """
    board = design.board
    if board is None:
        return design
    paths = {c.id: _path(c) for c in design.circuit.components}
    nets = list(design.circuit.nets)
    known = {net.id for net in nets}
    footprints: list[FootprintInstance] = []
    for fp in board.footprints:
        pads: list[Pad] = []
        # the pads of one open pin share one name (a pin bonded to several pads, c0123): the net is keyed
        # by the lowest of their numbers, which for a pin of one pad is the pad's own
        keyed: dict[str, str] = {}
        for pad in fp.pads:
            name = generated.pad_nets.get((fp.component_id, pad.number)) if pad.number else None
            if name is not None and pad.net_id is None:
                keyed[name] = min(keyed.get(name, pad.number), pad.number)
        for pad in fp.pads:
            wanted = generated.pad_nets.get((fp.component_id, pad.number)) if pad.number else None
            if wanted is not None and pad.net_id is None:
                net_id = derived_id(
                    "net", schgen.ID_BACKEND, f"unconnected:{paths.get(fp.component_id, '')}:{keyed[wanted]}"
                )
                if net_id not in known:
                    known.add(net_id)
                    nets.append(Net(id=net_id, name=wanted))
                pad = dataclasses.replace(pad, net_id=net_id)
            pads.append(pad)
        footprints.append(dataclasses.replace(fp, pads=tuple(pads)))
    components = tuple(
        dataclasses.replace(c, path=generated.paths[c.id]) if c.id in generated.paths else c
        for c in design.circuit.components
    )
    return dataclasses.replace(
        design,
        circuit=dataclasses.replace(design.circuit, components=components, nets=tuple(nets)),
        board=dataclasses.replace(board, footprints=tuple(footprints)),
    )


def _pad_nets(
    pads: tuple[Pad, ...],
    pins: list[Pin],
    on_net: Mapping[str, str],
    part: _Part,
    issues: list[Issue],
    pin_pads: Mapping[str, tuple[str, ...]],
) -> tuple[Pad, ...]:
    """``pads`` with the net of the pin that names each: ``pin_pads`` is ``Component.pin_pads()``, the pads
    of each mapped pin (several for a pin bonded to several pads, change c0123); a pin outside it names
    the pad of its own number."""
    numbers = {p.number for p in pins}
    pad_numbers = {p.number for p in pads if p.number}
    ref = part.component.ref
    for source, targets in sorted(pin_pads.items()):
        if source not in numbers:
            issues.append(
                issue("build.pin-pad-map-invalid", f"{ref} maps missing symbol pin {source}", part.path)
            )
        for target in targets:
            if target not in pad_numbers:
                issues.append(
                    issue(
                        "build.pin-pad-map-invalid",
                        f"{ref} maps to missing footprint pad {target}",
                        part.path,
                    )
                )
    resolved = {pin.number: pin_pads.get(pin.number, (pin.number,)) for pin in pins}
    assigned: dict[str, str] = {}
    for pin, targets in sorted(resolved.items()):
        for pad in targets:
            other = assigned.get(pad)
            if other is not None and other != pin:
                issues.append(
                    issue(
                        "build.pin-pad-map-invalid",
                        f"{ref} pins {other} and {pin} both map to pad {pad}",
                        part.path,
                    )
                )
            assigned[pad] = pin
    net_by_pad = {pad: on_net[pin] for pin, targets in resolved.items() if pin in on_net for pad in targets}
    for number in sorted(pad_numbers - numbers):
        if number not in assigned:
            issues.append(
                issue("build.pad-without-pin", f"{ref} pad {number} has no pin mapped to it", part.path)
            )
    for pin in pins:
        if any(pad in pad_numbers for pad in resolved[pin.number]):
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
    return tuple(dataclasses.replace(p, net_id=net_by_pad.get(p.number)) if p.number else p for p in pads)


def _vendor_plan(
    parts: list[_Part], vendor: Literal["all", "project"], issues: list[Issue]
) -> dict[str, Location]:
    """Vendored path → the location it is copied from, with ``build.global-library`` for the footprints
    left out by ``vendor="project"`` and ``build.vendor-unsafe-name`` for unsafe nicknames."""
    plan: dict[str, Location] = {}
    for part in parts:
        location = part.location
        if location is None:
            continue
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
    "SCHEMATIC_MODES",
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
    "lower_for_schematic",
    "schematic_netlist_issue",
    "stale_sheets",
    "read_record",
]
