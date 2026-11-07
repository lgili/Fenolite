# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The two-terminal families ``chip`` (R, C, L, bead) and ``molded`` (SOD, SMA/SMB/SMC, molded tantalum,
MELF) (change c0260, decision 2).

The body ``length`` lies along the pad axis (x), ``width`` across it. Pad 1 is on the left; under
``polarity = "pad1"`` it is the cathode or the negative terminal (decision 9)."""

from __future__ import annotations

from fenolite.catalog.footprints._draft import (
    Box,
    Context,
    Draft,
    PadSpec,
    length_of,
    nominal,
    record_rows,
    rows_land,
)
from fenolite.core.quantities import LengthRange


def _pads(spacing: int, length: int, width: int) -> list[PadSpec]:
    return [PadSpec("1", -spacing // 2, 0, length, width), PadSpec("2", spacing // 2, 0, length, width)]


def draw_chip(ctx: Context) -> Draft:
    keys = ctx.package.keys
    body = keys.table("body")
    terminal = keys.table("terminal")
    assert body is not None and terminal is not None
    length = length_of(ctx, "body.length", body.length("length"))
    width = length_of(ctx, "body.width", body.length("width"))
    band = length_of(ctx, "terminal.length", terminal.length("length"))
    _check_terminal(ctx, length, band, "terminal.length")
    land = rows_land(ctx, "chip", ("body.length", length), ("terminal.length", band), ("body.width", width))
    record_rows(ctx, land)
    return _draft(ctx, land.spacing, land.length, land.x)


def draw_molded(ctx: Context) -> Draft:
    keys = ctx.package.keys
    body = keys.table("body")
    lead = keys.table("lead")
    assert body is not None and lead is not None
    span = length_of(ctx, "span", keys.length("span"))
    lead_length = length_of(ctx, "lead.length", lead.length("length"))
    lead_width = length_of(ctx, "lead.width", lead.length("width"))
    body_length = length_of(ctx, "body.length", body.length("length"))
    if span.max is not None and body_length.min is not None and span.max < body_length.min:
        raise ctx.error(
            "package.dimensions-inconsistent",
            f"the span (max {span.max} nm) is shorter than the body (min {body_length.min} nm)",
            "span",
        )
    _check_terminal(ctx, span, lead_length, "lead.length")
    land = rows_land(ctx, "molded", ("span", span), ("lead.length", lead_length), ("lead.width", lead_width))
    record_rows(ctx, land)
    return _draft(ctx, land.spacing, land.length, land.x)


def _check_terminal(ctx: Context, length: LengthRange, band: LengthRange, key: str) -> None:
    if band.max is not None and length.min is not None and 2 * band.max >= length.min:
        raise ctx.error(
            "package.dimensions-inconsistent",
            f"{key} (max {band.max} nm) is not shorter than half the length (min {length.min} nm)",
            key,
        )


def _draft(ctx: Context, spacing: int, length: int, width: int) -> Draft:
    keys = ctx.package.keys
    body = keys.table("body")
    assert body is not None
    body_length = nominal(ctx, "body.length", body.length("length"))
    body_width = nominal(ctx, "body.width", body.length("width"))
    polarized = keys.text("polarity") == "pad1"
    return Draft(
        pads=_pads(spacing, length, width),
        body=Box.centred(body_length, body_width),
        pin1="none",
        polarized=polarized,
        two_terminal=True,
        cathode0="left" if polarized else "",
    )


__all__ = ["draw_chip", "draw_molded"]
