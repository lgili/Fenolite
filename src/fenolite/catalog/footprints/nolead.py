# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``nolead`` family: QFN, DFN and SON, with an exposed pad and its paste grid (change c0260,
decisions 2 and 8).

The body ``length`` lies along the pin rows (y), ``width`` across them (x). The span of the calculator is
the body across the rows, less twice the terminal ``pull_back``. The exposed pad is never enlarged: a
calculated signal land that comes closer to it than ``pad_gap`` is shortened from its inner end."""

from __future__ import annotations

from fenolite.catalog.footprints._draft import (
    Box,
    Context,
    Draft,
    PadSpec,
    PasteWindow,
    dual_rows,
    length_of,
    nominal,
    paste_grid,
    quad_rows,
    record_rows,
    rows_land,
)
from fenolite.catalog.footprints.lands import RowLand, ceil_to
from fenolite.catalog.footprints.record import Keys
from fenolite.core.quantities import LengthRange
from fenolite.core.units import Nm


def _span(body: LengthRange, pull_back: LengthRange) -> LengthRange:
    """The body less twice the pull-back, worst case: ``min - 2 pb.max``, ``max - 2 pb.min``."""
    low = None if body.min is None or pull_back.max is None else body.min - 2 * pull_back.max
    high = None if body.max is None or pull_back.min is None else body.max - 2 * pull_back.min
    if low is None and high is None:
        return body
    return LengthRange(low, None, high)


def draw_nolead(ctx: Context) -> Draft:
    pkg = ctx.package
    keys = pkg.keys
    pins = keys.count("pins") or 0
    pitch = nominal(ctx, "pitch", keys.length("pitch"))
    quad = keys.text("arrangement") == "quad"
    body = keys.table("body")
    terminal = keys.table("terminal")
    assert body is not None and terminal is not None
    body_length = length_of(ctx, "body.length", body.length("length"))
    body_width = length_of(ctx, "body.width", body.length("width"))
    t_length = length_of(ctx, "terminal.length", terminal.length("length"))
    t_width = length_of(ctx, "terminal.width", terminal.length("width"))
    pull_back = keys.length("pull_back") or LengthRange.exact(0)
    rows = 4 if quad else 2
    if pins % rows:
        raise ctx.error("package.pin-count", f"{pins} pins cannot fill {rows} equal rows", "pins")
    per_side = pins // rows
    for key, extent in (
        (("body.width", body_width), ("body.length", body_length)) if quad else (("body.width", body_width),)
    ):
        if t_length.max is not None and extent.min is not None and 2 * t_length.max >= extent.min:
            raise ctx.error(
                "package.dimensions-inconsistent",
                f"terminal.length (max {t_length.max} nm) is not shorter than "
                f"half of {key} (min {extent.min} nm)",
                "terminal.length",
            )
    for key, extent in (
        (("body.length", body_length), ("body.width", body_width))
        if quad
        else (("body.length", body_length),)
    ):
        if extent.max is not None and pitch * (per_side - 1) > extent.max:
            raise ctx.error(
                "package.dimensions-inconsistent",
                f"a row of {per_side} pins at {pitch} nm pitch is longer than {key} (max {extent.max} nm)",
                "pitch",
            )
    width_nom = nominal(ctx, "body.width", body_width)
    length_nom = nominal(ctx, "body.length", body_length)
    ep = _exposed(ctx, width_nom, length_nom)
    lead = ("terminal.length", t_length)
    wide = ("terminal.width", t_width)
    land_x = rows_land(
        ctx,
        "nolead",
        ("body.width", _span(body_width, pull_back)),
        lead,
        wide,
        spacing_key="row_spacing_x" if quad else "row_spacing",
        pitch=pitch,
        axis="x" if quad else "",
    )
    record_rows(ctx, land_x)
    if not ctx.manufacturer and ep is not None:
        land_x = _clear_of_ep(ctx, land_x, ep[0])
    draft = Draft(body=Box.centred(width_nom, length_nom), pin1="corner", pin1_index0=True)
    if quad:
        land_y = rows_land(
            ctx,
            "nolead",
            ("body.length", _span(body_length, pull_back)),
            lead,
            wide,
            spacing_key="row_spacing_y",
            pitch=pitch,
            axis="y",
        )
        if not ctx.manufacturer and ep is not None:
            land_y = _clear_of_ep(ctx, land_y, ep[1])
        draft.pads = quad_rows(
            pins,
            pitch,
            land_x.spacing,
            land_y.spacing,
            (land_x.length, land_x.x),
            (land_y.length, land_y.x),
            drawing=pkg.drawing,
        )
    else:
        draft.pads = dual_rows(pins, pitch, land_x.spacing, land_x.length, land_x.x, drawing=pkg.drawing)
    if ep is not None:
        number = keys.text("ep_number") or "EP"
        draft.pads.append(PadSpec(number, 0, 0, ep[0], ep[1], paste=False))
        draft.paste = _paste(ctx, ep)
    return draft


def _exposed(ctx: Context, width: Nm, length: Nm) -> tuple[Nm, Nm] | None:
    """The exposed pad's nominal size (x, y): the manufacturer's ``[land].ep`` when given, else ``ep``."""
    keys = ctx.package.keys
    ep = keys.table("ep")
    land = ctx.package.land
    given = land.table("ep") if land is not None else None
    if ep is not None:
        ep_x = length_of(ctx, "ep.width", ep.length("width"))
        ep_y = length_of(ctx, "ep.length", ep.length("length"))
        if (ep_x.min or 0) >= width or (ep_y.min or 0) >= length:
            raise ctx.error(
                "package.dimensions-inconsistent", "the exposed pad is not smaller than the body", "ep"
            )
    source = given if given is not None else ep
    if source is None:
        return None
    prefix = "land.ep" if given is not None else "ep"
    return (
        nominal(ctx, f"{prefix}.width", source.length("width")),
        nominal(ctx, f"{prefix}.length", source.length("length")),
    )


def _clear_of_ep(ctx: Context, land: RowLand, ep_across: Nm) -> RowLand:
    """Shorten a calculated row land from its inner end until it keeps ``pad_gap`` from the exposed pad."""
    table = ctx.require_table()
    need = -(-ep_across // 2) + table.pad_gap
    if land.g // 2 >= need:
        return land
    inner = ceil_to(need, table.grid)
    clipped = RowLand(land.z, 2 * inner, land.x)
    if clipped.length <= 0:
        raise ctx.error(
            "package.land-impossible", "the signal lands cannot keep the pad gap from the exposed pad", "ep"
        )
    ctx.warn(
        "package.pads-clipped",
        f"signal lands shortened from {land.length} to {clipped.length} nm to keep the pad gap of "
        f"{table.pad_gap} nm from the exposed pad; the heel goal is lost",
        "terminal.length",
    )
    return clipped


def _paste(ctx: Context, ep: tuple[Nm, Nm]) -> list[PasteWindow]:
    """The paste windows of the exposed pad: ``[land].paste`` or ``paste`` when given, else the
    table's grid."""
    land = ctx.package.land
    given: Keys | None = land.table("paste") if land is not None else None
    given = given or ctx.package.keys.table("paste")
    if given is not None:
        grid = given.counts("grid")
        if len(grid) != 2 or min(grid) < 1:
            raise ctx.error(
                "package.dimensions-inconsistent", "paste.grid must be [columns, rows]", "paste.grid"
            )
        window = nominal(ctx, "paste.window", given.length("window"))
        step = nominal(ctx, "paste.pitch", given.length("pitch"))
        return paste_grid(grid[0], grid[1], window, window, step, step)
    table = ctx.require_table()
    nx = max(2, -(-ep[0] // table.paste_cell))
    ny = max(2, -(-ep[1] // table.paste_cell))
    num, den = table.paste_window.numerator, table.paste_window.denominator
    return paste_grid(nx, ny, ep[0] * num // (den * nx), ep[1] * num // (den * ny), ep[0] // nx, ep[1] // ny)


__all__ = ["draw_nolead"]
