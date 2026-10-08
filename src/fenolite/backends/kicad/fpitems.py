# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The graphics, the texts and the corner ratios of the footprints of a KiCad board, projected on request
(capability kicad-file-backend, "Footprint items projected on request"; change c0126).

``read_board`` keeps the ``fp_line``, ``fp_arc``, ``fp_circle``, ``fp_rect``, ``fp_poly`` and ``fp_text``
children of a board footprint, and the ``roundrect_rratio`` of a pad, as opaque slots, and ``write_board``
writes each back verbatim. Nothing of that changes. ``with_footprint_items`` gives a copy of such a design
in which every footprint also holds them as model entities (``FootprintInstance.graphics``, ``.texts``,
``Pad.corner_ratio``): read-only copies of the opaque children, for a consumer that is not the KiCad
writer (the write of a KiCad design as Altium documents). The slots stay as they are, so the projected
design writes to the same board text.

No reader and no writer calls this module by itself. ``pcb.write_board`` imports it only inside its check
of a footprint that carries ``PROJECTED_PAIR``, to project again and compare.

Facts: ``docs/formats/kicad/board.md``, "Footprint children projected on request".
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from types import MappingProxyType

import fenolite.backends.kicad.slots as slotlib
from fenolite.backends.kicad._fpmap import FP_GRAPHIC_HEADS, Ids, read_graphic, unrepresentable
from fenolite.backends.kicad._libread import Context, Loaded, leading_atoms
from fenolite.backends.kicad.sexpr import Node, parse_fragment
from fenolite.backends.kicad.slots import Opaque
from fenolite.backends.kicad.versions import FileKind
from fenolite.core.coords import Size
from fenolite.core.errors import FenoliteError
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.transform import FULL_TURN
from fenolite.model.base import ExtBag
from fenolite.model.board import MAX_CORNER_RATIO, FootprintInstance, Graphic, Pad, Text
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PCB-FPGFX",))
"""The projection is checked against Fenolite's own library reader only."""
BACKEND = "kicad"
PROJECTED_PAIR: tuple[str, str] = ("fenolite.projected", "footprint-items")
"""The pair of a footprint's ``kicad`` bag that says its ``graphics``, ``texts`` and its pads'
``corner_ratio`` are projections of its opaque children: ``write_board`` then compares them with a fresh
projection and refuses a difference (``kicad.board.projection-read-only``)."""
TEXT_HEAD = "fp_text"
RATIO_HEAD = "roundrect_rratio"
DRAWN_HEADS: frozenset[str] = frozenset(
    {*FP_GRAPHIC_HEADS, TEXT_HEAD, "fp_text_box", "fp_curve", "dimension"}
)
"""The children of a board footprint that draw something: each one is projected or counted as skipped."""
PLAIN_STROKES: frozenset[str] = frozenset({"default", "solid"})
PPM = 1_000_000
_ROOT = ("footprint",)


@dataclass(frozen=True, slots=True)
class Projection:
    """What ``with_footprint_items`` returns: the projected design, the number of projected items per
    kind (``graphic``, ``text``, ``corner_ratio``), and per head the children that the model cannot hold
    and that were left out (they stay in the footprint's slots)."""

    design: Design
    projected: Mapping[str, int]
    skipped: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class FootprintItems:
    """The projection of one footprint."""

    graphics: tuple[Graphic, ...]
    texts: tuple[Text, ...]
    ratios: Mapping[str, int]
    """Pad id → ``corner_ratio`` in ppm."""
    skipped: tuple[str, ...]
    """The head of each child that was left out."""


def ratio_ppm(text: str) -> int | None:
    """A ``roundrect_rratio`` as parts per million of the pad's shorter side, rounded half to even to one
    ppm; ``None`` for a text that is no number or lies outside 0 to 0.5."""
    try:
        value = (Decimal(text) * PPM).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
    except (InvalidOperation, ValueError):
        return None
    ppm = int(value)
    return ppm if 0 <= ppm <= MAX_CORNER_RATIO else None


