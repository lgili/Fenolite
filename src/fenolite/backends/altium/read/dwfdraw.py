# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing content of an Altium Draftsman document (change c0180, capability draftsman-viewer).

``read_drawing(file)`` reads a document that ``read_draftsman`` decoded into plain values: the sheets with
their items, the font, line and fill styles, the document parameters, and the document's own copy of the
board (outline, layer primitives, holes and placed parts). Every length stays in the document's unit of
1/96 inch. The facts are in ``docs/formats/altium/draftsman.md``, "Drawing geometry": the board copy is in the
board's frame with Y up, a contour is a closed run of line and arc segments, a ``Uni`` is a stadium, and a
part's local geometry is placed by its location and rotation, mirrored in Y first for a bottom part. Nothing
is opened or run; members the reader does not find are left out.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from fenolite.backends.altium.read.draftsman import INSTANCE, NAMESPACE, DraftsmanFile
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-DWF-GEOM",))

_NS = "{" + NAMESPACE + "}"
_TYPE = "{" + INSTANCE + "}type"
_NIL = "{" + INSTANCE + "}nil"
ARC_STEP = 5.0
"""The largest angle, in degrees, between two points of a sampled arc."""

Pt = tuple[float, float]


@dataclass(frozen=True)
class Style:
    """A font (``family``, ``size`` in points), line (``color``, ``thickness``) or fill (``color``) style."""

    color: str = "#000000"
    thickness: float = 0.0
    family: str = ""
    size: float = 0.0
    pattern: str = ""
    alpha: float = 1.0


@dataclass(frozen=True)
class Item:
    """An object of a sheet: its ``i:type`` and the members the drawing uses."""

    kind: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class Page:
    """A sheet: size and margin in 1/96 inch, the zones, and its items in file order."""

    width: float
    height: float
    margin: tuple[float, float, float, float]
    zones: tuple[bool, int, int]
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Stadium:
    """A ``Uni``: centre, length along ``direction``, width and corner radius."""

    centre: Pt
    length: float
    width: float
    radius: float
    direction: Pt


@dataclass(frozen=True)
class LayerArc:
    centre: Pt
    radius: float
    start: float
    end: float
    thickness: float


@dataclass(frozen=True)
class BoardLayer:
    name: str
    v7: int
    color: str
    stadiums: tuple[Stadium, ...] = ()
    arcs: tuple[LayerArc, ...] = ()


@dataclass(frozen=True)
class Hole:
    centre: Pt
    size: float
    plated: bool
    length: float = 0.0


@dataclass(frozen=True)
class Part:
    """A placed part: its open strokes on the board (assembly drawing, else silkscreen) with their widths, its
    pad centres and its box (lower-left corner, width, height)."""

    ref: str
    comment: str
    side: str
    contours: tuple[tuple[Pt, ...], ...]
    pads: tuple[Pt, ...]
    box: tuple[float, float, float, float] | None
    widths: tuple[float, ...] = ()
    height: float = 0.0
    """The part type's ``Height``: the extent of its bodies along Z, in document units (change c0190)."""
    min_z: float = 0.0
    """The part type's ``MinZ``: where that extent starts, from the surface of the part's side (below it when
    negative, as for leads through the board)."""


@dataclass(frozen=True)
class StackLayer:
    name: str
    kind: str
    thickness: float
    material: str


@dataclass(frozen=True)
class BoardCopy:
    outline: tuple[Pt, ...] = ()
    cutouts: tuple[tuple[Pt, ...], ...] = ()
    bounds: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    """Lower-left corner, width and height."""
    thickness: float = 0.0
    layers: tuple[BoardLayer, ...] = ()
    holes: tuple[Hole, ...] = ()
    parts: tuple[Part, ...] = ()
    stack: tuple[StackLayer, ...] = ()
    side_frames: dict[str, tuple[float, float, float, float]] = field(default_factory=lambda: {})
    """``BoardBoundsBack`` and ``BoardBoundsRight`` of the assembly information, by ``Back`` and ``Right``
    (X, Y, width, height): the frames of the side views (change c0190)."""


