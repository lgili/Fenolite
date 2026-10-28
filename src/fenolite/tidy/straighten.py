# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Straighten runs of tracks (capability copper-tidy, "Straighten runs", "Turn costs" and "Runs left
alone"; ``docs/copper.md``, "Copper tidy").

A run is a chain of two or more movable tracks (unlocked, not kept, not of zero length) of one net, layer
and width through inner joints: points where exactly those two tracks end and nothing else of the net
touches the disc of the width. Its two ends are fixed. A run whose tracks touch another item of the net
elsewhere than at its end discs stays, since a new shape would drop that contact.

Between the ends a fixed list of shapes of at most three segments on the 0/45/90° lattice is tried
(``shapes``). A turn weighs ``angles.TURN_WEIGHTS``; a turn whose point lies in a pad that the run ends on
weighs nothing, and the joints with other tracks ending at the run's ends count as turns. A new shape
never makes an acute angle. Only shapes that weigh less than the run are tried, lightest first, then
shortest, then in list order; the first that touches of its net only what the end discs touched, makes no
short with another net, keeps the net's groups and adds no finding of ``check`` replaces the run.

Nets of a differential pair or selected by a length rule are left alone (``tidy.straighten-skipped``).
Runs go by net name, copper layer and smallest track id, each against the copper of the runs before it.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import content_hash, derived_id
from fenolite.geometry import Thick, floor_sqrt
from fenolite.model.board import Arc, Track
from fenolite.model.design import Design
from fenolite.model.pairs import net_bases, pair_nets
from fenolite.model.rules import RuleSubject
from fenolite.tidy.angles import TURN_WEIGHTS, turn_kind, vector
from fenolite.tidy.codes import issue
from fenolite.tidy.edits import Check, Clash, Edit, TidyResult, fresh_clashes
from fenolite.tidy.graph import Piece, copper_layers, joined_at, keeps_groups, net_pieces, track_piece
from fenolite.tidy.prune import selected_nets

REASON = "fewer-turns"
"""The reason of a straightened run."""
LENGTH_KINDS = frozenset({"length", "skew", "diff_pair_skew"})
"""The rule kinds whose nets are never straightened: a new shape changes the length."""
_PROBE = 2
"""The width of the disc that asks whether a point lies in a pad."""
_SPLITS = ((1, 2), (1, 4), (3, 4))
"""Where the diagonal of a three-segment shape sits along the straight part."""


@dataclass(frozen=True, slots=True)
class Run:
    """A run: its net, layer and width, its tracks in order and the points from one end to the other."""

    net_id: str
    net: str
    layer: str
    width: int
    tracks: tuple[Track, ...]
    points: tuple[Point, ...]

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(track.id for track in self.tracks)


def protected_nets(design: Design) -> frozenset[str]:
    """The ids of the nets that are never straightened: those of a pair (an interface of a pair kind, or
    the KiCad name rule of ``model.pairs``) and those that a rule of a kind of ``LENGTH_KINDS`` selects."""
    names = {net.name: net.id for net in design.circuit.nets}
    bases = net_bases(names)
    found = {names[name] for name in bases}
    for interface in design.circuit.interfaces:
        pair = pair_nets(interface)
        if pair is not None:
            found.update(pair)
    rules = [rule for rule in (design.rules.rules if design.rules else ()) if rule.kind in LENGTH_KINDS]
    if rules:
        classes = {netclass.id: netclass.name for netclass in design.circuit.netclasses}
        for net in design.circuit.nets:
            subject = RuleSubject(
                "track",
                net=net.name,
                netclass=classes.get(net.netclass_id or ""),
                diff_pair=bases.get(net.name),
            )
            for rule in rules:
                if rule.selector_a.matches(subject) or (
                    rule.selector_b is not None and rule.selector_b.matches(subject)
                ):
                    found.add(net.id)
                    break
    return frozenset(found)


def _touches(shape: Thick, layer: str, pieces: Iterable[Piece]) -> set[str]:
    """The ids of ``pieces`` that ``shape`` on ``layer`` touches."""
    return {piece.ident for piece in pieces if joined_at(shape, layer, "", (piece,))}


