# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCadRoutingTools adapter lifts new copper and turns process failures into issues."""

from __future__ import annotations

import json
import sys
from dataclasses import replace as dataclasses_replace
from pathlib import Path

import pytest
from _fakerouter import create_fake_router

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.evidence import Level
from fenolite.routing.merge import apply
from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from fenolite.routing.protocol import JobNet, JobPad, RoutingJob
from tests.unit.routing._designs import named_design, routing_design


@pytest.fixture(autouse=True)
def fake_process_import_path(monkeypatch: pytest.MonkeyPatch) -> None:
    source = Path(__file__).resolve().parents[3] / "src"
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(source))


def _job():
    design = routing_design()
    net = next(item for item in design.circuit.nets if item.name == "B")
    pads = design.by_net[net.name]
    job_net = JobNet(
        net.name,
        net.id,
        tuple(JobPad("J1", pad.number, net.name, pad.position, pad.layers, pad.drill) for pad in pads),
        250_000,
        200_000,
        600_000,
        300_000,
    )
    return RoutingJob(design, (job_net,), ("F.Cu", "B.Cu"))


def test_lifts_new_copper_and_runs_in_a_temporary_folder(tmp_path, monkeypatch) -> None:
    checkout = create_fake_router(tmp_path)
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_ROUTER_RECORD", str(record))
    router = KicadRoutingToolsRouter(checkout, sys.executable)

    result = router.route(_job())

    assert router.available().available
    assert result.routed == ("B",) and len(result.tracks) == 1, result
    assert result.tracks[0].net_id == _job().nets[0].net_id
    assert result.evidence.level is Level.UNVERIFIED
    saved = json.loads(record.read_text(encoding="utf-8"))
    assert "--nets" in saved["argv"] and "B" in saved["argv"]
    argv = saved["argv"]
    assert "--track-width" in argv and "--via-size" in argv and "--via-drill" in argv
    # change c0109: the sizes are kept exact, the project file is left alone, and the tool reads each
    # class's clearance from the project file of the copy set
    assert argv[argv.index("--escalation") + 1] == "off" and "--no-fix-drc-settings" in argv
    assert "--clearance" not in argv
    assert argv[0].endswith("fenolite-routing.kicad_pcb") and argv[1].endswith("routed-0.kicad_pcb")
    assert [(run.nets, run.tier, run.outcome) for run in result.runs] == [(("B",), 0, "done")]
    assert result.not_attempted == ()
    project = Path(__file__).resolve().parents[3]
    assert "fenolite-route-" in saved["cwd"]
    assert not Path(saved["cwd"]).is_relative_to(project)


def test_failure_is_returned_as_an_issue(tmp_path, monkeypatch) -> None:
    checkout = create_fake_router(tmp_path)
    monkeypatch.setenv("FAKE_ROUTER_MODE", "fail")
    result = KicadRoutingToolsRouter(checkout, sys.executable).route(_job())
    assert result.tracks == () and result.unrouted == ("B",)
    assert result.issues[0].code == "route.tool-failed"
    assert "boom from fake router" in result.issues[0].message
    assert [run.outcome for run in result.runs] == ["failed"]


def test_missing_router_is_available_as_a_readiness_result(monkeypatch) -> None:
    monkeypatch.delenv("FENOLITE_KRT", raising=False)
    status = KicadRoutingToolsRouter(path=None, python=sys.executable).available()
    assert not status.available and "FENOLITE_KRT" in status.reason


def test_budget_and_unpinned_checkout_are_reported(tmp_path, monkeypatch) -> None:
    """Reaching the budget is a warning, not ``route.tool-failed`` (change c0109); the constructor's
    budget serves a job that names none."""
    checkout = create_fake_router(tmp_path, version="0.23.0")
    monkeypatch.setenv("FAKE_ROUTER_MODE", "sleep")
    result = KicadRoutingToolsRouter(checkout, sys.executable, budget=0.05).route(_job())
    assert {issue.code for issue in result.issues} == {"route.budget-exhausted", "route.tool-unpinned"}
    assert result.unrouted == ("B",) and [run.outcome for run in result.runs] == ["cut"]


def test_router_removal_is_reported_but_not_lifted(tmp_path, monkeypatch) -> None:
    checkout = create_fake_router(tmp_path)
    monkeypatch.setenv("FAKE_ROUTER_MODE", "drop")
    result = KicadRoutingToolsRouter(checkout, sys.executable).route(_job())
    assert any(issue.code == "route.copper-removed" for issue in result.issues)
    assert result.tracks == ()
    assert apply(_job().design, result).board == _job().design.board


# --- groups, tiers and options (change c0109) ---------------------------------------------------------

MM = 1_000_000


