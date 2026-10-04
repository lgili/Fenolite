# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The opt-in ``render`` stage with a fake ``Plotter`` (capability verification-loop, "Render stage"; change
c0024). No backend module is imported."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fakes import FakeFillOracle, FakeOracle, FakeValidator, project

from fenolite.backends.base import PlotOutcome, Plotter, PlotView, ProjectSet
from fenolite.checks import DEFAULT_STAGES, ISSUE_CODES, STAGE_ORDER, run_checks
from fenolite.checks.render import render_stage
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level

PLOTTED = Evidence(Level.INFERRED, oracle="fake 1.0", hypotheses=("H-FAKE-PLOT",))
NAMES = ("top.png", "front.svg", "bottom.png", "back.svg")


def outcome(*names: str, failed: tuple[str, ...] = (), message: str = "") -> PlotOutcome:
    views = tuple(PlotView(name, 10 + i, f"{i:064x}") for i, name in enumerate(names))
    return PlotOutcome(views, "1.0", failed, message, PLOTTED if views else Evidence())


@dataclass
class FakePlotter:
    result: PlotOutcome = field(default_factory=lambda: outcome(*NAMES))
    name: str = "fake"
    calls: list[ProjectSet] = field(default_factory=lambda: [])

    def plot(self, project: ProjectSet) -> PlotOutcome:
        self.calls.append(project)
        return self.result


def test_fake_satisfies_the_protocol() -> None:
    assert isinstance(FakePlotter(), Plotter)


def test_stage_order_and_default_set() -> None:
    assert STAGE_ORDER[-1] == "render"
    assert "render" not in DEFAULT_STAGES and DEFAULT_STAGES == STAGE_ORDER[:-2]
    assert ISSUE_CODES["render.failed"] == ("warning",)


def test_opt_in_default_runs_no_plot() -> None:
    plotter = FakePlotter()
    report = run_checks(
        project=project(), model=None, built=False, validator=FakeValidator(), oracle=FakeOracle(),
        plotter=plotter,
        fill_oracle=FakeFillOracle(),
    )  # fmt: skip
    assert [s.name for s in report.stages] == list(DEFAULT_STAGES)
    assert plotter.calls == []


def test_views_in_the_summary() -> None:
    plotter = FakePlotter()
    report = run_checks(
        project=project(), stages=("render",), model=None, built=False, validator=None, oracle=None,
        plotter=plotter,
    )  # fmt: skip
    (stage,) = report.stages
    assert stage.name == "render" and stage.status == "ok" and stage.issues == ()
    assert stage.summary["tool_version"] == "1.0"
    views = stage.summary["views"]
    assert isinstance(views, list)
    assert [v["name"] for v in views] == sorted(NAMES)
    assert set(views[0]) == {"name", "bytes", "sha256"}
    assert stage.evidence == PLOTTED and report.evidence == PLOTTED
    assert len(plotter.calls) == 1


def test_a_failed_view_is_a_warning_never_an_error() -> None:
    result = outcome("front.svg", "back.svg", failed=("top.png", "bottom.png"), message="exit 1: no GL")
    stage = render_stage(FakePlotter(result), project())
    assert stage.status == "ok"
    assert [(i.code, i.severity, i.where) for i in stage.issues] == [
        ("render.failed", "warning", "bottom.png"),
        ("render.failed", "warning", "top.png"),
    ]
    assert all("no GL" in i.message for i in stage.issues)
    nothing = render_stage(FakePlotter(outcome(failed=NAMES)), project())
    assert nothing.status == "ok" and len(nothing.issues) == 4 and nothing.evidence == Evidence()


def test_read_refused_skips_the_stage() -> None:
    plotter = FakePlotter()
    validator = FakeValidator(error=FormatError("bad", file="p/board.kicad_pcb"))
    report = run_checks(
        project=project(), stages=("roundtrip", "render"), model=None, built=False, validator=validator,
        oracle=None, plotter=plotter,
    )  # fmt: skip
    render = report.stages[-1]
    assert render.name == "render" and render.status == "skipped" and render.reason == "read-refused"
    assert plotter.calls == []


def test_selected_without_a_plotter_is_a_bug() -> None:
    with pytest.raises(ValueError, match="no plotter"):
        run_checks(
            project=project(), stages=("render",), model=None, built=False, validator=None, oracle=None
        )
