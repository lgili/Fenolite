# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The deadline of the power analysis and of the split (change c0503; capability board-analyses, "Deadline
of power and split"), with a fake clock, on the authored plane bench of ``tests/_power.py``."""

from __future__ import annotations

import pytest
from _power import plane_board

from fenolite.analysis import analyze_power, load_requirements
from fenolite.analysis import split as split_module
from fenolite.analysis.deadline import Deadline
from fenolite.analysis.pour import pour_copper
from fenolite.analysis.power import PowerReport
from fenolite.analysis.requirements import SCHEMA
from fenolite.analysis.split import analyze_split

RHO = 20_000
"""An illustrative resistivity in picoohm-metres; Fenolite ships none."""
GRID = 200_000
"""The cell of the split here: coarser than the default, to keep the test short."""
ROW = '[[path]]\nfrom = ["J1-1"]\nto = ["U1-1"]\nmilliamps = 20000\ntemp_rise_mk = 10000\ndrop_mv = 1\n'


class Clock:
    """A fake clock: 0 until ``after`` readings were taken, then far past any deadline."""

    def __init__(self, after: int) -> None:
        self.after = after
        self.readings = 0

    def __call__(self) -> int:
        self.readings += 1
        return 0 if self.readings <= self.after else 10**18


def test_deadline_clock() -> None:
    clock = Clock(2)
    deadline = Deadline(10, clock)
    assert not deadline.passed() and deadline.passed()
    assert not Deadline(5, lambda: 7).passed() and Deadline(0, lambda: 7).passed()
    with pytest.raises(ValueError, match="0 seconds or more"):
        Deadline(-1)


def _power(deadline: Deadline | None) -> PowerReport:
    design, pads = plane_board(48)
    requirements = load_requirements(f'schema = "{SCHEMA}"\n' + ROW)
    return analyze_power(
        design,
        pads=pads,
        requirements=requirements,
        via_plating=25_000,
        resistivity_pohm_m=RHO,
        deadline=deadline,
    )


def test_a_cut_run_is_sound() -> None:
    """Scenario "A cut run is sound": the clock passes after the first region reached stage 1."""
    whole = _power(None)
    cut = _power(Deadline(1, Clock(2)))
    (full,), (part,) = whole.rows, cut.rows
    assert full.complete and not part.complete
    assert full.resistance_uohm is not None and part.resistance_uohm is not None
    assert part.resistance_uohm.low <= full.resistance_uohm.low
    assert part.resistance_uohm.high is None or (
        full.resistance_uohm.high is not None and part.resistance_uohm.high >= full.resistance_uohm.high
    )
    assert [i.code for i in cut.issues].count("analysis.deadline") == 1
    assert "analysis.deadline" not in [i.code for i in whole.issues]
    errors = {(i.code, i.where) for i in cut.issues if i.severity == "error"}
    assert errors <= {(i.code, i.where) for i in whole.issues if i.severity == "error"}


def test_a_cut_split_keeps_a_coarse_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A cut split keeps a coarse level": the clock passes once two levels are solved."""
    design, pads = plane_board(48)
    power = analyze_power(
        design, pads=pads, paths=((("J1-1",), ("U1-1",)),), via_plating=25_000, resistivity_pohm_m=RHO
    )
    pour = pour_copper(design, pads=pads, boundary=None, grid=GRID)
    kwargs = {"pads": pads, "pour": pour, "power": power, "via_plating": 25_000, "resistivity_pohm_m": RHO}
    (whole,) = analyze_split(design, **kwargs).rows  # type: ignore[arg-type]
    assert whole.complete and whole.cell_nm == GRID
    clock = Clock(10**9)
    solve = split_module._solve  # pyright: ignore[reportPrivateUsage]
    levels: list[int] = []

    def counted(*args: object, **kw: object) -> object:
        found = solve(*args, **kw)  # type: ignore[arg-type]
        levels.append(1)
        if len(levels) == 2:
            clock.after = clock.readings  # every later reading is past the deadline
        return found

    monkeypatch.setattr(split_module, "_solve", counted)
    report = analyze_split(design, deadline=Deadline(1, clock), **kwargs)  # type: ignore[arg-type]
    (row,) = report.rows
    assert not row.complete and row.cell_nm >= 4 * GRID and row.elements
    assert [i.code for i in report.issues] == ["analysis.deadline"]
    shares = {e.where: e.share_permille for e in whole.elements}
    for element in row.elements:
        assert abs((element.share_permille or 0) - (shares[element.where] or 0)) <= 50, element
