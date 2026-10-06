# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The levels of a design comparison (capability design-equivalence).

Level 1 pairs components by reference, level 2 compares the net-to-pin assignments as partitions of
``REF-PIN`` elements (the comparison of ``checks.assignment_compare``), level 3 compares footprints and
pads in the footprint's own frame, level 4 adds the placement, and level 5 the routing of each net
(``routing.py``). A component that a level reports as
missing or ambiguous takes no part in the later levels, so each fault is reported once. The comparison is
pure: it reads no file and runs no tool.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from fnmatch import fnmatchcase

from fenolite.backends.base import PadAssignment, PadNetList
from fenolite.checks import assignment_compare
from fenolite.checks.equivalence import norm
from fenolite.checks.equivalence.exclusions import Rule, apply_rules
from fenolite.checks.equivalence.model import (
    EXACT,
    KINDS,
    LEVELS,
    Difference,
    EquivalenceReport,
    Frame,
    LevelResult,
    Tolerances,
)
from fenolite.checks.equivalence.routing import has_copper, level_routing, pair_nets
from fenolite.core.coords import Point
from fenolite.model.board import Board, FootprintInstance, Pad
from fenolite.model.circuit import Component
from fenolite.model.design import Design

FootprintPair = tuple[str, FootprintInstance, FootprintInstance]
"""A reference and its footprint on each side."""
_FIELD = {(level, kind): field for level, kind, field in KINDS}


def _difference(level: int, kind: str, where: str, a: str, b: str) -> Difference:
    return Difference(level, kind, where, _FIELD[level, kind], a, b)


def _ordered(differences: Sequence[Difference]) -> tuple[Difference, ...]:
    return tuple(sorted(differences, key=lambda d: (d.where, d.kind, d.field, d.a, d.b)))


def _point(point: Point) -> str:
    return f"{point.x},{point.y}"


def _flag(value: bool) -> str:
    return "true" if value else "false"


# --- level 1 ---------------------------------------------------------------------------------------


def _by_ref(design: Design, ignore_refs: Sequence[str]) -> tuple[dict[str, list[Component]], set[str]]:
    found: dict[str, list[Component]] = defaultdict(list)
    ignored: set[str] = set()
    for component in design.circuit.components:
        if any(fnmatchcase(component.ref, glob) for glob in ignore_refs):
            ignored.add(component.ref)
        else:
            found[component.ref].append(component)
    return found, ignored


def level_components(
    a: Design, b: Design, *, ignore_refs: Sequence[str] = ()
) -> tuple[LevelResult, tuple[str, ...]]:
    """Level 1, and the references both sides hold exactly once (the components the later levels
    compare), sorted."""
    held_a, ignored_a = _by_ref(a, ignore_refs)
    held_b, ignored_b = _by_ref(b, ignore_refs)
    differences: list[Difference] = []
    compared: list[str] = []
    for ref in sorted(set(held_a) | set(held_b)):
        count_a, count_b = len(held_a.get(ref, ())), len(held_b.get(ref, ()))
        if not ref or count_a > 1 or count_b > 1:
            differences.append(_difference(1, "ref-ambiguous", ref, str(count_a), str(count_b)))
        elif count_a != count_b:
            differences.append(
                _difference(1, "component-missing", ref, ref if count_a else "", ref if count_b else "")
            )
        else:
            one, other = held_a[ref][0], held_b[ref][0]
            compared.append(ref)
            if one.value != other.value:
                differences.append(_difference(1, "value", ref, one.value, other.value))
            if one.dnp != other.dnp:
                differences.append(_difference(1, "dnp", ref, _flag(one.dnp), _flag(other.dnp)))
    summary = {
        "components": {"a": len(a.circuit.components), "b": len(b.circuit.components)},
        "ignored": len(ignored_a | ignored_b),
    }
    return LevelResult(1, len(compared), _ordered(differences), (), summary), tuple(compared)


# --- level 2 ---------------------------------------------------------------------------------------


def _has_footprints(design: Design) -> bool:
    return design.board is not None and bool(design.board.footprints)


Parts = dict[str, tuple[str, str]]
"""Each element ``REF-PIN`` with its reference and its pin."""


UNCONNECTED = "unconnected-("
"""The start of the name KiCad gives the net of a pin on no net (``docs/formats/kicad/schematic.md``)."""


