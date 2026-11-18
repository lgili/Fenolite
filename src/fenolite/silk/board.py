# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designators of a KiCad board placed and checked (capability silkscreen-layout, "Designator placement"
and "Placed designators checked"; change c0212; user guide ``docs/assembly.md``, "Designators").

``place_designators`` gathers, per silkscreen side, what a designator must keep ``clearance`` from: the
copper of the pads on that side's outer layer, every drilled hole (pad, via and board holes), the
silkscreen strokes of the board and of the footprints, the ink of every other text on the side, and the
board edge (outline, cut-outs and slots). Another part's courtyard only adds to a place's cost (change
c0493), unless the board's rules judge silkscreen against courtyards (``Settings.courtyard``): then every
courtyard, the text's own too, is kept that far. The ``altium`` model (``Settings.model``,
``H-A-SILK-DRC-MODEL``) keeps a text ``mask_clearance`` from each pad's mask opening instead of its copper,
leaves out unplated holes, and judges every text by the box Altium measures as well as by its ink
(``text_box``). Both models keep a text clear of its own footprint's silkscreen (field result, 2026-11-17).
It measures the ink of every text (``silk.extents``), runs the search of ``silk.layout`` and writes
each chosen place into the part's ``Reference`` field: anchor, angle 0 or 90 degrees on the board, size,
stroke, centred justification, and mirrored on the bottom side.

``check_designators`` then judges the written board on its own: each placed text is computed again from
its field, through the same frame facts, and must keep the clearance from every obstacle and every other
text, lie in the board's material, be at least the board's least text height and stroke, and read at
0 or 90 degrees (mirrored on the bottom). A miss is a ``silk.check-failed`` error and nothing is written.

How KiCad draws a field (``H-K-FIELD-FRAME``, ``H-K-FIELD-JUSTIFY``): the anchor is
``fp.position + R(fp.rotation)·field.position``; the angle is the board angle, a text at 180 or 270
degrees is drawn as at 0 or 90; a mirrored text runs the other way; the box is turned with
``H-G-ROT-DIR``. Other texts (footprint texts and board texts) are taken as the box symmetric about
their anchor, turned by their angle, so neither the upright rule nor a mirror can move ink out of it.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from fenolite.backends.base import BoardPad, EdgeRing, PlacedExtent
from fenolite.backends.kicad.fields import field_anchor, field_angle, set_field
from fenolite.backends.kicad.fpitems import footprint_items
from fenolite.backends.kicad.pcb import field_value
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.core.units import Nm, Udeg, format_length
from fenolite.geometry import (
    FULL_TURN,
    Arc,
    Circle,
    GeometryError,
    Location,
    Thick,
    Transform,
    cos_sin_fixed,
    point_in_ring,
)
from fenolite.geometry.transform import TRIG_BITS
from fenolite.model.board import FootprintField, FootprintInstance, Graphic, Text
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.silk.codes import issue
from fenolite.silk.extents import Ink, InkBox, TextKey, estimate, ink_boxes
from fenolite.silk.layout import Choice, Field, Look, Obstacle, Part, Plan, Rect, arrange, gap2

DEG = 1_000_000
SILK = {"top": "F.SilkS", "bottom": "B.SilkS"}
COPPER = {"top": "F.Cu", "bottom": "B.Cu"}
COURTYARD = {"top": "F.CrtYd", "bottom": "B.CrtYd"}
REFERENCE = "Reference"
DEFAULT_CLEARANCE: Nm = 150_000
"""The least distance from a designator's ink to a pad, a hole, other silkscreen, a courtyard or the edge
(a Fenolite choice, above KiCad's default silkscreen clearance of 0)."""
DEFAULT_GAP: Nm = 100_000
DEFAULT_REACH: Nm = 2_000_000
"""How far the rings of candidates reach beyond the gap by default (change c0493)."""
DEFAULT_SIZE_STEP: Nm = 100_000
DEFAULT_MASK_CLEARANCE: Nm = 100_000
ALTIUM_HYPOTHESIS = "H-A-SILK-DRC-MODEL"
KINDS = ("pad", "mask", "hole", "silk", "text", "courtyard", "edge", "outside")
"""What may block a designator's cheapest place (change c0493)."""
"""The distance from the own courtyard's box to a candidate's ink (a Fenolite choice)."""
MIN_HEIGHT: Nm = 800_000
MIN_STROKE: Nm = 80_000
"""The least text height and stroke of a board whose project does not say: the values that KiCad's DRC
reports as ``text_height`` and ``text_thickness`` by default (``docs/formats/kicad/text.md``)."""
STROKE_RATIO = (3, 20)
"""The stroke of a field without one, per height: 0.15 mm at 1 mm (a Fenolite choice)."""
ARC_TOL = 1_000
_DIGITS = re.compile(r"(\d+)")


def natural(text: str) -> tuple[tuple[int, int | str], ...]:
    """A sort key that puts ``R2`` before ``R10``."""
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in _DIGITS.split(text) if part)


