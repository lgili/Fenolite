# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``gullwing`` family: SOIC, SSOP, TSSOP, MSOP, QFP and SOT (change c0260, decision 2).

The body ``length`` lies along the pin rows (y), ``width`` across them (x). ``dual`` and ``sides`` put the
rows left and right; ``quad`` adds rows at the top and bottom (``span_x`` across the left and right rows,
``span_y`` across the top and bottom ones). A pitch below 0.65 mm uses the land class ``gullwing-fine``."""

from __future__ import annotations

from fenolite.catalog.footprints._draft import (
    Box,
    Context,
    Draft,
    PadSpec,
    dual_rows,
    length_of,
    nominal,
    quad_rows,
    record_rows,
    rows_land,
)
from fenolite.catalog.footprints.lands import FINE_PITCH, RowLand, ceil_to
from fenolite.core.errors import FormatError
from fenolite.core.quantities import LengthRange
from fenolite.core.units import Nm


def land_class(pitch: Nm) -> str:
    """``gullwing-fine`` below 0.65 mm pitch, else ``gullwing``."""
    return "gullwing-fine" if pitch < FINE_PITCH else "gullwing"


def _span_outside(ctx: Context, key: str, span: LengthRange, body: LengthRange, body_key: str) -> None:
    if span.max is not None and body.min is not None and span.max <= body.min:
        raise ctx.error(
            "package.dimensions-inconsistent",
            f"{key} (max {span.max} nm) is not larger than {body_key} (min {body.min} nm)",
            key,
        )


def _row_fits(ctx: Context, count: int, pitch: Nm, body: LengthRange, body_key: str) -> None:
    if body.max is not None and pitch * (count - 1) > body.max:
        raise ctx.error(
            "package.dimensions-inconsistent",
            f"a row of {count} pins at {pitch} nm pitch is longer than {body_key} (max {body.max} nm)",
            "pitch",
        )


def draw_gullwing(ctx: Context) -> Draft:
    pkg = ctx.package
    keys = pkg.keys
    pins = keys.count("pins") or 0
    pitch = nominal(ctx, "pitch", keys.length("pitch"))
    arrangement = keys.text("arrangement")
    body = keys.table("body")
    lead = keys.table("lead")
    assert body is not None and lead is not None
    body_length = length_of(ctx, "body.length", body.length("length"))
    body_width = length_of(ctx, "body.width", body.length("width"))
    lead_length = ("lead.length", length_of(ctx, "lead.length", lead.length("length")))
    lead_width = ("lead.width", length_of(ctx, "lead.width", lead.length("width")))
    cls = land_class(pitch)
    drawing = pkg.drawing
    draft = Draft(
        body=Box.centred(nominal(ctx, "body.width", body_width), nominal(ctx, "body.length", body_length)),
        pin1="dot",
    )
    if arrangement == "quad":
        if pins % 4:
            raise ctx.error("package.pin-count", f"{pins} pins cannot fill four equal rows", "pins")
        span_x = length_of(ctx, "span_x", keys.length("span_x"))
        span_y = length_of(ctx, "span_y", keys.length("span_y"))
        _span_outside(ctx, "span_x", span_x, body_width, "body.width")
        _span_outside(ctx, "span_y", span_y, body_length, "body.length")
        _row_fits(ctx, pins // 4, pitch, body_length, "body.length")
        _row_fits(ctx, pins // 4, pitch, body_width, "body.width")
        land_x = rows_land(
            ctx,
            cls,
            ("span_x", span_x),
            lead_length,
            lead_width,
            spacing_key="row_spacing_x",
            pitch=pitch,
            axis="x",
        )
        land_y = rows_land(
            ctx,
            cls,
            ("span_y", span_y),
            lead_length,
            lead_width,
            spacing_key="row_spacing_y",
            pitch=pitch,
            axis="y",
        )
        record_rows(ctx, land_x)
        if not ctx.manufacturer:
            land_x, land_y = _corner_clip(ctx, pins // 4, pitch, land_x, land_y)
        draft.pads = quad_rows(
            pins,
            pitch,
            land_x.spacing,
            land_y.spacing,
            (land_x.length, land_x.x),
            (land_y.length, land_y.x),
            drawing=drawing,
        )
        draft.pin1_index0 = True
        return draft
    span = length_of(ctx, "span", keys.length("span"))
    _span_outside(ctx, "span", span, body_width, "body.width")
    land = rows_land(ctx, cls, ("span", span), lead_length, lead_width, pitch=pitch)
    record_rows(ctx, land)
    if arrangement == "dual":
        if pins % 2:
            raise ctx.error("package.pin-count", f"{pins} pins cannot fill two equal rows", "pins")
        if keys.has("side") or keys.has("tab"):
            key = "side" if keys.has("side") else "tab"
            raise ctx.error("package.pin-count", f"{key} is for the arrangement 'sides'", key)
        _row_fits(ctx, pins // 2, pitch, body_length, "body.length")
        draft.pads = dual_rows(pins, pitch, land.spacing, land.length, land.x, drawing=drawing)
        return draft
    draft.pads = _sides(ctx, pins, pitch, land, body_length, drawing)
    return draft


def _sides(
    ctx: Context, pins: int, pitch: Nm, land: RowLand, body_length: LengthRange, drawing: int
) -> list[PadSpec]:
    keys = ctx.package.keys
    sides = keys.tables("side")
    if not sides:
        raise ctx.error("package.pin-count", "the arrangement 'sides' needs [[side]] tables", "side")
    tab = keys.table("tab")
    numbers = [n for side in sides for n in side.texts("numbers")]
    if len(numbers) + (1 if tab is not None else 0) != pins:
        raise ctx.error(
            "package.pin-count",
            f"pins is {pins}, the sides give {len(numbers)} lead(s){' and a tab' if tab is not None else ''}",
            "pins",
        )
    if len(set(numbers)) != len(numbers) or (tab is not None and tab.text("number") in numbers):
        raise ctx.error("package.pin-count", "a pin number is given twice", "side")
    slots = max(p for side in sides for p in side.counts("positions")) + 1
    _row_fits(ctx, slots, pitch, body_length, "body.length")
    pads: list[PadSpec] = []
    used: set[tuple[str, int]] = set()
    for index, side in enumerate(sides):
        edge = side.text("edge") or "left"
        names, positions = side.texts("numbers"), side.counts("positions")
        if len(names) != len(positions):
            raise ctx.error(
                "package.pin-count", "a side gives as many numbers as positions", f"side[{index}]"
            )
        x = -land.spacing // 2 if edge == "left" else land.spacing // 2
        for number, position in zip(names, positions, strict=True):
            if (edge, position) in used:
                raise ctx.error(
                    "package.dimensions-inconsistent",
                    f"two pins at position {position} on the {edge}",
                    "side",
                )
            used.add((edge, position))
            y = (2 * position - slots + 1) * pitch // 2
            pads.append(PadSpec(number, x, -y if drawing == 0 else y, land.length, land.x))
    if tab is not None:
        pads.append(_tab(ctx, land))
    return pads


def _tab(ctx: Context, leads: RowLand) -> PadSpec:
    """The tab land on its edge: the manufacturer's ``[land].tab``, else the class ``smd-tab`` on the span."""
    keys = ctx.package.keys
    tab = keys.table("tab")
    assert tab is not None
    edge = tab.text("edge") or "right"
    number = tab.text("number") or ""
    land = ctx.package.land
    if land is not None:
        given = land.table("tab")
        if given is None:
            raise FormatError("missing required key 'land.tab'", file=ctx.package.file, locator="land.tab")
        length = nominal(ctx, "land.tab.length", given.length("length"))
        width = nominal(ctx, "land.tab.width", given.length("width"))
        at = nominal(ctx, "land.tab.at", given.length("at"))
        return PadSpec(number, at if edge == "right" else -at, 0, length, width, key="tab")
    span = length_of(ctx, "span", keys.length("span"))
    tab_land = rows_land(
        ctx,
        "smd-tab",
        ("span", span),
        ("tab.length", length_of(ctx, "tab.length", tab.length("length"))),
        ("tab.width", length_of(ctx, "tab.width", tab.length("width"))),
    )
    del leads
    x = tab_land.spacing // 2
    return PadSpec(number, x if edge == "right" else -x, 0, tab_land.length, tab_land.x, key="tab")


