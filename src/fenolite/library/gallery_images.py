# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The images of the library gallery drawn by Fenolite (change c0405, ``docs/library-repo.md``, "Gallery").

A symbol or a footprint is drawn from the scene the library viewer draws (``catalog_scene``, c0262) as a
standalone SVG: integer coordinates in micrometres, a fixed palette, system fonts, no script. A footprint
shows its front copper, silkscreen, courtyard and fabrication layers (the back ones when it has no front
copper), the pad numbers and an outline around pin 1. The same definition gives the same bytes.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from html import escape
from typing import Any, cast

from fenolite.model.library import FootprintDef, SymbolDef

PIXELS = 480
"""The longer side of an image's intrinsic size, in pixels."""
PAPER, BOARD = "#ffffff", "#17202b"
"""The backgrounds of symbol and footprint images: a symbol on paper, a land on a dark board."""
LAYER_STYLE: Mapping[str, tuple[str, str]] = {
    "Fab": ("#7d8aa0", "fab"),
    "CrtYd": ("#e05cc8", "courtyard"),
    "Cu": ("#d8a743", "copper"),
    "SilkS": ("#f1f1ec", "silkscreen"),
}
"""Footprint layer suffix → (colour, class), in drawing order."""
DRILL_COLOUR, PIN1_COLOUR, NUMBER_COLOUR = "#0d1219", "#38d39f", "#17202b"
FONT = "system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
MAX_NUMBERED_PADS = 64
"""Pads above this count are drawn without their numbers, which would only clutter the land."""


@dataclass(frozen=True, slots=True)
class View:
    """One image of an item page: the file name beside the page, its caption and bytes."""

    name: str
    caption: str
    data: bytes


@dataclass(frozen=True, slots=True)
class Media:
    """The images and facts of one item; ``missing`` names why an expected image could not be made."""

    views: tuple[View, ...] = ()
    missing: str | None = None
    facts: tuple[tuple[str, str], ...] = ()
    table: tuple[tuple[str, ...], tuple[tuple[str, ...], ...]] | None = None
    links: tuple[tuple[str, str], ...] = field(default=())
    """(label, gallery page) of related items, e.g. a device's symbol and footprint."""


def _n(value: float) -> str:
    return str(round(value))


def _box(bounds: Sequence[float], margin: float) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = (round(v) for v in bounds)
    pad = max(round(max(x1 - x0, y1 - y0) * margin), 200)
    return x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad


def _svg(box: tuple[int, int, int, int], background: str, title: str, body: Iterable[str]) -> bytes:
    x, y, w, h = box
    scale = PIXELS / max(w, h, 1)
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}" '
        f'width="{max(round(w * scale), 1)}" height="{max(round(h * scale), 1)}" role="img">'
        f"<title>{escape(title)}</title>"
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{background}"/>'
    )
    return (head + "".join(body) + "</svg>\n").encode("utf-8")


# ---- symbols --------------------------------------------------------------------------------------


def _colour(value: object, default: str) -> str:
    return value if isinstance(value, str) and value.startswith("#") else default


def _fill(prim: Mapping[str, Any]) -> str:
    fill = prim.get("f")
    return fill if isinstance(fill, str) and fill.startswith("#") else "none"


def _text(prim: Mapping[str, Any]) -> str:
    anchor = {"left": "start", "center": "middle", "right": "end"}.get(str(prim.get("h")), "middle")
    baseline = {"top": "hanging", "center": "central", "bottom": "alphabetic"}.get(
        str(prim.get("v")), "central"
    )
    x, y, turns = int(prim["x"]), int(prim["y"]), int(prim.get("rot", 0)) % 4
    turn = f' transform="rotate({-90 * turns} {x} {y})"' if turns else ""
    return (
        f'<text x="{x}" y="{y}" font-size="{int(prim.get("sz", 1270))}" '
        f'fill="{_colour(prim.get("c"), "#333")}" '
        f'text-anchor="{anchor}" dominant-baseline="{baseline}"{turn}>{escape(str(prim.get("s", "")))}</text>'
    )


