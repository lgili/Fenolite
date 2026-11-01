# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The strict rule of level 5: the copper of two boards item by item (capability design-equivalence,
"Level 5 strict compares copper items" and "Level 5 strict matching"; ``docs/equivalence.md``).

The rule of ``routing.py`` compares what the copper of a net joins; this second rule table compares the
tracks, arcs and vias themselves. Each kind is matched as a multiset by its copper span and geometry: a
track by its two ends as an unordered pair, an arc by its ends (ordered) and its mid, a via by its position.
Equal keys match first; then each unmatched item of side ``a``, in key order, takes the first unmatched item
of side ``b`` whose every coordinate lies within the length tolerance. Matched items compare their width,
drill, diameter, span, type, net name and lock, in the order of ``STRICT_RULE``.

A track cut into two segments is two differences on purpose: a conversion must write the segments the
original holds. Copper spans are named as level 5 names them (``top``, ``inner<k>``, ``bottom``), so boards
whose layers carry other names compare. Integer arithmetic only.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from fenolite.checks.equivalence import norm
from fenolite.checks.equivalence.model import EXACT, KINDS, Difference, Tolerances
from fenolite.checks.equivalence.routing import NetPairing, span_names
from fenolite.core.coords import Point
from fenolite.model.board import Board
from fenolite.model.design import Design

LEVEL = 5
_FIELD = {kind: name for level, kind, name in KINDS if level == LEVEL}
SPAN_ORDER_INNER = "inner"


@dataclass(frozen=True, slots=True)
class Item:
    """One copper item as the strict rule sees it: its kind (``track``, ``arc`` or ``via``), its copper span
    (one span for a track or an arc, ``<first>-<last>`` for a via), its key points (a track's ends sorted, an
    arc's ends sorted around its mid, a via's position), its net id and name, and the values compared."""

    kind: str
    span: str
    points: tuple[Point, ...]
    net: str | None
    net_name: str
    width: int = 0
    diameter: int = 0
    drill: int = 0
    via_type: str = ""
    locked: bool = False

    @property
    def key(self) -> tuple[str, tuple[tuple[int, int], ...]]:
        return (self.span, tuple((p.x, p.y) for p in self.points))

    def where(self) -> str:
        points = "-".join(f"{p.x},{p.y}" for p in self.points)
        return f"{self.net_name}:{self.kind}:{self.span}:{points}"


def _sorted_ends(a: Point, b: Point) -> tuple[Point, Point]:
    return (a, b) if (a.x, a.y) <= (b.x, b.y) else (b, a)


def _rank(name: str) -> tuple[int, int]:
    if name == "top":
        return (0, 0)
    if name.startswith(SPAN_ORDER_INNER) and name[len(SPAN_ORDER_INNER) :].isdigit():
        return (1, int(name[len(SPAN_ORDER_INNER) :]))
    return (2, 0) if name == "bottom" else (3, 0)


def _via_span(board: Board, layers: Sequence[str], through: bool, spans: Mapping[str, str]) -> str:
    """The copper span of a via, ``<first>-<last>`` top first: every copper layer for a through via or for
    layers the board does not declare, else its two layers."""
    if not spans:
        return "-".join(layers)
    if through or len(layers) != 2 or layers[0] not in spans or layers[1] not in spans:
        ordered = sorted(spans.values(), key=_rank)
        return f"{ordered[0]}-{ordered[-1]}"
    first, last = sorted((spans[layers[0]], spans[layers[1]]), key=_rank)
    return f"{first}-{last}"


