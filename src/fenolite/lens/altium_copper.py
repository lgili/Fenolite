# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of the Altium PCB document, lowered from the model (change c0038, capability altium-build,
"Copper in an Altium build" and "Copper issue codes").

``lower_copper`` turns the tracks, arcs, vias and zones of a design into what ``pcbdoc.PcbDocSpec`` takes:
the board's copper layers and the entities with their net **names**. A zone becomes one unpoured polygon
per layer, which Altium fills on a repour. It finds every case the writer would
refuse and reports it as an issue of ``COPPER_ISSUE_CODES``, so no ``ValueError`` of the writer reaches the
user. Nothing is dropped to make a document fit: copper that cannot be written exactly is an error.
``fenolite.lens.altium`` calls it from ``pcb_document`` and adds the codes to its closed table.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from fenolite.backends.altium import pcbdoc, pcbrecords
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.docboard import Dielectric, StackSpec
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.model.board import Arc, Board, Stackup, Track, Via, Zone
from fenolite.model.design import Design

COPPER_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "altium.copper-stack": "error",
        "altium.copper-layer": "error",
        "altium.via-unsupported": "error",
        "altium.copper-invalid": "error",
        "altium.zone-unsupported": "error",
        "altium.zones-unpoured": "info",
    }
)
"""The copper rows of ``lens.altium.ALTIUM_ISSUE_CODES`` (change c0038, "Copper issue codes")."""
COPPER_COUNTS: Mapping[int, tuple[str, ...]] = MappingProxyType(
    {len(stack): stack for stack in pcbrecords.COPPER_STACKS}
)
"""Copper layer count of the script → the board's copper layers, top to bottom."""
STACK_HINT = "use design.board(..., copper=2) or copper=4"
REPOUR_COMMAND = "Tools » Polygon Pours » Repour All"
"""The Altium Designer command that fills the unpoured polygons (``pcb-copper.md``, "Polygon pour")."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, COPPER_ISSUE_CODES[code], message, where=where, hint=hint)


def has_copper(board: Board | None) -> bool:
    """True when the board itself holds a track, an arc, a via or a zone (the ``model`` source)."""
    return board is not None and bool(board.tracks or board.arcs or board.vias or board.zones)


def mm_text(nm: int) -> str:
    """Nanometres as millimetres without trailing zeros (``12.5``, ``0``)."""
    text = format(Decimal(nm) / Decimal(1_000_000), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


@dataclass(frozen=True, slots=True)
class CopperPlan:
    """The copper of one document: the board's copper layers, top to bottom, and the entities that
    ``pcbdoc.PcbDocSpec`` takes, their ``net_id`` holding the net's name. ``issues`` holds the errors and
    infos of the lowering; with an error the entities are not to be written."""

    layers: tuple[str, ...]
    tracks: tuple[Track, ...] = ()
    arcs: tuple[Arc, ...] = ()
    vias: tuple[Via, ...] = ()
    issues: tuple[Issue, ...] = ()
    stack: StackSpec | None = None
    zones: tuple[Zone, ...] = ()

    @property
    def failed(self) -> bool:
        return any(found.severity == "error" for found in self.issues)


def board_layers(design: Design, copper: int) -> tuple[tuple[str, ...], list[Issue]]:
    """The copper layers of the document: the copper layers of ``design.board.layers`` when it holds any,
    else those of the script's count ``copper``. A stack that is not one of ``pcbrecords.COPPER_STACKS``,
    or whose count differs from ``copper``, gives ``altium.copper-stack`` and the nearest written stack."""
    board = design.board
    named = tuple(layer.name for layer in board.layers if layer.kind == "copper") if board is not None else ()
    wanted = COPPER_COUNTS.get(copper)
    if named:
        if named not in pcbrecords.COPPER_STACKS:
            stacks = " or ".join(", ".join(stack) for stack in pcbrecords.COPPER_STACKS)
            message = f"the board's copper layers {', '.join(named)} are not {stacks}"
            return named, [issue("altium.copper-stack", message, "stack", STACK_HINT)]
        if wanted is not None and named != wanted:
            held = f"{len(named)} copper layers ({', '.join(named)})"
            message = f"the board holds {held}, the build asks for {copper}"
            return named, [issue("altium.copper-stack", message, "stack", STACK_HINT)]
        return named, []
    if wanted is None:
        message = f"a board of {copper} copper layers is not written; only 2 and 4 are"
        return pcbrecords.COPPER_STACKS[0], [issue("altium.copper-stack", message, "stack", STACK_HINT)]
    return wanted, []


@dataclass(frozen=True, slots=True)
class _Lowering:
    """The state of one lowering: the layers, the net names of the copper's net ids, and where a point
    lies relative to the outline's corner."""

    layers: tuple[str, ...]
    net_names: Mapping[str, str]
    corner: Point
    label: str

    def at(self, point: Point) -> str:
        return f"({mm_text(point.x - self.corner.x)}, {mm_text(point.y - self.corner.y)}) mm"

    def text(self, message: str) -> str:
        return f"{self.label}{message}"


