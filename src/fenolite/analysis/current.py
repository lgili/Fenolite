# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Current capacity of tracks, arcs and vias from one published fit (capability board-analyses,
"Published capacity fit", "Track and arc capacity" and "Via capacity"; facts and sources:
``docs/analyses.md``, table "Capacity fit").

The fit is ``I = K · ΔT^b · A^c`` with ``I`` in amperes, ``ΔT`` the temperature rise in kelvin and ``A``
the cross-section in square mils, as the source S-0269 states it. That source attributes the fit to a
standard; Fenolite did not consult the standard, reproduces none of its charts or tables and claims no
conformance. The value is computed with ``decimal`` at 40 digits, the same on every platform, and
rounded down to whole milliamperes, so a capacity is never overstated.

Nothing is assumed: an item whose copper thickness, plating or temperature rise is not given is left out
and counted. One row is one track, arc or via; parallel copper and zones are not combined.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from decimal import ROUND_FLOOR, Decimal, localcontext

from fenolite.analysis.codes import issue
from fenolite.analysis.report import (
    NO_NET,
    AnalysisReport,
    CurrentRow,
    report_evidence,
    sorted_issues,
)
from fenolite.analysis.requirements import Requirements
from fenolite.core.errors import Issue
from fenolite.core.units import Nm
from fenolite.model.base import Entity
from fenolite.model.board import Board
from fenolite.model.design import Design

FIT_K_EXTERNAL = Decimal("0.048")
FIT_K_INTERNAL = Decimal("0.024")
FIT_EXP_RISE = Decimal("0.44")
FIT_EXP_AREA = Decimal("0.725")
MIL_NM = 25_400
FIT_MAX_EXTERNAL_MA = 35_000
FIT_MAX_INTERNAL_MA = 17_500
FIT_MAX_RISE_MK = 100_000
FIT_MAX_WIDTH_NM = 10_160_000
SOURCE_OF_FIT = "S-0269"
PRECISION = 40
ALL_LAYERS = "*"