@dataclass(frozen=True)
class Drawing:
    pages: tuple[Page, ...]
    fonts: dict[str, Style] = field(default_factory=lambda: {})
    lines: dict[str, Style] = field(default_factory=lambda: {})
    fills: dict[str, Style] = field(default_factory=lambda: {})
    parameters: dict[str, str] = field(default_factory=lambda: {})
    board: BoardCopy = field(default_factory=BoardCopy)
    is_panel: bool = False
    metric: bool = False
    source: str = ""
    skipped: dict[str, int] = field(default_factory=lambda: {})


# --- element helpers ------------------------------------------------------------------------------------


def _find(element: ET.Element | None, path: str) -> ET.Element | None:
    if element is None:
        return None
    found: ET.Element | None = element
    for part in path.split("/"):
        found = found.find(_NS + part) if found is not None else None
    if found is None or found.get(_NIL) == "true":
        return None
    return found


def _text(element: ET.Element | None, path: str, default: str = "") -> str:
    found = _find(element, path)
    return default if found is None or found.text is None else found.text


def _num(element: ET.Element | None, path: str, default: float = 0.0) -> float:
    try:
        return float(_text(element, path) or default)
    except ValueError:
        return default


def _pt(element: ET.Element | None, path: str) -> Pt:
    found = _find(element, path)
    return (_num(found, "X"), _num(found, "Y"))


def _children(element: ET.Element | None, path: str) -> list[ET.Element]:
    found = _find(element, path)
    return [] if found is None else list(found)


def _colour(element: ET.Element | None) -> tuple[str, float]:
    if element is None:
        return "#000000", 1.0
    r, g, b = (max(0, min(255, round(_num(element, k)))) for k in ("R", "G", "B"))
    alpha = _num(element, "A", 255.0) / 255.0
    return f"#{r:02x}{g:02x}{b:02x}", alpha


def _name(element: ET.Element) -> str:
    return element.tag.split("}")[-1]


# --- contours -------------------------------------------------------------------------------------------


def _arc_points(centre: Pt, radius: float, a0: float, a1: float) -> list[Pt]:
    span = a1 - a0
    steps = max(1, math.ceil(abs(span) / ARC_STEP))
    return [
        (
            centre[0] + radius * math.cos(math.radians(a0 + span * k / steps)),
            centre[1] + radius * math.sin(math.radians(a0 + span * k / steps)),
        )
        for k in range(1, steps)
    ]


def contour(segments: list[ET.Element], *, closed: bool = True) -> tuple[Pt, ...]:
    """A run of segments as points, arcs sampled at ``ARC_STEP`` at most: a ``Line`` runs to the next
    segment's ``Point``; an ``Arc`` runs from its ``Point`` (at ``Angle1`` or at ``Angle2``) to the next
    segment's ``Point`` on its circle. A closed run (a board outline) returns to its first ``Point``; in an
    open run (a part's assembly or silkscreen stroke) the last ``Line`` only ends it and the last ``Arc``
    runs to its other angle, so a lone arc of 0 to 360 degrees is a circle."""
    out: list[Pt] = []
    for n, segment in enumerate(segments):
        point = _pt(segment, "Point")
        out.append(point)
        if _text(segment, "Kind") != "Arc":
            continue
        centre, radius = _pt(segment, "Center"), _num(segment, "Radius")
        a1, a2 = _num(segment, "Angle1"), _num(segment, "Angle2")
        at1 = (
            centre[0] + radius * math.cos(math.radians(a1)),
            centre[1] + radius * math.sin(math.radians(a1)),
        )
        forward = math.dist(at1, point) <= math.dist(_arc_end(centre, radius, a2), point)
        out += _arc_points(centre, radius, a1, a2) if forward else _arc_points(centre, radius, a2, a1)
        if not closed and n == len(segments) - 1:
            out.append(_arc_end(centre, radius, a2 if forward else a1))
    return tuple(out)


