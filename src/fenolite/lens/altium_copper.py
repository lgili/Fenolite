# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of the Altium PCB document, lowered from the model (change c0038, capability altium-build,
"Copper in an Altium build" and "Copper issue codes").

``lower_copper`` turns the tracks, arcs, vias and zones of a design into what ``pcbdoc.PcbDocSpec`` takes:
the board's copper layers and the entities with their net **names**. A zone becomes one unpoured polygon
per layer, which Altium fills on a repour. An inner layer that the script declares as a plane becomes an
internal plane on its net ("Internal planes in an Altium build"): it holds no primitive, and a zone of
the plane's net on that layer is left to the plane.

The copper comes from exactly one source: the model itself, or a ``CopperSource`` (the script's resolved
copper, or a routed KiCad board), which ``match_source`` checks against the design before its copper is
lowered the same way. The source's placements win. It finds every case the writer would
refuse and reports it as an issue of ``COPPER_ISSUE_CODES``, so no ``ValueError`` of the writer reaches the
user. Nothing is dropped to make a document fit: copper that cannot be written exactly is an error.
``fenolite.lens.altium`` calls it from ``pcb_document`` and adds the codes to its closed table.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Literal

from fenolite.backends.altium import pcbdoc, pcblib, pcbrecords
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.docboard import Dielectric, StackSpec
from fenolite.backends.altium.project import component_path
from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.netnames import UNCONNECTED_PREFIX
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.lens.build import PlacementRequest
from fenolite.model.board import Arc, Board, FootprintInstance, Side, Stackup, Track, Via, Zone
from fenolite.model.design import Design

COPPER_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "altium.copper-stack": "error",
        "altium.copper-layer": "error",
        "altium.via-unsupported": "error",
        "altium.copper-invalid": "error",
        "altium.zone-unsupported": "error",
        "altium.plane-copper": "error",
        "altium.copper-board-mismatch": "error",
        "altium.copper-net-missing": "error",
        "altium.copper-no-document": "error",
        "altium.zones-unpoured": "info",
        "altium.plane-zone-merged": "info",
        "altium.placement-from-board": "info",
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
    net_classes: tuple[pcbdoc.NetClassSpec, ...] = ()

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
    planes: Mapping[str, str] = dataclasses.field(default_factory=lambda: MappingProxyType({}))
    """Plane layer → the plane's net name."""
    known: frozenset[str] | None = None
    """The net names of the design, when the copper comes from a source (``None``: the model itself)."""
    missing: dict[str, list[str]] = dataclasses.field(default_factory=lambda: {})
    """Net name of a source that the design does not hold → the items on it, as message texts."""

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
    elif low.known is not None and name not in low.known:
        low.missing.setdefault(name, []).append(what)
    return name


PLANE_HINT = "a plane holds one net and no primitive; route on a signal layer, or drop the plane"


def _layer_ok(entity_id: str, layer: str, low: _Lowering, issues: list[Issue], what: str) -> bool:
    if layer in low.planes:
        message = (
            f"{what}: {layer} is an internal plane (net {low.planes[layer]}); split planes are not written"
        )
        issues.append(issue("altium.plane-copper", low.text(message), entity_id, PLANE_HINT))
        return False
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


def _zones(zones: Sequence[Zone], low: _Lowering, issues: list[Issue], merged: list[str]) -> list[Zone]:
    """The zones to write. A zone layer on a plane whose net is the plane's net is left to the plane and
    described in ``merged``; with another net, or none, it gives ``altium.plane-copper``."""
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
        kept: list[str] = []
        for layer in zone.layers:
            if layer not in low.planes:
                kept.append(layer)
            elif name is not None and low.planes[layer] == name:
                merged.append(f"the {name} zone on {layer}{where}")
            else:
                _layer_ok(zone.id, layer, low, issues, what)
        if len(issues) == before and kept:
            out.append(dataclasses.replace(zone, layers=tuple(kept), net_id=name, fills=()))
    return out