def _net_runs(
    net_id: str,
    name: str,
    tracks: Sequence[Track],
    arcs: Sequence[Arc],
    pieces: Sequence[Piece],
    kept: set[str],
) -> list[Run]:
    ends: dict[tuple[str, Point], list[Track | Arc]] = {}
    for item in (*tracks, *arcs):
        for point in dict.fromkeys((item.start, item.end)):
            ends.setdefault((item.layer, point), []).append(item)

    def movable(item: Track | Arc) -> bool:
        return isinstance(item, Track) and not item.locked and item.id not in kept and item.start != item.end

    inner_at: dict[tuple[str, Point], tuple[Track, Track] | None] = {}

    def inner(layer: str, at: Point) -> tuple[Track, Track] | None:
        key = (layer, at)
        if key not in inner_at:
            items = ends.get(key, [])
            found: tuple[Track, Track] | None = None
            if len(items) == 2 and all(movable(item) for item in items):
                a, b = items
                assert isinstance(a, Track) and isinstance(b, Track)
                others = [piece for piece in pieces if piece.ident not in (a.id, b.id)]
                if a.width == b.width and not joined_at(Thick((at,), a.width), layer, "", others):
                    found = (a, b)
            inner_at[key] = found
        return inner_at[key]

    runs: list[Run] = []
    seen: set[str] = set()
    for track in sorted(tracks, key=lambda item: item.id):
        if track.id in seen or not movable(track):
            continue
        seen.add(track.id)
        chain, points = [track], [track.start, track.end]
        closed = False
        for forward in (True, False):
            while not closed:
                tip = points[-1] if forward else points[0]
                last = chain[-1] if forward else chain[0]
                pair = inner(track.layer, tip)
                if pair is None:
                    break
                step = pair[0] if pair[1].id == last.id else pair[1]
                if step.id == (chain[0] if forward else chain[-1]).id:
                    closed = True
                    break
                if step.id in seen:
                    break
                seen.add(step.id)
                far = step.end if step.start == tip else step.start
                if forward:
                    chain.append(step)
                    points.append(far)
                else:
                    chain.insert(0, step)
                    points.insert(0, far)
        if closed or len(chain) < 2 or points[0] == points[-1]:
            continue
        own = {item.id for item in chain}
        others = [piece for piece in pieces if piece.ident not in own]
        width = track.width
        at_ends = _touches(Thick((points[0],), width), track.layer, others) | _touches(
            Thick((points[-1],), width), track.layer, others
        )
        along: set[str] = set()
        for item in chain:
            along |= _touches(Thick((item.start, item.end), width), track.layer, others)
        if along <= at_ends:
            runs.append(Run(net_id, name, track.layer, width, tuple(chain), tuple(points)))
    return runs


def find_runs(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    nets: Collection[str] | None = None,
    keep: Collection[str] = (),
) -> tuple[tuple[Run, ...], tuple[Issue, ...]]:
    """The runs of the selected nets, in the order they are straightened, and the issues: a
    ``tidy.net-skipped`` per net that could not be shaped and a ``tidy.straighten-skipped`` per protected
    net with a run."""
    board = design.board
    if board is None:
        return (), ()
    shaped = net_pieces(design, pads)
    protected = protected_nets(design)
    order = {layer: index for index, layer in enumerate(copper_layers(board))}
    kept = set(keep)
    runs: list[Run] = []
    issues: list[Issue] = []
    for net_id, name in selected_nets(design, nets):
        tracks = [track for track in board.tracks if track.net_id == net_id]
        if len(tracks) < 2:
            continue
        if net_id in shaped.unsupported:
            issues.append(
                issue(
                    "tidy.net-skipped",
                    f"net {name} has copper that could not be shaped, so tidy leaves it as it is",
                    where=name,
                )
            )
            continue
        arcs = [arc for arc in board.arcs if arc.net_id == net_id]
        found = _net_runs(net_id, name, tracks, arcs, shaped.pieces.get(net_id, ()), kept)
        if not found:
            continue
        if net_id in protected:
            issues.append(
                issue(
                    "tidy.straighten-skipped",
                    f"net {name} is in a differential pair or has a length rule, so its {len(found)} run(s) "
                    "stay as they are",
                    where=name,
                )
            )
            continue
        runs.extend(
            sorted(found, key=lambda run: (order.get(run.layer, len(order)), run.layer, min(run.ids)))
        )
    return tuple(runs), tuple(issues)