@dataclass(frozen=True, slots=True)
class Settings:
    """What ``fenolite silk --designators`` was asked: the clearance and gap, the heights to try (``None``:
    the field's own, then ``min_height`` when that is smaller), the board angles to try, ``keep``, the
    reference patterns, and the readable floor."""

    clearance: Nm = DEFAULT_CLEARANCE
    gap: Nm = DEFAULT_GAP
    heights: tuple[Nm, ...] | None = None
    angles: tuple[Udeg, ...] = (0, 90 * DEG)
    keep: bool = False
    refs: tuple[str, ...] = ("*",)
    min_height: Nm = MIN_HEIGHT
    min_stroke: Nm = MIN_STROKE
    model: str = "kicad"
    """``kicad`` or ``altium`` (change c0493): what a text keeps clear of and how its box is measured."""
    reach: Nm = DEFAULT_REACH
    """How far beyond ``gap`` the rings of candidates go (change c0493)."""
    step: Nm | None = None
    """The distance between rings (``None``: the look's height)."""
    over_body: bool = False
    min_size: Nm | None = None
    """The least height the steps go down to (``None``: ``min_height``)."""
    size_step: Nm = DEFAULT_SIZE_STEP
    mask_clearance: Nm = DEFAULT_MASK_CLEARANCE
    """In the ``altium`` model, the least distance from a text to a pad's mask opening."""
    board_mask: Nm = 0
    """The board's ``pad_to_mask_clearance``, the mask expansion of a pad without one of its own."""
    courtyard: Nm | None = None
    """The distance a text keeps from every courtyard, its own too, when the board's rules judge silkscreen
    against courtyards (``None``: another part's courtyard only adds cost)."""


@dataclass(frozen=True, slots=True)
class Mover:
    """A part whose designator is placed: its footprint, reference, side, and its field."""

    footprint: FootprintInstance
    ref: str
    side: str
    field: FootprintField


@dataclass(frozen=True, slots=True)
class Scene:
    """What ``gather`` finds on a board: the parts to place, the other texts to measure, and the obstacles
    and the material test per side."""

    movers: tuple[Mover, ...]
    others: tuple[tuple[str, str, TextKey, Point, Udeg, bool, bool], ...]
    """``(side, what, key, anchor, angle, mirrored, folded)`` of every other text on a silkscreen side:
    ``folded`` texts follow the upright rule of a field, the others are boxed symmetrically."""
    obstacles: Mapping[str, tuple[Obstacle, ...]]
    inside: Callable[[Rect], bool]
    boxes: Mapping[str, Rect]
    """The box of each part's own courtyard (or pads), by footprint id."""
    issues: tuple[Issue, ...]


def _turn(p: tuple[int, int], angle: Udeg) -> tuple[int, int]:
    """``p`` turned by ``angle`` as a footprint turns (``H-G-ROT-DIR``), for multiples of 90 degrees."""
    x, y = p
    quarter = (angle % FULL_TURN) // (90 * DEG)
    for _ in range(quarter):
        x, y = y, -x
    return x, y


def field_rect(ink: InkBox, angle: Udeg, mirrored: bool) -> Rect:
    """The ink rectangle of a field relative to its anchor on the board, for a board angle that is a
    multiple of 90 degrees: mirrored first, folded upright (180 as 0, 270 as 90), then turned."""
    x0, x1 = (-ink.x1, -ink.x0) if mirrored else (ink.x0, ink.x1)
    folded = angle % (180 * DEG)
    corners = [_turn(p, folded) for p in ((x0, ink.y0), (x1, ink.y1))]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return Rect(min(xs), min(ys), max(xs), max(ys))