def plane_nets(
    design: Design, layers: Sequence[str], planes: Mapping[str, str] | None
) -> tuple[dict[str, str], list[Issue]]:
    """The planes of the document, layer → net name, in stack order. A plane on a layer that is not an
    inner copper layer of the board, or on a net that the design does not hold, gives
    ``altium.copper-stack``."""
    issues: list[Issue] = []
    nets = {net.name for net in design.circuit.nets}
    inner = list(layers[1:-1])
    found: dict[str, str] = {}
    for layer, net in (planes or {}).items():
        if layer not in inner:
            held = ", ".join(inner) or "none"
            message = (
                f"the plane on {layer} (net {net}) is not on an inner copper layer of the board ({held})"
            )
            issues.append(
                issue(
                    "altium.copper-stack", message, layer, "declare planes on In1.Cu or In2.Cu with copper=4"
                )
            )
        elif net not in nets:
            message = f"the plane on {layer} names the net {net}, which the design does not hold"
            issues.append(
                issue("altium.copper-stack", message, layer, "connect a pin to the net, or name another net")
            )
        else:
            found[layer] = net
    return {layer: found[layer] for layer in inner if layer in found}, issues


DIELECTRIC_KINDS = {1: ("core",), 3: ("prepreg", "core", "prepreg")}
"""The kind of each dielectric of a stack-up, by their count: one core, or prepreg, core, prepreg."""


def stack_from_stackup(
    stackup: Stackup, layers: Sequence[str], copper: tuple[int, ...], nets: tuple[str, ...] = ()
) -> StackSpec | None:
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
        return StackSpec(copper, tuple(layer.thickness for layer in coppers), dielectrics, nets)
    except ValueError:
        return None


def stack_values(
    design: Design, layers: Sequence[str], planes: Mapping[str, str] | None = None
) -> tuple[StackSpec, list[Issue]]:
    """The stack of the document: the ids of ``pcbrecords.copper_stack(layers, planes)`` with the plane
    nets, and the values of ``design.board.stackup`` when it fits (``stack_from_stackup``), else Fenolite's
    defaults with one ``altium.not-lowered`` info."""
    on_planes = planes or {}
    copper = pcbrecords.copper_stack(layers, tuple(on_planes))
    nets = tuple(on_planes.values())
    stackup = design.board.stackup if design.board is not None else None
    if stackup is None:
        return StackSpec.default(copper, nets), []
    found = stack_from_stackup(stackup, layers, copper, nets)
    if found is not None:
        return found, []
    message = (
        "the stack-up does not hold one copper layer per copper layer of the board with one dielectric "
        "between neighbours; the document gets Fenolite's default stack values"
    )
    return StackSpec.default(copper, nets), [Issue("altium.not-lowered", "info", message, where="stackup")]


def net_classes(design: Design, issues: list[Issue]) -> tuple[pcbdoc.NetClassSpec, ...]:
    """One class of the document per net class of ``design``, with the names of its nets. Net classes
    always come from the design, never from a copper source. A name that cannot be written, or that holds
    an apostrophe (a rule scope quotes it), gives ``altium.text-unwritable``."""
    members: dict[str, list[str]] = {}
    for net in design.circuit.nets:
        if net.netclass_id is not None:
            members.setdefault(net.netclass_id, []).append(net.name)
    found: list[pcbdoc.NetClassSpec] = []
    for item in sorted(design.circuit.netclasses, key=lambda c: c.name):
        problem = text_problem(item.name) or ("holds an apostrophe" if "'" in item.name else None)
        if problem is not None:
            message = f"net class name {item.name!r} {problem}"
            hint = (
                "use printable 7-bit ASCII without '|', without an apostrophe and without surrounding spaces"
            )
            issues.append(Issue("altium.text-unwritable", "error", message, where=item.name, hint=hint))
            continue
        found.append(
            pcbdoc.NetClassSpec(
                item.name,
                tuple(sorted(members.get(item.id, ()))),
                item.clearance,
                item.track_width,
                item.via_diameter,
                item.via_drill,
            )
        )
    return tuple(found)


BOARD_KINDS: tuple[tuple[str, str], ...] = (
    ("keepouts", "keep-outs"),
    ("texts", "board texts"),
    ("graphics", "graphics"),
    ("holes", "holes"),
)
"""Board fields the document has no record for, and what a message calls them."""


def board_not_lowered(board: Board | None) -> list[Issue]:
    """One ``altium.not-lowered`` info per kind of board item the PCB document does not write: keep-outs,
    board texts, graphics and holes."""
    if board is None:
        return []
    found: list[Issue] = []
    for field_name, what in BOARD_KINDS:
        count = len(getattr(board, field_name))
        if count:
            message = f"{count} {what} of the board are kept in the model only"
            found.append(Issue("altium.not-lowered", "info", message, where=field_name))
    return found


def outline_corner(board: Board | None) -> Point:
    """The corner that positions in messages count from: the outline's lowest X and Y (KiCad frame)."""
    if board is None or board.outline is None or not board.outline.points:
        return Point(0, 0)
    points = board.outline.points
    return Point(min(p.x for p in points), min(p.y for p in points))


