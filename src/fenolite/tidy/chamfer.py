# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Chamfer the right-angle joints and the T-joints of tracks, and the corners of zone outlines (capability
copper-tidy, "Chamfer right-angle joints", "Chamfer T-joints" and "Chamfer zone outlines"; ``docs/copper.md``,
"Copper tidy").

A corner is a point where exactly two tracks of one net and one layer end, nothing else of the net touches
the disc of the track width there, both tracks are horizontal or vertical, at 90° to each other, of one
width, unlocked and not kept. Its chamfer moves both ends back by the leg along their tracks and joins the
two new ends by a 45° track. The leg is ``leg`` or twice the width, and at most half of the shorter track,
so two chamfers on one track never overlap; a track that two chamfers shorten to nothing is removed.

A T-joint is a point where a horizontal or vertical track (the stem, unlocked and not kept) ends at 90° on
a bar of its net, layer and width: the inside of one track, or the joint of two collinear tracks, with
nothing else of the net there. Its 45° entry moves the stem's end back by the leg and joins it by a 45°
track to the bar at the leg's distance from the joint, on the side with more bar (the side of increasing
x or y on a tie). The leg is at most half of the stem and of that side; the bar does not change.

A chamfer or an entry is kept only when it keeps its net's groups (``graph.keeps_groups``) and adds no
finding to the copper check that the caller passes (``check``). The check runs on the board with every
chamfer; a chamfer whose items a new finding names is undone, and the check runs again, until it finds
nothing new. A new finding that names no chamfer undoes all of them. Each undone chamfer gives
``tidy.chamfer-undone``.

With ``zones``, each convex corner of a horizontal and a vertical edge of the outline of an unlocked zone of
a selected net is cut by a 45° edge, with legs of ``leg`` or ``ZONE_LEG``, at most half of each edge. A cut
that leaves an item of the net that touched the outline without contact is undone; a cut zone loses its
fill.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import content_hash, derived_id
from fenolite.core.units import format_length
from fenolite.geometry import GeometryError, Thick, area2
from fenolite.model.board import Arc, Track, Zone
from fenolite.model.design import Design
from fenolite.tidy.codes import issue
from fenolite.tidy.edits import Check, Clash, Edit, TidyResult, fresh_clashes
from fenolite.tidy.graph import (
    Piece,
    copper_layers,
    expand_layers,
    joined_at,
    keeps_groups,
    net_pieces,
    ring,
    track_piece,
)
from fenolite.tidy.prune import selected_nets

ZONE_LEG = 1_000_000
"""The leg of a cut of a zone corner without ``leg``: 1 mm."""


@dataclass(frozen=True, slots=True)
class Corner:
    """A right-angle joint and its chamfer: the net, the layer, the joint, the two tracks (``first`` has
    the smaller id), the leg and the 45° track that replaces the corner."""

    net_id: str
    net: str
    layer: str
    at: Point
    first: Track
    second: Track
    leg: int
    diagonal: Track

    @property
    def items(self) -> frozenset[str]:
        return frozenset((self.first.id, self.second.id, self.diagonal.id))

    @property
    def cuts(self) -> dict[str, tuple[Point, Point]]:
        """Each cut track's id → its end at the joint and that end moved back."""
        return {self.first.id: (self.at, self.diagonal.start), self.second.id: (self.at, self.diagonal.end)}

    @property
    def label(self) -> str:
        return f"the chamfer of the joint of {self.first.id} and {self.second.id}"


@dataclass(frozen=True, slots=True)
class Tee:
    """A T-joint and its 45° entry: the net, the layer, the joint, the stem, the one or two tracks of the
    bar, the leg and the 45° track from the stem's moved end to the bar."""

    net_id: str
    net: str
    layer: str
    at: Point
    stem: Track
    bar: tuple[Track, ...]
    leg: int
    diagonal: Track

    @property
    def items(self) -> frozenset[str]:
        return frozenset((self.stem.id, *(track.id for track in self.bar), self.diagonal.id))

    @property
    def cuts(self) -> dict[str, tuple[Point, Point]]:
        return {self.stem.id: (self.at, self.diagonal.start)}

    @property
    def label(self) -> str:
        bar = " and ".join(track.id for track in self.bar)
        return f"the 45° entry of {self.stem.id} into {bar}"


Joint = Corner | Tee
"""A joint that ``chamfer`` changes."""


def _away(track: Track, at: Point) -> tuple[int, int] | None:
    """The unit step from ``at`` along ``track`` toward its other end, for a horizontal or vertical
    track; ``None`` for another direction."""
    other = track.end if track.start == at else track.start
    dx, dy = other.x - at.x, other.y - at.y
    if (dx == 0) == (dy == 0):
        return None
    return ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))


