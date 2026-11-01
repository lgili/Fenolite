# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The families with through-hole leads: ``dip``, ``to``, ``header`` and ``connector`` (change c0260,
decisions 2, 4 and 9).

The drill is the lead's diagonal plus ``hole_clearance``, rounded up to the grid; the pad diameter is the
drill plus twice ``annular_ring``. A pad wider than ``pitch - pad_gap`` becomes an oval of that width.

Axes: a ``dip`` has its two rows along y (``length`` along the rows); ``to``, ``header`` and ``connector``
put their pins along x (``length`` along x), rows of a header below one another, and ``body.offset`` moves
the body centre in y. An SMD ``to`` (DPAK-, D2PAK-style) has its leads at the bottom and its tab at the
top."""

from __future__ import annotations

from fenolite.catalog.footprints._draft import (
    Box,
    Context,
    Draft,
    PadSpec,
    dual_rows,
    length_of,
    nominal,
    record_rows,
    rows_land,
)
from fenolite.catalog.footprints.lands import bound, drill_for, floor_to
from fenolite.catalog.footprints.record import Keys
from fenolite.core.errors import FormatError
from fenolite.core.units import Nm


def _hole(ctx: Context, lead: Keys, lead_key: str) -> tuple[Nm, Nm]:
    """The drill and pad diameter: the manufacturer's ``[land]``, else the calculated ones."""
    land = ctx.package.land
    if land is not None:
        drill_given = land.length("drill")
        if drill_given is None:
            raise FormatError(
                "missing required key 'land.drill'", file=ctx.package.file, locator="land.drill"
            )
        drill = nominal(ctx, "land.drill", drill_given)
        pad_given = land.length("pad_diameter")
        if pad_given is not None:
            result = (drill, nominal(ctx, "land.pad_diameter", pad_given))
        else:
            # The manufacturer gives the hole only: the ring is the table's annular ring.
            table = ctx.table
            if table is None or table.annular_ring is None:
                raise ctx.error(
                    "package.no-goals",
                    "the [land] gives no pad_diameter and the record's table has no annular ring",
                    "land.pad_diameter",
                )
            result = (drill, drill + 2 * table.annular_ring)
        calculated = _calculated(ctx, lead, lead_key, comparing=True)
        if calculated is not None:
            ctx.land.deltas.update(
                {"drill": result[0] - calculated[0], "pad_diameter": result[1] - calculated[1]}
            )
    else:
        found = _calculated(ctx, lead, lead_key, comparing=False)
        assert found is not None
        result = found
    if result[0] <= 0 or result[1] <= result[0]:
        raise ctx.error(
            "package.land-impossible", f"a drill of {result[0]} nm in a pad of {result[1]} nm", "land"
        )
    ctx.land.drill, ctx.land.pad_diameter = result
    return result


def _calculated(ctx: Context, lead: Keys, lead_key: str, *, comparing: bool) -> tuple[Nm, Nm] | None:
    table = ctx.table
    width = length_of(ctx, f"{lead_key}.width", lead.length("width"))
    thickness = lead.length("thickness")
    if table is None or table.hole_clearance is None or table.annular_ring is None:
        if comparing:
            return None
        version = ctx.package.lands
        raise ctx.error(
            "package.no-goals",
            f"lands/{version} has no calibrated hole clearance and annular ring; "
            "give the manufacturer's [land]",
            "land",
        )
    try:
        w = bound(width, f"{lead_key}.width", "max")
        t = None if thickness is None else bound(thickness, f"{lead_key}.thickness", "max")
    except Exception as missing:  # MissingBound
        if comparing:
            return None
        raise ctx.error("package.missing-bound", str(missing), f"{lead_key}.width") from None
    drill = drill_for(w, t, table)
    assert drill is not None
    return drill, drill + 2 * table.annular_ring


def _fit(ctx: Context, diameter: Nm, pitch: Nm) -> Nm:
    """The pad's width across its neighbours: ``diameter``, or ``pitch - pad_gap`` with a warning."""
    if ctx.manufacturer or ctx.table is None:
        return diameter
    limit = floor_to(pitch - ctx.table.pad_gap, ctx.table.grid)
    if diameter <= limit:
        return diameter
    ctx.warn(
        "package.pads-clipped",
        f"pads narrowed from {diameter} to {limit} nm across the pitch (ovals) to keep the pad gap of "
        f"{ctx.table.pad_gap} nm",
        "pitch",
    )
    return limit


