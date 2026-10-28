# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where the designators go: candidates around each part, their cost, and the search (capability
silkscreen-layout, "Designator placement"; change c0212; user guide ``docs/assembly.md``, "Designators").

Everything here is board-frame geometry in integer nanometres, Y down. A text is the rectangle of its ink
(``Rect``); an obstacle is a ``Thick`` shape that a text must stay ``clearance`` away from. The module
knows nothing of KiCad: ``silk.board`` gathers the parts, the inks and the obstacles of a board.

- **Candidates.** For each allowed angle and size, twelve places beside the box of the part's own
  courtyard, ``gap`` away from it: centred above, below, left and right, then flush with either end of
  each side. Identical parts get identical candidates relative to their boxes (the same ``slot``).
- **Cost.** Grows with the distance to the own box and with the offset from its middle, with nearness to
  a foreign part (a text nearer to another part than to its own costs ``FOREIGN_COST`` more), with an
  angle other than the part's axis (``ANGLE_COST``) and with a size below the largest allowed.
- **Search.** Groups of identical parts in a row or a column first, each on one common slot when every
  member is free there; then the other parts greedily, the most constrained first; then repair rounds in
  which a part without a free candidate may push one placed text to that text's next free candidate.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from math import isqrt
from typing import Any

from fenolite.core.coords import Point
from fenolite.core.units import Nm, Udeg
from fenolite.geometry import BBox, SpatialIndex, Thick, thick_bbox, thick_closer_than

ANGLE_COST: Nm = 500_000
"""What a text across the part's axis costs, as a length (a Fenolite choice)."""
FOREIGN_COST: Nm = 10_000_000
"""What a text nearer to another part than to its own costs (a Fenolite choice)."""
NEAR: Nm = 300_000
"""A foreign part closer than the own one plus this adds to the cost."""
REPAIR_ROUNDS = 4
SortKey = Callable[[str], tuple[Any, ...]]
"""How references sort (``silk.board.natural`` puts ``R2`` before ``R10``)."""
SIDES = ("above", "below", "left", "right")


@dataclass(frozen=True, slots=True, order=True)
class Rect:
    """A closed axis-aligned box, ``x0 <= x1`` and ``y0 <= y1``."""

    x0: Nm
    y0: Nm
    x1: Nm
    y1: Nm

    def moved(self, dx: Nm, dy: Nm) -> Rect:
        return Rect(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy)

    def bbox(self, grow: Nm = 0) -> BBox:
        return BBox(self.x0 - grow, self.y0 - grow, self.x1 + grow, self.y1 + grow)

    def thick(self) -> Thick:
        """The rectangle as a filled shape (a segment or a point when it has no area)."""
        a, b = Point(self.x0, self.y0), Point(self.x1, self.y1)
        if self.x0 == self.x1 or self.y0 == self.y1:
            return Thick((a,) if a == b else (a, b), 0 if a != b else 1)
        return Thick((a, Point(self.x1, self.y0), b, Point(self.x0, self.y1)), 0, filled=True)

    @property
    def centre2(self) -> Point:
        """Twice the centre (exact)."""
        return Point(self.x0 + self.x1, self.y0 + self.y1)


def gap2(a: Rect, b: Rect) -> int:
    """The square of the distance between two rectangles (0 when they touch or overlap)."""
    dx = max(0, a.x0 - b.x1, b.x0 - a.x1)
    dy = max(0, a.y0 - b.y1, b.y0 - a.y1)
    return dx * dx + dy * dy


def gap_floor(a: Rect, b: Rect) -> Nm:
    """The distance between two rectangles, rounded down."""
    return isqrt(gap2(a, b))


@dataclass(frozen=True, slots=True)
class Obstacle:
    """A shape a text must keep ``clearance`` from; ``what`` names it in a finding. An obstacle with an
    ``owner`` (a part key: its courtyard) does not stand in the way of that part's own text."""

    shape: Thick
    box: BBox
    what: str
    owner: str = ""

    @classmethod
    def of(cls, shape: Thick, what: str, owner: str = "") -> Obstacle:
        return cls(shape, thick_bbox(shape), what, owner)


@dataclass(frozen=True, slots=True)
class Look:
    """One way a text may look: its board angle (0 or 90 degrees), glyph size, stroke, and the rectangle of
    its ink relative to its anchor in the board frame."""

    angle: Udeg
    width: Nm
    height: Nm
    stroke: Nm
    ink: Rect