def _length(track: Track) -> int:
    return abs(track.end.x - track.start.x) + abs(track.end.y - track.start.y)


def _go(at: Point, way: tuple[int, int], size: int) -> Point:
    return Point(at.x + size * way[0], at.y + size * way[1])


def _diagonal(net: str, first: Point, second: Point, like: Track) -> Track:
    a, b = sorted((first, second), key=lambda point: (point.x, point.y))
    key = content_hash(net, [a.x, a.y, b.x, b.y, like.width, like.layer])
    return Track(
        id=derived_id("trk", "tidy", key),
        start=first,
        end=second,
        width=like.width,
        layer=like.layer,
        net_id=like.net_id,
    )


def _movable(track: Track, kept: Collection[str]) -> bool:
    return not track.locked and track.id not in kept and track.start != track.end


def _skipped(name: str) -> Issue:
    return issue(
        "tidy.net-skipped",
        f"net {name} has copper that could not be shaped, so tidy leaves it as it is",
        where=name,
    )


def find_joints(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    nets: Collection[str] | None = None,
    keep: Collection[str] = (),
    leg: int | None = None,
) -> tuple[tuple[Joint, ...], tuple[Issue, ...]]:
    """The right-angle joints and the T-joints of the selected nets, in net-name, layer and point order,
    and the ``tidy.net-skipped`` issues of nets that could not be shaped."""
    board = design.board
    if board is None:
        return (), ()
    shaped = net_pieces(design, pads)
    kept = set(keep)
    found: list[Joint] = []
    issues: list[Issue] = []
    for net_id, name in selected_nets(design, nets):
        tracks = [track for track in board.tracks if track.net_id == net_id]
        if not tracks:
            continue
        if net_id in shaped.unsupported:
            issues.append(_skipped(name))
            continue
        ends: dict[tuple[str, Point], list[Track | Arc]] = {}
        for item in (*tracks, *(arc for arc in board.arcs if arc.net_id == net_id)):
            for point in dict.fromkeys((item.start, item.end)):
                ends.setdefault((item.layer, point), []).append(item)
        pieces = shaped.pieces.get(net_id, ())
        for (layer, at), items in sorted(
            ends.items(), key=lambda pair: (pair[0][0], pair[0][1].x, pair[0][1].y)
        ):
            joint = _corner(net_id, name, layer, at, items, pieces, kept, leg) or _tee(
                net_id, name, layer, at, items, tracks, pieces, kept, leg
            )
            if joint is not None:
                found.append(joint)
    return tuple(found), tuple(issues)


def find_corners(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    nets: Collection[str] | None = None,
    keep: Collection[str] = (),
    leg: int | None = None,
) -> tuple[tuple[Corner, ...], tuple[Issue, ...]]:
    """The right-angle joints of ``find_joints``, and its issues."""
    joints, issues = find_joints(design, pads=pads, nets=nets, keep=keep, leg=leg)
    return tuple(joint for joint in joints if isinstance(joint, Corner)), issues


