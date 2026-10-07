# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level 5 of a design comparison: the routing of each net (capability design-equivalence, "Routed
connectivity of a net" and "Level 5 compares routing per net"; ``docs/equivalence.md``, "Level 5").

``pieces`` reads the copper of a board as connected pieces per net. The tracks, arcs, vias, zone fills and
pads of one net are joined when two of them touch on a shared copper layer, by the exact touch test that
the copper check uses for shorts (``geometry.thick_touch``). A piece is described by the pads it holds, its
vias per pair of copper spans and its routed length per copper span; the path a track takes is not part of
it, so two routes of one connection with the same layers and length are the same piece.

``level_routing`` compares the pieces of the nets that level 2 pairs. What it compares, in which order
and under which kind is the table ``DEFAULT_RULE`` at the end of this module, and nothing else: another
rule (a stricter one, item by item) is a second table beside it, with no change to ``pieces``.

Everything is integer arithmetic. A pad's copper is shaped from the model alone (``_pad_shape``), because
this package may call no backend.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from math import gcd, isqrt

from fenolite.checks import assignment_compare
from fenolite.checks.equivalence.model import EXACT, KINDS, Difference, LevelResult, Tolerances
from fenolite.core.coords import Point, Size
from fenolite.core.units import round_half_even_div
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import GeometryError, Thick, Transform, touch_groups
from fenolite.model.board import Board, FootprintInstance, Pad
from fenolite.model.design import Design

LEVEL = 5
ARC_TOL_NM = 1_000
"""The chord error of the polyline that stands for an arc in the touch test, as in the copper check."""
TURN = 360_000_000
TOP, BOTTOM, INNER = "top", "bottom", "inner"
PAD_LIMIT = 3
"""How many pads of a pad set a location or a value names; the rest is counted (``,+<n>``)."""
SET_LIMIT = 3
"""How many pad sets a ``route-connectivity`` value names."""
_FIELD = {kind: name for level, kind, name in KINDS if level == LEVEL}

# --- lengths ---------------------------------------------------------------------------------------

_BITS = 128
_ONE = 1 << _BITS


def _round_sqrt(n: int) -> int:
    """``√n`` rounded to the nearest integer (the root of an integer is never a half)."""
    return (isqrt(4 * n) + 1) // 2


