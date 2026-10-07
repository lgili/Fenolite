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
``fenolite.lens.altium`` calls it from ``lowered_pcb`` and adds the codes to its closed table.

Change c0085 ("Complete board in an Altium build") lowers the rest of the board: a stack of any even
count that ``pcbrecords.copper_stack`` takes, blind and buried vias, and the free texts, graphics,
keep-outs and holes (``lower_items``). An item that has no record gives one ``altium.not-lowered`` whose
``where`` is ``<kind>/<id>``, and ``account`` counts every item of the board as written or not lowered.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Literal

from fenolite.backends.altium import pcbdoc, pcblib, pcbrecords, rulemap
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.docboard import Dielectric, StackSpec
from fenolite.backends.altium.lower import stack_unfit_reason, stack_unheld, stack_unheld_reason
from fenolite.backends.altium.project import component_path
from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.netnames import UNCONNECTED_PREFIX
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.lens.build import PlacementRequest
from fenolite.model.board import (
    Arc,
    Board,
    FootprintInstance,
    Graphic,
    Hole,
    Keepout,
    Side,
    Stackup,
    Text,
    Track,
    Via,
    Zone,
)
from fenolite.model.design import Design

COPPER_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "altium.copper-stack": "error",
        "altium.copper-layer": "error",
        "altium.via-unsupported": "warning",
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
STACK_HINT = (
    "make design.board(..., copper=…) equal to the board's copper layer count, "
    "or give the board its copper layers"
)
KINDS: tuple[str, ...] = (
    "footprint",
    "pad",
    "track",
    "arc",
    "via",
    "zone",
    "text",
    "graphic",
    "keep-out",
    "hole",
    "body",
    "rule",
)
"""The kinds of model items that ``account`` counts (capability altium-pcb-writer, "Written items are
accounted")."""
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
    texts: tuple[Text, ...] = ()
    graphics: tuple[Graphic, ...] = ()
    keepouts: tuple[Keepout, ...] = ()
    holes: tuple[Hole, ...] = ()
    counts: Mapping[str, tuple[int, int]] = dataclasses.field(default_factory=lambda: MappingProxyType({}))
    """Kind of ``KINDS`` → (items written, items not lowered), for the kinds the lowering decides."""

    @property
    def failed(self) -> bool:
        return any(found.severity == "error" for found in self.issues)


def layer_names(count: int) -> tuple[str, ...]:
    """The copper layers of a board of ``count`` layers that names none: ``F.Cu``, ``In1.Cu`` …, ``B.Cu``."""
    return ("F.Cu", *(f"In{index}.Cu" for index in range(1, count - 1)), "B.Cu")


