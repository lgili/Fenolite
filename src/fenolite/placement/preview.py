# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Integer SVG copper views queried from written/read-back board geometry (c0096)."""

from __future__ import annotations

from html import escape
from typing import Literal

from fenolite.backends.base import BoardFrame
from fenolite.core.coords import Point
from fenolite.geometry import BBox
from fenolite.model.design import Design


def _points(points: tuple[Point, ...]) -> str:
    return " ".join(f"{p.x},{p.y}" for p in points)


def _half(value: int) -> str:
    return str(value // 2) + (".5" if value % 2 else "")


def placement_preview(
    design: Design, frame: BoardFrame, *, face: Literal["top", "bottom"], envelopes: bool = False
) -> str:
    """Outside view; bottom mirrors the entire board once, after the backend supplied copper positions."""
    if face not in ("top", "bottom") or design.board is None or design.board.outline is None:
        raise ValueError("preview needs a board outline and a top/bottom face")
    board = design.board
    assert board.outline is not None
    box = BBox.of_points(board.outline.points)
    pad = max(1, max(box.width, box.height) // 30)
    viewport = box.inflate(pad)
    stroke = max(1, max(box.width, box.height) // 500)
    layer = "F.Cu" if face == "top" else "B.Cu"
    convention = (
        "top outside view; X right, Y down"
        if face == "top"
        else "bottom outside view; board mirrored once about its vertical centre"
    )
    note = (
        "; conservative extent overlay, review only"
        if envelopes
        else "; actual queried pad copper, review only"
    )
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewport.x0} {viewport.y0} '
        f'{viewport.width} {viewport.height}" width="1000" height="750">',
        f"<title>{escape(convention + note)}</title>",
        f"<metadata>source=queried board-frame geometry; layer={layer}; "
        "no manufacturing or native acceptance claim</metadata>",
        '<rect x="'
        + str(viewport.x0)
        + '" y="'
        + str(viewport.y0)
        + '" width="'
        + str(viewport.width)
        + '" height="'
        + str(viewport.height)
        + '" fill="#f5f3ec"/>',
    ]
    transform = f"translate({box.x0 + box.x1} 0) scale(-1 1)" if face == "bottom" else "translate(0 0)"
    rows.append(f'<g data-face="{face}" transform="{transform}">')
    path = " ".join(
        "M " + " L ".join(f"{p.x} {p.y}" for p in ring) + " Z"
        for ring in (board.outline.points, *board.outline.cutouts)
    )
    rows.append(
        f'<path d="{path}" fill="#dce8dd" fill-rule="evenodd" stroke="#45574a" stroke-width="{stroke}"/>'
    )
    for keepout in sorted(board.keepouts, key=lambda k: k.id):
        if not keepout.layers or layer in keepout.layers:
            rows.append(
                f'<polygon data-keepout="{escape(keepout.id, quote=True)}" '
                f'points="{_points(keepout.outline)}" fill="#eebc9d" opacity="0.5"/>'
            )
    pads = frame.board_pads(design)
    for entry_pad in sorted(pads, key=lambda p: (p.footprint_id, p.pad_id)):
        for index, copper in enumerate(entry_pad.copper):
            if copper.layer != layer:
                continue
            attr = (
                f'data-pad="{escape(entry_pad.pad_id, quote=True)}" '
                f'data-number="{escape(entry_pad.number, quote=True)}" '
                f'data-exact="{str(copper.exact).lower()}" '
                f'data-centre="{entry_pad.position.x},{entry_pad.position.y}" data-entry="{index}"'
            )
            if len(copper.core) == 1:
                p = copper.core[0]
                rows.append(
                    f'<circle {attr} cx="{p.x}" cy="{p.y}" r="{_half(copper.width)}" fill="#b16b29"/>'
                )
            else:
                tag = "polygon" if copper.filled else "polyline"
                fill = "#b16b29" if copper.filled else "none"
                rows.append(
                    f'<{tag} {attr} points="{_points(copper.core)}" fill="{fill}" stroke="#b16b29" '
                    f'stroke-width="{copper.width}" stroke-linejoin="round" stroke-linecap="round"/>'
                )
        if entry_pad.hole and entry_pad.drill:
            if len(entry_pad.hole) == 1:
                p = entry_pad.hole[0]
                rows.append(
                    f'<circle data-drill="{escape(entry_pad.pad_id, quote=True)}" cx="{p.x}" cy="{p.y}" '
                    f'r="{_half(entry_pad.drill)}" fill="#f5f3ec"/>'
                )
            else:
                rows.append(
                    f'<polyline data-drill="{escape(entry_pad.pad_id, quote=True)}" '
                    f'points="{_points(entry_pad.hole)}" fill="none" stroke="#f5f3ec" '
                    f'stroke-width="{entry_pad.drill}" stroke-linecap="round"/>'
                )
    for hole in sorted(board.holes, key=lambda h: h.id):
        rows.append(
            f'<circle data-hole="{escape(hole.id, quote=True)}" '
            f'cx="{hole.position.x}" cy="{hole.position.y}" '
            f'r="{_half(hole.drill)}" fill="#f5f3ec" stroke="#45574a" stroke-width="{stroke}"/>'
        )
    for fp in sorted(board.footprints, key=lambda f: f.id):
        if fp.locked:
            rows.append(
                f'<path data-lock="{escape(fp.id, quote=True)}" d="M {fp.position.x - pad} {fp.position.y} '
                f'h {2 * pad} M {fp.position.x} {fp.position.y - pad} v {2 * pad}" '
                f'stroke="#9d283c" stroke-width="{stroke}"/>'
            )
    if envelopes:
        for extent in frame.placed_extents(design):
            for ring in extent.front if face == "top" else extent.back:
                rows.append(
                    f'<polygon data-envelope="{escape(extent.footprint_id, quote=True)}" '
                    f'data-conservative="{str(not extent.exact).lower()}" points="{_points(ring)}" '
                    f'fill="none" stroke="#4657a8" stroke-width="{stroke}" stroke-dasharray="{pad} {pad}"/>'
                )
    rows.extend(("</g>", "</svg>"))
    return "\n".join(rows) + "\n"


__all__ = ["placement_preview"]
