# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What a family generator hands to the drawing conventions, and the land helpers families share."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from fenolite.catalog.footprints.codes import issue
from fenolite.catalog.footprints.lands import (
    Goals,
    LandTable,
    MissingBound,
    RowLand,
    facing_rows,
    floor_to,
)
from fenolite.catalog.footprints.record import Package
from fenolite.core.errors import FormatError, Issue
from fenolite.core.quantities import LengthRange
from fenolite.core.units import Nm

PadKindName = Literal["smd", "thru_hole", "np_thru_hole"]


@dataclass(frozen=True, slots=True)
class PadSpec:
    """One land before the conventions give it a shape: centre, size, kind and drill."""

    number: str
    x: Nm
    y: Nm
    w: Nm
    h: Nm
    kind: PadKindName = "smd"
    drill: Nm | None = None
    key: str = ""
    """The id key when it is not the number (an exposed pad, a hole, a second pad of one number)."""
    round: bool = False
    """A round land (a grid-array ball pad)."""
    paste: bool = True
    """``False`` for an exposed pad, whose paste is a grid of windows."""

    @property
    def x0(self) -> Nm:
        return self.x - self.w // 2

    @property
    def x1(self) -> Nm:
        return self.x + self.w // 2

    @property
    def y0(self) -> Nm:
        return self.y - self.h // 2

    @property
    def y1(self) -> Nm:
        return self.y + self.h // 2


