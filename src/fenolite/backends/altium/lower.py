# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A neutral design with a board, lowered to what the Altium writers take (capability altium-pcb-writer,
"Imported boards are written from the model"; capability backend-protocol, "Altium write of a model";
change c0090).

``from_design`` reads nothing but the design: the footprints are the board's footprint instances with
their own pads, the copper, the free items, the rules, the stack and the classes are those of the model.
What the writers cannot carry is left out, counted per kind in ``AltiumInputs.not_lowered`` and reported
once per kind with ``altium.not-lowered``; nothing is approximated without a line. ``write_design`` hands
the inputs to ``pcbdoc.write_pcbdoc`` and ``project.write_project``.

A build from a script does not come through this module: it writes library footprints with their
graphics and pad settings, which a footprint instance of the model does not hold. ``stored_board`` gives
the board that such a build wrote, as model entities, so that the model a build stores holds it.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType

import fenolite.backends.altium.pcbdoc as pcbdoc
import fenolite.backends.altium.pcblib as pcblib
import fenolite.backends.altium.pcbrecords as rec
import fenolite.backends.altium.project as project
import fenolite.backends.altium.rulemap as rulemap
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.cfb import CompoundTooLarge
from fenolite.backends.altium.docboard import Dielectric, StackSpec
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.geometry.transform import FULL_TURN, Transform
from fenolite.model.board import (
    Arc,
    Board,
    FootprintInstance,
    Graphic,
    Hole,
    Keepout,
    Layer,
    Pad,
    Stackup,
    Text,
    Track,
    Via,
    Zone,
)
from fenolite.model.circuit import Component, Net, Pin
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-VER-RTA2-3", "H-A-VER-RTA3"))
"""The lowering is checked by Fenolite's own readers only: the documents it gives are read back and
compared (RT-A2 on a built project, RT-A3 on a document that was read)."""
BACKEND = "altium"
EDGE_LAYER = "Edge.Cuts"
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
"""The kinds of board items that a write accounts for: those of ``lens.altium_copper.KINDS``."""
MORE_KINDS: tuple[str, ...] = (
    "net",
    "netclass",
    "copper-shape",
    "zone-fill",
    "via-pad-shape",
    "via-protection",
    "plane",
    "stackup",
    "outline",
    "schematic",
    "pin-pad-map",
    "pin-pads",
    "module",
    "channel",
)
"""What a write of a model accounts for besides ``KINDS``: a net or a net class whose name no record
holds, a filled shape on a copper layer (the model holds it as a graphic), the poured copper of a zone (a
polygon is written unpoured), the layers on which a via has no pad shape (the via is written with a pad on
every layer; change c0132), an internal plane, the stack-up values, a part of the outline, and the
schematic. Of the circuit (change c0083): a module (the generated schematic is one sheet), and the channel
of a repeated sheet (the bag keys ``sheet_symbol`` and ``channel_index`` of a module). Of the pin-to-pad map
(change c0123, which writes the map as records of the footprint model): ``pin-pad-map`` is the map of a
component that has no footprint model in the generated schematic, and ``pin-pads`` a component whose bag
holds what the model's map cannot say (the key ``pin_pads``: a record without a pad, or with a pad that
another pin holds)."""
LOSS_KINDS: frozenset[str] = frozenset(
    {"footprint", "pad", "track", "arc", "via", "zone", "net", "netclass", "copper-shape", "plane"}
)
"""The kinds whose loss changes the board that is made: a write refuses them without ``allow_lossy``."""
NOT_LOWERED = "altium.not-lowered"
PAD_REMOVED_KEY = "pad_removed"
"""The bag key under which the import keeps the layers on which a via has no pad shape
(``adapter.copper.PAD_REMOVED_KEY``; change c0132)."""
ARC_KEY = "arc"
"""The bag key under which the import keeps the record of an arc (``adapter.copper.arc_pair``)."""
ARC_TOLERANCE = 2
"""How far, in nanometres per axis, a point of a kept arc record may lie from the point of the model and
the record still be written (change c0127): the length tolerance of the written scope
(``roundtrip.RT_A2_SCOPE``). An untouched arc gives its points exactly."""
_INT32 = range(-(2**31), 2**31)
_FINITE = (float("-inf"), float("inf"))
_FP_NATIVE = re.compile(r"fp:([A-Z]{8})")
_SIDE = re.compile(r"^([FB])(\.|&)")


class LossyWriteError(FenoliteError):
    """A write of a model would leave out items of ``LOSS_KINDS`` and ``allow_lossy`` was not given;
    ``issues`` holds one ``altium.not-lowered`` per kind."""

    cli_code = "FEN-7001"

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = tuple(issues)
        kinds = ", ".join(found.where for found in self.issues)
        super().__init__(f"the Altium documents would not hold every item of the model ({kinds})")


@dataclass(frozen=True, slots=True)
class AltiumInputs:
    """What the writers take for one design. ``pcb`` is ``None`` when no PCB document can be written;
    ``schematic`` is the design whose circuit the schematic writer takes. ``written`` counts the model
    items the PCB document holds, per kind; ``not_lowered`` maps a kind to the ids of the model entities
    that it does not hold, and ``reasons`` to the reason of the first one."""

    name: str
    pcb: pcbdoc.PcbDocSpec | None
    schematic: Design
    written: Mapping[str, int]
    not_lowered: Mapping[str, tuple[str, ...]]
    reasons: Mapping[str, str]
    bodies: pcbdoc.BodyMode = "off"
    """What the write did with component bodies (change c0121): ``extruded`` when it was asked to write
    them, whether or not the board holds one."""
    body_reasons: Mapping[str, int] = dataclasses.field(default_factory=lambda: MappingProxyType({}))
    """Reason → the number of component bodies that were not written for it."""

    def counts(self) -> dict[str, int]:
        """Kind → number of model items that are not written, for the kinds that have any."""
        return {kind: len(found) for kind, found in self.not_lowered.items() if found}


@dataclass(frozen=True, slots=True)
class ProjectWrite:
    """What ``write_design`` returns: the files of the project by name, the issues of the write, and the
    inputs they were written from."""

    files: Mapping[str, bytes]
    issues: tuple[Issue, ...]
    inputs: AltiumInputs


