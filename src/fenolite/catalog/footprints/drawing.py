# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The versioned drawing conventions of the generators (change c0260, decisions 10 and 11).

``drawing/0`` is the 0.6 catalog: a fabrication rectangle of the nominal body (100 µm), a courtyard
symmetric about the origin, the 0.6 pin-1 and cathode lines, rectangular surface pads, round
through-hole pads, no silkscreen and no model. ``drawing/1`` adds a chamfered fabrication outline,
silkscreen kept clear of copper, a pin-1 mark, polarity bars, rounded surface pads, a square pad 1 for
through-hole parts and a grid-rounded courtyard. A released convention never changes; its constants are
published in ``docs/formats/library/lands.md`` ("Drawing conventions"), labelled ``INFERRED``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.catalog.footprints._draft import Box, Draft, PadSpec
from fenolite.catalog.footprints.lands import LandTable, ceil_to, corner_ratio, floor_to
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.model.board import Graphic, Pad

DRAWINGS = (0, 1)
"""The released drawing conventions."""
NAMESPACE = "fenolite.catalog"
"""The namespace of the ids of generated pads, graphics and footprints (the 0.6 catalog's)."""

DRAWING_1: Mapping[str, int] = MappingProxyType(
    {
        "fab_width": 100_000,
        "fab_chamfer_max": 1_000_000,
        "courtyard_width": 50_000,
        "silk_width": 125_000,
        "silk_copper_gap": 175_000,
        "silk_min_piece": 250_000,
        "pin1_dot_radius": 150_000,
        "corner_mark_max": 1_000_000,
        "corner_ratio_ppm": 200_000,
        "corner_radius_max": 100_000,
    }
)
"""The constants of ``drawing/1`` (``lands.md``, "Drawing conventions"). The chamfer and the corner mark are
``min(max, short side / 4)``; the fabrication polarity bar lies one fifth of the body length from the pad-1
end."""

_FAB0 = 100_000
_CRTYD0 = 50_000


@dataclass(frozen=True, slots=True)
class Drawn:
    """The pads and graphics of a footprint, and its courtyard rectangle."""

    pads: tuple[Pad, ...]
    graphics: tuple[Graphic, ...]
    courtyard: Box


def _gid(key: str) -> str:
    return derived_id("gfx", NAMESPACE, key)


def _layers(spec: PadSpec) -> tuple[str, ...]:
    if spec.kind != "smd":
        return ("*.Cu", "*.Mask")
    return ("F.Cu", "F.Paste", "F.Mask") if spec.paste else ("F.Cu", "F.Mask")


def _pad(name: str, spec: PadSpec, drawing: int) -> Pad:
    corner: int | None = None
    if spec.kind == "np_thru_hole":
        shape = "circle"
    elif spec.kind == "thru_hole":
        if drawing >= 1 and spec.number == "1":
            shape = "rect"
        else:
            shape = "circle" if spec.w == spec.h else "oval"
    elif spec.round:
        shape = "circle"
    elif drawing >= 1:
        shape = "roundrect"
        corner = corner_ratio(min(spec.w, spec.h))
    else:
        shape = "rect"
    return Pad(
        id=derived_id("pad", NAMESPACE, f"{name}:{spec.key or spec.number}"),
        number=spec.number,
        shape=shape,  # type: ignore[arg-type]
        size=Size(spec.w, spec.h),
        position=Point(spec.x, spec.y),
        kind=spec.kind,
        drill=spec.drill,
        layers=_layers(spec),
        corner_ratio=corner,
    )


def _rect(gid: str, layer: str, box: Box, width: Nm) -> Graphic:
    return Graphic(
        id=gid, kind="rect", layer=layer, points=(Point(box.x0, box.y0), Point(box.x1, box.y1)), width=width
    )


def _line(gid: str, layer: str, a: tuple[Nm, Nm], b: tuple[Nm, Nm], width: Nm) -> Graphic:
    return Graphic(id=gid, kind="line", layer=layer, points=(Point(*a), Point(*b)), width=width)


def _extent(pads: Sequence[PadSpec], body: Box) -> Box:
    return Box(
        min(body.x0, *(p.x0 for p in pads)) if pads else body.x0,
        min(body.y0, *(p.y0 for p in pads)) if pads else body.y0,
        max(body.x1, *(p.x1 for p in pads)) if pads else body.x1,
        max(body.y1, *(p.y1 for p in pads)) if pads else body.y1,
    )


# --- drawing/0 ------------------------------------------------------------------------------------------