def lower_copper(
    design: Design,
    *,
    copper: int = 2,
    planes: Mapping[str, str] | None = None,
    source: CopperSource | None = None,
    document: str = "",
) -> CopperPlan:
    """The copper of the document: the copper layers of ``design.board``, its stack with the planes of
    ``planes`` (layer name → net name), and the tracks, arcs, vias and zones of ``design.board`` (the
    ``model`` source) or of ``source`` with net names, or the issues that refuse them. Copper of a source on
    a net whose name the design does not hold gives one ``altium.copper-net-missing`` per net name.
    ``document`` is the document's file name, named by the infos about unpoured polygons and zones left to
    a plane."""
    layers, issues = board_layers(design, copper)
    held = source.design if source is not None else design
    board = held.board
    if design.board is None or board is None or issues:
        return CopperPlan(layers, issues=tuple(issues))
    on_planes, plane_issues = plane_nets(design, layers, planes)
    issues += plane_issues
    if plane_issues:
        return CopperPlan(layers, issues=tuple(issues))
    low = _Lowering(
        layers=layers,
        net_names={net.id: net.name for net in held.circuit.nets},
        corner=outline_corner(design.board),
        label=source.label if source is not None else "",
        planes=on_planes,
        known=frozenset(net.name for net in design.circuit.nets) if source is not None else None,
    )
    tracks = _tracks(board.tracks, low, issues)
    arcs = _arcs(board.arcs, low, issues)
    vias = _vias(board.vias, low, issues)
    merged: list[str] = []
    zones = _zones(board.zones, low, issues, merged)
    for name, items in sorted(low.missing.items()):
        count = f"{len(items)} item(s) on the net {name}"
        message = f"{count}, which the design does not hold; the first is a {items[0]}"
        issues.append(issue("altium.copper-net-missing", low.text(message), name, REBUILD_HINT))
    if merged:
        message = (
            f"{'; '.join(merged)}: left to the internal plane of that layer and net, not written as a polygon"
        )
        issues.append(issue("altium.plane-zone-merged", message, document))
    stack, stack_issues = stack_values(design, layers, on_planes)
    issues += stack_issues
    classes = net_classes(design, issues)
    polygons = sum(len(zone.layers) for zone in zones)
    if polygons and not any(found.severity == "error" for found in issues):
        message = (
            f"{polygons} polygon(s) are written without poured copper: run '{REPOUR_COMMAND}' in Altium "
            "Designer to fill them"
        )
        issues.append(issue("altium.zones-unpoured", message, document, f"{REPOUR_COMMAND}"))
    return CopperPlan(
        layers, tuple(tracks), tuple(arcs), tuple(vias), tuple(issues), stack, tuple(zones), classes
    )


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
        net_classes=plan.net_classes,
    )


def spec_planes(spec: pcbdoc.PcbDocSpec) -> dict[str, str]:
    """The planes of a spec: layer name → net name, in stack order."""
    if spec.stack is None:
        return {}
    layers = [
        name
        for name, layer in zip(spec.copper_layers, spec.stack.copper, strict=True)
        if layer >= pcbrecords.FIRST_PLANE
    ]
    return dict(zip(layers, spec.stack.plane_nets, strict=True))


def copper_summary(
    spec: pcbdoc.PcbDocSpec, *, source: str, where: str | None = None, placed: int = 0
) -> dict[str, object]:
    """The ``copper`` object of the build's summary: what the planned document holds. ``source`` is
    ``none``, ``model``, ``script`` or ``board``; ``where`` the board's path; ``placed`` the number of
    components placed from the board."""
    return {
        "source": source,
        "from": where,
        "layers": len(spec.copper_layers),
        "planes": spec_planes(spec),
        "tracks": len(spec.tracks),
        "arcs": len(spec.arcs),
        "vias": len(spec.vias),
        "zones": sum(len(zone.layers) for zone in spec.zones),
        "net_classes": len(spec.net_classes),
        "placements_from_board": placed,
    }


# --- copper sources (change c0038, "Script copper in an Altium build", "Copper from a routed KiCad board")

SourceOrigin = Literal["script", "board"]
SOURCE_ORIGINS: tuple[str, ...] = ("script", "board")
EDGE_LAYER = "Edge.Cuts"
REBUILD_HINT = "rebuild the KiCad project from the script, route that board, and pass it again"