def items(design: Design) -> dict[str, list[Item]]:
    """The tracks, arcs and vias of ``design.board`` as strict items, by kind, each list in key order."""
    board = design.board
    found: dict[str, list[Item]] = {"track": [], "arc": [], "via": []}
    if board is None:
        return found
    spans = span_names(board)
    names = {net.id: net.name for net in design.circuit.nets}

    def named(net: str | None) -> str:
        return names.get(net, net) if net is not None else ""

    for track in board.tracks:
        found["track"].append(
            Item(
                "track",
                spans.get(track.layer, track.layer),
                _sorted_ends(track.start, track.end),
                track.net_id,
                named(track.net_id),
                width=track.width,
                locked=track.locked,
            )
        )
    for arc in board.arcs:
        start, end = _sorted_ends(arc.start, arc.end)
        found["arc"].append(
            Item(
                "arc",
                spans.get(arc.layer, arc.layer),
                (start, arc.mid, end),
                arc.net_id,
                named(arc.net_id),
                width=arc.width,
                locked=arc.locked,
            )
        )
    for via in board.vias:
        found["via"].append(
            Item(
                "via",
                _via_span(board, via.layers, via.via_type == "through", spans),
                (via.position,),
                via.net_id,
                named(via.net_id),
                diameter=via.diameter,
                drill=via.drill,
                via_type=via.via_type,
                locked=via.locked,
            )
        )
    for held in found.values():
        held.sort(key=lambda item: (item.key, item.net_name))
    return found


def _near(one: Item, other: Item, tolerances: Tolerances) -> bool:
    """Whether two items of one kind lie within the length tolerance on every coordinate (a track's ends
    either way round, an arc's ends either way round with the same mid). A via's span is compared after
    matching; a track's or an arc's span is part of its key."""
    if one.kind != "via" and one.span != other.span:
        return False
    if len(one.points) != len(other.points):
        return False

    def within(p: Sequence[Point], q: Sequence[Point]) -> bool:
        return all(norm.points_equal(a, b, tolerances) for a, b in zip(p, q, strict=True))

    if within(one.points, other.points):
        return True
    return len(one.points) > 1 and within(one.points, tuple(reversed(other.points)))


def match(
    a: Sequence[Item], b: Sequence[Item], tolerances: Tolerances
) -> tuple[list[tuple[Item, Item]], list[Item], list[Item]]:
    """The matched pairs, then the items of ``a`` and of ``b`` left unmatched: equal keys first (as a
    multiset, in key order), then each unmatched item of ``a`` with the first unmatched item of ``b`` within
    the tolerance. A via's key is its position; a track's or an arc's its span and points."""

    def key(item: Item) -> tuple[object, ...]:
        return item.key[1:] if item.kind == "via" else item.key

    waiting: dict[tuple[object, ...], list[int]] = defaultdict(list)
    for index, item in enumerate(b):
        waiting[key(item)].append(index)
    taken = [False] * len(b)
    pairs: list[tuple[Item, Item]] = []
    left: list[Item] = []
    for item in a:
        found = waiting.get(key(item))
        if found:
            index = found.pop(0)
            taken[index] = True
            pairs.append((item, b[index]))
        else:
            left.append(item)
    only_a: list[Item] = []
    if tolerances.length_nm:
        for item in left:
            index = next(
                (k for k, other in enumerate(b) if not taken[k] and _near(item, other, tolerances)), None
            )
            if index is None:
                only_a.append(item)
            else:
                taken[index] = True
                pairs.append((item, b[index]))
    else:
        only_a = left
    only_b = [item for k, item in enumerate(b) if not taken[k]]
    return pairs, only_a, only_b


# --- the strict rule -------------------------------------------------------------------------------
#
# This block is the whole definition of the strict rule: which fields of a matched pair are compared, in
# which order, and the kind each difference gets. A finding is ``(value on a, value on b)``.

Pair = tuple[Item, Item]
Judge = Callable[[Item, Item, Tolerances, Mapping[str, str]], tuple[str, str] | None]


def _width(
    one: Item, other: Item, tolerances: Tolerances, paired: Mapping[str, str]
) -> tuple[str, str] | None:
    return (
        None if norm.lengths_equal(one.width, other.width, tolerances) else (str(one.width), str(other.width))
    )


def _net(one: Item, other: Item, tolerances: Tolerances, paired: Mapping[str, str]) -> tuple[str, str] | None:
    """Two nets are the same when level 2 pairs them; a net that level 2 does not pair compares by name."""
    if one.net is not None and one.net in paired:
        same = paired[one.net] == other.net
    elif other.net is not None and other.net in paired.values():
        same = False
    else:
        same = one.net_name == other.net_name
    return None if same else (one.net_name, other.net_name)