def board_layers(design: Design, copper: int) -> tuple[tuple[str, ...], list[Issue]]:
    """The copper layers of the document: the copper layers of ``design.board.layers`` when it holds any,
    else those of the script's count ``copper``. A count that differs from ``copper``, or a repeated
    layer, gives ``altium.copper-stack``. A stack that ``pcbrecords.stack_problem`` refuses (an odd count,
    more than 32 layers) gives one ``altium.not-lowered`` with ``where`` ``stackup`` and the default
    stack of the two outer layers: no partial stack is written (change c0085)."""
    board = design.board
    named = tuple(layer.name for layer in board.layers if layer.kind == "copper") if board is not None else ()
    if named and len(set(named)) != len(named):
        message = f"the board's copper layers {', '.join(named)} repeat a layer"
        return named, [issue("altium.copper-stack", message, "stack", STACK_HINT)]
    if named and len(named) != copper:
        held = f"{len(named)} copper layers ({', '.join(named)})"
        message = f"the board holds {held}, the build asks for {copper}"
        return named, [issue("altium.copper-stack", message, "stack", STACK_HINT)]
    problem = pcbrecords.stack_problem(len(named) or copper, 0)
    if problem is None:
        return named or layer_names(copper), []
    outer = (named[0], named[-1]) if len(named) > 1 else layer_names(2)
    message = f"{problem}; the document gets the stack of {outer[0]} and {outer[1]} alone"
    return outer, [Issue("altium.not-lowered", "info", message, where="stackup")]


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
    """The vias to write: every via whose span is two copper layers of the board. A micro via gives
    ``altium.via-unsupported`` (a warning) and is not written (change c0085)."""
    out: list[Via] = []
    for via in vias:
        what = f"via at {low.at(via.position)}"
        before = len(issues)
        outside = [layer for layer in via.layers if layer not in low.layers]
        if via.via_type == "micro":
            spans = ", ".join(via.layers)
            message = f"{what}: a micro via ({spans}) is not written; through, blind and buried vias are"
            issues.append(
                issue(
                    "altium.via-unsupported",
                    low.text(message),
                    f"via/{via.id}",
                    "use a blind via of the same span, or place the via in Altium",
                )
            )
        elif outside:
            issues.append(
                issue(
                    "altium.copper-layer",
                    low.text(
                        f"{what}: {outside[0]} is not a copper layer of the board ({', '.join(low.layers)})"
                    ),
                    via.id,
                    "build the board with copper=4, or move the copper",
                )
            )
        elif len(via.layers) != 2 or via.layers[0] == via.layers[1]:
            spans = ", ".join(via.layers) or "no layer"
            message = f"{what}: the via spans {spans}, not two different copper layers"
            issues.append(issue("altium.copper-invalid", low.text(message), via.id))
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
                    "altium.copper-stack",
                    message,
                    layer,
                    "declare planes on inner copper layers of the board",
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


def dielectric_kinds(count: int) -> tuple[str, ...]:
    """The kind of each of ``count`` dielectrics of a stack-up, top to bottom: one core; else prepreg and
    core in turn, the outermost a prepreg (three: prepreg, core, prepreg). The model's stack-up names a
    material and no kind, so the kind is Fenolite's choice (``pcb-copper.md``, "Fenolite's choices")."""
    if count == 1:
        return ("core",)
    return tuple("core" if index % 2 else "prepreg" for index in range(count))


def stack_from_stackup(
    stackup: Stackup, layers: Sequence[str], copper: tuple[int, ...], nets: tuple[str, ...] = ()
) -> StackSpec | None:
    """The stack values of ``stackup`` when it fits the document: one copper layer per copper layer of the
    board, named like it and in order, with exactly one dielectric between neighbours; ``None`` otherwise.
    Solder mask, silkscreen and paste layers of the stack-up are passed over. A dielectric whose
    ``dielectric_kind`` is stated is written with that kind (``DIELTYPE``, ``pcb-copper.md``, "Layer
    stack"); one without keeps the kind of ``dielectric_kinds`` by count (change c0101)."""
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
            Dielectric(
                layer.dielectric_kind or kind,  # type: ignore[arg-type]
                layer.thickness,
                layer.epsilon_r or "4.800",
                layer.material or "FR-4",
            )
            for kind, layer in zip(dielectric_kinds(len(between)), between, strict=True)
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
        unheld = stack_unheld(stackup)
        if not unheld:
            return found, []
        return found, [Issue("altium.not-lowered", "info", stack_unheld_reason(unheld), where="stackup")]
    message = f"{stack_unfit_reason(stackup)}; the document gets Fenolite's default stack values"
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
"""Board fields that only the PCB document holds, and what a message calls them."""
BOARD_WHERES: tuple[str, ...] = tuple(name for name, _what in BOARD_KINDS)


def board_not_lowered(board: Board | None) -> list[Issue]:
    """One ``altium.not-lowered`` info per kind of board item that a build without a PCB document keeps in
    the model only: keep-outs, board texts, graphics and holes. A build that writes the document drops
    these infos: ``lower_items`` then writes the items, or reports each one (change c0085)."""
    if board is None:
        return []
    found: list[Issue] = []
    for field_name, what in BOARD_KINDS:
        count = len(getattr(board, field_name))
        if count:
            message = f"{count} {what} of the board are kept in the model only"
            found.append(Issue("altium.not-lowered", "info", message, where=field_name))
    return found


