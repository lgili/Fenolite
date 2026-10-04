# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The build, place, route, rebuild, fill and check loop with the Freerouting plugin keeps the routes
(capability kicad-oracle, "Freerouting routes pass the oracle"; change c0023)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _resources import kicad_cli

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import read_board

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "blink_2layer" / "design.py"
pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_freerouting]


def _run(folder: Path, *args: str) -> dict[str, object]:
    process = subprocess.run(
        [sys.executable, "-m", "fenolite", *args, "--json"],
        cwd=folder,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert process.returncode == 0, process.stderr or process.stdout
    envelope: dict[str, object] = json.loads(process.stdout)
    assert envelope["ok"] is True, envelope
    return envelope


def _build(folder: Path, project: Path, target: int) -> None:
    _run(
        folder,
        "build",
        str(EXAMPLE),
        "--out",
        str(project),
        "--kicad-version",
        str(target),
        "--seed",
        "230023",
        "--timestamp",
        "2026-10-04T00:00:00Z",
        "--confirm",
        "--no-backup",
    )


def test_loop(tmp_path: Path) -> None:
    """Scenario "Loop keeps routes" with ``--router freerouting``: the second build keeps every routed
    track and via, and KiCad's DRC finds no unconnected item."""
    binary = kicad_cli()
    assert binary is not None
    cli = KicadCli(Path(binary), timeout=300)
    target = cli.major()
    project = tmp_path / "project"
    _build(tmp_path, project, target)
    board = project / "blink.kicad_pcb"
    _run(project, "place", board.name, "--strategy", "grid", "--confirm", "--no-backup")
    routed = _run(
        project, "route", board.name, "--router", "freerouting", "--allow-offsite", "--confirm", "--no-backup"
    )
    result = routed["result"]
    assert isinstance(result, dict) and result["routed"] and not result["unrouted"], routed
    after_route = read_board(board.read_text(encoding="utf-8"))
    assert after_route.board is not None
    copper = {item.id for item in (*after_route.board.tracks, *after_route.board.vias)}
    assert len(after_route.board.tracks) == result["tracks"] and len(after_route.board.vias) == result["vias"]
    _build(tmp_path, project, target)
    rebuilt = read_board(board.read_text(encoding="utf-8"))
    assert rebuilt.board is not None
    assert copper <= {item.id for item in (*rebuilt.board.tracks, *rebuilt.board.vias)}
    if target >= 10:
        _run(project, "fill", board.name, "--confirm", "--no-backup")
    _run(project, "check", board.name)
    files = {
        name: project / name for name in ("blink.kicad_pro", "blink.kicad_dru") if (project / name).exists()
    }
    judged = cli.drc(board, files=files)
    assert judged.report is not None, judged.run.stderr or judged.run.stdout
    assert not judged.report.unconnected_items