def draw0(name: str, draft: Draft, table: LandTable | None) -> Drawn:
    """The 0.6 drawing: the rules of ``_make_footprint``, ``_pin1_index`` and the paste grid."""
    body = draft.body or Box(0, 0, 0, 0)
    excess = table.courtyard if table is not None else 500_000
    pads = tuple(_pad(name, spec, 0) for spec in draft.pads)
    body_x, body_y = body.x1 - body.x0, body.y1 - body.y0
    centre_y = (body.y0 + body.y1) // 2
    extent_x = max((body_x // 2, *(abs(p.x) + p.w // 2 for p in draft.pads)))
    extent_y = max((abs(centre_y) + body_y // 2, *(abs(p.y) + p.h // 2 for p in draft.pads)))
    fab = _rect(_gid(f"{name}:F.Fab"), "F.Fab", body, _FAB0)
    if centre_y:
        lower = min((body.y0, *(p.y0 for p in draft.pads))) - excess
        upper = max((body.y1, *(p.y1 for p in draft.pads))) + excess
        court = Box(-extent_x - excess, lower, extent_x + excess, upper)
    else:
        court = Box(-extent_x - excess, -extent_y - excess, extent_x + excess, extent_y + excess)
    graphics = [fab, _rect(_gid(f"{name}:F.CrtYd"), "F.CrtYd", court, _CRTYD0)]
    if draft.cathode0:
        x = body.x0 + draft.cathode_inset0 if draft.cathode0 == "left" else body.x1 - draft.cathode_inset0
        graphics.append(
            _line(_gid(f"{name}:cathode"), "F.Fab", (x, body.y0 + 150_000), (x, body.y1 - 150_000), _FAB0)
        )
    if draft.pin1_index0:
        graphics.append(
            _line(
                _gid(f"{name}:pin1"),
                "F.Fab",
                (body.x0, body.y1 - 400_000),
                (body.x0 + 400_000, body.y1),
                _FAB0,
            )
        )
    graphics += _paste(name, draft, key_base=name)
    return Drawn(pads, tuple(graphics), court)


def _paste(name: str, draft: Draft, *, key_base: str) -> list[Graphic]:
    return [
        Graphic(
            id=_gid(f"{key_base}:paste:{w.index}"),
            kind="rect",
            layer="F.Paste",
            points=(Point(w.x - w.w // 2, w.y - w.h // 2), Point(w.x + w.w // 2, w.y + w.h // 2)),
            width=0,
            filled=True,
        )
        for w in draft.paste
    ]


# --- drawing/1 ------------------------------------------------------------------------------------------


def _keepouts(pads: Sequence[PadSpec], margin: Nm) -> list[Box]:
    return [Box(p.x0 - margin, p.y0 - margin, p.x1 + margin, p.y1 + margin) for p in pads]


def _cut(
    segment: tuple[tuple[Nm, Nm], tuple[Nm, Nm]], keepouts: Sequence[Box], min_piece: Nm
) -> list[tuple[tuple[Nm, Nm], tuple[Nm, Nm]]]:
    """The pieces of an axis-aligned segment outside every keep-out box, each at least ``min_piece`` long."""
    (ax, ay), (bx, by) = segment
    horizontal = ay == by
    if horizontal:
        fixed, low, high = ay, min(ax, bx), max(ax, bx)
    else:
        fixed, low, high = ax, min(ay, by), max(ay, by)
    pieces = [(low, high)]
    for box in keepouts:
        across = (box.y0, box.y1) if horizontal else (box.x0, box.x1)
        along = (box.x0, box.x1) if horizontal else (box.y0, box.y1)
        if not across[0] < fixed < across[1]:
            continue
        next_pieces: list[tuple[Nm, Nm]] = []
        for start, end in pieces:
            if along[1] <= start or along[0] >= end:
                next_pieces.append((start, end))
                continue
            if along[0] > start:
                next_pieces.append((start, along[0]))
            if along[1] < end:
                next_pieces.append((along[1], end))
        pieces = next_pieces
    kept = [(s, e) for s, e in pieces if e - s >= min_piece]
    if horizontal:
        return [((s, fixed), (e, fixed)) for s, e in kept]
    return [((fixed, s), (fixed, e)) for s, e in kept]


def _clear_of(x: Nm, y: Nm, radius: Nm, pads: Sequence[PadSpec], gap: Nm) -> bool:
    """Whether a disc of ``radius`` at ``(x, y)`` keeps ``gap`` from every pad rectangle (exact)."""
    for p in pads:
        dx = max(p.x0 - x, 0, x - p.x1)
        dy = max(p.y0 - y, 0, y - p.y1)
        if dx * dx + dy * dy < (radius + gap) ** 2:
            return False
    return True


def draw1(name: str, lib_id: str, draft: Draft, table: LandTable) -> Drawn:
    """The ``drawing/1`` footprint graphics and pads."""
    c = DRAWING_1
    body = draft.body or Box(0, 0, 0, 0)
    pads = tuple(_pad(name, spec, 1) for spec in draft.pads)
    graphics: list[Graphic] = []
    short = min(body.x1 - body.x0, body.y1 - body.y0)
    # Fabrication outline, chamfered at the pin-1 corner (top left) of a multi-pin package.
    chamfer = 0 if draft.two_terminal else min(c["fab_chamfer_max"], short // 4)
    corners = [
        (body.x0 + chamfer, body.y0),
        (body.x1, body.y0),
        (body.x1, body.y1),
        (body.x0, body.y1),
        (body.x0, body.y0 + chamfer),
    ]
    if chamfer == 0:
        corners = corners[:4]
    for i, a in enumerate(corners):
        b = corners[(i + 1) % len(corners)]
        graphics.append(_line(_gid(f"{lib_id}:fab:{i}"), "F.Fab", a, b, c["fab_width"]))
    if draft.polarized:
        x = body.x0 + (body.x1 - body.x0) // 5
        graphics.append(
            _line(_gid(f"{lib_id}:fab:polarity"), "F.Fab", (x, body.y0), (x, body.y1), c["fab_width"])
        )
    # Silkscreen: the body outline, cut clear of copper.
    width = c["silk_width"]
    margin = c["silk_copper_gap"] + width // 2
    keepouts = _keepouts(draft.pads, margin)
    outline = [
        ((body.x0, body.y0), (body.x1, body.y0)),
        ((body.x1, body.y0), (body.x1, body.y1)),
        ((body.x1, body.y1), (body.x0, body.y1)),
        ((body.x0, body.y1), (body.x0, body.y0)),
    ]
    silk: list[tuple[str, tuple[tuple[Nm, Nm], tuple[Nm, Nm]]]] = []
    for side, segment in enumerate(outline):
        for k, piece in enumerate(_cut(segment, keepouts, c["silk_min_piece"])):
            silk.append((f"silk:{side}:{k}", piece))
    pad1 = next((p for p in draft.pads if p.number == "1"), None)
    if draft.pin1 == "corner":
        arm = min(c["corner_mark_max"], short // 4)
        off = margin
        x0, y0 = body.x0 - off, body.y0 - off
        for role, segment in (("pin1:h", ((x0, y0), (x0 + arm, y0))), ("pin1:v", ((x0, y0), (x0, y0 + arm)))):
            for k, piece in enumerate(_cut(segment, keepouts, c["silk_min_piece"])):
                silk.append((f"{role}:{k}", piece))
    if draft.polarized and pad1 is not None:
        x = pad1.x0 - margin
        for k, piece in enumerate(_cut(((x, pad1.y0), (x, pad1.y1)), keepouts, c["silk_min_piece"])):
            silk.append((f"polarity:{k}", piece))
    for role, (a, b) in silk:
        graphics.append(_line(_gid(f"{lib_id}:{role}"), "F.SilkS", a, b, width))
    if draft.pin1 == "dot" and pad1 is not None:
        radius = c["pin1_dot_radius"]
        x = min(pad1.x0 - c["silk_copper_gap"], body.x0 - margin) - radius
        while not _clear_of(x, pad1.y, radius, draft.pads, c["silk_copper_gap"]):
            x -= table.grid
        # A disc drawn as a circle of half the radius with a stroke of the radius: no filled shape.
        graphics.append(
            Graphic(
                id=_gid(f"{lib_id}:pin1"),
                kind="circle",
                layer="F.SilkS",
                points=(Point(x, pad1.y), Point(x + radius // 2, pad1.y)),
                width=radius,
            )
        )
    # Courtyard: everything plus the excess, rounded outward to the grid.
    extent = _extent(draft.pads, body)
    excess, grid = table.courtyard, table.grid
    court = Box(
        floor_to(extent.x0 - excess, grid),
        floor_to(extent.y0 - excess, grid),
        ceil_to(extent.x1 + excess, grid),
        ceil_to(extent.y1 + excess, grid),
    )
    graphics.append(_rect(_gid(f"{lib_id}:crtyd"), "F.CrtYd", court, c["courtyard_width"]))
    graphics += _paste(name, draft, key_base=lib_id)
    return Drawn(pads, tuple(graphics), court)


__all__ = ["DRAWINGS", "DRAWING_1", "NAMESPACE", "Drawn", "draw0", "draw1"]
