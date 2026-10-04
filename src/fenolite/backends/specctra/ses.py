# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A Specctra session file read into copper (capability specctra-dsn, "Session files are read into
copper"; facts: ``docs/formats/specctra/ses.md``; change c0023).

``read_session`` gives the wires, vias, placement entries and pin swaps of a session in the session's own
numbers. ``to_copper`` turns the wires and vias of the selected nets into model tracks and vias in
nanometres, with the names that ``dsn.write_dsn`` returned, and refuses a session that moved a component
or swapped a pin.

Every fact behind this module is ``INFERRED`` until the probes of ``H-G-DSN-ACCEPT``, ``H-G-DSN-UNITS`` and
``H-G-DSN-PROTECT`` are recorded.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from fenolite.backends.specctra.dsn import UNIT_NM, Names, to_units
from fenolite.backends.specctra.lexer import SNode, number, parse
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import derived_id
from fenolite.model.board import Track, Via, ViaType

BACKEND = "specctra"
UNITS_NM: dict[str, int] = {"inch": 25_400_000, "mil": 25_400, "cm": 10_000_000, "mm": 1_000_000, "um": 1_000}
"""Nanometres per dimension unit."""
_SESSION = frozenset({"base_design", "history", "placement", "was_is", "routes"})
_PLACEMENT = frozenset({"unit", "resolution", "component"})
_ROUTES = frozenset({"resolution", "parser", "structure_out", "library_out", "network_out", "test_points"})
_NET = frozenset({"wire", "via", "net_number", "rule"})
_WIRE = frozenset({"path", "net", "type", "attr", "turret", "shield", "connect", "supply", "window"})
_VIA = frozenset({"net", "via_number", "type", "attr", "contact", "supply"})
Pair = tuple[Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class Wire:
    """A routed path of a net: its layer, its width and its points, in the session's numbers."""

    net: str
    layer: str
    width: Fraction
    points: tuple[Pair, ...]


@dataclass(frozen=True, slots=True)
class SessionVia:
    """A via of a net: the name of its padstack and its position, in the session's numbers."""

    net: str
    padstack: str
    position: Pair


@dataclass(frozen=True, slots=True)
class Place:
    """Where the session says a component is: position, side and rotation in degrees, as written."""

    component: str
    position: Pair
    side: str
    rotation: Fraction


@dataclass(frozen=True, slots=True)
class Session:
    """What a session file holds for Fenolite.

    ``unit`` and ``resolution`` are those of the ``routes`` section (``None`` without one): a number ``v``
    of a wire or via is ``v / resolution`` units. ``place_unit`` and ``place_resolution`` are what the
    ``placement`` section declares for itself, if anything. ``unknown`` lists the keywords of the lists
    the reader ignored, once each, sorted.
    """

    name: str
    unit: str | None = None
    resolution: int | None = None
    wires: tuple[Wire, ...] = ()
    vias: tuple[SessionVia, ...] = ()
    places: tuple[Place, ...] = ()
    place_unit: str | None = None
    place_resolution: int | None = None
    swaps: tuple[tuple[str, str], ...] = ()
    unknown: tuple[str, ...] = ()


class _Reader:
    def __init__(self, file: str) -> None:
        self.file = file
        self.unknown: set[str] = set()

    def error(self, message: str, node: SNode) -> FormatError:
        return FormatError(message, file=self.file, offset=node.offset)

    def num(self, text: str, node: SNode) -> Fraction:
        return number(text, file=self.file, offset=node.offset)

    def note(self, node: SNode, known: frozenset[str]) -> None:
        self.unknown.update(child.head for child in node.lists if child.head not in known)

    def scale(self, node: SNode) -> tuple[str, int | None]:
        """The unit and resolution of a ``unit`` or ``resolution`` list."""
        words = node.words
        if not words or words[0] not in UNITS_NM:
            raise self.error(f"{node.head} needs one of {', '.join(UNITS_NM)}", node)
        if node.head == "unit":
            return words[0], None
        if len(words) != 2 or not words[1].isdigit() or int(words[1]) <= 0:
            raise self.error("resolution needs a unit and a positive integer", node)
        return words[0], int(words[1])

    def pairs(self, words: Sequence[str], node: SNode) -> tuple[Pair, ...]:
        if len(words) % 2:
            raise self.error(f"{node.head} holds an odd number of coordinates", node)
        values = [self.num(word, node) for word in words]
        return tuple(zip(values[0::2], values[1::2], strict=True))

    def placement(self, node: SNode) -> tuple[tuple[Place, ...], str | None, int | None]:
        self.note(node, _PLACEMENT)
        unit: str | None = None
        resolution: int | None = None
        for head in ("unit", "resolution"):
            found = node.first(head)
            if found is not None:
                unit, resolution = self.scale(found)
        places: list[Place] = []
        for component in node.all("component"):
            for place in component.all("place"):
                words = place.words
                if len(words) < 5:
                    raise self.error("place needs a reference, a position, a side and a rotation", place)
                position = (self.num(words[1], place), self.num(words[2], place))
                places.append(Place(words[0], position, words[3].lower(), self.num(words[4], place)))
        return tuple(places), unit, resolution

    def swaps(self, node: SNode) -> tuple[tuple[str, str], ...]:
        found: list[tuple[str, str]] = []
        for pins in node.lists:
            if pins.head != "pins":
                self.unknown.add(pins.head)
                continue
            if len(pins.words) != 2:
                raise self.error("a was_is entry needs two pin references", pins)
            found.append((pins.words[0], pins.words[1]))
        return tuple(found)

    def net(self, node: SNode, wires: list[Wire], vias: list[SessionVia]) -> None:
        if not node.words:
            raise self.error("a net needs a name", node)
        name = node.words[0]
        self.note(node, _NET)
        for wire in node.all("wire"):
            self.note(wire, _WIRE)
            path = wire.first("path")
            if path is None:
                continue
            words = path.words
            if len(words) < 6:
                raise self.error("a path needs a layer, a width and at least two points", path)
            wires.append(Wire(name, words[0], self.num(words[1], path), self.pairs(words[2:], path)))
        for via in node.all("via"):
            self.note(via, _VIA)
            words = via.words
            if len(words) < 3:
                raise self.error("a via needs a padstack and a position", via)
            vias += [SessionVia(name, words[0], pair) for pair in self.pairs(words[1:], via)]

    def session(self, tree: SNode) -> Session:
        if tree.head != "session":
            raise self.error(f"a session file starts with (session …), not ({tree.head} …)", tree)
        self.note(tree, _SESSION)
        places: tuple[Place, ...] = ()
        place_unit: str | None = None
        place_resolution: int | None = None
        placement = tree.first("placement")
        if placement is not None:
            places, place_unit, place_resolution = self.placement(placement)
        was_is = tree.first("was_is")
        swaps = self.swaps(was_is) if was_is is not None else ()
        unit: str | None = None
        resolution: int | None = None
        wires: list[Wire] = []
        vias: list[SessionVia] = []
        routes = tree.first("routes")
        if routes is not None:
            self.note(routes, _ROUTES)
            declared = routes.first("resolution")
            if declared is None:
                raise self.error("the routes section declares no resolution", routes)
            unit, resolution = self.scale(declared)
            for network in routes.all("network_out"):
                self.unknown.update(child.head for child in network.lists if child.head != "net")
                for net in network.all("net"):
                    self.net(net, wires, vias)
        return Session(
            name=tree.words[0] if tree.words else "",
            unit=unit,
            resolution=resolution,
            wires=tuple(wires),
            vias=tuple(vias),
            places=places,
            place_unit=place_unit,
            place_resolution=place_resolution,
            swaps=swaps,
            unknown=tuple(sorted(self.unknown)),
        )


def read_session(text: str, *, file: str = "") -> Session:
    """The session of ``text``, in the session's own numbers.

    Raises ``FormatError`` with a byte offset for text that is not a session, a ``routes`` section without
    a resolution, a number that is not one, or a wire, via or placement entry that lacks a member. Lists
    the reader does not know are ignored and named in ``Session.unknown``.
    """
    return _Reader(file).session(parse(text, file=file))


def _nm(value: Fraction, unit: str, resolution: int | None) -> int:
    """``value`` in nanometres, rounded half to even when it is not a whole number of them."""
    return round(value * UNITS_NM[unit] / (resolution or 1))


def _point(pair: Pair, unit: str, resolution: int | None) -> Point:
    """A session point in the model frame: Y is negated back."""
    return Point(_nm(pair[0], unit, resolution), -_nm(pair[1], unit, resolution))


def _on_grid(point: Point) -> Point:
    return Point(to_units(point.x) * UNIT_NM, -to_units(-point.y) * UNIT_NM)


def _moved(session: Session, names: Names) -> str:
    """Why the session counts as having moved or swapped something, or ``""``."""
    if session.swaps:
        old, new = session.swaps[0]
        return f"it swaps {len(session.swaps)} pin(s), the first {old} with {new}"
    unit = session.place_unit or session.unit or "um"
    # A placement that declares its own resolution holds database units (what Freerouting 2.4.1 writes,
    # probe dsn-accept), and one that declares a unit holds that unit. For a placement that declares
    # neither, no source says which it is, so either reading may give the written position (docs: ses.md).
    scales: tuple[int | None, ...]
    if session.place_resolution is not None:
        scales = (session.place_resolution,)
    elif session.place_unit is not None:
        scales = (None,)
    else:
        scales = (None, session.resolution)
    for place in session.places:
        written = names.places.get(place.component)
        if written is None:
            return f"it places {place.component}, which the design file does not hold"
        found = {_on_grid(_point(place.position, unit, scale)) for scale in scales}
        if written not in found:
            return f"it moves {place.component}"
        if place.side != "front" or place.rotation != 0:
            return f"it turns {place.component} ({place.side}, {place.rotation} degrees)"
    return ""


def _via_type(layers: tuple[str, str], copper: Sequence[str]) -> ViaType:
    if not copper or layers == (copper[0], copper[-1]):
        return "through"
    return "blind" if layers[0] == copper[0] or layers[1] == copper[-1] else "buried"


def to_copper(
    session: Session, names: Names, *, selected: Sequence[str]
) -> tuple[tuple[Track, ...], tuple[Via, ...], tuple[Issue, ...]]:
    """The tracks and vias of the ``selected`` nets of ``session``, and the findings.

    ``names`` is what ``write_dsn`` returned for the design file the session answers; ``selected`` holds
    model net names. Each wire gives one track per segment, zero-length segments dropped; each via takes
    the diameter and drill of the padstack written under its name. Wiring equal to protected input, and
    everything on other nets, is ignored. Ids derive from the net name and the geometry.

    No copper is returned with ``specctra.session-moved`` (a component moved or turned, an unknown
    component, a pin swap) or ``specctra.unknown-padstack``. Raises ``FormatError`` for a wire on a layer
    the design file lacks.
    """
    issues = [
        Issue(
            "specctra.unknown-list", "info", f"the session list ({head} …) is not read and was ignored", head
        )
        for head in session.unknown
    ]
    why = _moved(session, names)
    if why:
        issues.append(
            Issue(
                "specctra.session-moved",
                "error",
                f"the session changes the placement: {why}; no copper is taken from it",
                hint="route with every component locked, or place the board first",
            )
        )
        return (), (), tuple(issues)
    if session.unit is None:
        return (), (), tuple(issues)
    unit, resolution = session.unit, session.resolution
    wanted = set(selected)
    copper = tuple(names.layers.values())
    tracks: dict[str, Track] = {}
    vias: dict[str, Via] = {}
    for wire in session.wires:
        net = names.nets.get(wire.net)
        if net is None or net not in wanted:
            continue
        layer = names.layers.get(wire.layer)
        if layer is None:
            raise FormatError(
                f"the session routes {wire.net} on {wire.layer!r}, a layer the design file lacks"
            )
        width = _nm(wire.width, unit, resolution)
        points = [_point(pair, unit, resolution) for pair in wire.points]
        for start, end in zip(points, points[1:], strict=False):
            if start == end:
                continue
            low, high = sorted((start, end))
            if (net, layer, width, low, high) in names.protected_wires:
                continue
            key = f"{net}:{layer}:{width}:{low.x},{low.y}:{high.x},{high.y}"
            ident = derived_id("trk", BACKEND, key)
            tracks.setdefault(
                ident,
                Track(
                    id=ident, start=start, end=end, width=width, layer=layer, net_id=names.net_ids[wire.net]
                ),
            )
    for via in session.vias:
        net = names.nets.get(via.net)
        if net is None or net not in wanted:
            continue
        stack = names.vias.get(via.padstack)
        if stack is None:
            issues.append(
                Issue(
                    "specctra.unknown-padstack",
                    "error",
                    f"the session places the via padstack {via.padstack!r} on {net}, which the design file "
                    f"does not define; no copper is taken from it",
                    where=net,
                )
            )
            return (), (), tuple(issues)
        position = _point(via.position, unit, resolution)
        if (net, position) in names.protected_vias:
            continue
        key = f"{net}:{via.padstack}:{position.x},{position.y}"
        ident = derived_id("via", BACKEND, key)
        vias.setdefault(
            ident,
            Via(
                id=ident,
                position=position,
                diameter=stack.diameter,
                drill=stack.drill,
                layers=stack.layers,
                net_id=names.net_ids[via.net],
                via_type=_via_type(stack.layers, copper),
            ),
        )
    return tuple(tracks.values()), tuple(vias.values()), tuple(issues)


__all__ = ["UNITS_NM", "Place", "Session", "SessionVia", "Wire", "read_session", "to_copper"]
