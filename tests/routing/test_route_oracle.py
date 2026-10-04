# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The build/place/route/fill/check loop retains plugin copper (c0016)."""

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
pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_router]


def _run(folder: Path, env: dict[str, str], *args: str) -> dict[str, object]:
    process = subprocess.run(
        [sys.executable, "-m", "fenolite", *args, "--json"],
        cwd=folder,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert process.returncode == 0, process.stderr or process.stdout
    envelope = json.loads(process.stdout)
    assert envelope["ok"] is True, envelope
    return envelope


def test_loop(tmp_path: Path) -> None:
    binary = kicad_cli()
    assert binary is not None
    cli = KicadCli(Path(binary), timeout=300)
    target = cli.major()
    router = Path(os.environ["FENOLITE_KRT"])
    python = Path(os.environ.get("FENOLITE_KRT_PYTHON", sys.executable))
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "FENOLITE_KRT": str(router),
        "FENOLITE_KRT_PYTHON": str(python),
    }
    project = tmp_path / "project"
    _run(
        tmp_path,
        env,
        "build",
        str(EXAMPLE),
        "--out",
        str(project),
        "--kicad-version",
        str(target),
        "--seed",
        "160016",
        "--timestamp",
        "2026-10-04T00:00:00Z",
        "--confirm",
        "--no-backup",
    )
    board = project / "blink.kicad_pcb"
    _run(project, env, "place", board.name, "--strategy", "grid", "--confirm", "--no-backup")
    routed = _run(
        project, env, "route", board.name, "--router", "kicadroutingtools", "--confirm", "--no-backup"
    )
    expected_tracks = int(routed["result"]["tracks"])
    _run(
        tmp_path,
        env,
        "build",
        str(EXAMPLE),
        "--out",
        str(project),
        "--kicad-version",
        str(target),
        "--seed",
        "160016",
        "--timestamp",
        "2026-10-04T00:00:00Z",
        "--confirm",
        "--no-backup",
    )
    rebuilt = read_board(board.read_text(encoding="utf-8"))
    assert rebuilt.board is not None and len(rebuilt.board.tracks) >= expected_tracks
    _run(project, env, "fill", board.name, "--confirm", "--no-backup")
    _run(project, env, "check", board.name)
    result = cli.drc(
        board,
        files={
            name: project / name
            for name in ("blink.kicad_pro", "blink.kicad_dru")
            if (project / name).exists()
        },
    )
    assert result.report is not None, result.run.stderr or result.run.stdout
    assert not result.report.unconnected_items