def _arc_end(centre: Pt, radius: float, angle: float) -> Pt:
    return (
        centre[0] + radius * math.cos(math.radians(angle)),
        centre[1] + radius * math.sin(math.radians(angle)),
    )


def _strokes(element: ET.Element | None, path: str) -> list[tuple[tuple[Pt, ...], float]]:
    """The open contours under ``path`` (each ``Contour`` of an assembly drawing or a silkscreen) with their
    ``Thickness``."""
    found = _find(element, path)
    if found is None:
        return []
    out: list[tuple[tuple[Pt, ...], float]] = []
    for item in found:
        segments = _children(item, "Segments") if _name(item) == "Contour" else []
        if segments:
            out.append((contour(segments, closed=False), _num(item, "Thickness")))
    return out


# --- styles, parameters, items --------------------------------------------------------------------------


def _styles(root: ET.Element) -> tuple[dict[str, Style], dict[str, Style], dict[str, Style]]:
    fonts: dict[str, Style] = {}
    for entry in _children(root, "FontStyles"):
        fonts[_text(entry, "Id")] = Style(
            family=_text(entry, "FamilyName", "Arial"), size=_num(entry, "Size", 10)
        )
    lines: dict[str, Style] = {}
    for entry in _children(root, "LineStyles"):
        colour, alpha = _colour(_find(entry, "Color"))
        lines[_text(entry, "Id")] = Style(color=colour, alpha=alpha, thickness=_num(entry, "Thickness"))
    fills: dict[str, Style] = {}
    for entry in _children(root, "FillStyles"):
        colour, alpha = _colour(_find(entry, "Color"))
        fills[_text(entry, "Id")] = Style(color=colour, alpha=alpha, pattern=_text(entry, "Pattern"))
    return fonts, lines, fills


def _parameters(root: ET.Element) -> dict[str, str]:
    found: dict[str, str] = {}
    data = _find(root, "ParametersData")
    for group in ("PCBParameters", "PCBParametersV2", "ProjectParameters"):
        for entry in _children(data, group):
            found.setdefault(_text(entry, "Name").casefold(), _text(entry, "Value"))
    for entry in _children(root, "Parameters"):
        found[_text(entry, "Name").casefold()] = _text(entry, "Value")
    return found


_SNAP = re.compile(r"\|(Line|Point):\s*([-0-9.eE+]+(?:\s*,\s*[-0-9.eE+]+)*)\s*$")


def snap_points(snap: str) -> tuple[Pt, ...]:
    """The board points a dimension anchor's ``SnapId`` names: two for ``…|Line: x1, y1, x2, y2``, one for
    ``…|Point: x, y``, none for another form (``draftsman.md``, "Drawing geometry")."""
    found = _SNAP.search(snap)
    if found is None:
        return ()
    values = [float(v) for v in found.group(2).split(",")]
    count = 2 if found.group(1) == "Line" else 1
    if len(values) != 2 * count:
        return ()
    return tuple((values[2 * k], values[2 * k + 1]) for k in range(count))