def _symbol_prim(prim: Mapping[str, Any]) -> str:
    kind, colour = prim.get("k"), _colour(prim.get("c"), "#8a1212")
    width = max(int(prim.get("w") or 0), 100)
    stroke = f'stroke="{colour}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"'
    if kind in ("l", "g"):
        points = cast(list[int], prim.get("p", []))
        coords = " ".join(f"{points[i]},{points[i + 1]}" for i in range(0, len(points) - 1, 2))
        dash = f' stroke-dasharray="{int(prim["d"])}"' if prim.get("d") else ""
        tag = "polygon" if kind == "g" else "polyline"
        fill = _fill(prim) if kind == "g" else "none"
        return f'<{tag} points="{coords}" fill="{fill}" {stroke}{dash}/>'
    if kind == "r":
        x0, y0, x1, y1 = (int(v) for v in prim["b"])
        return f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="{_fill(prim)}" {stroke}/>'
    if kind == "e":
        return (
            f'<ellipse cx="{int(prim["x"])}" cy="{int(prim["y"])}" rx="{int(prim["rx"])}" '
            f'ry="{int(prim["ry"])}" fill="{_fill(prim)}" {stroke}/>'
        )
    if kind == "a":
        cx, cy, r = int(prim["x"]), int(prim["y"]), int(prim["rx"])
        a0, a1 = math.radians(float(prim["a0"])), math.radians(float(prim["a1"]))
        start = (cx + r * math.cos(a0), cy - r * math.sin(a0))
        end = (cx + r * math.cos(a1), cy - r * math.sin(a1))
        large = 1 if float(prim["a1"]) - float(prim["a0"]) > 180 else 0
        path = f"M{_n(start[0])},{_n(start[1])}A{r},{r} 0 {large} 0 {_n(end[0])},{_n(end[1])}"
        if prim.get("pie"):
            path += f"L{cx},{cy}Z"
        return f'<path d="{path}" fill="{_fill(prim)}" {stroke}/>'
    if kind == "b":
        p = [int(v) for v in prim["p"]]
        if len(p) == 8:
            return (
                f'<path d="M{p[0]},{p[1]}C{p[2]},{p[3]} {p[4]},{p[5]} {p[6]},{p[7]}" fill="none" {stroke}/>'
            )
        return ""
    if kind == "t":
        return _text(prim)
    if kind == "x":
        x0, y0 = (int(v) for v in prim["b"][:2])
        return _text({**prim, "x": x0, "y": y0, "h": "left", "v": "top"})
    return ""  # images ("i") and unknown primitives are not drawn


def symbol_svg(definition: SymbolDef, scene: Mapping[str, Any]) -> bytes:
    """The SVG of a symbol's catalog scene."""
    prims = cast(list[Mapping[str, Any]], scene.get("prims", []))
    body = [f'<g font-family="{FONT}">', *(_symbol_prim(p) for p in prims), "</g>"]
    return _svg(_box(cast(list[int], scene["bounds"]), 0.06), PAPER, f"Symbol {definition.lib_id}", body)


def _extent(prim: Mapping[str, Any]) -> tuple[float, float, float, float]:
    """A schematic primitive's box in micrometres; a text's from its anchor, size and length."""
    kind = prim.get("k")
    if kind in ("l", "g", "b"):
        p = [float(v) for v in cast(list[Any], prim.get("p", []))]
        xs, ys = p[0::2] or [0.0], p[1::2] or [0.0]
        return min(xs), min(ys), max(xs), max(ys)
    if kind in ("r", "x"):
        x0, y0, x1, y1 = (float(v) for v in cast(list[Any], prim["b"])[:4])
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
    if kind in ("e", "a"):
        x, y = float(prim["x"]), float(prim["y"])
        rx, ry = float(prim["rx"]), float(prim.get("ry", prim["rx"]))
        return x - rx, y - ry, x + rx, y + ry
    if kind == "t":
        x, y, size = float(prim["x"]), float(prim["y"]), float(prim.get("sz", 1270))
        span = 0.65 * size * len(str(prim.get("s", "")))
        if int(prim.get("rot") or 0) % 180:
            reach = max(span, size)  # turned text: as far in either direction
            return x - reach, y - reach, x + reach, y + reach
        h, v = prim.get("h"), prim.get("v")
        x0 = x if h == "left" else x - span if h == "right" else x - span / 2
        y0 = y if v == "top" else y - size if v == "bottom" else y - size / 2
        return x0, y0, x0 + span, y0 + size
    return math.inf, math.inf, -math.inf, -math.inf


def scene_svg(scene: Mapping[str, Any], *, name: str, title: str) -> bytes:
    """The SVG of one schematic sheet from the scene of Fenolite's schematic viewer, without its drawing
    sheet and cropped to what the sheet holds. The caller builds the scene (``fenolite.view`` sits above
    ``library`` in the package layering). Raises ``ValueError`` on an empty sheet."""
    # The drawing sheet (frame, zone numbers, title block) belongs to no object.
    prims = [p for p in cast(list[Mapping[str, Any]], scene.get("prims", [])) if int(p.get("o", -1)) >= 0]
    boxes = [_extent(p) for p in prims]
    boxes = [b for b in boxes if b[0] <= b[2]]
    if not boxes:
        raise ValueError(f"{name} draws nothing")
    bounds = (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )
    body = [f'<g font-family="{FONT}">', *(_symbol_prim(p) for p in prims), "</g>"]
    return _svg(_box(bounds, 0.06), PAPER, title, body)


