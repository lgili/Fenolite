# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of a KiCad schematic sheet for the viewer page (capability native-themes, change c0178).

``build_kicad_schematic_scene(text, ...)`` turns a ``.kicad_sch`` into the ``fenolite.view_schematic.v0``
scene of change c0177, so the page draws it as it draws an Altium sheet: integer micrometres from the
paper's top-left corner, Y downwards, primitives in file order, selectable objects, parts and the nets of the
sheet. Colours come from a palette's schematic roles (``fenolite.view.themes``), texts are stroke texts
(``sheet.text == "stroke"``), as KiCad draws its own stroke font.

Symbols are placed by the rule of ``docs/formats/kicad/schematic.md``: a library point (Y up) is turned by
the instance angle, then mirrored, then moved, with Y turned down. Pin shapes, label flags, the frame and
the title block are Fenolite's drawings; the notes say so. Standard library only.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Any

from fenolite.backends.kicad.schlayout import turned
from fenolite.backends.kicad.sexpr import Atom, Node, parse
from fenolite.core.errors import FormatError
from fenolite.view.themes import colour_note

SCHEMA = "fenolite.view_schematic.v0"
MM = 1_000
"""Micrometres per millimetre."""
PAPERS: dict[str, tuple[float, float]] = {
    "A5": (210, 148),
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
    "A1": (841, 594),
    "A0": (1189, 841),
    "A": (279.4, 215.9),
    "B": (431.8, 279.4),
    "C": (558.8, 431.8),
    "D": (863.6, 558.8),
    "E": (1117.6, 863.6),
    "USLetter": (279.4, 215.9),
    "USLegal": (355.6, 215.9),
    "USLedger": (431.8, 279.4),
}
"""Paper sizes in millimetres, landscape (ISO 216 and ANSI sizes)."""
LINE = 152
"""The width of a line written with width 0, in µm (Fenolite's choice: 6 mil)."""
BUS = 305
TEXT = 1_270
"""The text size of a text written without one, in µm."""
GLYPH = 0.62
"""The glyph width of Fenolite's stroke font as a fraction of the text height, for KiCad texts."""
SKIPPED = ("image", "text_box", "table", "rule_area", "netclass_flag", "directive_label")
FENOLITE_DRAWINGS = (
    "Pin shapes, label flags, the frame and the title block are Fenolite's drawings; texts use Fenolite's "
    "stroke font, so their widths may differ a little from KiCad's."
)

Pt = tuple[int, int]


def _um(atom: Node | Atom | None) -> int:
    if not isinstance(atom, Atom):
        return 0
    try:
        return round(atom.to_nm(exact=False) / 1000)
    except ValueError:
        return 0


def _nums(node: Node | None) -> list[int]:
    return [_um(a) for a in node.atoms()] if node is not None else []


def _float(node: Node | None, index: int = 0, default: float = 0.0) -> float:
    if node is None:
        return default
    atoms = node.atoms()
    try:
        return float(atoms[index].value) if len(atoms) > index else default
    except ValueError:
        return default


def _text(node: Node, index: int = 0) -> str:
    atoms = node.atoms()
    return atoms[index].value if len(atoms) > index else ""


def _flag(node: Node | None, name: str) -> bool:
    """Whether ``node`` holds ``(name yes)``, ``(name)`` or the bare atom ``name``."""
    if node is None:
        return False
    if any(a.value == name for a in node.atoms()):
        return True
    child = node.find(name)
    return child is not None and (not child.atoms() or child.atoms()[0].value != "no")


