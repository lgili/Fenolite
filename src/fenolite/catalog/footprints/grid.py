# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``grid`` family: ball and land grid arrays (change c0260, decisions 2, 4 and 9).

Rows are lettered from ``A`` at the top (most negative y), skipping ``I``, ``O``, ``Q``, ``S``, ``X`` and
``Z``, then ``AA``, ``AB``, ...; columns are numbered from 1 at the left; ``A1`` is the top-left ball in the
top view. The land of a ball is round: the manufacturer's diameter, else the ball's nominal diameter times
the table's ``ball_ratio`` for the pad kind, rounded to the grid."""

from __future__ import annotations

from fenolite.catalog.footprints._draft import Box, Context, Draft, PadSpec, length_of, nominal
from fenolite.catalog.footprints.lands import floor_to

ROW_LETTERS = "ABCDEFGHJKLMNPRTUVWY"
"""The row letters: the alphabet without I, O, Q, S, X and Z (``naming.md``, "Grid arrays")."""


def row_name(index: int) -> str:
    """``0`` → ``A``, ``7`` → ``H``, ``8`` → ``J``, ``20`` → ``AA``, ``21`` → ``AB``."""
    count = len(ROW_LETTERS)
    if index < count:
        return ROW_LETTERS[index]
    return ROW_LETTERS[index // count - 1] + ROW_LETTERS[index % count]


def draw_grid(ctx: Context) -> Draft:
    pkg = ctx.package
    keys = pkg.keys
    rows = keys.count("rows") or 0
    columns = keys.count("columns") or 0
    if rows > len(ROW_LETTERS) * (len(ROW_LETTERS) + 1):
        raise ctx.error("package.dimensions-inconsistent", f"{rows} rows have no row letters", "rows")
    pitch = keys.length("pitch")
    pitch_x = nominal(ctx, "pitch_x", keys.length("pitch_x") or pitch)
    pitch_y = nominal(ctx, "pitch_y", keys.length("pitch_y") or pitch)
    body = keys.table("body")
    ball = keys.table("ball")
    assert body is not None and ball is not None
    body_length = length_of(ctx, "body.length", body.length("length"))
    body_width = length_of(ctx, "body.width", body.length("width"))
    for key, count, step, extent in (
        ("body.width", columns, pitch_x, body_width),
        ("body.length", rows, pitch_y, body_length),
    ):
        if extent.max is not None and step * (count - 1) > extent.max:
            raise ctx.error(
                "package.dimensions-inconsistent",
                f"the ball grid is wider than {key} (max {extent.max} nm)",
                key,
            )
    removed = _depopulated(ctx, rows, columns)
    diameter = _land_diameter(ctx)
    pads: list[PadSpec] = []
    for r in range(rows):
        y = (2 * r - rows + 1) * pitch_y // 2
        for col in range(columns):
            name = f"{row_name(r)}{col + 1}"
            if name in removed:
                continue
            x = (2 * col - columns + 1) * pitch_x // 2
            pads.append(PadSpec(name, x, y if pkg.drawing else -y, diameter, diameter, round=True))
    ctx.land.pad_diameter = diameter
    ctx.land.pad = (diameter, diameter)
    return Draft(
        pads=pads,
        body=Box.centred(nominal(ctx, "body.width", body_width), nominal(ctx, "body.length", body_length)),
        pin1="corner",
        pin1_index0=True,
    )


def _depopulated(ctx: Context, rows: int, columns: int) -> set[str]:
    raw = ctx.package.keys.raw("depopulated")
    if raw is None:
        return set()
    names = {f"{row_name(r)}{c + 1}" for r in range(rows) for c in range(columns)}
    if isinstance(raw, tuple) and raw and isinstance(raw[0], str):
        given = {str(name) for name in raw}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        outside = sorted(given - names)
        if outside:
            raise ctx.error(
                "package.dimensions-inconsistent",
                f"depopulated ball {outside[0]} lies outside the grid",
                "depopulated",
            )
        return given
    block_rows, block_columns = raw  # type: ignore[misc]
    assert isinstance(block_rows, int) and isinstance(block_columns, int)
    if (
        block_rows > rows
        or block_columns > columns
        or (rows - block_rows) % 2
        or (columns - block_columns) % 2
    ):
        raise ctx.error(
            "package.dimensions-inconsistent",
            f"a centre block of {block_rows}x{block_columns} does not sit centred in {rows}x{columns}",
            "depopulated.center",
        )
    r0, c0 = (rows - block_rows) // 2, (columns - block_columns) // 2
    return {
        f"{row_name(r)}{c + 1}" for r in range(r0, r0 + block_rows) for c in range(c0, c0 + block_columns)
    }


def _land_diameter(ctx: Context) -> int:
    land = ctx.package.land
    if land is not None:
        ctx.land.source = "manufacturer"
        return nominal(ctx, "land.pad_diameter", land.length("pad_diameter"))
    keys = ctx.package.keys
    ball = keys.table("ball")
    assert ball is not None
    kind = keys.text("pad") or "nsmd"
    table = ctx.require_table()
    ratio = table.ball_ratio.get(kind)
    if ratio is None:
        raise ctx.error(
            "package.no-goals",
            f"lands/{table.version} has no calibrated ball ratio for {kind} pads; "
            "give the manufacturer's [land]",
            "pad",
        )
    diameter = nominal(ctx, "ball.diameter", ball.length("diameter"))
    scaled = diameter * ratio.numerator
    return floor_to((scaled + ratio.denominator * table.grid // 2) // ratio.denominator, table.grid)


__all__ = ["ROW_LETTERS", "draw_grid", "row_name"]