def _body(ctx: Context, keys: Keys, *, length: Nm | None = None, width: Nm | None = None) -> Box:
    body = keys.table("body")
    assert body is not None
    x = length if length is not None else nominal(ctx, "body.length", body.length("length"))
    y = width if width is not None else nominal(ctx, "body.width", body.length("width"))
    offset = body.length("offset")
    return Box.centred(x, y, y=0 if offset is None else nominal(ctx, "body.offset", offset))


def draw_dip(ctx: Context) -> Draft:
    pkg = ctx.package
    keys = pkg.keys
    pins = keys.count("pins") or 0
    if pins % 2:
        raise ctx.error("package.pin-count", f"{pins} pins cannot fill two equal rows", "pins")
    pitch = nominal(ctx, "pitch", keys.length("pitch"))
    spacing = nominal(ctx, "row_spacing", keys.length("row_spacing"))
    body = keys.table("body")
    lead = keys.table("lead")
    assert body is not None and lead is not None
    length = length_of(ctx, "body.length", body.length("length"))
    if length.max is not None and pitch * (pins // 2 - 1) > length.max:
        raise ctx.error(
            "package.dimensions-inconsistent",
            f"a row of {pins // 2} pins is longer than body.length",
            "pitch",
        )
    drill, diameter = _hole(ctx, lead, "lead")
    across = _fit(ctx, diameter, pitch)
    pads = dual_rows(
        pins, pitch, spacing, diameter, across, drawing=pkg.drawing, kind="thru_hole", drill=drill
    )
    box = Box.centred(nominal(ctx, "body.width", body.length("width")), nominal(ctx, "body.length", length))
    return Draft(pads=pads, body=box, kind="through_hole", pin1="dot", pin1_index0=True)


def _row_x(count: int, pitch: Nm) -> list[Nm]:
    return [(2 * i - count + 1) * pitch // 2 for i in range(count)]


def draw_to(ctx: Context) -> Draft:
    pkg = ctx.package
    keys = pkg.keys
    leads = keys.count("leads") or 0
    pitch = nominal(ctx, "pitch", keys.length("pitch"))
    lead = keys.table("lead")
    assert lead is not None
    if keys.text("mount") == "tht":
        drill, diameter = _hole(ctx, lead, "lead")
        across = _fit(ctx, diameter, pitch)
        pads = [
            PadSpec(str(i + 1), x, 0, across, diameter, kind="thru_hole", drill=drill)
            for i, x in enumerate(_row_x(leads, pitch))
        ]
        return Draft(pads=pads, body=_body(ctx, keys), kind="through_hole", pin1="dot")
    tab = keys.table("tab")
    if tab is None:
        raise FormatError("an SMD 'to' package needs 'tab'", file=pkg.file, locator="tab")
    span = length_of(ctx, "span", keys.length("span"))
    tab_number = tab.text("number") or str(leads + 1)
    land = pkg.land
    if land is not None:
        lead_land = rows_land(
            ctx,
            "smd-tab",
            ("span", span),
            ("lead.length", length_of(ctx, "lead.length", lead.length("length"))),
            ("lead.width", length_of(ctx, "lead.width", lead.length("width"))),
        )
        given = land.table("tab")
        if given is None:
            raise FormatError("missing required key 'land.tab'", file=pkg.file, locator="land.tab")
        tab_size = (
            nominal(ctx, "land.tab.width", given.length("width")),
            nominal(ctx, "land.tab.length", given.length("length")),
        )
        tab_y = -nominal(ctx, "land.tab.at", given.length("at"))
    else:
        lead_land = rows_land(
            ctx,
            "smd-tab",
            ("span", span),
            ("lead.length", length_of(ctx, "lead.length", lead.length("length"))),
            ("lead.width", length_of(ctx, "lead.width", lead.length("width"))),
            pitch=pitch,
        )
        tab_land = rows_land(
            ctx,
            "smd-tab",
            ("span", span),
            ("tab.length", length_of(ctx, "tab.length", tab.length("length"))),
            ("tab.width", length_of(ctx, "tab.width", tab.length("width"))),
        )
        tab_size = (tab_land.x, tab_land.length)
        tab_y = -tab_land.spacing // 2
    record_rows(ctx, lead_land)
    pads = [
        PadSpec(str(i + 1), x, lead_land.spacing // 2, lead_land.x, lead_land.length)
        for i, x in enumerate(_row_x(leads, pitch))
        if str(i + 1) != tab_number
    ]
    pads.append(PadSpec(tab_number, 0, tab_y, tab_size[0], tab_size[1], key="tab"))
    return Draft(pads=pads, body=_body(ctx, keys), pin1="dot")


def draw_header(ctx: Context) -> Draft:
    pkg = ctx.package
    keys = pkg.keys
    rows = keys.count("rows") or 0
    columns = keys.count("columns") or 0
    pitch = nominal(ctx, "pitch", keys.length("pitch"))
    pin = keys.table("pin")
    assert pin is not None
    columns_first = keys.text("numbering") == "columns-first"
    if keys.text("mount") == "smd":
        land = pkg.land
        if land is None or land.table("pad") is None:
            raise ctx.error(
                "package.no-goals", "an SMD header needs the manufacturer's [land] with 'pad'", "land"
            )
        pad = land.table("pad")
        assert pad is not None
        size = (
            nominal(ctx, "land.pad.width", pad.length("width")),
            nominal(ctx, "land.pad.length", pad.length("length")),
        )
        kind, drill = "smd", None
    else:
        drill, diameter = _hole(ctx, pin, "pin")
        size = (_fit(ctx, diameter, pitch), diameter if rows == 1 else _fit(ctx, diameter, pitch))
        kind = "thru_hole"
    pads: list[PadSpec] = []
    for r in range(rows):
        y = (2 * r - rows + 1) * pitch // 2
        for c, x in enumerate(_row_x(columns, pitch)):
            number = r * columns + c + 1 if columns_first else c * rows + r + 1
            pads.append(
                PadSpec(str(number), x, y if pkg.drawing else -y, size[0], size[1], kind=kind, drill=drill)
            )  # type: ignore[arg-type]
    pads.sort(key=lambda p: int(p.number))
    body = keys.table("body")
    assert body is not None
    length = body.length("length")
    width = body.length("width")
    box = _body(
        ctx,
        keys,
        length=columns * pitch if length is None else None,
        width=rows * pitch if width is None else None,
    )
    return Draft(pads=pads, body=box, kind="smd" if kind == "smd" else "through_hole", pin1="dot")


def draw_connector(ctx: Context, positions: int) -> Draft:
    pkg = ctx.package
    keys = pkg.keys
    pitch = nominal(ctx, "pitch", keys.length("pitch"))
    pin = keys.table("pin")
    body = keys.table("body")
    assert pin is not None and body is not None
    drill, diameter = _hole(ctx, pin, "pin")
    across = _fit(ctx, diameter, pitch)
    pads = [
        PadSpec(str(i + 1), x, 0, across, diameter, kind="thru_hole", drill=drill)
        for i, x in enumerate(_row_x(positions, pitch))
    ]
    end = (positions - 1) * pitch // 2
    for index, mech in enumerate(keys.tables("mechanical")):
        beyond = nominal(ctx, f"mechanical[{index}].beyond", mech.length("beyond"))
        y = nominal(ctx, f"mechanical[{index}].y", mech.length("y"))
        hole = nominal(ctx, f"mechanical[{index}].drill", mech.length("drill"))
        plated = mech.text("kind") == "pad"
        copper = mech.length("pad_diameter")
        size = (
            nominal(ctx, f"mechanical[{index}].pad_diameter", copper)
            if plated and copper is not None
            else hole
        )
        for side, x in (("left", -end - beyond), ("right", end + beyond)):
            pads.append(
                PadSpec(
                    (mech.text("number") or "MP") if plated else "",
                    x,
                    y,
                    size,
                    size,
                    kind="thru_hole" if plated else "np_thru_hole",
                    drill=hole,
                    key=f"mech:{index}:{side}",
                )
            )
    raw_length = body.raw("length")
    if isinstance(raw_length, Keys):
        per = nominal(ctx, "body.length.per_position", raw_length.length("per_position"))
        extra = nominal(ctx, "body.length.extra", raw_length.length("extra"))
        length = per * positions + extra
    else:
        length = nominal(ctx, "body.length", body.length("length"))
    return Draft(pads=pads, body=_body(ctx, keys, length=length), kind="through_hole", pin1="dot")


__all__ = ["draw_connector", "draw_dip", "draw_header", "draw_to"]
