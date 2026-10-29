# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rigid fit of a block of parts over their pads (capability layout-reuse, "Block copy by pad fit";
``docs/placement.md``, "Layout reuse").

A rigid transform here is a quarter turn, an optional mirror and a translation: ``p ↦ R(k·90°)·M^m·p + t``
in the sense of ``geometry.Transform``. For pairs ``(source, goal)`` of points the translation that
minimises the squared distances is the difference of the centroids, ``t = c_goal − L·c_source``, so the
least-squares fit tries the eight linear parts and keeps the best. The arithmetic is exact (fractions);
only the translation of the result is rounded to 2**-128 nm and a distance is rounded up to a nanometre.

The block transform maps the reference board onto the target board. It is fitted on the anchor's pads:
the pads with a number that occurs once in both footprints, paired by number, and the pads that numbers
cannot pair, paired by net partition (change c0227): the pairs by number of the whole block map each
reference net to a target net, and within a part a net with one unpaired pad on each side pairs them, or,
with more, each pad pairs with the reference pad whose goal lies nearest its image under the fit by number,
both ways and within the tolerance. Every part is then fitted on its own: its pads as they lie on the
target board are fitted onto the block transform of its reference part's pads, and its new placement is
that fit composed with its placement. The side is decided by the fit, so a reference drawn with the Y axis
up is found, not copied.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.trig import ONE, QUARTER_TURN
from fenolite.core.units import Nm, Udeg, round_half_even_div
from fenolite.geometry.transform import Transform
from fenolite.model.board import FootprintInstance, Side
from fenolite.model.design import Design
from fenolite.reuse.codes import issue

DEFAULT_TOLERANCE: Nm = 50_000
"""The largest distance of a fitted pad from its goal, by default: 0.05 mm."""