def _item(element: ET.Element) -> Item:
    kind = element.get(_TYPE, _name(element))
    f: dict[str, Any] = {
        "id": _text(element, "Id"),
        "template": _text(element, "OriginatedFromTemplate") == "true",
    }
    if kind == "Line":
        f |= {
            "start": _pt(element, "StartPoint"),
            "end": _pt(element, "EndPoint"),
            "style": _text(element, "StyleId"),
        }
    elif kind in ("Rectangle", "Text", "Picture"):
        rect = _find(element, "Rect")
        f["rect"] = (_num(rect, "X"), _num(rect, "Y"), _num(rect, "Width"), _num(rect, "Height"))
        f["rotation"] = _text(element, "Rotation", "Ccw0")
        if kind == "Rectangle":
            f |= {"line": _text(element, "LineStyleId"), "fill": _text(element, "FillStyleId")}
        elif kind == "Text":
            colour, _alpha = _colour(_find(element, "Color"))
            f |= {
                "text": _text(element, "Text"),
                "font": _text(element, "FontStyleId"),
                "color": colour,
                "h": _text(element, "HorizontalAlignment", "Left"),
                "v": _text(element, "VerticalAlignment", "Top"),
            }
        else:
            f["bitmap"] = _text(element, "Bitmap")
    elif kind == "Note":
        colour, _alpha = _colour(_find(element, "ElementTextColor"))
        title = next(
            iter(_children(element, "ElementItems")), None
        )  # the linked title text, when there is one
        f |= {
            "start": _pt(element, "StartPoint"),
            "width": _num(element, "Width"),
            "title": _text(element, "Title") or _text(title, "Title"),
            "title_visible": _text(element, "TitleVisible", "true") == "true"
            and _text(title, "IsShow", "true") == "true",
            "font": _text(element, "ElementFontStyleId"),
            "title_font": _text(element, "TitleFontStyleId") or _text(title, "FontStyleId"),
            "color": colour,
            "spacing": _num(element, "VerticalSpacing"),
            "elements": [(_text(e, "Text"), _text(e, "Postfix")) for e in _children(element, "Elements")],
            "element_ids": [
                (_text(e, "Id"), _text(e, "BorderStyle", "None")) for e in _children(element, "Elements")
            ],
        }
    elif kind == "Callout":  # change c0190
        colour, _alpha = _colour(_find(element, "ForegroundTextColor"))
        source = next(iter(_children(element, "Sources")), None)
        f |= {
            "target": _pt(element, "TargetAnchor/PointOnPage"),
            "leader": _pt(element, "Leader"),
            "elbow": _num(element, "ElbowLength"),
            "elbow_side": _text(element, "ElbowPosition", "Left"),
            "font": _text(element, "FontStyleId"),
            "color": colour,
            "line": _text(element, "LineStyleId"),
            "border": _text(element, "BorderLineStyleId"),
            "source": _text(source, "SourceType"),
            "note_element": _text(source, "NoteElementId"),
            "custom": _text(source, "CustomText"),
            "prefix": _text(element, "Prefix"),
        }
    elif kind == "LinearDimension":
        colour, _alpha = _colour(_find(element, "TextColor"))
        f |= {
            "a": _pt(element, "StartAnchor/PointOnPage"),
            "b": _pt(element, "EndAnchor/PointOnPage"),
            "ref": _pt(element, "DimensionReferencePoint"),
            "line": _text(element, "DimensionLineStyleId"),
            "font": _text(element, "FontStyleId"),
            "color": colour,
            "override": _text(element, "OverriddenValue")
            if _text(element, "IsValueOverridden") == "true"
            else None,
            "prefix": _text(element, "TextPrefix"),
            "suffix": _text(element, "TextSuffix"),
            "direction": _pt(element, "ExtensionsDirection"),
            "target": _text(element, "StartAnchor/SnapTargetItemId")
            or _text(element, "EndAnchor/SnapTargetItemId"),
            "units": _text(element, "Units"),
            "snaps": (_text(element, "StartAnchor/SnapId"), _text(element, "EndAnchor/SnapId")),
            "offsets": (
                _pt(element, "StartAnchor/SnapPointOffset"),
                _pt(element, "EndAnchor/SnapPointOffset"),
            ),
        }
    elif _find(element, "Location") is not None:
        use_custom = _text(element, "UseCustomScale") == "true"
        ratio = _num(element, "Scale/Numenator", 1.0) / (_num(element, "Scale/Denominator", 1.0) or 1.0)
        title_colour, _alpha = _colour(_find(element, "TitleColor"))
        f |= {
            "location": _pt(element, "Location"),
            "scale": _num(element, "CustomScale", 1.0) if use_custom else ratio,
            "side": _text(element, "ViewSide", "Top"),
            "rotation": _text(element, "Rotation", "Ccw0"),
            "title": _text(element, "Title"),
            "show_title": _text(element, "ShowTitle", "true") == "true",
            "title_font": _text(element, "TitleFontStyleId"),
            "title_color": title_colour,
            "layer": int(_num(element, "LayerV7Id", -1)),
            "line": _text(element, "BoardShapeLineStyleId")
            or _text(element, "BoardLineStyleId")
            or _text(element, "LineStyleId"),
            "component_line": _text(element, "ComponentLineStyleId"),
            "size": (_num(element, "Size/Width"), _num(element, "Size/Height")),
        }
        if kind in (
            "DrillTableBoardView",
            "LayerStackLegendView",
            "BillOfMaterialsView",
            "TransmissionLineTableData",
        ):
            f["table_title"] = (
                next((_text(e, "Title") for e in _children(element, "ElementItems")), "") or f["title"]
            )
    return Item(kind, f)