def _elements(design: Design, refs: frozenset[str]) -> tuple[str, PadNetList, int, Parts]:
    """The netlist source of a side (``board`` or ``circuit``), its assignments cut down to the elements
    of ``refs``, the count of unnumbered pads, and each element's reference and pin."""
    parts: Parts = {}
    by_id = {c.id: c.ref for c in design.circuit.components}
    if _has_footprints(design):
        assert design.board is not None
        source = "board"
        listed, unnumbered = assignment_compare.board_netlist(design)
        for footprint in design.board.footprints:
            ref = by_id.get(footprint.component_id, "")
            for pad in footprint.pads:
                if pad.number and ref in refs:
                    parts[f"{ref}-{pad.number}"] = (ref, pad.number)
    else:
        source = "circuit"
        listed, unnumbered = assignment_compare.model_netlist(design), 0
        # an element names the pad of its pin, as ``model_netlist`` does (``Component.pin_pad_map``)
        pads = {c.id: dict(c.pin_pad_map) for c in design.circuit.components}
        for net in design.circuit.nets:
            for member in net.members:
                ref = by_id.get(member.component_id, "")
                if ref in refs:
                    pad = pads.get(member.component_id, {}).get(member.pin, member.pin)
                    parts[f"{ref}-{pad}"] = (ref, pad)
        for component in design.circuit.components:
            for pin in component.pins:
                if pin.number and component.ref in refs:
                    pad = pads[component.id].get(pin.number, pin.number)
                    parts[f"{component.ref}-{pad}"] = (component.ref, pad)
    # KiCad gives each pin on no net a net of its own, ``unconnected-(…)``, and a board built beside a
    # schematic carries those names on its pads (c0061): such a net with one pad is a pad on no net.
    names = assignment_compare.net_names(design)
    held = Counter(item.net for item in listed.assignments)
    open_nets = {
        net for net, count in held.items() if count == 1 and names.get(net, "").startswith(UNCONNECTED)
    }
    kept = tuple(
        PadAssignment(item.element, assignment_compare.NO_NET) if item.net in open_nets else item
        for item in listed.assignments
        if item.element in parts
    )
    return source, PadNetList(listed.source, kept), unnumbered, parts


def _renamed(
    one: PadNetList, other: PadNetList, common: frozenset[str], names_a: Mapping[str, str],
    names_b: Mapping[str, str],
) -> int:  # fmt: skip
    """The count of blocks that hold the same elements on both sides under different net names."""

    def blocks(listed: PadNetList) -> dict[frozenset[str], str]:
        members: dict[str, set[str]] = defaultdict(set)
        for item in listed.assignments:
            if item.element in common:
                members[item.net].add(item.element)
        return {frozenset(found): label for label, found in members.items()}

    blocks_a, blocks_b = blocks(one), blocks(other)
    return sum(
        1
        for block, label in blocks_a.items()
        if block in blocks_b
        and assignment_compare.net_text(label, names_a)
        != assignment_compare.net_text(blocks_b[block], names_b)
    )


def level_netlist(a: Design, b: Design, refs: Sequence[str]) -> LevelResult:
    """Level 2 over the components ``refs`` that level 1 compared. Net names are never compared."""
    wanted = frozenset(refs)
    source_a, listed_a, unnumbered_a, parts_a = _elements(a, wanted)
    source_b, listed_b, unnumbered_b, parts_b = _elements(b, wanted)
    pair = assignment_compare.compare(
        replace(listed_a, source="a"), replace(listed_b, source="b"), min_pins=1, joined_no_net=True
    )
    names_a, names_b = assignment_compare.net_names(a), assignment_compare.net_names(b)
    differences: list[Difference] = []
    for lone in pair.only_a:
        differences.append(_difference(2, "pin-missing", lone.element, parts_a[lone.element][1], ""))
    for lone in pair.only_b:
        differences.append(_difference(2, "pin-missing", lone.element, "", parts_b[lone.element][1]))
    for found in pair.differences:
        differences.append(
            _difference(
                2,
                "net",
                found.element,
                assignment_compare.net_text(found.net_a, names_a),
                assignment_compare.net_text(found.net_b, names_b),
            )
        )
    common = frozenset(parts_a) & frozenset(parts_b)
    summary = {
        "sources": {"a": source_a, "b": source_b},
        "unnumbered": {"a": unnumbered_a, "b": unnumbered_b},
        "renamed": _renamed(listed_a, listed_b, common, names_a, names_b),
    }
    return LevelResult(2, pair.common, _ordered(differences), (), summary)


