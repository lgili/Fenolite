# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Standalone SVG of shared composition geometry; no external fonts, images or scripts."""

from __future__ import annotations

from html import escape

from fenolite.schematic.bounds import field_boxes, pin_stub
from fenolite.schematic.composition import CHAR_WIDTH, GRID, TEXT_HEIGHT, CompositionPlan, rotate


def svg(plan: CompositionPlan) -> bytes:
    def text(value: str, point: tuple[int, int], *, size: int = TEXT_HEIGHT) -> str:
        return f'<text x="{point[0]}" y="{point[1]}" font-size="{size}">{escape(value)}</text>'

    def line(points: tuple[tuple[int, int], ...], *, color: str = "#174b8c") -> str:
        coords = " ".join(f"{x},{y}" for x, y in points)
        return f'<polyline points="{coords}" fill="none" stroke="{color}"/>'

    width, height = plan.region.x1 + plan.region.x0, plan.region.y1 + plan.region.y0
    result = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        "<title>Generated baseline — native edits are represented by saved Altium documents</title>",
        f'<g font-family="sans-serif" fill="#174b8c" stroke-width="{GRID // 40}">',
    ]
    for reserved in plan.reserved:
        result.append(
            f'<rect x="{reserved.x0}" y="{reserved.y0}" width="{reserved.width}" '
            f'height="{reserved.height}" fill="#ddd" opacity="0.35"/>'
        )
    for block in plan.blocks:
        result.append(text(block.title, (block.bounds.x0, block.bounds.y0 + 2 * TEXT_HEIGHT)))
    for placement in sorted(plan.placements, key=lambda p: p.unit.key):
        unit, quarter = placement.unit, placement.rotation // 90_000_000
        ox, oy = placement.origin

        def at(point: tuple[int, int], quarter: int = quarter, ox: int = ox, oy: int = oy) -> tuple[int, int]:
            x, y = rotate(point, quarter)
            return ox + x, oy + y

        result.append(f'<g id="{escape(unit.key, quote=True)}"><title>{escape(unit.component)}</title>')
        for primitive in unit.primitives:
            points = tuple(at(p) for p in primitive.points)
            fill = "#fff1c0" if primitive.filled else "none"
            if primitive.kind == "ellipse":
                x, y = points[0]
                result.append(
                    f'<circle cx="{x}" cy="{y}" r="{primitive.radius}" fill="{fill}" stroke="#800000"/>'
                )
            elif primitive.kind == "rectangle":
                a, b = points
                result.append(
                    f'<rect x="{min(a[0], b[0])}" y="{min(a[1], b[1])}" '
                    f'width="{abs(b[0] - a[0])}" height="{abs(b[1] - a[1])}" '
                    f'fill="{fill}" stroke="#800000"/>'
                )
            elif primitive.kind == "polygon":
                coords = " ".join(f"{x},{y}" for x, y in points)
                result.append(f'<polygon points="{coords}" fill="{fill}" stroke="#800000"/>')
            else:
                result.append(line(points, color="#800000"))
        reference, value = field_boxes(unit, quarter)
        result.extend(
            (
                text(unit.ref, (ox + reference.x0, oy + reference.y1)),
                text(unit.value, (ox + value.x0, oy + value.y1)),
            )
        )
        for pin in unit.pins:
            if not pin.hidden:
                result.append(line((at(pin.body_at), at(pin.at)), color="#800000"))
            hx, hy = at(pin.at)
            if pin.number_shown and not pin.hidden:
                result.append(
                    text(pin.number, (hx + CHAR_WIDTH // 2, hy - TEXT_HEIGHT // 3), size=TEXT_HEIGHT // 2)
                )
            if not pin.hidden:
                result.append(text(pin.name, at(pin.body_at), size=TEXT_HEIGHT // 2))
            if pin.net is not None:
                start, end, mark = pin_stub(pin, quarter)
                result.append(line(((ox + start[0], oy + start[1]), (ox + end[0], oy + end[1]))))
                mx, my = ox + mark[0], oy + mark[1]
                if pin.power:
                    result.append(line(((mx - GRID // 2, my), (mx + GRID // 2, my))))
                    if pin.power_style == "ground":
                        result.append(
                            line(((mx - GRID // 3, my + GRID // 5), (mx + GRID // 3, my + GRID // 5)))
                        )
                        result.append(
                            line(((mx - GRID // 6, my + 2 * GRID // 5), (mx + GRID // 6, my + 2 * GRID // 5)))
                        )
                label = text(pin.net, (mx, my))
                if not pin.power and (pin.direction + quarter) % 2:
                    label = f'<g transform="rotate(-90 {mx} {my})">{label}</g>'
                result.append(label)
        result.append("</g>")
    for wire in plan.wires:
        result.append(line(wire.points))
    result.append("</g></svg>\n")
    return "\n".join(result).encode("utf-8")