def _kept(kind: str, ident: str, message: str, hint: str = "") -> Issue:
    return Issue("altium.not-lowered", "info", message, where=f"{kind}/{ident}", hint=hint)


@dataclass(frozen=True, slots=True)
class LoweredItems:
    """The free items of a board that the document writes, and per kind (items written, not lowered)."""

    texts: tuple[Text, ...] = ()
    graphics: tuple[Graphic, ...] = ()
    keepouts: tuple[Keepout, ...] = ()
    holes: tuple[Hole, ...] = ()
    counts: Mapping[str, tuple[int, int]] = dataclasses.field(default_factory=lambda: MappingProxyType({}))


def lower_items(board: Board | None, layers: Sequence[str], issues: list[Issue]) -> LoweredItems:
    """The texts, graphics, keep-outs and holes of ``board`` that ``pcbdoc`` writes (change c0085,
    "Complete board in an Altium build"); ``layers`` are the copper layers of the document. An item that
    has no record gives one ``altium.not-lowered`` with ``where`` ``<kind>/<id>`` and its reason, and is
    left out. A graphic on ``Edge.Cuts`` is the outline, which the document writes from ``Board.outline``:
    it counts as written and is not passed on. A keep-out's ``no_footprints`` has no bit in the record: the
    keep-out is written with its other restrictions and one issue names the one that is lost. Component
    bodies are not decided here: ``lower_bodies`` places them on the components of the document."""
    if board is None:
        return LoweredItems()
    counts: dict[str, tuple[int, int]] = {}
    texts: list[Text] = []
    for text in board.texts:
        problem = pcbdoc.text_problem_of(text)
        if text.layer not in pcbrecords.BOARD_LAYER_MAP:
            problem = f"the layer {text.layer} has no layer in the document for a text"
        if problem is None:
            texts.append(text)
        else:
            issues.append(_kept("text", text.id, f"board text {text.text[:24]!r} is not written: {problem}"))
    counts["text"] = (len(texts), len(board.texts) - len(texts))
    graphics: list[Graphic] = []
    outline = 0
    for graphic in board.graphics:
        if graphic.layer == EDGE_LAYER:
            outline += 1
            continue
        problem = pcbdoc.graphic_problem(graphic)
        if problem is None:
            graphics.append(graphic)
        else:
            message = f"the {graphic.kind} on {graphic.layer} is not written: {problem}"
            issues.append(_kept("graphic", graphic.id, message))
    counts["graphic"] = (len(graphics) + outline, len(board.graphics) - len(graphics) - outline)
    keepouts: list[Keepout] = []
    for keepout in board.keepouts:
        problem = pcbdoc.keepout_problem(keepout, layers)
        if problem is not None:
            issues.append(_kept("keepout", keepout.id, f"the keep-out is not written: {problem}"))
            continue
        keepouts.append(keepout)
        if keepout.no_footprints:
            message = (
                "the restriction no_footprints of the keep-out is not written: the record holds vias, "
                "tracks, copper and pads only; the keep-out is written with its other restrictions"
            )
            issues.append(_kept("keepout", keepout.id, message, "add a component keep-out in Altium"))
    counts["keep-out"] = (len(keepouts), len(board.keepouts) - len(keepouts))
    holes: list[Hole] = []
    for hole in board.holes:
        if hole.drill > 0:
            holes.append(hole)
        else:
            message = f"the hole is not written: a drill of {mm_text(hole.drill)} mm is not positive"
            issues.append(_kept("hole", hole.id, message))
    counts["hole"] = (len(holes), len(board.holes) - len(holes))
    return LoweredItems(tuple(texts), tuple(graphics), tuple(keepouts), tuple(holes), counts)


BODIES_HINT = "build with --altium-bodies extruded"
BODY_HINT = "set the height on the footprint in Altium"