# ---- footprints -----------------------------------------------------------------------------------


def _arc3(data: Sequence[int]) -> str:
    """An SVG path through three points (start, mid, end); a straight line when they are collinear."""
    (sx, sy), (mx, my), (ex, ey) = (data[0], data[1]), (data[2], data[3]), (data[4], data[5])
    d = 2 * (sx * (my - ey) + mx * (ey - sy) + ex * (sy - my))
    if d == 0:
        return f"M{sx},{sy}L{ex},{ey}"
    ux = (
        (sx * sx + sy * sy) * (my - ey) + (mx * mx + my * my) * (ey - sy) + (ex * ex + ey * ey) * (sy - my)
    ) / d
    uy = (
        (sx * sx + sy * sy) * (ex - mx) + (mx * mx + my * my) * (sx - ex) + (ex * ex + ey * ey) * (mx - sx)
    ) / d
    r = math.hypot(sx - ux, sy - uy)
    cross = (mx - sx) * (ey - sy) - (my - sy) * (ex - sx)
    sweep = 1 if cross > 0 else 0
    a_s, a_m, a_e = (math.atan2(y - uy, x - ux) for x, y in ((sx, sy), (mx, my), (ex, ey)))
    span = (a_e - a_s) % (2 * math.pi) if sweep else (a_s - a_e) % (2 * math.pi)
    large = 1 if span > math.pi else 0
    del a_m
    return f"M{sx},{sy}A{_n(r)},{_n(r)} 0 {large} {sweep} {ex},{ey}"


HAIRLINE = 'stroke-width="2" vector-effect="non-scaling-stroke"'
"""Courtyard and fabrication outlines: two image pixels wide whatever their width in the file."""
HAIRLINE_LAYERS = frozenset({"CrtYd", "Fab"})


def _width(width: int, hairline: bool) -> str:
    return HAIRLINE if hairline else f'stroke-width="{max(width, 50)}"'


def _land_prim(kind: str, data: Sequence[Any], colour: str, hairline: bool = False) -> str:
    if kind == "s":
        x0, y0, x1, y1, w = (int(v) for v in data[:5])
        return (
            f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="{colour}" {_width(w, hairline)} '
            'stroke-linecap="round"/>'
        )
    if kind == "a":
        return (
            f'<path d="{_arc3([int(v) for v in data[:6]])}" fill="none" stroke="{colour}" '
            f'{_width(int(data[6]), hairline)} stroke-linecap="round"/>'
        )
    if kind == "c":
        return f'<circle cx="{int(data[0])}" cy="{int(data[1])}" r="{int(data[2])}" fill="{colour}"/>'
    if kind == "l":
        width, points = int(data[0]), [int(v) for v in data[1:]]
        coords = " ".join(f"{points[i]},{points[i + 1]}" for i in range(0, len(points) - 1, 2))
        return (
            f'<polyline points="{coords}" fill="none" stroke="{colour}" {_width(width, hairline)} '
            'stroke-linecap="round" stroke-linejoin="round"/>'
        )
    if kind == "p":
        rings = cast(list[list[int]], data)
        path = "".join(
            "M" + "L".join(f"{ring[i]},{ring[i + 1]}" for i in range(0, len(ring) - 1, 2)) + "Z"
            for ring in rings
            if len(ring) >= 6
        )
        return f'<path d="{path}" fill="{colour}" fill-rule="evenodd"/>' if path else ""
    return ""


