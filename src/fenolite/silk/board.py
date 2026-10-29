# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designators of a KiCad board placed and checked (capability silkscreen-layout, "Designator placement"
and "Placed designators checked"; change c0212; user guide ``docs/assembly.md``, "Designators").

``place_designators`` gathers, per silkscreen side, what a designator must keep ``clearance`` from: the
copper of the pads on that side's outer layer, every drilled hole (pad, via and board holes), the
silkscreen strokes of the board and of the footprints, the ink of every other text on the side, the
courtyards of the other parts, and the board edge (outline, cut-outs and slots). It measures the ink of
every text (``silk.extents``), runs the search of ``silk.layout`` and writes each chosen place into the
part's ``Reference`` field: anchor, angle 0 or 90 degrees on the board, size, stroke, centred
justification, and mirrored on the bottom side.

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
from fenolite.model.board import FootprintField, FootprintInstance, Graphic
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.silk.codes import issue
from fenolite.silk.extents import Ink, InkBox, TextKey, ink_boxes
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


def _layer_side(layer: str) -> str | None:
    for side, name in SILK.items():
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
    polygons = [ring.points for ring in rings]

    def inside(rect: Rect) -> bool:
        centre = Point((rect.x0 + rect.x1) // 2, (rect.y0 + rect.y1) // 2)
        count = sum(1 for points in polygons if point_in_ring(centre, points) == Location.INSIDE)
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
        rings = extent.own if extent is not None else ()
        points = [p for ring in rings for p in ring]
        if not points:
            points = [
                p for pad in pads if pad.footprint_id == footprint.id for c in pad.copper for p in c.core
            ]
        if not points:
            points = [footprint.position]
        boxes[footprint.id] = Rect(
            min(p.x for p in points),
            min(p.y for p in points),
            max(p.x for p in points),
            max(p.y for p in points),
        )
        if extent is not None:
            for side in ("top", "bottom"):
                face = extent.front if side == "top" else extent.back
                for ring in face:
                    try:
                        shape = Thick(ring, 0, filled=True)
                    except (GeometryError, ValueError):  # a ring the kernel refuses: its outline only
                        shape = Thick((*ring, ring[0]), 0)
                    obstacles[side].append(
                        Obstacle.of(shape, f"the courtyard of {ref or footprint.id}", footprint.id)
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
        items = footprint_items(footprint)
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
            if side is not None:
                for shape in _graphic_shapes(graphic, move):
                    obstacles[side].append(Obstacle.of(shape, f"silkscreen of {ref or footprint.id}"))
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
    for pad in pads:
        name = f"pad {pad.ref or pad.footprint_id}-{pad.number}"
        for side, layer in COPPER.items():
            for copper in pad.copper:
                if copper.layer == layer:
                    obstacles[side].append(Obstacle.of(Thick(copper.core, copper.width, copper.filled), name))
        if pad.hole and pad.drill:
            for side in ("top", "bottom"):
                obstacles[side].append(Obstacle.of(Thick(pad.hole, pad.drill), f"the hole of {name}"))
    for via in board.vias:
        for side in ("top", "bottom"):
            obstacles[side].append(Obstacle.of(Thick((via.position,), via.drill), "a via hole"))
    for hole in board.holes:
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


def looks_of(mover: Mover, settings: Settings) -> list[tuple[TextKey, Udeg]]:
    """``(ink key, board angle)`` of every look of a mover, largest height first."""
    field = mover.field
    if settings.heights is not None:
        heights = sorted(set(settings.heights), reverse=True)
    else:
        own = field.size.h
        heights = [own] + ([settings.min_height] if own > settings.min_height else [])
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


def _other_rects(scene: Scene, inks: Mapping[TextKey, Ink]) -> list[tuple[str, str, Rect]]:
    found: list[tuple[str, str, Rect]] = []
    for side, what, key, anchor, angle, mirrored, folded in scene.others:
        ink = inks[key].box
        if ink is None:
            continue
        if folded and angle % (90 * DEG) == 0:
            rect = field_rect(ink, angle, mirrored)
        else:
            rect = hull_rect(ink, angle)
        found.append((side, what, rect.moved(anchor.x, anchor.y)))
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
    others = _other_rects(scene, inks)
    for side in ("top", "bottom"):
        extra = tuple(Obstacle.of(rect.thick(), what) for s, what, rect in others if s == side)
        fields[side] = Field((*scene.obstacles[side], *extra), settings.clearance, scene.inside)
    parts: list[Part] = []
    for mover in scene.movers:
        looks: list[Look] = []
        for key, angle in looks_of(mover, settings):
            ink = inks[key].box
            if ink is None:
                continue
            looks.append(
                Look(angle, key.width, key.height, key.stroke, field_rect(ink, angle, mover.side == "bottom"))
            )
        current: Choice | None = None
        where: tuple[str, Rect] | None = None
        ink = inks[_current_key(mover)].box
        angle = field_angle(mover.footprint, mover.field)
        side = _layer_side(mover.field.layer)
        if ink is not None and side is not None:
            anchor = field_anchor(mover.footprint, mover.field)
            square = angle % (90 * DEG) == 0
            rect = (field_rect(ink, angle, mover.field.mirrored) if square else hull_rect(ink, angle)).moved(
                anchor.x, anchor.y
            )
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
                    "where": ("above", "below", "left", "right")[choice.slot[0]],
                }
            )
        elif mover.ref in plan.kept:
            rows.append({"ref": mover.ref, "side": mover.side, "status": "kept"})
        else:
            blocker = plan.blocked.get(key, "")
            rows.append({"ref": mover.ref, "side": mover.side, "status": "unplaced", "blocker": blocker})
            issues.append(
                issue(
                    "silk.no-place",
                    f"no free place for the designator of {mover.ref}: its best candidate meets {blocker}; "
                    "the text stays where it was",
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
    others = _other_rects(scene, inks)
    found: list[Issue] = []
    texts: dict[str, list[tuple[str, Rect]]] = {"top": [], "bottom": []}
    for footprint in board.footprints:
        mover = movers.get(footprint.id)
        if mover is None:
            continue
        field = next((f for f in footprint.fields if f.name == REFERENCE), None)
        if field is None:
            continue
        held = inks.get(_key(mover.ref, field.size, field.thickness, field.h_justify, field.v_justify))
        side = _layer_side(field.layer)
        if held is None or held.box is None or side is None:
            continue
        angle = field_angle(footprint, field)
        anchor = field_anchor(footprint, field)
        rect = (
            field_rect(held.box, angle, field.mirrored)
            if angle % (90 * DEG) == 0
            else hull_rect(held.box, angle)
        ).moved(anchor.x, anchor.y)
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
            problems.append(
                f"its height {format_length(field.size.h)} or stroke {format_length(stroke)} is below "
                f"{format_length(settings.min_height)} or {format_length(settings.min_stroke)}"
            )
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


__all__ = [
    "DEFAULT_CLEARANCE",
    "DEFAULT_GAP",
    "MIN_HEIGHT",
    "MIN_STROKE",
    "Mover",
    "Outcome",
    "Scene",
    "Settings",
    "check_designators",
    "field_rect",
    "gather",
    "groups_of",
    "hull_rect",
    "ink_keys",
    "looks_of",
    "natural",
    "place_designators",
    "silkscreen_ink",
]