def hull_rect(ink: InkBox, angle: Udeg) -> Rect:
    """A rectangle that holds the ink of a text however it is mirrored or kept upright: the box symmetric
    about the anchor, turned by ``angle`` and boxed again (rounded outward)."""
    mx = max(abs(ink.x0), abs(ink.x1))
    my = max(abs(ink.y0), abs(ink.y1))
    if angle % (90 * DEG) == 0:
        if (angle // (90 * DEG)) % 2:
            mx, my = my, mx
        return Rect(-mx, -my, mx, my)
    cos, sin = cos_sin_fixed(angle)
    one = 1 << TRIG_BITS
    span_x = abs(mx * cos) + abs(my * sin)
    span_y = abs(mx * sin) + abs(my * cos)
    rx, ry = -(-span_x // one) + 1, -(-span_y // one) + 1
    return Rect(-rx, -ry, rx, ry)


def _layer_side(layer: str, layers: Mapping[str, str] = SILK) -> str | None:
    for side, name in layers.items():
        if layer == name:
            return side
    return None


def _graphic_shapes(graphic: Graphic, move: Transform) -> list[Thick]:
    """The stroke (and fill) of a silkscreen graphic in the board frame, as thick shapes that hold it."""
    points = [move.apply(p) for p in graphic.points]
    width = max(graphic.width, 1)
    try:
        if graphic.kind == "line":
            return [Thick(tuple(points[:2]) if points[0] != points[1] else (points[0],), width)]
        if graphic.kind == "arc":
            core = Arc(points[0], points[1], points[2]).polygonize(ARC_TOL)
            return [Thick(core, width + 2 * ARC_TOL + 2)]
        if graphic.kind == "circle":
            circle = Circle.from_kicad(points[0], points[1])
            if graphic.filled:
                return [Thick(circle.polygonize(ARC_TOL, outer=True), width, filled=True)]
            ring = circle.polygonize(ARC_TOL, outer=True)
            return [Thick((*ring, ring[0]), width + 2 * ARC_TOL + 2)]
        if graphic.kind == "rect":
            a, b = graphic.points[0], graphic.points[1]
            corners = [move.apply(p) for p in (a, Point(b.x, a.y), b, Point(a.x, b.y))]
        else:
            corners = points
        ring = (*corners, corners[0])
        shapes = [Thick(ring, width)]
        if graphic.filled and len(corners) >= 3:
            shapes.append(Thick(tuple(corners), width, filled=True))
        return shapes
    except (GeometryError, ValueError, IndexError):
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        if not xs:
            return []
        grow = width // 2 + 1
        box = Rect(min(xs) - grow, min(ys) - grow, max(xs) + grow, max(ys) + grow)
        return [box.thick()]


def _edge_shapes(rings: Sequence[EdgeRing]) -> list[Obstacle]:
    found: list[Obstacle] = []
    for ring in rings:
        points: list[Point] = []
        count = len(ring.points)
        for index in range(count):
            start, end = ring.points[index], ring.points[(index + 1) % count]
            mid = ring.mids[index]
            if mid is None:
                points.append(start)
            else:
                try:
                    points.extend(Arc(start, mid, end).polygonize(ARC_TOL)[:-1])
                except GeometryError:
                    points.extend((start, mid))
        points.append(points[0])
        width = 2 * ARC_TOL + 2 if any(mid is not None for mid in ring.mids) else 0
        found.append(Obstacle.of(Thick(tuple(points), width), f"the board edge ({ring.name})"))
    return found


def _material(rings: Sequence[EdgeRing] | None) -> Callable[[Rect], bool]:
    """Whether a rectangle's centre lies inside an odd number of the edge's rings (the board's material);
    always true for a board without a closed edge."""
    if not rings:
        return lambda rect: True
    polygons = [
        (
            min(p.x for p in ring.points),
            min(p.y for p in ring.points),
            max(p.x for p in ring.points),
            max(p.y for p in ring.points),
            ring.points,
        )
        for ring in rings
    ]

    def inside(rect: Rect) -> bool:
        x, y = (rect.x0 + rect.x1) // 2, (rect.y0 + rect.y1) // 2
        centre = Point(x, y)
        count = sum(
            1
            for x0, y0, x1, y1, points in polygons
            if x0 <= x <= x1 and y0 <= y <= y1 and point_in_ring(centre, points) == Location.INSIDE
        )
        return count % 2 == 1

    return inside


def _field_text(field: FootprintField, component: Component | None) -> str:
    stored = field_value(field)
    if stored is not None:
        return stored
    if component is None:
        return ""
    if field.name == REFERENCE:
        return component.ref
    if field.name == "Value":
        return component.value
    return component.properties.get(field.name, "")


def _default_stroke(height: Nm) -> Nm:
    return height * STROKE_RATIO[0] // STROKE_RATIO[1]


def _key(text: str, size: Size, stroke: Nm | None, h: str = "center", v: str = "center") -> TextKey:
    thickness = _default_stroke(size.h) if stroke is None else stroke
    return TextKey(text, size.w, size.h, thickness, h, v)  # type: ignore[arg-type]


def gather(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    extents: Sequence[PlacedExtent],
    edges: Sequence[EdgeRing] | None,
    settings: Settings,
) -> Scene:
    """The parts, the other texts and the fixed obstacles of a board (see the module)."""
    board = design.board
    assert board is not None
    components = {c.id: c for c in design.circuit.components}
    altium = settings.model == "altium"
    issues: list[Issue] = []
    movers: list[Mover] = []
    others: list[tuple[str, str, TextKey, Point, Udeg, bool, bool]] = []
    obstacles: dict[str, list[Obstacle]] = {"top": [], "bottom": []}
    boxes: dict[str, Rect] = {}
    extent_of = {extent.footprint_id: extent for extent in extents}
    for footprint in board.footprints:
        component = components.get(footprint.component_id)
        ref = component.ref if component is not None else ""
        extent = extent_of.get(footprint.id)
        items = footprint_items(footprint)
        rings = extent.own if extent is not None else ()
        points = [p for ring in rings for p in ring]
        if not points:
            points = [
                p for pad in pads if pad.footprint_id == footprint.id for c in pad.copper for p in c.core
            ]
        if not points:
            points = [footprint.position]
        grow = 0
        if settings.courtyard is not None:  # the gap counts from the courtyard's ink, which is judged
            grow = max((g.width for g in items.graphics if g.layer in COURTYARD.values()), default=0)
            grow = (grow + 1) // 2
        boxes[footprint.id] = Rect(
            min(p.x for p in points) - grow,
            min(p.y for p in points) - grow,
            max(p.x for p in points) + grow,
            max(p.y for p in points) + grow,
        )
        for field in footprint.fields:
            side = _layer_side(field.layer)
            if not field.visible:
                continue
            text = _field_text(field, component)
            moving = (
                field.name == REFERENCE
                and bool(ref)
                and any(fnmatch.fnmatchcase(ref, pattern) for pattern in settings.refs)
            )
            if moving and (side is not None or field.layer.endswith(".SilkS")):
                movers.append(Mover(footprint, ref, footprint.side, field))
                continue
            if side is None or not text:
                continue
            others.append(
                (
                    side,
                    f"the {field.name} text of {ref or footprint.id}",
                    _key(text, field.size, field.thickness, field.h_justify, field.v_justify),
                    field_anchor(footprint, field),
                    field_angle(footprint, field),
                    field.mirrored,
                    True,
                )
            )
        if items.skipped:
            issues.append(
                issue(
                    "silk.item-skipped",
                    f"{ref or footprint.id} holds {len(items.skipped)} drawn item(s) that Fenolite does "
                    f"not model ({', '.join(sorted(set(items.skipped)))}); designators are not kept clear "
                    "of them",
                    where=ref or footprint.id,
                )
            )
        move = Transform.placement(footprint.position, footprint.rotation)
        for graphic in items.graphics:
            side = _layer_side(graphic.layer)
            if side is not None:  # Altium 24.5 judges a text against its own silk too (field result)
                for shape in _graphic_shapes(graphic, move):
                    obstacles[side].append(Obstacle.of(shape, f"silkscreen of {ref or footprint.id}"))
            court = _layer_side(graphic.layer, COURTYARD)
            if court is not None and settings.courtyard is not None:
                for shape in _graphic_shapes(graphic, move):
                    what = f"the courtyard of {ref or footprint.id}"
                    obstacles[court].append(Obstacle.of(shape, what, clearance=settings.courtyard))
        for text in items.texts:
            side = _layer_side(text.layer)
            if side is not None and text.text.strip():
                others.append(
                    (
                        side,
                        f"a text of {ref or footprint.id}",
                        _key(text.text, text.size, text.thickness, text.h_justify, text.v_justify),
                        move.apply(text.position),
                        (text.rotation + footprint.rotation) % FULL_TURN,
                        False,
                        False,
                    )
                )
    for graphic in board.graphics:
        side = _layer_side(graphic.layer)
        if side is not None:
            for shape in _graphic_shapes(graphic, Transform.identity()):
                obstacles[side].append(Obstacle.of(shape, "silkscreen of the board"))
    for text in board.texts:
        side = _layer_side(text.layer)
        if side is not None and text.text.strip():
            key = _key(text.text, text.size, text.thickness, text.h_justify, text.v_justify)
            others.append(
                (side, f"the board text {text.text!r}", key, text.position, text.rotation, False, False)
            )
    if altium:  # each pad's mask opening, its copper grown by its own expansion (H-A-SILK-DRC-MODEL)
        for side, pad, shape in mask_openings(design, pads, settings.board_mask):
            what = f"the mask opening of pad {pad.ref or pad.footprint_id}-{pad.number}"
            obstacles[side].append(Obstacle.of(shape, what, clearance=settings.mask_clearance))
        for pad in pads:
            name = f"pad {pad.ref or pad.footprint_id}-{pad.number}"
            if pad.hole and pad.drill and pad.kind != "np_thru_hole":  # an unplated hole is no obstacle
                for side in ("top", "bottom"):
                    obstacles[side].append(Obstacle.of(Thick(pad.hole, pad.drill), f"the hole of {name}"))
    else:
        for pad in pads:
            name = f"pad {pad.ref or pad.footprint_id}-{pad.number}"
            for side, layer in COPPER.items():
                for copper in pad.copper:
                    if copper.layer == layer:
                        obstacles[side].append(
                            Obstacle.of(Thick(copper.core, copper.width, copper.filled), name)
                        )
            if pad.hole and pad.drill:
                for side in ("top", "bottom"):
                    obstacles[side].append(Obstacle.of(Thick(pad.hole, pad.drill), f"the hole of {name}"))
    for via in board.vias:
        for side in ("top", "bottom"):
            obstacles[side].append(Obstacle.of(Thick((via.position,), via.drill), "a via hole"))
    for hole in board.holes if not altium else ():  # a board hole is unplated
        core = (hole.position,)
        if hole.length is not None:
            reach = (hole.length - hole.drill) // 2
            ends = Transform.placement(hole.position, hole.rotation)
            core = (ends.apply(Point(-reach, 0)), ends.apply(Point(reach, 0)))
        for side in ("top", "bottom"):
            obstacles[side].append(Obstacle.of(Thick(core, hole.drill), "a board hole"))
    if edges:
        for found in _edge_shapes(edges):
            for side in ("top", "bottom"):
                obstacles[side].append(found)
    else:
        issues.append(issue("silk.no-outline", "the board has no closed edge, so no text is kept inside it"))
    return Scene(
        movers=tuple(movers),
        others=tuple(others),
        obstacles={side: tuple(found) for side, found in obstacles.items()},
        inside=_material(edges),
        boxes=boxes,
        issues=tuple(issues),
    )


def mask_openings(
    design: Design, pads: Sequence[BoardPad], board_mask: Nm
) -> list[tuple[str, BoardPad, Thick]]:
    """``(side, pad, shape)`` of each pad's solder-mask opening: its copper on the side grown by its own mask
    margin, else ``board_mask``. A pad without copper on the side that opens the mask there (an unplated
    pad) opens its hole so grown: KiCad 10 and Altium judge silkscreen against it (field result,
    2026-11-17). An Altium import names no mask layer on a pad: each outer copper layer then has one."""
    from fenolite.silk.clip import has_mask  # noqa: PLC0415 - clip imports this module

    board = design.board
    assert board is not None
    margins = {pad.id: pad.mask_margin for fp in board.footprints for pad in fp.pads}
    found: list[tuple[str, BoardPad, Thick]] = []
    for pad in pads:
        bare = not any("Mask" in layer for layer in pad.layers)
        own = margins.get(pad.pad_id)
        grow = max(own if own is not None else board_mask, 0)
        for side, layer in COPPER.items():
            if not (bare or has_mask(pad.layers, side)):
                continue
            coppers = [c for c in pad.copper if c.layer == layer]
            for copper in coppers:
                found.append((side, pad, Thick(copper.core, copper.width + 2 * grow, copper.filled)))
            if not coppers and not bare and pad.hole and pad.drill:
                found.append((side, pad, Thick(pad.hole, pad.drill + 2 * grow)))
    return found


def looks_of(mover: Mover, settings: Settings) -> list[tuple[TextKey, Udeg]]:
    """``(ink key, board angle)`` of every look of a mover, largest height first."""
    field = mover.field
    if settings.heights is not None:
        heights = sorted(set(settings.heights), reverse=True)
    else:
        own = field.size.h
        floor = settings.min_size if settings.min_size is not None else settings.min_height
        step = max(settings.size_step, 1)
        heights = [h for h in range(own, floor, -step)] + ([floor] if own >= floor else [])
        heights = sorted(set(heights), reverse=True) or [own]
    found: list[tuple[TextKey, Udeg]] = []
    for height in heights:
        width = max(1, field.size.w * height // field.size.h)
        given = field.thickness if field.thickness is not None else _default_stroke(field.size.h)
        stroke = max(settings.min_stroke, given * height // field.size.h)
        stroke = min(stroke, min(width, height) // 4)
        for angle in settings.angles:
            found.append((TextKey(mover.ref, width, height, stroke), angle))
    return found


def ink_keys(scene: Scene, settings: Settings) -> list[TextKey]:
    """Every text whose ink the search needs."""
    keys = [key for mover in scene.movers for key, _ in looks_of(mover, settings)]
    keys.extend(other[2] for other in scene.others)
    keys.extend(_current_key(mover) for mover in scene.movers)
    return keys


def _current_key(mover: Mover) -> TextKey:
    field = mover.field
    return _key(mover.ref, field.size, field.thickness, field.h_justify, field.v_justify)


def altium_box(key: TextKey) -> InkBox | None:
    """The box Altium 24.5's DRC judges a stroke text by (``H-A-SILK-DRC-MODEL``), in the text's reading
    frame relative to its anchor (Y down). The record holds the lower-left corner that
    ``backends.altium.pcbdoc.text_corner`` writes: the offset between the estimated ink of the text's
    justification and that of the same text justified left and bottom. From there the box reaches half a
    stroke left and down, ``characters * height - height / 3 + 2 * stroke`` along the text (the font's
    advance is about one height per character) and ``height + 1.5 * stroke`` up."""
    if not key.text:
        return None
    own = estimate(key)
    corner = estimate(dataclasses.replace(key, h_justify="left", v_justify="bottom"))
    if own is None or corner is None:
        return None
    dx, dy = own.x0 - corner.x0, own.y1 - corner.y1
    h, s = key.height, key.stroke
    # shortcut: one line of text; a multi-line text is boxed by its longest line and one height
    n = max(len(line) for line in key.text.split("\n"))
    return InkBox(dx - s // 2, dy - h - 3 * s // 2, dx + n * h - h // 3 + 2 * s, dy + s // 2)


def text_box(key: TextKey, inks: Mapping[TextKey, Ink], settings: Settings | None) -> InkBox | None:
    """The box a model judges a text by, in its reading frame: its ink, and in the ``altium`` model also the
    box Altium measures (``altium_box``), so that both KiCad's and Altium's DRC find it clear."""
    ink = inks[key].box
    if settings is None or settings.model != "altium":
        return ink
    box = altium_box(key)
    if ink is None or box is None:
        return ink or box
    return InkBox(min(ink.x0, box.x0), min(ink.y0, box.y0), max(ink.x1, box.x1), max(ink.y1, box.y1))


def board_rect(box: InkBox, angle: Udeg, mirrored: bool, folded: bool, settings: Settings | None) -> Rect:
    """The rectangle of a text's box relative to its anchor on the board: ``field_rect`` for a field at a
    multiple of 90 degrees (in the ``altium`` model only at 0 or 90, as Altium does not keep a text
    upright), else ``hull_rect``."""
    upright = settings is None or settings.model != "altium" or angle in (0, 90 * DEG)
    if folded and angle % (90 * DEG) == 0 and upright:
        return field_rect(box, angle, mirrored)
    return hull_rect(box, angle)


def kind_of(blocker: str) -> str:
    """The kind of ``KINDS`` of what a ``silk.no-place`` names (change c0493)."""
    for head, kind in (
        ("pad ", "pad"),
        ("the mask opening", "mask"),
        ("the hole of", "hole"),
        ("a via hole", "hole"),
        ("a board hole", "hole"),
        ("silkscreen of", "silk"),
        ("the courtyard", "courtyard"),
        ("the board edge (", "edge"),
    ):
        if blocker.startswith(head):
            return kind
    if blocker in ("the board edge", "no candidate", ""):
        return "outside"
    return "text"


def _other_rects(
    scene: Scene, inks: Mapping[TextKey, Ink], settings: Settings | None = None
) -> list[tuple[str, str, Rect]]:
    found: list[tuple[str, str, Rect]] = []
    for side, what, key, anchor, angle, mirrored, folded in scene.others:
        box = text_box(key, inks, settings)
        if box is None:
            continue
        found.append(
            (side, what, board_rect(box, angle, mirrored, folded, settings).moved(anchor.x, anchor.y))
        )
    return found


def _axis(box: Rect) -> Udeg:
    return 90 * DEG if box.y1 - box.y0 > box.x1 - box.x0 else 0


def groups_of(movers: Sequence[Mover]) -> list[list[str]]:
    """Keys of identical parts (footprint, angle, side, field size) whose positions share a row (one y) or
    a column (one x), two or more each; a part joins its row first."""
    found: list[list[str]] = []
    taken: set[str] = set()
    kinds: dict[tuple[str, Udeg, str, Size], list[Mover]] = {}
    for mover in movers:
        fp = mover.footprint
        kinds.setdefault((fp.lib_ref, fp.rotation, mover.side, mover.field.size), []).append(mover)
    for members in kinds.values():
        for axis in ("y", "x"):
            lines: dict[int, list[Mover]] = {}
            for mover in members:
                if mover.footprint.id in taken:
                    continue
                coordinate = mover.footprint.position.y if axis == "y" else mover.footprint.position.x
                lines.setdefault(coordinate, []).append(mover)
            for line in lines.values():
                if len(line) >= 2:
                    keys = [m.footprint.id for m in sorted(line, key=lambda m: natural(m.ref))]
                    found.append(keys)
                    taken.update(keys)
    return found


@dataclass(frozen=True, slots=True)
class Outcome:
    """The placed design, the plan, the issues and the rows of ``result.placements``."""

    design: Design
    plan: Plan
    rows: tuple[dict[str, object], ...]
    issues: tuple[Issue, ...]


def place_designators(
    design: Design, scene: Scene, inks: Mapping[TextKey, Ink], settings: Settings
) -> Outcome:
    """Search and write the designators of ``scene`` (see the module)."""
    board = design.board
    assert board is not None
    issues = list(scene.issues)
    fields: dict[str, Field] = {}
    others = _other_rects(scene, inks, settings)
    for side in ("top", "bottom"):
        extra = tuple(Obstacle.of(rect.thick(), what) for s, what, rect in others if s == side)
        fields[side] = Field((*scene.obstacles[side], *extra), settings.clearance, scene.inside)
    parts: list[Part] = []
    for mover in scene.movers:
        looks: list[Look] = []
        for key, angle in looks_of(mover, settings):
            box = text_box(key, inks, settings)
            if box is None:
                continue
            rect = field_rect(box, angle, mover.side == "bottom")
            looks.append(Look(angle, key.width, key.height, key.stroke, rect))
        current: Choice | None = None
        where: tuple[str, Rect] | None = None
        box = text_box(_current_key(mover), inks, settings)
        angle = field_angle(mover.footprint, mover.field)
        side = _layer_side(mover.field.layer)
        if box is not None and side is not None:
            anchor = field_anchor(mover.footprint, mover.field)
            square = angle % (90 * DEG) == 0
            rect = board_rect(box, angle, mover.field.mirrored, True, settings).moved(anchor.x, anchor.y)
            where = (side, rect)
            if square and side == mover.side:
                size = mover.field.size
                look = Look(angle, size.w, size.h, _current_key(mover).stroke, rect)
                current = Choice(anchor, look, rect, 0, (-1, -1, -1))
        box = scene.boxes[mover.footprint.id]
        parts.append(
            Part(mover.footprint.id, mover.ref, mover.side, box, _axis(box), tuple(looks), current, where)
        )
    plan = arrange(
        parts,
        fields,
        gap=settings.gap,
        groups=[] if settings.keep else groups_of(scene.movers),
        keep=settings.keep,
        natural=natural,
        reach=settings.gap + settings.reach,
        step=settings.step,
        over_body=settings.over_body,
    )
    by_key = {mover.footprint.id: mover for mover in scene.movers}
    footprints = list(board.footprints)
    index = {fp.id: i for i, fp in enumerate(footprints)}
    rows: list[dict[str, object]] = []
    for key, choice in plan.placed.items():
        mover = by_key[key]
        look = choice.look
        placed = set_field(
            footprints[index[key]],
            REFERENCE,
            anchor=choice.anchor,
            angle=look.angle,
            layer=SILK[mover.side],
            size=Size(look.width, look.height),
            thickness=look.stroke,
            justify=("center", "center"),
            mirrored=mover.side == "bottom",
        )
        footprints[index[key]] = placed
    for mover in sorted(scene.movers, key=lambda m: natural(m.ref)):
        key = mover.footprint.id
        choice = plan.placed.get(key)
        if choice is not None:
            rows.append(
                {
                    "ref": mover.ref,
                    "side": mover.side,
                    "status": "placed",
                    "x": choice.anchor.x,
                    "y": choice.anchor.y,
                    "angle": choice.look.angle // DEG,
                    "height": choice.look.height,
                    "stroke": choice.look.stroke,
                    "where": ("above", "below", "left", "right", "over")[choice.slot[0]],
                }
            )
        elif mover.ref in plan.kept:
            rows.append({"ref": mover.ref, "side": mover.side, "status": "kept"})
        else:
            blocker = plan.blocked.get(key, "")
            kind = kind_of(blocker)
            rows.append(
                {"ref": mover.ref, "side": mover.side, "status": "unplaced", "blocker": blocker, "kind": kind}
            )
            issues.append(
                issue(
                    "silk.no-place",
                    f"no free place for the designator of {mover.ref}: its best candidate meets {blocker} "
                    f"({kind}); the text stays where it was",
                    where=mover.ref,
                    hint="allow smaller --sizes, both --angles or a smaller --clearance, or move the part",
                )
            )
    placed = dataclasses.replace(design, board=dataclasses.replace(board, footprints=tuple(footprints)))
    return Outcome(placed, plan, tuple(rows), tuple(issues))


def silkscreen_ink(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    extents: Sequence[PlacedExtent],
    edges: Sequence[EdgeRing] | None,
    side: str,
) -> tuple[tuple[Thick, str], ...]:
    """The silkscreen ink of one side of a board, as thick shapes with what each is: every stroke of a
    footprint or of the board, and the box of every visible text, estimated from the glyph table (the
    estimate only grows). For the test-point placement of change c0229: a probe's mask opening keeps off
    the ink, so that KiCad's ``silk_over_copper`` finds nothing new."""
    scene = gather(design, pads=pads, extents=extents, edges=edges, settings=Settings(refs=()))
    inks = ink_boxes(other[2] for other in scene.others)
    found = [(o.shape, o.what) for o in scene.obstacles[side] if o.what.startswith("silkscreen of")]
    found += [(rect.thick(), what) for at, what, rect in _other_rects(scene, inks) if at == side]
    return tuple(found)


def check_designators(
    design: Design,
    scene: Scene,
    inks: Mapping[TextKey, Ink],
    settings: Settings,
    keys: Iterable[str],
) -> list[Issue]:
    """Judge the designators of the footprints ``keys`` as ``design`` holds them (see the module)."""
    board = design.board
    assert board is not None
    wanted = set(keys)
    movers = {m.footprint.id: m for m in scene.movers}
    others = _other_rects(scene, inks, settings)
    found: list[Issue] = []
    texts: dict[str, list[tuple[str, Rect]]] = {"top": [], "bottom": []}
    for footprint in board.footprints:
        mover = movers.get(footprint.id)
        if mover is None:
            continue
        field = next((f for f in footprint.fields if f.name == REFERENCE), None)
        if field is None:
            continue
        held = _key(mover.ref, field.size, field.thickness, field.h_justify, field.v_justify)
        side = _layer_side(field.layer)
        box = text_box(held, inks, settings) if held in inks else None
        if box is None or side is None:
            continue
        angle = field_angle(footprint, field)
        anchor = field_anchor(footprint, field)
        rect = board_rect(box, angle, field.mirrored, True, settings).moved(anchor.x, anchor.y)
        texts[side].append((footprint.id, rect))
        if footprint.id not in wanted:
            continue
        problems: list[str] = []
        if side != mover.side:
            problems.append(f"it is on {field.layer}, not on the silkscreen of its side")
        if angle not in (0, 90 * DEG):
            problems.append(f"it reads at {angle / DEG:g} degrees, not 0 or 90")
        if field.mirrored != (mover.side == "bottom"):
            problems.append(
                "it is mirrored on the wrong side" if field.mirrored else "it is not mirrored on the bottom"
            )
        stroke = field.thickness if field.thickness is not None else _default_stroke(field.size.h)
        if field.size.h < settings.min_height or stroke < settings.min_stroke:
            small = (
                f"its height {format_length(field.size.h)} or stroke {format_length(stroke)} is below "
                f"{format_length(settings.min_height)} or {format_length(settings.min_stroke)}"
            )
            if field.size == mover.field.size and field.thickness == mover.field.thickness:
                # the text keeps the board's own size: a finding the board already had, not the search's
                found.append(
                    issue(
                        "silk.below-minimum",
                        f"the designator of {mover.ref} keeps its own size: {small}; it is written as it was",
                        where=mover.ref,
                        hint="enlarge the text in the source, or lower the board's minimum text height",
                    )
                )
            else:
                problems.append(small)
        here = Field(
            (*scene.obstacles[side], *(Obstacle.of(r.thick(), what) for s, what, r in others if s == side)),
            settings.clearance,
            scene.inside,
        )
        blocker = here.static_blocker(rect, footprint.id)
        if blocker is not None:
            problems.append(f"it is within {format_length(settings.clearance)} of {blocker}")
        for problem in problems:
            found.append(
                issue(
                    "silk.check-failed",
                    f"the placed designator of {mover.ref} fails its check: {problem}; nothing is written",
                    where=mover.ref,
                    hint="report it: every candidate is checked before it is chosen",
                )
            )
    limit = settings.clearance * settings.clearance
    for side, placed in texts.items():
        for i, (key, rect) in enumerate(placed):
            for other_key, other in placed[i + 1 :]:
                if (key in wanted or other_key in wanted) and gap2(rect, other) < limit:
                    a, b = movers[key].ref, movers[other_key].ref
                    found.append(
                        issue(
                            "silk.check-failed",
                            f"the designators of {a} and {b} on the {side} are closer than "
                            f"{format_length(settings.clearance)}; nothing is written",
                            where=f"{a}, {b}",
                            hint="report it: every candidate is checked before it is chosen",
                        )
                    )
    return found


@dataclass(frozen=True, slots=True)
class SilkFinding:
    """One silkscreen clearance finding of ``judge_silk`` (change c0498): its code, the side, the two items
    (a silk item's locator, a pad's ``REF-PIN`` or ``edge``), the closest place, the gap and the limit."""

    code: str
    side: str
    items: tuple[str, str]
    at: Point
    gap: Nm
    limit: Nm
    message: str


def _locator(entity: Graphic | FootprintField | Text, fallback: str) -> str:
    source = entity.provenance
    return source.locator if source is not None and source.locator else fallback


def _silk_items(design: Design) -> list[tuple[str, str, str, Thick, bool]]:
    """``(side, name, owner, shape, is_text)`` of every silkscreen stroke and visible text of a board, in the
    board frame; a text is its box in the ``altium`` model (``text_box``)."""
    board = design.board
    assert board is not None
    settings = Settings(model="altium")
    found: list[tuple[str, str, str, Thick, bool]] = []
    texts: list[tuple[str, str, str, TextKey, Point, Udeg, bool, bool]] = []
    components = {c.id: c for c in design.circuit.components}
    for footprint in board.footprints:
        move = Transform.placement(footprint.position, footprint.rotation)
        for graphic in footprint.graphics:
            side = _layer_side(graphic.layer)
            if side is not None:
                name = _locator(graphic, graphic.id)
                found += [
                    (side, name, footprint.id, shape, False) for shape in _graphic_shapes(graphic, move)
                ]
        for field in footprint.fields:
            side = _layer_side(field.layer)
            shown = _field_text(field, components.get(footprint.component_id))
            if side is None or not field.visible or not shown.strip():
                continue
            key = _key(shown, field.size, field.thickness, field.h_justify, field.v_justify)
            anchor, angle = field_anchor(footprint, field), field_angle(footprint, field)
            texts.append(
                (side, _locator(field, field.id), footprint.id, key, anchor, angle, field.mirrored, True)
            )
        for text in footprint.texts:
            side = _layer_side(text.layer)
            if side is not None and text.text.strip():
                key = _key(text.text, text.size, text.thickness, text.h_justify, text.v_justify)
                angle = (text.rotation + footprint.rotation) % FULL_TURN
                at = move.apply(text.position)
                texts.append((side, _locator(text, text.id), footprint.id, key, at, angle, False, False))
    for graphic in board.graphics:
        side = _layer_side(graphic.layer)
        if side is not None:
            name = _locator(graphic, graphic.id)
            found += [
                (side, name, "", shape, False) for shape in _graphic_shapes(graphic, Transform.identity())
            ]
    for text in board.texts:
        side = _layer_side(text.layer)
        if side is not None and text.text.strip():
            key = _key(text.text, text.size, text.thickness, text.h_justify, text.v_justify)
            texts.append((side, _locator(text, text.id), "", key, text.position, text.rotation, False, False))
    inks = ink_boxes(entry[3] for entry in texts)
    for side, name, owner, key, anchor, angle, mirrored, folded in texts:
        box = text_box(key, inks, settings)
        if box is None:
            continue
        rect = board_rect(box, angle, mirrored, folded, settings).moved(anchor.x, anchor.y)
        found.append((side, name, owner, rect.thick(), True))
    return found


def judge_silk(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    edges: Sequence[EdgeRing] | None,
    silk: Nm | None,
    mask: Nm | None,
    edge: Nm | None,
    board_mask: Nm = 0,
) -> list[SilkFinding]:
    """The silkscreen clearance findings of a whole board in the ``altium`` model (change c0498, design D4):
    ``silk.clearance`` for a text closer than ``silk`` to another silk item that is not of its own component,
    ``silk.mask-clearance`` for a silk item closer than ``mask`` to a pad's mask opening, and
    ``silk.edge-clearance`` for a silk item closer than ``edge`` to an edge ring. A limit of ``None`` judges
    nothing. Two strokes are not judged against each other: the stored violations of the public documents
    pair a text with a stroke only. A pad's mask opening is its copper grown by its own mask margin, else
    ``board_mask``, as ``gather`` grows it."""
    from fenolite.geometry import SpatialIndex, thick_bbox, thick_closer_than, thick_gap_floor, thick_witness

    items = _silk_items(design)
    openings = [
        (side, f"{pad.ref or pad.footprint_id}-{pad.number}", shape)
        for side, pad, shape in mask_openings(design, pads, board_mask)
    ]
    rims = [(side, "edge", o.shape) for o in _edge_shapes(edges or ()) for side in ("top", "bottom")]
    found: list[SilkFinding] = []

    def near(
        code: str,
        limit: Nm | None,
        shapes: Sequence[tuple[str, str, Thick]],
        pairs: Callable[[int, int], bool],
    ) -> None:
        if limit is None or limit <= 0:
            return
        index = SpatialIndex[int].build((thick_bbox(shape), n) for n, (_, _, shape) in enumerate(shapes))
        for a, (side, name, shape) in enumerate(items_of):
            for b in sorted(index.query(thick_bbox(shape).inflate(limit))):
                other_side, other, obstacle = shapes[b]
                if other_side != side or not pairs(a, b) or not thick_closer_than(shape, obstacle, limit):
                    continue
                gap = thick_gap_floor(shape, obstacle)
                at = thick_witness(shape, obstacle)
                found.append(
                    SilkFinding(
                        code, side, (name, other), at, gap, limit,
                        f"{name} is {format_length(gap)} from {other} on the {side} silkscreen; the "
                        f"clearance is {format_length(limit)}",
                    )
                )  # fmt: skip

    items_of = [(side, name, shape) for side, name, _, shape, _ in items]
    near(
        "silk.clearance", silk, items_of,
        lambda a, b: a != b and items[a][4] and (not items[b][4] or a < b)
        and not (items[a][2] and items[a][2] == items[b][2]),
    )  # fmt: skip
    near("silk.mask-clearance", mask, openings, lambda _a, _b: True)
    near("silk.edge-clearance", edge, rims, lambda _a, _b: True)
    found.sort(key=lambda f: (f.code, f.side, f.items, f.at))
    return found


__all__ = [
    "ALTIUM_HYPOTHESIS",
    "altium_box",
    "board_rect",
    "DEFAULT_CLEARANCE",
    "DEFAULT_GAP",
    "DEFAULT_MASK_CLEARANCE",
    "DEFAULT_REACH",
    "DEFAULT_SIZE_STEP",
    "KINDS",
    "MIN_HEIGHT",
    "MIN_STROKE",
    "Mover",
    "Outcome",
    "Scene",
    "Settings",
    "SilkFinding",
    "check_designators",
    "field_rect",
    "gather",
    "groups_of",
    "judge_silk",
    "hull_rect",
    "ink_keys",
    "kind_of",
    "looks_of",
    "mask_openings",
    "text_box",
    "natural",
    "place_designators",
    "silkscreen_ink",
]
