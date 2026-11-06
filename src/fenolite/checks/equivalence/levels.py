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

import math
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from fnmatch import fnmatchcase

from fenolite.backends.base import PadAssignment, PadNetList
from fenolite.checks import assignment_compare
from fenolite.checks.equivalence import norm
from fenolite.checks.equivalence import pairing as forms
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
from fenolite.checks.equivalence.rules import level_rules
from fenolite.checks.equivalence.shapes import level_geometry
from fenolite.checks.equivalence.strict import compare_strict
from fenolite.core.coords import Point
from fenolite.geometry.transform import rotate_point
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


SHARED_MARK = "#"
"""The separator of the number a shared reference takes when it is paired by placement (change c0277)."""


def _holders(design: Design) -> dict[str, list[Component]]:
    found: dict[str, list[Component]] = defaultdict(list)
    for component in design.circuit.components:
        found[component.ref].append(component)
    return found


def _placement_order(design: Design, holders: Sequence[Component]) -> list[Component] | None:
    """``holders`` in placement order (side, position, rotation, footprint name), or ``None`` when one of
    them has no footprint or several."""
    placed: dict[str, list[FootprintInstance]] = defaultdict(list)
    for footprint in design.board.footprints if design.board is not None else ():
        placed[footprint.component_id].append(footprint)
    keyed: list[tuple[tuple[object, ...], Component]] = []
    for component in holders:
        held = placed.get(component.id, [])
        if len(held) != 1:
            return None
        fp = held[0]
        keyed.append(
            ((fp.side, fp.position.x, fp.position.y, fp.rotation, norm.footprint_name(fp.lib_ref)), component)
        )
    return [component for _, component in sorted(keyed, key=lambda item: item[0])]


def paired_references(a: Design, b: Design, *, ignore_refs: Sequence[str] = ()) -> tuple[Design, Design]:
    """The two designs with each reference that both sides hold equally often, more than once or empty,
    numbered ``REF#1``, ``REF#2``, … in placement order on each side (change c0277: footprints that share a
    reference, such as stitching vias or logos, are paired by where they are). A reference that the sides
    hold a different number of times, that matches ``ignore_refs``, or one of whose holders is not placed
    exactly once, keeps its ``ref-ambiguous`` difference."""
    held_a, held_b = _holders(a), _holders(b)
    taken = set(held_a) | set(held_b)
    renamed_a: dict[str, str] = {}
    renamed_b: dict[str, str] = {}
    for ref in sorted(set(held_a) & set(held_b)):
        count = len(held_a[ref])
        if count != len(held_b[ref]) or (ref and count < 2):
            continue
        if any(fnmatchcase(ref, glob) for glob in ignore_refs):
            continue
        order_a, order_b = _placement_order(a, held_a[ref]), _placement_order(b, held_b[ref])
        if order_a is None or order_b is None:
            continue
        names = [f"{ref}{SHARED_MARK}{k}" for k in range(1, count + 1)]
        if taken & set(names):
            continue
        renamed_a.update((c.id, name) for c, name in zip(order_a, names, strict=True))
        renamed_b.update((c.id, name) for c, name in zip(order_b, names, strict=True))

    def renamed(design: Design, names: Mapping[str, str]) -> Design:
        if not names:
            return design
        components = tuple(
            replace(c, ref=names[c.id]) if c.id in names else c for c in design.circuit.components
        )
        return replace(design, circuit=replace(design.circuit, components=components))

    return renamed(a, renamed_a), renamed(b, renamed_b)


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
            if one.bom_only != other.bom_only:
                differences.append(
                    _difference(1, "bom-only", ref, _flag(one.bom_only), _flag(other.bom_only))
                )
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
        # an element names a pad of its pin, as ``model_netlist`` does (``Component.pads_of``)
        components = {c.id: c for c in design.circuit.components}
        for net in design.circuit.nets:
            for member in net.members:
                ref = by_id.get(member.component_id, "")
                if ref in refs:
                    owner = components.get(member.component_id)
                    for pad in owner.pads_of(member.pin) if owner is not None else (member.pin,):
                        parts[f"{ref}-{pad}"] = (ref, pad)
        for component in design.circuit.components:
            for pin in component.pins:
                if pin.number and component.ref in refs:
                    for pad in component.pads_of(pin.number):
                        parts[f"{component.ref}-{pad}"] = (component.ref, pad)
    # KiCad gives each pin on no net a net of its own, ``unconnected-(…)``, and a board built beside a
    # schematic carries those names on its pads (c0061): such a net held by one element (one pad, or the
    # pads of one number, as two shield pads ``0``; change c0281) is a pad on no net.
    names = assignment_compare.net_names(design)
    held: dict[str, set[str]] = defaultdict(set)
    for item in listed.assignments:
        held[item.net].add(item.element)
    open_nets = {
        net
        for net, elements in held.items()
        if len(elements) == 1 and names.get(net, "").startswith(UNCONNECTED)
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
    where: str,
    one: Pad,
    other: Pad,
    board_a: Board,
    board_b: Board,
    tolerances: Tolerances,
    masks: tuple[norm.MaskOf, norm.MaskOf] = (norm.own_mask, norm.own_mask),
) -> tuple[list[Difference], bool]:
    """The differences of one pad pair, and whether its copper span is unknown on a side."""
    found: list[Difference] = []
    if one.kind != other.kind:
        found.append(_difference(3, "pad-kind", where, one.kind, other.kind))
    if norm.shape_class(one, tolerances) != norm.shape_class(other, tolerances):
        found.append(_difference(3, "pad-shape", where, one.shape, other.shape))
    turned = norm.pads_equal_turned(one, other, tolerances)
    if not turned and not norm.sizes_equal(one.size, other.size, tolerances):
        found.append(
            _difference(3, "pad-size", where, f"{one.size.w}x{one.size.h}", f"{other.size.w}x{other.size.h}")
        )
    drill_a, drill_b = norm.drill_width(one), norm.drill_width(other)  # like with like (change c0407)
    if (drill_a is None) != (drill_b is None) or (
        drill_a is not None and drill_b is not None and not norm.lengths_equal(drill_a, drill_b, tolerances)
    ):
        found.append(
            _difference(
                3,
                "pad-drill",
                where,
                "" if drill_a is None else str(drill_a),
                "" if drill_b is None else str(drill_b),
            )
        )
    slot_a, slot_b = norm.slot_form(one), norm.slot_form(other)  # length and axis (change c0416)
    if (slot_a is None) != (slot_b is None) or (
        slot_a is not None
        and slot_b is not None
        and not (
            norm.lengths_equal(slot_a[1], slot_b[1], tolerances)
            and norm.angles_equal(slot_a[2], slot_b[2], tolerances, norm.HALF_TURN)
        )
    ):
        found.append(_difference(3, "pad-slot", where, norm.slot_text(slot_a), norm.slot_text(slot_b)))
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
    mask_a, mask_b = masks[0](one), masks[1](other)
    if not norm.masks_equal(mask_a, mask_b, tolerances):  # change c0440
        found.append(_difference(3, "pad-mask", where, str(mask_a), str(mask_b)))
    return found, unknown