class _Account:
    def __init__(self) -> None:
        self.written: dict[str, int] = {}
        self.kept: dict[str, list[str]] = {}
        self.reasons: dict[str, str] = {}
        self.body_reasons: dict[str, int] = {}

    def wrote(self, kind: str, count: int = 1) -> None:
        self.written[kind] = self.written.get(kind, 0) + count

    def skip(self, kind: str, ident: str, reason: str) -> None:
        self.kept.setdefault(kind, []).append(ident)
        self.reasons.setdefault(kind, reason)

    def skip_body(self, ident: str, reason: str) -> None:
        """A component body that is not written, counted under ``body`` and by its reason."""
        self.skip("body", ident, reason)
        self.body_reasons[reason] = self.body_reasons.get(reason, 0) + 1

    def issues(self) -> list[Issue]:
        found: list[Issue] = []
        for kind in (*KINDS, *MORE_KINDS):
            ids = self.kept.get(kind)
            if not ids:
                continue
            severity: Severity = "warning" if kind in LOSS_KINDS else "info"
            more = " (the first reason)" if len(ids) > 1 else ""
            message = f"{len(ids)} {kind} item(s) of the model are not written: {self.reasons[kind]}{more}"
            found.append(Issue(NOT_LOWERED, severity, message, where=kind))
        return found


def pairs_of(entity: object) -> dict[str, str]:
    """The pairs of the ``altium`` bag of a model entity (the last value of a repeated key)."""
    bag = getattr(entity, "ext", {}).get(BACKEND)
    return dict(bag.payload) if bag is not None else {}


def kept_arc(entity: object, points: Sequence[Point], frame: pcbdoc.Frame) -> rec.ArcGeometry | None:
    """The arc record that ``entity`` was read from, when it still says the entity's three ``points``
    (start, middle and end in the model's frame); ``None`` otherwise (change c0127).

    The import keeps the record's centre, radius and angles in the pair ``arc`` of the entity's bag, because
    the model's three points do not give them back in every case. A bag is not updated when the model is
    edited, so the pair is used only when it converts, as the import converts it
    (``adapter.units.arc_points``), to points that lie within ``ARC_TOLERANCE`` per axis of ``points`` in
    ``frame``, the frame of the written document. A pair that is missing, that does not parse into three
    32-bit integers and two finite doubles, whose radius is not positive, whose angles make a full turn, or
    whose points lie further away (the arc was moved or reshaped, or the board is written in another frame
    than the document's) gives ``None``: the arc is then written from its points."""
    text = pairs_of(entity).get(ARC_KEY)
    if text is None or len(points) != 3:
        return None
    parts = text.split(",")
    if len(parts) != 5:
        return None
    try:
        cx, cy, radius = (int(part) for part in parts[:3])
        start, end = (float.fromhex(part) for part in parts[3:])
    except (ValueError, OverflowError):
        return None
    if radius <= 0 or any(value not in _INT32 for value in (cx, cy, radius)):
        return None
    if not all(_FINITE[0] < value < _FINITE[1] for value in (start, end)):  # also false for a NaN
        return None
    from fenolite.backends.altium.adapter import units

    first, last = units.angle(start)[0], units.angle(end)[0]
    if units.sweep(first, last) == FULL_TURN:
        return None
    for read, mine in zip(units.arc_points(cx, cy, radius, first, last), points, strict=True):
        at = frame(mine)  # the written document's frame is Y up; the import gives (x, -y)
        if abs(at.x - read.x) > ARC_TOLERANCE or abs(at.y + read.y) > ARC_TOLERANCE:
            return None
    return rec.ArcGeometry(cx, cy, radius, start, end)


def _field_ok(text: str) -> bool:
    """Whether a property record can hold ``text`` as a value."""
    try:
        rec.property_block((("A", text),))
    except ValueError:
        return False
    return True


def _open(points: Sequence[Point]) -> tuple[Point, ...]:
    return tuple(points[:-1]) if len(points) > 1 and points[0] == points[-1] else tuple(points)


# --- stack ----------------------------------------------------------------------------------------------


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


def stack_gap(stackup: Stackup) -> str | None:
    """The first gap between two copper entries that holds two or more dielectric entries (the sheets of one
    dielectric), as ``"between <upper> and <lower> (<n> dielectric entries)"``, or ``None``. The document
    holds one dielectric per gap, and sheets are never merged, dropped or averaged (change c0101)."""
    upper: str | None = None
    count = 0
    for layer in stackup.layers:
        if layer.kind == "copper":
            if upper is not None and count > 1:
                return f"between {upper} and {layer.name} ({count} dielectric entries)"
            upper, count = layer.name, 0
        elif layer.kind == "dielectric":
            count += 1
    return None


def stack_unheld(stackup: Stackup) -> tuple[str, ...]:
    """The kinds of value of ``stackup`` for which the document has no recorded key: a solder mask
    thickness above 0, a colour, the finish and the impedance-control flag (change c0101)."""
    found: list[str] = []
    if any(layer.kind == "soldermask" and layer.thickness > 0 for layer in stackup.layers):
        found.append("the solder mask thickness")
    if any(layer.color for layer in stackup.layers):
        found.append("the colours")
    if stackup.finish:
        found.append("the finish")
    if stackup.impedance_controlled:
        found.append("the impedance-control flag")
    return tuple(found)


def stack_unfit_reason(stackup: Stackup) -> str:
    """Why ``stackup`` does not fit the document, naming a gap of several sheets when there is one."""
    gap = stack_gap(stackup)
    if gap is not None:
        return (
            f"the stack-up holds several dielectric sheets {gap} and the document holds one dielectric per "
            "gap"
        )
    return (
        "the stack-up does not hold one copper layer per copper layer of the board with one dielectric "
        "between neighbours"
    )


def stack_unheld_reason(unheld: Sequence[str]) -> str:
    return f"the document has no key for {', '.join(unheld)}; the copper and dielectric values are written"