_FPoint = tuple[Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class Layout:
    """A board and its board-frame pad records (``backends.base.BoardFrame.board_pads``)."""

    design: Design
    pads: tuple[BoardPad, ...]


@dataclass(frozen=True, slots=True)
class Rigid:
    """A rigid fit: the transform and, per pair in order, the distance from the image of the source to
    its goal, rounded up to a nanometre."""

    transform: Transform
    distances: tuple[Nm, ...]

    @property
    def residual(self) -> Nm:
        """The largest distance."""
        return max(self.distances, default=0)

    def within(self, tolerance: Nm) -> int:
        """The number of pairs whose distance is at most ``tolerance``."""
        return sum(1 for distance in self.distances if distance <= tolerance)


@dataclass(frozen=True, slots=True)
class Placement:
    """Where a footprint lies: its position, its angle in microdegrees and its side."""

    at: Point
    rotation: Udeg
    side: Side


@dataclass(frozen=True, slots=True)
class PadMatch:
    """A pad of a copied part paired with its reference pad: its number on the target board, the
    reference pad's position on the reference board, its goal (the block transform of that position) on
    the target board, the distance from the fitted pad to the goal, rounded up, the pad ids on the target
    board before the move and on the reference board, the net ids of both, and how the pair was made
    (``number``, or ``net`` by net partition). A move may give a pad a new id; its footprint id stays."""

    number: str
    reference: Point
    goal: Point
    distance: Nm
    pad_id: str = ""
    reference_pad_id: str = ""
    net_id: str | None = None
    reference_net_id: str | None = None
    by: str = "number"


@dataclass(frozen=True, slots=True)
class PartFit:
    """The fit of one part: its reference on the target board and that of its reference part, the ids of
    its footprint on the target board and of its reference part's, its placement before, its new
    placement (``None``: not placed), the matched pads, the largest distance (``None`` without a matched
    pad), whether its new side differs from its reference part's, and whether the fit needs the side
    opposite to the block's."""

    ref: str
    reference: str
    footprint_id: str
    reference_id: str
    before: Placement
    placement: Placement | None
    pads: tuple[PadMatch, ...]
    residual: Nm | None
    side_changed: bool = False
    mirror_suspected: bool = False

    @property
    def matched(self) -> int:
        """The number of pads paired, by number or by net."""
        return len(self.pads)

    @property
    def by_net(self) -> int:
        """The number of pads paired by net partition."""
        return sum(1 for pad in self.pads if pad.by == "net")

    def within(self, tolerance: Nm) -> int:
        """The number of matched pads whose distance is at most ``tolerance``."""
        return sum(1 for pad in self.pads if pad.distance <= tolerance)


@dataclass(frozen=True, slots=True)
class BlockFit:
    """The fit of a block: the block transform (reference board → target board; ``None`` when the
    anchor could not be fitted), the anchor's reference on the target board, whether the anchor lies on
    the other side than its reference part (the copper layers of the block flip), the tolerance, the
    fit of every part found on both boards, and the issues (codes of ``reuse.codes``)."""

    transform: Transform | None
    anchor: str
    flipped: bool
    tolerance: Nm
    parts: tuple[PartFit, ...] = ()
    issues: tuple[Issue, ...] = ()

    @property
    def placed(self) -> tuple[PartFit, ...]:
        """The parts that have a new placement."""
        return tuple(part for part in self.parts if part.placement is not None)


def _linear(point: _FPoint, turn: int, mirror: bool) -> _FPoint:
    """``R(turn·90°)·M^mirror·point`` exactly, with ``M`` the mirror about the X axis (``y ↦ −y``)."""
    x, y = point
    if mirror:
        y = -y
    for _ in range(turn % 4):
        x, y = y, -x  # x' = x·cos + y·sin, y' = −x·sin + y·cos at 90°
    return x, y


def _centroid(points: Sequence[_FPoint]) -> _FPoint:
    count = len(points)
    return sum((p[0] for p in points), Fraction(0)) / count, sum((p[1] for p in points), Fraction(0)) / count


def _ceil_sqrt(value: Fraction) -> int:
    """The smallest integer whose square is at least ``value`` (``value >= 0``)."""
    root = isqrt(value.numerator // value.denominator)
    while root * root < value:
        root += 1
    return root


def _exact(point: Point) -> _FPoint:
    return Fraction(point.x), Fraction(point.y)


def fit_rigid(pairs: Sequence[tuple[Point, Point]], *, tolerance: Nm, mirror: bool = False) -> Rigid:
    """The rigid transform that maps the first point of each pair onto the second, by least squares over
    the four quarter turns and both mirrors. Of the candidates whose largest distance is at most
    ``tolerance``, the one whose mirror is ``mirror`` wins, then the smallest largest distance, then the
    smallest turn; with none, the smallest largest distance wins. ``ValueError`` without a pair."""
    if not pairs:
        raise ValueError("a rigid fit needs at least one pair of points")
    sources = [_exact(source) for source, _ in pairs]
    goals = [_exact(goal) for _, goal in pairs]
    centre = _centroid(goals)
    best: tuple[tuple[bool, bool, int, int], Rigid] | None = None
    for flip in (mirror, not mirror):
        for turn in range(4):
            moved_centre = _linear(_centroid(sources), turn, flip)
            tx, ty = centre[0] - moved_centre[0], centre[1] - moved_centre[1]
            distances: list[Nm] = []
            for source, goal in zip(sources, goals, strict=True):
                x, y = _linear(source, turn, flip)
                dx, dy = x + tx - goal[0], y + ty - goal[1]
                distances.append(_ceil_sqrt(dx * dx + dy * dy))
            residual = max(distances)
            key = (residual > tolerance, flip != mirror and residual <= tolerance, residual, turn)
            if best is None or key < best[0]:
                transform = Transform(turn * QUARTER_TURN, flip, round(tx * ONE), round(ty * ONE))
                best = (key, Rigid(transform, tuple(distances)))
    assert best is not None
    return best[1]


def placement_transform(placement: Placement) -> Transform:
    """The footprint frame → board transform of a placement: ``at + R(rotation)·M^bottom·p``, as KiCad
    and the board frame place a footprint's pads (``H-G-BOTTOM-PLACE``)."""
    return Transform.placement(placement.at, placement.rotation, placement.side == "bottom")


def moved_placement(fit: Transform, placement: Placement) -> Placement:
    """The placement whose pads are those of ``placement`` moved by ``fit``."""
    moved = fit.compose(placement_transform(placement))
    at = Point(round_half_even_div(moved.tx_fixed, ONE), round_half_even_div(moved.ty_fixed, ONE))
    return Placement(at, moved.rot_udeg, "bottom" if moved.mirror else "top")


@dataclass(frozen=True, slots=True)
class _Part:
    footprint: FootprintInstance
    pads: dict[str, BoardPad]
    """The pads with a number that occurs once in the footprint, by number."""
    every: tuple[BoardPad, ...] = ()
    """Every pad record of the footprint, in record order."""

    @property
    def placement(self) -> Placement:
        fp = self.footprint
        return Placement(fp.position, fp.rotation, fp.side)


def _parts(layout: Layout) -> dict[str, _Part]:
    """The footprints of a board by reference (the component's, else the pad records', else the id; the
    first of a reference wins), with their uniquely numbered pads."""
    board = layout.design.board
    if board is None:
        return {}
    components = {component.id: component.ref for component in layout.design.circuit.components}
    records: dict[str, list[BoardPad]] = {}
    for record in layout.pads:
        records.setdefault(record.footprint_id, []).append(record)
    found: dict[str, _Part] = {}
    for fp in board.footprints:
        own = records.get(fp.id, [])
        ref = components.get(fp.component_id) or (own[0].ref if own else "") or fp.id
        counts = Counter(record.number for record in own)
        unique = {record.number: record for record in own if record.number and counts[record.number] == 1}
        found.setdefault(ref, _Part(fp, unique, tuple(own)))
    return found


_Pair = tuple[BoardPad, BoardPad, str]
"""A pad of a part, its reference pad, and how they were paired (``number`` or ``net``)."""


def _numbered(part: _Part, reference: _Part) -> list[_Pair]:
    """The pads paired by a number found once in both footprints, by number."""
    common = sorted(set(part.pads) & set(reference.pads))
    return [(part.pads[n], reference.pads[n], "number") for n in common]


def _net_images(pairs: Sequence[_Pair]) -> dict[str, str]:
    """Reference net id → the one target net id that the pairs by number give it; a reference net with
    two target nets has none."""
    claimed: dict[str, set[str]] = {}
    for mine, theirs, _ in pairs:
        if mine.net_id is not None and theirs.net_id is not None:
            claimed.setdefault(theirs.net_id, set()).add(mine.net_id)
    return {net: next(iter(images)) for net, images in claimed.items() if len(images) == 1}


def _square(a: Point, b: Point) -> int:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


def _by_net(
    part: _Part,
    reference: _Part,
    numbered: Sequence[_Pair],
    nets: Mapping[str, str],
    *,
    image: Transform | None,
    goal: Transform,
    tolerance: Nm,
) -> list[_Pair]:
    """The pads that numbers do not pair, paired by net partition. ``image`` maps a pad of the part to
    where the fit by number puts it (``None``: no such fit), ``goal`` a reference pad to its goal. A net
    with one pad on each side pairs them (within the tolerance when there is a fit); with more and a fit,
    a pad pairs with the reference pad whose goal lies nearest its image when that pad's nearest image is
    this one, within the tolerance. Every other pad stays unpaired."""
    used = {mine.pad_id for mine, _, _ in numbered}
    used_reference = {theirs.pad_id for _, theirs, _ in numbered}
    ours: dict[str, list[BoardPad]] = {}
    for record in part.every:
        if record.pad_id not in used and record.net_id is not None:
            ours.setdefault(record.net_id, []).append(record)
    theirs: dict[str, list[BoardPad]] = {}
    for record in reference.every:
        mapped = nets.get(record.net_id) if record.net_id is not None else None
        if record.pad_id not in used_reference and mapped is not None:
            theirs.setdefault(mapped, []).append(record)
    limit = tolerance * tolerance
    found: list[_Pair] = []
    for net in sorted(set(ours) & set(theirs)):
        mine = sorted(ours[net], key=lambda record: record.pad_id)
        other = sorted(theirs[net], key=lambda record: record.pad_id)
        if image is None:
            if len(mine) == 1 and len(other) == 1:
                found.append((mine[0], other[0], "net"))
            continue
        images = [image.apply(record.position) for record in mine]
        goals = [goal.apply(record.position) for record in other]
        square = [[_square(at, to) for to in goals] for at in images]
        for i, record in enumerate(mine):
            row = square[i]
            j = min(range(len(other)), key=row.__getitem__)
            column = [square[k][j] for k in range(len(mine))]
            # a tie in either direction is a pad the partition cannot tell apart
            if (
                row[j] <= limit
                and row.count(row[j]) == 1
                and min(column) == row[j]
                and column.count(row[j]) == 1
            ):
                found.append((record, other[j], "net"))
    return found


def fit_block(
    reference: Layout,
    target: Layout,
    parts: Sequence[str],
    *,
    anchor: str | None = None,
    mapping: Mapping[str, str] | None = None,
    tolerance: Nm = DEFAULT_TOLERANCE,
    transform: Transform | None = None,
) -> BlockFit:
    """Fit the parts ``parts`` of ``target`` (references on the target board) onto their reference parts
    of ``reference``: the part of the same reference, or ``mapping[ref]``.

    The block transform is fitted on the pads of ``anchor`` (default: the first part), preferring the
    mirror that the two sides of the anchor give. Each part is then fitted onto the block transform of
    its reference part's pads, preferring the side its reference part's side gives through the block; a
    part whose fit leaves a pad farther than ``tolerance`` from its goal, or that has no pad paired by
    number, is not placed (``reuse.no-fit``), and a part placed on the other side than the preferred one
    gives ``reuse.mirror-suspected``. The anchor keeps its placement. ``ValueError`` for an empty or
    repeated part list, or an anchor that is not in it.

    With an explicit ``transform`` (a block layout reuse in a build, change c0255) there is no search:
    that transform is the block transform, the anchor is fitted like every other part, and the block
    flips when the transform mirrors."""
    chosen = list(parts)
    if not chosen or len(set(chosen)) != len(chosen):
        raise ValueError("the parts of a block must be named once each")
    head = chosen[0] if anchor is None else anchor
    if head not in chosen:
        raise ValueError(f"the anchor {head} is not a part of the block")
    names = dict(mapping or {})
    ours, theirs = _parts(target), _parts(reference)
    issues: list[Issue] = []
    known: list[tuple[str, str]] = []
    for ref in chosen:
        source = names.get(ref, ref)
        if ref not in ours:
            issues.append(issue("reuse.unknown-part", f"the target board has no part {ref}", where=ref))
        elif source not in theirs:
            issues.append(
                issue("reuse.unknown-part", f"the reference board has no part {source}", where=source)
            )
        else:
            known.append((ref, source))
    numbered = {ref: _numbered(ours[ref], theirs[source]) for ref, source in known}
    nets = _net_images([pair for pairs in numbered.values() for pair in pairs])
    if transform is not None:
        given_fits, given_issues = _fit_parts(
            known, ours, theirs, numbered, nets, transform, transform.mirror, tolerance, head=None
        )
        return BlockFit(transform, head, transform.mirror, tolerance, given_fits, (*issues, *given_issues))
    if head not in dict(known):
        return BlockFit(None, head, False, tolerance, (), tuple(issues))
    first, first_source = ours[head], theirs[names.get(head, head)]
    flipped = first.footprint.side != first_source.footprint.side
    head_pairs = list(numbered[head])
    rough = _fit(head_pairs, None, tolerance, reverse=True, mirror=flipped)
    head_pairs += _by_net(
        first,
        first_source,
        head_pairs,
        nets,
        image=Transform() if rough is not None else None,
        goal=rough.transform if rough is not None else Transform(),
        tolerance=tolerance,
    )
    block = (
        fit_rigid(
            [(theirs_.position, mine.position) for mine, theirs_, _ in head_pairs],
            tolerance=tolerance,
            mirror=flipped,
        )
        if head_pairs
        else None
    )
    if block is None or block.residual > tolerance:
        detail = (
            "no pad of it pairs by a number found once in both footprints or by its net"
            if block is None
            else f"{block.within(tolerance)} of its {len(head_pairs)} paired pads lie within the tolerance "
            f"and the farthest lies {block.residual} nm away"
        )
        issues.append(
            issue(
                "reuse.no-fit",
                f"the anchor {head} does not fit its reference part {names.get(head, head)}: {detail}; "
                "nothing is placed",
                where=head,
                hint="pick another --anchor, or map the parts with --map",
            )
        )
        return BlockFit(None, head, flipped, tolerance, (), tuple(issues))
    transform = block.transform
    fits, more = _fit_parts(
        known,
        ours,
        theirs,
        numbered,
        nets,
        transform,
        flipped,
        tolerance,
        head=head,
        anchor_fit=(head_pairs, block),
    )
    issues += more
    return BlockFit(transform, head, flipped, tolerance, fits, tuple(issues))


def _fit_parts(
    known: Sequence[tuple[str, str]],
    ours: Mapping[str, _Part],
    theirs: Mapping[str, _Part],
    numbered: Mapping[str, list[_Pair]],
    nets: Mapping[str, str],
    transform: Transform,
    flipped: bool,
    tolerance: Nm,
    *,
    head: str | None,
    anchor_fit: tuple[list[_Pair], Rigid] | None = None,
) -> tuple[tuple[PartFit, ...], list[Issue]]:
    """Each known part fitted onto the block ``transform`` of its reference part's pads; the anchor
    ``head`` keeps its placement with the pairs and fit of ``anchor_fit``."""
    issues: list[Issue] = []
    fits: list[PartFit] = []
    for ref, source in known:
        part, origin = ours[ref], theirs[source]
        before = part.placement
        if ref == head and anchor_fit is not None:
            head_pairs, block = anchor_fit
            fits.append(
                PartFit(
                    ref,
                    source,
                    part.footprint.id,
                    origin.footprint.id,
                    before,
                    before,
                    _matches(head_pairs, transform, block.distances),
                    block.residual,
                    side_changed=flipped,
                )
            )
            continue
        expected: Side = origin.footprint.side if not flipped else _other(origin.footprint.side)
        mirror = expected != before.side
        pairs = list(numbered[ref])
        rough = _fit(pairs, transform, tolerance, reverse=False, mirror=mirror)
        pairs += _by_net(
            part,
            origin,
            pairs,
            nets,
            image=rough.transform if rough is not None else None,
            goal=transform,
            tolerance=tolerance,
        )
        if not pairs:
            issues.append(
                issue(
                    "reuse.no-fit",
                    f"{ref} has no pad that pairs with one of {source} by a number found once in both or by "
                    "its net; it stays",
                    where=ref,
                    hint="map it to a reference part of the same footprint with --map",
                )
            )
            fits.append(PartFit(ref, source, part.footprint.id, origin.footprint.id, before, None, (), None))
            continue
        rigid = fit_rigid(
            [(mine.position, transform.apply(theirs_.position)) for mine, theirs_, _ in pairs],
            tolerance=tolerance,
            mirror=mirror,
        )
        matches = _matches(pairs, transform, rigid.distances)
        if rigid.residual > tolerance:
            issues.append(
                issue(
                    "reuse.no-fit",
                    f"{ref} does not fit {source}: {rigid.within(tolerance)} of its {len(pairs)} paired "
                    f"pads lie within {tolerance} nm, the farthest {rigid.residual} nm away; it stays",
                    where=ref,
                    hint="compare the footprints with fenolite pads; raise --tolerance only for a known "
                    "small difference",
                )
            )
            fits.append(
                PartFit(
                    ref, source, part.footprint.id, origin.footprint.id, before, None, matches, rigid.residual
                )
            )
            continue
        placement = moved_placement(rigid.transform, before)
        suspected = placement.side != expected
        if suspected:
            issues.append(
                issue(
                    "reuse.mirror-suspected",
                    f"{ref} fits {source} only on the {placement.side} side, while the block puts "
                    f"{source}'s side on the {expected} side: one of the two footprints may be mirrored",
                    where=ref,
                    hint="compare the two footprints with fenolite pads before routing",
                )
            )
        fits.append(
            PartFit(
                ref,
                source,
                part.footprint.id,
                origin.footprint.id,
                before,
                placement,
                matches,
                rigid.residual,
                side_changed=placement.side != origin.footprint.side,
                mirror_suspected=suspected,
            )
        )
    return tuple(fits), issues


def _fit(
    pairs: Sequence[_Pair], transform: Transform | None, tolerance: Nm, *, reverse: bool, mirror: bool
) -> Rigid | None:
    """The fit by number of a part, ``None`` without a pair or beyond the tolerance: reference pads onto
    the part's pads (``reverse``, the anchor), or the part's pads onto the ``transform`` of the reference
    pads."""
    if not pairs:
        return None
    if reverse:
        points = [(theirs.position, mine.position) for mine, theirs, _ in pairs]
    else:
        assert transform is not None
        points = [(mine.position, transform.apply(theirs.position)) for mine, theirs, _ in pairs]
    rigid = fit_rigid(points, tolerance=tolerance, mirror=mirror)
    return rigid if rigid.residual <= tolerance else None


def _matches(pairs: Sequence[_Pair], transform: Transform, distances: Sequence[Nm]) -> tuple[PadMatch, ...]:
    """The matches of the pairs, the goals the ``transform`` of the reference pads."""
    return tuple(
        PadMatch(
            mine.number,
            theirs.position,
            transform.apply(theirs.position),
            distance,
            mine.pad_id,
            theirs.pad_id,
            mine.net_id,
            theirs.net_id,
            by,
        )
        for (mine, theirs, by), distance in zip(pairs, distances, strict=True)
    )


def _other(side: Side) -> Side:
    return "bottom" if side == "top" else "top"


__all__ = [
    "DEFAULT_TOLERANCE",
    "BlockFit",
    "Layout",
    "PadMatch",
    "PartFit",
    "Placement",
    "Rigid",
    "fit_block",
    "fit_rigid",
    "moved_placement",
    "placement_transform",
]
