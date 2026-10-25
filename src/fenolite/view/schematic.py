# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of an Altium schematic sheet for the viewer page (capability schematic-viewer, change c0177).

``build_schematic_scene(document, ...)`` turns a ``SchDocument`` into plain JSON values:

* units are integer micrometres, from the sheet's top-left corner, with Y growing downwards;
* ``sheet``: its size, area colour, visible grid, border, zones and title block;
* ``fonts``: the font table of the sheet, by ``FONTID``;
* ``prims``: the drawn primitives in stream order, each an object with a kind ``k`` (``l`` polyline,
  ``g`` polygon, ``r`` rectangle, ``e`` ellipse, ``a`` arc, ``b`` Bezier, ``t`` text, ``x`` text frame,
  ``i`` image), its geometry, its colours and the index ``o`` of the object it belongs to;
* ``objects``: what a click selects (a part, a pin, a wire, a label …), with its net, its part, its box and
  the rows of the Properties panel;
* ``comps`` and ``nets``: the parts of the sheet and its local nets.

Colours and widths are the record's own. The shapes of power ports, ports, sheet entries, pin marks, the
built-in title block and the zones of a standard sheet are Fenolite's drawings of documented styles
(``docs/formats/altium/schematic-ascii.md``); the notes say so. Standard library only.
"""

from __future__ import annotations

import base64
import hashlib
import math
from collections.abc import Sequence
from typing import Any

from fenolite.backends.altium.adapter.connectivity import (
    Lines,
    entry_point,
    local_nets,
    port_ends,
    pt,
)
from fenolite.backends.altium.adapter.parts import PartGroup, part_groups
from fenolite.backends.altium.read.sch import (
    Arc,
    Bezier,
    Bus,
    BusEntry,
    Component,
    Designator,
    Ellipse,
    EllipticalArc,
    HarnessConnector,
    HarnessEntry,
    HarnessType,
    Hyperlink,
    IeeeSymbol,
    Image,
    Implementation,
    ImplementationList,
    ImplementationParameters,
    Junction,
    Label,
    Line,
    MapDefiner,
    MapDefinerList,
    NetLabel,
    NoErc,
    Parameter,
    PieChart,
    Pin,
    Polygon,
    Polyline,
    Port,
    PowerPort,
    Rectangle,
    RoundRectangle,
    SchDocument,
    SchLength,
    SchRecord,
    Sheet,
    SheetEntry,
    SheetFileName,
    SheetName,
    SheetSymbol,
    SignalHarness,
    Template,
    TextFrame,
    WarningSign,
    Wire,
)
from fenolite.backends.altium.read.sch.records import DIRECTIONS, Font, RecordRef, read_fonts
from fenolite.backends.altium.read.sch.units import Color
from fenolite.backends.altium.read.schlib import SchLibComponent, SchLibrary
from fenolite.backends.altium.read.sheet import LINE_WIDTHS, SHEET_STYLES

SCHEMA = "fenolite.view_schematic.v0"
UNIT = 254
"""One file unit of 10 mil in micrometres."""
SHEET_COLOR = "#fffcf8"
"""``AREACOLOR=16317695``, the sheet colour seen in files, for a sheet record without one."""
DEFAULT_FONT = {"name": "Times New Roman", "size": 10, "bold": False, "italic": False, "underline": False}
JUSTIFY: tuple[tuple[str, str], ...] = tuple(
    (v, h) for v in ("bottom", "center", "top") for h in ("left", "center", "right")
)
"""``JUSTIFICATION`` 0 to 8 as (vertical, horizontal)."""
MODEL_RECORDS = (ImplementationList, Implementation, MapDefinerList, MapDefiner, ImplementationParameters)
PORT_VERTICAL = frozenset({4, 5, 6, 7})
TITLE_W, TITLE_H = 350, 80
"""The built-in title block, in file units (Fenolite's drawing)."""
DEFAULT_MARGIN = 20
"""The border margin of a standard sheet, in file units (Fenolite's choice)."""
FENOLITE_DRAWINGS = (
    "Power ports, ports, sheet entries, pin marks and pin text offsets are Fenolite's drawings of the "
    "documented styles; they may differ from Altium Designer's by a few mil."
)

Pt = tuple[int, int]


def _union(box: list[int] | None, other: Sequence[int]) -> list[int]:
    if box is None:
        return list(other)
    return [min(box[0], other[0]), min(box[1], other[1]), max(box[2], other[2]), max(box[3], other[3])]


def _hex(color: Color) -> str:
    return f"#{color.red:02x}{color.green:02x}{color.blue:02x}"


def _um(value: int) -> int:
    """A ``SchLength.value`` (1/100 000 of 10 mil) in micrometres, rounded half up."""
    nm = SchLength(value).nm()
    return (nm + 500) // 1000


def _width(record: SchRecord, least: int = 0) -> int:
    """The record's ``LINEWIDTH`` in micrometres, at least ``least`` file units of 10 mil … in µm."""
    code = 0 if record.props is None else record.props.int("LINEWIDTH")
    return max(LINE_WIDTHS.get(code, LINE_WIDTHS[1]) // 1000, least)


def _int(record: SchRecord, key: str, default: int = 0) -> int:
    return default if record.props is None else record.props.int(key, default)


def _em(size: int) -> int:
    """The em of a font of ``size`` points, in micrometres: 9 mil per point (a Fenolite choice). A 10-point
    upper-case letter of Times New Roman is then about 63 mil wide, inside the 70 mil that the Altium writer
    reserves per character (``symbols.CHAR_WIDTH``), and pin texts at a 100-mil pitch keep a gap."""
    return size * 9 * 254 // 10


def _len(record: SchRecord, key: str) -> SchLength:
    return SchLength.of(_int(record, key), _int(record, f"{key}_FRAC"))


def _overline(text: str) -> tuple[str, list[int]]:
    """An Altium pin name without its overbar marks (``\\`` after an overlined character) and the indexes
    of the overlined characters."""
    out: list[str] = []
    marks: list[int] = []
    for ch in text:
        if ch == "\\" and out:
            marks.append(len(out) - 1)
        else:
            out.append(ch)
    return "".join(out), sorted(set(marks))


class _Builder:
    """The scene being built: the sheet frame, the font table, primitives, objects and bounds."""

    def __init__(self, document: SchDocument, name: str, fonts: tuple[Font, ...] | None = None) -> None:
        self.doc = document
        self.part: int | None = None
        """A part to draw instead of each component's current part (library symbols, change c0179)."""
        self.name = name
        self.notes: list[str] = []
        self.prims: list[dict[str, Any]] = []
        self.objects: list[dict[str, Any]] = []
        self.comps: list[dict[str, Any]] = []
        self.box = [0, 0, 0, 0]
        self.skipped_ieee = 0
        sheet = document.sheet
        self.sheet = sheet
        self.fonts, self.font_of = self._fonts(sheet.fonts if sheet else (fonts or ()))
        self.system_font = self.font_of.get(sheet.system_font if sheet else 1, 0)
        self.params = self._sheet_params()
        self.w, self.h, self.style = self._size(sheet)
        self.current = -1

    # --- frame -------------------------------------------------------------------------------------------

    def _fonts(self, table: tuple[Font, ...]) -> tuple[list[dict[str, Any]], dict[int, int]]:
        fonts: list[dict[str, Any]] = []
        index: dict[int, int] = {}
        for font in table:
            index[font.index] = len(fonts)
            size = font.size if font.size > 0 else 10
            fonts.append(
                {
                    "name": font.name or "Times New Roman",
                    "size": size,
                    "em": _em(size),
                    "bold": font.bold,
                    "italic": font.italic,
                    "underline": font.underline,
                }
            )
        if not fonts:
            fonts.append(DEFAULT_FONT | {"em": _em(10)})
            index[1] = 0
            self.notes.append("The sheet holds no font table; texts use Times New Roman 10.")
        return fonts, index

    def _size(self, sheet: Sheet | None) -> tuple[int, int, str]:
        if sheet is not None and sheet.custom_size is not None:
            cx, cy = sheet.custom_size
            return _um(cx.value), _um(cy.value), "Custom"
        style = sheet.sheet_style if sheet is not None else 0
        if not 0 <= style < len(SHEET_STYLES):
            self.notes.append(f"SHEETSTYLE {style} is not known; the sheet is drawn as A4.")
            style = 0
        w, h, paper = SHEET_STYLES[style]
        names = (
            "A4",
            "A3",
            "A2",
            "A1",
            "A0",
            "A",
            "B",
            "C",
            "D",
            "E",
            "Letter",
            "Legal",
            "Tabloid",
            "OrCAD A",
            "OrCAD B",
            "OrCAD C",
            "OrCAD D",
            "OrCAD E",
        )
        if sheet is not None and sheet.portrait:
            w, h = h, w
        return w * UNIT, h * UNIT, names[style] if paper == "custom" else paper

    def _sheet_params(self) -> dict[str, str]:
        found: dict[str, str] = {}
        for record in self.doc.of_type(Parameter):
            if record.owner is None and record.name:
                found.setdefault(record.name.casefold(), record.text)
        found.setdefault("documentname", self.name)
        return found

    def special(self, text: str, owner: dict[str, str] | None = None) -> str:
        """``=Name`` as the value of the parameter it names (the owner's, else the sheet's)."""
        if not text.startswith("="):
            return text
        key = text[1:].strip().casefold()
        table = owner if owner is not None else self.params
        return table.get(key, text)

    def xy(self, point: tuple[SchLength, SchLength]) -> Pt:
        return (_um(point[0].value), self.h - _um(point[1].value))

    def ixy(self, point: Pt) -> Pt:
        """A connectivity point (``SchLength.value`` integers) in the scene frame."""
        return (_um(point[0]), self.h - _um(point[1]))

    # --- primitives --------------------------------------------------------------------------------------

    def _grow(self, x0: int, y0: int, x1: int, y1: int) -> None:
        b = self.box
        b[0], b[1], b[2], b[3] = min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)

    def add(self, prim: dict[str, Any], bbox: Sequence[int]) -> None:
        prim["o"] = self.current
        self.prims.append(prim)
        self._grow(*bbox)
        if self.current < 0:
            return
        obj = self.objects[self.current]
        if prim["k"] == "t" and obj["k"] == "comp":
            return  # a part's box is its body and pins, without its texts
        obj["b"] = _union(obj["b"], bbox)

    def line(self, pts: Sequence[Pt], color: str, width: int, **extra: Any) -> None:
        if not pts:
            return
        flat = [v for p in pts for v in p]
        xs, ys = flat[0::2], flat[1::2]
        half = width // 2
        self.add(
            {"k": "l", "p": flat, "c": color, "w": width, **extra},
            (min(xs) - half, min(ys) - half, max(xs) + half, max(ys) + half),
        )

    def polygon(self, pts: Sequence[Pt], color: str, width: int, fill: str | None) -> None:
        if len(pts) < 2:
            return
        flat = [v for p in pts for v in p]
        xs, ys = flat[0::2], flat[1::2]
        self.add(
            {"k": "g", "p": flat, "c": color, "w": width, "f": fill}, (min(xs), min(ys), max(xs), max(ys))
        )

    def rect(self, a: Pt, b: Pt, color: str, width: int, fill: str | None, **extra: Any) -> None:
        box = [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]
        self.add({"k": "r", "b": box, "c": color, "w": width, "f": fill, **extra}, box)

    def ellipse(self, c: Pt, rx: int, ry: int, color: str, width: int, fill: str | None) -> None:
        self.add(
            {"k": "e", "x": c[0], "y": c[1], "rx": rx, "ry": ry, "c": color, "w": width, "f": fill},
            (c[0] - rx, c[1] - ry, c[0] + rx, c[1] + ry),
        )

    def text(
        self,
        at: Pt,
        string: str,
        font: int,
        color: str,
        *,
        rot: int = 0,
        h: str = "left",
        v: str = "bottom",
        ol: list[int] | None = None,
        role: str = "",
    ) -> None:
        if not string:
            return
        em = self.fonts[font]["em"] if 0 <= font < len(self.fonts) else self.fonts[0]["em"]
        width = max(1, int(0.55 * em * max((len(s) for s in string.split("\n")), default=1)))
        height = em * max(1, string.count("\n") + 1)
        x0 = {"left": 0, "center": -width // 2, "right": -width}[h]
        y0 = {"bottom": -height, "center": -height // 2, "top": 0}[v]
        corners = [(x0, y0), (x0 + width, y0), (x0, y0 + height), (x0 + width, y0 + height)]
        c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][rot % 4]  # cos and sin of the quarter turns, Y downwards
        pts = [(at[0] + dx * c + dy * s, at[1] - dx * s + dy * c) for dx, dy in corners]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        prim: dict[str, Any] = {
            "k": "t",
            "x": at[0],
            "y": at[1],
            "s": string,
            "font": font,
            "c": color,
            "rot": rot % 4,
            "h": h,
            "v": v,
        }
        if ol:
            prim["ol"] = ol
        if role:
            prim["role"] = role
        self.add(prim, (min(xs), min(ys), max(xs), max(ys)))

    def font(self, font_id: int) -> int:
        return self.font_of.get(font_id, self.system_font)

    def obj(
        self,
        kind: str,
        record: SchRecord | None,
        *,
        comp: int = -1,
        info: list[list[str]] | None = None,
        **extra: Any,
    ) -> int:
        self.objects.append(
            {
                "k": kind,
                "net": -1,
                "comp": comp,
                "b": None,
                "info": info or [],
                "rec": None if record is None else [record.ref.stream, record.ref.index],
                **extra,
            }
        )
        self.current = len(self.objects) - 1
        return self.current

    def done(self) -> None:
        self.current = -1


# --- drawing of records ---------------------------------------------------------------------------------


def _text_record(
    b: _Builder, record: SchRecord, string: str, color: str | None = None, role: str = ""
) -> None:
    """A text record at its location, by its font, orientation and justification."""
    font = b.font(_int(record, "FONTID"))
    v, h = JUSTIFY[_int(record, "JUSTIFICATION") % 9]
    loc = b.xy((_len(record, "LOCATION.X"), _len(record, "LOCATION.Y")))
    rgb = color or _hex(Color.of(_int(record, "COLOR")))
    b.text(loc, string, font, rgb, rot=_int(record, "ORIENTATION") % 4, h=h, v=v, role=role)


def _dash(record: SchRecord) -> int:
    return _int(record, "LINESTYLE") % 4


def _graphic(b: _Builder, record: SchRecord) -> bool:
    """Draw one graphic record; ``False`` when ``record`` is not a graphic."""
    if isinstance(record, IeeeSymbol):
        b.skipped_ieee += 1
        return True
    if isinstance(record, Line):
        b.line(
            [b.xy(record.location), b.xy(record.corner)], _hex(record.color), _width(record), d=_dash(record)
        )
    elif isinstance(record, Polyline):
        extra: dict[str, Any] = {"d": record.line_style % 4}
        if record.start_line_shape or record.end_line_shape:
            extra |= {
                "s0": record.start_line_shape,
                "s1": record.end_line_shape,
                "ss": record.line_shape_size,
            }
        b.line([b.xy(p) for p in record.points], _hex(record.color), _width(record), **extra)
    elif isinstance(record, Bezier):
        pts = [v for p in record.points for v in b.xy(p)]
        if len(pts) >= 4:
            xs, ys = pts[0::2], pts[1::2]
            b.add(
                {"k": "b", "p": pts, "c": _hex(record.color), "w": _width(record)},
                (min(xs), min(ys), max(xs), max(ys)),
            )
    elif isinstance(record, Polygon):
        fill = _hex(record.area_color) if record.solid else None
        b.polygon([b.xy(p) for p in record.points], _hex(record.color), _width(record), fill)
    elif isinstance(record, RoundRectangle):
        fill = _hex(record.area_color) if record.solid else None
        rr = [_um(record.corner_x_radius.value), _um(record.corner_y_radius.value)]
        b.rect(b.xy(record.location), b.xy(record.corner), _hex(record.color), _width(record), fill, rr=rr)
    elif isinstance(record, Rectangle):
        fill = _hex(record.area_color) if record.solid else None
        extra = {"ta": True} if record.transparent and fill else {}
        b.rect(b.xy(record.location), b.xy(record.corner), _hex(record.color), _width(record), fill, **extra)
    elif isinstance(record, Ellipse):
        fill = _hex(record.area_color) if record.solid else None
        rx, ry = _um(record.radius.value), _um(record.secondary_radius.value)
        b.ellipse(b.xy(record.location), rx, ry or rx, _hex(record.color), _width(record), fill)
    elif isinstance(record, Arc | EllipticalArc | PieChart):
        c = b.xy(record.location)
        rx = _um(record.radius.value)
        ry = _um(record.secondary_radius.value) if isinstance(record, EllipticalArc) else rx
        ry = ry or rx
        prim: dict[str, Any] = {
            "k": "a",
            "x": c[0],
            "y": c[1],
            "rx": rx,
            "ry": ry,
            "a0": record.start_angle / 1e6,
            "a1": record.end_angle / 1e6,
            "c": _hex(record.color),
            "w": _width(record),
            "f": None,
        }
        if isinstance(record, PieChart):
            prim["pie"] = True
            prim["f"] = _hex(record.area_color) if record.solid else None
        b.add(prim, (c[0] - rx, c[1] - ry, c[0] + rx, c[1] + ry))
    elif isinstance(record, TextFrame):
        a, z = b.xy(record.location), b.xy(record.corner)
        box = [min(a[0], z[0]), min(a[1], z[1]), max(a[0], z[0]), max(a[1], z[1])]
        b.add(
            {
                "k": "x",
                "b": box,
                "s": b.special(record.text).replace("~1", "\n"),
                "font": b.font(record.font_id),
                "tc": _hex(record.color),
                "f": _hex(record.area_color) if record.solid else None,
                "bc": _hex(Color.of(_int(record, "LINECOLOR"))) if record.show_border else None,
                "wrap": record.word_wrap,
                "al": record.alignment,
                "m": _um(record.text_margin.value),
            },
            box,
        )
    elif isinstance(record, Image):
        a, z = b.xy(record.location), b.xy(record.corner)
        box = [min(a[0], z[0]), min(a[1], z[1]), max(a[0], z[0]), max(a[1], z[1])]
        b.add({"k": "i", "b": box, "src": _image_src(b.doc, record), "name": record.file_name}, box)
    elif isinstance(record, Hyperlink):
        _text_record(b, record, record.text or record.url)
    elif isinstance(record, Label):
        _text_record(b, record, b.special(record.text), role="note")
    else:
        return False
    return True


def _image_src(document: SchDocument, image: Image) -> str | None:
    embedded = document.image_data(image) if image.embedded else None
    if embedded is None:
        return None
    try:
        data = embedded.data()
    except Exception:  # an image that does not expand is drawn as its frame
        return None
    kinds = (
        (b"\x89PNG", "image/png"),
        (b"\xff\xd8", "image/jpeg"),
        (b"BM", "image/bmp"),
        (b"GIF8", "image/gif"),
    )
    mime = next((m for magic, m in kinds if data.startswith(magic)), None)
    if mime is None:
        return None
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


# --- components and pins -------------------------------------------------------------------------------


def _component_params(document: SchDocument, component: Component) -> dict[str, str]:
    found: dict[str, str] = {}
    for record in document.children_of(component):
        if isinstance(record, Parameter) and record.name:
            found.setdefault(record.name.casefold(), record.text)
    return found


def _footprint(document: SchDocument, component: Component) -> str:
    for record in document.walk(component):
        if isinstance(record, Implementation) and record.is_current and record.model_type.upper() == "PCBLIB":
            return record.model_name
    return ""


def _pin(b: _Builder, pin: Pin, comp: int, ref: str) -> None:
    color = _hex(pin.color)
    bx, by = b.xy(pin.location)
    hx, hy = b.xy(pin.hot_end)
    fx, fy = DIRECTIONS[pin.direction]
    dx, dy = fx, -fy  # outwards from the body, in the scene frame
    width = _width(pin, LINE_WIDTHS[1] // 1000)
    name, marks = _overline(pin.name)
    b.obj(
        "pin",
        pin,
        comp=comp,
        info=[
            ["Pin", f"{ref}-{pin.designator}" if ref else pin.designator],
            ["Name", name],
            ["Type", PIN_TYPES.get(pin.electrical, str(pin.electrical))],
        ],
    )
    start = (bx, by)
    px, py = (0, -1) if dx else (-1, 0)  # "above" the pin line
    unit = UNIT
    if pin.outer_edge == 1:  # inversion dot
        r = round(1.5 * unit)
        b.ellipse((bx + dx * r, by + dy * r), r, r, color, width, None)
        start = (bx + dx * 2 * r, by + dy * 2 * r)
    b.line([start, (hx, hy)], color, width)
    if pin.inner_edge == 3:  # clock wedge inside the body
        w, d = round(2.5 * unit), round(4 * unit)
        b.line(
            [(bx + px * w, by + py * w), (bx - dx * d, by - dy * d), (bx - px * w, by - py * w)], color, width
        )
    if pin.outer_edge == 4:  # active-low input
        b.line(
            [(bx, by), (bx + px * 2 * unit, by + py * 2 * unit), (bx + dx * 4 * unit, by + dy * 4 * unit)],
            color,
            width,
        )
    elif pin.outer_edge == 17:  # active-low output
        b.line(
            [(bx + px * 2 * unit, by + py * 2 * unit), (bx + dx * 4 * unit, by + dy * 4 * unit)], color, width
        )
    font = b.system_font
    rot = 0 if dx else 1
    along = dx if dx else -dy  # the pin's direction measured along the text's reading direction
    if pin.name_shown and name:
        at = (bx - dx * 5 * unit, by - dy * 5 * unit)
        b.text(
            at,
            name,
            font,
            color,
            rot=rot,
            h="right" if along > 0 else "left",
            v="center",
            ol=marks,
            role="pin-name",
        )
    if pin.designator_shown and pin.designator:
        at = (bx + dx * 3 * unit + px * unit, by + dy * 3 * unit + py * unit)
        b.text(
            at,
            pin.designator,
            font,
            color,
            rot=rot,
            h="left" if along > 0 else "right",
            v="bottom",
            role="pin-number",
        )


PIN_TYPES = {
    0: "Input",
    1: "I/O",
    2: "Output",
    3: "Open Collector",
    4: "Passive",
    5: "HiZ",
    6: "Open Emitter",
    7: "Power",
}


def _component(b: _Builder, component: Component, group_ref: str) -> int:
    doc = b.doc
    params = _component_params(doc, component)
    children = (
        doc.children_of(component, part=b.part, mode=component.display_mode)
        if b.part
        else doc.shown_children(component)
    )
    designator = next((r for r in doc.children_of(component) if isinstance(r, Designator)), None)
    ref = designator.text if designator is not None else ""
    shown_ref = ref
    if component.part_count > 1 and ref:
        shown_ref = ref + chr(ord("A") + max(b.part or component.current_part, 1) - 1)
    comment = b.special(params.get("comment", ""), params)
    comp = len(b.comps)
    entry: dict[str, Any] = {
        "ref": shown_ref,
        "group": group_ref or ref,
        "comment": comment,
        "lib": component.lib_reference,
        "description": component.description,
        "footprint": _footprint(doc, component),
        "params": {
            r.name: b.special(r.text, params)
            for r in doc.children_of(component)
            if isinstance(r, Parameter) and r.name and r.name.casefold() != "comment"
        },
        "b": None,
    }
    b.comps.append(entry)
    info = [
        ["Designator", shown_ref],
        ["Comment", comment],
        ["Design Item ID", component.design_item_id or component.lib_reference],
    ]
    if component.description:
        info.append(["Description", component.description])
    if entry["footprint"]:
        info.append(["Footprint", entry["footprint"]])
    if component.source_library:
        info.append(["Library", component.source_library])
    oid = b.obj("comp", component, comp=comp, info=info)
    pins: list[Pin] = []
    for child in children:
        if isinstance(child, MODEL_RECORDS) or isinstance(child, Designator | Parameter):
            continue
        if isinstance(child, Pin):
            pins.append(child)
            continue
        b.current = oid
        _graphic(b, child)
    b.current = oid
    texts: list[tuple[SchRecord, str]] = []
    if designator is not None and not designator.hidden:
        texts.append((designator, shown_ref))
    for child in doc.children_of(component):
        if isinstance(child, Parameter) and not child.hidden and child.name.casefold() != "designator":
            value = b.special(child.text, params)
            texts.append((child, f"{child.name}: {value}" if child.show_name else value))
    body_box = b.objects[oid]["b"]
    entry["b"] = list(body_box) if body_box else None
    for record, string in texts:
        b.current = oid
        _text_record(b, record, string, role="designator" if isinstance(record, Designator) else "parameter")
    for pin in pins:
        if not pin.hidden:
            _pin(b, pin, comp, group_ref or ref)
            pin_box = b.objects[-1]["b"]
            if pin_box:
                entry["b"] = _union(entry["b"], pin_box)
    b.objects[oid]["b"] = entry["b"]
    b.done()
    return comp


# --- connectivity symbols ------------------------------------------------------------------------------

POWER_DIRS: tuple[Pt, ...] = ((1, 0), (0, -1), (-1, 0), (0, 1))
"""``ORIENTATION`` 0 to 3 of a power port as a scene direction: right, up, left, down."""


def _power(b: _Builder, port: PowerPort) -> None:
    color = _hex(port.color)
    lx, ly = b.xy(port.location)
    ux, uy = POWER_DIRS[port.orientation % 4]
    vx, vy = -uy, ux
    style = {7: 1, 8: 4, 9: 6, 10: 2}.get(port.style, port.style)
    w = LINE_WIDTHS[1] // 1000

    def p(a: float, c: float) -> Pt:
        return (round(lx + (ux * a + vx * c) * UNIT), round(ly + (uy * a + vy * c) * UNIT))

    kind = "offsheet" if port.cross_sheet else "power"
    b.obj(
        "power",
        port,
        info=[
            ["Net", port.text],
            ["Kind", "Off-sheet connector" if port.cross_sheet else "Power port"],
            ["Style", POWER_STYLES.get(port.style, str(port.style))],
        ],
        power=kind,
    )
    end = 6.0
    if port.cross_sheet:
        b.line([p(0, 0), p(2, 0)], color, w)
        b.line([p(2, -2), p(5, 0), p(2, 2)], color, w)
        b.line([p(5, -2), p(8, 0), p(5, 2)], color, w)
        end = 8.0
    elif style == 0:
        b.line([p(0, 0), p(4, 0)], color, w)
        b.ellipse(p(6, 0), 2 * UNIT, 2 * UNIT, color, w, None)
        end = 8.0
    elif style == 1:
        b.line([p(0, 0), p(4, 0)], color, w)
        b.polygon([p(4, -3), p(8, 0), p(4, 3)], color, w, color)
        end = 8.0
    elif style == 3:
        b.line([p(0, 0), p(4, 0)], color, w)
        b.line([p(4 + math.sin(math.pi * c / 2) * 1.2, c) for c in [k / 2 for k in range(-8, 9)]], color, w)
        end = 5.5
    elif style == 4:
        b.line([p(0, 0), p(4, 0)], color, w)
        for a, c in ((4, 5), (6, 3), (8, 1)):
            b.line([p(a, -c), p(a, c)], color, w)
        end = 8.0
    elif style == 5:
        b.line([p(0, 0), p(4, 0)], color, w)
        b.polygon([p(4, -5), p(9, 0), p(4, 5)], color, w, None)
        end = 9.0
    elif style == 6:
        b.line([p(0, 0), p(4, 0)], color, w)
        b.line([p(4, -5), p(4, 5)], color, w)
        for c in (-5, 0, 5):
            b.line([p(4, c), p(7, c - 2.5)], color, w)
        end = 7.0
    else:  # 2, a bar, and any unknown style
        b.line([p(0, 0), p(5, 0)], color, w)
        b.line([p(5, -5), p(5, 5)], color, w)
        end = 5.0
    if port.show_net_name and port.text:
        at = p(end + 1.5, 0)
        h, v = {
            (1, 0): ("left", "center"),
            (-1, 0): ("right", "center"),
            (0, -1): ("center", "bottom"),
            (0, 1): ("center", "top"),
        }[(ux, uy)]
        b.text(at, port.text, b.font(port.font_id), color, h=h, v=v, role="power")
    b.done()


POWER_STYLES = {
    0: "Circle",
    1: "Arrow",
    2: "Bar",
    3: "Wave",
    4: "Power Ground",
    5: "Signal Ground",
    6: "Earth",
    7: "GOST Arrow",
    8: "GOST Power Ground",
    9: "GOST Earth",
    10: "GOST Bar",
}
IO_TYPES = {0: "Unspecified", 1: "Output", 2: "Input", 3: "Bidirectional"}


def _port(b: _Builder, port: Port) -> None:
    x, y = b.xy(port.location)
    length = _um(port.width.value)
    half = _um(port.height.value or SchLength.of(10).value) // 2
    vertical = port.style in PORT_VERTICAL
    style = port.style - 4 if vertical else port.style
    tip = min(half, length // 2)
    b.obj(
        "port", port, info=[["Port", port.name], ["I/O Type", IO_TYPES.get(port.io_type, str(port.io_type))]]
    )
    if vertical:  # top (5) points the far end, bottom (6) the near end, as styles 2 and 1 do
        style = {1: 2, 2: 1}.get(style, style)
    near, far = length, length - tip
    shape = {
        1: [(0, 0), (tip, -half), (near, -half), (near, half), (tip, half)],
        2: [(0, -half), (far, -half), (length, 0), (far, half), (0, half)],
        3: [(0, 0), (tip, -half), (far, -half), (length, 0), (far, half), (tip, half)],
    }.get(style, [(0, -half), (length, -half), (length, half), (0, half)])
    # along `a` from the location (rightwards, or upwards for a vertical port), across `c`
    pts = [(x + c, y - a) if vertical else (x + a, y + c) for a, c in shape]
    b.polygon(pts, _hex(port.color), LINE_WIDTHS[1] // 1000, _hex(port.area_color))
    centre = (x, y - length // 2) if vertical else (x + length // 2, y)
    align = {1: "left", 2: "right"}.get(port.alignment, "center")
    at = centre
    if align != "center":
        inset = tip + UNIT if align == "left" else length - tip - UNIT
        at = (x, y - inset) if vertical else (x + inset, y)
    b.text(
        at,
        port.name,
        b.font(port.font_id),
        _hex(port.text_color),
        rot=1 if vertical else 0,
        h=align,
        v="center",
        role="port",
    )
    b.done()


def _sheet_symbol(b: _Builder, symbol: SheetSymbol) -> None:
    doc = b.doc
    x, y = b.xy(symbol.location)
    w, h = _um(symbol.x_size.value), _um(symbol.y_size.value)
    name = next((r.text for r in doc.children_of(symbol) if isinstance(r, SheetName)), "")
    file = next((r.text for r in doc.children_of(symbol) if isinstance(r, SheetFileName)), "")
    b.obj("sheet", symbol, info=[["Sheet Symbol", name], ["File Name", file]], file=file, name=name)
    fill = _hex(symbol.area_color) if symbol.solid else None
    b.rect((x, y), (x + w, y + h), _hex(symbol.color), _width(symbol, LINE_WIDTHS[1] // 1000), fill)
    for child in doc.children_of(symbol):
        if isinstance(child, SheetName | SheetFileName) and not child.hidden:
            b.current = len(b.objects) - 1
            _text_record(
                b, child, child.text, role="sheet-name" if isinstance(child, SheetName) else "sheet-file"
            )
    sheet_obj = len(b.objects) - 1
    b.done()
    for child in doc.children_of(symbol):
        if isinstance(child, SheetEntry):
            _entry(b, child, symbol, sheet_obj)


def _entry(
    b: _Builder, entry: SheetEntry | HarnessEntry, owner: SheetSymbol | HarnessConnector, parent: int
) -> None:
    point = entry_point(b.doc, entry)
    if point is None:
        return
    ex, ey = b.ixy(point)
    side = entry.side % 4
    ix, iy = ((1, 0), (-1, 0), (0, 1), (0, -1))[side]  # inwards, in the scene frame
    color, fill, text_color = _hex(entry.color), _hex(entry.area_color), _hex(entry.text_color)
    io = entry.io_type if isinstance(entry, SheetEntry) else 0
    harness = isinstance(entry, HarnessEntry)
    b.obj(
        "entry", entry, info=[["Entry", entry.name], ["I/O Type", IO_TYPES.get(io, str(io))]], parent=parent
    )
    length, half = 12 * UNIT, 3 * UNIT
    jx, jy = -iy, ix

    def q(a: int, c: int) -> Pt:
        return (ex + ix * a + jx * c, ey + iy * a + jy * c)

    if not harness:
        out_tip = io in (1, 3)
        in_tip = io in (2, 3)
        shape = [q(half if out_tip else 0, -half), q(length - half if in_tip else length, -half)]
        if in_tip:
            shape.append(q(length, 0))
        shape += [q(length - half if in_tip else length, half), q(half if out_tip else 0, half)]
        if out_tip:
            shape.append(q(0, 0))
        b.polygon(shape, color, LINE_WIDTHS[1] // 1000, fill)
        offset = length + 3 * UNIT
    else:
        b.line([q(0, 0), q(4 * UNIT, 0)], color, LINE_WIDTHS[1] // 1000)
        offset = 5 * UNIT
    at = q(offset, 0)
    font = b.font(entry.text_font_id)
    if side in (0, 1):
        b.text(at, entry.name, font, text_color, h="left" if side == 0 else "right", v="center", role="entry")
    else:
        b.text(
            at,
            entry.name,
            font,
            text_color,
            rot=1,
            h="right" if side == 2 else "left",
            v="center",
            role="entry",
        )
    b.done()


def _harness_connector(b: _Builder, connector: HarnessConnector) -> None:
    x, y = b.xy(connector.location)
    w, h = _um(connector.x_size.value), _um(connector.y_size.value)
    b.obj("harness", connector, info=[["Harness Connector", ""]])
    b.rect(
        (x, y),
        (x + w, y + h),
        _hex(connector.color),
        _width(connector, LINE_WIDTHS[1] // 1000),
        _hex(connector.area_color),
    )
    parent = len(b.objects) - 1
    for child in b.doc.children_of(connector):
        if isinstance(child, HarnessType) and not child.hidden:
            b.current = parent
            _text_record(b, child, child.text, role="harness-type")
    b.done()
    for child in b.doc.children_of(connector):
        if isinstance(child, HarnessEntry):
            _entry(b, child, connector, parent)


def _directive(b: _Builder, sign: WarningSign) -> None:
    color = _hex(sign.color)
    x, y = b.xy(sign.location)
    b.obj("directive", sign, info=[["Directive", sign.name]])
    b.line([(x, y), (x, y - 6 * UNIT)], color, LINE_WIDTHS[1] // 1000)
    b.polygon(
        [(x, y - 6 * UNIT), (x + 5 * UNIT, y - 5 * UNIT), (x, y - 4 * UNIT)],
        color,
        LINE_WIDTHS[1] // 1000,
        color,
    )
    for child in b.doc.children_of(sign):
        if isinstance(child, Parameter) and not child.hidden:
            value = b.special(child.text)
            b.current = len(b.objects) - 1
            _text_record(b, child, f"{child.name}: {value}" if child.show_name else value, role="parameter")
    b.done()


# --- sheet frame ---------------------------------------------------------------------------------------


def _frame(b: _Builder) -> dict[str, Any]:
    sheet = b.sheet
    props = sheet.props if sheet is not None else None
    color = SHEET_COLOR
    if props is not None and props.has("AREACOLOR"):
        color = _hex(sheet.area_color) if sheet else SHEET_COLOR
    elif sheet is not None:
        b.notes.append(
            "The sheet record holds no area colour; the sheet is drawn off-white, as saved sheets are."
        )
    grid = 0
    if sheet is not None and sheet.visible_grid_on:
        grid = max(sheet.visible_grid_size, 1) * UNIT
    border = bool(sheet is not None and sheet.border)
    custom = sheet is not None and sheet.custom_size is not None
    margin = DEFAULT_MARGIN * UNIT
    zones = [round(b.w / (287.5 * UNIT)), round(b.h / (190 * UNIT))]
    if custom and props is not None:
        margin = (
            _um(SchLength.of(props.int("CUSTOMMARGINWIDTH"), props.int("CUSTOMMARGINWIDTH_FRAC")).value)
            or margin
        )
        zones = [props.int("CUSTOMXZONES") or zones[0], props.int("CUSTOMYZONES") or zones[1]]
    zones = [max(1, min(zones[0], 64)), max(1, min(zones[1], 26))]
    title = bool(sheet is not None and sheet.title_block)
    frame = {
        "w": b.w,
        "h": b.h,
        "color": color,
        "grid": grid,
        "border": border,
        "margin": margin if border else 0,
        "zones": zones,
        "title_block": title,
        "style": b.style,
    }
    if border:
        _border(b, margin, zones)
    if title:
        _title_block(b, margin if border else 0)
    return frame


def _border(b: _Builder, margin: int, zones: list[int]) -> None:
    color, w = "#000000", LINE_WIDTHS[1] // 1000
    W, H = b.w, b.h
    b.rect((0, 0), (W, H), color, w, None)
    b.rect((margin, margin), (W - margin, H - margin), color, w, None)
    nx, ny = zones
    font = b.system_font
    for i in range(1, nx):
        x = W * i // nx
        b.line([(x, 0), (x, margin)], color, w)
        b.line([(x, H - margin), (x, H)], color, w)
    for j in range(1, ny):
        y = H * j // ny
        b.line([(0, y), (margin, y)], color, w)
        b.line([(W - margin, y), (W, y)], color, w)
    for i in range(nx):
        x = W * (2 * i + 1) // (2 * nx)
        for y in (margin // 2, H - margin // 2):
            b.text((x, y), str(i + 1), font, color, h="center", v="center", role="zone")
    for j in range(ny):
        y = H * (2 * j + 1) // (2 * ny)
        for x in (margin // 2, W - margin // 2):
            b.text((x, y), chr(ord("A") + j), font, color, h="center", v="center", role="zone")


def _title_block(b: _Builder, inset: int) -> None:
    color, w = "#000000", LINE_WIDTHS[1] // 1000
    x1, y1 = b.w - inset, b.h - inset
    x0, y0 = x1 - TITLE_W * UNIT, y1 - TITLE_H * UNIT
    u = UNIT
    b.rect((x0, y0), (x1, y1), color, w, None)
    rows = [y0 + 30 * u, y0 + 50 * u, y0 + 60 * u, y0 + 70 * u]
    for y in rows:
        b.line([(x0, y), (x1, y)], color, w)
    b.line([(x0 + 50 * u, y0 + 30 * u), (x0 + 50 * u, y0 + 50 * u)], color, w)
    b.line([(x0 + 250 * u, y0 + 30 * u), (x0 + 250 * u, y0 + 50 * u)], color, w)
    b.line([(x0 + 200 * u, y0 + 50 * u), (x0 + 200 * u, y1)], color, w)
    p = b.params
    font = b.system_font
    small = font

    def put(x: int, y: int, label: str, value: str) -> None:
        b.text((x0 + x * u, y0 + y * u), label, small, color, v="top", role="title-label")
        if value:
            b.text((x0 + x * u + 5 * u, y0 + y * u + 11 * u), value, font, color, v="top", role="title-value")

    put(3, 2, "Title", p.get("title", ""))
    put(3, 32, "Size", b.style)
    put(53, 32, "Number", p.get("documentnumber", ""))
    put(253, 32, "Revision", p.get("revision", ""))
    b.text((x0 + 3 * u, y0 + 57 * u), "Date:", small, color, v="bottom", role="title-label")
    b.text((x0 + 40 * u, y0 + 57 * u), p.get("date", ""), font, color, v="bottom", role="title-value")
    b.text((x0 + 3 * u, y0 + 67 * u), "File:", small, color, v="bottom", role="title-label")
    b.text((x0 + 40 * u, y0 + 67 * u), b.name, font, color, v="bottom", role="title-value")
    sheet_of = f"{p.get('sheetnumber', '')} of {p.get('sheettotal', '')}".strip()
    b.text(
        (x0 + 203 * u, y0 + 57 * u),
        f"Sheet {sheet_of}" if sheet_of != "of" else "Sheet",
        small,
        color,
        v="bottom",
        role="title-label",
    )
    b.text(
        (x0 + 203 * u, y0 + 67 * u),
        f"Drawn By: {p.get('drawnby', '')}",
        small,
        color,
        v="bottom",
        role="title-label",
    )


# --- nets ----------------------------------------------------------------------------------------------


def _nets(
    b: _Builder, groups: Sequence[PartGroup], wires: list[Wire]
) -> tuple[list[dict[str, Any]], dict[tuple[int, str], int], dict[tuple[str, int], int], list[int], Lines]:
    """The local nets; the net of each pin key, of each identifier record and of each wire."""
    doc = b.doc
    lines = Lines([[pt(p) for p in wire.points] for wire in wires])
    wire_groups = lines.groups([pt(j.location) for j in doc.junctions()])
    nets: list[dict[str, Any]] = []
    pin_net: dict[tuple[int, str], int] = {}
    ident_net: dict[tuple[str, int], int] = {}
    group_net: dict[int, int] = {}
    order = {"label": 0, "power": 1, "offsheet": 2, "port": 3, "entry": 4, "harness": 5}
    for index, net in enumerate(local_nets(doc, groups)):
        points: list[tuple[int, int]] = []
        for pin in net.pins:
            pin_net[(pin.group, pin.designator)] = index
            points += [pt(p.hot_end) for p in groups[pin.group].shown if p.designator == pin.designator]
        for ident in net.idents:
            ident_net[(ident.stream, ident.index)] = index
            record = doc.get(RecordRef(ident.stream, ident.index))
            if isinstance(record, Port):
                points += list(port_ends(record))
            elif isinstance(record, SheetEntry | HarnessEntry):
                found = entry_point(doc, record)
                points += [found] if found else []
            elif isinstance(record, NetLabel | PowerPort):
                points.append(pt(record.location))
        for point in points:
            for line in lines.at(point):
                group_net.setdefault(wire_groups[line], index)
        named = sorted(net.idents, key=lambda i: order.get(i.kind, 9))
        if named and named[0].text:
            name = named[0].text
        elif net.pins:
            first = net.pins[0]
            name = f"Net{groups[first.group].ref}_{first.designator}"
        else:
            name = ""
        nets.append({"name": name, "pins": [f"{groups[p.group].ref}-{p.designator}" for p in net.pins]})
    wire_net: list[int] = []
    for group in wire_groups:
        if group not in group_net:
            group_net[group] = len(nets)
            nets.append({"name": "", "pins": []})
        wire_net.append(group_net[group])
    return nets, pin_net, ident_net, wire_net, lines


# --- the scene -----------------------------------------------------------------------------------------


def build_schematic_scene(
    document: SchDocument, *, name: str, data: bytes = b"", evidence: str = "INFERRED"
) -> dict[str, Any]:
    """The scene of one Altium schematic sheet (see the module text)."""
    b = _Builder(document, name)
    frame = _frame(b)
    groups = part_groups(document)
    group_of: dict[tuple[str, int], int] = {}
    for number, group in enumerate(groups):
        for part in group.parts:
            group_of[(part.ref.stream, part.ref.index)] = number
    wires = [wire for wire in document.wires() if wire.points]
    nets, pin_net, ident_net, wire_net, _lines = _nets(b, groups, wires)
    wire_index = {(w.ref.stream, w.ref.index): k for k, w in enumerate(wires)}
    template_refs = {ref for template in document.templates() for ref in template.children}
    # the template under everything else
    for record in document.all_records():
        if record.ref in template_refs:
            _graphic(b, record)
    comp_group: list[int] = []
    for record in document.all_records():
        if record.owner is not None or record.ref in template_refs:
            continue
        key = (record.ref.stream, record.ref.index)
        if isinstance(record, Component):
            group = group_of.get(key, -1)
            ref = groups[group].ref if group >= 0 else ""
            first_obj = len(b.objects)
            comp = _component(b, record, ref)
            comp_group.append(group)
            for obj in b.objects[first_obj:]:
                if obj["k"] == "pin" and group >= 0:
                    pin = document.get(RecordRef(obj["rec"][0], obj["rec"][1]))
                    if isinstance(pin, Pin):
                        obj["net"] = pin_net.get((group, pin.designator), -1)
                obj["comp"] = comp
        elif isinstance(record, Wire):
            if not record.points:
                continue
            net = wire_net[wire_index[key]]
            b.obj("wire", record, info=[["Wire", ""]])
            b.objects[-1]["net"] = net
            b.line(
                [b.xy(p) for p in record.points], _hex(record.color), _width(record, LINE_WIDTHS[1] // 1000)
            )
            b.done()
        elif isinstance(record, Bus):
            b.obj("bus", record, info=[["Bus", ""]])
            b.line(
                [b.xy(p) for p in record.points], _hex(record.color), _width(record, LINE_WIDTHS[2] // 1000)
            )
            b.done()
        elif isinstance(record, SignalHarness):
            b.obj("harnessline", record, info=[["Signal Harness", ""]])
            b.line(
                [b.xy(p) for p in record.points], _hex(record.color), _width(record, LINE_WIDTHS[3] // 1000)
            )
            b.done()
        elif isinstance(record, BusEntry):
            b.obj("entryline", record, info=[["Bus Entry", ""]])
            b.line(
                [b.xy(record.location), b.xy(record.corner)],
                _hex(record.color),
                _width(record, LINE_WIDTHS[1] // 1000),
            )
            b.done()
        elif isinstance(record, Junction):
            b.obj("junction", record, info=[["Junction", ""]])
            c = b.xy(record.location)
            hits = _lines.at(pt(record.location))
            b.objects[-1]["net"] = wire_net[hits[0]] if hits else -1
            b.ellipse(c, round(1.5 * UNIT), round(1.5 * UNIT), _hex(record.color), 0, _hex(record.color))
            b.done()
        elif isinstance(record, NetLabel):
            b.obj("label", record, info=[["Net Label", record.text]])
            b.objects[-1]["net"] = ident_net.get(key, -1)
            _text_record(b, record, record.text, role="label")
            b.done()
        elif isinstance(record, PowerPort):
            _power(b, record)
            b.objects[-1]["net"] = ident_net.get(key, -1)
        elif isinstance(record, Port):
            _port(b, record)
            b.objects[-1]["net"] = ident_net.get(key, -1)
        elif isinstance(record, NoErc):
            b.obj("noerc", record, info=[["No ERC", ""]])
            x, y = b.xy(record.location)
            r, c, w = 3 * UNIT, _hex(record.color), LINE_WIDTHS[1] // 1000
            b.line([(x - r, y - r), (x + r, y + r)], c, w)
            b.line([(x - r, y + r), (x + r, y - r)], c, w)
            b.done()
        elif isinstance(record, SheetSymbol):
            first = len(b.objects)
            _sheet_symbol(b, record)
            for obj in b.objects[first:]:
                if obj["k"] == "entry":
                    obj["net"] = ident_net.get((obj["rec"][0], obj["rec"][1]), -1)
        elif isinstance(record, HarnessConnector):
            _harness_connector(b, record)
        elif isinstance(record, WarningSign):
            _directive(b, record)
        elif isinstance(record, Template | Sheet | Parameter):
            continue
        else:
            first = len(b.objects)
            b.obj("graphic", record)
            if not _graphic(b, record):
                b.objects.pop()
            elif b.objects[first]["b"] is None:
                b.objects.pop()
            b.done()
    for obj in b.objects:
        obj.pop("rec", None)
        if obj["net"] >= 0:
            obj["info"].append(["Net", nets[obj["net"]]["name"] or "(no name)"])
    if b.skipped_ieee:
        b.notes.append(f"{b.skipped_ieee} IEEE symbols are not drawn.")
    b.notes.append(FENOLITE_DRAWINGS)
    if frame["title_block"]:
        b.notes.append("The built-in title block is Fenolite's drawing of the sheet's parameters.")
    kinds = [obj["k"] for obj in b.objects]
    counts = {
        "components": len(b.comps),
        "pins": kinds.count("pin"),
        "wires": kinds.count("wire"),
        "buses": kinds.count("bus"),
        "bus_entries": kinds.count("entryline"),
        "labels": kinds.count("label"),
        "power_ports": kinds.count("power"),
        "ports": kinds.count("port"),
        "junctions": kinds.count("junction"),
        "no_erc": kinds.count("noerc"),
        "sheet_symbols": kinds.count("sheet"),
        "sheet_entries": kinds.count("entry"),
        "harness_connectors": kinds.count("harness"),
        "nets": sum(1 for net in nets if net["pins"] or net["name"]),
        "prims": len(b.prims),
    }
    bounds = [min(0, b.box[0]), min(0, b.box[1]), max(b.w, b.box[2]), max(b.h, b.box[3])]
    return {
        "schema": SCHEMA,
        "kind": "schematic",
        "meta": {
            "name": name,
            "sha256": hashlib.sha256(data).hexdigest() if data else "",
            "bytes": len(data),
            "backend": "altium",
            "evidence": evidence,
            "counts": counts,
            "notes": b.notes,
        },
        "bounds": bounds,
        "sheet": frame,
        "fonts": b.fonts,
        "prims": b.prims,
        "objects": b.objects,
        "comps": b.comps,
        "nets": nets,
        "overlays": [],
    }


class _LibraryDocument(SchDocument):
    """The records of one library symbol seen as a document: their owners name the stream ``data``."""

    def get(self, ref: RecordRef) -> SchRecord:
        if ref.stream == "data":
            return self.records[ref.index]
        return super().get(ref)


def build_symbol_scene(
    library: SchLibrary,
    component: SchLibComponent,
    *,
    name: str,
    part: int = 1,
    data: bytes = b"",
    evidence: str = "INFERRED",
) -> dict[str, Any]:
    """The scene of one part of an Altium library symbol (change c0179), on a sheet the size of the symbol,
    grown by 10 units; ``sheet.origin`` is the symbol's origin, so the status line reads library
    coordinates."""
    document = _LibraryDocument(
        file=name, form="binary", codepage=library.codepage, header=library.header, records=component.records
    )
    header = library.header.props
    b = _Builder(document, name, fonts=read_fonts(header) if header is not None else None)
    b.part = part
    big = 10**12
    b.box = [big, big, -big, -big]
    record = next((r for r in component.records if isinstance(r, Component)), None)
    if record is not None:
        _component(b, record, "")
    if b.box[0] > b.box[2]:
        b.box = [-UNIT, b.h - UNIT, UNIT, b.h + UNIT]
    pad = 10 * UNIT
    x0, y0, x1, y1 = b.box[0] - pad, b.box[1] - pad, b.box[2] + pad, b.box[3] + pad
    kinds = [obj["k"] for obj in b.objects]
    counts = {"components": len(b.comps), "pins": kinds.count("pin"), "prims": len(b.prims)}
    if b.skipped_ieee:
        b.notes.append(f"{b.skipped_ieee} IEEE symbols are not drawn.")
    return {
        "schema": SCHEMA,
        "kind": "schematic",
        "meta": {
            "name": name,
            "sha256": hashlib.sha256(data).hexdigest() if data else "",
            "bytes": len(data),
            "backend": "altium",
            "evidence": evidence,
            "counts": counts,
            "notes": b.notes,
        },
        "bounds": [x0, y0, x1, y1],
        "sheet": {
            "w": x1 - x0,
            "h": y1 - y0,
            "x0": x0,
            "y0": y0,
            "origin": [0, b.h],
            "color": SHEET_COLOR,
            "grid": 10 * UNIT,
            "border": False,
            "margin": 0,
            "zones": [1, 1],
            "title_block": False,
            "style": "Library",
        },
        "fonts": b.fonts,
        "prims": b.prims,
        "objects": [{k: v for k, v in obj.items() if k != "rec"} for obj in b.objects],
        "comps": b.comps,
        "nets": [],
        "overlays": [],
    }


def summary(scene: dict[str, Any]) -> dict[str, Any]:
    """The part of a schematic scene that a reply carries."""
    return {"kind": "schematic", "counts": dict(scene["meta"]["counts"]), "bounds_um": list(scene["bounds"])}


__all__ = ["SCHEMA", "build_schematic_scene", "build_symbol_scene", "summary"]