def lower_bodies(
    design: Design,
    spec: pcbdoc.PcbDocSpec,
    mode: pcbdoc.BodyMode,
    issues: list[Issue],
) -> tuple[tuple[pcbdoc.PlacedBody, ...], tuple[int, int]]:
    """The component bodies of the board's footprints that the document ``spec`` writes, and (bodies
    written, bodies not lowered) (change c0121, capability altium-pcb-writer, "Component bodies are
    reported"). With ``mode`` ``off`` none is written. With ``extruded`` a body is placed by the placement
    that ``spec`` gives the component of its footprint (``pcbdoc.place_body``), in the order of the
    components and, within one, of its bodies. Each body without a record gives one ``altium.not-lowered``
    with ``where`` ``body/<id>``, its height and its reason. A footprint without a body gives nothing: no
    body is derived from a courtyard or any other graphic, and no height is assumed."""
    board = design.board
    if board is None:
        return (), (0, 0)
    refs = {component.id: component.ref for component in design.circuit.components}
    index = {component.ref: number for number, component in enumerate(spec.components)}
    frame = spec.frame if spec.frame is not None else pcbdoc.Frame.of(spec.outline)
    placed: list[pcbdoc.PlacedBody] = []
    kept = 0
    for footprint in board.footprints:
        number = index.get(refs.get(footprint.component_id, ""))
        for body in footprint.bodies:
            if mode == "off":
                found: pcbdoc.PlacedBody | str = pcbdoc.BODIES_OFF
            elif number is None:
                found = pcbdoc.BODY_NO_FOOTPRINT
            else:
                component = spec.components[number]
                found = pcbdoc.place_body(
                    body,
                    component=number,
                    at=component.at,
                    rotation=component.rotation,
                    bottom=component.side == "bottom",
                    frame=frame,
                )
            if isinstance(found, str):
                kept += 1
                message = (
                    f"the component body {body.name or body.id} (height {mm_text(body.height)} mm) is not "
                    f"written: {found}"
                )
                issues.append(_kept("body", body.id, message, BODIES_HINT if mode == "off" else BODY_HINT))
            else:
                placed.append(found)
    placed.sort(key=lambda body: body.component)
    return tuple(placed), (len(placed), kept)


def account(
    design: Design, spec: pcbdoc.PcbDocSpec, plan: CopperPlan, source: Design | None = None
) -> dict[str, dict[str, int]]:
    """``result.pcb`` of a build that writes the document ``spec`` (capability altium-pcb-writer, "Written
    items are accounted"): ``written`` maps every kind of ``KINDS`` to the number of model items the
    document holds, and ``not_lowered`` the kinds with items that it does not hold to their number. The
    copper is that of ``source`` when the build took a copper source. ``RuntimeError`` when an item of a
    kind is in neither count: nothing is absent without a line."""
    board = design.board
    copper = (source or design).board
    rules = len(design.rules.rules) if design.rules is not None else 0
    lowered = sum(len(record.rules) for record in spec.design_rules)  # change c0084
    counts: dict[str, tuple[int, int]] = {
        "footprint": (len(spec.components), 0),
        "pad": (sum(len(component.footprint.defn.pads) for component in spec.components), 0),
        "rule": (lowered, rules - lowered),
        **plan.counts,
    }
    totals = {
        "track": len(copper.tracks) if copper is not None else 0,
        "arc": len(copper.arcs) if copper is not None else 0,
        "via": len(copper.vias) if copper is not None else 0,
        "zone": len(copper.zones) if copper is not None else 0,
        "text": len(board.texts) if board is not None else 0,
        "graphic": len(board.graphics) if board is not None else 0,
        "keep-out": len(board.keepouts) if board is not None else 0,
        "hole": len(board.holes) if board is not None else 0,
        "body": sum(len(fp.bodies) for fp in board.footprints) if board is not None else 0,
    }
    for kind, total in totals.items():
        written, kept = counts.get(kind, (0, 0))
        if written + kept != total:
            raise RuntimeError(
                f"altium build: {total} {kind} item(s) in the model, {written} written and {kept} reported"
            )
    return {
        "written": {kind: counts.get(kind, (0, 0))[0] for kind in KINDS},
        "not_lowered": {kind: counts[kind][1] for kind in KINDS if counts.get(kind, (0, 0))[1]},
    }


