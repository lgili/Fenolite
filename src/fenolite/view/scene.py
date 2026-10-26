# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of a board for the viewer (capability board-viewer, "Board scene"): plain JSON values, built from
the neutral model and the backend's board frame, so every backend's boards are drawn the same way.

Units are integer micrometres in the model's board frame (origin at the outline's top-left corner, Y down).

* ``layers``: ``{id, name, kind, side, color, visible}`` in drawing order, back side first; ``id`` is the
  model's layer name. View layers are added: ``View.Drill``, ``View.Outline``, ``View.ZoneOutline`` (zones
  without a fill) and ``View.ZoneEdge`` (every zone's outline, hidden at first; change c0193).
* ``prims``: ``[layer, kind, data, net, comp, label]``, ``net`` and ``comp`` indices into ``nets`` and
  ``comps`` (-1 for none). Kinds: ``s`` segment ``[x1, y1, x2, y2, w]``; ``a`` arc ``[x1, y1, xm, ym, x2,
  y2, w]`` through three points; ``c`` disc ``[cx, cy, r]``; ``l`` polyline ``[w, x0, y0, x1, y1, ...]``;
  ``p`` polygon ``[[ring], ...]`` filled even-odd, rings flat ``[x0, y0, x1, y1, ...]``; ``o`` outline
  ``[[ring], ...]``, stroked only.
* ``texts``: ``[layer, x, y, height, width, stroke, rotation, h_justify, v_justify, mirrored, text, comp]``
  with the rotation in degrees, counter-clockwise on the board as seen from the front. A text of an Altium
  board is anchored at its lower-left corner with a glyph two thirds of its height (``ALTIUM_TEXT_NOTE``).
* ``comps``: ``{ref, value, footprint, side, x, y, rotation, bbox}``; ``nets``: names; ``board``: the rings
  of the edge, each ``{points, mids}`` with ``mids[i]`` the mid of the arc from vertex ``i`` or ``None``.
* ``board3d``: ``thickness``; ``bodies``: ``{comp, ref, side, ring, z0, z1, zs, model, locator}``, a body's
  outline on the board extruded from its standoff to its height above the face its footprint is on (``z0`` at
  least 0); ``zs`` holds the signed standoff and height, which a model is compared with (change c0193), and
  ``locator`` the body's provenance locator, which a model names.
* ``meta``: file, SHA-256, backend, evidence level, counts, ``unfilled`` zones and ``notes``.

The page and the colours are Fenolite's own; nothing here runs a tool or opens a connection.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING, Any

from fenolite.backends.base import BoardFrame, BoardPad, EdgeRing, PlacedExtent
from fenolite.core.coords import Point
from fenolite.geometry.lengths import arc_length, segment_length
from fenolite.geometry.transform import rotate_point
from fenolite.model.board import Board, FootprintInstance, Graphic, Pad
from fenolite.model.design import Design

if TYPE_CHECKING:
    from fenolite.view.altium_layers import NativeView, Opening

SCHEMA = "fenolite.view_scene.v0"
DRILL, OUTLINE, ZONE_OUTLINE = "View.Drill", "View.Outline", "View.ZoneOutline"
KEEPOUTS, CHECKS = "View.Keepouts", "View.Checks"
"""Keep-outs that name no layer of the scene, and the marks of placement findings (change c0183)."""
ALTIUM_KEEPOUT = "Altium.KeepOut"
"""The Altium Keep-Out Layer: its filled regions are drawn hatched (change c0183)."""
DIMENSION_WIDTH, DIMENSION_TEXT = 100_000, 1_000_000
"""The line width and text height of a dimension whose file gives none, in nm (Fenolite's choice)."""
ZONE_EDGE = "View.ZoneEdge"
"""Every zone's outline, filled or not, hidden when a scene opens (change c0193): a saved fill that no longer
follows its outline shows against it."""
DEFAULT_THICKNESS = 1_600_000
"""The board thickness of the 3D view when the design has no stack-up, in nanometres (an assumption the
notes state)."""

# The palette, authored for Fenolite: one colour per layer kind and side, inner copper and mechanical
# layers from fixed lists. No tool's scheme is copied.
COLORS: dict[str, str] = {
    "F.Cu": "#c83434",
    "B.Cu": "#4d7fc4",
    "F.SilkS": "#f0e68c",
    "B.SilkS": "#c9a0dc",
    "F.Mask": "#b066c0",
    "B.Mask": "#4fa58a",
    "F.Paste": "#b4b4b4",
    "B.Paste": "#8c8c8c",
    "F.CrtYd": "#e0e0e0",
    "B.CrtYd": "#9e9e9e",
    "F.Fab": "#c8b896",
    "B.Fab": "#8896c8",
    "Edge.Cuts": "#e8d36a",
    DRILL: "#2a2a2a",
    OUTLINE: "#ffffff",
    ZONE_OUTLINE: "#40d0d0",
    KEEPOUTS: "#ff5fa8",
    CHECKS: "#ff3030",
    ZONE_EDGE: "#00e0e0",
}
INNER = ("#c2c200", "#33a9a9", "#c27a2b", "#7f5fbf", "#5fa35f", "#bf5f9f")
OTHER = ("#d97fd9", "#7fd9d9", "#d9a97f", "#a9d97f", "#7f9fd9", "#d97f9f", "#bfbf7f", "#7fbfbf")
USER = "#e05080"
SHOWN = frozenset({"copper", "silkscreen", "edge"})
"""The layer kinds shown when a scene opens; every other kind starts hidden."""
ALTIUM_TEXT_NOTE = (
    "Texts of an Altium board are drawn at the stroke text's anchor, its lower-left corner, with a glyph two "
    "thirds of the height: the advance of Altium's stroke font is about the height (the stored text boxes of "
    "1095 stroke texts of eight public documents: median 0.979 of the height, at most 1.0). The import gives "
    "these texts as centred, with a width equal to the height."
)
"""What the scene states for an Altium board (change c0193; ``docs/formats/altium/pcb-records.md``,
``H-A-PCBX-KICAD`` for the anchor)."""
FRONT_ORDER = ("F.Cu", "F.Mask", "F.Paste", "F.SilkS", "F.CrtYd", "F.Fab")
BACK_ORDER = ("B.Fab", "B.CrtYd", "B.SilkS", "B.Paste", "B.Mask", "B.Cu")


def _um(value: int) -> int:
    """Nanometres to whole micrometres, ties to even."""
    return round(value / 1000)


def _deg(udeg: int) -> float:
    return round(udeg / 1_000_000, 3)


def _flat(points: Iterable[Point]) -> list[int]:
    out: list[int] = []
    for p in points:
        out += [_um(p.x), _um(p.y)]
    return out


def _side(name: str) -> str:
    if name.startswith("F."):
        return "top"
    if name.startswith("B."):
        return "bottom"
    return "both"


def _same(p: Point) -> Point:
    return p


def _place(fp: FootprintInstance, p: Point) -> Point:
    """A pad-frame point of a footprint on the board: ``position + R(rotation)·p``."""
    q = rotate_point(p, fp.rotation)
    return Point(fp.position.x + q.x, fp.position.y + q.y)


class _Builder:
    """Collects the primitives, with the layers that hold something."""

    def __init__(self, nets: dict[str, int]) -> None:
        self.prims: list[list[Any]] = []
        self.used: set[str] = set()
        self.nets = nets

    def add(
        self, layer: str, kind: str, data: Any, net: str | None = None, comp: int = -1, label: str = ""
    ) -> None:
        self.prims.append([layer, kind, data, self.nets.get(net, -1) if net else -1, comp, label])
        self.used.add(layer)

    def graphic(self, g: Graphic, place: Callable[[Point], Point], comp: int, label: str) -> None:
        pts = [place(p) for p in g.points]
        w = _um(g.width)
        if g.kind == "line" and len(pts) == 2:
            self.add(g.layer, "s", [*_flat(pts), w], comp=comp, label=label)
        elif g.kind == "arc" and len(pts) == 3:
            self.add(g.layer, "a", [*_flat(pts), w], comp=comp, label=label)
        elif g.kind == "circle" and len(pts) == 2:
            c, e = pts
            r = _um(round(((e.x - c.x) ** 2 + (e.y - c.y) ** 2) ** 0.5))
            if g.filled:
                self.add(g.layer, "c", [_um(c.x), _um(c.y), r + w // 2], comp=comp, label=label)
            else:
                ring = _circle_ring(_um(c.x), _um(c.y), r)
                self.add(g.layer, "l", [w, *ring, ring[0], ring[1]], comp=comp, label=label)
        elif g.kind == "rect" and len(g.points) == 2:
            a, b = g.points
            corners = [
                place(Point(a.x, a.y)),
                place(Point(b.x, a.y)),
                place(Point(b.x, b.y)),
                place(Point(a.x, b.y)),
            ]
            ring = _flat(corners)
            if g.filled:
                self.add(g.layer, "p", [ring], comp=comp, label=label)
            else:
                self.add(g.layer, "l", [w, *ring, ring[0], ring[1]], comp=comp, label=label)
        elif g.kind == "polygon" and len(pts) >= 3:
            ring = _flat(pts)
            if g.filled:
                self.add(g.layer, "p", [ring], comp=comp, label=label)
            if w > 0 or not g.filled:
                self.add(g.layer, "l", [max(w, 1), *ring, ring[0], ring[1]], comp=comp, label=label)


def _circle_ring(cx: int, cy: int, r: int, n: int = 48) -> list[int]:
    from math import cos, pi, sin

    out: list[int] = []
    for k in range(n):
        t = 2 * pi * k / n
        out += [round(cx + r * cos(t)), round(cy + r * sin(t))]
    return out


def _grow(shape: tuple[str, Any], by: int) -> list[tuple[str, Any]]:
    """``shape`` grown by ``by`` µm (shrunk when negative) as primitives, none when nothing is left: a
    circle's radius, a stroke's width, and a filled ring as itself with an edge stroke of twice ``by``, or
    moved inwards edge by edge (a convex ring)."""
    kind, data = shape
    if by == 0:
        return [shape]
    if kind == "c":
        return [("c", [data[0], data[1], data[2] + by])] if data[2] + by > 0 else []
    if kind == "l":
        return [("l", [data[0] + 2 * by, *data[1:]])] if data[0] + 2 * by > 0 else []
    ring = data[0]
    if by > 0:
        return [("p", [ring]), ("l", [2 * by, *ring, ring[0], ring[1]])]
    inner = _inset(ring, -by)
    return [("p", [inner])] if inner else []


def _inset(ring: list[int], by: int) -> list[int]:
    """A convex ring moved inwards by ``by`` µm, edge by edge; ``[]`` when it vanishes."""
    from math import hypot

    pts = list(zip(ring[0::2], ring[1::2], strict=True))
    n = len(pts)
    if n < 3:
        return []
    area = sum(pts[k][0] * pts[(k + 1) % n][1] - pts[(k + 1) % n][0] * pts[k][1] for k in range(n))
    sign = 1 if area > 0 else -1
    lines: list[tuple[float, float, float, float]] = []
    for k in range(n):
        (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        length = hypot(dx, dy)
        if length == 0:
            continue
        nx, ny = -dy / length * sign, dx / length * sign  # the inward normal
        lines.append((x0 + nx * by, y0 + ny * by, dx, dy))
    out: list[int] = []
    for k in range(len(lines)):
        ax, ay, adx, ady = lines[k - 1]
        bx, by_, bdx, bdy = lines[k]
        cross = adx * bdy - ady * bdx
        if abs(cross) < 1e-9:
            out += [round(bx), round(by_)]
            continue
        t = ((bx - ax) * bdy - (by_ - ay) * bdx) / cross
        out += [round(ax + adx * t), round(ay + ady * t)]
    q = list(zip(out[0::2], out[1::2], strict=True))
    shrunk = sum(q[k][0] * q[(k + 1) % len(q)][1] - q[(k + 1) % len(q)][0] * q[k][1] for k in range(len(q)))
    return out if shrunk * area > 0 and abs(shrunk) < abs(area) else []


def _pad_prims(
    b: _Builder, pad: BoardPad, comp: int, derive_mask: bool, opening: Opening | None = None
) -> None:
    label = f"{pad.ref}-{pad.number}" if pad.ref else pad.number
    shapes: dict[str, tuple[str, Any]] = {}
    edge: dict[str, int] = {}
    """Per layer, the half width of the edge stroke a filled ring is grown by."""
    for copper in pad.copper:
        core, w = copper.core, _um(copper.width)
        if len(core) == 1:
            shape: tuple[str, Any] = ("c", [_um(core[0].x), _um(core[0].y), max(w // 2, 1)])
        elif copper.filled:
            shape = ("p", [_flat(core)])
        else:
            shape = ("l", [max(w, 1), *_flat(core)])
        b.add(copper.layer, shape[0], shape[1], pad.net, comp, label)
        if copper.filled and len(core) > 1 and w > 0:  # a filled ring grown by its width: stroke the edge too
            b.add(copper.layer, "l", [w, *_flat(core), _um(core[0].x), _um(core[0].y)], pad.net, comp, label)
        if copper.layer not in shapes:
            shapes[copper.layer] = shape
            edge[copper.layer] = w // 2 if copper.filled and len(core) > 1 else 0
    sides: list[tuple[str, str]] = []
    if derive_mask or opening is not None:
        if pad.kind in ("thru_hole", "np_thru_hole"):
            sides = [("F.Mask", "F.Cu"), ("B.Mask", "B.Cu")]
        elif pad.side == "bottom" or "B.Cu" in shapes and "F.Cu" not in shapes:
            sides = [("B.Mask", "B.Cu"), ("B.Paste", "B.Cu")]
        else:
            sides = [("F.Mask", "F.Cu"), ("F.Paste", "F.Cu")]
    else:
        for layer in pad.layers:
            if layer.endswith((".Mask", ".Paste")):
                sides.append((layer, "B.Cu" if layer.startswith("B.") else "F.Cu"))
        if "*.Mask" in pad.layers:
            sides += [("F.Mask", "F.Cu"), ("B.Mask", "B.Cu")]
    for layer, cu in sides:
        source = cu if cu in shapes else ("F.Cu" if "F.Cu" in shapes else next(iter(shapes), ""))
        hole = shapes.get(source)
        if hole is None or layer.startswith("*"):
            continue
        by = edge.get(source, 0)  # the copper's own edge first, then the expansion
        if opening is not None:
            by += _um(opening.mask if layer.endswith("Mask") else opening.paste)
        grown = _grow(hole, by)
        for kind, data in grown:
            b.add(layer, kind, data, None, comp, label)
    if pad.drill is not None and pad.hole:
        r = max(_um(pad.drill) // 2, 1)
        if len(pad.hole) == 1:
            b.add(DRILL, "c", [_um(pad.hole[0].x), _um(pad.hole[0].y), r], pad.net, comp, label + " hole")
        else:
            b.add(DRILL, "l", [2 * r, *_flat(pad.hole)], pad.net, comp, label + " slot")


def kinds_of(board: Board) -> set[str]:
    return {layer.name for layer in board.layers}


def _forbids(keepout: Any) -> str:
    """What a keep-out forbids, as words."""
    names = (
        ("no_tracks", "tracks"),
        ("no_vias", "vias"),
        ("no_pads", "pads"),
        ("no_copper_pour", "copper pours"),
        ("no_footprints", "footprints"),
    )
    found = [word for attr, word in names if getattr(keepout, attr, False)]
    return "no " + ", ".join(found) if found else ""


def _dimension(b: _Builder, dim: Any, label: str, text: Callable[..., None]) -> None:
    """A linear dimension: the extension lines, the dimension line and its value. An orthogonal one measures
    along x or y and puts its line ``offset`` below (right of) the first point, above (left) when negative
    (``docs/formats/kicad/board.md``); an aligned one measures the distance and puts its line ``offset`` along
    the normal (dy, −dx) turned to the left of the direction, as an orthogonal one would (INFERRED)."""
    from math import hypot

    (sx, sy), (ex, ey) = (dim.start.x, dim.start.y), (dim.end.x, dim.end.y)
    if dim.kind == "orthogonal" and dim.direction == "vertical":
        a, z = (sx + dim.offset, sy), (sx + dim.offset, ey)
        value = abs(ey - sy)
    elif dim.kind == "orthogonal":
        a, z = (sx, sy + dim.offset), (ex, sy + dim.offset)
        value = abs(ex - sx)
    else:
        length = hypot(ex - sx, ey - sy) or 1.0
        nx, ny = -(ey - sy) / length, (ex - sx) / length
        a = (round(sx + nx * dim.offset), round(sy + ny * dim.offset))
        z = (round(ex + nx * dim.offset), round(ey + ny * dim.offset))
        value = round(length)
    w = _um(dim.width or DIMENSION_WIDTH)
    for p, q in (((sx, sy), a), ((ex, ey), z), (a, z)):
        b.add(dim.layer, "s", [_um(p[0]), _um(p[1]), _um(q[0]), _um(q[1]), w], label=label)
    places = max(0, min(dim.precision, 4))
    shown = f"{value / 1e6:.{places}f} mm" if dim.units == "mm" else f"{value / 25_400_000:.{places}f} in"
    size = dim.size.h if dim.size is not None else DIMENSION_TEXT
    middle = Point((a[0] + z[0]) // 2, (a[1] + z[1]) // 2 - size)
    text(dim.layer, middle, size, size, dim.thickness, 0, "center", "center", False, shown, -1, native=False)


_SHOWN_FIELDS = frozenset({"Reference", "Value", "Footprint"})
"""Fields a part's Properties already show by their own rows."""


def _net_info(
    board: Board, nets: list[str], net_index: dict[str, int], pads: list[dict[str, Any]]
) -> list[dict[str, int]]:
    """Per net of ``nets``: its pad count and its routed length in µm, the centre lines of its tracks and
    arcs (change c0187; Fenolite's computation, vias not counted)."""
    lengths = [0] * len(nets)
    count = [0] * len(nets)
    for track in board.tracks:
        k = net_index.get(track.net_id or "")
        if k is not None:
            lengths[k] += segment_length(track.start, track.end)
    for arc in board.arcs:
        k = net_index.get(arc.net_id or "")
        if k is not None:
            lengths[k] += arc_length(arc.start, arc.mid, arc.end)
    by_name = {name: k for k, name in enumerate(nets)}
    for pad in pads:
        k = by_name.get(pad["net"])
        if k is not None:
            count[k] += 1
    return [{"pads": n, "length": _um(length)} for n, length in zip(count, lengths, strict=True)]


def _pad_list(board: Board, pads: Sequence[BoardPad], comp_of: dict[str, int]) -> list[dict[str, Any]]:
    """Every pad with its exact size (change c0179): centre in µm, sizes, drill and slot in nm from the
    model pad, shape, board rotation in degrees, corner ratio, kind, layers, net and part."""
    model: dict[tuple[str, str], Pad] = {(fp.id, pad.id): pad for fp in board.footprints for pad in fp.pads}
    out: list[dict[str, Any]] = []
    for pad in pads:
        source = model.get((pad.footprint_id, pad.pad_id))
        slot = None
        if len(pad.hole) == 2:
            a, z = pad.hole
            slot = round(((z.x - a.x) ** 2 + (z.y - a.y) ** 2) ** 0.5)
        out.append(
            {
                "label": f"{pad.ref}-{pad.number}" if pad.ref else pad.number,
                "number": pad.number,
                "x": _um(pad.position.x),
                "y": _um(pad.position.y),
                "w": source.size.w if source is not None else None,
                "h": source.size.h if source is not None else None,
                "shape": source.shape if source is not None else "",
                "ratio": source.corner_ratio if source is not None else None,
                "rot": _deg(pad.rotation),
                "drill": pad.drill,
                "slot": slot,
                "kind": pad.kind,
                "layers": list(pad.layers),
                "net": pad.net or "",
                "comp": comp_of.get(pad.footprint_id, -1),
            }
        )
    return out


def _copper_span(board: Board, ends: Sequence[str]) -> list[str]:
    copper = [layer.name for layer in board.layers if layer.kind == "copper"]
    found = [copper.index(name) for name in ends if name in copper]
    if len(found) < 2:
        return copper if not found else [copper[found[0]]]
    lo, hi = min(found), max(found)
    return copper[lo : hi + 1]


def _field_text(name: str, ref: str, value: str, properties: dict[str, str]) -> str:
    if name == "Reference":
        return ref
    if name == "Value":
        return value
    return properties.get(name, "")


def _edges(design: Design, frame: BoardFrame | None) -> list[dict[str, Any]]:
    rings: tuple[EdgeRing, ...] | None = None
    if frame is not None:
        try:
            rings = frame.board_edges(design)
        except (ValueError, TypeError, KeyError):
            rings = None
    out: list[dict[str, Any]] = []
    if rings:
        for ring in rings:
            mids = list(ring.mids) + [None] * (len(ring.points) - len(ring.mids))
            out.append(
                {
                    "name": ring.name,
                    "points": _flat(ring.points),
                    "mids": [None if m is None else [_um(m.x), _um(m.y)] for m in mids],
                }
            )
        return out
    outline = design.board.outline if design.board is not None else None
    if outline is not None and outline.points:
        out.append({"name": "board", "points": _flat(outline.points), "mids": [None] * len(outline.points)})
        for k, cut in enumerate(outline.cutouts):
            out.append({"name": f"cut-out {k + 1}", "points": _flat(cut), "mids": [None] * len(cut)})
    return out


def _bounds(rings: list[dict[str, Any]], prims: list[list[Any]]) -> list[int]:
    xs: list[int] = []
    ys: list[int] = []
    for ring in rings[:1]:
        xs += ring["points"][0::2]
        ys += ring["points"][1::2]
    if not xs:
        for prim in prims:
            data = prim[2]
            flat = data[0] if prim[1] in ("p", "o") else data[1:] if prim[1] == "l" else data[:-1]
            if prim[1] == "c":
                flat = data[:2]
            xs += flat[0::2]
            ys += flat[1::2]
    if not xs:
        return [0, 0, 100_000, 100_000]
    return [min(xs), min(ys), max(xs), max(ys)]


def build_scene(
    design: Design,
    frame: BoardFrame | None,
    *,
    name: str,
    data: bytes = b"",
    backend: str = "",
    evidence: str = "INFERRED",
    native: NativeView | None = None,
    checks: Sequence[tuple[str, tuple[str, ...]]] = (),
    extents: Sequence[PlacedExtent] | None = None,
) -> dict[str, Any]:
    """The scene of ``design``'s board (module docstring). ``frame`` gives the pads, the courtyards and the
    edge in the board frame; ``data`` are the file's bytes, for its SHA-256 only. ``native`` (an Altium
    board, change c0181) names the layers as the board does, orders their tabs, and grows each pad's mask and
    paste opening by its expansion. ``checks`` (change c0183) are placement findings, each a message and the
    references of the parts it names, whose courtyards are marked on the ``View.Checks`` layer."""
    board = design.board
    if board is None:
        raise ValueError(f"{name}: the design holds no board")
    nets = [net.name for net in design.circuit.nets]
    net_index = {net.id: k for k, net in enumerate(design.circuit.nets)}
    by_name = {n: k for k, n in enumerate(nets)}
    b = _Builder({net_id: k for net_id, k in net_index.items()} | by_name)
    components = {c.id: c for c in design.circuit.components}
    notes: list[str] = []

    comps: list[dict[str, Any]] = []
    comp_of: dict[str, int] = {}
    for fp in board.footprints:
        component = components.get(fp.component_id)
        ref = component.ref if component is not None else fp.lib_ref.split(":")[-1]
        comp_of[fp.id] = len(comps)
        params = dict(native.parts.get(ref, {})) if native is not None else {}
        uid = params.pop("uid", "")
        if component is not None:
            params |= {k: v for k, v in component.properties.items() if v and k not in _SHOWN_FIELDS}
        comps.append(
            {
                "ref": ref,
                "value": component.value if component is not None else "",
                "footprint": fp.lib_ref,
                "side": fp.side,
                "x": _um(fp.position.x),
                "y": _um(fp.position.y),
                "rotation": _deg(fp.rotation),
                "bbox": None,
                "params": params,
            }
            | ({"uid": uid} if uid else {})
        )

    # pads, through the backend's board frame
    pads: tuple[BoardPad, ...] = ()
    if frame is not None:
        pads = frame.board_pads(design)
    has_mask = any(layer.kind == "soldermask" for layer in board.layers)
    openings = native.openings if native is not None else {}
    if not has_mask and pads and native is None:
        notes.append(
            "The board holds no solder-mask layer: mask and paste openings are derived from the pads "
            "(SMD on its side, through-hole on both), with no expansion."
        )
    for pad in pads:
        _pad_prims(b, pad, comp_of.get(pad.footprint_id, -1), not has_mask, openings.get(pad.pad_id))
    pad_list = _pad_list(board, pads, comp_of)
    for entry, pad in zip(pad_list, pads, strict=True):
        found = openings.get(pad.pad_id)
        if found is not None:
            entry |= {
                "mask": found.mask,
                "paste": found.paste,
                "mask_src": found.mask_source,
                "paste_src": found.paste_source,
            }
    if native is not None:
        notes.extend(native.notes)

    # tracks, arcs, vias
    for k, t in enumerate(board.tracks):
        b.add(t.layer, "s", [*_flat((t.start, t.end)), _um(t.width)], t.net_id, label=f"track {k + 1}")
    for k, a in enumerate(board.arcs):
        b.add(a.layer, "a", [*_flat((a.start, a.mid, a.end)), _um(a.width)], a.net_id, label=f"arc {k + 1}")
    for k, v in enumerate(board.vias):
        x, y, r = _um(v.position.x), _um(v.position.y), max(_um(v.diameter) // 2, 1)
        for layer in _copper_span(board, v.layers):
            b.add(layer, "c", [x, y, r], v.net_id, label=f"via {k + 1}")
        b.add(DRILL, "c", [x, y, max(_um(v.drill) // 2, 1)], v.net_id, label=f"via {k + 1} hole")
        protection = v.protection
        for layer, tented in (("F.Mask", protection.tenting_front), ("B.Mask", protection.tenting_back)):
            if tented is False:
                b.add(layer, "c", [x, y, r], None, label=f"via {k + 1}")
    for k, h in enumerate(board.holes):
        r = max(_um(h.drill) // 2, 1)
        b.add(DRILL, "c", [_um(h.position.x), _um(h.position.y), r], None, label=f"hole {k + 1}")

    # zones: the fills of the file, or the outline when there is none
    unfilled: list[str] = []
    zone_labels: list[str] = []
    for k, z in enumerate(board.zones):
        label = z.name or f"zone {k + 1}"
        zone_labels.append(label)
        if z.fills:
            for fill in z.fills:
                if len(fill.polygon) >= 3:
                    b.add(fill.layer, "p", [_flat(fill.polygon)], z.net_id, label=label)
        elif len(z.outline) >= 3:
            unfilled.append(label)
            b.add(ZONE_OUTLINE, "o", [_flat(z.outline)], z.net_id, label=label + " (no fill)")
        if len(z.outline) >= 3:
            b.add(ZONE_EDGE, "o", [_flat(z.outline)], z.net_id, label=label + " (outline)")
    if unfilled:
        notes.append(
            f"{len(unfilled)} zone(s) hold no fill in the file and are drawn as outlines; refill them in "
            "their tool to see the copper."
        )

    # graphics and texts: board, then footprints in the pad frame
    altium_text = backend == "altium"
    if altium_text:
        notes.append(ALTIUM_TEXT_NOTE)
    for k, g in enumerate(board.graphics):
        b.graphic(g, _same, -1, f"graphic {k + 1}")
    texts: list[list[Any]] = []

    def text(
        layer: str,
        at: Point,
        size_h: int,
        size_w: int,
        stroke: int | None,
        rot: int,
        hj: str,
        vj: str,
        mirrored: bool,
        value: str,
        comp: int,
        native: bool = True,
    ) -> None:
        if not value:
            return
        if altium_text and native:  # a text of the file, not one the scene writes (a dimension's)
            hj, vj, size_w = "left", "bottom", round(2 * size_h / 3)
        sw = _um(stroke) if stroke is not None else max(_um(size_h) // 8, 1)
        texts.append(
            [
                layer,
                _um(at.x),
                _um(at.y),
                _um(size_h),
                _um(size_w),
                sw,
                _deg(rot),
                hj,
                vj,
                mirrored,
                value,
                comp,
            ]
        )
        b.used.add(layer)

    for t in board.texts:
        text(
            t.layer,
            t.position,
            t.size.h,
            t.size.w,
            t.thickness,
            t.rotation,
            t.h_justify,
            t.v_justify,
            t.layer.startswith("B."),
            t.text,
            -1,
        )
    for fp in board.footprints:
        ci = comp_of[fp.id]
        component = components.get(fp.component_id)

        def place(p: Point, fp: FootprintInstance = fp) -> Point:
            return _place(fp, p)

        for k, g in enumerate(fp.graphics):
            b.graphic(g, place, ci, f"{comps[ci]['ref']} graphic {k + 1}")
        for t in fp.texts:
            text(
                t.layer,
                place(t.position),
                t.size.h,
                t.size.w,
                t.thickness,
                fp.rotation + t.rotation,
                t.h_justify,
                t.v_justify,
                t.layer.startswith("B."),
                t.text,
                ci,
            )
        for f in fp.fields:
            if not f.visible:
                continue
            value = _field_text(
                f.name,
                comps[ci]["ref"],
                comps[ci]["value"],
                dict(component.properties) if component is not None else {},
            )
            text(
                f.layer,
                place(f.position),
                f.size.h,
                f.size.w,
                f.thickness,
                fp.rotation + f.rotation,
                f.h_justify,
                f.v_justify,
                f.mirrored,
                value,
                ci,
            )

    # keep-outs, the Altium Keep-Out Layer, dimensions (change c0183)
    copper_names = [layer.name for layer in board.layers if layer.kind == "copper"]
    for k, keepout in enumerate(board.keepouts):
        if len(keepout.outline) < 3:
            continue
        what = _forbids(keepout)
        label = f"keep-out {keepout.name or k + 1}: {what}" if what else f"rule area {keepout.name or k + 1}"
        named = [
            n for layer in keepout.layers for n in (copper_names if layer in ("*.Cu", "F&B.Cu") else [layer])
        ]
        targets = [n for n in dict.fromkeys(named) if n in kinds_of(board)] or [KEEPOUTS]
        for layer in targets:
            b.add(layer, "h", [_flat(keepout.outline)], label=label)
    for prim in b.prims:
        if prim[0] == ALTIUM_KEEPOUT and prim[1] == "p":
            prim[1] = "h"
            prim[5] = f"{prim[5]} (Keep-Out Layer)" if prim[5] else "Keep-Out Layer"
    shown_too = {ALTIUM_KEEPOUT}  # layers shown although their kind is hidden by default
    for k, dim in enumerate(board.dimensions):
        _dimension(b, dim, f"dimension {k + 1}", text)
        shown_too.add(dim.layer)

    # component boxes: the courtyard where the backend gives one, else the pads
    if extents is None and frame is not None:
        try:
            extents = frame.placed_extents(design)
        except (ValueError, TypeError, KeyError):
            extents = ()
    extents = extents or ()
    for extent in extents:
        ci = comp_of.get(extent.footprint_id)
        rings = [r for r in (extent.front + extent.back) if r]
        if ci is None or not rings:
            continue
        xs = [p.x for r in rings for p in r]
        ys = [p.y for r in rings for p in r]
        comps[ci]["bbox"] = [_um(min(xs)), _um(min(ys)), _um(max(xs)), _um(max(ys))]
    boxes: dict[int, list[int]] = {}
    for pad in pads:
        ci = comp_of.get(pad.footprint_id)
        if ci is None or comps[ci]["bbox"] is not None:
            continue
        pts = [p for c in pad.copper for p in c.core] or [pad.position]
        box = boxes.setdefault(ci, [10**12, 10**12, -(10**12), -(10**12)])
        for p in pts:
            box[0], box[1] = min(box[0], _um(p.x)), min(box[1], _um(p.y))
            box[2], box[3] = max(box[2], _um(p.x)), max(box[3], _um(p.y))
    for ci, box in boxes.items():
        comps[ci]["bbox"] = box
    if checks:
        rings_of: dict[str, list[tuple[Point, ...]]] = {}
        for extent in extents:
            ci = comp_of.get(extent.footprint_id)
            if ci is not None:
                rings_of.setdefault(comps[ci]["ref"], []).extend(r for r in extent.own if len(r) >= 3)
        for message, refs in checks:
            if not refs:  # a finding the scene only states
                notes.append(message + ".")
                continue
            for ref in refs:
                for ring in rings_of.get(ref, []):
                    ci = next((i for i, c in enumerate(comps) if c["ref"] == ref), -1)
                    b.add(CHECKS, "h", [_flat(ring)], comp=ci, label=message)
        marked = sum(1 for _message, refs in checks if refs)
        if marked:
            notes.append(f"{marked} placement finding(s) are marked on the Checks layer.")

    # 3D: the slab and the bodies
    thickness = DEFAULT_THICKNESS
    if board.stackup is not None and board.stackup.layers:
        thickness = sum(layer.thickness for layer in board.stackup.layers) or DEFAULT_THICKNESS
    else:
        notes.append("The board holds no stack-up: the 3D view assumes a thickness of 1.6 mm.")
    bodies: list[dict[str, Any]] = []
    for fp in board.footprints:
        ci = comp_of[fp.id]
        for body in fp.bodies:
            if body.projection_unknown or len(body.outline) < 3:
                continue
            z0 = body.standoff if body.z_min is None else body.z_min
            z1 = body.height if body.z_max is None else body.z_max
            bodies.append(
                {
                    "comp": ci,
                    "ref": comps[ci]["ref"],
                    "side": fp.side,
                    "ring": _flat(_place(fp, p) for p in body.outline),
                    "z0": _um(max(min(z0, z1), 0)),
                    "z1": _um(max(z0, z1, 50_000)),
                    "zs": [_um(min(z0, z1)), _um(max(z0, z1))],
                    "model": body.model,
                    "locator": body.provenance.locator if body.provenance is not None else body.id,
                }
            )

    # layers in drawing order, back side first
    edges = _edges(design, frame)
    if edges:
        b.used.add(OUTLINE)
    kinds: dict[str, str] = {layer.name: layer.kind for layer in board.layers}
    for derived in ("F.Mask", "B.Mask", "F.Paste", "B.Paste"):
        if derived in b.used and derived not in kinds:
            kinds[derived] = "soldermask" if derived.endswith("Mask") else "solderpaste"
    copper = [layer.name for layer in board.layers if layer.kind == "copper"]
    inner = [n for n in copper if n not in ("F.Cu", "B.Cu")]
    head = [n for n in BACK_ORDER if n in kinds] + inner[::-1] + [n for n in FRONT_ORDER if n in kinds]
    order = head + [n for n in kinds if n not in head]
    layers: list[dict[str, Any]] = []
    inner_k = other_k = 0
    for layer_name in order:
        kind = kinds[layer_name]
        if layer_name not in b.used and kind != "copper":
            continue
        if layer_name in COLORS:
            color = COLORS[layer_name]
        elif kind == "copper":
            color, inner_k = INNER[inner_k % len(INNER)], inner_k + 1
        elif kind == "user":
            color = USER
        else:
            color, other_k = OTHER[other_k % len(OTHER)], other_k + 1
        layers.append(
            {
                "id": layer_name,
                "name": native.labels.get(layer_name, layer_name) if native is not None else layer_name,
                "kind": kind,
                "side": _side(layer_name),
                "color": color,
                "visible": kind in SHOWN or layer_name in shown_too,
            }
        )
        if native is not None and layer_name in native.tabs:
            layers[-1]["tab"] = native.tabs[layer_name]
    for view_layer in (ZONE_EDGE, ZONE_OUTLINE, KEEPOUTS, CHECKS, DRILL, OUTLINE):
        if view_layer in b.used:
            layers.append(
                {
                    "id": view_layer,
                    "name": view_layer.split(".")[1],
                    "kind": "view",
                    "side": "both",
                    "color": COLORS[view_layer],
                    "visible": view_layer != ZONE_EDGE,
                }
            )
    known = {layer["id"] for layer in layers}
    for layer_name in sorted(b.used - known):
        layers.append(
            {
                "id": layer_name,
                "name": layer_name,
                "kind": "user",
                "side": _side(layer_name),
                "color": USER,
                "visible": False,
            }
        )

    counts = {
        "pads": len(pads),
        "tracks": len(board.tracks),
        "arcs": len(board.arcs),
        "vias": len(board.vias),
        "zones": len(board.zones),
        "zone_fills": sum(len(z.fills) for z in board.zones),
        "graphics": len(board.graphics) + sum(len(fp.graphics) for fp in board.footprints),
        "texts": len(texts),
        "footprints": len(board.footprints),
        "bodies": len(bodies),
        "holes": len(board.holes),
        "prims": len(b.prims),
    }
    return {
        "schema": SCHEMA,
        "netinfo": _net_info(board, nets, net_index, pad_list),
        "zones": zone_labels,
        "meta": {
            "name": name,
            "sha256": hashlib.sha256(data).hexdigest() if data else "",
            "bytes": len(data),
            "backend": backend,
            "evidence": evidence,
            "counts": counts,
            "unfilled": unfilled,
            "notes": notes,
        },
        "bounds": _bounds(edges, b.prims),
        "board": edges,
        "layers": layers,
        "prims": b.prims,
        "texts": texts,
        "comps": comps,
        "nets": nets,
        "board3d": {"thickness": _um(thickness)},
        "bodies": bodies,
        "pads": pad_list,
        "overlays": [],
    }


def summary(scene: dict[str, Any]) -> dict[str, Any]:
    """The part of a scene that a reply carries: its layers and the count of each item kind."""
    return {
        "layers": [layer["id"] for layer in scene["layers"]],
        "counts": dict(scene["meta"]["counts"]),
        "unfilled": len(scene["meta"]["unfilled"]),
        "bounds_um": list(scene["bounds"]),
    }


__all__ = ["COLORS", "DRILL", "OUTLINE", "SCHEMA", "ZONE_EDGE", "ZONE_OUTLINE", "build_scene", "summary"]