def _positive(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be an int above 0, got {value!r}")


def capacity_ma(area_nm2: int, temp_rise_mk: int, *, external: bool) -> int:
    """The current of the fit in milliamperes, rounded down: ``area_nm2`` is the cross-section in square
    nanometres and ``temp_rise_mk`` the rise in millikelvin."""
    _positive(area_nm2, "area_nm2")
    _positive(temp_rise_mk, "temp_rise_mk")
    with localcontext() as context:
        context.prec = PRECISION
        area = Decimal(area_nm2) / (Decimal(MIL_NM) * Decimal(MIL_NM))
        rise = Decimal(temp_rise_mk) / Decimal(1000)
        k = FIT_K_EXTERNAL if external else FIT_K_INTERNAL
        amperes = k * rise**FIT_EXP_RISE * area**FIT_EXP_AREA
        return int((amperes * Decimal(1000)).to_integral_value(rounding=ROUND_FLOOR))


def _pi() -> Decimal:
    """π to the precision of the current context: the series of the ``decimal`` documentation (S-0012)."""
    with localcontext() as context:
        context.prec += 2
        three = Decimal(3)
        last, t, s, n, na, d, da = Decimal(0), three, three, 1, 0, 0, 24
        while s != last:
            last = s
            n, na = n + na, na + 8
            d, da = d + da, da + 32
            t = (t * n) / d
            s += t
    return +s


def barrel_area_nm2(drill: Nm, plating: Nm) -> int:
    """The cross-section of a plated barrel, ``π · (drill + plating) · plating``, rounded down; ``drill``
    is the finished hole diameter (``H-G-AN-VIA``)."""
    _positive(drill, "drill")
    _positive(plating, "plating")
    with localcontext() as context:
        context.prec = PRECISION
        area = _pi() * Decimal(drill + plating) * Decimal(plating)
        return int(area.to_integral_value(rounding=ROUND_FLOOR))


def in_range(width: Nm | None, temp_rise_mk: int, capacity: int, *, external: bool) -> bool:
    """Whether the width, the rise and the capacity are each inside the range S-0269 states for the fit.
    A via has no width."""
    limit = FIT_MAX_EXTERNAL_MA if external else FIT_MAX_INTERNAL_MA
    if width is not None and width > FIT_MAX_WIDTH_NM:
        return False
    return temp_rise_mk <= FIT_MAX_RISE_MK and capacity <= limit


def _where(entity: Entity) -> str:
    provenance = entity.provenance
    return provenance.locator if provenance is not None and provenance.locator else entity.id


def _thickness(board: Board, layer: str, given: Mapping[str, Nm] | None) -> Nm | None:
    if given is not None:
        if layer in given:
            return given[layer]
        if ALL_LAYERS in given:
            return given[ALL_LAYERS]
    if board.stackup is not None:
        for entry in board.stackup.layers:
            if entry.kind == "copper" and entry.name == layer and entry.thickness > 0:
                return entry.thickness
    return None


def analyze_current(
    design: Design,
    *,
    temp_rise_mk: int | None = None,
    copper_thickness: Mapping[str, Nm] | None = None,
    via_plating: Nm | None = None,
    requirements: Requirements | None = None,
) -> AnalysisReport:
    """One row per track, arc and via whose inputs are known, the weakest item of each net, and the
    findings against the user's current rows."""
    board = design.board
    if board is None:
        return AnalysisReport(summary={"rows": 0, "skipped": 0, "nets": {}, "fit": SOURCE_OF_FIT})
    circuit = design.circuit
    nets = {net.id: net for net in circuit.nets}
    copper = tuple(layer.name for layer in board.layers if layer.kind == "copper")
    outer = {copper[0], copper[-1]} if copper else set[str]()
    governing = {
        net.id: requirements.current_for(net, circuit) if requirements is not None else None
        for net in circuit.nets
    }
    rows: list[CurrentRow] = []
    missing: Counter[str] = Counter()

    def rise_of(net_id: str | None) -> int | None:
        row = governing.get(net_id) if net_id is not None else None
        return row.temp_rise_mk if row is not None else temp_rise_mk

    def name_of(net_id: str | None) -> str:
        net = nets.get(net_id) if net_id is not None else None
        return net.name if net is not None else (net_id or NO_NET)

    for kind, items in (("track", board.tracks), ("arc", board.arcs)):
        for item in items:
            if item.layer not in copper:
                if not copper:
                    missing["copper layers of the board"] += 1
                continue
            thickness = _thickness(board, item.layer, copper_thickness)
            rise = rise_of(item.net_id)
            if thickness is None or rise is None or item.width <= 0:
                missing["copper thickness" if thickness is None else "temperature rise"] += 1
                continue
            external = item.layer in outer
            area = item.width * thickness
            capacity = capacity_ma(area, rise, external=external)
            rows.append(
                CurrentRow(
                    "track" if kind == "track" else "arc",
                    _where(item),
                    item.id,
                    name_of(item.net_id),
                    item.layer,
                    item.start,
                    item.width,
                    thickness,
                    area,
                    external,
                    rise,
                    capacity,
                    in_range(item.width, rise, capacity, external=external),
                )
            )
    for via in board.vias:
        rise = rise_of(via.net_id)
        if via_plating is None or rise is None or via.drill <= 0:
            missing["via plating" if via_plating is None else "temperature rise"] += 1
            continue
        area = barrel_area_nm2(via.drill, via_plating)
        capacity = capacity_ma(area, rise, external=True)
        rows.append(
            CurrentRow(
                "via",
                _where(via),
                via.id,
                name_of(via.net_id),
                "/".join(via.layers),
                via.position,
                None,
                via_plating,
                area,
                True,
                rise,
                capacity,
                in_range(None, rise, capacity, external=True),
            )
        )
    rows.sort(key=lambda row: (row.net, row.layer, row.where, row.entity_id))

    issues: list[Issue] = []
    for name, count in sorted(missing.items()):
        issues.append(
            issue(
                "analysis.input-missing",
                f"{name} not given: {count} item(s) left out of the capacity analysis",
                where=name,
                hint="Fenolite assumes no value; give it as an option or in the requirements file",
            )
        )
    weakest: dict[str, CurrentRow] = {}
    outside: Counter[str] = Counter()
    for row in rows:
        if not row.in_range:
            outside[row.net] += 1
        if row.net != NO_NET and (row.net not in weakest or row.capacity_ma < weakest[row.net].capacity_ma):
            weakest[row.net] = row
    for name, count in sorted(outside.items()):
        issues.append(
            issue(
                "analysis.fit-out-of-range",
                f"{count} item(s) of net {name or '<no net>'} lie outside the range the source states for "
                "the fit (width, temperature rise or current); their capacity is an extrapolation",
                where=name or "<no net>",
            )
        )
    if requirements is not None:
        names = {net.name: net for net in circuit.nets}
        for row in rows:
            net = names.get(row.net)
            wanted = governing.get(net.id) if net is not None else None
            if wanted is not None and row.capacity_ma < wanted.milliamps:
                issues.append(
                    issue(
                        "analysis.current-exceeded",
                        f"{row.kind} of net {row.net} on {row.layer} carries {row.capacity_ma} mA at a rise "
                        f"of {row.temp_rise_mk} mK by the fit, below the {wanted.milliamps} mA required",
                        where=row.where,
                    )
                )
        for index, wanted in enumerate(requirements.currents):
            if not any(wanted.select.matches(net, circuit) for net in circuit.nets):
                issues.append(
                    issue(
                        "analysis.requirement-unmatched",
                        f"current row {index} ({wanted.select.text()}) matches no net of the design",
                        where=f"current[{index}]",
                    )
                )
    summary: dict[str, object] = {
        "rows": len(rows),
        "skipped": sum(missing.values()),
        "nets": {
            name: {"capacity_ma": row.capacity_ma, "where": row.where}
            for name, row in sorted(weakest.items())
        },
        "fit": SOURCE_OF_FIT,
    }
    ordered = sorted_issues(issues)
    return AnalysisReport(tuple(rows), ordered, summary, report_evidence(ordered))


__all__ = [
    "FIT_EXP_AREA",
    "FIT_EXP_RISE",
    "FIT_K_EXTERNAL",
    "FIT_K_INTERNAL",
    "FIT_MAX_EXTERNAL_MA",
    "FIT_MAX_INTERNAL_MA",
    "FIT_MAX_RISE_MK",
    "FIT_MAX_WIDTH_NM",
    "SOURCE_OF_FIT",
    "MIL_NM",
    "analyze_current",
    "barrel_area_nm2",
    "capacity_ma",
    "in_range",
]