@dataclass(frozen=True, slots=True)
class Choice:
    """A place for a text: its anchor, how it looks, its ink rectangle on the board, its cost, and its
    ``slot`` (side, offset, look), equal for identical parts."""

    anchor: Point
    look: Look
    rect: Rect
    cost: int
    slot: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class Part:
    """A part whose designator is placed: ``key`` (the footprint id), its reference, its silkscreen side,
    the box of its own courtyard, its axis angle, the looks to try (largest size first), its text as it
    is when ``--keep`` may keep it (``current``), and where that text lies (``held``: its side and
    rectangle), which stays in the way of the others when the part gets no new place."""

    key: str
    ref: str
    side: str
    box: Rect
    axis: Udeg
    looks: tuple[Look, ...]
    current: Choice | None = None
    held: tuple[str, Rect] | None = None


@dataclass
class Plan:
    """The outcome: the chosen place per part key, the parts left without one with what blocks them,
    the parts kept as they were (``--keep``), and the groups aligned (lists of refs)."""

    placed: dict[str, Choice] = field(default_factory=lambda: {})
    blocked: dict[str, str] = field(default_factory=lambda: {})
    kept: list[str] = field(default_factory=lambda: [])
    aligned: list[list[str]] = field(default_factory=lambda: [])


def _offsets(look: Look, box: Rect, gap: Nm) -> list[tuple[int, int, Point]]:
    """``(side, offset, anchor)`` of the twelve candidates of one look around ``box``."""
    ink = look.ink
    cx2, cy2 = box.x0 + box.x1, box.y0 + box.y1
    centred_x = (cx2 - ink.x0 - ink.x1) // 2
    centred_y = (cy2 - ink.y0 - ink.y1) // 2
    xs = (centred_x, box.x0 - ink.x0, box.x1 - ink.x1)
    ys = (centred_y, box.y0 - ink.y0, box.y1 - ink.y1)
    above, below = box.y0 - gap - ink.y1, box.y1 + gap - ink.y0
    left, right = box.x0 - gap - ink.x1, box.x1 + gap - ink.x0
    found: list[tuple[int, int, Point]] = []
    for offset in range(3):
        found.append((0, offset, Point(xs[offset], above)))
        found.append((1, offset, Point(xs[offset], below)))
        found.append((2, offset, Point(left, ys[offset])))
        found.append((3, offset, Point(right, ys[offset])))
    return found


def candidates(part: Part, foreign: Sequence[Rect], *, gap: Nm) -> tuple[Choice, ...]:
    """Every candidate of ``part``, cheapest first (ties in slot order). ``foreign`` are the boxes of the
    other parts on the same side."""
    if not part.looks:
        return ()
    largest = max(look.height for look in part.looks)
    index: SpatialIndex[Rect] | None = (
        SpatialIndex[Rect].build((rect.bbox(), rect) for rect in foreign) if foreign else None
    )
    found: list[Choice] = []
    for look_index, look in enumerate(part.looks):
        for side, offset, anchor in _offsets(look, part.box, gap):
            rect = look.ink.moved(anchor.x, anchor.y)
            own = gap_floor(rect, part.box)
            centre = rect.centre2
            shift = (
                abs(centre.x - (part.box.x0 + part.box.x1))
                if side < 2
                else abs(centre.y - (part.box.y0 + part.box.y1))
            )
            cost = own + shift // 8 + 2 * (largest - look.height)
            if look.angle != part.axis:
                cost += ANGLE_COST
            reach = own + NEAR
            near: list[Rect] = index.query(rect.bbox(reach)) if index is not None else []
            if near:
                closest = min(gap_floor(rect, other) for other in near)
                if closest < own:
                    cost += FOREIGN_COST
                if closest < reach:
                    cost += reach - closest
            found.append(Choice(anchor, look, rect, cost, (side, offset, look_index)))
    found.sort(key=lambda choice: (choice.cost, choice.slot))
    return tuple(found)