def _grouped(footprint: FootprintInstance) -> dict[str, list[Pad]]:
    groups: dict[str, list[Pad]] = defaultdict(list)
    for pad in footprint.pads:
        groups[pad.number].append(pad)
    for pads in groups.values():
        pads.sort(key=lambda p: (p.position.x, p.position.y))
    return groups


def _copper_roles(board: Board) -> dict[str, str]:
    """The role of each copper layer of ``board`` by its ordinal: ``top``, ``bottom`` or ``inner<k>``."""
    copper = sorted((layer for layer in board.layers if layer.kind == "copper"), key=lambda x: x.ordinal)
    roles: dict[str, str] = {}
    for index, layer in enumerate(copper):
        last = index == len(copper) - 1
        roles[layer.name] = "top" if index == 0 else "bottom" if last else f"inner{index}"
    return roles


Piece = tuple[str, str, int, tuple[Point, ...]]
"""One piece of copper of a footprint (change c0431): ``(role, form, width, points)``. A ``segment`` holds
its two ends, a ``region`` its corners and an ``arc`` its start, middle and end; the points of a segment and
a region are sorted, so the direction and the first corner do not count."""


def _ends(points: Sequence[Point]) -> tuple[Point, ...]:
    return tuple(sorted(points, key=lambda p: (p.x, p.y)))


_PRIMITIVE_GRAPHIC = {"poly": "polygon", "segment": "line", "circle": "circle", "arc": "arc"}
"""The graphic kind whose copper a custom pad's primitive kind gives (change c0431)."""