def grouped_job(
    widths: dict[str, float],
    *,
    tiers: dict[str, int] | None = None,
    budget: float | None = None,
    **options: str,
) -> RoutingJob:
    """A job whose nets are the keys of ``widths`` (track width in mm), with the same via sizes."""
    design = named_design(*widths)
    tiers = tiers or {}
    nets = []
    for name, width in widths.items():
        net = design.nets_by_name[name]
        pads = tuple(
            JobPad("J1", pad.number, name, pad.position, pad.layers, pad.drill) for pad in design.by_net[name]
        )
        nets.append(
            JobNet(name, net.id, pads, round(width * MM), 200_000, 600_000, 300_000, tier=tiers.get(name, 0))
        )
    nets.sort(key=lambda item: (item.tier, item.name))
    return RoutingJob(design, tuple(nets), ("F.Cu", "B.Cu"), options, budget=budget)


def recorded(path: Path) -> list[dict]:
    """The runs the fake recorded, in order."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def width_of(run: dict) -> str:
    return run["argv"][run["argv"].index("--track-width") + 1]


@pytest.fixture
def fake(tmp_path, monkeypatch) -> tuple[KicadRoutingToolsRouter, Path]:
    runs = tmp_path / "runs.jsonl"
    monkeypatch.setenv("FAKE_ROUTER_RUNS", str(runs))
    return KicadRoutingToolsRouter(create_fake_router(tmp_path), sys.executable), runs


def test_groups_one_run_per_size_group(fake) -> None:
    """Scenario "One run per group"."""
    router, runs = fake
    result = router.route(grouped_job({"A1": 0.2, "A2": 0.2, "B1": 0.4}))
    saved = recorded(runs)
    assert [(run["nets"], width_of(run)) for run in saved] == [(["A1", "A2"], "0.2"), (["B1"], "0.4")]
    assert [(run.nets, run.outcome) for run in result.runs] == [(("A1", "A2"), "done"), (("B1",), "done")]
    # the fake routes the first net of a run only: the others of the run stay unrouted
    assert result.routed == ("A1", "B1") and result.unrouted == ("A2",)
    assert len(result.tracks) == 2 and not [issue for issue in result.issues]
    # the second run was given the board with the first run's track
    second = read_board(saved[1]["board"], file="second.kicad_pcb")
    assert second.board is not None and len(second.board.tracks) == 1


def test_groups_follow_the_first_net_and_the_via_sizes() -> None:
    from fenolite.routing.plugins.kicad.routingtools import plan_runs

    job = grouped_job({"A1": 0.2, "B1": 0.4, "C1": 0.2})
    assert [[net.name for net in run] for run in plan_runs(job.nets)] == [["A1", "C1"], ["B1"]]
    wide_via = dataclasses_replace(job.nets[2], via_diameter=800_000)
    nets = (job.nets[0], job.nets[1], wide_via)
    assert [[net.name for net in run] for run in plan_runs(nets)] == [["A1"], ["B1"], ["C1"]]
    assert [[net.name for net in run] for run in plan_runs(job.nets, 1)] == [["A1"], ["C1"], ["B1"]]


def test_groups_split_by_the_option(fake) -> None:
    """Scenario "Groups split by the option"."""
    router, runs = fake
    result = router.route(grouped_job({"A1": 0.2, "A2": 0.2, "B1": 0.4}, **{"group-nets": "1"}))
    saved = recorded(runs)
    assert [run["nets"] for run in saved] == [["A1"], ["A2"], ["B1"]]
    assert all("--group-nets" not in run["argv"] for run in saved)
    assert result.routed == ("A1", "A2", "B1") and not result.issues


def test_tool_fails_on_one_group(fake, monkeypatch) -> None:
    """Scenario "Tool fails": the first run's copper is kept and the failed run names its nets."""
    router, runs = fake
    monkeypatch.setenv("FAKE_ROUTER_FAIL_NET", "B1")
    result = router.route(grouped_job({"A1": 0.2, "A2": 0.2, "B1": 0.4}))
    assert [run.outcome for run in result.runs] == ["done", "failed"]
    assert len(result.tracks) == 1 and result.routed == ("A1",) and "B1" in result.unrouted
    (issue,) = result.issues
    assert (issue.code, issue.severity, issue.where) == ("route.tool-failed", "error", "B1")
    assert "boom" in issue.message and issue.message.startswith("B1: ")


