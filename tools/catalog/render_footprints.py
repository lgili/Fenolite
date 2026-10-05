# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Render Fenolite catalog geometry as a self-contained SVG review sheet."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

from fenolite.catalog import get_footprint, list_entries
from fenolite.model.board import Graphic, Pad

_CARD_W = 450
_CARD_H = 240


def _graphic_svg(graphic: Graphic, cx: float, cy: float, scale: float) -> str:
    color = {"F.CrtYd": "#16a34a", "F.Paste": "#64748b"}.get(graphic.layer, "#2563eb")
    dash = ' stroke-dasharray="5 4"' if graphic.layer == "F.CrtYd" else ""
    if graphic.kind == "rect":
        a, b = graphic.points
        x = cx + a.x / 1_000_000 * scale
        y = cy - b.y / 1_000_000 * scale
        width = (b.x - a.x) / 1_000_000 * scale
        height = (b.y - a.y) / 1_000_000 * scale
        return (
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
            f'fill="{color if graphic.filled else "none"}" stroke="{color}" '
            f'stroke-width="{0 if graphic.filled else 1.5}"{dash}/>'
        )
    if graphic.kind == "circle":
        center, edge = graphic.points
        radius = ((edge.x - center.x) ** 2 + (edge.y - center.y) ** 2) ** 0.5 / 1_000_000 * scale
        return (
            f'<circle cx="{cx + center.x / 1_000_000 * scale:.2f}" '
            f'cy="{cy - center.y / 1_000_000 * scale:.2f}" r="{radius:.2f}" '
            f'fill="none" stroke="{color}" stroke-width="1.5"/>'
        )
    if graphic.kind == "line":
        a, b = graphic.points
        return (
            f'<line x1="{cx + a.x / 1_000_000 * scale:.2f}" '
            f'y1="{cy - a.y / 1_000_000 * scale:.2f}" '
            f'x2="{cx + b.x / 1_000_000 * scale:.2f}" '
            f'y2="{cy - b.y / 1_000_000 * scale:.2f}" '
            f'stroke="{color}" stroke-width="2"{dash}/>'
        )
    return ""


def _pad_svg(pad: Pad, cx: float, cy: float, scale: float) -> str:
    x = cx + (pad.position.x - pad.size.w // 2) / 1_000_000 * scale
    y = cy - (pad.position.y + pad.size.h // 2) / 1_000_000 * scale
    width = pad.size.w / 1_000_000 * scale
    height = pad.size.h / 1_000_000 * scale
    color = "white" if pad.kind == "np_thru_hole" else "#f59e0b"
    if pad.shape == "circle":
        body = (
            f'<ellipse cx="{x + width / 2:.2f}" cy="{y + height / 2:.2f}" '
            f'rx="{width / 2:.2f}" ry="{height / 2:.2f}" fill="{color}" stroke="#b45309"/>'
        )
    else:
        radius = min(width, height) / 2 if pad.shape == "oval" else 0
        body = (
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
            f'rx="{radius:.2f}" fill="{color}" stroke="#b45309"/>'
        )
    if pad.drill is not None:
        drill_w = drill_h = pad.drill / 1_000_000 * scale
        if pad.padstack and pad.padstack.hole_length is not None:
            if pad.padstack.hole_rotation % 180_000_000 == 90_000_000:
                drill_h = pad.padstack.hole_length / 1_000_000 * scale
            else:
                drill_w = pad.padstack.hole_length / 1_000_000 * scale
        body += (
            f'<rect x="{x + (width - drill_w) / 2:.2f}" y="{y + (height - drill_h) / 2:.2f}" '
            f'width="{drill_w:.2f}" height="{drill_h:.2f}" rx="{min(drill_w, drill_h) / 2:.2f}" '
            'fill="white" stroke="#b45309"/>'
        )
    font_size = min(12, min(width, height) * 0.85, width / max(1, len(pad.number)) * 1.4)
    return body + (
        f'<text x="{x + width / 2:.2f}" y="{y + height / 2 + font_size / 3:.2f}" '
        f'text-anchor="middle" font-family="Arial" font-size="{font_size:.2f}" font-weight="bold" '
        f'fill="#1e293b">{escape(pad.number)}</text>'
    )


def render(names: tuple[str, ...]) -> str:
    """Render the requested exact catalog names; no external CAD library is read."""
    rows = (len(names) + 1) // 2
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{rows * _CARD_H}" '
        f'viewBox="0 0 900 {rows * _CARD_H}">',
        f'<rect width="900" height="{rows * _CARD_H}" fill="#f8fafc"/>',
    ]
    for index, name in enumerate(names):
        fp = get_footprint(f"Fenolite:{name}")
        ox = index % 2 * _CARD_W
        oy = index // 2 * _CARD_H
        cx, cy = ox + _CARD_W / 2, oy + 145
        court = fp.graphics_on("F.CrtYd")[0]
        lower, upper = court.points
        width = (upper.x - lower.x) / 1_000_000
        height = (upper.y - lower.y) / 1_000_000
        scale = min(55, 360 / width, 130 / height)
        cx -= (lower.x + upper.x) / 2_000_000 * scale
        cy += (lower.y + upper.y) / 2_000_000 * scale
        title_size = min(16, 400 / (0.62 * len(name)))
        parts.append(
            f'<rect x="{ox + 10}" y="{oy + 10}" width="430" height="220" rx="12" '
            'fill="white" stroke="#cbd5e1"/>'
        )
        parts.append(
            f'<text x="{ox + 24}" y="{oy + 36}" font-family="Arial" font-size="{title_size:.2f}" '
            f'fill="#0f172a">{escape(name)}</text>'
        )
        parts.extend(
            _graphic_svg(graphic, cx, cy, scale) for graphic in fp.graphics if graphic.layer != "F.Paste"
        )
        parts.extend(_pad_svg(pad, cx, cy, scale) for pad in fp.pads)
        parts.extend(_graphic_svg(graphic, cx, cy, scale) for graphic in fp.graphics_on("F.Paste"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("names", nargs="*")
    parser.add_argument(
        "--page-size",
        type=int,
        default=0,
        help="also write numbered review sheets with this many patterns per page",
    )
    args = parser.parse_args()
    if args.page_size < 0:
        parser.error("--page-size must be non-negative")
    names = tuple(args.names) or tuple(
        entry.lib_id.removeprefix("Fenolite:") for entry in list_entries(kind="footprint")
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(names), encoding="utf-8")
    if args.page_size:
        for index, offset in enumerate(range(0, len(names), args.page_size), start=1):
            page = args.output.with_stem(f"{args.output.stem}-page{index}")
            page.write_text(render(names[offset : offset + args.page_size]), encoding="utf-8")


if __name__ == "__main__":
    main()