@dataclass(frozen=True, slots=True)
class Box:
    """An axis-aligned rectangle ``x0 <= x1``, ``y0 <= y1``."""

    x0: Nm
    y0: Nm
    x1: Nm
    y1: Nm

    @staticmethod
    def centred(w: Nm, h: Nm, *, y: Nm = 0) -> Box:
        return Box(-(w // 2), y - h // 2, w // 2, y + h // 2)


@dataclass(frozen=True, slots=True)
class PasteWindow:
    """One window of an exposed pad's paste grid: its centre, size and index."""

    x: Nm
    y: Nm
    w: Nm
    h: Nm
    index: int


@dataclass(slots=True)
class Draft:
    """A family generator's output: lands, nominal body, pin-1 style and the land report numbers."""

    pads: list[PadSpec] = field(default_factory=lambda: [])
    body: Box | None = None
    kind: Literal["smd", "through_hole"] = "smd"
    pin1: Literal["dot", "corner", "none"] = "dot"
    """How ``drawing/1`` marks pin 1: a dot beyond pad 1, an L mark at the body corner, or nothing."""
    polarized: bool = False
    """A two-terminal part whose pad 1 is the cathode or the negative terminal."""
    two_terminal: bool = False
    paste: list[PasteWindow] = field(default_factory=lambda: [])
    pin1_index0: bool = False
    """``drawing/0``: the 0.6 pin-1 line across the fabrication corner (``_pin1_index``)."""
    cathode0: Literal["", "left", "right"] = ""
    """``drawing/0``: the 0.6 cathode line, at the left or the right end of the body."""
    cathode_inset0: Nm = 200_000


@dataclass(slots=True)
class LandNumbers:
    """The numbers of ``LandReport`` gathered while drawing."""

    source: Literal["calculated", "manufacturer"] = "calculated"
    z: Nm | None = None
    g: Nm | None = None
    x: Nm | None = None
    pad: tuple[Nm, Nm] | None = None
    drill: Nm | None = None
    pad_diameter: Nm | None = None
    deltas: dict[str, Nm] = field(default_factory=lambda: {})


class Refused(Exception):
    """A family cannot draw the record; the issues say why (at least one error)."""


@dataclass(slots=True)
class Context:
    """What a family generator reads besides the record, and where it puts its findings."""

    package: Package
    table: LandTable | None
    issues: list[Issue] = field(default_factory=lambda: [])
    land: LandNumbers = field(default_factory=LandNumbers)

    @property
    def manufacturer(self) -> bool:
        return self.package.land is not None

    def where(self, key: str = "") -> str:
        name = self.package.file or self.package.name
        return f"{name}:{key}" if key else name

    def error(self, code: str, message: str, key: str = "") -> Refused:
        self.issues.append(issue(code, message, where=self.where(key)))
        return Refused(message)

    def warn(self, code: str, message: str, key: str = "") -> None:
        self.issues.append(issue(code, message, where=self.where(key)))

    def goals(self, land_class: str) -> Goals | None:
        """The goals of ``land_class`` in the record's table, or ``None`` without a table or a calibration."""
        if self.table is None:
            return None
        return self.table.goals.get(land_class)

    def require_table(self) -> LandTable:
        """The constant table; the reader guarantees one when the record has no ``[land]``."""
        if self.table is None:
            raise FormatError(
                "the record needs 'lands' (the constant table version) for this land",
                file=self.package.file,
                locator="generate.lands",
            )
        return self.table


def length_of(ctx: Context, key: str, value: LengthRange | None) -> LengthRange:
    """``value``, or a ``FormatError`` naming ``key`` (the reader checks required keys; this guards the
    keys that are required only in one arrangement)."""
    if value is None:
        raise FormatError(f"missing required key {key!r}", file=ctx.package.file, locator=key)
    return value


def nominal(ctx: Context, key: str, value: LengthRange | None) -> Nm:
    """The nominal of ``value``; ``package.missing-bound`` when the range has neither nominal nor both
    bounds."""
    found = length_of(ctx, key, value).nominal
    if found is None:
        raise ctx.error("package.missing-bound", f"{key} has no nominal (give nom, or min and max)", key)
    return found


def manufacturer_rows(ctx: Context, spacing_key: str) -> RowLand:
    """The facing-row land of the record's ``[land]``: ``pad`` (length, width) at ``spacing_key``."""
    land = ctx.package.land
    assert land is not None
    pad = land.table("pad")
    spacing = land.length(spacing_key)
    if pad is None or spacing is None:
        missing = "land.pad" if pad is None else f"land.{spacing_key}"
        raise FormatError(f"missing required key {missing!r}", file=ctx.package.file, locator=missing)
    length = nominal(ctx, "land.pad.length", pad.length("length"))
    width = nominal(ctx, "land.pad.width", pad.length("width"))
    centre = nominal(ctx, f"land.{spacing_key}", spacing)
    return RowLand(centre + length, centre - length, width)


def calculated_rows(
    ctx: Context,
    land_class: str,
    span: tuple[str, LengthRange],
    lead: tuple[str, LengthRange],
    width: tuple[str, LengthRange],
) -> RowLand | None:
    """The calculated land, ``None`` when the class has no goals; ``package.missing-bound`` raised."""
    goals = ctx.goals(land_class)
    table = ctx.table
    if goals is None or table is None:
        return None
    try:
        return facing_rows(span, lead, width, goals, table.grid)
    except MissingBound as missing:
        raise ctx.error(
            "package.missing-bound",
            f"the calculator needs the {missing.bound} of {missing.key}, which the record does not give",
            missing.key,
        ) from None


def rows_land(
    ctx: Context,
    land_class: str,
    span: tuple[str, LengthRange],
    lead: tuple[str, LengthRange],
    width: tuple[str, LengthRange],
    *,
    spacing_key: str = "row_spacing",
    pitch: Nm | None = None,
    axis: str = "",
) -> RowLand:
    """The land of two facing rows: the manufacturer's when the record gives ``[land]`` (the calculated one
    then only gives the deltas), else the calculated one, clipped to keep ``pad_gap`` at ``pitch``."""
    if ctx.manufacturer:
        given = manufacturer_rows(ctx, spacing_key)
        try:
            calculated = calculated_rows(ctx, land_class, span, lead, width)
        except Refused:
            ctx.issues.pop()  # a calculation for comparison only: a missing bound is no finding here
            calculated = None
        if calculated is not None:
            suffix = f"_{axis}" if axis else ""
            ctx.land.deltas.update(
                {
                    f"pad_length{suffix}": given.length - calculated.length,
                    f"pad_width{suffix}": given.x - calculated.x,
                    f"row_spacing{suffix}": given.spacing - calculated.spacing,
                }
            )
        _check_positive(ctx, given)
        return given
    calculated = calculated_rows(ctx, land_class, span, lead, width)
    if calculated is None:
        raise ctx.error(
            "package.no-goals",
            f"lands/{ctx.package.lands} has no calibrated goals for the land class {land_class!r}; "
            "give the manufacturer's [land]",
            "land",
        )
    _check_positive(ctx, calculated)
    table = ctx.require_table()
    if pitch is not None and pitch - calculated.x < table.pad_gap:
        clipped = floor_to(pitch - table.pad_gap, table.grid)
        if clipped <= 0:
            raise ctx.error(
                "package.land-impossible",
                f"a pitch of {pitch} nm leaves no land width with a pad gap of {table.pad_gap} nm",
                "pitch",
            )
        ctx.warn(
            "package.pads-clipped",
            f"lands narrowed from {calculated.x} to {clipped} nm to keep the pad gap of {table.pad_gap} nm; "
            f"the side goal is lost",
            "lead.width",
        )
        calculated = RowLand(calculated.z, calculated.g, clipped)
    return calculated


def _check_positive(ctx: Context, land: RowLand) -> None:
    if land.g <= 0 or land.length <= 0 or land.x <= 0:
        raise ctx.error(
            "package.land-impossible",
            f"the land has no positive gap or size (Z {land.z}, G {land.g}, X {land.x} nm)",
            "land",
        )


def record_rows(ctx: Context, land: RowLand) -> None:
    """Keep the numbers of a facing-row land for the report (the first rows recorded win)."""
    if ctx.land.z is None:
        ctx.land.z, ctx.land.g, ctx.land.x = land.z, land.g, land.x
        ctx.land.pad = (land.length, land.x)


def dual_offsets(count: int, pitch: Nm, *, drawing: int) -> tuple[Nm, ...]:
    """The y of ``count`` lands of one row, in numbering order: from the top (most negative y) under
    ``drawing >= 1``; from the most positive y under ``drawing/0``, as the 0.6 helpers placed them."""
    if drawing == 0:
        return tuple(((count - 1 - 2 * i) * pitch) // 2 for i in range(count))
    return tuple(((2 * i - count + 1) * pitch) // 2 for i in range(count))


def dual_rows(
    count: int,
    pitch: Nm,
    spacing: Nm,
    w: Nm,
    h: Nm,
    *,
    drawing: int,
    kind: PadKindName = "smd",
    drill: Nm | None = None,
) -> list[PadSpec]:
    """``count`` lands in two rows at ``x = ±spacing / 2``, numbered counter-clockwise from pin 1 at the top
    of     the left row (``drawing/0``: the 0.6 placement, see ``dual_offsets``)."""
    per_side = count // 2
    offsets = dual_offsets(per_side, pitch, drawing=drawing)
    coords = [(-spacing // 2, y) for y in offsets] + [(spacing // 2, y) for y in reversed(offsets)]
    return [PadSpec(str(i + 1), x, y, w, h, kind=kind, drill=drill) for i, (x, y) in enumerate(coords)]


def quad_rows(
    count: int,
    pitch: Nm,
    spacing_x: Nm,
    spacing_y: Nm,
    size_x: tuple[Nm, Nm],
    size_y: tuple[Nm, Nm],
    *,
    drawing: int,
) -> list[PadSpec]:
    """``count`` lands on four sides, numbered counter-clockwise in the top view from the upper left
    (``drawing/0``: the 0.6 placement of ``_quad_pads``). ``size_x`` is the (length, width) of the left and
    right lands, long in x; ``size_y`` that of the top and bottom lands, long in y."""
    per_side = count // 4
    offsets = dual_offsets(per_side, pitch, drawing=drawing)
    half_x, half_y = spacing_x // 2, spacing_y // 2
    if drawing == 0:
        # As _quad_pads placed them: left, then the row at -y, right, then the row at +y.
        coords = (
            *((-half_x, y, True) for y in offsets),
            *((x, -half_y, False) for x in reversed(offsets)),
            *((half_x, y, True) for y in reversed(offsets)),
            *((x, half_y, False) for x in offsets),
        )
    else:
        # Down the left side, left to right along the bottom, up the right, right to left along the top.
        coords = (
            *((-half_x, y, True) for y in offsets),
            *((x, half_y, False) for x in offsets),
            *((half_x, y, True) for y in reversed(offsets)),
            *((x, -half_y, False) for x in reversed(offsets)),
        )
    return [
        PadSpec(str(i + 1), x, y, *(size_x if across else (size_y[1], size_y[0])))
        for i, (x, y, across) in enumerate(coords)
    ]


def paste_grid(nx: int, ny: int, w: Nm, h: Nm, pitch_x: Nm, pitch_y: Nm) -> list[PasteWindow]:
    """``nx × ny`` windows of ``w × h`` on the pitches, centred, indexed column by column (as 0.6)."""
    return [
        PasteWindow((2 * i - nx + 1) * pitch_x // 2, (2 * j - ny + 1) * pitch_y // 2, w, h, i * ny + j)
        for i in range(nx)
        for j in range(ny)
    ]


def deltas_view(deltas: Mapping[str, Nm]) -> dict[str, Nm]:
    """The deltas sorted by key."""
    return {key: deltas[key] for key in sorted(deltas)}


__all__ = [
    "Box",
    "Context",
    "Draft",
    "LandNumbers",
    "PadSpec",
    "PasteWindow",
    "Refused",
    "dual_offsets",
    "dual_rows",
    "length_of",
    "manufacturer_rows",
    "nominal",
    "paste_grid",
    "quad_rows",
    "record_rows",
    "rows_land",
]