# --- level 3 ---------------------------------------------------------------------------------------


def _placed(design: Design) -> dict[str, FootprintInstance]:
    """The footprint of each reference: the first by position when a component holds several."""
    by_id = {c.id: c.ref for c in design.circuit.components}
    found: dict[str, FootprintInstance] = {}
    board = design.board
    for footprint in sorted(
        board.footprints if board is not None else (), key=lambda f: (f.position.x, f.position.y, f.id)
    ):
        found.setdefault(by_id.get(footprint.component_id, ""), footprint)
    return found


def _pad_where(ref: str, pad: Pad) -> str:
    return f"{ref}-{pad.number}" if pad.number else f"{ref}-@{pad.position.x},{pad.position.y}"


def _pad_differences(
    where: str, one: Pad, other: Pad, board_a: Board, board_b: Board, tolerances: Tolerances
) -> tuple[list[Difference], bool]:
    """The differences of one pad pair, and whether its copper span is unknown on a side."""
    found: list[Difference] = []
    if one.kind != other.kind:
        found.append(_difference(3, "pad-kind", where, one.kind, other.kind))
    if one.shape != other.shape:
        found.append(_difference(3, "pad-shape", where, one.shape, other.shape))
    turned = norm.pads_equal_turned(one, other, tolerances)
    if not turned and not norm.sizes_equal(one.size, other.size, tolerances):
        found.append(
            _difference(3, "pad-size", where, f"{one.size.w}x{one.size.h}", f"{other.size.w}x{other.size.h}")
        )
    if (one.drill is None) != (other.drill is None) or (
        one.drill is not None
        and other.drill is not None
        and not norm.lengths_equal(one.drill, other.drill, tolerances)
    ):
        found.append(
            _difference(
                3,
                "pad-drill",
                where,
                "" if one.drill is None else str(one.drill),
                "" if other.drill is None else str(other.drill),
            )
        )
    if not norm.points_equal(one.position, other.position, tolerances):
        found.append(_difference(3, "pad-position", where, _point(one.position), _point(other.position)))
    period_a, period_b = norm.pad_symmetry(one, tolerances), norm.pad_symmetry(other, tolerances)
    if not turned and period_a is not None and period_b is not None:
        if not norm.angles_equal(one.rotation, other.rotation, tolerances, min(period_a, period_b)):
            found.append(_difference(3, "pad-rotation", where, str(one.rotation), str(other.rotation)))
    span_a, span_b = norm.copper_span(one, board_a), norm.copper_span(other, board_b)
    unknown = span_a is None or span_b is None
    if span_a is not None and span_b is not None and span_a != span_b:
        found.append(_difference(3, "pad-copper", where, norm.span_text(span_a), norm.span_text(span_b)))
    return found, unknown


def _grouped(footprint: FootprintInstance) -> dict[str, list[Pad]]:
    groups: dict[str, list[Pad]] = defaultdict(list)
    for pad in footprint.pads:
        groups[pad.number].append(pad)
    for pads in groups.values():
        pads.sort(key=lambda p: (p.position.x, p.position.y))
    return groups


def level_footprints(
    a: Design, b: Design, refs: Sequence[str], tolerances: Tolerances = EXACT
) -> tuple[LevelResult, tuple[FootprintPair, ...]]:
    """Level 3 over the components ``refs``, and the footprint pairs it compared (those of level 4)."""
    assert a.board is not None and b.board is not None
    placed_a, placed_b = _placed(a), _placed(b)
    differences: list[Difference] = []
    pairs: list[FootprintPair] = []
    compared = 0
    unknown = 0
    for ref in refs:
        one, other = placed_a.get(ref), placed_b.get(ref)
        if one is None and other is None:
            continue
        if one is None or other is None:
            differences.append(
                _difference(
                    3,
                    "footprint-missing",
                    ref,
                    "" if one is None else norm.footprint_name(one.lib_ref),
                    "" if other is None else norm.footprint_name(other.lib_ref),
                )
            )
            continue
        pairs.append((ref, one, other))
        name_a, name_b = norm.footprint_name(one.lib_ref), norm.footprint_name(other.lib_ref)
        if name_a != name_b:
            differences.append(_difference(3, "footprint-name", ref, name_a, name_b))
        groups_a, groups_b = _grouped(one), _grouped(other)
        for number in sorted(set(groups_a) | set(groups_b)):
            pads_a, pads_b = groups_a.get(number, []), groups_b.get(number, [])
            if len(pads_a) != len(pads_b):
                differences.append(
                    _difference(3, "pad-missing", f"{ref}-{number}", str(len(pads_a)), str(len(pads_b)))
                )
                continue
            for pad_a, pad_b in zip(pads_a, pads_b, strict=True):
                found, no_span = _pad_differences(
                    _pad_where(ref, pad_a), pad_a, pad_b, a.board, b.board, tolerances
                )
                differences += found
                unknown += no_span
                compared += 1
    summary = {"footprints": len(pairs), "copper_unknown": unknown}
    return LevelResult(3, compared, _ordered(differences), (), summary), tuple(pairs)