def shapes(start: Point, end: Point) -> tuple[tuple[Point, ...], ...]:
    """The shapes tried between two points, in list order: the straight segment when the points are
    aligned or on a diagonal; else diagonal then straight, straight then diagonal, straight-diagonal-straight
    with the diagonal at 1/2, 1/4 and 3/4 of the straight part, the two L shapes, and the two L shapes with
    a 45° cut of half the shorter side."""
    dx, dy = end.x - start.x, end.y - start.y
    ax, ay = abs(dx), abs(dy)
    if ax == 0 and ay == 0:
        return ()
    if ax == 0 or ay == 0 or ax == ay:
        return ((start, end),)
    sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
    d, rest = min(ax, ay), abs(ax - ay)
    major = (sx, 0) if ax > ay else (0, sy)

    def go(point: Point, way: tuple[int, int], n: int) -> Point:
        return Point(point.x + way[0] * n, point.y + way[1] * n)

    found: list[tuple[Point, ...]] = [
        (start, go(start, (sx, sy), d), end),
        (start, go(start, major, rest), end),
    ]
    for num, den in _SPLITS:
        cut = rest * num // den
        if 0 < cut < rest:
            bend = go(start, major, cut)
            found.append((start, bend, go(bend, (sx, sy), d), end))
    found += [(start, Point(end.x, start.y), end), (start, Point(start.x, end.y), end)]
    half = d // 2
    if half > 0:
        found.append((start, Point(end.x - half * sx, start.y), Point(end.x, start.y + half * sy), end))
        found.append((start, Point(start.x, end.y - half * sy), Point(start.x + half * sx, end.y), end))
    return tuple(dict.fromkeys(found))


def _in_pad(point: Point, layer: str, pads: Sequence[Piece]) -> bool:
    return joined_at(Thick((point,), _PROBE), layer, "", pads)


def weight(
    points: Sequence[Point],
    layer: str,
    *,
    before: Sequence[tuple[int, int]] = (),
    after: Sequence[tuple[int, int]] = (),
    bars: tuple[Sequence[tuple[int, int]], Sequence[tuple[int, int]]] = ((), ()),
    pads: Sequence[Piece] = (),
    acute: bool = False,
) -> int | None:
    """The weighted turns of the path ``points``: its own turns (free in ``pads``), the joints with tracks
    that leave its first point along ``before`` and its last point along ``after``, and the joints with
    tracks that pass through its first and its last point along the directions of ``bars`` (each the
    lighter of its two ways). ``None`` when a turn is acute and ``acute`` is false."""
    total = 0
    turns: list[tuple[str, Point | None]] = []
    for a, b, c in zip(points, points[1:], points[2:], strict=False):
        turns.append((turn_kind(vector(a, b), vector(b, c)), b))
    first, last = vector(points[0], points[1]), vector(points[-2], points[-1])
    turns += [(turn_kind((-way[0], -way[1]), first), None) for way in before]
    turns += [(turn_kind(last, way), None) for way in after]
    for way in bars[0]:
        kinds = (turn_kind(way, first), turn_kind((-way[0], -way[1]), first))
        turns.append((min(kinds, key=TURN_WEIGHTS.__getitem__), None))
    for way in bars[1]:
        kinds = (turn_kind(last, way), turn_kind(last, (-way[0], -way[1])))
        turns.append((min(kinds, key=TURN_WEIGHTS.__getitem__), None))
    for kind, at in turns:
        if kind == "acute" and not acute:
            return None
        if kind == "straight" or (at is not None and pads and _in_pad(at, layer, pads)):
            continue
        total += TURN_WEIGHTS[kind]
    return total


def _length(points: Sequence[Point]) -> int:
    return sum(floor_sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2) for a, b in pairwise(points))


def _leaving(point: Point, items: Iterable[Track | Arc]) -> list[tuple[int, int]]:
    """The directions in which the tracks and arcs of ``items`` that end at ``point`` leave it (an arc
    toward its middle point)."""
    found: list[tuple[int, int]] = []
    for item in items:
        if point not in (item.start, item.end):
            continue
        other = item.mid if isinstance(item, Arc) else item.end if item.start == point else item.start
        way = vector(point, other)
        if way != (0, 0):
            found.append(way)
    return found


def _through(point: Point, items: Iterable[Track]) -> list[tuple[int, int]]:
    """The directions of the tracks of ``items`` that pass through ``point`` strictly between their
    ends."""
    found: list[tuple[int, int]] = []
    for item in items:
        way, to_point = vector(item.start, item.end), vector(item.start, point)
        along = way[0] * to_point[0] + way[1] * to_point[1]
        if way[0] * to_point[1] - way[1] * to_point[0] == 0 and 0 < along < way[0] ** 2 + way[1] ** 2:
            found.append(way)
    return found


