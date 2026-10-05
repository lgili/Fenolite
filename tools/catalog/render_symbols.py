# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Render actual catalog symbol geometry, including KiCad background fill, to SVG."""

from __future__ import annotations

import argparse
from html import escape
from math import isqrt
from pathlib import Path

from fenolite.catalog import get_symbol, list_entries
from fenolite.model.library import SymbolGraphic

_CARD_W = 450
_CARD_H = 300
_INK = "#182a40"


def _graphic_svg(graphic: SymbolGraphic, cx: float, cy: float, scale: float) -> str:
    def xy(x: int, y: int) -> tuple[float, float]:
        return cx + x / 1_000_000 * scale, cy - y / 1_000_000 * scale

    points = [xy(p.x, p.y) for p in graphic.points]
    width = (graphic.width or 254_000) / 1_000_000 * scale
    style = (
        f'fill="{"white" if graphic.filled else "none"}" stroke="{_INK}" '
        f'stroke-width="{width:.3f}" stroke-linejoin="round"'
    )
    if graphic.kind == "line":
        (ax, ay), (bx, by) = points
        return f'<line x1="{ax:.3f}" y1="{ay:.3f}" x2="{bx:.3f}" y2="{by:.3f}" {style}/>'
    if graphic.kind == "rect":
        (ax, ay), (bx, by) = points
        return (
            f'<rect x="{min(ax, bx):.3f}" y="{min(ay, by):.3f}" '
            f'width="{abs(bx - ax):.3f}" height="{abs(by - ay):.3f}" {style}/>'
        )
    if graphic.kind == "circle":
        a, b = graphic.points
        radius = isqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2) / 1_000_000 * scale
        return f'<circle cx="{points[0][0]:.3f}" cy="{points[0][1]:.3f}" r="{radius:.3f}" {style}/>'
    if graphic.kind == "polygon":
        coordinates = " ".join(f"{x:.3f},{y:.3f}" for x, y in points)
        return f'<polygon points="{coordinates}" {style}/>'
    raise ValueError(f"Unsupported symbol graphic: {graphic.kind}")


def render(names: tuple[str, ...]) -> str:
    """Render exact names using the offline catalog; no imported drawing templates."""
    height = (len(names) + 1) // 2 * _CARD_H
    items = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}">',
        '<rect width="100%" height="100%" fill="#f6f8fb"/>',
    ]
    for index, name in enumerate(names):
        symbol = get_symbol(f"Fenolite:{name}")
        ox, oy = index % 2 * _CARD_W, index // 2 * _CARD_H
        title_size = min(18, 395 / (0.6 * len(name)))
        items += [
            f'<rect x="{ox + 10}" y="{oy + 10}" width="430" height="280" '
            'rx="10" fill="white" stroke="#d7dce5"/>',
            f'<text x="{ox + 24}" y="{oy + 39}" font-family="Arial,sans-serif" '
            f'font-size="{title_size:.3f}" font-weight="bold" fill="#0f172a">{escape(name)}</text>',
        ]
        bounds = [(p.position.x, p.position.y) for p in symbol.pins]
        for graphic in symbol.graphics:
            if graphic.kind == "circle":
                center, edge = graphic.points
                radius = isqrt((edge.x - center.x) ** 2 + (edge.y - center.y) ** 2)
                bounds += [(center.x - radius, center.y - radius), (center.x + radius, center.y + radius)]
            else:
                bounds += [(p.x, p.y) for p in graphic.points]
        xmin, xmax = min(x for x, _ in bounds), max(x for x, _ in bounds)
        ymin, ymax = min(y for _, y in bounds), max(y for _, y in bounds)
        scale = min(24, 350 / ((xmax - xmin) / 1_000_000 + 4), 170 / ((ymax - ymin) / 1_000_000 + 4))
        cx = ox + 225 - (xmin + xmax) / 2_000_000 * scale
        cy = oy + 151 + (ymin + ymax) / 2_000_000 * scale
        for graphic in symbol.graphics:
            items.append(_graphic_svg(graphic, cx, cy, scale))
        for pin in symbol.pins:
            dx, dy = {0: (1, 0), 90_000_000: (0, 1), 180_000_000: (-1, 0), 270_000_000: (0, -1)}[pin.rotation]
            ax, ay = cx + pin.position.x / 1_000_000 * scale, cy - pin.position.y / 1_000_000 * scale
            bx, by = ax + dx * pin.length / 1_000_000 * scale, ay - dy * pin.length / 1_000_000 * scale
            items.append(
                f'<line x1="{ax:.3f}" y1="{ay:.3f}" x2="{bx:.3f}" y2="{by:.3f}" '
                f'stroke="{_INK}" stroke-width="{0.254 * scale:.3f}"/>'
            )
            # Roles are beside the stem rather than laid over the body motif.
            label = pin.number if symbol.pin_names_hidden else f"{pin.number} {pin.name}"
            if dx:
                tx, ty, anchor = ax - 5 * dx, ay - 8, "end" if dx > 0 else "start"
            else:
                peers = [
                    p.position.x
                    for p in symbol.pins
                    if p.position.y == pin.position.y and p.rotation == pin.rotation
                ]
                left = pin.position.x == min(peers) and (len(peers) > 1 or ax < cx)
                tx, ty, anchor = ax - 7 if left else ax + 7, (ay + by) / 2 + 4, "end" if left else "start"
            items.append(
                f'<text x="{tx:.3f}" y="{ty:.3f}" text-anchor="{anchor}" '
                f'font-family="Arial,sans-serif" font-size="12" fill="#52667c">{escape(label)}</text>'
            )
        roles = " · ".join(f"{p.number}={p.name}" for p in symbol.pins)
        font_size = min(12, 398 / max(1, 0.57 * len(roles)))
        items.append(
            f'<text x="{ox + 24}" y="{oy + 272}" font-family="Arial,sans-serif" '
            f'font-size="{font_size:.3f}" fill="#64748b">{escape(roles)}</text>'
        )
    return "\n".join([*items, "</svg>"]) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("names", nargs="*")
    parser.add_argument("--page-size", type=int, default=0)
    args = parser.parse_args()
    if args.page_size < 0:
        parser.error("--page-size must be non-negative")
    names = tuple(args.names) or tuple(
        e.lib_id.removeprefix("Fenolite:") for e in list_entries(kind="symbol")
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(names), encoding="utf-8")
    if args.page_size:
        for index, start in enumerate(range(0, len(names), args.page_size), 1):
            page = args.output.with_name(f"{args.output.stem}-page{index}.svg")
            page.write_text(render(names[start : start + args.page_size]), encoding="utf-8")


if __name__ == "__main__":
    main()