def _shape_pieces(role: str, kind: str, points: Sequence[Point], width: int, filled: bool) -> list[Piece]:
    if kind == "rect" and len(points) == 2:
        s, e = points
        points = (s, Point(e.x, s.y), e, Point(s.x, e.y))
    pieces: list[Piece] = []
    if kind in ("rect", "polygon"):
        if filled:
            pieces.append((role, "region", 0, _ends(points)))
            if width <= 0:
                return pieces
        for index, point in enumerate(points):
            following = points[(index + 1) % len(points)]
            if point != following:
                pieces.append((role, "segment", width, _ends((point, following))))
    elif kind == "line":
        pieces.append((role, "segment", width, _ends(points)))
    elif kind == "circle" and len(points) == 2:
        centre, edge = points
        radius = round(math.hypot(edge.x - centre.x, edge.y - centre.y))
        pieces.append((role, "arc", width, (centre, Point(radius, 0))))
    else:
        ordered = (
            points
            if len(points) != 3 or (points[0].x, points[0].y) <= (points[2].x, points[2].y)
            else tuple(points)[::-1]
        )
        pieces.append((role, "arc", width, tuple(ordered)))
    return pieces


def _is_copper_drawing(pad: Pad) -> bool:
    """A pad that only draws copper: no number, no net, a custom shape. KiCad's importer turns a copper
    region of an Altium component into such a pad, with a point anchor and the region as its primitive
    (``docs/formats/altium/pcb-read.md``, "What KiCad does not import")."""
    return pad.number == "" and pad.net_id is None and pad.shape == "custom"


def _on_pad(pad: Pad, point: Point) -> Point:
    turned = rotate_point(point, pad.rotation)
    return Point(pad.position.x + turned.x, pad.position.y + turned.y)


def copper_pieces(footprint: FootprintInstance, board: Board) -> list[Piece]:
    """The copper of ``footprint``'s graphics in its own frame (change c0431): a line, and each side of a
    rectangle or polygon outline, is a ``segment``; a filled rectangle or polygon is a ``region``; a circle
    is an ``arc`` of its centre and its radius; an arc is an ``arc`` of its three points. A graphic on a
    layer that is not a copper layer of ``board`` is not copper.

    The primitives of a pad without a number and without a net (``_is_copper_drawing``) are copper of the
    footprint too, placed by the pad's position and rotation, on each copper layer of the pad: they are how
    KiCad's importer holds a copper region of a component. The anchor of such a pad is not counted (the
    importer's anchor is a point, 1 nm wide); a numbered pad is compared at level 3, not here."""
    roles = _copper_roles(board)
    pieces: list[Piece] = []
    for graphic in footprint.graphics:
        role = roles.get(graphic.layer)
        if role is not None:
            pieces += _shape_pieces(role, graphic.kind, graphic.points, graphic.width, graphic.filled)
    for pad in footprint.pads:
        if not _is_copper_drawing(pad):
            continue
        for layer in pad.layers:
            role = roles.get(layer)
            if role is None:
                continue
            for primitive in pad.primitives:
                points = tuple(_on_pad(pad, p) for p in primitive.points)
                kind = _PRIMITIVE_GRAPHIC[primitive.kind]
                pieces += _shape_pieces(role, kind, points, primitive.width, primitive.filled)
    return sorted(pieces, key=lambda p: (p[0], p[1], p[2], [(q.x, q.y) for q in p[3]]))


def _piece_text(piece: Piece) -> str:
    role, form, width, points = piece
    return f"{role} {form} width {width} at " + " ".join(_point(p) for p in points)


def _same_piece(a: Piece, b: Piece, tolerances: Tolerances) -> bool:
    return (
        a[0] == b[0]
        and a[1] == b[1]
        and norm.lengths_equal(a[2], b[2], tolerances)
        and len(a[3]) == len(b[3])
        and all(norm.points_equal(p, q, tolerances) for p, q in zip(a[3], b[3], strict=True))
    )


def net_tie_copper_differences(
    ref: str, one: FootprintInstance, other: FootprintInstance, a: Board, b: Board, tolerances: Tolerances
) -> list[Difference]:
    """The copper of a net-tie footprint that one side holds and the other does not (change c0431): the
    copper that joins the nets of its pads, which levels 2 and 5 never see, since each pad keeps its own
    net. One ``net-tie-copper`` difference per piece of ``copper_pieces`` that no piece of the other side
    matches within ``tolerances``; nothing for a footprint that is a net tie on neither side."""
    if not one.net_ties and not other.net_ties:
        return []
    left, right = copper_pieces(one, a), copper_pieces(other, b)
    unmatched: list[Piece] = []
    for piece in left:
        found = next((k for k, held in enumerate(right) if _same_piece(piece, held, tolerances)), None)
        if found is None:
            unmatched.append(piece)
        else:
            del right[found]
    return [_difference(3, "net-tie-copper", ref, _piece_text(p), "") for p in unmatched] + [
        _difference(3, "net-tie-copper", ref, "", _piece_text(p)) for p in right
    ]