def test_tiers_are_routed_one_after_the_other(fake) -> None:
    """Scenario "Two tiers with KiCadRoutingTools"."""
    router, runs = fake
    job = grouped_job({"CLK": 0.2, "D0": 0.2}, tiers={"CLK": 0, "D0": 1})
    result = router.route(job)
    saved = recorded(runs)
    assert [run["nets"] for run in saved] == [["CLK"], ["D0"]]
    assert [(run.nets, run.tier) for run in result.runs] == [(("CLK",), 0), (("D0",), 1)]
    second = read_board(saved[1]["board"], file="second.kicad_pcb")
    assert second.board is not None
    clk = next(net.id for net in second.circuit.nets if net.name == "CLK")
    assert [track.net_id for track in second.board.tracks] == [clk]
    first = read_board(saved[0]["board"], file="first.kicad_pcb")
    assert first.board is not None and first.board.tracks == ()


def test_tier_comes_before_the_name(fake) -> None:
    router, runs = fake
    router.route(grouped_job({"A": 0.2, "Z": 0.2}, tiers={"A": 1, "Z": 0}))
    assert [run["nets"] for run in recorded(runs)] == [["Z"], ["A"]]


def test_own_options_are_ignored_and_others_reach_the_tool(fake) -> None:
    router, runs = fake
    options = {
        "nets": "X*",
        "output": "o.kicad_pcb",
        "overwrite": "1",
        "group-nets": "0",
        "ordering": "original",
    }
    result = router.route(grouped_job({"A1": 0.2}, **options))
    (run,) = recorded(runs)
    argv = run["argv"]
    assert run["nets"] == ["A1"] and "--output" not in argv and "--overwrite" not in argv
    assert argv[argv.index("--ordering") + 1] == "original" and argv.count("--nets") == 1
    ignored = sorted(issue.where for issue in result.issues if issue.code == "route.option-ignored")
    assert ignored == ["group-nets", "nets", "output", "overwrite"]
    assert all(issue.severity == "warning" for issue in result.issues)


def test_escalation_option_comes_after_the_default(fake) -> None:
    """``--router-option escalation=board`` is appended after ``--escalation off``, so the tool's
    argument parser takes the caller's value."""
    router, runs = fake
    router.route(grouped_job({"A1": 0.2}, escalation="board"))
    argv = recorded(runs)[0]["argv"]
    positions = [index for index, word in enumerate(argv) if word == "--escalation"]
    assert [argv[index + 1] for index in positions] == ["off", "board"]


# --- plane layers and layer sets (change c0107) --------------------------------------------------------


def test_constraint_not_sent(tmp_path, monkeypatch) -> None:
    """Scenario "KiCadRoutingTools told nothing" (change c0107): one warning naming the plane layers, and
    the arguments of a job without them."""
    import dataclasses

    checkout = create_fake_router(tmp_path)
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_ROUTER_RECORD", str(record))
    router = KicadRoutingToolsRouter(checkout, sys.executable)
    plain = router.route(_job())
    assert not [i for i in plain.issues if i.code == "route.constraint-not-sent"]
    plain_args = json.loads(record.read_text(encoding="utf-8"))["argv"]
    job = dataclasses.replace(_job(), plane_layers=("In1.Cu",))
    result = router.route(job)
    (found,) = [i for i in result.issues if i.code == "route.constraint-not-sent"]
    assert found.severity == "warning" and "In1.Cu" in found.message
    argv = json.loads(record.read_text(encoding="utf-8"))["argv"]
    assert argv[3:] == plain_args[3:] and result.routed == plain.routed
    kept = dataclasses.replace(_job(), nets=(dataclasses.replace(_job().nets[0], layers=("F.Cu",)),))
    (found,) = [i for i in router.route(kept).issues if i.code == "route.constraint-not-sent"]
    assert "B" in found.message and "plane" not in found.message.split(":")[0]


def test_rules_read_from_a_file_reach_the_run_folder(tmp_path, monkeypatch) -> None:
    """The rules of the job's design, read from a rules file by ``route`` (change c0107), are written back
    into the run's rules file with their own names: a set read from a file is not lowered again."""
    import dataclasses

    from fenolite.backends.kicad.dru import read_rules

    text = (
        "(version 1)\n"
        '(rule "sig_outer" (layer "B.Cu") (condition "A.NetName == \'B\'") (constraint disallow track))\n'
        '(rule "wide" (constraint clearance (min 0.3mm)))\n'
    )
    checkout = create_fake_router(tmp_path)
    runs = tmp_path / "runs.jsonl"
    monkeypatch.setenv("FAKE_ROUTER_RUNS", str(runs))
    job = dataclasses.replace(_job(), design=dataclasses.replace(_job().design, rules=read_rules(text)))
    result = KicadRoutingToolsRouter(checkout, sys.executable).route(job)
    assert not [i for i in result.issues if i.severity == "error"], result.issues
    assert result.routed == ("B",)
    (run,) = [json.loads(line) for line in runs.read_text(encoding="utf-8").splitlines()]
    assert '"sig_outer"' in run["rules"] and "(constraint disallow track)" in run["rules"]
    assert '"wide"' in run["rules"]