@dataclass(frozen=True, slots=True)
class CopperSource:
    """Copper that comes from outside ``design.board``: a model with placed footprints and copper in the
    frame of its placements. ``origin`` is ``script`` (the model the KiCad build of the same script holds
    after its copper intents are resolved) or ``board`` (a routed KiCad board read from ``where``, the path
    as the user gave it)."""

    design: Design
    origin: SourceOrigin
    where: str = ""

    def __post_init__(self) -> None:
        if self.origin not in SOURCE_ORIGINS:
            raise ValueError(f"a copper source is of origin script or board, not {self.origin!r}")

    @property
    def label(self) -> str:
        """What opens every message about this source: the board's path, or ``script copper``."""
        return f"{self.where}: " if self.where else "script copper: "


@dataclass(frozen=True, slots=True)
class SourcePlacement:
    """Where a copper source places a component (a ``lens.build.PlacementRequest``)."""

    at: Point
    rotation: int
    side: Side
    locked: bool


def _box(points: Sequence[Point]) -> tuple[int, int, int, int] | None:
    if not points:
        return None
    return (
        min(p.x for p in points),
        min(p.y for p in points),
        max(p.x for p in points),
        max(p.y for p in points),
    )


def source_outline_box(board: Board | None) -> tuple[int, int, int, int] | None:
    """The bounding box of a source's outline: of its ``Edge.Cuts`` graphics, else of its ``Board.outline``.
    A circle counts with its whole extent."""
    if board is None:
        return None
    points: list[Point] = []
    for graphic in board.graphics:
        if graphic.layer != EDGE_LAYER:
            continue
        if graphic.kind == "circle" and len(graphic.points) == 2:
            centre, edge = graphic.points
            reach = max(abs(edge.x - centre.x), abs(edge.y - centre.y))
            points += [Point(centre.x - reach, centre.y - reach), Point(centre.x + reach, centre.y + reach)]
        else:
            points += graphic.points
    if not points and board.outline is not None:
        points = list(board.outline.points)
    return _box(points)


def _mismatch(source: CopperSource, message: str, where: str) -> Issue:
    return issue("altium.copper-board-mismatch", f"{source.label}{message}", where, REBUILD_HINT)