def _stack(
    board: Board, nets: frozenset[str], account: _Account
) -> tuple[tuple[str, ...], StackSpec, frozenset[str]]:
    """The copper layers of the document, top to bottom, their stack, and the layers that are planes."""
    copper: list[Layer] = [layer for layer in board.layers if layer.kind == "copper"]
    names = tuple(dict.fromkeys(layer.name for layer in copper)) or ("F.Cu", "B.Cu")
    planes: dict[str, str] = {}
    for layer in copper:
        net = pairs_of(layer).get("plane_net")
        if net is None:
            continue
        if layer.name in (names[0], names[-1]) or net not in nets:
            account.skip("plane", layer.id, f"the plane {layer.name} is on an outer layer or on no net")
        else:
            planes[layer.name] = net
    problem = rec.stack_problem(len(names), len(planes))
    if problem is not None and planes:
        for layer in copper:
            if layer.name in planes:
                account.skip("plane", layer.id, problem)
        planes = {}
        problem = rec.stack_problem(len(names), 0)
    if problem is not None:
        account.skip("stackup", board.id, f"{problem}; the stack of {names[0]} and {names[-1]} is written")
        names = (names[0], names[-1]) if len(names) > 1 else ("F.Cu", "B.Cu")
    ids = rec.copper_stack(names, tuple(planes))
    plane_nets = tuple(planes[name] for name in names if name in planes)
    found = None
    if board.stackup is not None and problem is None:
        found = stack_from_stackup(board.stackup, names, ids, plane_nets)
        if found is None:
            reason = f"{stack_unfit_reason(board.stackup)}; the default stack values are written"
            account.skip("stackup", board.stackup.id, reason)
        elif stack_unheld(board.stackup):
            account.skip("stackup", board.stackup.id, stack_unheld_reason(stack_unheld(board.stackup)))
    return names, found or StackSpec.default(ids, plane_nets), frozenset(planes)


# --- outline --------------------------------------------------------------------------------------------


def _ring_of(graphics: Sequence[Graphic], account: _Account) -> tuple[Point, ...]:
    """One closed ring from the graphics of the outline: a rectangle or a polygon alone, else lines and
    arcs chained by their end points (an arc gives its start, middle and end). Empty when none closes."""
    segments: list[tuple[Point, Point, tuple[Point, ...], Graphic]] = []
    for graphic in graphics:
        points = graphic.points
        if graphic.kind == "rect" and len(points) == 2:
            s, e = points
            return (s, Point(e.x, s.y), e, Point(s.x, e.y))
        if graphic.kind == "polygon" and len(_open(points)) >= 3:
            return _open(points)
        if graphic.kind == "line" and len(points) == 2 and points[0] != points[1]:
            segments.append((points[0], points[1], (), graphic))
        elif graphic.kind == "arc" and len(points) == 3:
            segments.append((points[0], points[2], (points[1],), graphic))
    if not segments:
        return ()
    first = segments[0]
    ring: list[Point] = [first[0], *first[2]]
    used = {0}
    arcs = [first[3]] if first[2] else []
    current = first[1]
    while current != ring[0]:
        for index, (a, b, mids, graphic) in enumerate(segments):
            if index in used or current not in (a, b):
                continue
            used.add(index)
            ring += [current, *(mids if current == a else reversed(mids))]
            current = b if current == a else a
            if mids:
                arcs.append(graphic)
            break
        else:
            return ()
    for graphic in arcs:
        account.skip("outline", graphic.id, "an arc of the outline is written as two straight edges")
    for index, segment in enumerate(segments):
        if index not in used:
            account.skip("outline", segment[3].id, "an edge outside the first ring of the outline")
    return tuple(ring) if len(ring) >= 3 else ()


def _extent(board: Board) -> tuple[Point, ...]:
    points: list[Point] = [fp.position for fp in board.footprints]
    points += [p for track in board.tracks for p in (track.start, track.end)]
    points += [via.position for via in board.vias]
    points += [p for zone in board.zones for p in zone.outline]
    points += [p for graphic in board.graphics for p in graphic.points]
    if not points:
        return ()
    x0, y0 = min(p.x for p in points), min(p.y for p in points)
    x1, y1 = max(p.x for p in points), max(p.y for p in points)
    if x0 == x1 or y0 == y1:
        x1, y1 = x1 + 1_000_000, y1 + 1_000_000
    return (Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1))


def _outline(board: Board, account: _Account) -> tuple[Point, ...]:
    """The outline of the document: ``Board.outline``, else the ring of the ``Edge.Cuts`` graphics, else
    the box of the board's items (reported)."""
    if board.outline is not None and len(_open(board.outline.points)) >= 3:
        if board.outline.cutouts:
            account.skip("outline", board.outline.id, "the cut-outs of the outline are not written")
        return _open(board.outline.points)
    ring = _ring_of([g for g in board.graphics if g.layer == EDGE_LAYER], account)
    if ring:
        return ring
    box = _extent(board)
    if box:
        account.skip(
            "outline", board.id, "the board holds no closed outline; the box of its items is written"
        )
    return box


# --- footprints -----------------------------------------------------------------------------------------


def _other_side(layer: str) -> str:
    return _SIDE.sub(lambda m: ("B" if m.group(1) == "F" else "F") + m.group(2), layer)


def _extras(pad: Pad, ratios: Mapping[str, Decimal]) -> pcblib.PadExtras:
    """The corner ratio of a rounded rectangle: the caller's, else the percentage the import kept."""
    ratio = ratios.get(pad.id)
    if ratio is None and pad.shape == "roundrect":
        percent = pairs_of(pad).get("corner_percent")
        try:
            ratio = Decimal(percent) / 200 if percent is not None else None
        except InvalidOperation:
            ratio = None
    return pcblib.PadExtras(corner_ratio=ratio)


def _pad_problem(pad: Pad, extras: pcblib.PadExtras, *, unnamed: bool = False) -> str | None:
    """Why the pad record cannot hold ``pad`` (``pcblib.check_footprint``), or ``None``. ``unnamed``
    accepts a pad without a number: a free pad has none."""
    probe = dataclasses.replace(pad, number="1") if unnamed and not pad.number else pad
    return pcblib.check_footprint(
        FootprintDef(id=pad.id, name="pad", pads=(probe,)), {pad.id: extras}
    ).refusal


def _library_pad(pad: Pad, *, bottom: bool) -> Pad:
    """An instance's pad as ``pcbdoc.place_component`` takes it: on the bottom side the writer mirrors the
    position and the angle and swaps the layers, so they are given as on the top side."""
    if not bottom:
        return dataclasses.replace(pad, net_id=None)
    return dataclasses.replace(
        pad,
        net_id=None,
        position=Point(pad.position.x, -pad.position.y),
        rotation=(-pad.rotation) % FULL_TURN,
        layers=tuple(_other_side(layer) for layer in pad.layers),
    )


