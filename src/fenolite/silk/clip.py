# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Silkscreen of a KiCad board cut at its mask openings (capability silkscreen-layout, "Silkscreen
clipping", "Clipped strokes checked" and "Clipped footprints and their library"; change c0226; user guide
``docs/assembly.md``, "Clipping").

``openings_of`` gathers, per side, what the silkscreen must keep clear of: every pad whose layers hold the
side's mask, by its copper on the side's outer layer grown by its positive mask expansion (the pad's
``mask_margin``, else the board's ``pad_to_mask_clearance``), and every pad's hole on both sides. KiCad's
DRC measures to the copper (``H-K-SILK-MASK``), which the grown opening holds.

``clip_board`` cuts the silkscreen strokes with ``silk.cut``. A board graphic is replaced by its pieces. A
footprint's own children are cut first by the openings of its own pads, once per group of instances that
share the footprint name, side, silkscreen children (uuids aside) and pads, on the first of them in
reference order, and the same pieces go into every member: so ``fenolite library`` makes one footprint
of them (c0223). The openings of other parts then cut an instance further, which makes it differ from the
others (``silk.cut-by-other``). Each written piece is judged again against every opening of its side with
the margin (``silk.check-failed``).
"""

from __future__ import annotations

import dataclasses
import fnmatch
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import fenolite.backends.kicad.slots as slotlib
from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.fpitems import drawn_children, replace_children
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import FENOLITE_NS, derived_id
from fenolite.core.units import Nm, format_length
from fenolite.geometry import GeometryError, Thick, Transform, thick_closer_than
from fenolite.model.base import Modeled
from fenolite.model.board import FootprintInstance, Graphic
from fenolite.model.design import Design
from fenolite.silk.board import natural
from fenolite.silk.codes import issue
from fenolite.silk.cut import GUARD, Cut, Kind, Piece, cut, near_openings, piece_shape, stroke_shapes

SILK = {"F.SilkS": "top", "B.SilkS": "bottom"}
MASK = {"top": "F.Mask", "bottom": "B.Mask"}
COPPER = {"top": "F.Cu", "bottom": "B.Cu"}
POINT_HEADS = frozenset({"start", "mid", "end", "center", "pts", "fill", "uuid"})
HYPOTHESIS = "H-K-SILK-CLIP"
"""The register row that a board whose strokes ``clip_board`` cut gives KiCad's DRC no
``silk_over_copper`` and nothing new."""
MASK_HYPOTHESIS = "H-K-SILK-MASK"
"""The register row of what KiCad's ``silk_over_copper`` measures."""


@dataclass(frozen=True, slots=True)
class Opening:
    """What a stroke on one side must keep clear of: a thick shape, the footprint id of its pad, and its
    name for a message."""

    shape: Thick
    owner: str
    what: str


@dataclass(frozen=True, slots=True)
class ClipOutcome:
    """The clipped design, one row per owner whose strokes were cut, the issues, the footprint names whose
    own graphics changed (with their references), and the counts."""

    design: Design
    rows: tuple[dict[str, object], ...]
    issues: tuple[Issue, ...]
    changed: Mapping[str, tuple[str, ...]]
    openings: int
    items: int
    pieces: int
    dropped: int


def board_mask_margin(text: str) -> Nm:
    """The board's ``(setup (pad_to_mask_clearance M))`` in nanometres; 0 when absent or unreadable."""
    try:
        setup = parse(text).find("setup")
        node = setup.find("pad_to_mask_clearance") if setup is not None else None
        if node is None or not node.atoms():
            return 0
        return int(Decimal(node.atoms()[0].value) * 1_000_000)
    except (ValueError, InvalidOperation):
        return 0


def _has_mask(layers: Sequence[str], side: str) -> bool:
    return MASK[side] in layers or "*.Mask" in layers or "F&B.Mask" in layers


def openings_of(design: Design, pads: Sequence[BoardPad], board_margin: Nm) -> dict[str, list[Opening]]:
    """The openings of each side (see the module)."""
    board = design.board
    assert board is not None
    margins = {pad.id: pad.mask_margin for fp in board.footprints for pad in fp.pads}
    found: dict[str, list[Opening]] = {"top": [], "bottom": []}
    for pad in pads:
        name = f"pad {pad.ref or pad.footprint_id}-{pad.number}"
        own = margins.get(pad.pad_id)
        grow = max(own if own is not None else board_margin, 0)
        for side in ("top", "bottom"):
            if not _has_mask(pad.layers, side):
                continue
            for copper in pad.copper:
                if copper.layer == COPPER[side]:
                    shape = Thick(copper.core, copper.width + 2 * grow, copper.filled)
                    found[side].append(Opening(shape, pad.footprint_id, name))
        if pad.hole and pad.drill:
            for side in ("top", "bottom"):
                found[side].append(
                    Opening(Thick(pad.hole, pad.drill), pad.footprint_id, f"the hole of {name}")
                )
    return found


def _uuid(old: str, count: int) -> str:
    return str(uuid.uuid5(FENOLITE_NS, f"silk-clip:{old}:{count}"))


def _point(head: str, point: Point) -> Node:
    return Node(Atom.symbol(head), (Atom.from_nm(point.x), Atom.from_nm(point.y)))


def piece_node(original: Node, piece: Piece, ident: str) -> Node:
    """A footprint child for a piece: ``fp_line`` or ``fp_arc`` with the original's other children (its
    stroke and layer) and the uuid ``ident``."""
    heads = ("start", "end") if piece.kind == "line" else ("start", "mid", "end")
    points = [_point(head, p) for head, p in zip(heads, piece.points, strict=True)]
    rest = [c for c in original.children[1:] if not (isinstance(c, Node) and c.name in POINT_HEADS)]
    uuid_node = Node(Atom.symbol("uuid"), (Atom.string(ident),))
    head = Atom.symbol("fp_line" if piece.kind == "line" else "fp_arc")
    return Node(head, (*points, *rest, uuid_node))


def _node_uuid(node: Node) -> str:
    found = node.find("uuid")
    return found.atoms()[0].value if found is not None and found.atoms() else dumps(node, style="compact")


def _apply(move: Transform, piece: Piece) -> Piece:
    return Piece(tuple(move.apply(p) for p in piece.points))


def _shape_cut(
    kind: Kind, points: Sequence[Point], width: Nm, filled: bool, openings: Sequence[Opening], margin: Nm
) -> Cut | None:
    return cut(kind, points, width, [o.shape for o in openings], margin, filled=filled)


def _key(footprint: FootprintInstance, silk: Sequence[Node]) -> tuple[object, ...]:
    pads = tuple(
        sorted(
            (
                pad.number,
                pad.position,
                pad.size,
                pad.shape,
                pad.rotation,
                pad.layers,
                pad.mask_margin,
                pad.drill,
            )
            for pad in footprint.pads
        )
    )
    children = tuple(
        dumps(Node(n.head, tuple(c for c in n.children if not (isinstance(c, Node) and c.name == "uuid"))))
        for n in silk
    )
    return (footprint.lib_ref, footprint.side, children, repr(pads))


@dataclass
class _Tally:
    items: int = 0
    pieces: int = 0
    dropped: int = 0
    own: bool = False
    other: bool = False
    by: set[str] = dataclasses.field(default_factory=lambda: set[str]())


def _graphic_pieces(graphic: Graphic, pieces: Sequence[Piece]) -> list[Graphic]:
    """The board graphics of a cut board graphic: its slots without ``fill``, a derived id and uuid."""
    bag = graphic.ext.get("kicad")
    ext = dict(graphic.ext)
    if bag is not None:
        slots = [s for s in slotlib.from_ext(bag) if s != Modeled("filled")]
        ext["kicad"] = slotlib.to_ext(slots, base=bag)
    old = graphic.native_ids.get("kicad", graphic.id)
    found: list[Graphic] = []
    for count, piece in enumerate(pieces):
        found.append(
            dataclasses.replace(
                graphic,
                id=derived_id("gfx", "fenolite.silk", f"{graphic.id}:{count}"),
                native_ids={**graphic.native_ids, "kicad": _uuid(old, count)},
                ext=ext,
                kind=piece.kind,
                points=piece.points,
                filled=False,
            )
        )
    return found


def _check(
    pieces: Sequence[Piece], width: Nm, openings: Sequence[Opening], margin: Nm, owner: str
) -> list[Issue]:
    found: list[Issue] = []
    for piece in pieces:
        try:
            shape = piece_shape(piece, width)
        except (GeometryError, ValueError):
            found.append(
                issue(
                    "silk.check-failed",
                    f"a cut piece of the silkscreen of {owner} is not a valid stroke; nothing is written",
                    where=owner,
                    hint="report the board: every piece is checked before it is written",
                )
            )
            continue
        blocker = next((o for o in openings if thick_closer_than(shape, o.shape, margin)), None)
        if blocker is not None:
            found.append(
                issue(
                    "silk.check-failed",
                    f"a cut piece of the silkscreen of {owner} is within {format_length(margin)} of "
                    f"{blocker.what}; nothing is written",
                    where=owner,
                    hint="report the board: every piece is checked before it is written",
                )
            )
    return found


def clip_board(
    design: Design,
    pads: Sequence[BoardPad],
    *,
    margin: Nm,
    board_margin: Nm = 0,
    refs: Sequence[str] = ("*",),
) -> ClipOutcome:
    """Cut the silkscreen strokes of ``design``'s board (see the module); ``refs`` are patterns of the
    references whose footprints are cut (board graphics are always cut)."""
    board = design.board
    assert board is not None
    refs_of = {c.id: c.ref for c in design.circuit.components}
    openings = openings_of(design, pads, board_margin)
    issues: list[Issue] = []
    rows: list[dict[str, object]] = []
    totals = _Tally()
    # board graphics
    graphics: list[Graphic] = []
    board_tally = {side: _Tally() for side in ("top", "bottom")}
    for graphic in board.graphics:
        side = SILK.get(graphic.layer)
        if side is None:
            graphics.append(graphic)
            continue
        result = _shape_cut(
            graphic.kind, graphic.points, graphic.width, graphic.filled, openings[side], margin
        )
        if result is None:
            graphics.append(graphic)
            continue
        if result.skipped:
            issues.append(_skipped("the board", graphic.kind))
            graphics.append(graphic)
            continue
        tally = board_tally[side]
        tally.items += 1
        tally.pieces += len(result.pieces)
        tally.dropped += result.dropped
        issues.extend(_check(result.pieces, graphic.width, openings[side], margin, "the board"))
        graphics.extend(_graphic_pieces(graphic, result.pieces))
    for side, tally in board_tally.items():
        if tally.items:
            rows.append(_row("board", None, side, tally))
            _add(totals, tally)
    # footprints, by groups of identical instances
    chosen = [
        fp
        for fp in board.footprints
        if any(fnmatch.fnmatchcase(refs_of.get(fp.component_id, ""), pattern) for pattern in refs)
    ]
    chosen.sort(key=lambda fp: natural(refs_of.get(fp.component_id, fp.id)))
    groups: dict[tuple[object, ...], list[FootprintInstance]] = {}
    silk_of: dict[str, list[tuple[int, Node, Graphic]]] = {}
    for footprint in chosen:
        ref = refs_of.get(footprint.component_id, "") or footprint.id
        silk: list[tuple[int, Node, Graphic]] = []
        for child in drawn_children(footprint):
            layer = child.node.find("layer")
            on_silk = layer is not None and bool(layer.atoms()) and layer.atoms()[0].value in SILK
            if not on_silk:
                continue
            if isinstance(child.item, Graphic):
                silk.append((child.slot, child.node, child.item))
            elif child.item is None and child.node.name != "fp_text":
                issues.append(_unmodelled(ref, child.node.name))
        silk_of[footprint.id] = silk
        groups.setdefault(_key(footprint, [node for _, node, _ in silk]), []).append(footprint)
    footprints = {fp.id: fp for fp in board.footprints}
    changed: dict[str, list[str]] = {}
    for members in groups.values():
        first = members[0]
        move = Transform.placement(first.position, first.rotation)
        back = move.inverse()
        own_cuts: list[Cut | None] = []
        for _, _, graphic in silk_of[first.id]:
            side = SILK[graphic.layer]
            own = [o for o in openings[side] if o.owner == first.id]
            board_points = [move.apply(p) for p in graphic.points]
            result = _shape_cut(graphic.kind, board_points, graphic.width, graphic.filled, own, margin)
            if result is not None and not result.skipped:
                result = Cut(tuple(_apply(back, piece) for piece in result.pieces), result.dropped)
            own_cuts.append(result)
        for member in members:
            ref = refs_of.get(member.component_id, "") or member.id
            here = Transform.placement(member.position, member.rotation)
            home = here.inverse()
            replacements: dict[int, list[Node]] = {}
            tally = _Tally()
            for (slot, node, graphic), own_cut in zip(silk_of[member.id], own_cuts, strict=True):
                side = SILK[graphic.layer]
                foreign = [o for o in openings[side] if o.owner != member.id]
                if own_cut is not None and own_cut.skipped:
                    issues.append(_skipped(ref, graphic.kind))
                    continue
                local = (
                    list(own_cut.pieces)
                    if own_cut is not None
                    else [Piece(tuple(graphic.points))]
                    if graphic.kind in ("line", "arc")
                    else None
                )
                dropped = own_cut.dropped if own_cut is not None else 0
                cut_by_other = False
                if local is None:  # an uncut rectangle, polygon or circle
                    board_points = [here.apply(p) for p in graphic.points]
                    result = _shape_cut(
                        graphic.kind, board_points, graphic.width, graphic.filled, foreign, margin
                    )
                    if result is not None and result.skipped:
                        issues.append(_skipped(ref, graphic.kind))
                        continue
                    if result is not None:
                        cut_by_other = True
                        local = [_apply(home, piece) for piece in result.pieces]
                        dropped += result.dropped
                        tally.by.update(_names(graphic, here, foreign, margin))
                else:
                    kept: list[Piece] = []
                    for piece in local:
                        on_board = _apply(here, piece)
                        result = _shape_cut(
                            piece.kind, on_board.points, graphic.width, False, foreign, margin
                        )
                        if result is None:
                            kept.append(piece)
                            continue
                        cut_by_other = True
                        dropped += result.dropped
                        kept.extend(_apply(home, p) for p in result.pieces)
                        tally.by.update(_near_names([piece_shape(on_board, graphic.width)], foreign, margin))
                    local = kept
                if own_cut is None and not cut_by_other:
                    continue
                assert local is not None
                tally.items += 1
                tally.pieces += len(local)
                tally.dropped += dropped
                tally.own = tally.own or own_cut is not None
                tally.other = tally.other or cut_by_other
                old = _node_uuid(node)
                replacements[slot] = [piece_node(node, p, _uuid(old, n)) for n, p in enumerate(local)]
                issues.extend(
                    _check([_apply(here, p) for p in local], graphic.width, openings[side], margin, ref)
                )
            if not replacements:
                continue
            footprints[member.id] = replace_children(footprints[member.id], replacements)
            rows.append(_row(ref, member.lib_ref, member.side, tally))
            _add(totals, tally)
            if tally.own:
                changed.setdefault(member.lib_ref, []).append(ref)
            if tally.other:
                issues.append(
                    issue(
                        "silk.cut-by-other",
                        f"the silkscreen of {ref} was cut at {', '.join(sorted(tally.by)) or 'another part'}"
                        "; "
                        f"{ref} now differs from the other instances of {member.lib_ref}, and fenolite "
                        f"library would make it a footprint of its own",
                        where=ref,
                        hint="move the parts apart so that no outline crosses another part's pads",
                    )
                )
    for name, names in sorted(changed.items()):
        issues.append(
            issue(
                "silk.footprint-changed",
                f"the silkscreen of footprint {name} ({', '.join(names)}) was cut at its own pads; "
                "its library copy no longer matches the board",
                where=name,
                hint="write the library from the board with fenolite library BOARD --out LIB.pretty, or "
                "compare it with --diff LIB.pretty, before the next rebuild",
            )
        )
    new_board = dataclasses.replace(
        board,
        graphics=tuple(graphics),
        footprints=tuple(footprints[fp.id] for fp in board.footprints),
    )
    return ClipOutcome(
        design=dataclasses.replace(design, board=new_board),
        rows=tuple(rows),
        issues=tuple(issues),
        changed={name: tuple(names) for name, names in sorted(changed.items())},
        openings=sum(len(found) for found in openings.values()),
        items=totals.items,
        pieces=totals.pieces,
        dropped=totals.dropped,
    )


def _near_names(shapes: Sequence[Thick], openings: Sequence[Opening], margin: Nm) -> list[str]:
    """The names of the openings that a shape comes near (as ``silk.cut`` decides it)."""
    return [o.what for o in openings if near_openings(shapes, [o.shape], margin + GUARD)]


def _names(graphic: Graphic, move: Transform, openings: Sequence[Opening], margin: Nm) -> list[str]:
    """The names of the openings an uncut stroke comes near."""
    shapes = stroke_shapes(graphic.kind, [move.apply(p) for p in graphic.points], graphic.width)
    return _near_names(shapes, openings, margin)


def _row(owner: str, footprint: str | None, side: str, tally: _Tally) -> dict[str, object]:
    by = ["own"] if tally.own else []
    if tally.other:
        by.append("other")
    return {
        "owner": owner,
        "footprint": footprint,
        "side": side,
        "items": tally.items,
        "pieces": tally.pieces,
        "dropped": tally.dropped,
        "by": by or ["board"],
    }


def _add(total: _Tally, tally: _Tally) -> None:
    total.items += tally.items
    total.pieces += tally.pieces
    total.dropped += tally.dropped


def _skipped(owner: str, kind: str) -> Issue:
    return issue(
        "silk.clip-skipped",
        f"a filled {kind} of the silkscreen of {owner} meets a mask opening; a filled shape is not cut",
        where=owner,
        hint="edit the shape by hand, or check the board with --drc",
    )


def _unmodelled(owner: str, head: str) -> Issue:
    return issue(
        "silk.item-skipped",
        f"{owner} holds a silkscreen {head} that Fenolite does not model; it is not cut",
        where=owner,
        hint="check the board with --drc",
    )


__all__ = [
    "HYPOTHESIS",
    "MASK_HYPOTHESIS",
    "ClipOutcome",
    "Opening",
    "board_mask_margin",
    "clip_board",
    "openings_of",
    "piece_node",
]
