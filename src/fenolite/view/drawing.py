# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of an Altium Draftsman document for the viewer page (capability draftsman-viewer, change c0180).

``drawing_scene(path)`` reads a ``.PCBDwf`` with ``read.dwfdraw`` and returns a library-form scene (c0179)
with ``lib`` ``drawing`` and one item per sheet. Each item is a schematic-form scene (c0177) in integer
micrometres from the sheet's top-left corner, Y down:

* the sheet's own lines, rectangles, texts (``=Parameter`` filled in), pictures, notes and linear dimensions;
* assembly views: the board outline, the parts of the view's side with their designators, and the holes;
* fabrication views: the outline and the primitives of the view's layer;
* drill views: the outline and one symbol per hole size;
* the drill table, the layer stack legend and the bill of materials, drawn from the document's own data.

The document's copy of the board is drawn, as Altium shows it before a refresh. The view placement (the
view's location is the top-left corner of the board's bounds on the sheet) is ``INFERRED``
(``docs/formats/altium/draftsman.md``, "Drawing geometry"). Drill symbols, table cells, zone marks, the
dimension text and the view titles' place are Fenolite's drawings. Standard library only.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fenolite.backends.altium.read.cfb import is_compound, open_compound
from fenolite.backends.altium.read.draftsman import read_draftsman
from fenolite.backends.altium.read.dwfdraw import (
    BoardCopy,
    Drawing,
    Item,
    Page,
    Part,
    Pt,
    Stadium,
    read_drawing,
    snap_points,
)

SCHEMA = "fenolite.view_schematic.v0"
LIBRARY_SCHEMA = "fenolite.view_library.v0"
UM = 25_400 / 96
"""One document unit of 1/96 inch in micrometres."""
SHEET = "#ffffff"
WORKSPACE = "#4a4d52"
TEXT = "#000000"
TABLE_TEXT = 8
ROW = 14
"""Table rows of 14 units with text of 8 units (Fenolite's choice)."""
SYMBOL = 4.0
"""The half size of a drill symbol on the sheet, in units (Fenolite's choice)."""
SIDE_VIEWS = frozenset({"Right", "Left", "Front", "Back"})
VIEWS = frozenset({"BoardAssemblyViewData", "BoardFabricationViewData", "DrillViewView"})
TABLES = frozenset({"DrillTableBoardView", "LayerStackLegendView", "BillOfMaterialsView"})
PANEL_NOTE = (
    "This document holds an Embedded Board Array (a panel). Fenolite does not draw the array until its "
    "records are measured (docs/evidence/altium-pcb.md, Part Q); the board is drawn once."
)
FENOLITE_DRAWINGS = (
    "Drill symbols, table cells, zone marks, dimension texts and view titles are Fenolite's drawings; "
    "the views are the document's own copy of the board, placed as INFERRED."
)
_PARAM = re.compile(r"=([A-Za-z_][A-Za-z0-9_]*)")
_TURNS = {"Ccw0": 0, "Ccw90": 1, "Ccw180": 2, "Ccw270": 3, "0": 0, "90": 1, "180": 2, "270": 3}


def um(value: float) -> int:
    return round(value * UM)


def _turns(rotation: str) -> int:
    return _TURNS.get(rotation, 0)


def fill_parameters(text: str, parameters: dict[str, str]) -> str:
    """``text`` with each ``=Name`` that names a parameter replaced by its value; other text stays."""

    def value(match: re.Match[str]) -> str:
        return parameters.get(match.group(1).casefold(), match.group(0))

    return _PARAM.sub(value, text)


def _scale_text(scale: float) -> str:
    if scale >= 1:
        return f"{scale:g}:1"
    return f"1:{1 / scale:g}" if scale > 0 else "1:1"


def _length(value: float, metric: bool) -> str:
    """A length of 1/96 inch as the document's unit system shows it (Fenolite's number format)."""
    if metric:
        return f"{value * 25.4 / 96:.2f}mm"
    return f"{value * 1000 / 96:.1f}mil"