def _corner_clip(
    ctx: Context, per_side: int, pitch: Nm, land_x: RowLand, land_y: RowLand
) -> tuple[RowLand, RowLand]:
    """Shorten calculated quad lands from their inner end so that corner lands of perpendicular rows keep
    ``pad_gap`` (decision 4)."""
    table = ctx.require_table()
    gap, grid = table.pad_gap, table.grid
    reach_y = (per_side - 1) * pitch // 2 + land_y.x // 2  # x reach of the top and bottom lands
    reach_x = (per_side - 1) * pitch // 2 + land_x.x // 2  # y reach of the left and right lands

    def clear(lx: RowLand, ly: RowLand) -> bool:
        # The upper land of the left row (inner edge at x = -G_x / 2, top at y = -reach_x) against the left
        # land of the top row (left edge at x = -reach_y, inner edge at y = -G_y / 2).
        dx = max(0, lx.g // 2 - reach_y)
        dy = max(0, ly.g // 2 - reach_x)
        return dx * dx + dy * dy >= gap * gap

    if clear(land_x, land_y):
        return land_x, land_y
    clipped: list[str] = []
    if land_x.g // 2 < reach_y + gap:
        land_x = _shorten(land_x, ceil_to(reach_y + gap, grid))
        clipped.append("left and right")
    if not clear(land_x, land_y) and land_y.g // 2 < reach_x + gap:
        land_y = _shorten(land_y, ceil_to(reach_x + gap, grid))
        clipped.append("top and bottom")
    if land_x.length <= 0 or land_y.length <= 0:
        raise ctx.error("package.land-impossible", "corner lands cannot keep the pad gap", "span")
    ctx.warn(
        "package.pads-clipped",
        f"the {' and '.join(clipped)} lands were shortened from their inner end to keep the pad gap of "
        f"{gap} nm at the corners; the heel goal is lost",
        "lead.length",
    )
    return land_x, land_y


def _shorten(land: RowLand, inner_half: Nm) -> RowLand:
    """``land`` with its inner gap widened to ``2 * inner_half``; the outer extent is kept."""
    return RowLand(land.z, 2 * inner_half, land.x)


__all__ = ["draw_gullwing", "land_class"]