def _net_name(
    entity_id: str, net_id: str | None, low: _Lowering, issues: list[Issue], what: str
) -> str | None:
    if net_id is None:
        return None
    name = low.net_names.get(net_id)
    if name is None:
        issues.append(
            issue("altium.copper-invalid", low.text(f"{what}: the net id {net_id} names no net"), entity_id)
        )
    return name


def _layer_ok(entity_id: str, layer: str, low: _Lowering, issues: list[Issue], what: str) -> bool:
    if layer in low.layers:
        return True
    message = f"{what}: {layer} is not a copper layer of the board ({', '.join(low.layers)})"
    issues.append(
        issue(
            "altium.copper-layer",
            low.text(message),
            entity_id,
            "build the board with copper=4, or move the copper",
        )
    )
    return False


def _tracks(tracks: Sequence[Track], low: _Lowering, issues: list[Issue]) -> list[Track]:
    out: list[Track] = []
    for track in tracks:
        what = f"track on {track.layer} at {low.at(track.start)}"
        before = len(issues)
        _layer_ok(track.id, track.layer, low, issues, what)
        if track.width <= 0:
            message = f"{what}: a width of {mm_text(track.width)} mm is not positive"
            issues.append(issue("altium.copper-invalid", low.text(message), track.id))
        if track.start == track.end:
            issues.append(
                issue("altium.copper-invalid", low.text(f"{what}: the track has zero length"), track.id)
            )
        name = _net_name(track.id, track.net_id, low, issues, what)
        if len(issues) == before:
            out.append(dataclasses.replace(track, net_id=name))
    return out


def _arcs(arcs: Sequence[Arc], low: _Lowering, issues: list[Issue]) -> list[Arc]:
    out: list[Arc] = []
    for arc in arcs:
        what = f"arc on {arc.layer} at {low.at(arc.start)}"
        before = len(issues)
        _layer_ok(arc.id, arc.layer, low, issues, what)
        if arc.width <= 0:
            message = f"{what}: a width of {mm_text(arc.width)} mm is not positive"
            issues.append(issue("altium.copper-invalid", low.text(message), arc.id))
        try:
            pcbrecords.arc_from_points(arc.start, arc.mid, arc.end)
        except ValueError:
            message = f"{what}: its three points lie on one line"
            issues.append(issue("altium.copper-invalid", low.text(message), arc.id))
        name = _net_name(arc.id, arc.net_id, low, issues, what)
        if len(issues) == before:
            out.append(dataclasses.replace(arc, net_id=name))
    return out