def _link(text: str, suffix: str) -> tuple[str, str]:
    """``(library file, name)`` of a ``<library>:<name>`` reference, each ``""`` when no record holds it."""
    parts = project.split_link(text) if text else None
    library, name = parts if parts is not None else ("", text)
    if library and not library.lower().endswith(suffix.lower()):
        library += suffix
    return (library if _field_ok(library) else "", name if name and text_problem(name) is None else "")


def _footprints(
    design: Design,
    board: Board,
    net_names: Mapping[str, str],
    ratios: Mapping[str, Decimal],
    account: _Account,
    *,
    bodies: pcbdoc.BodyMode = "off",
    frame: pcbdoc.Frame | None = None,
    placed_bodies: list[pcbdoc.PlacedBody] | None = None,
) -> tuple[list[pcbdoc.PlacedComponent], list[pcbdoc.FreePad]]:
    """The components and the free pads of the document. With ``bodies`` ``extruded`` (change c0121) the
    bodies of a written footprint that have a record are appended to ``placed_bodies``, placed in
    ``frame``; every other body is counted with its reason."""
    components = {component.id: component for component in design.circuit.components}

    def skip_bodies(fp: FootprintInstance, reason: str) -> None:
        for body in fp.bodies:
            account.skip_body(body.id, reason)

    links = unique_links(design)
    placed: list[pcbdoc.PlacedComponent] = []
    free: list[pcbdoc.FreePad] = []
    for fp in board.footprints:
        component = components.get(fp.component_id)
        ref = component.ref if component is not None else ""
        if not ref and not fp.lib_ref and len(fp.pads) == 1:
            pad = fp.pads[0]
            extras = _extras(pad, ratios)
            problem = _pad_problem(pad, extras, unnamed=True)
            if problem is not None:
                account.skip("footprint", fp.id, f"a free pad: {problem}")
                account.skip("pad", pad.id, problem)
                skip_bodies(fp, pcbdoc.BODY_NO_FOOTPRINT)
                continue
            at = Transform.placement(fp.position, fp.rotation).apply(pad.position)
            rotation = (fp.rotation + pad.rotation) % FULL_TURN
            moved = dataclasses.replace(pad, position=at, rotation=rotation)
            free.append(pcbdoc.FreePad(moved, extras, net_names.get(pad.net_id or "")))
            account.wrote("footprint")
            account.wrote("pad")
            skip_bodies(fp, "a free pad is no component, and a body is written with a component")
            continue
        if not _field_ok(ref):
            account.skip("footprint", fp.id, f"the reference {ref!r} holds '|', which no record holds")
            for pad in fp.pads:
                account.skip("pad", pad.id, "its footprint is not written")
            skip_bodies(fp, pcbdoc.BODY_NO_FOOTPRINT)
            continue
        bottom = fp.side == "bottom"
        pads: list[Pad] = []
        extras_of: dict[str, pcblib.PadExtras] = {}
        nets_by_pad: dict[str, str] = {}
        for pad in fp.pads:
            extras = _extras(pad, ratios)
            problem = _pad_problem(pad, extras)
            if problem is not None:
                account.skip("pad", pad.id, problem)
                continue
            pads.append(_library_pad(pad, bottom=bottom))
            extras_of[pad.id] = extras
            name = net_names.get(pad.net_id or "")
            if name is not None:
                nets_by_pad[pad.id] = name
        library, pattern = _link(fp.lib_ref, ".PcbLib")
        symbol_library, symbol = _link(component.lib_symbol_ref if component is not None else "", ".SchLib")
        defn = FootprintDef(id=fp.id, name=pattern or "FOOTPRINT", pads=tuple(pads))
        native = _FP_NATIVE.fullmatch(fp.native_ids.get(BACKEND, ""))
        linked = links.get(component.id) if component is not None else None
        placed.append(
            pcbdoc.PlacedComponent(
                ref=ref,
                unique_id=linked or project.unique_id(component.id if component is not None else fp.id),
                comment=component.value if component is not None else "",
                footprint=pcblib.LibFootprint(defn, extras_of),
                footprint_library=library,
                lib_reference=symbol,
                component_library=symbol_library,
                at=fp.position,
                rotation=fp.rotation,
                side=fp.side,
                locked=fp.locked,
                nets_by_pad=nets_by_pad,
                record_unique_id=native.group(1) if native is not None else None,
            )
        )
        account.wrote("footprint")
        account.wrote("pad", len(pads))
        for body in fp.bodies:
            if bodies == "off" or frame is None or placed_bodies is None:
                account.skip_body(body.id, pcbdoc.BODIES_OFF)
                continue
            found = pcbdoc.place_body(
                body,
                component=len(placed) - 1,
                at=fp.position,
                rotation=fp.rotation,
                bottom=bottom,
                frame=frame,
            )
            if isinstance(found, str):
                account.skip_body(body.id, found)
            else:
                placed_bodies.append(found)
                account.wrote("body")
    return placed, free


# --- copper and free items ------------------------------------------------------------------------------