@dataclass
class Field:
    """The obstacles of one silkscreen side and the texts placed on it so far."""

    obstacles: Sequence[Obstacle]
    clearance: Nm
    inside: Callable[[Rect], bool]
    """Whether a rectangle lies in the board's material (its edges are among the obstacles)."""
    texts: dict[str, Rect] = field(default_factory=lambda: {})
    _index: SpatialIndex[Obstacle] | None = None

    def __post_init__(self) -> None:
        if self.obstacles:
            self._index = SpatialIndex[Obstacle].build((o.box, o) for o in self.obstacles)

    def static_blocker(self, rect: Rect, own: str = "") -> str | None:
        """What of the fixed obstacles is within the clearance of ``rect`` (``None``: nothing); the
        obstacles that ``own`` owns are passed over."""
        if not self.inside(rect):
            return "the board edge"
        if self._index is None:
            return None
        shape = rect.thick()
        for obstacle in self._index.query(rect.bbox(self.clearance)):
            if own and obstacle.owner == own:
                continue
            if thick_closer_than(shape, obstacle.shape, self.clearance):
                return obstacle.what
        return None

    def text_blockers(self, rect: Rect, *, skip: str = "") -> list[str]:
        """The keys of the placed texts within the clearance of ``rect``."""
        limit = self.clearance * self.clearance
        return [key for key, other in self.texts.items() if key != skip and gap2(rect, other) < limit]


def _free(field_: Field, choice: Choice, key: str) -> bool:
    """Whether the text of part ``key`` may stand at ``choice``."""
    return field_.static_blocker(choice.rect, key) is None and not field_.text_blockers(choice.rect, skip=key)


def _group_slot(
    members: Sequence[Part], options: Mapping[str, tuple[Choice, ...]], field_: Field
) -> dict[str, Choice] | None:
    """The cheapest slot that every member can take at once, or ``None``."""
    per_slot: list[dict[tuple[int, int, int], Choice]] = [
        {choice.slot: choice for choice in options[part.key]} for part in members
    ]
    common = set(per_slot[0]).intersection(*per_slot[1:])
    ranked = sorted(common, key=lambda slot: (sum(slots[slot].cost for slots in per_slot), slot))
    limit = field_.clearance * field_.clearance
    for slot in ranked:
        chosen = [slots[slot] for slots in per_slot]
        if not all(_free(field_, choice, part.key) for part, choice in zip(members, chosen, strict=True)):
            continue
        if any(gap2(a.rect, b.rect) < limit for i, a in enumerate(chosen) for b in chosen[i + 1 :]):
            continue
        return {part.key: choice for part, choice in zip(members, chosen, strict=True)}
    return None


def arrange(
    parts: Sequence[Part],
    fields: Mapping[str, Field],
    *,
    gap: Nm,
    groups: Sequence[Sequence[str]] = (),
    keep: bool = False,
    natural: SortKey = lambda text: (text,),
) -> Plan:
    """Place the designators of ``parts`` (see the module). ``fields`` maps a side to its field, whose
    ``texts`` already hold the texts that stay where they are. ``groups`` lists keys of identical parts
    in a row or a column. With ``keep``, a part whose current text is free keeps it."""
    plan = Plan()
    by_key = {part.key: part for part in parts}
    boxes: dict[str, list[tuple[str, Rect]]] = {}
    for part in parts:
        boxes.setdefault(part.side, []).append((part.key, part.box))
    options = {
        part.key: candidates(part, [box for key, box in boxes[part.side] if key != part.key], gap=gap)
        for part in parts
    }
    todo = list(parts)
    if keep:
        for part in parts:
            if part.current is not None:
                fields[part.side].texts[part.key] = part.current.rect
        for part in parts:
            here = fields[part.side]
            current = part.current
            if current is not None and _free(here, current, part.key):
                plan.kept.append(part.ref)
            else:
                here.texts.pop(part.key, None)
        kept = set(plan.kept)
        todo = [part for part in parts if part.ref not in kept]
    single = {part.key for part in todo}
    if not keep:
        for keys in sorted(groups, key=lambda g: (-len(g), [natural(by_key[k].ref) for k in g])):
            members = [by_key[key] for key in keys if key in single]
            if len(members) < 2 or len({m.side for m in members}) != 1:
                continue
            here = fields[members[0].side]
            chosen = _group_slot(members, options, here)
            if chosen is None:
                continue
            for key, choice in chosen.items():
                plan.placed[key] = choice
                here.texts[key] = choice.rect
                single.discard(key)
            plan.aligned.append(sorted((by_key[key].ref for key in chosen), key=natural))
    loose = [by_key[key] for key in single]

    def room(part: Part) -> int:
        here = fields[part.side]
        return sum(1 for choice in options[part.key] if here.static_blocker(choice.rect, part.key) is None)

    for part in sorted(loose, key=lambda p: (room(p), natural(p.ref))):
        here = fields[part.side]
        best = next((choice for choice in options[part.key] if _free(here, choice, part.key)), None)
        if best is None:
            continue
        plan.placed[part.key] = best
        here.texts[part.key] = best.rect
    movable = {part.key for part in loose}
    for _ in range(REPAIR_ROUNDS):
        moved = False
        for part in sorted(loose, key=lambda p: natural(p.ref)):
            if part.key in plan.placed:
                continue
            if _repair(part, options, fields[part.side], plan, movable):
                moved = True
        if not moved:
            break
    for part in loose:
        if part.key not in plan.placed:
            plan.blocked[part.key] = _blocker(part, options[part.key], fields[part.side], by_key)
    _settle(parts, options, fields, plan, by_key)
    return plan


