# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Review findings drawn on a board by the viewer (capability board-viewer, "Review findings"; change c0193).

These are aids for a person reviewing the board, not a design rule check: ``fenolite check`` and the native
tool judge. Every group is reported with its count, title, colour and a note that names its rule and its
model, so that a zero is a result. Lengths are nanometres of the board frame; the items are overlay items of
the scene, in micrometres.

* Corners (the 45° routing style):
  - two free tracks of one copper layer that share an end point, with no other track, arc or via ending
    there, turning more than 90° (``corner_acute``), 90° (``corner_90``: a straight track may turn 90° on
    purpose, so these are apart) or between 45° and 90° (``corner_mid``); a corner inside a pad's copper or
    a via on that layer is hidden by it and not listed;
  - a track whose direction is more than 0.5° from a multiple of 45° (``track_angle``);
  - a vertex of a zone outline with an interior angle below 134° (``corner_zone``), where a fill of the zone
    lies within 50 µm of it or the zone holds no fill, and not inside a pad.
* Silkscreen, on each side: an item closer than the silk gap to a mask opening (``silk_mask``); a text closer
  than the gap to another item (``silk_silk``); an item outside the board ring, in a cut-out, or closer than
  the gap to an edge (``silk_edge``). Items are graphics, texts and visible fields; a text is the box of its
  ink as the page draws it (for an Altium board, the scene's convention: lower-left anchor, glyph two thirds
  of the height). Openings are the pads' copper on the side's copper layer grown by the mask expansion (the
  pad's own mask layers, or for a board without mask layers an SMD pad on its side and a through-hole pad on
  both), and the untented vias.
* Copper outside the board (``copper_out``): pad copper, tracks, arcs, vias and fill polygons with no core
  point inside the board ring, or all of them in a cut-out, one finding per net and cluster (items within 2
  mm).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from fenolite.backends.base import BoardFrame, BoardPad, EdgeRing
from fenolite.core.coords import Point
from fenolite.geometry import (
    BBox,
    GeometryError,
    Location,
    SpatialIndex,
    Thick,
    point_in_ring,
    rotate_point,
    thick_bbox,
    thick_closer_than,
    thick_gap_floor,
    thick_touch,
    thick_witness,
)
from fenolite.model.board import Board, FootprintInstance, Graphic
from fenolite.model.design import Design

GROUPS: dict[str, tuple[str, str]] = {
    "corner_acute": ("Tracks: acute corner", "#ff3030"),
    "corner_90": ("Tracks: 90° corner", "#ff9f1a"),
    "corner_mid": ("Tracks: corner between 45° and 90°", "#ffcc33"),
    "track_angle": ("Tracks off 0/45/90°", "#e8e83a"),
    "corner_zone": ("Zone outline corner over 45°", "#ff5ad1"),
    "silk_mask": ("Silkscreen near a mask opening", "#00e5ff"),
    "silk_silk": ("Silkscreen: text near other silkscreen", "#7fd3ff"),
    "silk_edge": ("Silkscreen outside or near the edge", "#b78cff"),
    "copper_out": ("Copper outside the board", "#ff6060"),
}
"""Every group, in panel order: id → (title, colour)."""
MAX_ITEMS = 400
"""The items kept per group; the note says when more were found."""
ANGLE_TOL_DEG = 0.5
ZONE_TOL_DEG = 1.0
FILL_NEAR_NM = 50_000
CLUSTER_NM = 2_000_000
ARC_STEP_DEG = 5.0


@dataclass
class Review:
    """The findings: overlay items (micrometres) and one record per group of ``GROUPS``."""

    items: list[dict[str, Any]] = field(default_factory=lambda: [])
    groups: list[dict[str, Any]] = field(default_factory=lambda: [])


def _um(v: int | float) -> int:
    return round(v / 1000)


def _mm(v: int | float) -> str:
    return f"{v / 1e6:.3f}"


def _item(
    group: str, kind: str, pts: Iterable[Point], label: str, layer: str | None, box: BBox | None = None
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "group": group,
        "kind": kind,
        "pts": [[_um(p.x), _um(p.y)] for p in pts],
        "label": label,
        "layer": layer,
        "color": GROUPS[group][1],
    }
    if box is not None:
        out["bbox"] = [_um(box.x0), _um(box.y0), _um(box.x1), _um(box.y1)]
    return out