def _opaque_nodes(entity: FootprintInstance | Pad) -> list[Node]:
    bag = entity.ext.get(BACKEND)
    if bag is None:
        return []
    nodes: list[Node] = []
    for slot in slotlib.from_ext(bag):
        if isinstance(slot, Opaque):
            parsed = parse_fragment(slot.fragment)
            if isinstance(parsed, Node):
                nodes.append(parsed)
    return nodes


def _plain_stroke(node: Node) -> bool:
    stroke = node.find("stroke")
    kind = stroke.find("type") if stroke is not None else None
    if kind is None:
        return True
    atoms = kind.atoms()
    return bool(atoms) and atoms[0].value in PLAIN_STROKES


def _text(ctx: Context, node: Node, loc: str, ids: Ids, footprint: FootprintInstance) -> Text | None:
    """One ``fp_text`` as a ``Text``, as ``pcb`` maps a ``gr_text``; ``None`` when it holds no string, no
    position, no layer, no font size or no thickness. The file stores the board angle of the text."""
    effects = node.find("effects")
    font = effects.find("font") if effects is not None else None
    size_node = font.find("size") if font is not None else None
    thickness = font.find("thickness") if font is not None else None
    leading = leading_atoms(node)
    at, layer = node.find("at"), node.find("layer")
    strings = leading[1:]
    if size_node is None or thickness is None or not strings or at is None or layer is None:
        return None
    if not thickness.atoms() or not layer.atoms():
        return None
    values = at.atoms()
    size = ctx.point(size_node, f"{loc}/effects[0]/font[0]/size[0]")
    stored = ctx.udeg(values[2], f"{loc}/at[0]", at) if len(values) > 2 else 0
    ident, native_ids = ids.of("txt", TEXT_HEAD, node)
    return Text(
        id=ident,
        native_ids=native_ids,
        provenance=ctx.provenance(loc),
        text=strings[0].value,
        position=ctx.point(at, f"{loc}/at[0]"),
        rotation=(stored - footprint.rotation) % FULL_TURN,  # pcb.pad_angle_from_board
        layer=layer.atoms()[0].value,
        size=Size(size.y, size.x),
        thickness=ctx.nm(thickness.atoms()[0], f"{loc}/effects[0]/font[0]/thickness[0]", thickness),
    )


def footprint_items(footprint: FootprintInstance) -> FootprintItems:
    """The projection of the opaque children of one board footprint, in child order. A child that the
    model cannot hold (a stroke that is not solid, a polygon with an arc, a text without a font size, a
    number that is no whole number of nanometres, ``fp_text_box``, ``fp_curve``, ``dimension``) is named
    in ``skipped``."""
    key = footprint.native_ids.get(BACKEND, footprint.id)
    ids = Ids(key)
    source = footprint.provenance
    base = source.locator if source is not None else "/footprint"
    graphics: list[Graphic] = []
    texts: list[Text] = []
    skipped: list[str] = []
    seen: Counter[str] = Counter()
    for node in _opaque_nodes(footprint):
        head = node.name
        if head not in DRAWN_HEADS:
            continue
        loc = f"{base}/{head}[{seen[head]}]"
        seen[head] += 1
        loaded = Loaded(
            node,
            source.file_sha256 if source is not None else "",
            source.file if source is not None else "",
            None,
        )
        ctx = Context(loaded, FileKind.FOOTPRINT, EVIDENCE)
        kind = FP_GRAPHIC_HEADS.get(head)
        try:
            if kind is not None:
                if unrepresentable(node, kind) is not None or not _plain_stroke(node):
                    skipped.append(head)
                    continue
                graphic = read_graphic(ctx, node, loc, kind, ids, root=_ROOT)
                graphics.append(dataclasses.replace(graphic, ext={}))
            elif head == TEXT_HEAD:
                text = _text(ctx, node, loc, ids, footprint)
                if text is None:
                    skipped.append(head)
                else:
                    texts.append(text)
            else:
                skipped.append(head)
        except FenoliteError:  # an inexact or malformed number: the child stays in its slot only
            skipped.append(head)
    ratios: dict[str, int] = {}
    for pad in footprint.pads:
        if pad.shape != "roundrect":
            continue
        for node in _opaque_nodes(pad):
            atoms = node.atoms()
            ppm = ratio_ppm(atoms[0].value) if node.name == RATIO_HEAD and len(atoms) == 1 else None
            if ppm is not None:
                ratios[pad.id] = ppm
    return FootprintItems(tuple(graphics), tuple(texts), MappingProxyType(ratios), tuple(skipped))