def _vias(vias: Sequence[Via], low: _Lowering, issues: list[Issue]) -> list[Via]:
    top, bottom = low.layers[0], low.layers[-1]
    out: list[Via] = []
    for via in vias:
        what = f"via at {low.at(via.position)}"
        before = len(issues)
        outside = [layer for layer in via.layers if layer not in low.layers]
        if via.via_type != "through":
            spans = ", ".join(via.layers)
            message = f"{what}: a {via.via_type} via ({spans}) is not written; only through vias are"
            issues.append(
                issue(
                    "altium.via-unsupported", low.text(message), via.id, "use a through via from F.Cu to B.Cu"
                )
            )
        elif outside:
            _layer_ok(via.id, outside[0], low, issues, what)
        elif len(via.layers) != 2 or set(via.layers) != {top, bottom}:
            spans = ", ".join(via.layers) or "no layer"
            message = f"{what}: a through via spans {spans}, not {top} to {bottom}"
            issues.append(
                issue(
                    "altium.via-unsupported", low.text(message), via.id, "use a through via from F.Cu to B.Cu"
                )
            )
        if not 0 < via.drill < via.diameter:
            message = (
                f"{what}: the drill of {mm_text(via.drill)} mm is not below the diameter of "
                f"{mm_text(via.diameter)} mm"
            )
            issues.append(issue("altium.copper-invalid", low.text(message), via.id))
        name = _net_name(via.id, via.net_id, low, issues, what)
        if len(issues) == before:
            out.append(dataclasses.replace(via, net_id=name))
    return out


def _zones(zones: Sequence[Zone], low: _Lowering, issues: list[Issue]) -> list[Zone]:
    out: list[Zone] = []
    for zone in zones:
        where = f" at {low.at(zone.outline[0])}" if zone.outline else ""
        what = f"zone on {', '.join(zone.layers) or 'no layer'}{where}"
        before = len(issues)
        outline = (
            zone.outline[:-1]
            if len(zone.outline) > 1 and zone.outline[0] == zone.outline[-1]
            else zone.outline
        )
        if len(outline) < 3 or not zone.layers:
            reason = "names no layer" if len(outline) >= 3 else f"has an outline of {len(outline)} points"
            message = f"{what}: the zone {reason}, so no polygon can be written"
            hint = "an outline kept as an opaque slot cannot be lowered; redraw the zone as a polygon"
            issues.append(issue("altium.zone-unsupported", low.text(message), zone.id, hint))
        outside = [layer for layer in zone.layers if layer not in low.layers]
        if outside:
            _layer_ok(zone.id, outside[0], low, issues, what)
        if zone.name and text_problem(zone.name) is not None:
            message = f"{what}: the name {zone.name!r} {text_problem(zone.name)}"
            issues.append(issue("altium.copper-invalid", low.text(message), zone.id))
        name = _net_name(zone.id, zone.net_id, low, issues, what)
        if len(issues) == before:
            out.append(dataclasses.replace(zone, net_id=name, fills=()))
    return out


DIELECTRIC_KINDS = {1: ("core",), 3: ("prepreg", "core", "prepreg")}
"""The kind of each dielectric of a stack-up, by their count: one core, or prepreg, core, prepreg."""


def stack_from_stackup(stackup: Stackup, layers: Sequence[str], copper: tuple[int, ...]) -> StackSpec | None:
    """The stack values of ``stackup`` when it fits the document: one copper layer per copper layer of the
    board, named like it and in order, with exactly one dielectric between neighbours; ``None`` otherwise.
    Solder mask, silkscreen and paste layers of the stack-up are passed over."""
    physical = [layer for layer in stackup.layers if layer.kind in ("copper", "dielectric")]
    if len(physical) != 2 * len(layers) - 1:
        return None
    coppers, between = physical[0::2], physical[1::2]
    if [layer.kind for layer in coppers] != ["copper"] * len(layers):
        return None
    if [layer.name for layer in coppers] != list(layers) or any(d.kind != "dielectric" for d in between):
        return None
    try:
        dielectrics = tuple(
            Dielectric(kind, layer.thickness, layer.epsilon_r or "4.800", layer.material or "FR-4")  # type: ignore[arg-type]
            for kind, layer in zip(DIELECTRIC_KINDS[len(between)], between, strict=True)
        )
        return StackSpec(copper, tuple(layer.thickness for layer in coppers), dielectrics)
    except ValueError:
        return None