class _Sheet:
    """The primitives, objects and parts of one sheet, in micrometres."""

    def __init__(self, drawing: Drawing, height: float) -> None:
        self.drawing = drawing
        self.height = height
        self.prims: list[dict[str, Any]] = []
        self.objects: list[dict[str, Any]] = []
        self.comps: list[dict[str, Any]] = []
        self.fonts: list[dict[str, Any]] = []
        self._font_ids: dict[tuple[str, float], int] = {}
        self.current = -1
        self.notes: list[str] = []
        self.kinds: dict[str, int] = defaultdict(int)

    def font(self, family: str, size: float) -> int:
        """The index of the font ``family`` of ``size`` units of 1/96 inch (a font style's ``Size``)."""
        key = (family or "Arial", size or 13)
        if key not in self._font_ids:
            self._font_ids[key] = len(self.fonts)
            self.fonts.append(
                {
                    "name": key[0],
                    "size": round(key[1] * 72 / 96, 2),
                    "em": um(key[1]),
                    "bold": False,
                    "italic": False,
                    "underline": False,
                }
            )
        return self._font_ids[key]

    def style_font(self, style_id: str) -> int:
        style = self.drawing.fonts.get(style_id)
        return self.font(style.family, style.size) if style else self.font("Arial", 13)

    def line_style(self, style_id: str, default: str = TEXT) -> tuple[str, int]:
        style = self.drawing.lines.get(style_id)
        if style is None:
            return default, um(1)
        return style.color, max(um(style.thickness), 1)

    def xy(self, x: float, y: float) -> tuple[int, int]:
        """A sheet point (Y up from the lower-left corner) in the scene (micrometres, Y down from the top)."""
        return um(x), um(self.height - y)

    def box(self, x: float, y: float, w: float, h: float) -> tuple[int, int, int, int]:
        """The scene box of a sheet rectangle whose lower-left corner is (x, y)."""
        return um(x), um(self.height - y - h), um(x + w), um(self.height - y)

    def obj(self, kind: str, info: list[list[str]], comp: int = -1) -> int:
        self.objects.append({"k": kind, "net": -1, "comp": comp, "b": None, "info": info})
        self.current = len(self.objects) - 1
        return self.current

    def add(self, prim: dict[str, Any], box: tuple[int, int, int, int]) -> None:
        prim["o"] = self.current
        self.prims.append(prim)
        if self.current >= 0:
            ob = self.objects[self.current]["b"]
            self.objects[self.current]["b"] = (
                list(box)
                if ob is None
                else [min(ob[0], box[0]), min(ob[1], box[1]), max(ob[2], box[2]), max(ob[3], box[3])]
            )

    def line(self, pts: list[Pt], color: str, width: int, *, closed: bool = False, **extra: Any) -> None:
        if len(pts) < 2:
            return
        q = [self.xy(x, y) for x, y in pts]
        if closed:
            q.append(q[0])
        flat = [v for p in q for v in p]
        xs, ys = flat[0::2], flat[1::2]
        self.add({"k": "l", "p": flat, "c": color, "w": width, **extra}, (min(xs), min(ys), max(xs), max(ys)))

    def polygon(self, pts: list[Pt], color: str, width: int, fill: str | None) -> None:
        if len(pts) < 3:
            return
        flat = [v for x, y in pts for v in self.xy(x, y)]
        xs, ys = flat[0::2], flat[1::2]
        self.add(
            {"k": "g", "p": flat, "c": color, "w": width, "f": fill}, (min(xs), min(ys), max(xs), max(ys))
        )

    def rect(self, x: float, y: float, w: float, h: float, color: str, width: int, fill: str | None) -> None:
        box = self.box(x, y, w, h)
        self.add({"k": "r", "b": list(box), "c": color, "w": width, "f": fill}, box)

    def circle(self, c: Pt, r: float, color: str, width: int, fill: str | None = None) -> None:
        (x, y), ru = self.xy(*c), max(um(r), 1)
        self.add(
            {"k": "e", "x": x, "y": y, "rx": ru, "ry": ru, "c": color, "w": width, "f": fill},
            (x - ru, y - ru, x + ru, y + ru),
        )

    def text(
        self, at: Pt, s: str, font: int, color: str, *, h: str = "left", v: str = "top", rot: int = 0
    ) -> None:
        if not s:
            return
        em = self.fonts[font]["em"]
        x, y = self.xy(*at)
        lines = s.split("\n")
        width = max(1, int(0.55 * em * max(len(line) for line in lines)))
        height = int(em * 1.2 * len(lines))
        x0 = {"left": 0, "center": -width // 2, "right": -width}[h]
        y0 = {"bottom": -height, "center": -height // 2, "top": 0}[v]
        c, sn = [(1, 0), (0, 1), (-1, 0), (0, -1)][rot % 4]
        corners = [(x0, y0), (x0 + width, y0), (x0, y0 + height), (x0 + width, y0 + height)]
        pts = [(x + dx * c + dy * sn, y - dx * sn + dy * c) for dx, dy in corners]
        prim = {"k": "t", "x": x, "y": y, "s": s, "font": font, "c": color, "rot": rot % 4, "h": h, "v": v}
        self.add(
            prim,
            (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)),
        )


# --- view placement -------------------------------------------------------------------------------------


class _View:
    """The map from the board copy to a view on the sheet (``design.md`` decision 2)."""

    def __init__(self, item: Item, board: BoardCopy) -> None:
        f = item.fields
        self.scale: float = f["scale"] or 1.0
        self.location: Pt = f["location"]
        self.bottom = f["side"] == "Bottom"
        self.turns = _turns(f["rotation"])
        self.bx, self.by, self.bw, self.bh = board.bounds

    def size(self) -> Pt:
        w, h = self.bw * self.scale, self.bh * self.scale
        return (h, w) if self.turns % 2 else (w, h)

    def __call__(self, p: Pt) -> Pt:
        u = (self.bx + self.bw - p[0]) if self.bottom else (p[0] - self.bx)
        v = p[1] - self.by
        w, h = self.bw, self.bh
        for _ in range(self.turns):  # a quarter turn counter-clockwise, Y up
            u, v, w, h = h - v, u, h, w
        return (self.location[0] + u * self.scale, self.location[1] + v * self.scale)


def stadium(shape: Stadium) -> list[Pt]:
    """A ``Uni`` as a closed run of points: a rectangle of ``length`` by ``width`` along ``direction``, its
    corners rounded by ``radius``."""
    dx, dy = shape.direction
    norm = math.hypot(dx, dy) or 1.0
    dx, dy = dx / norm, dy / norm
    hw, hh = shape.length / 2, shape.width / 2
    r = max(0.0, min(shape.radius, hw, hh))
    local: list[Pt] = []
    for cx, cy, a0 in (
        (hw - r, hh - r, 0),
        (-hw + r, hh - r, 90),
        (-hw + r, -hh + r, 180),
        (hw - r, -hh + r, 270),
    ):
        if r <= 0:
            local.append((cx, cy))
            continue
        for k in range(4):
            a = math.radians(a0 + 30 * k)
            local.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    cx, cy = shape.centre
    return [(cx + x * dx - y * dy, cy + x * dy + y * dx) for x, y in local]


def _arc(centre: Pt, radius: float, a0: float, a1: float) -> list[Pt]:
    span = a1 - a0
    if span <= 0:
        span += 360
    steps = max(2, math.ceil(span / 5))
    return [
        (
            centre[0] + radius * math.cos(math.radians(a0 + span * k / steps)),
            centre[1] + radius * math.sin(math.radians(a0 + span * k / steps)),
        )
        for k in range(steps + 1)
    ]


def _drill_groups(board: BoardCopy) -> list[tuple[float, bool, int]]:
    """The holes by size and plating, smallest first: (size, plated, count)."""
    counts: dict[tuple[float, bool], int] = defaultdict(int)
    for hole in board.holes:
        counts[(round(hole.size, 4), hole.plated)] += 1
    return [(size, plated, n) for (size, plated), n in sorted(counts.items())]


def _symbol(sheet: _Sheet, kind: int, at: Pt, color: str, width: int) -> None:
    """Fenolite's drill symbol ``kind`` at ``at``: circle, cross, triangle, square, diamond, X, then a
    circle with a cross, a circle with an X and so on."""
    x, y, r = at[0], at[1], SYMBOL
    shape = kind % 6
    if shape == 0:
        sheet.circle(at, r, color, width)
    elif shape == 1:
        sheet.line([(x - r, y), (x + r, y)], color, width)
        sheet.line([(x, y - r), (x, y + r)], color, width)
    elif shape == 2:
        sheet.line([(x, y - r), (x + r, y + r * 0.8), (x - r, y + r * 0.8)], color, width, closed=True)
    elif shape == 3:
        sheet.line(
            [(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r)], color, width, closed=True
        )
    elif shape == 4:
        sheet.line([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], color, width, closed=True)
    else:
        sheet.line([(x - r, y - r), (x + r, y + r)], color, width)
        sheet.line([(x - r, y + r), (x + r, y - r)], color, width)
    if kind >= 6:
        sheet.circle(at, r * 1.4, color, width)


def _outline(sheet: _Sheet, view: _View, board: BoardCopy, color: str, width: int) -> None:
    for ring in (board.outline, *board.cutouts):
        sheet.line([view(p) for p in ring], color, width, closed=True)


def _part_params(part: Part) -> dict[str, str]:
    """The Properties rows of a part: its side and, from its box, its size on the board (not on the sheet)."""
    params = {"Side": part.side}
    if part.box is not None:
        w, h = part.box[2], part.box[3]
        params["Size on the board"] = (
            f"{w * 25.4 / 96:.3f} × {h * 25.4 / 96:.3f} mm ({w * 1000 / 96:.1f} × {h * 1000 / 96:.1f} mil)"
        )
    return params


def _assembly(sheet: _Sheet, item: Item, view: _View, board: BoardCopy) -> int:
    f = item.fields
    color, width = sheet.line_style(f["line"])
    part_color, part_width = sheet.line_style(f["component_line"], color)
    _outline(sheet, view, board, color, width)
    side = "Bottom" if view.bottom else "Top"
    largest = 5 * view.scale
    drawn = 0
    for part in board.parts:
        if part.side != side:
            continue
        index = len(sheet.comps)
        info = [["Designator", part.ref], ["Comment", part.comment], ["Side", part.side]]
        sheet.obj("comp", info, comp=index)
        rings = part.contours
        if not rings and part.box is not None:
            x, y, w, h = part.box
            rings = (((x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)),)
        for ring in rings:  # open strokes, as the document holds them
            sheet.line([view(p) for p in ring], part_color, part_width)
        if part.box is not None:
            x, y, w, h = part.box
            centre = view((x + w / 2, y + h / 2))
        elif part.pads:
            centre = view(
                (sum(p[0] for p in part.pads) / len(part.pads), sum(p[1] for p in part.pads) / len(part.pads))
            )
        else:
            centre = view(rings[0][0]) if rings else view((0.0, 0.0))
        size = largest
        if part.box is not None:  # the designator fits its part's box (Fenolite's choice)
            wide, high = part.box[2] * view.scale, part.box[3] * view.scale
            fit = min(wide / (0.6 * max(len(part.ref), 1)), high * 0.7)
            size = max(1.0, min(largest, round(fit * 2) / 2))
        sheet.text(centre, part.ref, sheet.font("Arial", size), part_color, h="center", v="center")
        box = sheet.objects[sheet.current]["b"]
        sheet.comps.append(
            {"ref": part.ref, "comment": part.comment, "lib": "", "b": box, "params": _part_params(part)}
        )
        sheet.current = -1
        drawn += 1
    return drawn


def _fabrication(sheet: _Sheet, item: Item, view: _View, board: BoardCopy) -> str:
    f = item.fields
    color, width = sheet.line_style(f["line"])
    layer = next((layer for layer in board.layers if layer.v7 == f["layer"]), None)
    _outline(sheet, view, board, color, width)
    if layer is None:
        return ""
    for shape in layer.stadiums:
        sheet.polygon([view(p) for p in stadium(shape)], color, 0, color)
    for arc in layer.arcs:
        sheet.line(
            [view(p) for p in _arc(arc.centre, arc.radius, arc.start, arc.end)],
            color,
            max(um(arc.thickness * view.scale), 1),
        )
    return layer.name


def _drill(sheet: _Sheet, item: Item, view: _View, board: BoardCopy) -> None:
    color, width = sheet.line_style(item.fields["line"])
    _outline(sheet, view, board, color, width)
    kinds = {(size, plated): k for k, (size, plated, _n) in enumerate(_drill_groups(board))}
    for hole in board.holes:
        _symbol(
            sheet, kinds[(round(hole.size, 4), hole.plated)], view(hole.centre), color, max(width // 2, 1)
        )


MM = 96 / 25.4
"""One millimetre in document units."""
SIDE_FILL = "#d8dcd2"
"""The board's section in a side view (Fenolite's choice)."""


def _side_axis(
    side: str, board: BoardCopy
) -> Callable[[tuple[float, float, float, float]], tuple[float, float]]:
    """The horizontal extent, in the view, of a box of the board copy (x, y, width, height), seen from
    ``side``: the board's X from the front, its Y from the right, mirrored from the back and the left."""
    bx, by, bw, bh = board.bounds
    if side == "Front":
        return lambda b: (b[0] - bx, b[0] + b[2] - bx)
    if side == "Back":
        return lambda b: (bx + bw - b[0] - b[2], bx + bw - b[0])
    if side == "Right":
        return lambda b: (b[1] - by, b[1] + b[3] - by)
    return lambda b: (by + bh - b[1] - b[3], by + bh - b[1])


class _SideView:
    """The map from a side view's own frame (``u`` along the view, ``z`` up from the board's upper face, the
    frame of its dimensions' snaps) to the sheet (``_side_view``)."""

    def __init__(self, item: Item, board: BoardCopy) -> None:
        f = item.fields
        frame = board.side_frames.get("Back" if f["side"] in ("Front", "Back") else "Right")
        self.ok = frame is not None and bool(board.outline)
        _fx, self.below, self.width, _height = frame or (0.0, 0.0, 0.0, 0.0)
        self.scale: float = f["scale"] or 1.0
        self.location: Pt = f["location"]
        self.thickness = board.thickness

    def __call__(self, p: Pt) -> Pt:
        u, z = p
        return (
            self.location[0] + u * self.scale,
            self.location[1] + (self.below + self.thickness + z) * self.scale,
        )


def _side_view(sheet: _Sheet, item: Item, board: BoardCopy) -> None:
    """A side view (change c0190, ``INFERRED``): the board's section and each part's box from the side, in the
    frame the document stores (``BoardBoundsBack`` for front and back, ``BoardBoundsRight`` for the sides).
    The frame's lower-left corner is the view's location; the board's lower face lies the frame's ``Y`` above
    it; a part spans ``MinZ`` to ``MinZ + Height`` from the face of its side."""
    f = item.fields
    side = f["side"]
    view = _SideView(item, board)
    if not view.ok:
        sheet.notes.append(f"A {side} side view: the document holds no frame for it, so it is not drawn.")
        return
    s, width, t = view.scale, view.width, board.thickness
    lowest = -t

    def box(u0: float, u1: float, z0: float, z1: float) -> list[Pt]:
        return [view((u0, z0)), view((u1, z0)), view((u1, z1)), view((u0, z1))]

    color, line = sheet.line_style(f["line"])
    part_color, part_line = sheet.line_style(f["component_line"] or f["line"])
    own = sheet.obj("view", [["View", "side view"], ["Side", side], ["Scale", _scale_text(s)]])
    sheet.polygon(box(0, width, -t, 0), color, line, SIDE_FILL)
    across = _side_axis(side, board)
    drawn, flat = 0, 0
    for part in board.parts:
        if part.box is None:
            continue
        u0, u1 = across(part.box)
        tall = part.height if part.height > 0 else MM
        flat += part.height <= 0
        z0, z1 = part.min_z, part.min_z + tall
        if part.side == "Bottom":
            z0, z1 = -t - z1, -t - z0
        lowest = min(lowest, z0)
        sheet.obj("comp", [["Designator", part.ref], ["Comment", part.comment], ["Side", part.side],
                           ["Height", f"{part.height / MM:.2f} mm"]])  # fmt: skip
        sheet.polygon(box(u0, u1, z0, z1), part_color, part_line, None)
        drawn += 1
    sheet.objects[own]["info"].append(["Parts", str(drawn)])
    sheet.current = own  # the title belongs to the view
    if flat:
        sheet.notes.append(f"{flat} part(s) without a height are drawn 1 mm high in the side views.")
    if f["show_title"] and f["title"]:
        values = dict(sheet.drawing.parameters) | {"viewside": side, "viewscale": _scale_text(s)}
        font = sheet.style_font(f["title_font"])
        x, y = view((width / 2, lowest))  # under what the view draws, as the top views' titles
        sheet.text(
            (x, y - 6), fill_parameters(f["title"], values), font, f["title_color"], h="center", v="top"
        )
    sheet.current = -1


def _callout(sheet: _Sheet, item: Item, numbers: dict[str, tuple[int, str]]) -> None:
    """A callout (change c0190, ``INFERRED``): a leader from its tag to the point it targets, with an arrow
    there, a short elbow at the tag, and the tag: the number of the note element it names (in the border that
    element has in its note), else its own text."""
    f = item.fields
    target = f["target"]
    elbow_at = (target[0] + f["leader"][0], target[1] + f["leader"][1])
    toward = -1.0 if f["elbow_side"] == "Left" else 1.0
    tag_at = (elbow_at[0] + toward * f["elbow"], elbow_at[1])
    color, width = sheet.line_style(f["line"], f["color"])
    found = numbers.get(f["note_element"]) if f["source"] == "NoteItem" else None
    text = f"{f['prefix']}{found[0]}" if found else f["custom"] or "?"
    sheet.obj("callout", [["Callout", text], ["Source", f["source"] or "custom text"]])
    sheet.line([tag_at, elbow_at, target], color, width)
    dx, dy = elbow_at[0] - target[0], elbow_at[1] - target[1]
    size = math.hypot(dx, dy) or 1.0
    ux, uy, head = dx / size, dy / size, 6.0
    sheet.polygon(
        [target, (target[0] + head * ux - head * 0.35 * uy, target[1] + head * uy + head * 0.35 * ux),
         (target[0] + head * ux + head * 0.35 * uy, target[1] + head * uy - head * 0.35 * ux)],
        color, width, color,
    )  # fmt: skip
    font = sheet.style_font(f["font"])
    em = sheet.fonts[font]["em"] / UM
    half = em * 0.8
    centre = (tag_at[0] + toward * half, tag_at[1])
    border = found[1] if found else "None"
    if border == "Circle":
        sheet.circle(centre, half, color, width)
    elif border != "None":
        sheet.rect(centre[0] - half, centre[1] - half, 2 * half, 2 * half, color, width, None)
    sheet.text(centre, text, font, f["color"], h="center", v="center")
    sheet.current = -1


def _view(sheet: _Sheet, item: Item, board: BoardCopy) -> None:
    f = item.fields
    if f["side"] in SIDE_VIEWS:
        _side_view(sheet, item, board)
        return
    if not board.outline:
        sheet.notes.append(f"{item.kind}: the document holds no board copy.")
        return
    view = _View(item, board)
    info = [["View", item.kind], ["Side", f["side"]], ["Scale", _scale_text(view.scale)]]
    own = sheet.obj("view", info)
    layer_name = ""
    if item.kind == "BoardAssemblyViewData":
        info.append(["Parts", str(_assembly(sheet, item, view, board))])
        sheet.current = own
    elif item.kind == "BoardFabricationViewData":
        layer_name = _fabrication(sheet, item, view, board)
        info.append(["Layer", layer_name or f"V7 id {f['layer']}"])
    else:
        _drill(sheet, item, view, board)
    if f["show_title"] and f["title"]:
        values = dict(sheet.drawing.parameters)
        values |= {"viewside": f["side"], "viewscale": _scale_text(view.scale), "viewlayername": layer_name}
        title = fill_parameters(f["title"], values)
        font = sheet.style_font(f["title_font"])
        w, _h = view.size()
        x, y = view.location
        sheet.text((x + w / 2, y - 6), title, font, f["title_color"], h="center", v="top")
    sheet.current = -1


# --- tables ---------------------------------------------------------------------------------------------


def _table(
    sheet: _Sheet,
    at: Pt,
    title: str,
    header: list[str],
    rows: list[list[str]],
    widths: list[float],
    color: str,
    width: int,
) -> None:
    font = sheet.font("Arial", TABLE_TEXT)
    title_font = sheet.font("Arial", TABLE_TEXT + 3)
    x0, y_end = at  # the lower-left corner; the rows run down from the top
    y0 = y_end + (len(rows) + 1) * ROW
    sheet.text((x0, y0 + 3), title, title_font, color, v="bottom")
    total = sum(widths)
    for r, row in enumerate([header, *rows]):
        y = y0 - r * ROW
        sheet.line([(x0, y), (x0 + total, y)], color, width)
        x = x0
        for c, cell in enumerate(row):
            sheet.text((x + 3, y - ROW / 2), cell, font, color, v="center")
            x += widths[c]
    sheet.line([(x0, y_end), (x0 + total, y_end)], color, width)
    x = x0
    for w in [0.0, *widths]:
        x += w
        sheet.line([(x, y0), (x, y_end)], color, width)


def _clip(text: str, chars: int) -> str:
    return text if len(text) <= chars else text[: chars - 1] + "…"


def _tables(sheet: _Sheet, item: Item, board: BoardCopy) -> None:
    f = item.fields
    color, width = sheet.line_style(f["line"])
    metric = sheet.drawing.metric
    title = f.get("table_title") or f["title"] or item.kind
    sheet.obj("table", [["Table", title]])
    if item.kind == "DrillTableBoardView":
        groups = _drill_groups(board)
        rows = [
            ["", str(n), _length(size, metric), "Plated" if plated else "Non-plated"]
            for size, plated, n in groups
        ]
        _table(
            sheet,
            f["location"],
            title,
            ["Symbol", "Count", "Hole size", "Plating"],
            rows,
            [40, 40, 70, 70],
            color,
            width,
        )
        for k in range(len(groups)):
            _symbol(
                sheet,
                k,
                (f["location"][0] + 20, f["location"][1] + (len(groups) - k - 0.5) * ROW),
                color,
                max(width // 2, 1),
            )
    elif item.kind == "LayerStackLegendView":
        rows = [
            [layer.name, layer.material, _length(layer.thickness, metric) if layer.thickness else ""]
            for layer in board.stack
        ]
        _table(
            sheet,
            f["location"],
            title,
            ["Layer", "Material", "Thickness"],
            rows,
            [110, 110, 70],
            color,
            width,
        )
    else:
        by_comment: dict[str, list[str]] = defaultdict(list)
        for part in board.parts:
            by_comment[part.comment].append(part.ref)
        rows = [
            [_clip(comment, 32), _clip(", ".join(sorted(refs)), 70), str(len(refs))]
            for comment, refs in sorted(by_comment.items())
        ]
        _table(
            sheet,
            f["location"],
            title,
            ["Comment", "Designators", "Quantity"],
            rows,
            [150, 330, 50],
            color,
            width,
        )
    sheet.current = -1


# --- sheet items ----------------------------------------------------------------------------------------


def _wrap(text: str, width: float, size: float) -> list[str]:
    """``text`` cut at its line breaks, then, when ``width`` is given, at spaces to fit ``width`` units with
    characters of about 0.55 of the font's ``size`` (Fenolite's estimate; the browser draws the font)."""
    per_line = max(1, int(width / (0.55 * size))) if width > 0 else 10_000
    out: list[str] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = ""
        for word in paragraph.split(" "):
            if line and len(line) + 1 + len(word) > per_line:
                out.append(line)
                line = word
            else:
                line = f"{line} {word}" if line else word
        out.append(line)
    return out


def _lines(
    sheet: _Sheet, at: Pt, rows: list[str], font: int, color: str, *, h: str, v: str, rot: int = 0
) -> None:
    """Rows of text whose block is aligned at ``at`` (``v`` is the block's vertical alignment)."""
    step = sheet.fonts[font]["em"] / UM * 1.2
    if rot % 2:
        for row in rows:  # turned texts keep one row each, side by side
            sheet.text(at, row, font, color, h=h, v=v, rot=rot)
            at = (at[0] + step, at[1])
        return
    top = {"top": at[1], "center": at[1] + step * len(rows) / 2, "bottom": at[1] + step * len(rows)}[v]
    for k, row in enumerate(rows):
        sheet.text((at[0], top - k * step), row, font, color, h=h, v="top")


def _text_item(sheet: _Sheet, item: Item) -> None:
    f = item.fields
    x, y, w, h = f["rect"]
    s = fill_parameters(f["text"], sheet.drawing.parameters)
    hz = {"Left": "left", "Center": "center", "Right": "right"}.get(f["h"], "left")
    vt = {"Top": "top", "Center": "center", "Bottom": "bottom"}.get(f["v"], "top")
    at = (
        {"left": x, "center": x + w / 2, "right": x + w}[hz],
        {"top": y + h, "center": y + h / 2, "bottom": y}[vt],
    )
    font = sheet.style_font(f["font"])
    rot = _turns(f["rotation"])
    sheet.obj("text", [["Text", f["text"]], ["Shown", s]])
    _lines(
        sheet,
        at,
        _wrap(s, 0, 0),
        font,
        f["color"],
        h=hz,
        v=vt,
        rot=rot,
    )
    sheet.current = -1


def _note(sheet: _Sheet, item: Item) -> None:
    f = item.fields
    x, y = f["start"]
    font = sheet.style_font(f["font"])
    size = sheet.fonts[font]["em"] / UM
    step = sheet.fonts[font]["em"] / UM * 1.2
    sheet.obj("note", [["Note", f["title"]], ["Elements", str(len(f["elements"]))]])
    if f["title_visible"] and f["title"]:
        title_font = sheet.style_font(f["title_font"]) if f["title_font"] else font
        sheet.text((x, y), fill_parameters(f["title"], sheet.drawing.parameters), title_font, f["color"])
        y -= sheet.fonts[title_font]["em"] / UM * 1.2 + f["spacing"]
    indent = 0.55 * size * 4
    for n, (text, postfix) in enumerate(f["elements"], start=1):
        sheet.text((x, y), f"{n}{postfix or '.'}", font, f["color"])
        rows = _wrap(fill_parameters(text, sheet.drawing.parameters), f["width"] - indent, size)
        _lines(sheet, (x + indent, y), rows, font, f["color"], h="left", v="top")
        y -= step * len(rows) + f["spacing"]
    sheet.current = -1


def _dimension(sheet: _Sheet, item: Item, views: dict[str, tuple[Item, _View | _SideView]]) -> None:
    """A linear dimension measured on the board copy: its anchors are the board points its snaps name, its
    dimension line passes through the reference point (relative to the first anchor), all in the frame of the
    view it snaps to (``draftsman.md``, "Drawing geometry", INFERRED)."""
    f = item.fields
    target = views.get(f["target"])
    first, second = (snap_points(snap) for snap in f["snaps"])
    if target is None or not first or not second:
        sheet.notes.append(
            "A dimension on a view that is not drawn, or with a snap of another form, is not drawn."
        )
        return
    view = target[1]
    a = first[0]
    b = second[1] if len(second) == 2 and f["snaps"][0] == f["snaps"][1] else second[0]
    (oax, oay), (obx, oby) = f["offsets"]
    a, b = (a[0] + oax, a[1] + oay), (b[0] + obx, b[1] + oby)
    ref = (a[0] + f["ref"][0], a[1] + f["ref"][1])
    dx, dy = f["direction"]
    norm = math.hypot(dx, dy) or 1.0
    dx, dy = dx / norm, dy / norm
    ta = (ref[0] - a[0]) * dx + (ref[1] - a[1]) * dy
    tb = (ref[0] - b[0]) * dx + (ref[1] - b[1]) * dy
    a2, b2 = (a[0] + dx * ta, a[1] + dy * ta), (b[0] + dx * tb, b[1] + dy * tb)
    value = math.dist(a2, b2)
    shown = f["override"] if f["override"] is not None else _length(value, f["units"] != "Imperial")
    shown = f"{f['prefix']}{shown}{f['suffix']}"
    color, width = sheet.line_style(f["line"], f["color"])
    pa, pb, qa, qb = view(a), view(b), view(a2), view(b2)
    sheet.obj("dimension", [["Dimension", shown], ["Measured", _length(value, True)]])
    sheet.line([pa, qa], color, width)
    sheet.line([pb, qb], color, width)
    sheet.line([qa, qb], color, width, s0=2, s1=2, ss=1)
    mid = ((qa[0] + qb[0]) / 2, (qa[1] + qb[1]) / 2)
    vertical = abs(qa[0] - qb[0]) < abs(qa[1] - qb[1])
    sheet.text(
        (mid[0] - 2, mid[1]) if vertical else (mid[0], mid[1] + 2),
        shown,
        sheet.style_font(f["font"]),
        f["color"],
        h="center",
        v="bottom",
        rot=1 if vertical else 0,
    )
    sheet.current = -1


def _plain(sheet: _Sheet, item: Item) -> None:
    f = item.fields
    if item.kind == "Line":
        color, width = sheet.line_style(f["style"])
        sheet.obj("graphic", [["Line", f["id"]]])
        sheet.line([f["start"], f["end"]], color, width)
    elif item.kind == "Rectangle":
        color, width = sheet.line_style(f["line"])
        fill = sheet.drawing.fills.get(f["fill"])
        solid = fill.color if fill is not None and fill.alpha > 0 and fill.pattern == "Solid" else None
        x, y, w, h = f["rect"]
        sheet.obj("graphic", [["Rectangle", f["id"]], ["Size", f"{w:g} × {h:g} units of 1/96 in"]])
        sheet.rect(x, y, w, h, color, width, solid)
    elif item.kind == "Picture":
        box = sheet.box(*f["rect"])
        sheet.obj("graphic", [["Picture", f["id"]]])
        src = f"data:image/png;base64,{f['bitmap']}" if f["bitmap"] else ""
        sheet.add({"k": "i", "b": list(box), "src": src, "w": 0}, box)
    sheet.current = -1


def _zones(sheet: _Sheet, page: Page) -> None:
    show, columns, rows = page.zones
    left, top, right, bottom = page.margin
    if not show or left <= 0:
        return
    x0, y0, x1, y1 = left, bottom, page.width - right, page.height - top
    width = um(1)
    font = sheet.font("Arial", 10)
    sheet.obj("zones", [["Zones", f"{columns} × {rows}"]])
    sheet.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], TEXT, width, closed=True)
    sheet.line(
        [
            (0.4 * left, 0.4 * top),
            (page.width - 0.4 * right, 0.4 * top),
            (page.width - 0.4 * right, page.height - 0.4 * bottom),
            (0.4 * left, page.height - 0.4 * bottom),
        ],
        TEXT,
        width,
        closed=True,
    )
    for k in range(columns):
        xa, xb = x0 + (x1 - x0) * k / columns, x0 + (x1 - x0) * (k + 1) / columns
        if k:
            sheet.line([(xa, 0.4 * top), (xa, y0)], TEXT, width)
            sheet.line([(xa, y1), (xa, page.height - 0.4 * bottom)], TEXT, width)
        label = str(k + 1)
        sheet.text(((xa + xb) / 2, 0.7 * top), label, font, TEXT, h="center", v="center")
        sheet.text(((xa + xb) / 2, page.height - 0.7 * bottom), label, font, TEXT, h="center", v="center")
    for k in range(rows):
        ya, yb = y0 + (y1 - y0) * k / rows, y0 + (y1 - y0) * (k + 1) / rows
        if k:
            sheet.line([(0.4 * left, ya), (x0, ya)], TEXT, width)
            sheet.line([(x1, ya), (page.width - 0.4 * right, ya)], TEXT, width)
        label = chr(ord("A") + rows - 1 - k) if rows <= 26 else str(rows - k)  # row 0 is the lowest
        sheet.text((0.7 * left, (ya + yb) / 2), label, font, TEXT, h="center", v="center")
        sheet.text((page.width - 0.7 * right, (ya + yb) / 2), label, font, TEXT, h="center", v="center")
    sheet.current = -1


def sheet_scene(drawing: Drawing, page: Page, *, name: str, evidence: str = "INFERRED") -> dict[str, Any]:
    """The schematic-form scene of one sheet of ``drawing``."""
    sheet = _Sheet(drawing, page.height)
    sheet.font("Arial", 13)
    _zones(sheet, page)
    views: dict[str, tuple[Item, _View | _SideView]] = {
        item.fields["id"]: (item, _View(item, drawing.board))
        for item in page.items
        if item.kind in VIEWS and item.fields["side"] not in SIDE_VIEWS and drawing.board.outline
    }
    for item in page.items:  # change c0190: a dimension on a side view snaps in the view's own frame
        if item.kind in VIEWS and item.fields["side"] in SIDE_VIEWS:
            side = _SideView(item, drawing.board)
            if side.ok:
                views[item.fields["id"]] = (item, side)
    numbers = {  # the note elements a callout can name: their number in their note and their border
        element: (n, border)
        for item in page.items
        if item.kind == "Note"
        for n, (element, border) in enumerate(item.fields.get("element_ids", []), start=1)
        if element
    }
    for item in page.items:
        sheet.kinds[item.kind] += 1
        if item.kind in VIEWS:
            _view(sheet, item, drawing.board)
        elif item.kind in TABLES:
            _tables(sheet, item, drawing.board)
        elif item.kind == "Text":
            _text_item(sheet, item)
        elif item.kind == "Note":
            _note(sheet, item)
        elif item.kind == "LinearDimension":
            _dimension(sheet, item, views)
        elif item.kind == "Callout":
            _callout(sheet, item, numbers)
        else:
            _plain(sheet, item)
    w, h = um(page.width), um(page.height)
    notes = list(dict.fromkeys(sheet.notes))
    if drawing.is_panel:
        notes.insert(0, PANEL_NOTE)
    notes.append(FENOLITE_DRAWINGS)
    counts: dict[str, Any] = {
        "items": len(page.items),
        "components": len(sheet.comps),
        "prims": len(sheet.prims),
    }
    counts["kinds"] = dict(sorted(sheet.kinds.items()))
    return {
        "schema": SCHEMA,
        "kind": "schematic",
        "meta": {
            "name": name,
            "sha256": "",
            "bytes": 0,
            "backend": "altium",
            "evidence": evidence,
            "counts": counts,
            "notes": notes,
        },
        "bounds": [0, 0, w, h],
        "sheet": {
            "w": w,
            "h": h,
            "color": SHEET,
            "grid": 0,
            "grid_color": None,
            "border": False,
            "margin": um(page.margin[0]),
            "zones": [page.zones[1], page.zones[2]],
            "title_block": False,
            "style": f"{page.width * 25.4 / 96:.0f} × {page.height * 25.4 / 96:.0f} mm",
            "text": "font",
            "workspace": WORKSPACE,
        },
        "fonts": sheet.fonts,
        "prims": sheet.prims,
        "objects": sheet.objects,
        "comps": sheet.comps,
        "nets": [],
        "overlays": [],
    }


def holds_panel(path: Path) -> bool:
    """Whether the Altium board at ``path`` holds an Embedded Board Array: its ``EmbeddedBoards6`` storage
    has a record count above 0 or data (``pcb-document.md``: its empty form is ``Header`` 0, no ``Data``)."""
    if path.suffix.lower() != ".pcbdoc":
        return False
    data = path.read_bytes()
    if not is_compound(data):
        return False
    document = open_compound(data)
    header = document.read("EmbeddedBoards6/Header") if "EmbeddedBoards6/Header" in document else b""
    count = int.from_bytes(header[:4], "little") if len(header) >= 4 else 0
    body = document.read("EmbeddedBoards6/Data") if "EmbeddedBoards6/Data" in document else b""
    return count > 0 or len(body) > 0


def drawing_scene(path: Path) -> dict[str, Any]:
    """The library-form scene of a ``.PCBDwf``: one item per sheet."""
    data = path.read_bytes()
    drawing = read_drawing(read_draftsman(data))
    items: list[dict[str, Any]] = []
    kinds: dict[str, int] = defaultdict(int)
    for n, page in enumerate(drawing.pages, start=1):
        label = f"Sheet {n}"
        scene = sheet_scene(drawing, page, name=f"{path.name} › {label}")
        for kind, count in scene["meta"]["counts"]["kinds"].items():
            kinds[kind] += count
        size = f"{page.width * 25.4 / 96:.0f} × {page.height * 25.4 / 96:.0f} mm"
        info = [["Sheet", str(n)], ["Size", size], ["Items", str(len(page.items))]]
        items.append({"name": label, "description": size, "info": info, "scene": scene})
    notes: list[str] = []
    if drawing.is_panel:
        notes.append(PANEL_NOTE)
    if drawing.skipped:
        notes.append(
            "Not drawn: " + ", ".join(f"{n} × {kind}" for kind, n in sorted(drawing.skipped.items())) + "."
        )
    return {
        "schema": LIBRARY_SCHEMA,
        "kind": "library",
        "lib": "drawing",
        "meta": {
            "name": path.name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "backend": "altium",
            "evidence": "INFERRED",
            "counts": {"items": len(items), "sheets": len(items), "kinds": dict(sorted(kinds.items()))},
            "notes": notes,
            "panel": drawing.is_panel,
            "source": re.split(r"[\\/]", drawing.source)[-1],
        },
        "items": items,
        "overlays": [],
    }


def summary(scene: dict[str, Any]) -> dict[str, Any]:
    """The part of a drawing scene that a reply carries."""
    counts = scene["meta"]["counts"]
    return {
        "kind": "drawing",
        "counts": {"sheets": counts["sheets"], **counts["kinds"]},
        "sheets": [item["name"] for item in scene["items"]],
        "panel": scene["meta"]["panel"],
    }


__all__ = [
    "PANEL_NOTE",
    "drawing_scene",
    "fill_parameters",
    "holds_panel",
    "sheet_scene",
    "stadium",
    "summary",
]