def level_footprints(
    a: Design,
    b: Design,
    refs: Sequence[str],
    tolerances: Tolerances = EXACT,
    masks: tuple[norm.MaskOf, norm.MaskOf] = (norm.own_mask, norm.own_mask),
) -> tuple[LevelResult, tuple[FootprintPair, ...]]:
    """Level 3 over the components ``refs``, and the footprint pairs it compared (those of level 4).
    ``masks`` gives each side's solder-mask expansion of a pad (``norm.MaskOf``; change c0440)."""
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
        if not norm.same_footprint_name(name_a, name_b):
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
                    _pad_where(ref, pad_a), pad_a, pad_b, a.board, b.board, tolerances, masks
                )
                differences += found
                unknown += no_span
                compared += 1
        differences += net_tie_copper_differences(ref, one, other, a.board, b.board, tolerances)
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
    strict: bool = False,
    keepout_layers: tuple[Collection[str], Collection[str]] = ((), ()),
    across: bool = False,
    masks: tuple[norm.MaskOf, norm.MaskOf] = (norm.own_mask, norm.own_mask),
) -> EquivalenceReport:
    """Run the levels 1 to ``level`` in order and apply ``rules`` to each; with ``strict`` level 5 also runs
    the item rule of ``strict.py``. Before level 1 a board-only one-pad NPTH footprint that a free hole of
    the other side matches is taken as that hole; layers pair by user name for levels 6 and 7, and
    ``keepout_layers`` names each side's layers whose drawings level 7 compares with rule areas; ``across``
    says the sides come from two backends, so what one backend always declares and the other leaves out
    is not a difference (``rules.level_rules``, ``shapes.level_geometry``; change c0421, ``pairing.py``).
    ``ValueError`` for a level outside ``LEVELS``, or above what both sides hold (the message names the
    side without footprints, or without copper when only level 5 is out of reach). Levels 6 and 7 need a
    footprint on both sides; they run level 5 only when both sides hold copper."""
    if type(level) is not int or level not in LEVELS:
        raise ValueError(f"level is one of {', '.join(map(str, LEVELS))}, got {level!r}")
    highest = max_level(a, b)
    if level > 5 and highest < 4:
        bare = " and ".join(name for name, side in (("a", a), ("b", b)) if not _has_footprints(side))
        raise ValueError(
            f"level {level} needs footprints on both sides, and side {bare} holds none; "
            f"the highest level available is {highest}"
        )
    if 5 >= level > highest:
        held, needs = (
            (_has_footprints, "footprints") if highest < 4 else (has_copper, "a track, an arc or a via")
        )
        bare = " and ".join(name for name, side in (("a", a), ("b", b)) if not held(side))
        raise ValueError(
            f"level {level} needs {needs} on both sides, and side {bare} holds none; "
            f"the highest level available is {highest}"
        )
    a, b = forms.mounting_holes(a, b, tolerances)
    a, b = paired_references(a, b, ignore_refs=ignore_refs)
    aliases = forms.layer_aliases(a.board, b.board) if a.board is not None and b.board is not None else {}
    first, refs = level_components(a, b, ignore_refs=ignore_refs)
    results = [first]
    shift = Point(0, 0)
    if level >= 2:
        results.append(level_netlist(a, b, refs))
    if level >= 3:
        third, pairs = level_footprints(a, b, refs, tolerances, masks)
        results.append(third)
        if level >= 4:
            fourth, shift = level_placement(pairs, tolerances, frame)
            results.append(fourth)
        if level >= 5 and highest == 5:
            pairing = pair_nets(a, b, refs)
            routed = level_routing(a, b, pairing, tolerances, shift=shift)
            if strict:
                extra = compare_strict(a, b, pairing, tolerances)
                routed = replace(
                    routed,
                    compared=routed.compared + extra.compared,
                    differences=routed.differences + extra.differences,
                    notices=routed.notices + extra.notices,
                    summary={**routed.summary, "strict": dict(extra.summary)},
                )
            results.append(routed)
        if level >= 6:
            results.append(
                level_rules(a, b, tolerances, aliases=aliases, across=across, keepout_layers=keepout_layers)
            )
        if level >= 7:
            results.append(
                level_geometry(
                    a,
                    b,
                    pairs,
                    tolerances,
                    aliases=aliases,
                    keepout_layers=keepout_layers,
                    across=across,
                    shift=shift,
                )
            )
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
    "paired_references",
]