def _copper(
    board: Board,
    layers: Sequence[str],
    planes: frozenset[str],
    net_names: Mapping[str, str],
    frame: pcbdoc.Frame,
    account: _Account,
    *,
    full_drill: bool = False,
) -> tuple[list[Track], list[Arc], list[Via], list[Zone], dict[str, rec.ArcGeometry]]:
    signal = [name for name in layers if name not in planes]
    records: dict[str, rec.ArcGeometry] = {}

    def named(net_id: str | None) -> str | None:
        return net_names.get(net_id or "")

    def layer_problem(layer: str) -> str | None:
        if layer in planes:
            return f"{layer} is an internal plane, which holds no primitive"
        return None if layer in signal else f"{layer} is not a copper layer of the written stack"

    tracks: list[Track] = []
    for track in board.tracks:
        problem = layer_problem(track.layer)
        if problem is None and track.width <= 0:
            problem = "a track needs a positive width"
        if problem is None and track.start == track.end:
            problem = "the track has zero length"
        if problem is not None:
            account.skip("track", track.id, problem)
        else:
            tracks.append(dataclasses.replace(track, net_id=named(track.net_id)))
    arcs: list[Arc] = []
    for arc in board.arcs:
        problem = layer_problem(arc.layer)
        if problem is None and arc.width <= 0:
            problem = "an arc needs a positive width"
        if problem is None:
            kept = kept_arc(arc, (arc.start, arc.mid, arc.end), frame)
            if kept is not None:
                records[arc.id] = kept
            else:
                try:
                    rec.arc_from_points(*(frame(p) for p in (arc.start, arc.mid, arc.end)))
                except ValueError as error:
                    problem = str(error)
        if problem is not None:
            account.skip("arc", arc.id, problem)
        else:
            arcs.append(dataclasses.replace(arc, net_id=named(arc.net_id)))
    vias: list[Via] = []
    for via in board.vias:
        problem = None
        try:
            pcbdoc.via_span(via, layers)
        except ValueError as error:
            problem = str(error).partition(": ")[2] or str(error)
        full = full_drill and 0 < via.drill == via.diameter  # a rewrite of a document that was read
        if problem is None and not (0 < via.drill < via.diameter or full):
            problem = "the drill is not below the diameter"
        if problem is not None:
            account.skip("via", via.id, problem)
        else:
            vias.append(dataclasses.replace(via, net_id=named(via.net_id)))
            unwritten = pcbdoc.unwritten_features(via, board.via_protection)
            if unwritten:
                account.skip(
                    "via-protection",
                    via.id,
                    f"{', '.join(unwritten)} of the via is not written: the Altium document holds the "
                    "tenting of a via only",
                )
            if PAD_REMOVED_KEY in pairs_of(via):
                account.skip(
                    "via-pad-shape",
                    via.id,
                    "the layers on which a via has no pad shape are not written: the written via has its "
                    "pad on every layer of its span",
                )
    zones: list[Zone] = []
    for zone in board.zones:
        outline = _open(zone.outline)
        kept = tuple(layer for layer in zone.layers if layer in signal)
        problem = None
        if len(outline) < 3:
            problem = "the model holds no outline of the zone (an outline with an arc is kept by the reader)"
        elif not kept:
            problem = (
                f"none of its layers ({', '.join(zone.layers) or 'none'}) is a signal layer of the stack"
            )
        if problem is not None:
            account.skip("zone", zone.id, problem)
            continue
        if zone.fills:
            account.skip("zone-fill", zone.id, "a polygon is written unpoured; Altium fills it on a repour")
        name = zone.name if text_problem(zone.name) is None else ""
        zones.append(
            dataclasses.replace(
                zone, outline=outline, layers=kept, net_id=named(zone.net_id), fills=(), name=name
            )
        )
    account.wrote("track", len(tracks))
    account.wrote("arc", len(arcs))
    account.wrote("via", len(vias))
    account.wrote("zone", len(zones))
    return tracks, arcs, vias, zones, records


def _items(
    board: Board,
    layers: Sequence[str],
    frame: pcbdoc.Frame,
    records: dict[str, rec.ArcGeometry],
    account: _Account,
) -> tuple[list[Text], list[Graphic], list[Keepout], list[Hole]]:
    texts: list[Text] = []
    for text in board.texts:
        problem = pcbdoc.text_problem_of(text)
        if text.layer not in rec.BOARD_LAYER_MAP:
            problem = f"the layer {text.layer} has no layer in the document for a text"
        if problem is None:
            texts.append(text)
        else:
            account.skip("text", text.id, problem)
    graphics: list[Graphic] = []
    outline = 0
    for graphic in board.graphics:
        if graphic.layer == EDGE_LAYER:
            outline += 1
            continue
        if graphic.layer.endswith(".Cu"):
            account.skip("copper-shape", graphic.id, "a shape on a copper layer has no record written")
            continue
        kept = kept_arc(graphic, graphic.points, frame) if graphic.kind == "arc" else None
        problem = pcbdoc.graphic_problem(graphic, arc_known=kept is not None)
        if problem is None and graphic.layer not in rec.BOARD_LAYER_MAP:
            problem = f"the layer {graphic.layer} has no layer in the document"
        if problem is None:
            graphics.append(graphic)
            if kept is not None:
                records[graphic.id] = kept
        else:
            account.skip("graphic", graphic.id, problem)
    keepouts: list[Keepout] = []
    for keepout in board.keepouts:
        problem = pcbdoc.keepout_problem(keepout, layers)
        if problem is None:
            keepouts.append(keepout)
        else:
            account.skip("keep-out", keepout.id, problem)
    holes: list[Hole] = []
    for hole in board.holes:
        if hole.drill > 0:
            holes.append(hole)
        else:
            account.skip("hole", hole.id, "a hole needs a positive drill")
    account.wrote("text", len(texts))
    account.wrote("graphic", len(graphics) + outline)
    account.wrote("keep-out", len(keepouts))
    account.wrote("hole", len(holes))
    return texts, graphics, keepouts, holes


def _classes(design: Design, nets: frozenset[str], account: _Account) -> tuple[pcbdoc.NetClassSpec, ...]:
    members: dict[str, list[str]] = {}
    for net in design.circuit.nets:
        if net.netclass_id is not None and net.name in nets:
            members.setdefault(net.netclass_id, []).append(net.name)
    found: list[pcbdoc.NetClassSpec] = []
    for item in sorted(design.circuit.netclasses, key=lambda c: c.name):
        if text_problem(item.name) is not None or "'" in item.name:
            account.skip("netclass", item.id, f"no record holds the name {item.name!r}")
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


# --- the schematic's design -----------------------------------------------------------------------------


def unique_links(design: Design) -> dict[str, str]:
    """Component id → the native unique id that the written documents reuse for it
    (``project.native_unique_id``): only an id that one component alone holds. The instances of a repeated
    sheet share the id of their schematic part, and a link must name one component."""
    found = {c.id: project.native_unique_id(c) for c in design.circuit.components}
    count: dict[str, int] = {}
    for unique in found.values():
        if unique is not None:
            count[unique] = count.get(unique, 0) + 1
    return {ident: unique for ident, unique in found.items() if unique is not None and count[unique] == 1}