def is_projected(footprint: FootprintInstance) -> bool:
    """Whether ``footprint`` carries ``PROJECTED_PAIR``."""
    bag = footprint.ext.get(BACKEND)
    return bag is not None and PROJECTED_PAIR in bag.payload


def _marked(footprint: FootprintInstance) -> dict[str, ExtBag]:
    bag = footprint.ext.get(BACKEND, ExtBag())
    if PROJECTED_PAIR in bag.payload:
        return dict(footprint.ext)
    return {**footprint.ext, BACKEND: dataclasses.replace(bag, payload=(PROJECTED_PAIR, *bag.payload))}


def with_footprint_items(design: Design) -> Projection:
    """A copy of ``design``, read from a KiCad board, in which every footprint holds the graphics, the
    texts and the corner ratios of its opaque children as read-only projections, and carries
    ``PROJECTED_PAIR``. Every slot stays as it was: ``write_board`` gives the same text for both designs.
    A design without a board is returned as it is, and so is a footprint without a KiCad bag: it was not
    read from a KiCad board (the stored board of an Altium build holds its graphics itself, change c0126),
    and a projection would empty its items."""
    board = design.board
    projected: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    if board is None:
        return Projection(design, MappingProxyType({}), MappingProxyType({}))
    footprints: list[FootprintInstance] = []
    for footprint in board.footprints:
        if BACKEND not in footprint.ext:
            footprints.append(footprint)
            continue
        items = footprint_items(footprint)
        pads = tuple(
            dataclasses.replace(pad, corner_ratio=items.ratios[pad.id]) if pad.id in items.ratios else pad
            for pad in footprint.pads
        )
        footprints.append(
            dataclasses.replace(
                footprint, pads=pads, graphics=items.graphics, texts=items.texts, ext=_marked(footprint)
            )
        )
        projected["graphic"] += len(items.graphics)
        projected["text"] += len(items.texts)
        projected["corner_ratio"] += len(items.ratios)
        skipped.update(items.skipped)
    new = dataclasses.replace(design, board=dataclasses.replace(board, footprints=tuple(footprints)))
    return Projection(
        new,
        MappingProxyType(dict(sorted(projected.items()))),
        MappingProxyType(dict(sorted(skipped.items()))),
    )


def projection_problems(footprint: FootprintInstance) -> list[tuple[str, str]]:
    """``(field, detail)`` for each of ``graphics``, ``texts`` and ``corner_ratio`` of a footprint that
    carries ``PROJECTED_PAIR`` and differs from a fresh projection of its opaque children: the fields are
    read-only copies, and the writer writes the children."""
    if not is_projected(footprint):
        return []
    fresh = footprint_items(footprint)
    found: list[tuple[str, str]] = []
    if footprint.graphics != fresh.graphics:
        found.append(("graphics", "the graphics of a footprint are written as read: an edit is not written"))
    if footprint.texts != fresh.texts:
        found.append(("texts", "the texts of a footprint are written as read: an edit is not written"))
    held = {pad.id: pad.corner_ratio for pad in footprint.pads if pad.corner_ratio is not None}
    if held != dict(fresh.ratios):
        found.append(("corner_ratio", "the corner ratio of a pad is written as read: an edit is not written"))
    return found


__all__ = [
    "DRAWN_HEADS",
    "EVIDENCE",
    "PROJECTED_PAIR",
    "FootprintItems",
    "Projection",
    "footprint_items",
    "is_projected",
    "projection_problems",
    "ratio_ppm",
    "with_footprint_items",
]