def _settle(
    parts: Sequence[Part],
    options: Mapping[str, tuple[Choice, ...]],
    fields: Mapping[str, Field],
    plan: Plan,
    by_key: Mapping[str, Part],
) -> None:
    """A part left without a place keeps its text where it was: that text stands in the way of the others.
    A placed text that meets one moves to its next free candidate, or gives up its place, until no placed
    text meets a text that stays."""
    kept = set(plan.kept)
    while True:
        staying = [
            part
            for part in parts
            if part.key not in plan.placed and part.ref not in kept and part.held is not None
        ]
        for part in staying:
            assert part.held is not None
            fields[part.held[0]].texts[part.key] = part.held[1]
        clash = None
        for part in staying:
            assert part.held is not None
            side, rect = part.held
            for other in fields[side].text_blockers(rect, skip=part.key):
                if other in plan.placed:
                    clash = (other, part)
                    break
            if clash is not None:
                break
        if clash is None:
            return
        other, part = clash
        mover = by_key[other]
        here = fields[mover.side]
        del here.texts[other]
        del plan.placed[other]
        for aligned in plan.aligned:
            if mover.ref in aligned:
                aligned.remove(mover.ref)
        plan.aligned[:] = [group for group in plan.aligned if len(group) >= 2]
        moved = next((c for c in options[other] if _free(here, c, other)), None)
        if moved is not None:
            plan.placed[other] = moved
            here.texts[other] = moved.rect
        else:
            plan.blocked[other] = f"the designator of {part.ref}, which stays"


def _repair(
    part: Part, options: Mapping[str, tuple[Choice, ...]], here: Field, plan: Plan, movable: set[str]
) -> bool:
    """Place ``part`` by moving one placed text out of the way, when one free move does it."""
    for choice in options[part.key]:
        if here.static_blocker(choice.rect, part.key) is not None:
            continue
        blockers = here.text_blockers(choice.rect, skip=part.key)
        if len(blockers) != 1 or blockers[0] not in movable:
            continue
        other = blockers[0]
        held = here.texts.pop(other)
        here.texts[part.key] = choice.rect
        for alternative in options[other]:
            if alternative.rect == held:
                continue
            if _free(here, alternative, other):
                here.texts[other] = alternative.rect
                plan.placed[other] = alternative
                plan.placed[part.key] = choice
                return True
        del here.texts[part.key]
        here.texts[other] = held
    return False


def _blocker(part: Part, choices: Sequence[Choice], here: Field, by_key: Mapping[str, Part]) -> str:
    """What blocks the cheapest candidate of a part left without a place."""
    if not choices:
        return "no candidate"
    first = choices[0]
    found = here.static_blocker(first.rect, part.key)
    if found is not None:
        return found
    texts = here.text_blockers(first.rect, skip=part.key)
    if texts:
        return f"the designator of {by_key[texts[0]].ref}" if texts[0] in by_key else texts[0]
    return "no candidate"


__all__ = [
    "ANGLE_COST",
    "FOREIGN_COST",
    "NEAR",
    "Choice",
    "Field",
    "Look",
    "Obstacle",
    "Part",
    "Plan",
    "Rect",
    "arrange",
    "candidates",
    "gap2",
    "gap_floor",
]
