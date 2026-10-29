# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The split of a power path's current on a raster of its copper (change c0213; capability board-analyses,
"Current split"), on the authored benches of ``tests/_power.py``, bracketed by the interval of ``power`` on
the same benches. Every thickness and resistivity here is illustrative."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from _coppercheck import ident
from _power import branch, two_strips, via_array

from fenolite.analysis import analyze_power, load_requirements
from fenolite.analysis.pour import pour_copper
from fenolite.analysis.power import Interval, PowerReport
from fenolite.analysis.requirements import SCHEMA
from fenolite.analysis.split import SplitReport, SplitRow, analyze_split
from fenolite.backends.base import BoardPad
from fenolite.core.evidence import Level
from fenolite.core.units import Nm
from fenolite.model.board import StackLayer, Stackup
from fenolite.model.design import Design

RHO = 20_000
"""An illustrative resistivity in picoohm-metres; Fenolite ships none."""
PATHS = ((("J1-1",), ("U1-1",)),)
MM = 1_000_000


def stacked(design: Design) -> Design:
    """``design`` with a stack-up of 35 µm of copper on each side of 1.53 mm of laminate."""
    assert design.board is not None
    entries = (("F.Cu", "copper", 35_000), ("core", "dielectric", 1_530_000), ("B.Cu", "copper", 35_000))
    layers = tuple(
        StackLayer(id=ident("stk", n), name=name, kind=kind, thickness=thickness)  # type: ignore[arg-type]
        for n, (name, kind, thickness) in enumerate(entries)
    )
    board = dataclasses.replace(design.board, stackup=Stackup(id=ident("stu", 1), layers=layers))
    return dataclasses.replace(design, board=board)


def solve(
    design: Design,
    pads: tuple[BoardPad, ...],
    *,
    grid: int,
    thickness: Mapping[str, Nm] | None = None,
    plating: Nm | None = None,
    power: PowerReport | None = None,
) -> tuple[PowerReport, SplitReport]:
    if power is None:
        power = analyze_power(
            design,
            pads=pads,
            paths=PATHS,
            copper_thickness=thickness,
            via_plating=plating,
            resistivity_pohm_m=RHO,
        )
    pour = pour_copper(design, pads=pads, boundary=None, grid=grid)
    split = analyze_split(
        design,
        pads=pads,
        pour=pour,
        power=power,
        copper_thickness=thickness,
        via_plating=plating,
        resistivity_pohm_m=RHO,
    )
    return power, split


def shares(row: SplitRow) -> dict[str, int | None]:
    return {element.where: element.share_permille for element in row.elements}


def test_two_strips_share_by_thickness() -> None:
    """Scenario "Two strips share by thickness": 70 µm against 35 µm carry two thirds and one third, and the
    resistance lies in the interval of ``power``, here one microohm wide."""
    design, pads = two_strips()
    power, split = solve(design, pads, grid=MM // 2, thickness={"F.Cu": 70_000, "B.Cu": 35_000})
    (row,) = split.rows
    assert shares(row) == {"/strip-B.Cu#0": 333, "/strip-F.Cu#0": 667}
    assert row.bounds == power.rows[0].resistance_uohm == Interval(685, 686)
    assert row.resistance_uohm == 686 and row.within is True and row.converged
    assert split.issues == () and split.evidence.level is Level.INFERRED
    # equal copper: half each, and the interval of power is exact
    power, split = solve(design, pads, grid=MM // 2, thickness={"*": 50_000})
    (row,) = split.rows
    assert shares(row) == {"/strip-B.Cu#0": 500, "/strip-F.Cu#0": 500}
    assert row.bounds == Interval(720, 720) and row.resistance_uohm == 720 and row.within is True


def test_vias_in_parallel() -> None:
    """Scenario "Vias in parallel": the four vias carry the whole current, the outer two more than the inner
    two, and each region carries all of it."""
    design, pads = via_array(4)
    _, split = solve(stacked(design), pads, grid=MM // 4, plating=25_000)
    (row,) = split.rows
    vias = {e.where: e.share_permille for e in row.elements if e.kind == "via"}
    assert sorted(vias) == [f"/via[{n}]" for n in range(4)]
    assert all(value is not None for value in vias.values())
    assert abs(sum(value or 0 for value in vias.values()) - 1000) <= 2
    assert (vias["/via[0]"] or 0) > (vias["/via[1]"] or 0) and vias["/via[0]"] == vias["/via[3]"]
    assert [e.share_permille for e in row.elements if e.kind == "fill"] == [1000, 1000]
    assert row.within is True and row.bounds is not None and row.bounds.high is not None
    # without a plating the barrels have no conductance: the path is not split
    _, bare = solve(stacked(design), pads, grid=MM // 4, thickness={"*": 35_000})
    assert bare.rows == () and [(i.code, i.where) for i in bare.issues] == [
        ("analysis.input-missing", "via plating")
    ]
    assert bare.summary["unsolved"] == 1


def test_a_branch_carries_nothing() -> None:
    """The side track to ``C1-1`` is no part of the path: it carries no current. ``power`` counts the track
    from the centres of the pads, the solve holds each pad at one potential: on a path of tracks the solve
    lies below the interval by the copper inside the pads."""
    design, pads = branch()
    row = '[[path]]\nfrom = ["J1-1"]\nto = ["U1-1"]\nmilliamps = 3000\ntemp_rise_mk = 10000\n'
    text = f'schema = "{SCHEMA}"\n' + row
    power = analyze_power(
        design,
        pads=pads,
        requirements=load_requirements(text),
        copper_thickness={"*": 35_000},
        resistivity_pohm_m=RHO,
    )
    _, split = solve(design, pads, grid=MM // 4, thickness={"*": 35_000}, power=power)
    (row,) = split.rows
    assert [(e.where, e.share_permille, e.milliamps) for e in row.elements] == [
        ("/main", 1000, 3000),
        ("/side", 0, 0),
    ]
    assert row.bounds is not None and row.resistance_uohm is not None
    assert row.resistance_uohm < row.bounds.low and row.within is False


def test_thickness_missing() -> None:
    design, pads = two_strips()
    _, split = solve(design, pads, grid=MM // 2)
    assert split.rows == () and [(i.code, i.where) for i in split.issues] == [
        ("analysis.input-missing", "copper thickness")
    ]
