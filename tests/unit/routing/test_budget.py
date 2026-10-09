# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The one time budget of a routing job (capability routing, "Routing time budget"; change c0109): the
clock, the kill of the process under way, and what a plugin keeps and reports when the budget ends."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from _fakerouter import create_fake_router

from fenolite.cli import explain
from fenolite.routing.budget import Budget, RunOutcome, exhausted
from fenolite.routing.codes import ISSUE_CODES
from fenolite.routing.direct import DirectRouter
from fenolite.routing.plugins.kicad import routingtools
from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from fenolite.routing.plugins.specctra import freerouting
from fenolite.routing.protocol import RouterRun, RoutingJob, RoutingResult
from tests.unit.routing.test_routingtools import grouped_job, recorded

SLEEP = "import time; time.sleep(30)"


class Clock:
    """A clock a test moves by hand."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_budget_clock_spent_and_left() -> None:
    clock = Clock()
    budget = Budget(10, clock=clock)
    assert (budget.seconds, budget.spent(), budget.left()) == (10.0, 0.0, 10.0)
    clock.now += 4
    assert (budget.spent(), budget.left()) == (4.0, 6.0)
    clock.now += 60
    assert (budget.spent(), budget.left()) == (64.0, 0.0), "left() never goes below zero"


@pytest.mark.parametrize("seconds", [0, -1, float("nan")])
def test_budget_must_be_positive(seconds: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        Budget(seconds)


def test_budget_runs_a_process_and_returns_its_output(tmp_path: Path) -> None:
    code = "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(3)"
    done = Budget(60).run([sys.executable, "-c", code], cwd=tmp_path)
    assert isinstance(done, RunOutcome)
    assert (done.returncode, done.stdout.strip(), done.stderr.strip()) == (3, "out", "err")
    assert done.cut is False and done.started is True and done.seconds > 0


def test_budget_kills_a_sleeping_child_at_the_end(tmp_path: Path) -> None:
    """The kill: a child that sleeps 30 s is stopped when the 0.5 s are spent."""
    budget = Budget(0.5)
    began = time.monotonic()
    done = budget.run([sys.executable, "-c", SLEEP], cwd=tmp_path)
    took = time.monotonic() - began
    assert done.cut is True and done.returncode is None and done.started is True
    assert 0.4 < took < 20, took
    assert budget.left() == 0.0 and budget.spent() >= 0.5


def test_budget_starts_no_process_once_spent(tmp_path: Path) -> None:
    clock = Clock()
    budget = Budget(1, clock=clock)
    clock.now += 2
    marker = tmp_path / "ran"
    done = budget.run([sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"], cwd=tmp_path)
    assert done.cut is True and done.started is False and done.seconds == 0.0
    assert not marker.exists()


def test_budget_gives_each_process_the_time_left(tmp_path: Path) -> None:
    """Two processes share one budget: the second gets what the first left."""
    budget = Budget(2.0)
    first = budget.run([sys.executable, "-c", "import time; time.sleep(0.8)"], cwd=tmp_path)
    assert first.cut is False and first.returncode == 0
    began = time.monotonic()
    second = budget.run([sys.executable, "-c", SLEEP], cwd=tmp_path)
    assert second.cut is True and time.monotonic() - began < 1.9


def test_budget_codes_and_their_explanations() -> None:
    assert ISSUE_CODES["route.budget-exhausted"] == "warning"
    assert ISSUE_CODES["route.optimizer-cut"] == "info"
    for code in ("route.budget-exhausted", "route.optimizer-cut"):
        entry = explain.explain(code)
        assert entry is not None and entry.see == "route"
        assert "route again" in entry.fix or "--timeout" in entry.fix
    issue = exhausted(2, 3, 4, "router")
    assert (issue.code, issue.severity, issue.where) == ("route.budget-exhausted", "warning", "router")
    assert "2 s" in issue.message and "3 net(s)" in issue.message and "4 net(s)" in issue.message


def test_budget_defaults_of_the_plugins() -> None:
    assert routingtools.DEFAULT_BUDGET == 900 and freerouting.DEFAULT_BUDGET == 900
    run = RouterRun(("A",), 0, 1.5, "done")
    assert RoutingResult(runs=(run,), not_attempted=("B",)).runs == (run,)
    assert RoutingResult().runs == () and RoutingResult().not_attempted == ()


def test_budget_is_ignored_by_the_direct_router() -> None:
    job = grouped_job({"A1": 0.2}, budget=0.000001)
    result = DirectRouter().route(job)
    assert result.routed == ("A1",) and result.runs == () and result.not_attempted == ()
    assert not result.issues


# --- the KiCadRoutingTools plugin inside a budget ------------------------------------------------------


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[KicadRoutingToolsRouter, Path]:
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(Path(__file__).resolve().parents[3] / "src"))
    runs = tmp_path / "runs.jsonl"
    monkeypatch.setenv("FAKE_ROUTER_RUNS", str(runs))
    return KicadRoutingToolsRouter(create_fake_router(tmp_path), sys.executable), runs


def test_budget_second_group_cut(fake, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Second group cut"."""
    router, runs = fake
    monkeypatch.setenv("FAKE_ROUTER_SLEEP_NET", "B1")
    job: RoutingJob = grouped_job({"A1": 0.2, "B1": 0.4}, budget=2)
    began = time.monotonic()
    result = router.route(job)
    assert time.monotonic() - began < 4.5, "the sleeping run was killed at the end of the budget"
    a1 = job.design.nets_by_name["A1"].id
    assert [track.net_id for track in result.tracks] == [a1]
    assert result.routed == ("A1",) and result.unrouted == ("B1",) and result.not_attempted == ()
    assert [run.outcome for run in result.runs] == ["done", "cut"]
    assert sum(run.seconds for run in result.runs) <= 2.5
    (issue,) = result.issues
    assert (issue.code, issue.severity) == ("route.budget-exhausted", "warning")
    assert "2 s" in issue.message and "(1 net(s))" in issue.message and "0 net(s)" in issue.message
    assert len(recorded(runs)) == 2