# --- level 4 ---------------------------------------------------------------------------------------


def level_placement(
    pairs: Sequence[FootprintPair], tolerances: Tolerances = EXACT, frame: Frame = "absolute"
) -> tuple[LevelResult, Point]:
    """Level 4 over the footprint pairs of level 3, and the translation removed from side ``b``."""
    shift = Point(0, 0)
    if frame == "relative":
        shift = norm.translation((one.position, other.position) for _, one, other in pairs)
    differences: list[Difference] = []
    for ref, one, other in pairs:
        if one.side != other.side:
            differences.append(_difference(4, "side", ref, one.side, other.side))
        moved = Point(other.position.x - shift.x, other.position.y - shift.y)
        if not norm.points_equal(one.position, moved, tolerances):
            differences.append(_difference(4, "position", ref, _point(one.position), _point(other.position)))
        if not norm.angles_equal(one.rotation, other.rotation, tolerances):
            differences.append(_difference(4, "rotation", ref, str(one.rotation), str(other.rotation)))
    summary = {"frame": frame, "translation": [shift.x, shift.y]}
    return LevelResult(4, len(pairs), _ordered(differences), (), summary), shift


# --- all levels ------------------------------------------------------------------------------------


def max_level(a: Design, b: Design) -> int:
    """5 when both designs hold a board with at least one footprint and at least one track, arc or via, 4
    when both hold a board with at least one footprint, else 2."""
    if not (_has_footprints(a) and _has_footprints(b)):
        return 2
    return 5 if has_copper(a) and has_copper(b) else 4


def compare_designs(
    a: Design,
    b: Design,
    *,
    level: int,
    tolerances: Tolerances = EXACT,
    frame: Frame = "absolute",
    ignore_refs: Sequence[str] = (),
    rules: Sequence[Rule] = (),
) -> EquivalenceReport:
    """Run the levels 1 to ``level`` in order and apply ``rules`` to each. ``ValueError`` for a level
    outside ``LEVELS``, or above what both sides hold (the message names the side without footprints, or
    without copper when only level 5 is out of reach)."""
    if type(level) is not int or level not in LEVELS:
        raise ValueError(f"level is one of {', '.join(map(str, LEVELS))}, got {level!r}")
    highest = max_level(a, b)
    if level > highest:
        held, needs = (
            (_has_footprints, "footprints") if highest < 4 else (has_copper, "a track, an arc or a via")
        )
        bare = " and ".join(name for name, side in (("a", a), ("b", b)) if not held(side))
        raise ValueError(
            f"level {level} needs {needs} on both sides, and side {bare} holds none; "
            f"the highest level available is {highest}"
        )
    first, refs = level_components(a, b, ignore_refs=ignore_refs)
    results = [first]
    shift = Point(0, 0)
    if level >= 2:
        results.append(level_netlist(a, b, refs))
    if level >= 3:
        third, pairs = level_footprints(a, b, refs, tolerances)
        results.append(third)
        if level >= 4:
            fourth, shift = level_placement(pairs, tolerances, frame)
            results.append(fourth)
        if level >= 5:
            results.append(level_routing(a, b, pair_nets(a, b, refs), tolerances))
    return EquivalenceReport(
        levels=tuple(apply_rules(result, rules) for result in results),
        tolerances=tolerances,
        frame=frame,
        translation=shift,
    )


__all__ = [
    "KINDS",
    "FootprintPair",
    "compare_designs",
    "level_components",
    "level_footprints",
    "level_netlist",
    "level_placement",
    "level_routing",
    "max_level",
]