# --- the board copy -------------------------------------------------------------------------------------


def _layers(root: ET.Element) -> tuple[BoardLayer, ...]:
    out: list[BoardLayer] = []
    for geometry in _children(root, "BoardLayersGeometryInformation/LayersGeometry"):
        layer = _find(geometry, "Layer")
        colour, _alpha = _colour(_find(layer, "Color"))
        stadiums: list[Stadium] = []
        arcs: list[LayerArc] = []
        for primitive in _children(geometry, "Primitives"):
            items = _find(primitive, "CopperItems/PrimitiveItem")
            for uni in _children(items, "Unis"):
                stadiums.append(
                    Stadium(
                        _pt(uni, "Location"),
                        _num(uni, "Size/Width"),
                        _num(uni, "Size/Height"),
                        _num(uni, "Radius"),
                        _pt(uni, "Direction"),
                    )
                )
            for arc in _children(items, "Arcs"):
                arcs.append(
                    LayerArc(
                        _pt(arc, "Center"),
                        _num(arc, "Radius"),
                        _num(arc, "StartAngle"),
                        _num(arc, "EndAngle"),
                        _num(arc, "Thickness"),
                    )
                )
        out.append(
            BoardLayer(
                _text(layer, "Name"), int(_num(layer, "V7LayerId", -1)), colour, tuple(stadiums), tuple(arcs)
            )
        )
    return tuple(out)


def place(local: Pt, location: Pt, rotation: float, bottom: bool) -> Pt:
    """A part's local point on the board: mirrored in Y first for a bottom part, then turned by ``rotation``
    degrees counter-clockwise and moved to ``location`` (``draftsman.md``, "Drawing geometry")."""
    x, y = local[0], -local[1] if bottom else local[1]
    a = math.radians(rotation)
    c, s = math.cos(a), math.sin(a)
    return (location[0] + x * c - y * s, location[1] + x * s + y * c)


def _parts(root: ET.Element) -> tuple[Part, ...]:
    out: list[Part] = []
    for part_type in _children(root, "BoardAssemblyInformation/ComponentTypes"):
        height, min_z = _num(part_type, "Height"), _num(part_type, "MinZ")
        local = _strokes(part_type, "AssemblyDrawing") or _strokes(part_type, "Silkscreen")
        pads = [
            _pt(p, "CenterPoint")
            for side in ("TopLayerPads", "BottomLayerPads")
            for p in _children(part_type, side)
        ]
        for component in _children(part_type, "Components"):
            location = _pt(component, "Location")
            rotation = _num(component, "Rotation")
            side = _text(component, "BoardSide", "Top")
            bottom = side == "Bottom"
            contours = tuple(tuple(place(p, location, rotation, bottom) for p in ring) for ring, _w in local)
            placed = tuple(place(p, location, rotation, bottom) for p in pads)
            box_el = _find(component, "BoundingBox")
            box = None
            if box_el is not None:
                box = (_num(box_el, "X"), _num(box_el, "Y"), _num(box_el, "Width"), _num(box_el, "Height"))
            out.append(
                Part(
                    _text(component, "Designator"),
                    _text(component, "Comment"),
                    side,
                    contours,
                    placed,
                    box,
                    tuple(w for _ring, w in local),
                    height,
                    min_z,
                )
            )
    return tuple(out)


def _holes(root: ET.Element) -> tuple[Hole, ...]:
    entries = _children(root, "DrillTableInformation/HolesV2") or _children(
        root, "BoardAssemblyInformation/Holes"
    )
    return tuple(
        Hole(_pt(h, "CenterPoint"), _num(h, "HoleSize"), _text(h, "Plated") == "true", _num(h, "Lenght"))
        for h in entries
    )


