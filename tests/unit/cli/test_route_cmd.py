# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from _checkcli import run
from _fakerouter import create_fake_router

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.cli import cmd_route
from fenolite.core.coords import Point
from fenolite.model.board import Zone
from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter

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