def schematic_design(design: Design, name: str) -> Design:
    """The design whose circuit the schematic writer takes: every component with a reference, a symbol
    link, a value and pins. A component without a reference (a free pad) is left out with its net
    members; a symbol link that is not ``<library>:<name>`` becomes ``<name>.SchLib:<its text or PART>``;
    a component without pins gets one passive pin per pin its nets name, and a pin without a name is named
    by its number. A part of a link that no record holds (a library named outside 7-bit ASCII) is
    replaced the same way, and a footprint link that no record holds is left out. Two components of one
    path (two footprints of one reference on a board read alone) get paths of their own, and a native
    unique id that two components share (the instances of a repeated sheet) is not reused. The schematic
    is generated: no drawing of the source is kept."""
    used: dict[str, list[str]] = {}
    for net in design.circuit.nets:
        for member in net.members:
            used.setdefault(member.component_id, []).append(member.pin)
    links = unique_links(design)
    paths: dict[str, int] = {}
    components: list[Component] = []
    for component in design.circuit.components:
        if not component.ref:
            continue
        link = component.lib_symbol_ref
        parts = project.split_link(link)
        if parts is None:
            _library, symbol = _link(component.lib_footprint_ref, ".PcbLib")
            link = f"{name}.SchLib:{link if link and text_problem(link) is None else symbol or 'PART'}"
        elif text_problem(parts[0]) is not None or text_problem(parts[1]) is not None:
            link = f"{name}.SchLib:{parts[1] if text_problem(parts[1]) is None else 'PART'}"
        path = project.component_path(component)
        seen = paths.get(path, 0)
        paths[path] = seen + 1
        if seen:
            properties = {**component.properties, project.PATH_PROPERTY: f"{path}#{seen + 1}"}
            component = dataclasses.replace(component, properties=properties)
        if component.id not in links and BACKEND in component.native_ids:
            native = {key: value for key, value in component.native_ids.items() if key != BACKEND}
            component = dataclasses.replace(component, native_ids=native)
        pins = tuple(
            pin if pin.name else dataclasses.replace(pin, name=pin.number)
            for pin in component.pins
            if pin.number
        )
        if not pins:
            pins = tuple(
                Pin(
                    id=derived_id("pin", BACKEND, f"pin:{component.id}:{number}"),
                    number=number,
                    name=number,
                    etype="passive",
                )
                for number in dict.fromkeys(used.get(component.id, ()))
            )
        footprint = component.lib_footprint_ref
        found = project.split_link(footprint)
        if found is None or text_problem(found[0]) is not None or text_problem(found[1]) is not None:
            footprint = ""
        components.append(
            dataclasses.replace(
                component,
                lib_symbol_ref=link,
                lib_footprint_ref=footprint,
                pins=pins,
                value=component.value or link.rpartition(":")[2],
            )
        )
    kept = {component.id: {pin.number for pin in component.pins} for component in components}
    nets: list[Net] = []
    for net in design.circuit.nets:
        members = tuple(m for m in net.members if m.pin in kept.get(m.component_id, ()))
        nets.append(dataclasses.replace(net, members=members))
    marks = tuple(m for m in design.circuit.no_connects if m.pin in kept.get(m.component_id, ()))
    circuit = dataclasses.replace(
        design.circuit, components=tuple(components), nets=tuple(nets), no_connects=marks
    )
    return dataclasses.replace(design, circuit=circuit)


# --- the lowering ---------------------------------------------------------------------------------------


def design_name(design: Design) -> str:
    """The stem of the written files: the design's name when a file name and a record can hold it."""
    name = design.header.name
    safe = name and text_problem(name) is None and not set(name) & set('\\/:*?"<>')
    return name if safe else "design"


def from_design(
    design: Design,
    *,
    issues: list[Issue],
    corner_ratios: Mapping[str, Decimal] | None = None,
    rewrite: bool = False,
    bodies: str = "off",
) -> AltiumInputs:
    """The inputs of the PCB and schematic writers from ``design`` alone. ``corner_ratios`` maps a pad id
    to the corner ratio of its rounded rectangle, for a caller that knows what the model does not hold (a
    board read from KiCad keeps the ratio in KiCad's own bag); a pad read from an Altium document carries
    it. One ``altium.not-lowered`` per kind of item that is not written is added to ``issues``.

    ``rewrite`` (change c0128) is the caller's statement that ``design`` is the reading of an Altium
    document and that the write gives the document back: a via whose drill equals its diameter, which a
    saved document can hold and a build refuses, is then written as it was read. It is not inferred from
    the design, and ``ValueError`` refuses it for a board that was not read from an Altium document.

    ``bodies`` (change c0121) is ``off`` (the default) or ``extruded``; another value raises ``ValueError``.
    With ``extruded`` the extruded component bodies of the footprint instances that have an outline and a
    height above their standoff are written into the document (``pcbdoc.place_body``); every other body,
    and every body with ``off``, is left out and counted under ``body``. The definition that is
    synthesised from an instance holds no body: the document carries them. ``rewrite`` does not decide
    it."""
    body_mode = pcbdoc.body_mode(bodies)
    account = _Account()
    name = design_name(design)
    board = design.board
    if rewrite and board is not None and BACKEND not in board.native_ids:
        raise ValueError(
            "rewrite=True is for the reading of an Altium document; this board was not read from one"
        )
    spec: pcbdoc.PcbDocSpec | None = None
    if board is not None:
        outline = _outline(board, account)
        if len(outline) >= 3:
            spec = _document(
                design, board, outline, corner_ratios or {}, account, rewrite=rewrite, bodies=body_mode
            )
    schematic = schematic_design(design, name)
    modelled = {component.id: component.lib_footprint_ref for component in schematic.circuit.components}
    for component in design.circuit.components:
        if component.pin_pad_map and not modelled.get(component.id):
            reason = "the component has no footprint model in the generated schematic to hold its map"
            account.skip("pin-pad-map", component.id, reason)
        if "pin_pads" in pairs_of(component):
            reason = "a map record that names no pad, or a pad that another pin holds, is not written"
            account.skip("pin-pads", component.id, reason)
    for module in design.circuit.modules:
        account.skip(
            "module", module.id, "the generated schematic is one sheet: no sheet of a module is written"
        )
        if "channel_index" in pairs_of(module):
            account.skip(
                "channel", module.id, "a repeated sheet is not written: its components are on the one sheet"
            )
    issues += account.issues()
    return AltiumInputs(
        name,
        spec,
        schematic,
        MappingProxyType(dict(account.written)),
        MappingProxyType({kind: tuple(found) for kind, found in account.kept.items()}),
        MappingProxyType(dict(account.reasons)),
        body_mode,
        MappingProxyType(dict(sorted(account.body_reasons.items()))),
    )


