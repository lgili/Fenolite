# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of a board for the viewer (capability board-viewer, "Board scene"): plain JSON values, built from
the neutral model and the backend's board frame, so every backend's boards are drawn the same way.

Units are integer micrometres in the model's board frame (origin at the outline's top-left corner, Y down).

* ``layers``: ``{id, name, kind, side, color, visible}`` in drawing order, back side first; ``id`` is the
  model's layer name. Three view layers are added: ``View.Drill``, ``View.Outline``, ``View.ZoneOutline``.
* ``prims``: ``[layer, kind, data, net, comp, label]``, ``net`` and ``comp`` indices into ``nets`` and
  ``comps`` (-1 for none). Kinds: ``s`` segment ``[x1, y1, x2, y2, w]``; ``a`` arc ``[x1, y1, xm, ym, x2,
  y2, w]`` through three points; ``c`` disc ``[cx, cy, r]``; ``l`` polyline ``[w, x0, y0, x1, y1, ...]``;
  ``p`` polygon ``[[ring], ...]`` filled even-odd, rings flat ``[x0, y0, x1, y1, ...]``; ``o`` outline
  ``[[ring], ...]``, stroked only.
* ``texts``: ``[layer, x, y, height, width, stroke, rotation, h_justify, v_justify, mirrored, text, comp]``
  with the rotation in degrees, counter-clockwise on the board as seen from the front.
* ``comps``: ``{ref, value, footprint, side, x, y, rotation, bbox}``; ``nets``: names; ``board``: the rings
  of the edge, each ``{points, mids}`` with ``mids[i]`` the mid of the arc from vertex ``i`` or ``None``.
* ``board3d``: ``thickness``; ``bodies``: ``{comp, ref, side, ring, z0, z1}``, a body's outline on the
  board extruded from its standoff to its height above the face its footprint is on.
* ``meta``: file, SHA-256, backend, evidence level, counts, ``unfilled`` zones and ``notes``.

The page and the colours are Fenolite's own; nothing here runs a tool or opens a connection.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from fenolite.backends.base import BoardFrame, BoardPad, EdgeRing
from fenolite.core.coords import Point
from fenolite.geometry.transform import rotate_point
from fenolite.model.board import Board, FootprintInstance, Graphic, Pad
from fenolite.model.design import Design

SCHEMA = "fenolite.view_scene.v0"
DRILL, OUTLINE, ZONE_OUTLINE = "View.Drill", "View.Outline", "View.ZoneOutline"
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
}
INNER = ("#c2c200", "#33a9a9", "#c27a2b", "#7f5fbf", "#5fa35f", "#bf5f9f")
OTHER = ("#d97fd9", "#7fd9d9", "#d9a97f", "#a9d97f", "#7f9fd9", "#d97f9f", "#bfbf7f", "#7fbfbf")
USER = "#e05080"
SHOWN = frozenset({"copper", "silkscreen", "edge"})
"""The layer kinds shown when a scene opens; every other kind starts hidden."""
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


def _pad_prims(b: _Builder, pad: BoardPad, comp: int, derive_mask: bool) -> None:
    label = f"{pad.ref}-{pad.number}" if pad.ref else pad.number
    shapes: dict[str, tuple[str, Any]] = {}
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
        shapes.setdefault(copper.layer, shape)
    front = shapes.get("F.Cu") or next(iter(shapes.values()), None)
    back = shapes.get("B.Cu") or front
    sides: list[tuple[str, str]] = []
    if derive_mask:
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
        opening = shapes.get(cu) or (back if cu == "B.Cu" else front)
        if opening is not None and not layer.startswith("*"):
            b.add(layer, opening[0], opening[1], None, comp, label)
    if pad.drill is not None and pad.hole:
        r = max(_um(pad.drill) // 2, 1)
        if len(pad.hole) == 1:
            b.add(DRILL, "c", [_um(pad.hole[0].x), _um(pad.hole[0].y), r], pad.net, comp, label + " hole")
        else:
            b.add(DRILL, "l", [2 * r, *_flat(pad.hole)], pad.net, comp, label + " slot")


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
) -> dict[str, Any]:
    """The scene of ``design``'s board (module docstring). ``frame`` gives the pads, the courtyards and the
    edge in the board frame; ``data`` are the file's bytes, for its SHA-256 only."""
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
            }
        )

    # pads, through the backend's board frame
    pads: tuple[BoardPad, ...] = ()
    if frame is not None:
        pads = frame.board_pads(design)
    has_mask = any(layer.kind == "soldermask" for layer in board.layers)
    if not has_mask and pads:
        notes.append(
            "The board holds no solder-mask layer: mask and paste openings are derived from the pads "
            "(SMD on its side, through-hole on both), with no expansion."
        )
    for pad in pads:
        _pad_prims(b, pad, comp_of.get(pad.footprint_id, -1), derive_mask=not has_mask)
    pad_list = _pad_list(board, pads, comp_of)

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
    for k, z in enumerate(board.zones):
        label = z.name or f"zone {k + 1}"
        if z.fills:
            for fill in z.fills:
                if len(fill.polygon) >= 3:
                    b.add(fill.layer, "p", [_flat(fill.polygon)], z.net_id, label=label)
        elif len(z.outline) >= 3:
            unfilled.append(label)
            b.add(ZONE_OUTLINE, "o", [_flat(z.outline)], z.net_id, label=label + " (no fill)")
    if unfilled:
        notes.append(
            f"{len(unfilled)} zone(s) hold no fill in the file and are drawn as outlines; refill them in "
            "their tool to see the copper."
        )

    # graphics and texts: board, then footprints in the pad frame
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
    ) -> None:
        if not value:
            return
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

    # component boxes: the courtyard where the backend gives one, else the pads
    if frame is not None:
        try:
            extents = frame.placed_extents(design)
        except (ValueError, TypeError, KeyError):
            extents = ()
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
                    "model": body.model,
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
                "name": layer_name,
                "kind": kind,
                "side": _side(layer_name),
                "color": color,
                "visible": kind in SHOWN,
            }
        )
    for view_layer in (ZONE_OUTLINE, DRILL, OUTLINE):
        if view_layer in b.used:
            layers.append(
                {
                    "id": view_layer,
                    "name": view_layer.split(".")[1],
                    "kind": "view",
                    "side": "both",
                    "color": COLORS[view_layer],
                    "visible": True,
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


__all__ = ["COLORS", "DRILL", "OUTLINE", "SCHEMA", "ZONE_OUTLINE", "build_scene", "summary"]