def _corner(
    net_id: str,
    name: str,
    layer: str,
    at: Point,
    items: Sequence[Track | Arc],
    pieces: Sequence[Piece],
    kept: set[str],
    leg: int | None,
) -> Corner | None:
    if len(items) != 2 or not all(isinstance(item, Track) for item in items):
        return None
    first, second = sorted((item for item in items if isinstance(item, Track)), key=lambda item: item.id)
    if first.width != second.width or not _movable(first, kept) or not _movable(second, kept):
        return None
    one, two = _away(first, at), _away(second, at)
    if one is None or two is None or one[0] * two[0] + one[1] * two[1] != 0:
        return None
    others = [piece for piece in pieces if piece.ident not in (first.id, second.id)]
    if joined_at(Thick((at,), first.width), layer, "", others):
        return None
    size = min(leg if leg is not None else 2 * first.width, _length(first) // 2, _length(second) // 2)
    if size <= 0:
        return None
    a, b = _go(at, one, size), _go(at, two, size)
    return Corner(net_id, name, layer, at, first, second, size, _diagonal(name, a, b, first))


def _inside(track: Track, at: Point) -> bool:
    """Whether ``at`` lies on the horizontal or vertical ``track`` strictly between its ends."""
    a, b = track.start, track.end
    if a.y == b.y == at.y:
        return min(a.x, b.x) < at.x < max(a.x, b.x)
    if a.x == b.x == at.x:
        return min(a.y, b.y) < at.y < max(a.y, b.y)
    return False


def _tee(
    net_id: str,
    name: str,
    layer: str,
    at: Point,
    items: Sequence[Track | Arc],
    tracks: Sequence[Track],
    pieces: Sequence[Piece],
    kept: set[str],
    leg: int | None,
) -> Tee | None:
    if not all(isinstance(item, Track) and item.start != item.end for item in items):
        return None
    ends = [item for item in items if isinstance(item, Track)]
    sides: list[tuple[tuple[int, int], int]] = []
    if len(ends) == 3:
        ways = [_away(track, at) for track in ends]
        if any(way is None for way in ways) or len({track.width for track in ends}) != 1:
            return None
        stems = [
            index
            for index, way in enumerate(ways)
            if all(
                other is not None and way is not None and way[0] * other[0] + way[1] * other[1] == 0
                for other in ways[:index] + ways[index + 1 :]
            )
        ]
        if len(stems) != 1:
            return None
        stem = ends[stems[0]]
        bar = tuple(sorted((track for track in ends if track is not stem), key=lambda track: track.id))
        for track in bar:
            way = _away(track, at)
            assert way is not None
            sides.append((way, _length(track)))
    elif len(ends) == 1:
        stem = ends[0]
        bars = [
            track
            for track in tracks
            if track.layer == layer
            and track.id != stem.id
            and track.width == stem.width
            and _inside(track, at)
        ]
        if len(bars) != 1:
            return None
        bar = (bars[0],)
        for point in (bars[0].start, bars[0].end):
            dx, dy = point.x - at.x, point.y - at.y
            sides.append((((dx > 0) - (dx < 0), (dy > 0) - (dy < 0)), abs(dx) + abs(dy)))
    else:
        return None
    if not _movable(stem, kept):
        return None
    out = _away(stem, at)
    if out is None or any(way[0] * out[0] + way[1] * out[1] != 0 for way, _ in sides):
        return None
    if sides[0][0] != (-sides[1][0][0], -sides[1][0][1]):
        return None
    others = [piece for piece in pieces if piece.ident not in {stem.id, *(track.id for track in bar)}]
    if joined_at(Thick((at,), stem.width), layer, "", others):
        return None
    way, side = max(sides, key=lambda pair: (pair[1], pair[0][0] + pair[0][1]))
    size = min(leg if leg is not None else 2 * stem.width, _length(stem) // 2, side // 2)
    if size <= 0:
        return None
    diagonal = _diagonal(name, _go(at, out, size), _go(at, way, size), stem)
    return Tee(net_id, name, layer, at, stem, bar, size, diagonal)


def _cut_tracks(tracks: Sequence[Track], joints: Sequence[Joint]) -> tuple[list[Track], set[str]]:
    """``tracks`` with the ends of ``joints`` moved back, and the ids of tracks shortened to nothing
    (left out)."""
    cuts: dict[str, dict[Point, Point]] = {}
    for joint in joints:
        for ident, (old, new) in joint.cuts.items():
            cuts.setdefault(ident, {})[old] = new
    out: list[Track] = []
    gone: set[str] = set()
    for track in tracks:
        moved = cuts.get(track.id)
        if moved is None:
            out.append(track)
            continue
        start, end = moved.get(track.start, track.start), moved.get(track.end, track.end)
        if start == end:
            gone.add(track.id)
            continue
        out.append(dataclasses.replace(track, start=start, end=end))
    return out, gone


def apply_corners(design: Design, corners: Sequence[Joint]) -> Design:
    """``design`` with the chamfers of ``corners`` (right-angle joints or T-joints): the 45° tracks follow
    the board's tracks, in the order of ``corners``."""
    board = design.board
    if board is None or not corners:
        return design
    tracks, _ = _cut_tracks(board.tracks, corners)
    tracks.extend(corner.diagonal for corner in corners)
    return dataclasses.replace(design, board=dataclasses.replace(board, tracks=tuple(tracks)))


def _keeps(pieces: Sequence[Piece], tracks: Sequence[Track], joints: Sequence[Joint]) -> bool:
    """Whether the chamfers ``joints`` of one net keep the groups of its ``pieces``."""
    touched = {ident for joint in joints for ident in joint.cuts}
    own = [track for track in tracks if track.id in touched]
    cut, gone = _cut_tracks(own, joints)
    after = [piece for piece in pieces if piece.ident not in touched]
    after.extend(track_piece(track) for track in cut)
    after.extend(track_piece(joint.diagonal) for joint in joints)
    return keeps_groups(pieces, after, removed=gone)


def _undone(joint: Joint, why: str) -> Issue:
    where = sorted(joint.items - {joint.diagonal.id})
    return issue(
        "tidy.chamfer-undone",
        f"{joint.label} of net {joint.net} on {joint.layer} (leg {format_length(joint.leg)}) is undone: "
        f"{why}",
        where=", ".join(where),
    )


def _blame(clash: Clash) -> str:
    return f"it adds {clash.code} on {clash.layer} between {', '.join(clash.items)}"


def _edit(joint: Joint, gone: set[str], reported: set[str]) -> Edit:
    if isinstance(joint, Tee):
        return Edit(
            "chamfer", "t-joint", joint.net, joint.layer, joint.at, (), (joint.stem.id,), (joint.diagonal.id,)
        )
    pair = (joint.first.id, joint.second.id)
    removed = tuple(ident for ident in pair if ident in gone and ident not in reported)
    reported.update(removed)
    return Edit(
        "chamfer",
        "right-angle",
        joint.net,
        joint.layer,
        joint.at,
        removed=removed,
        replaced=tuple(ident for ident in pair if ident not in gone),
        added=(joint.diagonal.id,),
    )


def chamfer(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    check: Check,
    nets: Collection[str] | None = None,
    keep: Collection[str] = (),
    leg: int | None = None,
    zones: bool = False,
) -> TidyResult:
    """``design`` with its right-angle joints chamfered and its T-joints entered at 45° (see the module),
    each kept only when it keeps its net's groups and adds no finding of ``check``; with ``zones``, the
    corners of the zone outlines of the selected nets cut too."""
    board = design.board
    joints, issues_found = find_joints(design, pads=pads, nets=nets, keep=keep, leg=leg)
    issues = list(issues_found)
    edits: list[Edit] = []
    done = design
    if board is not None and joints:
        shaped = net_pieces(design, pads)
        accepted: list[Joint] = []
        for joint in joints:
            if _keeps(shaped.pieces.get(joint.net_id, ()), board.tracks, (joint,)):
                accepted.append(joint)
            else:
                issues.append(_undone(joint, "it would change the groups of its net"))
        for net_id in sorted({joint.net_id for joint in accepted}):
            own = [joint for joint in accepted if joint.net_id == net_id]
            if not _keeps(shaped.pieces.get(net_id, ()), board.tracks, own):
                accepted = [joint for joint in accepted if joint.net_id != net_id]
                issues.extend(
                    _undone(joint, "the chamfers of its net together change its groups") for joint in own
                )
        base = check(design)
        while accepted:
            fresh = fresh_clashes(base, check(apply_corners(design, accepted)))
            if not fresh:
                break
            blamed: dict[int, Clash] = {}
            for index, joint in enumerate(accepted):
                named = next((clash for clash in fresh if joint.items & set(clash.items)), None)
                if named is not None:
                    blamed[index] = named
            if not blamed:
                blamed = dict.fromkeys(range(len(accepted)), fresh[0])
            for index, clash in blamed.items():
                issues.append(_undone(accepted[index], _blame(clash)))
            accepted = [joint for index, joint in enumerate(accepted) if index not in blamed]
        if accepted:
            _, gone = _cut_tracks(board.tracks, accepted)
            reported: set[str] = set()
            edits.extend(_edit(joint, gone, reported) for joint in accepted)
            done = apply_corners(design, accepted)
    if zones:
        done, zone_edits, zone_issues = cut_zones(done, pads=pads, nets=nets, keep=keep, leg=leg)
        edits.extend(zone_edits)
        issues.extend(zone_issues)
    return TidyResult(done, tuple(edits), tuple(issues))


def _zone_cuts(outline: Sequence[Point], leg: int) -> list[tuple[int, Point, Point]]:
    """The cuts of the convex corners of ``outline`` (as a ring) whose two edges are horizontal and
    vertical: the vertex index and the two new vertices, the one toward the previous vertex first."""
    points = ring(outline)
    turn = area2(points) if len(points) >= 3 else 0
    found: list[tuple[int, Point, Point]] = []
    for index, at in enumerate(points):
        if turn == 0:
            break
        before, after = points[index - 1], points[(index + 1) % len(points)]
        back = (before.x - at.x, before.y - at.y)
        ahead = (after.x - at.x, after.y - at.y)
        if (back[0] == 0) == (back[1] == 0) or (ahead[0] == 0) == (ahead[1] == 0):
            continue
        if back[0] * ahead[0] + back[1] * ahead[1] != 0:
            continue
        cross = (at.x - before.x) * (after.y - at.y) - (at.y - before.y) * (after.x - at.x)
        if (cross > 0) != (turn > 0):
            continue
        size = min(leg, (abs(back[0]) + abs(back[1])) // 2, (abs(ahead[0]) + abs(ahead[1])) // 2)
        if size <= 0:
            continue
        unit_back = ((back[0] > 0) - (back[0] < 0), (back[1] > 0) - (back[1] < 0))
        unit_ahead = ((ahead[0] > 0) - (ahead[0] < 0), (ahead[1] > 0) - (ahead[1] < 0))
        found.append((index, _go(at, unit_back, size), _go(at, unit_ahead, size)))
    return found


def _cut_outline(outline: Sequence[Point], cuts: Sequence[tuple[int, Point, Point]]) -> tuple[Point, ...]:
    points = ring(outline)
    by_index = {index: (a, b) for index, a, b in cuts}
    out: list[Point] = []
    for index, point in enumerate(points):
        out.extend(by_index.get(index, (point,)))
    return tuple(out)


def _contacts(
    outline: Sequence[Point], layers: Sequence[str], pieces: Sequence[Piece]
) -> set[tuple[str, str]]:
    """The (piece id, layer) of the pieces that touch the region of ``outline`` on ``layers``."""
    try:
        area = Thick(ring(outline), 0, filled=True)
    except (GeometryError, ValueError):
        return set()
    zone = Piece("zone", "outline", tuple((layer, area) for layer in layers))
    return {
        (piece.ident, layer)
        for piece in pieces
        for layer, shape in piece.shapes
        if layer in layers and joined_at(shape, layer, "", (zone,))
    }


def cut_zones(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    nets: Collection[str] | None = None,
    keep: Collection[str] = (),
    leg: int | None = None,
) -> tuple[Design, tuple[Edit, ...], tuple[Issue, ...]]:
    """``design`` with the convex right-angle corners of the zone outlines of the selected nets cut (see
    the module), the edits (reason ``zone-corner``, no layer) and the ``tidy.chamfer-undone`` issues."""
    board = design.board
    if board is None:
        return design, (), ()
    copper = copper_layers(board)
    shaped = net_pieces(design, pads)
    names = dict(selected_nets(design, nets))
    size = leg if leg is not None else ZONE_LEG
    edits: list[Edit] = []
    issues: list[Issue] = []
    zones: list[Zone] = []
    for zone in board.zones:
        name = names.get(zone.net_id or "")
        layers = expand_layers(zone.layers, copper)
        cuts = _zone_cuts(zone.outline, size) if name and not zone.locked and zone.id not in keep else []
        if name is None or not cuts or zone.net_id in shaped.unsupported:
            zones.append(zone)
            continue
        pieces = [piece for piece in shaped.pieces.get(zone.net_id or "", ()) if piece.kind != "fill"]
        before = _contacts(zone.outline, layers, pieces)
        kept_cuts: list[tuple[int, Point, Point]] = []
        points = ring(zone.outline)
        for cut in cuts:
            lost = before - _contacts(_cut_outline(zone.outline, (cut,)), layers, pieces)
            if lost:
                issues.append(_zone_undone(zone, name, points[cut[0]], lost))
            else:
                kept_cuts.append(cut)
        if kept_cuts:
            lost = before - _contacts(_cut_outline(zone.outline, kept_cuts), layers, pieces)
            if lost:
                issues.extend(_zone_undone(zone, name, points[cut[0]], lost) for cut in kept_cuts)
                kept_cuts = []
        if not kept_cuts:
            zones.append(zone)
            continue
        zones.append(
            dataclasses.replace(zone, outline=_cut_outline(zone.outline, kept_cuts), fills=(), filled=False)
        )
        edits.extend(
            Edit("chamfer", "zone-corner", name, "", points[cut[0]], replaced=(zone.id,)) for cut in kept_cuts
        )
    if not edits:
        return design, (), tuple(issues)
    return (
        dataclasses.replace(design, board=dataclasses.replace(board, zones=tuple(zones))),
        tuple(edits),
        tuple(issues),
    )


def _zone_undone(zone: Zone, name: str, at: Point, lost: set[tuple[str, str]]) -> Issue:
    items = ", ".join(sorted({ident for ident, _ in lost}))
    return issue(
        "tidy.chamfer-undone",
        f"the cut of the corner of zone {zone.id} of net {name} at ({format_length(at.x)}, "
        f"{format_length(at.y)}) is undone: it would leave {items} without contact with the zone",
        where=zone.id,
    )


__all__ = [
    "ZONE_LEG",
    "Corner",
    "Joint",
    "Tee",
    "apply_corners",
    "chamfer",
    "cut_zones",
    "find_corners",
    "find_joints",
]
