# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from _checkcli import run
from _fakefreerouting import create_fake_jar, create_fake_java
from _fakerouter import create_fake_router
from _specctra import two_pads

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.cli import cmd_route
from fenolite.core.coords import Point
from fenolite.model.board import Zone
from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from fenolite.routing.protocol import RouterStatus, RoutingJob, RoutingResult

ROOT = Path(__file__).resolve().parents[3]


def test_example_route_dry_run(monkeypatch, tmp_path: Path) -> None:
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        str(ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"),
        "--router",
        "direct",
        "--out",
        "routed.kicad_pcb",
        "--rip",
        "--dry-run",
    )
    assert code == 0, (env, error)
    assert env["result"]["routed"] == ["ROUTE_ME"]
    assert env["result"]["ripped"] == 0
    assert env["evidence"]["level"] == "UNVERIFIED"
    assert env["result"]["plan"][0]["path"] == "routed.kicad_pcb"


def test_unknown_router(monkeypatch, tmp_path: Path) -> None:
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, env, error, _ = run(monkeypatch, tmp_path, "route", str(board), "--router", "nope", "--dry-run")
    assert code == 2 and error["code"] == "FEN-2001"


def test_fake_router_and_net_filter(monkeypatch, tmp_path: Path) -> None:
    checkout = create_fake_router(tmp_path)
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(ROOT / "src"))
    router = KicadRoutingToolsRouter(checkout, sys.executable)
    monkeypatch.setattr(cmd_route, "_router", lambda _name, _args: router)
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        str(board),
        "--router",
        "kicadroutingtools",
        "--nets",
        "ROUTE*",
        "--out",
        "routed.kicad_pcb",
        "--dry-run",
    )
    assert code == 0, (env, error)
    assert env["result"]["selected"] == ["ROUTE_ME"]
    assert env["result"]["routed"] == ["ROUTE_ME"]


def test_offsite_router_requires_explicit_flag(monkeypatch, tmp_path: Path) -> None:
    class Offsite:
        name = "offsite"
        description = "test"
        sends_data_offsite = True

        def available(self):
            from fenolite.routing.protocol import RouterStatus

            return RouterStatus(True)

    monkeypatch.setattr(cmd_route, "_router", lambda _name, _args: Offsite())
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, _, error, _ = run(monkeypatch, tmp_path, "route", str(board), "--router", "offsite", "--dry-run")
    assert code == 2 and "sends design data offsite" in error["message"]


def test_log_paths_are_redacted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    lines = cmd_route._safe_log((f"tool used {tmp_path}/router and {Path.home()}/board.kicad_pcb",), tmp_path)
    assert lines == ["tool used <tmp>/router and <home>/board.kicad_pcb"]


def test_routing_marks_existing_fills_stale(monkeypatch, tmp_path: Path) -> None:
    source = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    design = read_board(source.read_text(encoding="utf-8"))
    assert design.board is not None
    net = next(item for item in design.circuit.nets if item.name == "ROUTE_ME")
    zone = Zone(
        id="zone_test",
        outline=(Point(0, 0), Point(1_000_000, 0), Point(1_000_000, 1_000_000), Point(0, 1_000_000)),
        name="filled zone",
        layers=("F.Cu",),
        net_id=net.id,
        filled=True,
    )
    board = replace(design.board, zones=(zone,))
    synthetic = replace(design, board=board)
    board_path = tmp_path / "filled.kicad_pcb"
    board_path.write_text(write_board(synthetic, target=10).text, encoding="utf-8")
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        str(board_path),
        "--router",
        "direct",
        "--include-zone-nets",
        "--dry-run",
    )
    assert code == 0, (env, error)
    assert env["result"]["fills_stale"] is True
    assert "route.fill-stale" in [issue["code"] for issue in env["issues"]]
    code, env, error, _ = run(
        monkeypatch, tmp_path, "route", str(board_path), "--router", "direct", "--dry-run"
    )
    assert code == 0, (env, error)
    assert env["result"]["fills_stale"] is False
    assert "route.zone-net-skipped" in [issue["code"] for issue in env["issues"]]


class _RecordingRouter:
    """A router that keeps the job it was given and routes nothing."""

    name = "recorder"
    description = "records its job"
    sends_data_offsite = False

    def __init__(self) -> None:
        self.jobs: list[RoutingJob] = []

    def available(self) -> RouterStatus:
        return RouterStatus(True)

    def route(self, job: RoutingJob) -> RoutingResult:
        self.jobs.append(job)
        return RoutingResult(unrouted=tuple(net.name for net in job.nets), tool=self.name)