def _diameter(
    one: Item, other: Item, tolerances: Tolerances, paired: Mapping[str, str]
) -> tuple[str, str] | None:
    if norm.lengths_equal(one.diameter, other.diameter, tolerances):
        return None
    return (str(one.diameter), str(other.diameter))


def _drill(
    one: Item, other: Item, tolerances: Tolerances, paired: Mapping[str, str]
) -> tuple[str, str] | None:
    return (
        None if norm.lengths_equal(one.drill, other.drill, tolerances) else (str(one.drill), str(other.drill))
    )


def _span(
    one: Item, other: Item, tolerances: Tolerances, paired: Mapping[str, str]
) -> tuple[str, str] | None:
    if (one.span, one.via_type) == (other.span, other.via_type):
        return None
    return (f"{one.span}/{one.via_type}", f"{other.span}/{other.via_type}")


def _locked(
    one: Item, other: Item, tolerances: Tolerances, paired: Mapping[str, str]
) -> tuple[str, str] | None:
    if one.locked == other.locked:
        return None
    return ("true" if one.locked else "false", "true" if other.locked else "false")


STRICT_RULE: Mapping[str, tuple[tuple[str, Judge], ...]] = {
    "track": (("track-width", _width), ("track-net", _net), ("copper-locked", _locked)),
    "arc": (("arc-width", _width), ("arc-net", _net), ("copper-locked", _locked)),
    "via": (
        ("via-size", _diameter),
        ("via-drill", _drill),
        ("via-span", _span),
        ("via-net", _net),
        ("copper-locked", _locked),
    ),
}
"""Per kind of item, the steps of the comparison of a matched pair, in order."""
NOTICES = frozenset({"copper-locked"})
"""The kinds of the strict rule that are reported and never make two designs unequal."""

# --- end of the rule -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StrictResult:
    """The differences and notices of the strict rule, each in ``(where, kind, field)`` order, and its
    counts per kind: matched pairs and the items each side holds alone."""

    differences: tuple[Difference, ...]
    notices: tuple[Difference, ...]
    summary: Mapping[str, Mapping[str, int]]

    @property
    def compared(self) -> int:
        return sum(counts["matched"] for counts in self.summary.values())


def _ordered(found: Sequence[Difference]) -> tuple[Difference, ...]:
    return tuple(sorted(found, key=lambda d: (d.where, d.kind, d.field, d.a, d.b)))


def compare_strict(a: Design, b: Design, pairing: NetPairing, tolerances: Tolerances = EXACT) -> StrictResult:
    """The strict rule over the boards of ``a`` and ``b``: every track, arc and via matched and compared."""
    items_a, items_b = items(a), items(b)
    paired = dict(pairing.pairs)
    differences: list[Difference] = []
    notices: list[Difference] = []
    summary: dict[str, dict[str, int]] = {}
    for kind in ("track", "arc", "via"):
        pairs, only_a, only_b = match(items_a[kind], items_b[kind], tolerances)
        missing = f"{kind}-missing"
        for item in only_a:
            differences.append(Difference(LEVEL, missing, item.where(), _FIELD[missing], item.where(), ""))
        for item in only_b:
            differences.append(Difference(LEVEL, missing, item.where(), _FIELD[missing], "", item.where()))
        for one, other in pairs:
            for name, judge in STRICT_RULE[kind]:
                found = judge(one, other, tolerances, paired)
                if found is not None:
                    difference = Difference(LEVEL, name, one.where(), _FIELD[name], *found)
                    (notices if name in NOTICES else differences).append(difference)
        summary[f"{kind}s"] = {"matched": len(pairs), "a": len(only_a), "b": len(only_b)}
    return StrictResult(_ordered(differences), _ordered(notices), summary)


__all__ = ["NOTICES", "STRICT_RULE", "Item", "StrictResult", "compare_strict", "items", "match"]