def _rgb(node: Node | None) -> str | None:
    """A ``(color r g b a)`` that is not the default ``0 0 0 0``, as ``#rrggbb``."""
    if node is None:
        return None
    values = [_float(node, k) for k in range(4)]
    if len(node.atoms()) < 3 or all(v == 0 for v in values):
        return None
    r, g, b = (max(0, min(255, round(v))) for v in values[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


class _Place:
    """The placement of a symbol instance: origin, angle and mirror."""

    def __init__(self, x: int, y: int, angle: int, mirror: str) -> None:
        self.x, self.y, self.angle, self.mirror = x, y, angle % 360, mirror

    def pt(self, lx: int, ly: int) -> Pt:
        """A library point (Y up, µm) on the sheet."""
        px, py = turned(lx, ly, self.angle, self.mirror)
        return (self.x + px, self.y - py)

    def vec(self, dx: int, dy: int) -> Pt:
        px, py = turned(dx, dy, self.angle, self.mirror)
        return (px, -py)


IDENT = _Place(0, 0, 0, "")


class _Builder:
    def __init__(self, palette: dict[str, Any]) -> None:
        self.roles: dict[str, str] = palette["schematic"]
        self.prims: list[dict[str, Any]] = []
        self.objects: list[dict[str, Any]] = []
        self.comps: list[dict[str, Any]] = []
        self.current = -1
        self.box = [0, 0, 0, 0]
        self.notes: list[str] = []

    def color(self, role: str) -> str:
        return self.roles.get(role) or "#000000"

    def add(self, prim: dict[str, Any], bbox: Sequence[int]) -> None:
        prim["o"] = self.current
        self.prims.append(prim)
        b = self.box
        b[0], b[1], b[2], b[3] = (
            min(b[0], bbox[0]),
            min(b[1], bbox[1]),
            max(b[2], bbox[2]),
            max(b[3], bbox[3]),
        )
        if self.current >= 0:
            obj = self.objects[self.current]
            if prim["k"] == "t" and obj["k"] == "comp":
                return
            ob = obj["b"]
            obj["b"] = (
                list(bbox)
                if ob is None
                else [min(ob[0], bbox[0]), min(ob[1], bbox[1]), max(ob[2], bbox[2]), max(ob[3], bbox[3])]
            )

    def line(self, pts: Sequence[Pt], color: str, width: int, dash: int = 0) -> None:
        if len(pts) < 2:
            return
        flat = [v for p in pts for v in p]
        xs, ys, h = flat[0::2], flat[1::2], width // 2
        prim: dict[str, Any] = {"k": "l", "p": flat, "c": color, "w": width}
        if dash:
            prim["d"] = dash
        self.add(prim, (min(xs) - h, min(ys) - h, max(xs) + h, max(ys) + h))

    def polygon(self, pts: Sequence[Pt], color: str, width: int, fill: str | None) -> None:
        flat = [v for p in pts for v in p]
        xs, ys = flat[0::2], flat[1::2]
        self.add(
            {"k": "g", "p": flat, "c": color, "w": width, "f": fill}, (min(xs), min(ys), max(xs), max(ys))
        )

    def circle(self, c: Pt, r: int, color: str, width: int, fill: str | None) -> None:
        self.add(
            {"k": "e", "x": c[0], "y": c[1], "rx": r, "ry": r, "c": color, "w": width, "f": fill},
            (c[0] - r, c[1] - r, c[0] + r, c[1] + r),
        )

    def text(
        self,
        at: Pt,
        s: str,
        size: int,
        color: str,
        *,
        rot: int = 0,
        h: str = "center",
        v: str = "center",
        role: str = "",
        ol: list[int] | None = None,
    ) -> None:
        if not s:
            return
        lines = s.split("\n")
        width = int(size * 0.95 * max(len(line) for line in lines))
        height = int(size * 1.4 * len(lines))
        x0 = {"left": 0, "center": -width // 2, "right": -width}[h]
        y0 = {"bottom": -height, "center": -height // 2, "top": 0}[v]
        c, sn = [(1, 0), (0, 1), (-1, 0), (0, -1)][rot % 4]
        corners = [(x0, y0), (x0 + width, y0), (x0, y0 + height), (x0 + width, y0 + height)]
        pts = [(at[0] + dx * c + dy * sn, at[1] - dx * sn + dy * c) for dx, dy in corners]
        prim: dict[str, Any] = {
            "k": "t",
            "x": at[0],
            "y": at[1],
            "s": s,
            "font": 0,
            "c": color,
            "rot": rot % 4,
            "h": h,
            "v": v,
            "sz": size,
            "gw": round(size * GLYPH),
            "th": max(size // 8, 1),
        }
        if role:
            prim["role"] = role
        if ol:
            prim["ol"] = ol
        self.add(
            prim,
            (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)),
        )

    def obj(self, kind: str, *, comp: int = -1, info: list[list[str]] | None = None, **extra: Any) -> int:
        self.objects.append({"k": kind, "net": -1, "comp": comp, "b": None, "info": info or [], **extra})
        self.current = len(self.objects) - 1
        return self.current

    def done(self) -> None:
        self.current = -1


# --- effects and strokes ---------------------------------------------------------------------------------


def _effects(node: Node) -> tuple[int, str, str, bool]:
    """The text size (µm), horizontal and vertical justification and the hidden flag of ``node``'s
    ``effects`` (a ``hide`` beside the effects counts as well)."""
    effects = node.find("effects")
    size = TEXT
    h, v = "center", "center"
    hidden = _flag(node, "hide")
    if effects is not None:
        font = effects.find("font")
        sizes = _nums(font.find("size") if font is not None else None)
        if sizes:
            size = sizes[0] or TEXT
        justify = effects.find("justify")
        if justify is not None:
            words = {a.value for a in justify.atoms()}
            h = "left" if "left" in words else "right" if "right" in words else "center"
            v = "top" if "top" in words else "bottom" if "bottom" in words else "center"
        hidden = hidden or _flag(effects, "hide")
    return size, h, v, hidden


def _stroke(node: Node, role_color: str, default: int = LINE) -> tuple[str, int, int]:
    stroke = node.find("stroke")
    width, color, dash = default, role_color, 0
    if stroke is not None:
        widths = _nums(stroke.find("width"))
        width = (widths[0] if widths else 0) or default
        color = _rgb(stroke.find("color")) or role_color
        kind = stroke.find("type")
        dash = {"dash": 1, "dot": 2, "dash_dot": 3, "dash_dot_dot": 3}.get(
            _text(kind) if kind is not None else "", 0
        )
    return color, width, dash


def _fill(b: _Builder, node: Node, outline: str) -> str | None:
    fill = node.find("fill")
    if fill is None:
        return None
    kind = fill.find("type")
    kind_name = _text(kind) if kind is not None else ""
    if kind_name == "outline":
        return outline
    if kind_name == "background":
        return b.color("component_body")
    if kind_name == "color":
        return _rgb(fill.find("color"))
    return None


# --- graphics -------------------------------------------------------------------------------------------


def _xy(node: Node | None) -> Pt:
    values = _nums(node)
    return (values[0], values[1]) if len(values) >= 2 else (0, 0)


def _arc(b: _Builder, s: Pt, m: Pt, e: Pt, color: str, width: int, fill: str | None) -> None:
    """An arc through three sheet points, as an ``a`` primitive (angles counter-clockwise, Y up)."""
    (x1, y1), (x2, y2), (x3, y3) = s, m, e
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if d == 0:
        b.line([s, m, e], color, width)
        return
    q1, q2, q3 = x1 * x1 + y1 * y1, x2 * x2 + y2 * y2, x3 * x3 + y3 * y3
    cx = (q1 * (y2 - y3) + q2 * (y3 - y1) + q3 * (y1 - y2)) / d
    cy = (q1 * (x3 - x2) + q2 * (x1 - x3) + q3 * (x2 - x1)) / d
    r = math.hypot(x1 - cx, y1 - cy)

    def ang(x: int, y: int) -> float:
        return math.degrees(math.atan2(-(y - cy), x - cx)) % 360

    a1, am, a3 = ang(x1, y1), ang(x2, y2), ang(x3, y3)
    ccw = (am - a1) % 360 < (a3 - a1) % 360
    a0, a2 = (a1, a3) if ccw else (a3, a1)
    if a2 < a0:
        a2 += 360
    ri = round(r)
    prim: dict[str, Any] = {
        "k": "a",
        "x": round(cx),
        "y": round(cy),
        "rx": ri,
        "ry": ri,
        "a0": round(a0, 3),
        "a1": round(a2, 3),
        "c": color,
        "w": width,
        "f": None,
    }
    if fill:
        prim |= {"pie": True, "f": fill}
    b.add(prim, (round(cx) - ri, round(cy) - ri, round(cx) + ri, round(cy) + ri))


def _graphic(b: _Builder, node: Node, place: _Place, role: str, lib: bool) -> bool:
    """One graphic item (library frame when ``lib``); ``False`` when ``node`` is none."""
    base = b.color(role)
    color, width, dash = _stroke(node, base)
    fill = _fill(b, node, color)

    def p(pair: Pt) -> Pt:
        return place.pt(pair[0], pair[1]) if lib else pair

    name = node.name
    if name == "rectangle":
        a, z = p(_xy(node.find("start"))), p(_xy(node.find("end")))
        if fill:
            b.polygon([a, (z[0], a[1]), z, (a[0], z[1])], color, width, fill)
        else:
            b.line([a, (z[0], a[1]), z, (a[0], z[1]), a], color, width, dash)
    elif name == "polyline":
        pts = [p(_xy(xy)) for xy in (node.find("pts") or Node(Atom.symbol("pts"))).nodes("xy")]
        if fill and len(pts) > 2:
            b.polygon(pts, color, width, fill)
        else:
            b.line(pts, color, width, dash)
    elif name == "circle":
        c = p(_xy(node.find("center")))
        radius = _nums(node.find("radius"))
        b.circle(c, radius[0] if radius else 0, color, width, fill)
    elif name == "arc":
        _arc(
            b,
            p(_xy(node.find("start"))),
            p(_xy(node.find("mid"))),
            p(_xy(node.find("end"))),
            color,
            width,
            fill,
        )
    elif name == "bezier":
        pts = [v for xy in (node.find("pts") or Node(Atom.symbol("pts"))).nodes("xy") for v in p(_xy(xy))]
        if len(pts) >= 4:
            xs, ys = pts[0::2], pts[1::2]
            b.add({"k": "b", "p": pts, "c": color, "w": width}, (min(xs), min(ys), max(xs), max(ys)))
    elif name == "text":
        at = node.find("at")
        values = _nums(at)
        size, h, v, hidden = _effects(node)
        if hidden:
            return True
        point = p((values[0], values[1])) if len(values) >= 2 else (0, 0)
        degrees = _float(at, 2)
        degrees = degrees / 10 if abs(degrees) > 360 else degrees  # library texts may hold tenths of a degree
        rot = (round(degrees / 90) + (place.angle // 90 if lib else 0)) % 2
        b.text(
            point,
            _text(node).replace("\\n", "\n"),
            size,
            base if lib else b.color("note"),
            rot=rot,
            h=h,
            v=v,
            role="note",
        )
    else:
        return False
    return True


# --- symbols --------------------------------------------------------------------------------------------

_UNIT = re.compile(r"_(\d+)_(\d+)$")


def _definitions(root: Node) -> dict[str, Node]:
    found: dict[str, Node] = {}
    libs = root.find("lib_symbols")
    for symbol in libs.nodes("symbol") if libs is not None else ():
        found[_text(symbol)] = symbol
    return found


def _units(definition: Node, unit: int, style: int) -> list[Node]:
    out: list[Node] = []
    for sub in definition.nodes("symbol"):
        match = _UNIT.search(_text(sub))
        if match is None:
            continue
        u, s = int(match.group(1)), int(match.group(2))
        if u in (0, unit) and s in (0, style):
            out.append(sub)
    return out


def _unit_count(definition: Node) -> int:
    counts = [int(m.group(1)) for sub in definition.nodes("symbol") if (m := _UNIT.search(_text(sub)))]
    return max(counts + [1])


def _pin(
    b: _Builder, pin: Node, place: _Place, names: tuple[bool, int], numbers: bool
) -> tuple[Pt, str, str, str]:
    """Draw one pin; its connection point, number, name and electrical type."""
    atoms = pin.atoms()
    etype = atoms[0].value if atoms else "passive"
    shape = atoms[1].value if len(atoms) > 1 else "line"
    at = pin.find("at")
    values = _nums(at)
    lx, ly = (values[0], values[1]) if len(values) >= 2 else (0, 0)
    angle = round(_float(at, 2)) % 360
    length_nums = _nums(pin.find("length"))
    length = length_nums[0] if length_nums else 2_540
    step = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}.get(angle, (1, 0))
    conn = place.pt(lx, ly)
    body = place.pt(lx + step[0] * length, ly + step[1] * length)
    name_node, number_node = pin.find("name"), pin.find("number")
    name = _text(name_node) if name_node is not None else ""
    number = _text(number_node) if number_node is not None else ""
    if _flag(pin, "hide"):
        return conn, number, name, etype
    color = b.color("pin")
    dx = (body[0] - conn[0]) // max(1, abs(body[0] - conn[0])) if body[0] != conn[0] else 0
    dy = (body[1] - conn[1]) // max(1, abs(body[1] - conn[1])) if body[1] != conn[1] else 0
    px, py = (0, -1) if dx else (-1, 0)
    start = conn
    end = body
    if shape in ("inverted", "inverted_clock"):
        r = 318
        b.circle((body[0] - dx * r, body[1] - dy * r), r, color, LINE, None)
        end = (body[0] - dx * 2 * r, body[1] - dy * 2 * r)
    b.line([start, end], color, LINE)
    if shape in ("clock", "inverted_clock", "clock_low", "edge_clock_high"):
        w, d = 500, 600
        b.line(
            [
                (body[0] + px * w, body[1] + py * w),
                (body[0] + dx * d, body[1] + dy * d),
                (body[0] - px * w, body[1] - py * w),
            ],
            color,
            LINE,
        )
    if shape in ("input_low", "clock_low", "edge_clock_high"):
        b.line(
            [
                body,
                (body[0] - dx * 1_000 + px * 600, body[1] - dy * 1_000 + py * 600),
                (body[0] - dx * 1_000, body[1] - dy * 1_000),
            ],
            color,
            LINE,
        )
    elif shape == "output_low":
        b.line(
            [(body[0] + px * 600, body[1] + py * 600), (body[0] - dx * 1_000, body[1] - dy * 1_000)],
            color,
            LINE,
        )
    rot = 0 if dx else 1
    along = dx if dx else -dy
    show_names, offset = names
    name_size = _effects(name_node)[0] if name_node is not None else TEXT
    number_size = _effects(number_node)[0] if number_node is not None else TEXT
    shown_name = "" if name == "~" else name
    text_name, marks = _overbar(shown_name)
    mid = ((conn[0] + body[0]) // 2, (conn[1] + body[1]) // 2)
    gap = 250
    if show_names and text_name:
        if offset > 0:
            at_name = (body[0] + dx * offset, body[1] + dy * offset)
            b.text(
                at_name,
                text_name,
                name_size,
                b.color("pin_name"),
                rot=rot,
                h="left" if along > 0 else "right",
                v="center",
                role="pin-name",
                ol=marks,
            )
        else:
            b.text(
                (mid[0] + px * gap, mid[1] + py * gap),
                text_name,
                name_size,
                b.color("pin_name"),
                rot=rot,
                v="bottom",
                role="pin-name",
                ol=marks,
            )
    if numbers and number:
        if offset > 0 or not (show_names and text_name):
            b.text(
                (mid[0] + px * gap, mid[1] + py * gap),
                number,
                number_size,
                b.color("pin_number"),
                rot=rot,
                v="bottom",
                role="pin-number",
            )
        else:
            b.text(
                (mid[0] - px * gap, mid[1] - py * gap),
                number,
                number_size,
                b.color("pin_number"),
                rot=rot,
                v="top",
                role="pin-number",
            )
    return conn, number, name, etype


def _overbar(text: str) -> tuple[str, list[int]]:
    """KiCad's ``~{…}`` overbar as plain text and the indexes of the overlined characters."""
    out: list[str] = []
    marks: list[int] = []
    k = 0
    while k < len(text):
        if text.startswith("~{", k):
            end = text.find("}", k + 2)
            end = len(text) if end < 0 else end
            for ch in text[k + 2 : end]:
                marks.append(len(out))
                out.append(ch)
            k = end + 1
        else:
            out.append(text[k])
            k += 1
    return "".join(out), marks


def _properties(node: Node) -> dict[str, Node]:
    return {_text(p): p for p in node.nodes("property")}


def _field(b: _Builder, prop: Node, text: str, role: str, symbol_angle: int) -> None:
    size, h, v, hidden = _effects(prop)
    if hidden or not text or text == "~":
        return
    at = prop.find("at")
    values = _nums(at)
    if len(values) < 2:
        return
    rot = (round(_float(at, 2) / 90) + symbol_angle // 90) % 2
    b.text((values[0], values[1]), text, size, b.color(role), rot=rot, h=h, v=v, role=role)


# --- labels ---------------------------------------------------------------------------------------------

DIRS: dict[int, Pt] = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}
"""A text angle as the scene direction it reads in (Y down)."""


def _flag_shape(
    b: _Builder, at: Pt, angle: int, text: str, size: int, shape: str, color: str, hier: bool
) -> None:
    """A global label's flag (or a hierarchical label's arrow) at its connection point, with its text."""
    ux, uy = DIRS.get(angle % 360, (1, 0))  # the body lies in the reading direction from the point
    vx, vy = -uy, ux
    half = round(size * 0.7)

    def q(a: int, c: int) -> Pt:
        return (at[0] + ux * a + vx * c, at[1] + uy * a + vy * c)

    if hier:
        length = 2 * half
        tips = {
            "input": (True, False),
            "output": (False, True),
            "bidirectional": (True, True),
            "tri_state": (True, True),
        }
        near, far = tips.get(shape, (False, False))
        pts = [q(half if near else 0, -half), q(length - half if far else length, -half)]
        if far:
            pts.append(q(length, 0))
        pts += [q(length - half if far else length, half), q(half if near else 0, half)]
        if near:
            pts.append(q(0, 0))
        b.line([*pts, pts[0]], color, LINE)
        text_at = q(length + size // 2, 0)
    else:
        length = int(size * 0.95 * len(text)) + 2 * half + size // 2
        near = shape in ("input", "bidirectional", "tri_state")
        far = shape in ("output", "bidirectional", "tri_state")
        pts = [q(half if near else 0, -half), q(length - half if far else length, -half)]
        if far:
            pts.append(q(length, 0))
        pts += [q(length - half if far else length, half), q(half if near else 0, half)]
        if near:
            pts.append(q(0, 0))
        b.line([*pts, pts[0]], color, LINE)
        text_at = q(half + size // 3, 0)
    rot = 1 if uy else 0
    along = ux if ux else -uy
    b.text(text_at, text, size, color, rot=rot, h="left" if along > 0 else "right", v="center", role="label")


# --- paper, frame and title block -----------------------------------------------------------------------


def _paper(root: Node) -> tuple[int, int, str]:
    paper = root.find("paper")
    name = _text(paper) if paper is not None else "A4"
    if name == "User" and paper is not None:
        values = _nums(paper)
        if len(values) >= 2:
            return values[0], values[1], "User"
    w, h = PAPERS.get(name, PAPERS["A4"])
    if paper is not None and any(a.value == "portrait" for a in paper.atoms()):
        w, h = h, w
    return round(w * MM), round(h * MM), name


def _frame(b: _Builder, w: int, h: int, root: Node, name: str, paper: str) -> None:
    color = b.color("worksheet")
    m, inner = 10 * MM, 12 * MM
    b.line([(m, m), (w - m, m), (w - m, h - m), (m, h - m), (m, m)], color, LINE)
    b.line(
        [(inner, inner), (w - inner, inner), (w - inner, h - inner), (inner, h - inner), (inner, inner)],
        color,
        LINE,
    )
    nx, ny = max(1, round((w - 2 * m) / (50 * MM))), max(1, round((h - 2 * m) / (50 * MM)))
    for i in range(nx):
        x = m + (w - 2 * m) * i // nx
        if i:
            b.line([(x, m), (x, inner)], color, LINE)
            b.line([(x, h - inner), (x, h - m)], color, LINE)
        cx = m + (w - 2 * m) * (2 * i + 1) // (2 * nx)
        for y in (m + MM, h - m - MM):
            b.text((cx, y), str(i + 1), 1_300, color, role="zone")
    for j in range(ny):
        y = m + (h - 2 * m) * j // ny
        if j:
            b.line([(m, y), (inner, y)], color, LINE)
            b.line([(w - inner, y), (w - m, y)], color, LINE)
        cy = m + (h - 2 * m) * (2 * j + 1) // (2 * ny)
        for x in (m + MM, w - m - MM):
            b.text((x, cy), chr(ord("A") + j % 26), 1_300, color, role="zone")
    block = root.find("title_block")
    fields: dict[str, str] = {}
    for child in block.nodes() if block is not None else ():
        if child.name == "comment":
            fields[f"comment{_text(child)}"] = _text(child, 1)
        else:
            fields[child.name] = _text(child)
    x1, y1 = w - inner, h - inner
    x0, y0 = x1 - 110 * MM, y1 - 32 * MM
    b.line([(x0, y1), (x0, y0), (x1, y0)], color, LINE)
    for y in (y1 - 24 * MM, y1 - 16 * MM, y1 - 8 * MM):
        b.line([(x0, y), (x1, y)], color, LINE)
    b.line([(x0 + 70 * MM, y1 - 16 * MM), (x0 + 70 * MM, y1 - 8 * MM)], color, LINE)
    small, big = 1_270, 2_000

    def put(x: int, y: int, s: str, size: int = small) -> None:
        b.text((x0 + x, y), s, size, color, h="left", v="center", role="title")

    company = fields.get("company", "")
    comments = [fields.get(f"comment{k}", "") for k in (1, 2)]
    put(MM, y0 + 2 * MM, company)
    put(MM, y0 + 5 * MM, " · ".join(c for c in comments if c))
    put(MM, y1 - 20 * MM, f"Title: {fields.get('title', '')}", big)
    put(MM, y1 - 12 * MM, f"Size: {paper}   Date: {fields.get('date', '')}")
    put(71 * MM, y1 - 12 * MM, f"Rev: {fields.get('rev', '')}")
    put(MM, y1 - 4 * MM, f"File: {name}")


# --- nets -----------------------------------------------------------------------------------------------


class _Union:
    def __init__(self) -> None:
        self.parent: dict[Any, Any] = {}

    def find(self, a: Any) -> Any:
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def join(self, a: Any, b: Any) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _on(p: Pt, a: Pt, z: Pt) -> bool:
    (x, y), (x1, y1), (x2, y2) = p, a, z
    if (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1) != 0:
        return False
    return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


# --- the scene ------------------------------------------------------------------------------------------


def build_kicad_schematic_scene(
    text: str, *, name: str, data: bytes = b"", palette: dict[str, Any], evidence: str = "INFERRED"
) -> dict[str, Any]:
    """The scene of one KiCad schematic sheet (see the module text)."""
    root = parse(text, file=name)
    if root.name != "kicad_sch":
        raise FormatError(f"{name} is not a KiCad schematic (root {root.name!r})", file=name)
    b = _Builder(palette)
    w, h, paper = _paper(root)
    b.box = [0, 0, w, h]
    _frame(b, w, h, root, name, paper)
    defs = _definitions(root)
    union = _Union()
    points: list[tuple[Pt, Any]] = []
    """Electrical points and the union node each belongs to."""
    named: dict[Any, tuple[int, str]] = {}
    """Union node → (priority, name) of what names it: labels 0, power symbols 1."""
    wires: list[tuple[int, Pt, Pt]] = []
    pin_obj: list[tuple[int, Any]] = []
    ident_obj: list[tuple[int, Any]] = []
    pins_of: list[tuple[Any, str]] = []
    skipped: dict[str, int] = {}
    wire_count = 0
    for item in root.nodes():
        kind = item.name
        if kind == "symbol":
            _symbol(b, item, defs, union, points, named, pin_obj, pins_of)
        elif kind in ("wire", "bus"):
            pts = [_xy(xy) for xy in (item.find("pts") or Node(Atom.symbol("pts"))).nodes("xy")]
            role = "wire" if kind == "wire" else "bus"
            color, width, dash = _stroke(item, b.color(role), LINE if kind == "wire" else BUS)
            index = b.obj(kind, info=[["Wire" if kind == "wire" else "Bus", ""]])
            b.line(pts, color, width, dash)
            b.done()
            if kind == "wire":
                key = ("wire", wire_count)
                wire_count += 1
                union.find(key)
                for a, z in zip(pts, pts[1:], strict=False):
                    wires.append((index, a, z))
                    points += [(a, key), (z, key)]
                pin_obj.append((index, key))
        elif kind == "bus_entry":
            at, size = _xy(item.find("at")), _xy(item.find("size"))
            color, width, _ = _stroke(item, b.color("bus"))
            b.obj("entryline", info=[["Bus Entry", ""]])
            b.line([at, (at[0] + size[0], at[1] + size[1])], color, width)
            b.done()
        elif kind == "junction":
            at = _xy(item.find("at"))
            diameter = _nums(item.find("diameter"))
            r = diameter[0] // 2 if diameter and diameter[0] else 457
            color = _rgb(item.find("color")) or b.color("junction")
            index = b.obj("junction", info=[["Junction", ""]])
            b.circle(at, r, color, 0, color)
            b.done()
            key = ("junction", index)
            points.append((at, key))
            pin_obj.append((index, key))
        elif kind == "no_connect":
            at = _xy(item.find("at"))
            s, color = 635, b.color("no_connect")
            b.obj("noerc", info=[["No Connect", ""]])
            b.line([(at[0] - s, at[1] - s), (at[0] + s, at[1] + s)], color, LINE)
            b.line([(at[0] - s, at[1] + s), (at[0] + s, at[1] - s)], color, LINE)
            b.done()
        elif kind in ("label", "global_label", "hierarchical_label"):
            label = _text(item)
            at_node = item.find("at")
            at = _xy(at_node)
            angle = round(_float(at_node, 2)) % 360
            size, hj, vj, _hidden = _effects(item)
            role = {
                "label": "label_local",
                "global_label": "label_global",
                "hierarchical_label": "label_hier",
            }[kind]
            index = b.obj(
                "label",
                info=[
                    [
                        "Net Label"
                        if kind == "label"
                        else "Global Label"
                        if kind == "global_label"
                        else "Hierarchical Label",
                        label,
                    ]
                ],
            )
            if kind == "label":
                rot = 1 if angle in (90, 270) else 0
                b.text(
                    at,
                    label,
                    size,
                    b.color(role),
                    rot=rot,
                    h=hj if hj != "center" else "left",
                    v=vj if vj != "center" else "bottom",
                    role="label",
                )
            else:
                shape = item.find("shape")
                _flag_shape(
                    b,
                    at,
                    angle,
                    label,
                    size,
                    _text(shape) if shape is not None else "passive",
                    b.color(role),
                    kind == "hierarchical_label",
                )
            b.done()
            key = ("label", kind if kind != "hierarchical_label" else "hier", label)
            union.find(key)
            named[key] = (0, label)
            points.append((at, key))
            ident_obj.append((index, key))
        elif kind == "sheet":
            _sheet(b, item, union, points, named, ident_obj)
        elif kind in ("polyline", "rectangle", "circle", "arc", "bezier", "text"):
            b.obj("graphic")
            _graphic(b, item, IDENT, "note", lib=False)
            b.done()
        elif kind in SKIPPED:
            skipped[kind] = skipped.get(kind, 0) + 1
    # connectivity: coincident points, and points on wires
    by_point: dict[Pt, list[Any]] = {}
    for point, key in points:
        by_point.setdefault(point, []).append(key)
    for keys in by_point.values():
        for other in keys[1:]:
            union.join(keys[0], other)
    wire_key = dict(pin_obj)
    for index, a, z in wires:
        owner = wire_key[index]
        for point in by_point:
            if point not in (a, z) and _on(point, a, z):
                union.join(owner, by_point[point][0])
    names: dict[Any, tuple[int, str]] = {}
    for key, (priority, label) in named.items():
        root_key = union.find(key)
        if root_key not in names or (priority, label) < names[root_key]:
            names[root_key] = (priority, label)
    net_of: dict[Any, int] = {}
    nets: list[dict[str, Any]] = []

    def net(key: Any) -> int:
        root_key = union.find(key)
        if root_key not in net_of:
            net_of[root_key] = len(nets)
            nets.append({"name": names.get(root_key, (9, ""))[1], "pins": []})
        return net_of[root_key]

    for key, pin_name in pins_of:
        index = net(key)
        nets[index]["pins"].append(pin_name)
    for net_entry in nets:
        if not net_entry["name"] and net_entry["pins"]:
            ref, _, number = net_entry["pins"][0].partition("-")
            net_entry["name"] = f"Net-({ref}-Pad{number})"
    for index, key in pin_obj + ident_obj:
        b.objects[index]["net"] = net(key)
    for obj in b.objects:
        if obj["net"] >= 0:
            obj["info"].append(["Net", nets[obj["net"]]["name"] or "(no name)"])
    for kind, count in sorted(skipped.items()):
        b.notes.append(f"{count} {kind.replace('_', ' ')} item(s) are not drawn.")
    b.notes.append(FENOLITE_DRAWINGS)
    b.notes.append(colour_note(palette))
    kinds = [obj["k"] for obj in b.objects]
    counts = {
        "components": sum(1 for comp in b.comps if not comp["ref"].startswith("#")),
        "symbols": len(b.comps),
        "pins": kinds.count("pin"),
        "wires": kinds.count("wire"),
        "buses": kinds.count("bus"),
        "bus_entries": kinds.count("entryline"),
        "labels": kinds.count("label"),
        "power_ports": sum(1 for comp in b.comps if comp.get("power")),
        "ports": 0,
        "junctions": kinds.count("junction"),
        "no_erc": kinds.count("noerc"),
        "sheet_symbols": kinds.count("sheet"),
        "sheet_entries": kinds.count("entry"),
        "harness_connectors": 0,
        "nets": sum(1 for n in nets if n["name"] and (n["pins"] or not n["name"].startswith("Net-"))),
        "prims": len(b.prims),
    }
    roles = b.roles
    return {
        "schema": SCHEMA,
        "kind": "schematic",
        "meta": {
            "name": name,
            "sha256": hashlib.sha256(data).hexdigest() if data else "",
            "bytes": len(data),
            "backend": "kicad",
            "evidence": evidence,
            "counts": counts,
            "notes": b.notes,
            "theme": palette["name"],
        },
        "bounds": list(b.box),
        "sheet": {
            "w": w,
            "h": h,
            "color": roles.get("background", "#f4f2ea"),
            "grid": 1_270,
            "grid_color": roles.get("grid"),
            "border": True,
            "margin": 10 * MM,
            "zones": [0, 0],
            "title_block": True,
            "style": paper,
            "text": "stroke",
            "workspace": roles.get("background"),
        },
        "fonts": [
            {"name": "stroke", "size": 0, "em": TEXT, "bold": False, "italic": False, "underline": False}
        ],
        "prims": b.prims,
        "objects": b.objects,
        "comps": b.comps,
        "nets": nets,
        "overlays": [],
    }


def _symbol(
    b: _Builder,
    item: Node,
    defs: dict[str, Node],
    union: _Union,
    points: list[tuple[Pt, Any]],
    named: dict[Any, tuple[int, str]],
    pin_obj: list[tuple[int, Any]],
    pins_of: list[tuple[Any, str]],
) -> None:
    lib_node = item.find("lib_id")
    lib_id = _text(lib_node) if lib_node is not None else ""
    lib_name_node = item.find("lib_name")
    definition = defs.get(_text(lib_name_node)) if lib_name_node is not None else None
    definition = definition or defs.get(lib_id)
    at_node = item.find("at")
    values = _nums(at_node)
    angle = round(_float(at_node, 2)) % 360
    mirror_node = item.find("mirror")
    mirror = _text(mirror_node) if mirror_node is not None else ""
    place = _Place(
        values[0] if values else 0,
        values[1] if len(values) > 1 else 0,
        angle - angle % 90,
        mirror if mirror in ("x", "y") else "",
    )
    unit_node, style_node = item.find("unit"), item.find("body_style") or item.find("convert")
    unit = int(_float(unit_node, 0, 1)) if unit_node is not None else 1
    style = int(_float(style_node, 0, 1)) if style_node is not None else 1
    props = _properties(item)
    ref = _text(props["Reference"], 1) if "Reference" in props else ""
    value = _text(props["Value"], 1) if "Value" in props else ""
    power = definition is not None and definition.find("power") is not None
    shown_ref = ref
    if definition is not None and _unit_count(definition) > 1 and ref and not ref.startswith("#"):
        shown_ref = ref + chr(ord("A") + max(unit, 1) - 1)
    comp = len(b.comps)
    entry: dict[str, Any] = {
        "ref": shown_ref,
        "group": ref,
        "comment": value,
        "lib": lib_id,
        "description": _text(props["Description"], 1) if "Description" in props else "",
        "footprint": _text(props["Footprint"], 1) if "Footprint" in props else "",
        "params": {
            k: _text(p, 1) for k, p in props.items() if k not in ("Reference", "Value") and _text(p, 1)
        },
        "b": None,
    }
    if power:
        entry["power"] = True
    b.comps.append(entry)
    info = [["Designator", shown_ref], ["Value", value], ["Library", lib_id]]
    if entry["footprint"]:
        info.append(["Footprint", entry["footprint"]])
    oid = b.obj("comp", comp=comp, info=info)
    pin_nodes: list[Node] = []
    names_shown, offset, numbers_shown = True, 508, True
    if definition is not None:
        pin_names = definition.find("pin_names")
        if pin_names is not None:
            names_shown = not _flag(pin_names, "hide")
            offset_nums = _nums(pin_names.find("offset"))
            offset = offset_nums[0] if offset_nums else 508
        pin_numbers = definition.find("pin_numbers")
        numbers_shown = pin_numbers is None or not _flag(pin_numbers, "hide")
        for sub in _units(definition, unit, style):
            for graphic in sub.nodes():
                if graphic.name == "pin":
                    pin_nodes.append(graphic)
                else:
                    b.current = oid
                    _graphic(b, graphic, place, "component_outline", lib=True)
    else:
        b.notes.append(f"{ref or lib_id}: no embedded symbol {lib_id!r}; only its fields are drawn.")
    entry["b"] = b.objects[oid]["b"]
    for key, role in (("Reference", "reference"), ("Value", "value")):
        if key in props:
            b.current = oid
            _field(b, props[key], shown_ref if key == "Reference" else value, role, place.angle)
    for key, prop in props.items():
        if key not in ("Reference", "Value"):
            b.current = oid
            _field(b, prop, _text(prop, 1), "fields", place.angle)
    for pin in pin_nodes:
        index = b.obj("pin", comp=comp)
        conn, number, pin_name, etype = _pin(b, pin, place, (names_shown, offset), numbers_shown)
        hidden = _flag(pin, "hide")
        b.objects[index]["info"] = [["Pin", f"{ref}-{number}"], ["Name", pin_name], ["Type", etype]]
        key = ("pin", comp, number, index)
        union.find(key)
        points.append((conn, key))
        if power:
            power_key = ("power", value)
            union.join(power_key, key)
            named[power_key] = (1, value)
        elif hidden and etype == "power_in" and pin_name:
            power_key = ("power", pin_name)
            union.join(power_key, key)
            named[power_key] = (1, pin_name)
        if not ref.startswith("#"):
            pins_of.append((key, f"{ref}-{number}"))
        if hidden:
            b.objects.pop()
            continue
        pin_obj.append((index, key))
        pin_box = b.objects[index]["b"]
        if pin_box:
            eb = entry["b"]
            entry["b"] = (
                list(pin_box)
                if eb is None
                else [
                    min(eb[0], pin_box[0]),
                    min(eb[1], pin_box[1]),
                    max(eb[2], pin_box[2]),
                    max(eb[3], pin_box[3]),
                ]
            )
    b.objects[oid]["b"] = entry["b"]
    b.done()


def _sheet(
    b: _Builder,
    item: Node,
    union: _Union,
    points: list[tuple[Pt, Any]],
    named: dict[Any, tuple[int, str]],
    ident_obj: list[tuple[int, Any]],
) -> None:
    at, size = _xy(item.find("at")), _xy(item.find("size"))
    props = _properties(item)
    sheet_name = _text(props["Sheetname"], 1) if "Sheetname" in props else ""
    sheet_file = _text(props["Sheetfile"], 1) if "Sheetfile" in props else ""
    b.obj("sheet", info=[["Sheet", sheet_name], ["File Name", sheet_file]], file=sheet_file, name=sheet_name)
    color, width, _ = _stroke(item, b.color("sheet"))
    fill_node = item.find("fill")
    fill = _rgb(fill_node.find("color")) if fill_node is not None else None
    corners = [at, (at[0] + size[0], at[1]), (at[0] + size[0], at[1] + size[1]), (at[0], at[1] + size[1])]
    b.polygon(corners, color, width, fill or b.color("sheet_background"))
    for key, role, prefix in (("Sheetname", "sheet_name", ""), ("Sheetfile", "sheet_filename", "File: ")):
        if key in props:
            _field(b, props[key], prefix + _text(props[key], 1), role, 0)
    sheet_obj = len(b.objects) - 1
    b.done()
    x0, y0, x1, y1 = at[0], at[1], at[0] + size[0], at[1] + size[1]
    for pin in item.nodes("pin"):
        label = _text(pin)
        shape = _text(pin, 1) if len(pin.atoms()) > 1 else "passive"
        point = _xy(pin.find("at"))
        text_size = _effects(pin)[0]
        index = b.obj("entry", info=[["Sheet Pin", label], ["Shape", shape]], parent=sheet_obj)
        inward = 0 if point[0] <= x0 else 180 if point[0] >= x1 else 270 if point[1] <= y0 else 90
        _flag_shape(b, point, inward, label, text_size, shape, b.color("sheet_label"), True)
        b.done()
        key = ("sheetpin", sheet_obj, label)
        points.append((point, key))
        named[key] = (0, label)
        ident_obj.append((index, key))
    del y1


__all__ = ["SCHEMA", "build_kicad_schematic_scene", "symbol_scene", "symbol_units"]


def symbol_units(node: Node, library: dict[str, Node]) -> int:
    """The number of units of a library symbol, its parent's for a derived symbol (``extends``)."""
    return _unit_count(_base(node, library))


def _base(node: Node, library: dict[str, Node]) -> Node:
    extends = node.find("extends")
    parent = library.get(_text(extends)) if extends is not None else None
    return parent if parent is not None else node


def symbol_scene(
    node: Node,
    library: dict[str, Node],
    *,
    unit: int = 1,
    style: int = 1,
    name: str,
    palette: dict[str, Any],
    evidence: str = "INFERRED",
    show_properties: bool = True,
) -> dict[str, Any]:
    """The scene of one unit of a library symbol (change c0179), at the origin, on a sheet the size of the
    symbol grown by 2.54 mm; ``sheet.origin`` is the symbol's origin. Catalog previews may hide
    property text while retaining it in component metadata; ordinary libraries draw it as stored."""
    b = _Builder(palette)
    big = 10**12
    b.box = [big, big, -big, -big]
    base = _base(node, library)
    props = _properties(node)
    ref = _text(props["Reference"], 1) if "Reference" in props else ""
    value = _text(props["Value"], 1) if "Value" in props else _text(node)
    b.comps.append(
        {
            "ref": ref,
            "group": ref,
            "comment": value,
            "lib": _text(node),
            "description": _text(props["Description"], 1) if "Description" in props else "",
            "footprint": _text(props["Footprint"], 1) if "Footprint" in props else "",
            "params": {k: _text(p, 1) for k, p in props.items() if _text(p, 1)},
            "b": None,
        }
    )
    oid = b.obj("comp", comp=0, info=[["Symbol", _text(node)], ["Unit", str(unit)]])
    names_shown, offset, numbers_shown = True, 508, True
    pin_names = base.find("pin_names") or node.find("pin_names")
    if pin_names is not None:
        names_shown = not _flag(pin_names, "hide")
        offsets = _nums(pin_names.find("offset"))
        offset = offsets[0] if offsets else 508
    pin_numbers = base.find("pin_numbers") or node.find("pin_numbers")
    numbers_shown = pin_numbers is None or not _flag(pin_numbers, "hide")
    pins: list[Node] = []
    for sub in _units(base, unit, style):
        for graphic in sub.nodes():
            if graphic.name == "pin":
                pins.append(graphic)
            else:
                b.current = oid
                _graphic(b, graphic, IDENT, "component_outline", lib=True)
    for key, prop in props.items():
        if not show_properties:
            continue
        size, h, v, hidden = _effects(prop)
        text = _text(prop, 1)
        values = _nums(prop.find("at"))
        if hidden or not text or text == "~" or len(values) < 2:
            continue
        role = {"Reference": "reference", "Value": "value"}.get(key, "fields")
        b.current = oid
        rot = round(_float(prop.find("at"), 2) / 90) % 2
        b.text((values[0], -values[1]), text, size, b.color(role), rot=rot, h=h, v=v, role=role)
    entry = b.comps[0]
    entry["b"] = b.objects[oid]["b"]
    for pin in pins:
        index = b.obj("pin", comp=0)
        _conn, number, pin_name, etype = _pin(b, pin, IDENT, (names_shown, offset), numbers_shown)
        if _flag(pin, "hide"):
            b.objects.pop()
            continue
        b.objects[index]["info"] = [["Pin", number], ["Name", pin_name], ["Type", etype]]
    b.done()
    if b.box[0] > b.box[2]:
        b.box = [-2_540, -2_540, 2_540, 2_540]
    pad = 2_540
    x0, y0, x1, y1 = b.box[0] - pad, b.box[1] - pad, b.box[2] + pad, b.box[3] + pad
    kinds = [obj["k"] for obj in b.objects]
    roles = b.roles
    b.notes.append(colour_note(palette))
    return {
        "schema": SCHEMA,
        "kind": "schematic",
        "meta": {
            "name": name,
            "sha256": "",
            "bytes": 0,
            "backend": "kicad",
            "evidence": evidence,
            "counts": {"components": 1, "pins": kinds.count("pin"), "prims": len(b.prims)},
            "notes": b.notes,
            "theme": palette["name"],
        },
        "bounds": [x0, y0, x1, y1],
        "sheet": {
            "w": x1 - x0,
            "h": y1 - y0,
            "x0": x0,
            "y0": y0,
            "origin": [0, 0],
            "color": roles.get("background", "#f4f2ea"),
            "grid": 1_270,
            "grid_color": roles.get("grid"),
            "border": False,
            "margin": 0,
            "zones": [1, 1],
            "title_block": False,
            "style": "Library",
            "text": "stroke",
            "workspace": roles.get("background"),
        },
        "fonts": [
            {"name": "stroke", "size": 0, "em": TEXT, "bold": False, "italic": False, "underline": False}
        ],
        "prims": b.prims,
        "objects": b.objects,
        "comps": b.comps,
        "nets": [],
        "overlays": [],
    }
