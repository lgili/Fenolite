# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A router reports each of its tool processes while it works (capability routing, "Router runs reported
for progress and resumption"; change c0120). Hermetic: the fake KiCadRoutingTools, with ``group-nets=1``
for one process per net (change c0109 routes a group of nets per process); the Freerouting plugin's unit
is tested in ``test_freerouting.py``, beside its fake java."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest
from _fakerouter import create_fake_router
from _fivenets import NETS, five_nets, job_nets

from fenolite.core.progress import NULL_PROGRESS
from fenolite.routing.direct import DirectRouter
from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from fenolite.routing.protocol import FinishedRun, RoutingJob

ROOT = Path(__file__).resolve().parents[3]


class Recorder:
    """A ``Progress`` that keeps what it was told."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, int | None, int | None, str]] = []

    def step(self, name: str, *, index: int | None = None, total: int | None = None) -> None:
        self.events.append(("step", name, index, total, ""))

    def done(self, name: str, *, detail: str = "") -> None:
        self.events.append(("done", name, None, None, detail))


def test_finished_run_is_a_frozen_value() -> None:
    run = FinishedRun(nets=("A",))
    assert (run.tracks, run.arcs, run.vias, run.tier, run.seconds) == ((), (), (), 0, 0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        run.tier = 1  # type: ignore[misc]
    job = RoutingJob(five_nets(), (), ("F.Cu",))
    assert job.on_run is None and job.progress is NULL_PROGRESS
    hash(run)


def test_one_call_per_finished_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "One call per finished process": three nets of which the second fails."""
    checkout = create_fake_router(tmp_path)
    starts = tmp_path / "starts.txt"
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(ROOT / "src"))
    monkeypatch.setenv("FAKE_ROUTER_FAIL_NETS", "N2")
    monkeypatch.setenv("FAKE_ROUTER_STARTS", str(starts))
    design = five_nets()
    runs: list[FinishedRun] = []
    started_at_call: list[list[str]] = []

    def on_run(run: FinishedRun) -> None:
        runs.append(run)
        started_at_call.append(starts.read_text(encoding="utf-8").split())

    recorder = Recorder()
    job = RoutingJob(
        design,
        job_nets(design, NETS[:3]),
        ("F.Cu", "B.Cu"),
        {"group-nets": "1"},
        on_run=on_run,
        progress=recorder,
    )
    result = KicadRoutingToolsRouter(checkout, sys.executable).route(job)

    assert [run.nets for run in runs] == [("N1",), ("N3",)]
    assert started_at_call == [["N1"], ["N1", "N2", "N3"]], "each call came before the next process"
    assert starts.read_text(encoding="utf-8").split() == ["N1", "N2", "N3"]
    assert [(kind, name) for kind, name, *_ in recorder.events] == [
        ("step", "N1"), ("done", "N1"), ("step", "N2"), ("done", "N2"), ("step", "N3"), ("done", "N3"),
    ]  # fmt: skip
    assert [event[2:4] for event in recorder.events if event[0] == "step"] == [(1, 3), (2, 3), (3, 3)]
    assert [event[4] for event in recorder.events if event[0] == "done"] == ["routed", "failed", "routed"]
    assert result.routed == ("N1", "N3") and result.unrouted == ("N2",)
    assert tuple(item for run in runs for item in run.tracks) == result.tracks and len(result.tracks) == 2
    assert tuple(item for run in runs for item in run.vias) == result.vias
    assert tuple(item for run in runs for item in run.arcs) == result.arcs
    assert all(run.tier == 0 and run.seconds > 0 for run in runs)


def test_timeout_is_not_a_finished_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    checkout = create_fake_router(tmp_path)
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(ROOT / "src"))
    monkeypatch.setenv("FAKE_ROUTER_MODE", "sleep")
    design = five_nets()
    runs: list[FinishedRun] = []
    recorder = Recorder()
    job = RoutingJob(design, job_nets(design, NETS[:1]), ("F.Cu",), on_run=runs.append, progress=recorder)
    # the budget lets the process start and ends long before its sleep of 5 s does
    result = KicadRoutingToolsRouter(checkout, sys.executable, budget=2).route(job)
    assert runs == [] and result.unrouted == ("N1",)
    assert [(kind, name, detail) for kind, name, _, _, detail in recorder.events] == [
        ("step", "N1", ""), ("done", "N1", "timeout"),
    ]  # fmt: skip


def test_router_that_ignores_the_fields(tmp_path: Path) -> None:
    """Scenario "A router that ignores the fields": the direct router starts no process."""
    design = five_nets()
    runs: list[FinishedRun] = []
    recorder = Recorder()
    nets = job_nets(design)
    plain = DirectRouter().route(RoutingJob(design, nets, ("F.Cu", "B.Cu")))
    told = DirectRouter().route(
        RoutingJob(design, nets, ("F.Cu", "B.Cu"), on_run=runs.append, progress=recorder)
    )
    assert runs == [] and recorder.events == []
    assert told == plain and len(plain.tracks) == 5


def test_a_group_is_one_unit_and_one_finished_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``group-nets`` the nets of one tier and one size are one process (change c0109): one unit,
    named by its first net and the count of the others, and one finished run."""
    checkout = create_fake_router(tmp_path)
    starts = tmp_path / "starts.txt"
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(ROOT / "src"))
    monkeypatch.setenv("FAKE_ROUTER_STARTS", str(starts))
    design = five_nets()
    runs: list[FinishedRun] = []
    recorder = Recorder()
    job = RoutingJob(
        design, job_nets(design, NETS[:3]), ("F.Cu", "B.Cu"), on_run=runs.append, progress=recorder
    )
    result = KicadRoutingToolsRouter(checkout, sys.executable).route(job)
    assert starts.read_text(encoding="utf-8").split() == ["N1,N2,N3"]
    assert recorder.events == [
        ("step", "N1 and 2 more", 1, 1, ""),
        ("done", "N1 and 2 more", None, None, "routed"),
    ]
    (run,) = runs  # the fake adds one segment, on the first net of the group
    assert run.nets == ("N1",) and run.tracks == result.tracks and run.tier == 0