def _thick(core: Sequence[Point], width: int, filled: bool = False) -> Thick | None:
    clean: list[Point] = []
    for p in core:
        if not clean or clean[-1] != p:
            clean.append(p)
    if filled:
        while len(clean) > 1 and clean[0] == clean[-1]:
            clean.pop()
    try:
        return Thick(tuple(clean), max(width, 0 if len(clean) > 1 or filled else 2), filled)
    except (GeometryError, ValueError):
        return None


def _index_of(boxes: Iterable[BBox]) -> SpatialIndex[int]:
    """A spatial index of ``boxes`` whose payloads are their positions."""
    return SpatialIndex[int].build((box, k) for k, box in enumerate(boxes))


def _grow(box: BBox, by: int) -> BBox:
    return BBox(box.x0 - by, box.y0 - by, box.x1 + by, box.y1 + by)


def _arc_points(a: Point, m: Point, b: Point) -> list[Point]:
    """A polyline of the arc through ``a``, ``m``, ``b`` (a chord every 5° at most)."""
    x1, y1, x2, y2, x3, y3 = a.x, a.y, m.x, m.y, b.x, b.y
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if d == 0:
        return [a, b]
    q1, q2, q3 = x1 * x1 + y1 * y1, x2 * x2 + y2 * y2, x3 * x3 + y3 * y3
    cx = (q1 * (y2 - y3) + q2 * (y3 - y1) + q3 * (y1 - y2)) / d
    cy = (q1 * (x3 - x2) + q2 * (x1 - x3) + q3 * (x2 - x1)) / d
    r = math.hypot(x1 - cx, y1 - cy)
    t1, tm, t3 = (math.atan2(y - cy, x - cx) for x, y in ((x1, y1), (x2, y2), (x3, y3)))
    turn = 2 * math.pi
    sweep = (t3 - t1) % turn
    if (tm - t1) % turn > sweep:
        sweep -= turn
    n = max(2, math.ceil(abs(math.degrees(sweep)) / ARC_STEP_DEG))
    out = [a]
    for k in range(1, n):
        t = t1 + sweep * k / n
        out.append(Point(round(cx + r * math.cos(t)), round(cy + r * math.sin(t))))
    out.append(b)
    return out


def _ring_points(ring: EdgeRing) -> list[Point]:
    out: list[Point] = []
    n = len(ring.points)
    for i, p in enumerate(ring.points):
        mid = ring.mids[i] if i < len(ring.mids) else None
        if mid is None:
            out.append(p)
        else:
            out += _arc_points(p, mid, ring.points[(i + 1) % n])[:-1]
    return out


def _place(fp: FootprintInstance) -> Callable[[Point], Point]:
    def place(p: Point) -> Point:
        q = rotate_point(p, fp.rotation)
        return Point(fp.position.x + q.x, fp.position.y + q.y)

    return place


def _same(p: Point) -> Point:
    return p


def _graphic_shapes(g: Graphic, place: Callable[[Point], Point]) -> list[Thick]:
    pts = [place(p) for p in g.points]
    w = g.width
    out: list[Thick | None] = []
    if g.kind == "line" and len(pts) == 2:
        out.append(_thick(pts, w))
    elif g.kind == "arc" and len(pts) == 3:
        out.append(_thick(_arc_points(*pts), w))
    elif g.kind == "circle" and len(pts) == 2:
        c, e = pts
        r = round(math.hypot(e.x - c.x, e.y - c.y))
        if g.filled:
            out.append(_thick([c], 2 * r + w))
        else:
            ring = [
                Point(round(c.x + r * math.cos(t)), round(c.y + r * math.sin(t)))
                for t in (2 * math.pi * k / 48 for k in range(49))
            ]
            out.append(_thick(ring, w))
    elif g.kind == "rect" and len(g.points) == 2:
        a, b = g.points
        ring = [
            place(Point(a.x, a.y)),
            place(Point(b.x, a.y)),
            place(Point(b.x, b.y)),
            place(Point(a.x, b.y)),
        ]
        out.append(_thick(ring, w, filled=True) if g.filled else _thick([*ring, ring[0]], w))
    elif g.kind == "polygon" and len(pts) >= 3:
        out.append(_thick(pts, w, filled=True) if g.filled else _thick([*pts, pts[0]], w))
    return [t for t in out if t is not None]