def _document(
    design: Design,
    board: Board,
    outline: tuple[Point, ...],
    ratios: Mapping[str, Decimal],
    account: _Account,
    *,
    rewrite: bool = False,
    bodies: pcbdoc.BodyMode = "off",
) -> pcbdoc.PcbDocSpec:
    net_names: dict[str, str] = {}
    for net in design.circuit.nets:
        if net.name and _field_ok(net.name) and net.name not in net_names.values():
            net_names[net.id] = net.name
        else:
            account.skip("net", net.id, f"no net record holds the name {net.name!r}, or two nets share it")
    nets = frozenset(net_names.values())
    layers, stack, planes = _stack(board, nets, account)
    read = BACKEND in board.native_ids
    frame = pcbdoc.Frame.document() if read else pcbdoc.Frame.of(outline)
    origin: Point | None = None
    if read:
        origin = Point(0, 0)
        texts = pairs_of(board).get("origin", "").split(",")
        if len(texts) == 2:
            from fenolite.backends.altium.adapter.units import text_length

            found = [text_length(text) for text in texts]
            if found[0] is not None and found[1] is not None:
                origin = Point(found[0][0], found[1][0])
    placed_bodies: list[pcbdoc.PlacedBody] = []
    components, free_pads = _footprints(
        design, board, net_names, ratios, account, bodies=bodies, frame=frame, placed_bodies=placed_bodies
    )
    tracks, arcs, vias, zones, arc_records = _copper(
        board, layers, planes, net_names, frame, account, full_drill=rewrite
    )
    texts_, graphics, keepouts, holes = _items(board, layers, frame, arc_records, account)
    lowered = rulemap.lower(design.rules.rules if design.rules is not None else ())
    account.wrote("rule", sum(len(record.rules) for record in lowered.records))
    for item in lowered.not_lowered:
        account.skip("rule", item.rule.id, f"{item.kind} ({item.selector}): {item.reason}")
    return pcbdoc.PcbDocSpec(
        outline,
        tuple(components),
        tuple(sorted(nets)),
        copper_layers=layers,
        stack=stack,
        tracks=tuple(tracks),
        arcs=tuple(arcs),
        vias=tuple(vias),
        via_protection=board.via_protection,  # the default of the tenting flags (c0112)
        zones=tuple(zones),
        net_classes=_classes(design, nets, account),
        texts=tuple(texts_),
        graphics=tuple(graphics),
        keepouts=tuple(keepouts),
        holes=tuple(holes),
        design_rules=lowered.records,
        frame=frame,
        origin=origin,
        free_pads=tuple(free_pads),
        arc_records=MappingProxyType(arc_records),
        allow_full_drill=rewrite,
        bodies=tuple(placed_bodies),
    )


def write_design(
    design: Design,
    *,
    allow_lossy: bool = False,
    corner_ratios: Mapping[str, Decimal] | None = None,
    rewrite: bool = False,
    bodies: str = "off",
) -> ProjectWrite:
    """The files of an Altium project written from ``design`` alone: ``<name>.PcbDoc`` when the design
    holds a board with an outline or an item, and ``<name>.SchDoc`` with its libraries and
    ``<name>.PrjPcb`` when the schematic writer takes the circuit (otherwise one ``altium.not-lowered``
    with ``where`` ``schematic`` says why). Without ``allow_lossy``, ``LossyWriteError`` when an item of
    ``LOSS_KINDS`` would be left out. Two calls on equal designs give equal bytes. ``rewrite`` is that of
    ``from_design``: the write of the reading of an Altium document. ``bodies`` is that of ``from_design``
    too: ``extruded`` writes the extruded component bodies (change c0121)."""
    issues: list[Issue] = []
    inputs = from_design(design, issues=issues, corner_ratios=corner_ratios, rewrite=rewrite, bodies=bodies)
    lost = [found for found in issues if found.where in LOSS_KINDS]
    if lost and not allow_lossy:
        raise LossyWriteError(lost)
    name = inputs.name
    files: dict[str, bytes] = {}
    try:
        files.update(project.write_project(inputs.schematic, name=name, issues=issues, pcb=inputs.pcb))
    except CompoundTooLarge:
        raise
    except (ValueError, KeyError) as error:
        message = f"the schematic and the project file are not written: {error}"
        issues.append(Issue(NOT_LOWERED, "info", message, where="schematic"))
        if inputs.pcb is not None:
            files[f"{name}.PcbDoc"] = pcbdoc.write_pcbdoc(inputs.pcb, filename=f"{name}.PcbDoc")
    return ProjectWrite(MappingProxyType(dict(sorted(files.items()))), tuple(issues), inputs)


# --- the board a build wrote ----------------------------------------------------------------------------