NO_DOCUMENT = "no-document"
"""Why no rule is written when the build plans no PCB document: a reason of the build, beside the reasons
of ``rulemap.NOT_LOWERED_REASONS``."""


def lowered_rules(design: Design) -> rulemap.Lowered:
    """The rules of ``design`` as rule records, and those that are not written (change c0084)."""
    return rulemap.lower(design.rules.rules if design.rules is not None else ())


def rules_report(design: Design, *, document: str | None) -> tuple[dict[str, object], list[Issue]]:
    """The ``rules`` object of the build's summary and one ``altium.not-lowered`` warning per rule of
    ``design`` that is not written, with ``where`` ``design-rules/<kind>`` (capability altium-build, "Rules
    in an Altium build"). ``document`` is the PCB document's name, or ``None`` when none is planned: then no
    rule is written and each one is reported with the reason ``no-document``."""
    lowered = lowered_rules(design)
    written = [
        {"kind": rule.kind, "selector": rulemap.rule_selector(rule), "rule": record.name}
        for record in (lowered.records if document is not None else ())
        for rule in record.rules
    ]
    refused: list[tuple[str, str, str, str, str]] = [
        (item.rule.name, item.kind, item.selector, item.reason, item.detail) for item in lowered.not_lowered
    ]
    if document is None:
        refused += [
            (rule.name, rule.kind, rulemap.rule_selector(rule), NO_DOCUMENT, "no PCB document is written")
            for rule in lowered.written
        ]
    issues = [
        Issue(
            "altium.not-lowered",
            "warning",
            f"the {kind} rule {name!r} ({selector}) is not written into the PCB document "
            f"({reason}): {detail}",
            where=f"design-rules/{kind}",
        )
        for name, kind, selector, reason, detail in refused
    ]
    not_lowered = [
        {"kind": kind, "selector": selector, "reason": reason}
        for _name, kind, selector, reason, _detail in refused
    ]
    return {"written": written, "not_lowered": not_lowered}, issues


def outline_corner(board: Board | None) -> Point:
    """The corner that positions in messages count from: the outline's lowest X and Y (KiCad frame)."""
    if board is None or board.outline is None or not board.outline.points:
        return Point(0, 0)
    points = board.outline.points
    return Point(min(p.x for p in points), min(p.y for p in points))


LOCK_WHERE = "copper/locked"
"""``where`` of the warning about locked copper written unlocked (change c0108)."""
LOCK_HINT = "lock the items in Altium Designer's editor after the import"


def locked_counts(
    tracks: Sequence[Track], arcs: Sequence[Arc], vias: Sequence[Via]
) -> dict[str, tuple[int, int]]:
    """Per record kind (``track``, ``arc``, ``via``): the locked items written locked and those written
    unlocked, because the kind is not in ``pcbrecords.LOCK_WRITTEN``."""
    out: dict[str, tuple[int, int]] = {}
    for kind, items in (("track", tracks), ("arc", arcs), ("via", vias)):
        count = sum(1 for item in items if item.locked)
        out[kind] = (count, 0) if kind in pcbrecords.LOCK_WRITTEN else (0, count)
    return out