def _pin_one(pads: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for number in ("1", "A1"):
        for pad in pads:
            if str(pad.get("number")) == number:
                return pad
    return pads[0] if pads else None


def footprint_svg(definition: FootprintDef, scene: Mapping[str, Any]) -> bytes:
    """The SVG of a footprint's catalog scene: the land on a dark board, pin 1 outlined."""
    prims = cast(list[list[Any]], scene.get("prims", []))
    pads = cast(list[Mapping[str, Any]], scene.get("pads", []))
    front = any(str(p[0]) == "F.Cu" for p in prims) or not any(str(p[0]) == "B.Cu" for p in prims)
    side = "F." if front else "B."
    body: list[str] = []
    for suffix, (colour, name) in LAYER_STYLE.items():
        layer = side + suffix
        thin = suffix in HAIRLINE_LAYERS
        group = [_land_prim(str(p[1]), cast(list[Any], p[2]), colour, thin) for p in prims if p[0] == layer]
        if suffix == "Cu":  # through-hole pads also draw on the other copper side
            group += [
                _land_prim(str(p[1]), cast(list[Any], p[2]), colour) for p in prims if p[0] in ("*.Cu",)
            ]
        if group:
            body.append(f'<g class="{name}">' + "".join(group) + "</g>")
    holes = [
        _land_prim(str(p[1]), cast(list[Any], p[2]), DRILL_COLOUR) for p in prims if p[0] == "View.Drill"
    ]
    if holes:
        body.append('<g class="drill">' + "".join(holes) + "</g>")
    labels: list[str] = []
    if len(pads) <= MAX_NUMBERED_PADS:
        for pad in pads:
            size = min(int(pad.get("w") or 0), int(pad.get("h") or 0)) // 1000
            if size <= 0:
                continue
            font = max(size * 45 // 100, 120)
            labels.append(
                f'<text x="{int(pad["x"])}" y="{int(pad["y"])}" font-size="{font}" '
                f'stroke-width="{max(font // 6, 20)}">'
                f"{escape(str(pad.get('number', '')))}</text>"
            )
    if labels:
        body.append(
            f'<g class="numbers" font-family="{FONT}" font-weight="600" fill="#ffffff" '
            f'stroke="{NUMBER_COLOUR}" '
            'paint-order="stroke" text-anchor="middle" dominant-baseline="central">'
            + "".join(labels)
            + "</g>"
        )
    first = _pin_one(pads)
    bounds = list(cast(list[int], scene["bounds"]))
    if first is not None:
        w, h = int(first.get("w") or 0) // 1000, int(first.get("h") or 0) // 1000
        # A rounded outline a little outside pad 1, whatever its shape (a circle would swell on long pads).
        gap, stroke = max(min(w, h) // 6, 60), max(min(w, h) // 12, 40)
        x, y = int(first["x"]), int(first["y"])
        half_w, half_h = w // 2 + gap, h // 2 + gap
        body.append(
            f'<rect class="pin1" x="{x - half_w}" y="{y - half_h}" '
            f'width="{2 * half_w}" height="{2 * half_h}" rx="{min(half_w, half_h) // 2}" fill="none" '
            f'stroke="{PIN1_COLOUR}" stroke-width="{stroke}"/>'
        )
        bounds = [min(bounds[0], x - half_w - stroke), min(bounds[1], y - half_h - stroke),
                  max(bounds[2], x + half_w + stroke), max(bounds[3], y + half_h + stroke)]  # fmt: skip
    return _svg(_box(bounds, 0.08), BOARD, f"Footprint {definition.lib_id}, pin 1 outlined", body)


# ---- facts ----------------------------------------------------------------------------------------


def mm(value_um: float) -> str:
    """A length in micrometres as millimetres with two decimals."""
    return f"{value_um / 1000:.2f} mm"


def symbol_media(definition: SymbolDef, scene: Mapping[str, Any]) -> Media:
    units = max(definition.unit_count, 1)
    facts = [("Pins", str(len(definition.pins))), ("Units", str(units))]
    if reference := definition.properties.get("Reference"):
        facts.append(("Reference", reference))
    rows = tuple(
        (pin.number, pin.name, str(pin.etype))
        for pin in sorted(definition.pins, key=lambda p: (len(p.number), p.number, p.name))
    )
    return Media(
        views=(View("symbol.svg", "symbol", symbol_svg(definition, scene)),),
        facts=tuple(facts),
        table=(("Pin", "Name", "Type"), rows),
    )


def footprint_media(definition: FootprintDef, scene: Mapping[str, Any]) -> Media:
    kinds: dict[str, int] = {}
    for pad in definition.pads:
        kinds[pad.kind] = kinds.get(pad.kind, 0) + 1
    x0, y0, x1, y1 = cast(list[int], scene["bounds"])
    facts = [
        ("Package", definition.name),
        ("Pads", str(len(definition.pads))),
        ("Pad kinds", ", ".join(f"{count} {kind}" for kind, count in sorted(kinds.items())) or "none"),
        ("Extent", f"{mm(x1 - x0)} × {mm(y1 - y0)}"),
    ]
    if definition.description:
        facts.append(("Description", definition.description))
    return Media(
        views=(View("footprint.svg", "footprint, pin 1 outlined", footprint_svg(definition, scene)),),
        facts=tuple(facts),
    )


__all__ = [
    "Media",
    "View",
    "footprint_media",
    "footprint_svg",
    "mm",
    "symbol_media",
    "symbol_svg",
]