def stored_board(design: Design, spec: pcbdoc.PcbDocSpec) -> Board:
    """The board of ``design`` with what the PCB document ``spec`` holds, as model entities in the frame
    of the design (change c0090, "RT-A2 on a written model"): one footprint per placed component with the
    pads that are written, and the tracks, arcs, vias and zones of ``spec`` with the design's net ids. A
    zone is one entity per written polygon, so a zone on two layers is two. The board's other fields are
    kept. Ids are derived from the component's id and the entity's place. A footprint holds the component
    bodies that ``spec`` writes for its component (change c0121) and no other: the stored board of a build
    without ``--altium-bodies extruded`` holds no body, as before."""
    board = design.board
    if board is None:
        raise ValueError("the design holds no board")
    net_ids = {net.name: net.id for net in design.circuit.nets}
    by_ref = {component.ref: component for component in design.circuit.components}
    model_bodies = {body.id: body for footprint in board.footprints for body in footprint.bodies}
    footprints: list[FootprintInstance] = []
    for number, placed in enumerate(spec.components):
        component = by_ref[placed.ref]
        bottom = placed.side == "bottom"
        to_board = Transform.placement(placed.at, placed.rotation, mirror=bottom)
        to_footprint = Transform.placement(placed.at, placed.rotation).inverse()
        check = pcblib.check_footprint(
            placed.footprint.defn, placed.footprint.extras, texts=placed.footprint.texts
        )
        pads: list[Pad] = []
        for index, pad in enumerate(check.pads):
            net = (
                placed.nets_by_pad.get(pad.id)
                if placed.nets_by_pad is not None
                else placed.pad_nets.get(pad.number)
            )
            pads.append(
                dataclasses.replace(
                    pad,
                    id=derived_id("pad", BACKEND, f"stored:{component.id}:{index}"),
                    native_ids={},
                    provenance=None,
                    position=to_footprint.apply(to_board.apply(pad.position)),
                    rotation=(to_board.apply_angle(pad.rotation) - placed.rotation) % FULL_TURN,
                    layers=tuple(_other_side(layer) for layer in pad.layers) if bottom else pad.layers,
                    net_id=net_ids.get(net or ""),
                )
            )
        footprints.append(
            FootprintInstance(
                id=derived_id("fp", BACKEND, f"stored:{component.id}"),
                component_id=component.id,
                lib_ref=component.lib_footprint_ref,
                position=placed.at,
                rotation=placed.rotation,
                side=placed.side,
                locked=placed.locked,
                pads=tuple(pads),
                bodies=tuple(
                    model_bodies[body.body_id]
                    for body in spec.bodies
                    if body.component == number and body.body_id in model_bodies
                ),
            )
        )
    zones = [
        dataclasses.replace(
            zone,
            id=zone.id if len(zone.layers) == 1 else derived_id("zon", BACKEND, f"stored:{zone.id}:{layer}"),
            layers=(layer,),
            net_id=net_ids.get(zone.net_id or ""),
            fills=(),
            filled=False,
        )
        for zone in spec.zones
        for layer in zone.layers
    ]
    return dataclasses.replace(
        board,
        footprints=tuple(footprints),
        tracks=tuple(dataclasses.replace(t, net_id=net_ids.get(t.net_id or "")) for t in spec.tracks),
        arcs=tuple(dataclasses.replace(a, net_id=net_ids.get(a.net_id or "")) for a in spec.arcs),
        vias=tuple(dataclasses.replace(v, net_id=net_ids.get(v.net_id or "")) for v in spec.vias),
        zones=tuple(zones),
    )


def _corner(board: Board | None) -> Point | None:
    """The corner that ``pcbdoc.Frame.of`` anchors: the lowest X and the highest Y of the outline, taken
    from ``Board.outline`` or from the ``Edge.Cuts`` graphics."""
    if board is None:
        return None
    points: list[Point] = list(board.outline.points) if board.outline is not None else []
    if not points:
        points = [p for graphic in board.graphics if graphic.layer == EDGE_LAYER for p in graphic.points]
    return Point(min(p.x for p in points), max(p.y for p in points)) if points else None


def moved(board: Board, dx: int, dy: int) -> Board:
    """``board`` with every position moved by (``dx``, ``dy``); pad positions are relative and stay."""

    def at(point: Point) -> Point:
        return Point(point.x + dx, point.y + dy)

    def ring(points: Sequence[Point]) -> tuple[Point, ...]:
        return tuple(at(p) for p in points)

    outline = board.outline
    if outline is not None:
        outline = dataclasses.replace(
            outline, points=ring(outline.points), cutouts=tuple(ring(cut) for cut in outline.cutouts)
        )
    return dataclasses.replace(
        board,
        outline=outline,
        footprints=tuple(dataclasses.replace(fp, position=at(fp.position)) for fp in board.footprints),
        tracks=tuple(dataclasses.replace(t, start=at(t.start), end=at(t.end)) for t in board.tracks),
        arcs=tuple(
            dataclasses.replace(a, start=at(a.start), mid=at(a.mid), end=at(a.end)) for a in board.arcs
        ),
        vias=tuple(dataclasses.replace(v, position=at(v.position)) for v in board.vias),
        zones=tuple(
            dataclasses.replace(
                z,
                outline=ring(z.outline),
                fills=tuple(dataclasses.replace(f, polygon=ring(f.polygon)) for f in z.fills),
            )
            for z in board.zones
        ),
        keepouts=tuple(dataclasses.replace(k, outline=ring(k.outline)) for k in board.keepouts),
        texts=tuple(dataclasses.replace(t, position=at(t.position)) for t in board.texts),
        graphics=tuple(dataclasses.replace(g, points=ring(g.points)) for g in board.graphics),
        holes=tuple(dataclasses.replace(h, position=at(h.position)) for h in board.holes),
    )


def in_frame_of(model: Design, reading: Design) -> Design:
    """``reading`` (the PCB document that was written from ``model``) in the frame of ``model``. A build
    moves the outline's lowest X and highest Y to (1000 mil, 1000 mil) of the document
    (``pcbdoc.Frame``); that corner is a whole number of units, so the reading holds it exactly and the
    move back is exact. Without an outline on both sides the reading is returned as it is."""
    board = reading.board
    if board is None:
        return reading
    if model.board is not None and model.board.holes:
        board = dataclasses.replace(
            board, footprints=tuple(fp for fp in board.footprints if not _is_hole(fp))
        )
    mine, theirs = _corner(model.board), _corner(board)
    if mine is not None and theirs is not None and mine != theirs:
        board = moved(board, mine.x - theirs.x, mine.y - theirs.y)
    return dataclasses.replace(reading, board=board)


def _is_hole(footprint: FootprintInstance) -> bool:
    """Whether ``footprint`` is the reading of a hole of the model: the writer gives a hole a free pad
    without a name, a net or a copper ring (``pcbrecords.hole_record``), and the import reads every free
    pad as a footprint of its own."""
    if footprint.lib_ref or len(footprint.pads) != 1:
        return False
    pad = footprint.pads[0]
    ring = (pad.size.w, pad.size.h) != (pad.drill, pad.drill)
    return not (pad.number or pad.net_id or pad.drill is None or ring)


__all__ = [
    "ARC_KEY",
    "ARC_TOLERANCE",
    "EVIDENCE",
    "KINDS",
    "LOSS_KINDS",
    "MORE_KINDS",
    "NOT_LOWERED",
    "AltiumInputs",
    "LossyWriteError",
    "ProjectWrite",
    "design_name",
    "dielectric_kinds",
    "from_design",
    "in_frame_of",
    "kept_arc",
    "moved",
    "pairs_of",
    "schematic_design",
    "stack_from_stackup",
    "stack_gap",
    "stack_unfit_reason",
    "stack_unheld",
    "stack_unheld_reason",
    "stored_board",
    "unique_links",
    "write_design",
]