def match_source(
    design: Design,
    source: CopperSource,
    footprints: Mapping[str, pcblib.LibFootprint],
    *,
    requested: Mapping[str, PlacementRequest] | None = None,
) -> tuple[Mapping[str, PlacementRequest], list[Issue]]:
    """The placements a copper source gives the components of ``design``, and the issues of the match.

    Each component with a footprint link must match exactly one footprint of the source, by the
    ``fenolite.path`` property when the source's footprint holds it, else by reference; the footprint must
    be the linked one, with the pad numbers and positions of the definition in ``footprints`` and every pad
    on the net of the design's pin; and the outline's box must be the design's. Anything else gives
    ``altium.copper-board-mismatch``. The source's placements win: for a board, a placement that differs
    from the script's request ``requested`` gives one ``altium.placement-from-board`` info.
    """
    issues: list[Issue] = []
    board = source.design.board
    held = {component.id: component for component in source.design.circuit.components}
    by_path: dict[str, list[FootprintInstance]] = {}
    by_ref: dict[str, list[FootprintInstance]] = {}
    refs: dict[str, str] = {}
    for footprint in board.footprints if board is not None else ():
        component = held.get(footprint.component_id)
        refs[footprint.id] = component.ref if component is not None else footprint.id
        path = component.properties.get(PATH_PROPERTY) if component is not None else None
        if path:
            by_path.setdefault(path, []).append(footprint)
        else:
            by_ref.setdefault(refs[footprint.id], []).append(footprint)
    source_nets = {net.id: net.name for net in source.design.circuit.nets}
    # A board built beside a schematic names the net of each unconnected pin as KiCad does (c0061): a net
    # ``unconnected-(…)`` that holds one pad is that pad on no net.
    pads_on = Counter(
        pad.net_id for fp in (board.footprints if board is not None else ()) for pad in fp.pads if pad.net_id
    )
    open_nets = {
        net_id
        for net_id, name in source_nets.items()
        if name.startswith(UNCONNECTED_PREFIX) and pads_on[net_id] <= 1
    }
    pin_nets: dict[str, dict[str, str]] = {}
    for net in design.circuit.nets:
        for member in net.members:
            pin_nets.setdefault(member.component_id, {})[member.pin] = net.name
    used: set[str] = set()
    placements: dict[str, PlacementRequest] = {}
    moved: list[str] = []
    for component in sorted(design.circuit.components, key=component_path):
        link = component.lib_footprint_ref
        if not link:
            continue
        path, ref = component_path(component), component.ref
        found = [*by_path.get(path, ()), *by_ref.get(ref, ())]
        used.update(footprint.id for footprint in found)
        if not found:
            issues.append(_mismatch(source, f"{ref} has no footprint in the copper source", path))
            continue
        if len(found) > 1:
            issues.append(
                _mismatch(source, f"{ref} matches {len(found)} footprints of the copper source", path)
            )
            continue
        footprint = found[0]
        if footprint.lib_ref != link:
            message = f"{ref} is the footprint {footprint.lib_ref} there, the design links {link}"
            issues.append(_mismatch(source, message, path))
            continue
        definition = footprints.get(link)
        if definition is not None:
            wanted = sorted((pad.number, pad.position.x, pad.position.y) for pad in definition.defn.pads)
            got = sorted((pad.number, pad.position.x, pad.position.y) for pad in footprint.pads)
            if wanted != got:
                odd = sorted(set(got) ^ set(wanted))
                pad = odd[0][0] if odd else "?"
                message = (
                    f"{ref}: the pads of {link} differ from the footprint the design resolves (pad {pad})"
                )
                issues.append(_mismatch(source, message, path))
                continue
        for pad in footprint.pads:
            named = pad.net_id is not None and pad.net_id not in open_nets
            got_net = source_nets.get(pad.net_id or "") if named else None
            want_net = pin_nets.get(component.id, {}).get(pad.number)
            if got_net != want_net:
                message = (
                    f"pad {pad.number} of {ref} is on {got_net or 'no net'} there, the design puts it on "
                    f"{want_net or 'no net'}"
                )
                issues.append(_mismatch(source, message, f"{ref}.{pad.number}"))
        placement = SourcePlacement(footprint.position, footprint.rotation, footprint.side, footprint.locked)
        placements[path] = placement
        request = requested.get(path) if requested is not None else None
        if request is None or (request.at, request.rotation, request.side, request.locked) != (
            placement.at,
            placement.rotation,
            placement.side,
            placement.locked,
        ):
            moved.append(ref)
    for footprint in board.footprints if board is not None else ():
        if footprint.id not in used:
            ref = refs[footprint.id]
            issues.append(_mismatch(source, f"the footprint {ref} has no component in the design", ref))
    design_box = _box(design.board.outline.points) if design.board and design.board.outline else None
    source_box = source_outline_box(board)
    if design_box != source_box:

        def size(box: tuple[int, int, int, int] | None) -> str:
            return "none" if box is None else f"{mm_text(box[2] - box[0])} x {mm_text(box[3] - box[1])} mm"

        message = (
            f"the outline's box there ({size(source_box)}) is not the box of the design's outline "
            f"({size(design_box)}) at the same place"
        )
        issues.append(_mismatch(source, message, "outline"))
    if source.origin == "board" and moved and not any(found.severity == "error" for found in issues):
        message = (
            f"{source.label}{', '.join(moved)} placed as the board places them, not as the script requests: "
            "the copper is only right relative to the board's footprints"
        )
        issues.append(issue("altium.placement-from-board", message, source.where))
    return placements, issues


def source_not_lowered(source: CopperSource) -> list[Issue]:
    """One ``altium.not-lowered`` info per kind of item of a source that is not copied: keep-outs, texts,
    graphics (but for the outline) and holes."""
    board = source.design.board
    if board is None:
        return []
    kinds = (
        ("keep-outs", len(board.keepouts)),
        ("texts", len(board.texts)),
        ("graphics", sum(1 for graphic in board.graphics if graphic.layer != EDGE_LAYER)),
        ("holes", len(board.holes)),
    )
    return [
        Issue(
            "altium.not-lowered", "info", f"{source.label}{count} {kind} are not copied", where=source.where
        )
        for kind, count in kinds
        if count
    ]


__all__ = [
    "COPPER_COUNTS",
    "COPPER_ISSUE_CODES",
    "CopperPlan",
    "CopperSource",
    "SourcePlacement",
    "board_layers",
    "board_not_lowered",
    "copper_summary",
    "has_copper",
    "issue",
    "lower_copper",
    "match_source",
    "mm_text",
    "net_classes",
    "outline_corner",
    "source_not_lowered",
    "source_outline_box",
    "plane_nets",
    "spec_planes",
    "stack_from_stackup",
    "stack_values",
    "with_copper",
]