def _segments(run: Run, shape: Sequence[Point]) -> list[Track]:
    """The tracks of ``shape``: the run's tracks in order with new ends, then new tracks."""
    out: list[Track] = []
    for index, (a, b) in enumerate(pairwise(shape)):
        if index < len(run.tracks):
            out.append(dataclasses.replace(run.tracks[index], start=a, end=b))
            continue
        key = content_hash(run.net, ["straighten", a.x, a.y, b.x, b.y, run.width, run.layer])
        out.append(
            Track(
                id=derived_id("trk", "tidy", key),
                start=a,
                end=b,
                width=run.width,
                layer=run.layer,
                net_id=run.net_id,
            )
        )
    return out


def _try_run(
    design: Design,
    run: Run,
    pieces: Mapping[str, Sequence[Piece]],
    check: Check,
    base: Sequence[Clash],
) -> tuple[Design, Edit, list[Piece]] | None:
    """The design with ``run`` replaced by the first shape that passes, its edit and the net's new pieces;
    ``None`` when no shape passes."""
    board = design.board
    assert board is not None
    own = list(pieces.get(run.net_id, ()))
    others = [piece for piece in own if piece.ident not in run.ids]
    start, end = run.points[0], run.points[-1]
    contacts = _touches(Thick((start,), run.width), run.layer, others) | _touches(
        Thick((end,), run.width), run.layer, others
    )
    end_pads = [piece for piece in others if piece.kind == "pad" and piece.ident in contacts]
    near = [
        item
        for item in (*board.tracks, *board.arcs)
        if item.net_id == run.net_id and item.layer == run.layer and item.id not in run.ids
    ]
    before, after = _leaving(start, near), _leaving(end, near)
    straight = [item for item in near if isinstance(item, Track)]
    bars = (_through(start, straight), _through(end, straight))
    found = weight(run.points, run.layer, before=before, after=after, bars=bars, pads=end_pads, acute=True)
    assert found is not None
    tried: list[tuple[int, int, int, tuple[Point, ...]]] = []
    for index, shape in enumerate(shapes(start, end)):
        cost = weight(shape, run.layer, before=before, after=after, bars=bars, pads=end_pads)
        if cost is not None and cost < found:
            tried.append((cost, _length(shape), index, shape))
    foreign = [piece for net, held in pieces.items() if net != run.net_id for piece in held]
    for _, _, _, shape in sorted(tried):
        tracks = _segments(run, shape)
        made = [track_piece(track) for track in tracks]
        touched: set[str] = set()
        for piece in made:
            touched |= _touches(piece.shapes[0][1], run.layer, others)
        if not touched <= contacts:
            continue
        if any(joined_at(piece.shapes[0][1], run.layer, "", foreign) for piece in made):
            continue
        dropped = tuple(track.id for track in run.tracks[len(tracks) :])
        if not keeps_groups(own, [*others, *made], removed=dropped):
            continue
        changed = {track.id: track for track in tracks}
        kept = [changed.pop(track.id, track) for track in board.tracks if track.id not in dropped]
        edited = dataclasses.replace(
            design, board=dataclasses.replace(board, tracks=(*kept, *changed.values()))
        )
        if fresh_clashes(base, check(edited)):
            continue
        reused = tuple(track.id for track in run.tracks[: len(tracks)])
        added = tuple(track.id for track in tracks[len(run.tracks) :])
        edit = Edit("straighten", REASON, run.net, run.layer, start, dropped, reused, added)
        return edited, edit, [*others, *made]
    return None


def straighten(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    check: Check,
    nets: Collection[str] | None = None,
    keep: Collection[str] = (),
) -> TidyResult:
    """``design`` with its runs straightened (see the module). ``pads`` are the board-frame pad records,
    ``check`` the copper check, ``nets`` the net names (every net for ``None``), ``keep`` ids that stay."""
    runs, found = find_runs(design, pads=pads, nets=nets, keep=keep)
    if design.board is None or not runs:
        return TidyResult(design, (), found)
    pieces = {net: list(held) for net, held in net_pieces(design, pads).pieces.items()}
    base = check(design)
    current = design
    edits: list[Edit] = []
    for run in runs:
        outcome = _try_run(current, run, pieces, check, base)
        if outcome is None:
            continue
        current, edit, pieces[run.net_id] = outcome
        edits.append(edit)
    return TidyResult(current, tuple(edits), found)


__all__ = ["LENGTH_KINDS", "REASON", "Run", "find_runs", "protected_nets", "shapes", "straighten", "weight"]