def stack_values(design: Design, layers: Sequence[str]) -> tuple[StackSpec, list[Issue]]:
    """The stack of the document: the values of ``design.board.stackup`` when it fits
    (``stack_from_stackup``), else Fenolite's defaults with one ``altium.not-lowered`` info."""
    copper = pcbrecords.copper_stack(layers)
    stackup = design.board.stackup if design.board is not None else None
    if stackup is None:
        return StackSpec.default(copper), []
    found = stack_from_stackup(stackup, layers, copper)
    if found is not None:
        return found, []
    message = (
        "the stack-up does not hold one copper layer per copper layer of the board with one dielectric "
        "between neighbours; the document gets Fenolite's default stack values"
    )
    return StackSpec.default(copper), [Issue("altium.not-lowered", "info", message, where="stackup")]


def outline_corner(board: Board | None) -> Point:
    """The corner that positions in messages count from: the outline's lowest X and Y (KiCad frame)."""
    if board is None or board.outline is None or not board.outline.points:
        return Point(0, 0)
    points = board.outline.points
    return Point(min(p.x for p in points), min(p.y for p in points))


def lower_copper(design: Design, *, copper: int = 2, document: str = "") -> CopperPlan:
    """The copper of ``design.board`` for the document (the ``model`` source): the board's copper layers
    and its tracks, arcs, vias and zones with net names, or the issues that refuse them. ``document``
    is the document's file name, named by the info about unpoured polygons."""
    layers, issues = board_layers(design, copper)
    board = design.board
    if board is None or issues:
        return CopperPlan(layers, issues=tuple(issues))
    low = _Lowering(
        layers=layers,
        net_names={net.id: net.name for net in design.circuit.nets},
        corner=outline_corner(board),
        label="",
    )
    tracks = _tracks(board.tracks, low, issues)
    arcs = _arcs(board.arcs, low, issues)
    vias = _vias(board.vias, low, issues)
    zones = _zones(board.zones, low, issues)
    stack, stack_issues = stack_values(design, layers)
    issues += stack_issues
    polygons = sum(len(zone.layers) for zone in zones)
    if polygons and not any(found.severity == "error" for found in issues):
        message = (
            f"{polygons} polygon(s) are written without poured copper: run '{REPOUR_COMMAND}' in Altium "
            "Designer to fill them"
        )
        issues.append(issue("altium.zones-unpoured", message, document, f"{REPOUR_COMMAND}"))
    return CopperPlan(layers, tuple(tracks), tuple(arcs), tuple(vias), tuple(issues), stack, tuple(zones))


def with_copper(spec: pcbdoc.PcbDocSpec, plan: CopperPlan) -> pcbdoc.PcbDocSpec:
    """``spec`` with the layers and the copper of ``plan``."""
    return dataclasses.replace(
        spec,
        copper_layers=plan.layers,
        stack=plan.stack,
        tracks=plan.tracks,
        arcs=plan.arcs,
        vias=plan.vias,
        zones=plan.zones,
    )


def copper_summary(spec: pcbdoc.PcbDocSpec, *, source: str, where: str | None = None) -> dict[str, object]:
    """The ``copper`` object of the build's summary: what the planned document holds."""
    return {
        "source": source,
        "from": where,
        "layers": len(spec.copper_layers),
        "planes": {},
        "tracks": len(spec.tracks),
        "arcs": len(spec.arcs),
        "vias": len(spec.vias),
        "zones": sum(len(zone.layers) for zone in spec.zones),
        "net_classes": 0,
        "placements_from_board": 0,
    }


__all__ = [
    "COPPER_COUNTS",
    "COPPER_ISSUE_CODES",
    "CopperPlan",
    "board_layers",
    "copper_summary",
    "has_copper",
    "issue",
    "lower_copper",
    "mm_text",
    "outline_corner",
    "stack_from_stackup",
    "stack_values",
    "with_copper",
]