def lock_issues(
    tracks: Sequence[Track], arcs: Sequence[Arc], vias: Sequence[Via], low: _Lowering | None = None
) -> list[Issue]:
    """One ``altium.not-lowered`` warning per record kind that holds a locked item and whose lock is not
    written (capability altium-build, "Copper locks in an Altium build"): a lock is never dropped in
    silence."""
    found: list[Issue] = []
    for kind, (_written, dropped) in locked_counts(tracks, arcs, vias).items():
        if dropped:
            message = (
                f"{dropped} locked {kind}(s) are written unlocked: the locked flag of a free {kind} is "
                "not recorded for the Altium document"
            )
            text = low.text(message) if low is not None else message
            found.append(Issue("altium.not-lowered", "warning", text, where=LOCK_WHERE, hint=LOCK_HINT))
    return found


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
    if design.board is None or board is None or any(found.severity == "error" for found in issues):
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
    issues += lock_issues(tracks, arcs, vias, low)
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
    items = lower_items(design.board, layers, issues)
    counts = {
        "track": (len(tracks), len(board.tracks) - len(tracks)),
        "arc": (len(arcs), len(board.arcs) - len(arcs)),
        "via": (len(vias), len(board.vias) - len(vias)),
        "zone": (len(board.zones), 0),
        **items.counts,
    }
    polygons = sum(len(zone.layers) for zone in zones)
    if polygons and not any(found.severity == "error" for found in issues):
        message = (
            f"{polygons} polygon(s) are written without poured copper: run '{REPOUR_COMMAND}' in Altium "
            "Designer to fill them"
        )
        issues.append(issue("altium.zones-unpoured", message, document, f"{REPOUR_COMMAND}"))
    return CopperPlan(
        layers,
        tuple(tracks),
        tuple(arcs),
        tuple(vias),
        tuple(issues),
        stack,
        tuple(zones),
        classes,
        items.texts,
        items.graphics,
        items.keepouts,
        items.holes,
        MappingProxyType(counts),
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
        texts=plan.texts,
        graphics=plan.graphics,
        keepouts=plan.keepouts,
        holes=plan.holes,
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
        "locked": {
            f"{kind}s": written
            for kind, (written, _dropped) in locked_counts(spec.tracks, spec.arcs, spec.vias).items()
        },
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


def pad_net_names(design: Design) -> dict[str, dict[str, str]]:
    """Component id → pad number → net name: the net of each pin on every pad that the component's
    pin-to-pad map names for it (``Component.pads_of``; a pin outside the map on the pad of its own number).
    The PCB document and the check of a copper source both read the nets by pad from here, so they cannot
    disagree about a mapped part (changes c0135 and c0123)."""
    by_id = {component.id: component for component in design.circuit.components}
    nets: dict[str, dict[str, str]] = {}
    for net in design.circuit.nets:
        for member in net.members:
            owner = by_id.get(member.component_id)
            for pad in owner.pads_of(member.pin) if owner is not None else (member.pin,):
                nets.setdefault(member.component_id, {})[pad] = net.name
    return nets


def library_pad_positions(footprint: FootprintInstance) -> list[tuple[str, int, int]]:
    """(number, x, y) of each pad of a source's footprint in the frame of its library definition (change
    c0142). A KiCad board stores the pads footprint-local and unrotated on both sides, and those of a
    bottom footprint mirrored about local X (``docs/formats/kicad/board.md``, ``H-G-BOTTOM-STORE``,
    ``KICAD-VERIFIED``): the mirror is undone by negating Y, and the footprint's rotation does not enter."""
    sign = -1 if footprint.side == "bottom" else 1
    return [(pad.number, pad.position.x, sign * pad.position.y) for pad in footprint.pads]


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
    be the linked one, with the pad numbers and positions of the definition in ``footprints`` (read in the
    definition's frame by ``library_pad_positions``, which undoes the mirror of a bottom footprint) and
    every pad on the net of the design's pin; and the outline's box must be the design's. Anything else gives
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
    pin_nets = pad_net_names(design)
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
            got = sorted(library_pad_positions(footprint))
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
    "BOARD_WHERES",
    "COPPER_COUNTS",
    "COPPER_ISSUE_CODES",
    "KINDS",
    "lower_bodies",
    "LoweredItems",
    "account",
    "dielectric_kinds",
    "layer_names",
    "library_pad_positions",
    "lower_items",
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