def _text_box(
    at: Point, h: int, w: int, stroke: int, udeg: int, hj: str, vj: str, mirrored: bool, n: int
) -> Thick | None:
    """The box of a text's ink as the page draws it (Fenolite's stroke font: cap height ``h``, glyph width
    ``w`` or two thirds of ``h``, advance one and a half glyph widths)."""
    if n == 0 or h <= 0:
        return None
    u, ux = h / 6, (w if w > 0 else h * 2 / 3) / 4
    tw = (n - 1) * 6 * ux + 4 * ux
    ox = 0.0 if hj == "left" else -tw if hj == "right" else -tw / 2
    oy = 0.0 if vj == "bottom" else -6 * u if vj == "top" else -3 * u
    th = math.radians(udeg / 1e6)
    c, s = math.cos(th), math.sin(th)
    mir = -1 if mirrored else 1
    half = stroke / 2
    corners: list[Point] = []
    for gx, gy in (
        (ox - half, oy - half),
        (ox + tw + half, oy - half),
        (ox + tw + half, oy + 6 * u + half),
        (ox - half, oy + 6 * u + half),
    ):
        lx, ly = gx * mir, -gy
        corners.append(Point(round(at.x + lx * c + ly * s), round(at.y - lx * s + ly * c)))
    return _thick(corners, 0, filled=True)


@dataclass
class _Silk:
    layer: str
    shape: Thick
    text: bool
    what: str