def test_job_extra_holds_the_board_pads_and_the_outline(monkeypatch, tmp_path: Path) -> None:
    """Capability routing, "Job extras" (c0023): scenario "Extras passed by the command"."""
    router = _RecordingRouter()
    monkeypatch.setattr(cmd_route, "_router", lambda _name, _args: router)
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, env, error, _ = run(monkeypatch, tmp_path, "route", str(board), "--router", "recorder", "--dry-run")
    assert code == 0, (env, error)
    (job,) = router.jobs
    assert set(job.extra) == {"board_pads", "outline"}
    pads = job.extra["board_pads"]
    assert isinstance(pads, tuple) and pads and all(isinstance(pad, BoardPad) for pad in pads)
    assert {pad.net for pad in pads if pad.net} >= {net.name for net in job.nets}
    outline = job.extra["outline"]
    assert isinstance(outline, tuple) and all(isinstance(point, Point) for ring in outline for point in ring)


def test_freerouting_is_refused_without_allow_offsite(monkeypatch, tmp_path: Path) -> None:
    """Capability cli-contract, "Freerouting in doctor" (c0023): scenario "Refused without the flag"."""
    monkeypatch.setenv("FENOLITE_FREEROUTING_JAR", str(create_fake_jar(tmp_path)))
    monkeypatch.setenv("FENOLITE_JAVA", str(create_fake_java(tmp_path)))
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, _env, error, _ = run(
        monkeypatch, tmp_path, "route", str(board), "--router", "freerouting", "--dry-run"
    )
    assert code == 2 and error["code"] == "FEN-2001"
    assert "--allow-offsite" in error["hint"]


@pytest.mark.skipif(sys.platform == "win32", reason="the fake java is a shell script")
def test_freerouting_through_the_command(monkeypatch, tmp_path: Path) -> None:
    """The whole path with a fake java: ``--router-path`` names the jar, ``--router-option max-passes``
    reaches the command line, and the authored session's copper is planned into the board."""
    board = tmp_path / "two_pads.kicad_pcb"
    board.write_text(write_board(two_pads().design, target=10).text, encoding="utf-8")
    monkeypatch.setenv("FENOLITE_JAVA", str(create_fake_java(tmp_path)))
    monkeypatch.setenv("FAKE_JAVA_SESSION", str(ROOT / "tests/data/specctra/two_pads.ses"))
    monkeypatch.delenv("FAKE_JAVA_MODE", raising=False)
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_JAVA_RECORD", str(record))
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        board.name,
        "--router",
        "freerouting",
        "--router-path",
        str(create_fake_jar(tmp_path)),
        "--router-option",
        "max-passes=3",
        "--allow-offsite",
        "--out",
        "routed.kicad_pcb",
        "--dry-run",
    )
    assert code == 0, (env, error)
    result = env["result"]
    assert result["router"] == "freerouting" and result["tool_version"] == "2.4.1"
    assert result["selected"] == ["A"] and result["routed"] == ["A"] and result["unrouted"] == []
    assert (result["tracks"], result["vias"]) == (2, 1)
    assert result["plan"][0]["path"] == "routed.kicad_pcb"
    assert env["evidence"]["level"] == "UNVERIFIED" and "2.4.1" in env["evidence"]["oracle"]
    argv = json.loads(record.read_text(encoding="utf-8"))["argv"]
    assert argv[argv.index("-mp") + 1] == "3" and "-da" in argv


def test_freerouting_needs_a_board_outline(monkeypatch, tmp_path: Path) -> None:
    """A board without an outline cannot be written as a design file: ``route.tool-failed``, no run."""
    monkeypatch.setenv("FENOLITE_JAVA", str(create_fake_java(tmp_path)))
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_JAVA_RECORD", str(record))
    board = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"
    code, env, error, _ = run(
        monkeypatch,
        tmp_path,
        "route",
        str(board),
        "--router",
        "freerouting",
        "--router-path",
        str(create_fake_jar(tmp_path)),
        "--allow-offsite",
        "--dry-run",
    )
    assert code == 5, (env, error)
    failed = [issue for issue in env["issues"] if issue["code"] == "route.tool-failed"]
    assert failed and "outline" in failed[0]["message"]
    assert not record.exists()