def test_budget_runs_not_attempted(fake, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Runs not attempted"."""
    router, runs = fake
    monkeypatch.setenv("FAKE_ROUTER_SLEEP_NET", "B1")
    result = router.route(grouped_job({"A1": 0.2, "B1": 0.4, "C1": 0.6, "C2": 0.6}, budget=2))
    assert [(run.nets, run.outcome) for run in result.runs] == [(("A1",), "done"), (("B1",), "cut")]
    assert result.not_attempted == ("C1", "C2")
    assert result.unrouted == ("B1", "C1", "C2") and result.routed == ("A1",)
    assert len(recorded(runs)) == 2, "no process starts once the budget is spent"
    (issue,) = result.issues
    assert issue.code == "route.budget-exhausted" and "2 net(s) were not attempted" in issue.message
    assert not [found for found in result.issues if found.code == "route.tool-failed"]


def test_budget_not_reached(fake) -> None:
    """Scenario "Budget not reached": the default budget, two groups."""
    router, runs = fake
    result = router.route(grouped_job({"A1": 0.2, "B1": 0.4}))
    assert [run.outcome for run in result.runs] == ["done", "done"]
    assert result.not_attempted == () and not result.issues and len(recorded(runs)) == 2


def test_budget_of_the_job_wins_over_the_constructor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(Path(__file__).resolve().parents[3] / "src"))
    monkeypatch.setenv("FAKE_ROUTER_MODE", "sleep")
    router = KicadRoutingToolsRouter(create_fake_router(tmp_path), sys.executable, budget=60)
    result = router.route(grouped_job({"A1": 0.2}, budget=0.3))
    (issue,) = result.issues
    assert issue.code == "route.budget-exhausted" and "0.3 s" in issue.message
