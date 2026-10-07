# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite route`` keeps the copper of each finished router run and the same call made again reuses it
(capability cli-contract, "Resumable route jobs"; change c0120). Hermetic: a fake router that works one
net per "process" and reports each as the routing protocol asks."""

from __future__ import annotations

import os
import signal
from collections.abc import Iterator
from pathlib import Path

import pytest
from _checkcli import run
from _fivenets import NETS, SPAN, write_five_nets

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board
from fenolite.cli import jobs
from fenolite.core.errors import Issue
from fenolite.core.state import STATE_ENV, state_dir
from fenolite.model.board import Track
from fenolite.routing import registry
from fenolite.routing.codes import ISSUE_CODES
from fenolite.routing.protocol import FinishedRun, RouterStatus, RoutingJob, RoutingResult

MonkeyPatch = pytest.MonkeyPatch
NAME = "test-per-net"


class PerNetRouter:
    """Joins the two pads of each net with one track, one "process" per net. ``stop_at`` is the number of
    the process that never ends: the command is interrupted when it starts. The nets of ``fail`` end
    without copper and with an error."""

    name = NAME
    description = "a test router that works one net per process"
    sends_data_offsite = False

    def __init__(self) -> None:
        self.started: list[str] = []
        self.stop_at: int | None = None
        self.fail: set[str] = set()
        self.budget_after: int | None = None

    def available(self) -> RouterStatus:
        return RouterStatus(True, version="1")

    def route(self, job: RoutingJob) -> RoutingResult:
        tracks: list[Track] = []
        routed: list[str] = []
        unrouted: list[str] = []
        issues: list[Issue] = []
        left: list[str] = []
        for index, net in enumerate(job.nets):
            if self.budget_after is not None and index >= self.budget_after:
                left.append(net.name)  # the budget ended: no process starts for this net
                continue
            job.progress.step(net.name, index=index + 1, total=len(job.nets))
            self.started.append(net.name)
            if self.stop_at is not None and len(self.started) == self.stop_at:
                raise cli_main.Interrupted(signal.SIGTERM)
            if net.name in self.fail:
                issues.append(Issue("route.tool-failed", "error", f"{net.name}: exit 1", net.name))
                unrouted.append(net.name)
                job.progress.done(net.name, detail="failed")
                continue
            track = Track(id="", start=net.pads[0].position, end=net.pads[1].position,
                          width=net.width, layer="F.Cu", net_id=net.net_id)  # fmt: skip
            tracks.append(track)
            routed.append(net.name)
            if job.on_run is not None:
                job.on_run(FinishedRun(nets=(net.name,), tracks=(track,), seconds=0.5))
            job.progress.done(net.name, detail="routed")
        if left:
            issues.append(
                Issue("route.budget-exhausted", "warning", f"{len(left)} net(s) were not attempted")
            )
        return RoutingResult(
            tracks=tuple(tracks), routed=tuple(routed), unrouted=tuple(unrouted), issues=tuple(issues),
            tool=self.name, tool_version="1", not_attempted=tuple(left),
        )  # fmt: skip


@pytest.fixture
def router() -> Iterator[PerNetRouter]:
    made = PerNetRouter()
    registry.register(made)  # type: ignore[arg-type]
    try:
        yield made
    finally:
        registry._BUILTINS.pop(NAME, None)  # pyright: ignore[reportPrivateUsage]


def records() -> list[Path]:
    root = state_dir()
    assert root is not None
    return sorted((root / "jobs").iterdir()) if (root / "jobs").is_dir() else []


def tracks(board: Path) -> list[Track]:
    design = read_board(board.read_text(encoding="utf-8"))
    assert design.board is not None
    return list(design.board.tracks)


ARGS = ("route", "five.kicad_pcb", "--router", NAME, "--confirm")


def test_code_and_bounds() -> None:
    assert ISSUE_CODES["route.resumed"] == "info" and (jobs.JOB_KEEP, jobs.JOB_DAYS) == (8, 7)


def test_stopped_route_goes_on(monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter) -> None:
    """Scenario "A stopped route goes on": stopped after its second net of five."""
    board = write_five_nets(tmp_path)
    before = board.read_bytes()
    router.stop_at = 3
    code, env, err, _ = run(monkeypatch, tmp_path, *ARGS)
    assert code == 1 and err["code"] == "FEN-1003" and env["receipt"] is None
    assert board.read_bytes() == before and router.started == ["N1", "N2", "N3"]
    (record,) = records()
    assert sorted(p.name for p in record.iterdir()) == ["0000.json", "0001.json"], "one file per finished run"

    router.stop_at, router.started = None, []
    code, env, err, _ = run(monkeypatch, tmp_path, *ARGS)
    assert code == 0, (env, err)
    assert router.started == ["N3", "N4", "N5"], "three router processes start"
    assert env["result"]["resumed"] == {"runs": 2, "nets": 2}
    (info,) = [issue for issue in env["issues"] if issue["code"] == "route.resumed"]
    assert info["severity"] == "info" and "2 router run(s)" in info["message"]
    assert env["result"]["selected"] == ["N3", "N4", "N5"] and env["result"]["tracks"] == 5
    assert env["evidence"]["level"] == "UNVERIFIED"
    written = tracks(board)
    assert len(written) == 5 and {abs(t.end.x - t.start.x) for t in written} == {SPAN}
    assert sorted({t.start.y for t in written}) == sorted({row * 2_000_000 for row in range(len(NETS))})
    assert records() == [], "the record is removed after the confirmed write"

    router.started = []
    code, env, _, _ = run(monkeypatch, tmp_path, *ARGS)
    assert code == 0 and router.started == [] and env["result"]["resumed"] is None


def test_another_board_another_record(monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter) -> None:
    """Scenario "Another board, another record": one byte of the board changes."""
    board = write_five_nets(tmp_path)
    router.stop_at = 3
    code, _, _, _ = run(monkeypatch, tmp_path, *ARGS)
    assert code == 1 and len(records()) == 1
    board.write_bytes(board.read_bytes() + b"\n")
    router.stop_at, router.started = None, []
    code, env, err, _ = run(monkeypatch, tmp_path, *ARGS)
    assert code == 0, (env, err)
    assert env["result"]["resumed"] is None and router.started == list(NETS)
    assert "route.resumed" not in [issue["code"] for issue in env["issues"]]


def test_other_arguments_another_record(
    monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter
) -> None:
    write_five_nets(tmp_path)
    router.stop_at = 3
    assert run(monkeypatch, tmp_path, *ARGS)[0] == 1
    router.stop_at, router.started = None, []
    code, env, _, _ = run(monkeypatch, tmp_path, *ARGS[:-1], "--nets", "N*", "--dry-run")
    assert code == 0 and env["result"]["resumed"] is None and router.started == list(NETS)
    # --out and the run flags take no part in the key: the first job goes on into another file
    router.started = []
    code, env, _, _ = run(monkeypatch, tmp_path, *ARGS, "--out", "routed.kicad_pcb", "--timeout", "30")
    assert code == 0 and env["result"]["resumed"] == {"runs": 2, "nets": 2}
    assert router.started == ["N3", "N4", "N5"] and len(tracks(tmp_path / "routed.kicad_pcb")) == 5


def test_failed_run_is_routed_again(monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter) -> None:
    """Scenario "A failed run is routed again": the third process ends without copper."""
    board = write_five_nets(tmp_path)
    before = board.read_bytes()
    router.fail = {"N3"}
    args = (*ARGS, "--nets", "N1", "--nets", "N2", "--nets", "N3")
    code, env, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 5 and err["code"] == "FEN-5001" and env["receipt"] is None
    assert board.read_bytes() == before, "an error finding plans no write"
    (record,) = records()
    assert len(list(record.iterdir())) == 2, "only finished processes with copper are recorded"

    router.started = []
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 5 and router.started == ["N3"], "the third net is routed again, the others are not"
    assert env["result"]["resumed"] == {"runs": 2, "nets": 2}

    router.fail, router.started = set(), []
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0 and router.started == ["N3"] and len(tracks(board)) == 3 and records() == []


def test_dry_run_removes_the_record(monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter) -> None:
    board = write_five_nets(tmp_path)
    before = board.read_bytes()
    code, env, _, _ = run(monkeypatch, tmp_path, *ARGS[:-1], "--dry-run")
    assert code == 0 and records() == [] and board.read_bytes() == before
    plan = env["result"]["plan_id"]
    router.started = []
    code, env, _, _ = run(monkeypatch, tmp_path, *ARGS, "--plan", plan)
    assert code == 0 and router.started == [] and len(tracks(board)) == 5, "the plan holds the board"


def test_dry_run_with_an_error_keeps_the_record(
    monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter
) -> None:
    """A dry run that reports an error plans no write, so no plan holds its copper: the record stays, as
    it does after a confirmed run whose errors wrote nothing."""
    write_five_nets(tmp_path)
    router.fail = {"N3"}
    dry = (*ARGS[:-1], "--dry-run", "--nets", "N1", "--nets", "N2", "--nets", "N3")
    code, env, _, _ = run(monkeypatch, tmp_path, *dry)
    assert code == 5 and "plan_id" not in env["result"]
    (record,) = records()
    assert len(list(record.iterdir())) == 2
    router.fail, router.started = set(), []
    code, env, _, _ = run(monkeypatch, tmp_path, *dry)
    assert code == 0 and router.started == ["N3"] and env["result"]["resumed"] == {"runs": 2, "nets": 2}
    assert records() == [] and env["result"]["plan_id"]


def test_dry_run_cut_by_the_budget_keeps_the_record(
    monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter
) -> None:
    """ "End": the record stays after a run that a time limit cut, a dry run too, so the same dry run made
    again goes on with the nets that were not attempted instead of routing the first ones for ever."""
    board = write_five_nets(tmp_path)
    before = board.read_bytes()
    dry = (*ARGS[:-1], "--dry-run")
    router.budget_after = 3
    code, env, _, _ = run(monkeypatch, tmp_path, *dry)
    assert code == 0 and env["result"]["not_attempted"] == ["N4", "N5"] and board.read_bytes() == before
    (record,) = records()
    assert len(list(record.iterdir())) == 3, "the three finished runs are kept"

    router.budget_after, router.started = None, []
    code, env, _, _ = run(monkeypatch, tmp_path, *dry)
    assert code == 0 and router.started == ["N4", "N5"], "only the nets that were not attempted"
    assert env["result"]["resumed"] == {"runs": 3, "nets": 3} and env["result"]["tracks"] == 5
    assert records() == [] and board.read_bytes() == before
    code, env, _, _ = run(monkeypatch, tmp_path, *ARGS, "--plan", env["result"]["plan_id"])
    assert code == 0 and len(tracks(board)) == 5, "the plan of the second dry run holds the whole board"


def test_the_rules_file_is_an_input_of_the_plan_and_of_the_job(
    monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter
) -> None:
    """The router is given the rules of the rules file beside the board (change c0107), so the file is a
    declared input: a reviewed plan is refused when it changed, and other rules are another job."""
    board = write_five_nets(tmp_path)
    before = board.read_bytes()
    rules = board.with_suffix(".kicad_dru")
    rules.write_text("(version 1)\n", encoding="utf-8", newline="\n")
    code, env, _, _ = run(monkeypatch, tmp_path, *ARGS[:-1], "--dry-run")
    assert code == 0 and "route.project-unread" not in [issue["code"] for issue in env["issues"]]
    plan = env["result"]["plan_id"]
    rules.write_text(
        '(version 1)\n(rule "wide"\n  (constraint clearance (min 0.3mm)))\n', encoding="utf-8", newline="\n"
    )
    code, env, err, _ = run(monkeypatch, tmp_path, *ARGS, "--plan", plan)
    assert code == 4 and err["code"] == "FEN-4002" and "five.kicad_dru" in err["message"]
    assert board.read_bytes() == before

    router.stop_at, router.started = 3, []
    code, _, err, _ = run(monkeypatch, tmp_path, *ARGS)
    assert code == 1 and err["code"] == "FEN-1003" and len(records()) == 1
    rules.write_text("(version 1)\n", encoding="utf-8", newline="\n")
    router.stop_at, router.started = None, []
    code, env, _, _ = run(monkeypatch, tmp_path, *ARGS)
    assert code == 0 and env["result"]["resumed"] is None and len(router.started) == 5


def test_record_stays_after_a_failed_write(
    monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter
) -> None:
    write_five_nets(tmp_path)
    (tmp_path / "blocker").write_bytes(b"a file")
    args = (*ARGS, "--out", "blocker/routed.kicad_pcb")
    code, _, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 1 and err["code"] == "FEN-1002"
    (record,) = records()
    assert len(list(record.iterdir())) == 5
    router.started = []
    (tmp_path / "blocker").unlink()
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0 and router.started == [] and env["result"]["resumed"] == {"runs": 5, "nets": 5}
    assert len(tracks(tmp_path / "blocker" / "routed.kicad_pcb")) == 5 and records() == []


def test_unreadable_record_is_removed(monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter) -> None:
    write_five_nets(tmp_path)
    router.stop_at = 3
    assert run(monkeypatch, tmp_path, *ARGS)[0] == 1
    (record,) = records()
    (record / "0001.json").write_text("{", encoding="utf-8")
    router.stop_at, router.started = None, []
    code, env, _, _ = run(monkeypatch, tmp_path, *ARGS)
    assert code == 0 and env["result"]["resumed"] is None and router.started == list(NETS)


def test_state_folder_off_keeps_no_record(
    monkeypatch: MonkeyPatch, tmp_path: Path, router: PerNetRouter
) -> None:
    monkeypatch.setenv(STATE_ENV, "off")
    board = write_five_nets(tmp_path)
    router.stop_at = 3
    assert run(monkeypatch, tmp_path, *ARGS)[0] == 1
    router.stop_at, router.started = None, []
    code, env, _, _ = run(monkeypatch, tmp_path, *ARGS)
    assert code == 0 and env["result"]["resumed"] is None and router.started == list(NETS)
    assert len(tracks(board)) == 5 and sorted(p.name for p in tmp_path.iterdir()) == [
        "five.kicad_pcb",
        "five.kicad_pcb.bak",
    ]


def test_key_and_bounds(tmp_path: Path) -> None:
    base = {"fenolite_version": "1", "router": "r", "router_version": "2", "board_sha256": "aa",
            "project_sha256": None, "arguments": {"nets": ["A"], "out": "x.kicad_pcb"}}  # fmt: skip
    key = jobs.route_job_key(**base)  # type: ignore[arg-type]
    assert len(key) == 16 and int(key, 16) >= 0
    assert key == jobs.route_job_key(**(base | {"arguments": {"nets": ["A"], "out": "y.kicad_pcb"}}))  # type: ignore[arg-type]
    changes: tuple[dict[str, object], ...] = (
        {"fenolite_version": "2"}, {"router": "s"}, {"router_version": "3"}, {"board_sha256": "bb"},
        {"project_sha256": "cc"}, {"arguments": {"nets": ["B"]}}, {"rules_sha256": "dd"},
    )  # fmt: skip
    for change in changes:
        assert jobs.route_job_key(**(base | change)) != key  # type: ignore[arg-type]

    root = tmp_path / "state"
    now = 1_800_000_000
    for n in range(9):
        record = jobs.JobRecord(root, f"{n:016x}")
        record.add(FinishedRun(nets=("A",)))
        assert record.folder is not None
        os.utime(record.folder, (now + n, now + n))
    jobs.prune(root, now=now + 100)
    kept = sorted(p.name for p in (root / "jobs").iterdir())
    assert len(kept) == 8 and f"{0:016x}" not in kept
    jobs.prune(root, now=now + 8 * 86400)
    assert list((root / "jobs").iterdir()) == []
    off = jobs.JobRecord(None, "a" * 16)
    off.add(FinishedRun(nets=("A",)))
    assert off.runs() == () and off.folder is None