def _distance(a: Point, b: Point) -> int:
    return _round_sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _atan_fixed(t: int) -> int:
    """``atan(t)`` for ``0 ≤ t ≤ 1``, argument and result scaled by ``2**_BITS``: the angle is halved
    three times (``tan(x/2) = t / (1 + √(1 + t²))``), then the power series is summed."""
    for _ in range(3):
        t = (t * _ONE) // (_ONE + isqrt(_ONE * _ONE + t * t))
    square = t * t // _ONE
    total, term, n, sign = 0, t, 1, 1
    while term:
        total += sign * (term // n)
        term = term * square // _ONE
        n += 2
        sign = -sign
    return total << 3


_PI = 4 * _atan_fixed(_ONE)


def _angle(cross: int, dot: int) -> int:
    """The angle in ``[0, π]`` whose sine and cosine are proportional to ``cross ≥ 0`` and ``dot``, scaled
    by ``2**_BITS``."""
    a, b = cross, abs(dot)
    if a <= b:
        angle = _atan_fixed((a << _BITS) // b)
    else:
        angle = _PI // 2 - _atan_fixed((b << _BITS) // a)
    return _PI - angle if dot < 0 else angle


def arc_length(start: Point, mid: Point, end: Point) -> int:
    """The true length in nanometres of the circular arc from ``start`` through ``mid`` to ``end``,
    rounded half to even. The arc turns by twice the angle between ``start → mid`` and ``mid → end``, so
    its length is the radius times that. Collinear points give the two straight parts, and points that
    form no arc the distance of the ends."""
    try:
        shape = GeoArc(start, mid, end)
    except GeometryError:
        return _distance(start, end)
    radius2 = shape.radius2
    if radius2 is None:
        return _distance(start, mid) + _distance(mid, end)
    ux, uy, vx, vy = mid.x - start.x, mid.y - start.y, end.x - mid.x, end.y - mid.y
    turn = 2 * _angle(abs(ux * vy - uy * vx), ux * vx + uy * vy)
    radius = isqrt((radius2.numerator << (2 * _BITS)) // radius2.denominator)
    return round_half_even_div(radius * turn, 1 << (2 * _BITS))


def track_length(segments: Sequence[tuple[Point, Point]]) -> int:
    """The length of straight segments in nanometres. The segments that lie on one line are added exactly
    (each is a whole number of the line's smallest integer step) and the sum is rounded once to the nearest
    nanometre, so a track cut at a point of itself, or joined again, has the same length to the nanometre.
    Copper drawn twice counts twice."""
    lines: Counter[tuple[int, int, int]] = Counter()
    for a, b in segments:
        dx, dy = b.x - a.x, b.y - a.y
        steps = gcd(abs(dx), abs(dy))
        if steps == 0:
            continue
        ux, uy = dx // steps, dy // steps
        if ux < 0 or (ux == 0 and uy < 0):
            ux, uy = -ux, -uy
        lines[ux, uy, ux * a.y - uy * a.x] += steps
    return sum(_round_sqrt(steps * steps * (ux * ux + uy * uy)) for (ux, uy, _), steps in lines.items())


# --- copper spans ----------------------------------------------------------------------------------


def span_names(board: Board) -> dict[str, str]:
    """Each copper layer of the board with the name of its span: ``top`` for the lowest ordinal, ``bottom``
    for the highest and ``inner<k>`` for the ``k``-th between them, as level 3 reads a pad's copper."""
    copper = sorted((layer for layer in board.layers if layer.kind == "copper"), key=lambda la: la.ordinal)
    names: dict[str, str] = {}
    for rank, layer in enumerate(copper):
        names[layer.name] = TOP if rank == 0 else BOTTOM if rank == len(copper) - 1 else f"{INNER}{rank}"
    return names


def _span_rank(name: str) -> tuple[int, int, str]:
    if name == TOP:
        return (0, 0, "")
    if name.startswith(INNER) and name[len(INNER) :].isdigit():
        return (1, int(name[len(INNER) :]), "")
    return (2, 0, "") if name == BOTTOM else (3, 0, name)


def _pair_rank(pair: str) -> tuple[tuple[int, int, str], ...]:
    return tuple(_span_rank(name) for name in pair.split("-", 1))


# --- pieces ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Piece:
    """One connected piece of the copper of a net: the ``REF-PAD`` elements it holds (sorted), its vias
    per pair of copper spans (``top-bottom``), its routed length in nanometres per copper span, and
    whether it holds a track, an arc, a via or a zone fill (false for a pad that nothing reaches)."""

    pads: tuple[str, ...] = ()
    vias: tuple[tuple[str, int], ...] = ()
    lengths: tuple[tuple[str, int], ...] = ()
    copper: bool = False

    @property
    def via_count(self) -> int:
        return sum(count for _, count in self.vias)

    @property
    def length(self) -> int:
        return sum(length for _, length in self.lengths)


@dataclass(frozen=True, slots=True)
class NetPieces(Mapping[str, tuple[Piece, ...]]):
    """The pieces of each net of a board, by net id, with what was left out: the count of zones without
    a fill and the ids of their nets, the count of copper items on no net, and the count of items that
    could not be shaped."""

    by_net: Mapping[str, tuple[Piece, ...]] = field(default_factory=lambda: {})
    zones_unfilled: int = 0
    unfilled_nets: frozenset[str] = frozenset()
    no_net: int = 0
    unshaped: int = 0

    def __getitem__(self, key: str) -> tuple[Piece, ...]:
        return self.by_net[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.by_net)

    def __len__(self) -> int:
        return len(self.by_net)


@dataclass(slots=True)
class _Item:
    """One copper item of a net: its shapes per layer, and what it adds to its piece."""

    net: str
    shapes: list[tuple[str, Thick]]
    element: str = ""
    copper: bool = True
    via: str = ""
    span: str = ""
    segment: tuple[Point, Point] | None = None
    arc: int = 0


def _clean_ring(points: Sequence[Point]) -> tuple[Point, ...]:
    """A stored polygon without consecutive repeats and without a closing copy of its first point."""
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return tuple(out)


def _pad_shape(shape: str, size: Size, centre: Point, angle: int) -> Thick:
    """The copper of a pad on one layer, from the model alone: a disc for ``circle`` (and for an oval of
    two equal sizes), a stadium for ``oval``, and the rectangle of the size for every other shape, which is
    a superset of a ``roundrect``, ``trapezoid`` or ``custom`` pad. ``ValueError`` for a pad without size."""
    w, h = size.w, size.h
    if w <= 0 or h <= 0:
        raise ValueError("a pad without a size has no copper")
    half = abs(w - h) // 2
    if shape == "circle" or (shape == "oval" and half == 0):
        return Thick((centre,), min(w, h))
    place = Transform.placement(centre, angle)
    if shape == "oval":
        ends = (Point(-half, 0), Point(half, 0)) if w > h else (Point(0, -half), Point(0, half))
        return Thick(tuple(place.apply(p) for p in ends), min(w, h))
    x, y = w // 2, h // 2
    ring = tuple(place.apply(Point(sx, sy)) for sx, sy in ((-x, -y), (x, -y), (x, y), (-x, y)))
    return Thick(ring, 0, filled=True)


class _Copper:
    """The copper items of a board, per net, and what was left out."""

    def __init__(self, design: Design, board: Board) -> None:
        self.items: list[_Item] = []
        self.no_net = 0
        self.unshaped = 0
        self.zones_unfilled = 0
        self.unfilled_nets: set[str] = set()
        self.spans = span_names(board)
        self._order = [name for name, _ in sorted(self.spans.items(), key=lambda e: _span_rank(e[1]))]
        self._refs = {c.id: c.ref for c in design.circuit.components}
        self._tracks(board)
        self._arcs(board)
        self._vias(board)
        self._fills(board)
        for footprint in board.footprints:
            self._pads(footprint)

    def _span(self, layer: str) -> str:
        return self.spans.get(layer, layer)

    def _tracks(self, board: Board) -> None:
        for track in board.tracks:
            if track.net_id is None:
                self.no_net += 1
                continue
            try:
                if track.start == track.end:
                    shape = Thick((track.start,), track.width)
                else:
                    shape = Thick((track.start, track.end), track.width)
            except (GeometryError, ValueError):
                self.unshaped += 1
                continue
            span = self._span(track.layer)
            self.items.append(
                _Item(track.net_id, [(track.layer, shape)], span=span, segment=(track.start, track.end))
            )

    def _arcs(self, board: Board) -> None:
        for arc in board.arcs:
            if arc.net_id is None:
                self.no_net += 1
                continue
            try:
                try:
                    core = GeoArc(arc.start, arc.mid, arc.end).polygonize(ARC_TOL_NM)
                except GeometryError:
                    core = (arc.start, arc.end) if arc.start != arc.end else (arc.start,)
                shape = Thick(core, arc.width)
            except (GeometryError, ValueError):
                self.unshaped += 1
                continue
            length = arc_length(arc.start, arc.mid, arc.end)
            self.items.append(_Item(arc.net_id, [(arc.layer, shape)], span=self._span(arc.layer), arc=length))

    def _via_layers(self, layers: Sequence[str], through: bool) -> tuple[str, ...]:
        """The copper layers a via spans, as the copper check reads them: from its first layer to its
        second in stack order, and every copper layer for a through via or for layers the board lacks."""
        order = self._order
        if not order:
            return tuple(dict.fromkeys(layers))
        if through or len(layers) != 2 or layers[0] not in order or layers[1] not in order:
            return tuple(order)
        first, last = sorted((order.index(layers[0]), order.index(layers[1])))
        return tuple(order[first : last + 1])

    def _vias(self, board: Board) -> None:
        for via in board.vias:
            if via.net_id is None:
                self.no_net += 1
                continue
            layers = self._via_layers(via.layers, via.via_type == "through")
            try:
                shape = Thick((via.position,), via.diameter)
            except (GeometryError, ValueError):
                self.unshaped += 1
                continue
            if not layers:
                self.unshaped += 1
                continue
            pair = f"{self._span(layers[0])}-{self._span(layers[-1])}"
            self.items.append(_Item(via.net_id, [(layer, shape) for layer in layers], via=pair))

    def _fills(self, board: Board) -> None:
        for zone in board.zones:
            if not zone.fills:
                self.zones_unfilled += 1
                if zone.net_id is not None:
                    self.unfilled_nets.add(zone.net_id)
                continue
            for fill in zone.fills:
                if zone.net_id is None:
                    self.no_net += 1
                    continue
                try:
                    shape = Thick(_clean_ring(fill.polygon), 0, filled=True)
                except (GeometryError, ValueError):
                    self.unshaped += 1
                    continue
                self.items.append(_Item(zone.net_id, [(fill.layer, shape)]))

    def _pads(self, footprint: FootprintInstance) -> None:
        ref = self._refs.get(footprint.component_id, "")
        place = Transform.placement(footprint.position, footprint.rotation)
        for pad in footprint.pads:
            if pad.kind == "np_thru_hole" or pad.net_id is None:
                continue
            layers = [layer for layer in pad.layers if layer in self.spans]
            if not layers:
                continue
            centre = place.apply(pad.position)
            angle = (pad.rotation + footprint.rotation) % TURN
            element = f"{ref}-{pad.number}" if pad.number else ""
            try:
                shapes = [(layer, self._layer_shape(pad, layer, centre, angle)) for layer in layers]
            except (GeometryError, ValueError):
                self.unshaped += 1
                continue
            self.items.append(_Item(pad.net_id, shapes, element=element, copper=False))

    @staticmethod
    def _layer_shape(pad: Pad, layer: str, centre: Point, angle: int) -> Thick:
        """The pad's copper on ``layer``: the shape, size and offset of its padstack entry for the layer
        when it has one, else the pad's own."""
        stack = pad.padstack.layers if pad.padstack is not None else ()
        entry = next((found for found in stack if found.layer == layer), None)
        if entry is None:
            return _pad_shape(pad.shape, pad.size, centre, angle)
        moved = Transform.placement(centre, angle).apply(entry.offset)
        return _pad_shape(entry.shape, entry.size, moved, angle)


def _joined(items: Sequence[_Item]) -> list[int]:
    """The piece of each item, as the index of one item of it: two items of one net are joined when two of
    their shapes on one layer touch (``geometry.touch_groups``, keyed by net and layer)."""
    return touch_groups([[((item.net, layer), shape) for layer, shape in item.shapes] for item in items])


def _piece(items: Sequence[_Item]) -> Piece:
    vias = Counter(item.via for item in items if item.via)
    segments: dict[str, list[tuple[Point, Point]]] = defaultdict(list)
    lengths: Counter[str] = Counter()
    for item in items:
        if item.segment is not None:
            segments[item.span].append(item.segment)
        elif item.arc:
            lengths[item.span] += item.arc
    for span, found in segments.items():
        lengths[span] += track_length(found)
    return Piece(
        pads=tuple(sorted({item.element for item in items if item.element})),
        vias=tuple(sorted(vias.items(), key=lambda entry: _pair_rank(entry[0]))),
        lengths=tuple(sorted(((s, n) for s, n in lengths.items() if n), key=lambda e: _span_rank(e[0]))),
        copper=any(item.copper for item in items),
    )


def pieces(design: Design) -> NetPieces:
    """The connected pieces of the copper of each net of ``design.board``, by net id. A net appears when
    it holds a track, an arc, a via, a zone fill or a pad with copper; a pad that nothing reaches is a piece
    of its own. A zone without a fill joins nothing and is counted. The order of the board's items does not
    change the result."""
    board = design.board
    if board is None:
        return NetPieces()
    copper = _Copper(design, board)
    roots = _joined(copper.items)
    groups: dict[tuple[str, int], list[_Item]] = defaultdict(list)
    for item, root in zip(copper.items, roots, strict=True):
        groups[item.net, root].append(item)
    found: dict[str, list[Piece]] = defaultdict(list)
    for (net, _), members in groups.items():
        found[net].append(_piece(members))
    by_net = {
        net: tuple(sorted(held, key=lambda p: (p.pads, p.vias, p.lengths, p.copper)))
        for net, held in sorted(found.items())
    }
    return NetPieces(
        by_net, copper.zones_unfilled, frozenset(copper.unfilled_nets), copper.no_net, copper.unshaped
    )


def has_copper(design: Design) -> bool:
    """Whether the design's board holds at least one track, arc or via."""
    board = design.board
    return board is not None and bool(board.tracks or board.arcs or board.vias)


# --- pairing ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NetPairing:
    """The nets that level 2 pairs: each pair of net ids ``(a, b)`` whose blocks of ``REF-PIN`` elements
    are equal, and the elements both sides hold (those of the components that level 1 compared)."""

    pairs: tuple[tuple[str, str], ...] = ()
    elements: frozenset[str] = frozenset()


def pair_nets(a: Design, b: Design, refs: Sequence[str]) -> NetPairing:
    """The pairing of the nets of two boards over the components ``refs``, by the pad assignments that
    level 2 compares (``assignment_compare.board_netlist``). Net names take no part. A net whose block
    differs between the sides is a difference of level 2 and is in no pair."""
    wanted = frozenset(refs)

    def blocks(design: Design) -> dict[str, set[str]]:
        found: dict[str, set[str]] = defaultdict(set)
        for item in assignment_compare.board_netlist(design)[0].assignments:
            if item.net != assignment_compare.NO_NET and item.element.rpartition("-")[0] in wanted:
                found[item.net].add(item.element)
        return found

    blocks_a, blocks_b = blocks(a), blocks(b)
    numbered_a = {element for held in blocks_a.values() for element in held}
    numbered_b = {element for held in blocks_b.values() for element in held}
    common = frozenset(numbered_a & numbered_b)
    by_block: dict[frozenset[str], str] = {}
    for net, held in sorted(blocks_b.items()):
        by_block.setdefault(frozenset(held & common), net)
    pairs: list[tuple[str, str]] = []
    taken: set[str] = set()
    for net, held in sorted(blocks_a.items()):
        block = frozenset(held & common)
        other = by_block.get(block)
        if block and other is not None and other not in taken:
            pairs.append((net, other))
            taken.add(other)
    return NetPairing(tuple(pairs), common)


# --- one net on one side ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Joined:
    """The pieces of a net that hold one pad set, added up: how many they are, their vias per span pair
    and their length per span."""

    count: int = 0
    vias: Mapping[str, int] = field(default_factory=lambda: {})
    lengths: Mapping[str, int] = field(default_factory=lambda: {})

    @property
    def length(self) -> int:
        return sum(self.lengths.values())


@dataclass(frozen=True, slots=True)
class NetRouting:
    """What level 5 knows of one net on one side: its name, its pieces by pad set (the empty pad set
    holds the pieces without a pad: stubs and lone vias), whether it holds copper, the count of its pieces,
    and whether it holds a zone without a fill."""

    name: str
    joined: Mapping[tuple[str, ...], Joined]
    copper: bool
    pieces: int
    unfilled: bool

    @property
    def stubs(self) -> Joined:
        return self.joined.get((), Joined())

    @property
    def pad_sets(self) -> Counter[tuple[str, ...]]:
        return Counter({pads: found.count for pads, found in self.joined.items() if pads})


def net_routing(name: str, held: Sequence[Piece], elements: frozenset[str], unfilled: bool) -> NetRouting:
    """The pieces ``held`` of a net as level 5 compares them: only the pads of ``elements`` count."""
    count: Counter[tuple[str, ...]] = Counter()
    vias: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    lengths: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for piece in held:
        pads = tuple(pad for pad in piece.pads if pad in elements)
        if not pads and not piece.copper:
            continue  # a pad of a component that is not compared, with nothing on it
        count[pads] += 1
        vias[pads].update(dict(piece.vias))
        lengths[pads].update(dict(piece.lengths))
    joined = {pads: Joined(n, dict(vias[pads]), dict(lengths[pads])) for pads, n in sorted(count.items())}
    return NetRouting(name, joined, any(p.copper for p in held), sum(count.values()), unfilled)


# --- texts -----------------------------------------------------------------------------------------


def pads_text(pads: Sequence[str]) -> str:
    """A pad set as text: its first ``PAD_LIMIT`` pads, then ``+<n>`` for the rest."""
    shown = list(pads[:PAD_LIMIT])
    if len(pads) > PAD_LIMIT:
        shown.append(f"+{len(pads) - PAD_LIMIT}")
    return ",".join(shown)


def _sets_text(sets: Sequence[tuple[str, ...]]) -> str:
    shown = [pads_text(pads) for pads in sets[:SET_LIMIT]]
    if len(sets) > SET_LIMIT:
        shown.append(f"+{len(sets) - SET_LIMIT}")
    return " | ".join(shown)


def _counts_text(counts: Mapping[str, int], names: Sequence[str]) -> str:
    return ",".join(f"{name}={counts.get(name, 0)}" for name in names)


def routed_equal(p: int, q: int, tolerances: Tolerances) -> bool:
    """Two routed lengths are equal within ``max(length_nm, max(p, q) × length_ppm // 1_000_000)``."""
    return abs(p - q) <= max(tolerances.length_nm, max(p, q) * tolerances.length_ppm // 1_000_000)


# --- the rule of level 5 ---------------------------------------------------------------------------
#
# This block is the whole definition of level 5: which fields of a net's routing are compared, in which
# order, and the kind each difference gets. A finding is ``(pad set, value on a, value on b)``; the pad
# set is empty when the finding concerns the whole net. To change the definition, change this block; to
# add another definition (a strict one that matches copper item by item), add a second table like
# ``DEFAULT_RULE`` and give ``level_routing`` its name. ``pieces`` and ``NetRouting`` do not change.

Finding = tuple[tuple[str, ...], str, str]
Judge = Callable[[NetRouting, NetRouting, Tolerances], list[Finding]]


def _unjudged(a: NetRouting, b: NetRouting, tolerances: Tolerances) -> list[Finding]:
    """A side holds a zone without a fill on the net, and more than one piece: whether its pads are
    joined depends on copper that is not there to read."""
    open_a, open_b = a.unfilled and a.pieces > 1, b.unfilled and b.pieces > 1
    if not (open_a or open_b):
        return []
    return [((), f"pieces={a.pieces}" if open_a else "", f"pieces={b.pieces}" if open_b else "")]


def _missing(a: NetRouting, b: NetRouting, tolerances: Tolerances) -> list[Finding]:
    """One side has copper on the net and the other has none."""
    if a.copper == b.copper:
        return []
    return [((), "routed" if a.copper else "", "routed" if b.copper else "")]


def _connectivity(a: NetRouting, b: NetRouting, tolerances: Tolerances) -> list[Finding]:
    """The multisets of the pad sets of the pieces differ: one finding per net, located at the first pad
    set that one side holds more often than the other."""
    sets_a, sets_b = a.pad_sets, b.pad_sets
    only_a, only_b = sorted((sets_a - sets_b).elements()), sorted((sets_b - sets_a).elements())
    if not only_a and not only_b:
        return []
    return [(min(only_a + only_b), _sets_text(only_a), _sets_text(only_b))]


def _vias(a: NetRouting, b: NetRouting, tolerances: Tolerances) -> list[Finding]:
    """For each pad set, the via counts per pair of copper spans differ."""
    found: list[Finding] = []
    for pads in sorted(set(a.pad_sets) & set(b.pad_sets)):
        one, other = a.joined[pads].vias, b.joined[pads].vias
        if dict(one) != dict(other):
            names = sorted(set(one) | set(other), key=_pair_rank)
            found.append((pads, _counts_text(one, names), _counts_text(other, names)))
    return found


def _lengths(a: NetRouting, b: NetRouting, tolerances: Tolerances) -> list[Finding]:
    """For each pad set, the routed length on a copper span differs beyond the tolerance."""
    found: list[Finding] = []
    for pads in sorted(set(a.pad_sets) & set(b.pad_sets)):
        one, other = a.joined[pads].lengths, b.joined[pads].lengths
        names = sorted(set(one) | set(other), key=_span_rank)
        if any(not routed_equal(one.get(name, 0), other.get(name, 0), tolerances) for name in names):
            found.append((pads, _counts_text(one, names), _counts_text(other, names)))
    return found


def _stubs(a: NetRouting, b: NetRouting, tolerances: Tolerances) -> list[Finding]:
    """The pieces without a pad differ in number, or in total length beyond the tolerance."""
    one, other = a.stubs, b.stubs
    if one.count == other.count and routed_equal(one.length, other.length, tolerances):
        return []
    return [((), f"pieces={one.count},length={one.length}", f"pieces={other.count},length={other.length}")]


@dataclass(frozen=True, slots=True)
class Step:
    """One step of a rule: the kind of its findings, how it judges a net, and whether a finding ends the
    judgement of the net."""

    kind: str
    judge: Judge
    final: bool = False


DEFAULT_RULE: tuple[Step, ...] = (
    Step("route-unjudged", _unjudged, final=True),
    Step("route-missing", _missing, final=True),
    Step("route-connectivity", _connectivity, final=True),
    Step("route-vias", _vias),
    Step("route-length", _lengths),
    Step("route-stub", _stubs),
)
"""Level 5 as the proposal of c0089 defines it: connectivity per net, vias per pair of copper spans and
length per copper span within the tolerance (``Tolerances.length_nm`` and ``Tolerances.length_ppm``).
The path of a track is not compared."""
NOTICES = frozenset({"route-stub", "route-unjudged"})
"""The kinds that are reported and never make two designs unequal (``LevelResult.notices``)."""

# --- end of the rule -------------------------------------------------------------------------------


def _located(net: str, pads: Sequence[str]) -> str:
    return f"{net}:{pads_text(pads)}" if pads else net


def level_routing(
    a: Design,
    b: Design,
    pairing: NetPairing,
    tolerances: Tolerances = EXACT,
    rule: Sequence[Step] = DEFAULT_RULE,
) -> LevelResult:
    """Level 5 over the net pairs of ``pairing``: each net that holds copper on a side is judged by the
    steps of ``rule`` in order, and every finding is located by the net's name on side ``a`` and the pads
    of its pad set. Nets on which neither side holds copper, and nets in no pair, are not compared; the
    summary counts them."""
    held_a, held_b = pieces(a), pieces(b)
    names_a = {net.id: net.name for net in a.circuit.nets}
    differences: list[Difference] = []
    notices: list[Difference] = []
    compared = 0
    totals = {key: {"a": 0, "b": 0} for key in ("pieces", "vias", "length")}
    for net_a, net_b in pairing.pairs:
        one = net_routing(
            names_a.get(net_a, net_a), held_a.get(net_a, ()), pairing.elements, net_a in held_a.unfilled_nets
        )
        other = net_routing("", held_b.get(net_b, ()), pairing.elements, net_b in held_b.unfilled_nets)
        if not one.copper and not other.copper:
            continue
        compared += 1
        for side, routing in (("a", one), ("b", other)):
            totals["pieces"][side] += routing.pieces
            totals["vias"][side] += sum(sum(found.vias.values()) for found in routing.joined.values())
            totals["length"][side] += sum(found.length for found in routing.joined.values())
        for step in rule:
            findings = step.judge(one, other, tolerances)
            for pads, value_a, value_b in findings:
                found = Difference(
                    LEVEL, step.kind, _located(one.name, pads), _FIELD[step.kind], value_a, value_b
                )
                (notices if step.kind in NOTICES else differences).append(found)
            if findings and step.final:
                break
    paired_a, paired_b = {pair[0] for pair in pairing.pairs}, {pair[1] for pair in pairing.pairs}

    def loose(held: NetPieces, paired: set[str]) -> int:
        return sum(1 for net, found in held.items() if net not in paired and any(p.copper for p in found))

    def order(found: Sequence[Difference]) -> tuple[Difference, ...]:
        return tuple(sorted(found, key=lambda d: (d.where, d.kind, d.field, d.a, d.b)))

    summary: dict[str, object] = {
        "nets": compared,
        **totals,
        "unjudged": sum(1 for found in notices if found.kind == "route-unjudged"),
        "nets_unpaired": {"a": loose(held_a, paired_a), "b": loose(held_b, paired_b)},
        "zones_unfilled": {"a": held_a.zones_unfilled, "b": held_b.zones_unfilled},
        "copper_no_net": {"a": held_a.no_net, "b": held_b.no_net},
        "unshaped": {"a": held_a.unshaped, "b": held_b.unshaped},
    }
    return LevelResult(LEVEL, compared, order(differences), (), summary, order(notices))


__all__ = [
    "DEFAULT_RULE",
    "NOTICES",
    "Joined",
    "NetPairing",
    "NetPieces",
    "NetRouting",
    "Piece",
    "Step",
    "arc_length",
    "has_copper",
    "level_routing",
    "net_routing",
    "pads_text",
    "pair_nets",
    "pieces",
    "routed_equal",
    "span_names",
    "track_length",
]