def _stack(root: ET.Element) -> tuple[StackLayer, ...]:
    layers = _children(root, "LayerStackInformation/BoardLayerStackData/BoardLayerStack/Stack")
    out: list[StackLayer] = []
    for layer in layers:
        out.append(
            StackLayer(
                _text(layer, "Name") or _text(layer, "LayerName"),
                _text(layer, "LayerType") or _text(layer, "Type") or _text(layer, "Kind"),
                _num(layer, "Thickness"),
                _text(layer, "Material") or _text(layer, "MaterialName"),
            )
        )
    return tuple(out)


def _board(root: ET.Element) -> BoardCopy:
    fabrication = _find(root, "BoardFabricationInformation")
    assembly = _find(root, "BoardAssemblyInformation")
    source = fabrication if _find(fabrication, "BoardOutline") is not None else assembly
    outline = contour(_children(source, "BoardOutline/Segments"))
    cutouts = tuple(contour(_children(c, "Segments")) for c in _children(source, "Cutouts"))
    frames: dict[str, tuple[float, float, float, float]] = {}
    for name in ("Back", "Right"):
        frame = _find(assembly, f"BoardBounds{name}")
        if frame is not None:
            frames[name] = (_num(frame, "X"), _num(frame, "Y"), _num(frame, "Width"), _num(frame, "Height"))
    bounds_el = _find(source, "BoardOutlineBounds")
    bounds = (_num(bounds_el, "X"), _num(bounds_el, "Y"), _num(bounds_el, "Width"), _num(bounds_el, "Height"))
    if bounds[2] <= 0 and outline:
        xs, ys = [p[0] for p in outline], [p[1] for p in outline]
        bounds = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    return BoardCopy(
        outline,
        cutouts,
        bounds,
        _num(assembly, "BoardThickness"),
        _layers(root),
        _holes(root),
        _parts(root),
        _stack(root),
        frames,
    )


def read_drawing(file: DraftsmanFile) -> Drawing:
    """The sheets, styles, parameters and board copy of a decoded document."""
    root = file.root
    pages: list[Page] = []
    skipped: dict[str, int] = {}
    known = {
        "Line",
        "Rectangle",
        "Text",
        "Picture",
        "Note",
        "LinearDimension",
        "BoardAssemblyViewData",
        "BoardFabricationViewData",
        "DrillViewView",
        "DrillTableBoardView",
        "LayerStackLegendView",
        "BillOfMaterialsView",
        "Callout",
    }
    for page in _children(root, "Pages"):
        items: list[Item] = []
        for element in _children(page, "Items"):
            kind = element.get(_TYPE, _name(element))
            if kind not in known:
                skipped[kind] = skipped.get(kind, 0) + 1
                continue
            items.append(_item(element))
        margin = _find(page, "Margin")
        pages.append(
            Page(
                _num(page, "Size/Width"),
                _num(page, "Size/Height"),
                (_num(margin, "Left"), _num(margin, "Top"), _num(margin, "Right"), _num(margin, "Bottom")),
                (
                    _text(page, "ShowZones") == "true",
                    int(_num(page, "HorizontalZoneCount")),
                    int(_num(page, "VerticalZoneCount")),
                ),
                tuple(items),
            )
        )
    fonts, lines, fills = _styles(root)
    return Drawing(
        tuple(pages),
        fonts,
        lines,
        fills,
        _parameters(root),
        _board(root),
        _text(root, "IsPanel") == "true",
        _text(root, "MeasurementSystem") == "Metric",
        _text(root, "SourceDocumentName"),
        skipped,
    )


__all__ = [
    "BoardCopy",
    "BoardLayer",
    "Drawing",
    "Hole",
    "Item",
    "LayerArc",
    "Page",
    "Part",
    "StackLayer",
    "Stadium",
    "Style",
    "contour",
    "place",
    "read_drawing",
    "snap_points",
]