def _silk_items(board: Board, design: Design, layers: set[str], altium: bool) -> list[_Silk]:
    components = {c.id: c for c in design.circuit.components}
    out: list[_Silk] = []

    def box(
        at: Point, h: int, w: int, stroke: int, udeg: int, hj: str, vj: str, mirrored: bool, n: int
    ) -> Thick | None:
        if altium:  # the scene's convention for an Altium board (``scene.ALTIUM_TEXT_NOTE``)
            hj, vj, w = "left", "bottom", round(2 * h / 3)
        return _text_box(at, h, w, stroke, udeg, hj, vj, mirrored, n)

    for k, g in enumerate(board.graphics):
        if g.layer in layers:
            out += [_Silk(g.layer, t, False, f"graphic {k + 1}") for t in _graphic_shapes(g, _same)]
    for t in board.texts:
        if t.layer in layers:
            shape = box(
                t.position,
                t.size.h,
                t.size.w,
                t.thickness,
                t.rotation,
                t.h_justify,
                t.v_justify,
                t.layer.startswith("B."),
                len(t.text),
            )
            if shape is not None:
                out.append(_Silk(t.layer, shape, True, f"text '{t.text}'"))
    for fp in board.footprints:
        place = _place(fp)
        component = components.get(fp.component_id)
        ref = component.ref if component is not None else fp.lib_ref.split(":")[-1]
        for k, g in enumerate(fp.graphics):
            if g.layer in layers:
                out += [_Silk(g.layer, t, False, f"{ref} graphic {k + 1}") for t in _graphic_shapes(g, place)]
        for t in fp.texts:
            if t.layer in layers:
                shape = box(
                    place(t.position),
                    t.size.h,
                    t.size.w,
                    t.thickness,
                    fp.rotation + t.rotation,
                    t.h_justify,
                    t.v_justify,
                    t.layer.startswith("B."),
                    len(t.text),
                )
                if shape is not None:
                    out.append(_Silk(t.layer, shape, True, f"{ref} text '{t.text}'"))
        for f in fp.fields:
            if f.visible and f.layer in layers:
                value = (
                    ref
                    if f.name == "Reference"
                    else (component.value if component is not None else "")
                    if f.name == "Value"
                    else dict(component.properties).get(f.name, "")
                    if component is not None
                    else ""
                )
                thickness = f.thickness if f.thickness is not None else max(f.size.h // 8, 1)
                shape = box(
                    place(f.position),
                    f.size.h,
                    f.size.w,
                    thickness,
                    fp.rotation + f.rotation,
                    f.h_justify,
                    f.v_justify,
                    f.mirrored,
                    len(value),
                )
                if shape is not None:
                    out.append(_Silk(f.layer, shape, True, f"{ref} {f.name.lower()}"))
    return out


def _openings(
    pads: Sequence[BoardPad], board: Board, side: str, expansion: int, derive: bool
) -> list[tuple[Thick, str]]:
    cu, mask = ("F.Cu", "F.Mask") if side == "top" else ("B.Cu", "B.Mask")
    out: list[tuple[Thick, str]] = []
    for pad in pads:
        if derive:
            through = pad.kind in ("thru_hole", "np_thru_hole")
            opens = through or pad.side == side
        else:
            opens = mask in pad.layers or "*.Mask" in pad.layers or "F&B.Mask" in pad.layers
        if not opens:
            continue
        for copper in pad.copper:
            if copper.layer != cu:
                continue
            t = _thick(copper.core, copper.width + 2 * expansion, copper.filled and len(copper.core) > 2)
            if t is not None:
                out.append((t, f"{pad.ref}-{pad.number}" if pad.ref else pad.number))
    for k, via in enumerate(board.vias):
        tented = via.protection.tenting_front if side == "top" else via.protection.tenting_back
        if tented is False:
            t = _thick([via.position], via.diameter + 2 * expansion)
            if t is not None:
                out.append((t, f"via {k + 1}"))
    return out


class _Board:
    """The board ring and its cut-outs, for point tests and edge distances."""

    def __init__(self, rings: Sequence[EdgeRing]) -> None:
        sampled = [_ring_points(r) for r in rings]
        self.outer = sampled[0] if sampled else []
        self.cuts = sampled[1:]
        self.edges = [t for t in (_thick([*r, r[0]], 0) for r in sampled if len(r) > 2) if t is not None]

    def inside(self, p: Point) -> bool:
        if len(self.outer) < 3 or point_in_ring(p, self.outer) == Location.OUTSIDE:
            return False
        return not any(len(c) > 2 and point_in_ring(p, c) == Location.INSIDE for c in self.cuts)


def _corners(
    board: Board, pads: Sequence[BoardPad], copper: set[str], out: dict[str, list[dict[str, Any]]]
) -> None:
    hide: dict[str, list[Thick]] = {}
    for pad in pads:
        for c in pad.copper:
            t = _thick(c.core, c.width, c.filled and len(c.core) > 2)
            if t is not None:
                hide.setdefault(c.layer, []).append(t)
    for via in board.vias:
        t = _thick([via.position], via.diameter)
        if t is not None:
            for layer in copper:
                hide.setdefault(layer, []).append(t)
    index: dict[str, SpatialIndex[int]] = {
        layer: _index_of(thick_bbox(t) for t in ts) for layer, ts in hide.items()
    }
    empty = _index_of(())

    def hidden(layer: str, p: Point) -> bool:
        probe = Thick((p,), 2)
        return any(
            thick_touch(probe, hide[layer][k]) for k in index.get(layer, empty).query(thick_bbox(probe))
        )

    ends: dict[tuple[str, Point], list[tuple[int, Point]]] = {}
    others: set[tuple[str, Point]] = set()
    for k, t in enumerate(board.tracks):
        if t.layer not in copper or t.start == t.end:
            continue
        dx, dy = abs(t.end.x - t.start.x), abs(t.end.y - t.start.y)
        ang = math.degrees(math.atan2(-(t.end.y - t.start.y), t.end.x - t.start.x)) % 180
        if min(ang % 45, 45 - ang % 45) > ANGLE_TOL_DEG:
            out["track_angle"].append(
                _item(
                    "track_angle",
                    "line",
                    (t.start, t.end),
                    f"track {k + 1} ({t.layer}): direction {ang:.1f}°, {_mm(math.hypot(dx, dy))} mm long",
                    t.layer,
                )
            )
        ends.setdefault((t.layer, t.start), []).append((k, t.end))
        ends.setdefault((t.layer, t.end), []).append((k, t.start))
    for a in board.arcs:
        others.update({(a.layer, a.start), (a.layer, a.end)})
    for v in board.vias:
        others.update((layer, v.position) for layer in copper)
    for (layer, b), meet in ends.items():
        if len(meet) != 2 or (layer, b) in others:
            continue
        (k1, a), (k2, c) = meet
        ux, uy, vx, vy = a.x - b.x, a.y - b.y, c.x - b.x, c.y - b.y
        lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
        if lu == 0 or lv == 0:
            continue
        turn = 180.0 - math.degrees(math.acos(max(-1.0, min(1.0, (ux * vx + uy * vy) / (lu * lv)))))
        if turn <= 45 + ANGLE_TOL_DEG or hidden(layer, b):
            continue
        group = (
            "corner_acute"
            if turn > 90 + ANGLE_TOL_DEG
            else "corner_90"
            if turn >= 90 - ANGLE_TOL_DEG
            else "corner_mid"
        )
        out[group].append(
            _item(
                group,
                "path",
                (a, b, c),
                f"tracks {k1 + 1} and {k2 + 1} ({layer}): turn of {turn:.0f}° at ({_mm(b.x)}, {_mm(b.y)})",
                layer,
            )
        )
    for k, z in enumerate(board.zones):
        ring: list[Point] = []
        for p in z.outline:
            if not ring or math.hypot(p.x - ring[-1].x, p.y - ring[-1].y) > 2_000:
                ring.append(p)
        if len(ring) > 1 and math.hypot(ring[0].x - ring[-1].x, ring[0].y - ring[-1].y) <= 2_000:
            ring.pop()
        fills = [
            t
            for t in (_thick(f.polygon, 0, filled=True) for f in z.fills if len(f.polygon) >= 3)
            if t is not None
        ]
        layer = z.layers[0] if z.layers else (z.fills[0].layer if z.fills else "")
        n = len(ring)
        for i in range(n):
            a, b, c = ring[i - 1], ring[i], ring[(i + 1) % n]
            ux, uy, vx, vy = a.x - b.x, a.y - b.y, c.x - b.x, c.y - b.y
            lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
            if lu == 0 or lv == 0:
                continue
            inner = math.degrees(math.acos(max(-1.0, min(1.0, (ux * vx + uy * vy) / (lu * lv)))))
            if inner >= 135 - ZONE_TOL_DEG:
                continue
            probe = Thick((b,), 2)
            if fills and not any(thick_closer_than(probe, f, FILL_NEAR_NM) for f in fills):
                continue
            if any(hidden(name, b) for name in (z.layers or (layer,))):
                continue
            name = z.name or f"zone {k + 1}"
            out["corner_zone"].append(
                _item(
                    "corner_zone",
                    "path",
                    (a, b, c),
                    f"{name} ({layer}): interior angle {inner:.0f}° at ({_mm(b.x)}, {_mm(b.y)})",
                    layer,
                )
            )


def _silk(
    board: Board,
    design: Design,
    pads: Sequence[BoardPad],
    edge: _Board,
    gap: int,
    expansion: int,
    altium: bool,
    out: dict[str, list[dict[str, Any]]],
) -> None:
    silk_layers = {layer.name for layer in board.layers if layer.kind == "silkscreen"} | {
        "F.SilkS",
        "B.SilkS",
    }
    derive = not any(layer.kind == "soldermask" for layer in board.layers)
    items = _silk_items(board, design, silk_layers, altium)
    for side, prefix in (("top", "F."), ("bottom", "B.")):
        mine = [s for s in items if s.layer.startswith(prefix)]
        if not mine:
            continue
        openings = _openings(pads, board, side, expansion, derive)
        oindex = _index_of(thick_bbox(t) for t, _ in openings)
        sindex = _index_of(thick_bbox(s.shape) for s in mine)
        for s in mine:
            for k in oindex.query(_grow(thick_bbox(s.shape), gap)):
                t, label = openings[k]
                if thick_closer_than(s.shape, t, gap) if gap > 0 else thick_touch(s.shape, t):
                    d = thick_gap_floor(s.shape, t)
                    out["silk_mask"].append(
                        _item(
                            "silk_mask",
                            "point",
                            (thick_witness(s.shape, t),),
                            f"{s.what} ({s.layer}) {_mm(d)} mm from the mask opening of {label}",
                            s.layer,
                        )
                    )
        seen: set[tuple[int, int]] = set()
        for i, s in enumerate(mine):
            if not s.text:
                continue
            for j in sindex.query(_grow(thick_bbox(s.shape), gap)):
                if j == i or (min(i, j), max(i, j)) in seen:
                    continue
                o = mine[j]
                if thick_closer_than(s.shape, o.shape, gap) if gap > 0 else thick_touch(s.shape, o.shape):
                    seen.add((min(i, j), max(i, j)))
                    d = thick_gap_floor(s.shape, o.shape)
                    out["silk_silk"].append(
                        _item(
                            "silk_silk",
                            "point",
                            (thick_witness(s.shape, o.shape),),
                            f"{s.what} {_mm(d)} mm from {o.what} ({s.layer})",
                            s.layer,
                        )
                    )
        for s in mine:
            outside = [p for p in s.shape.core if not edge.inside(p)]
            if outside:
                out["silk_edge"].append(
                    _item(
                        "silk_edge",
                        "point",
                        (outside[0],),
                        f"{s.what} ({s.layer}) outside the board",
                        s.layer,
                    )
                )
            elif gap > 0:
                near = next((e for e in edge.edges if thick_closer_than(s.shape, e, gap)), None)
                if near is not None:
                    d = thick_gap_floor(s.shape, near)
                    out["silk_edge"].append(
                        _item(
                            "silk_edge",
                            "point",
                            (thick_witness(s.shape, near),),
                            f"{s.what} ({s.layer}) {_mm(d)} mm from the board edge",
                            s.layer,
                        )
                    )


def _root(parent: list[int], k: int) -> int:
    while parent[k] != k:
        parent[k] = parent[parent[k]]
        k = parent[k]
    return k


def _outside(
    board: Board, design: Design, pads: Sequence[BoardPad], edge: _Board, out: dict[str, list[dict[str, Any]]]
) -> None:
    if len(edge.outer) < 3:
        return
    names = {net.id: net.name for net in design.circuit.nets}
    found: list[tuple[str, str, list[Point]]] = []
    for pad in pads:
        core = [p for c in pad.copper for p in c.core] or [pad.position]
        found.append((pad.net or "", "pad", core))
    for t in board.tracks:
        found.append((names.get(t.net_id or "", ""), "track", [t.start, t.end]))
    for a in board.arcs:
        found.append((names.get(a.net_id or "", ""), "arc", [a.start, a.mid, a.end]))
    for v in board.vias:
        found.append((names.get(v.net_id or "", ""), "via", [v.position]))
    for z in board.zones:
        for f in z.fills:
            found.append((names.get(z.net_id or "", ""), "fill", list(f.polygon)))
    off = [(net, kind, core) for net, kind, core in found if core and not any(edge.inside(p) for p in core)]
    by_net: dict[str, list[tuple[str, list[Point]]]] = {}
    for net, kind, core in off:
        by_net.setdefault(net, []).append((kind, core))
    for net in sorted(by_net):
        rows = by_net[net]
        boxes = [BBox.of_points(core) for _, core in rows]
        index = _index_of(_grow(b, CLUSTER_NM // 2) for b in boxes)
        parent = list(range(len(rows)))
        for k, b in enumerate(boxes):
            for j in index.query(_grow(b, CLUSTER_NM // 2)):
                parent[_root(parent, j)] = _root(parent, k)
        clusters: dict[int, list[int]] = {}
        for k in range(len(rows)):
            clusters.setdefault(_root(parent, k), []).append(k)
        for members in clusters.values():
            box = BBox.of_points(
                [
                    p
                    for k in members
                    for p in (Point(boxes[k].x0, boxes[k].y0), Point(boxes[k].x1, boxes[k].y1))
                ]
            )
            counts: dict[str, int] = {}
            for k in members:
                counts[rows[k][0]] = counts.get(rows[k][0], 0) + 1
            what = ", ".join(f"{n} {kind}{'s' if n > 1 else ''}" for kind, n in sorted(counts.items()))
            centre = Point((box.x0 + box.x1) // 2, (box.y0 + box.y1) // 2)
            out["copper_out"].append(
                _item(
                    "copper_out",
                    "point",
                    (centre,),
                    f"{net or 'no net'}: {what} outside the board, "
                    f"x {_mm(box.x0)}…{_mm(box.x1)}, y {_mm(box.y0)}…{_mm(box.y1)} mm",
                    None,
                    box,
                )
            )


def silk_gap_of(design: Design) -> int | None:
    """The smallest minimum of the design's ``silk_clearance`` rules, or ``None``."""
    rules = design.rules.rules if design.rules is not None else ()
    found = [r.min for r in rules if r.kind == "silk_clearance" and r.min is not None]
    return min(found) if found else None


def review(
    design: Design,
    frame: BoardFrame | None,
    *,
    silk_gap: int | None = None,
    mask_expansion: int = 0,
    backend: str = "",
) -> Review:
    """The review findings of ``design``'s board (module docstring). ``silk_gap`` (nanometres) is the gap of
    the silkscreen findings; ``None`` takes the design's ``silk_clearance`` rule, else 0. ``mask_expansion``
    grows the pads' openings. ``backend`` is the reader's name: an Altium board's texts take the scene's
    convention (``scene.ALTIUM_TEXT_NOTE``)."""
    board = design.board
    result = Review()
    if board is None:
        return result
    pads: tuple[BoardPad, ...] = ()
    rings: tuple[EdgeRing, ...] = ()
    if frame is not None:
        try:
            pads = frame.board_pads(design)
            rings = frame.board_edges(design) or ()
        except (ValueError, TypeError, KeyError):
            pads, rings = (), ()
    copper = {layer.name for layer in board.layers if layer.kind == "copper"}
    found: dict[str, list[dict[str, Any]]] = {g: [] for g in GROUPS}
    rule_gap = silk_gap_of(design)
    gap = silk_gap if silk_gap is not None else (rule_gap if rule_gap is not None else 0)
    gap_source = (
        "--silk-gap"
        if silk_gap is not None
        else "the design's silk_clearance rule"
        if rule_gap is not None
        else "no rule (0: touching)"
    )
    edge = _Board(rings)
    _corners(board, pads, copper, found)
    _silk(board, design, pads, edge, gap, mask_expansion, backend == "altium", found)
    _outside(board, design, pads, edge, found)
    expansion = (
        f"grown by {_mm(mask_expansion)} mm (--mask-expansion)"
        if mask_expansion
        else "with no expansion (the model holds none)"
    )
    notes = {
        "corner_acute": "Two free tracks meeting at an end, turning more than 90°; "
        "corners inside a pad or a via are not listed.",
        "corner_90": "Two free tracks turning 90°: allowed when it keeps a track straight; "
        "listed for review.",
        "corner_mid": "Two free tracks turning between 45° and 90°.",
        "track_angle": "A free track whose direction is more than 0.5° from a multiple of 45°.",
        "corner_zone": "A zone outline vertex with an interior angle below 134°, "
        "where the zone has copper (its saved fill) or no fill at all.",
        "silk_mask": f"Silkscreen closer than {_mm(gap)} mm ({gap_source}) to a mask opening: "
        f"a pad {expansion}, or an untented via.",
        "silk_silk": f"A text closer than {_mm(gap)} mm ({gap_source}) to other silkscreen of its side; "
        "a text is the box of its ink.",
        "silk_edge": f"Silkscreen outside the board ring, in a cut-out, "
        f"or closer than {_mm(gap)} mm ({gap_source}) to an edge.",
        "copper_out": "Copper with no point inside the board, one finding per net and cluster "
        "(items within 2 mm).",
    }
    if not rings:
        for g in ("silk_edge", "copper_out"):
            notes[g] += " The board has no closed edge ring: not judged."
    for gid, (title, color) in GROUPS.items():
        mine = found[gid]
        note = notes[gid]
        if len(mine) > MAX_ITEMS:
            note += f" {len(mine)} found; the first {MAX_ITEMS} are listed."
            mine = mine[:MAX_ITEMS]
        result.items += mine
        result.groups.append({"id": gid, "title": title, "color": color, "n": len(mine), "note": note})
    return result


__all__ = ["GROUPS", "MAX_ITEMS", "Review", "review", "silk_gap_of"]
