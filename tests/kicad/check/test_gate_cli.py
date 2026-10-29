# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``--gate drc`` of ``route`` and ``tidy`` against the running ``kicad-cli`` (change c0225; capability
kicad-oracle, "DRC gate on writing commands"; ``H-K-DRC-TRIAL``).

The route bench is the bench of ``test_trial.py``: the ``direct`` router joins pad 2 of ``R1`` to pad 1 of
``R2`` on ``S``, and pad 2 of ``R3`` to pad 1 of ``R4`` on ``T``, a straight track that passes 0.1 mm or so
from both pads of ``R5`` (nets ``U`` and ``V``) under KiCad's default 0.2 mm clearance. The tidy bench is
``tests/_tidybench.py``, whose edits KiCad finds clean.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from _probes import major, runner
from _tidybench import bench as tidy_bench
from test_trial import folder

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.cli import main as cli_main

pytestmark = pytest.mark.needs_kicad


def fenolite(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(cwd)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    code = cli_main.main([*args, "--kicad-cli", str(runner().path), "--json"])
    return code, json.loads(out.getvalue() or "{}")


def test_a_gated_route(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "A gated route" and "Verdict of a gated route"."""
    board = folder(tmp_path)
    code, env = fenolite(monkeypatch, tmp_path, "route", board.name, "--router", "direct", "--gate", "drc",
                         "--confirm")  # fmt: skip
    assert code == 0, env
    result = env["result"]
    assert result["routed"] == ["S"] and result["unrouted"] == ["T"] and result["tracks"] == 1
    gate = result["gate"]
    assert gate["items"] == 2 and gate["kept"] == 1 and gate["findings"] == []
    (dropped,) = gate["dropped"]
    assert {finding["type"] for finding in dropped["findings"]} == {"clearance"}
    assert [found["where"] for found in env["issues"] if found["code"] == "gate.dropped"] == [dropped["id"]]
    assert env["evidence"]["level"] == "KICAD-VERIFIED"
    written = read_board(board.read_text(encoding="utf-8"), file=board.name)
    assert written.board is not None
    nets = {net.id: net.name for net in written.circuit.nets}
    assert [nets[track.net_id or ""] for track in written.board.tracks] == ["S"]


def test_a_gated_tidy_keeps_clean_edits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    design = tidy_bench()
    board = tmp_path / "tidy.kicad_pcb"
    board.write_text(write_board(design, target=major()).text, encoding="utf-8", newline="\n")
    project = synthesize_project(design, target=major(), board_name="tidy")
    board.with_suffix(".kicad_pro").write_text(project, encoding="utf-8", newline="\n")
    code, env = fenolite(monkeypatch, tmp_path, "tidy", board.name, "--gate", "drc", "--dry-run")
    assert code == 0, env
    gate = env["result"]["gate"]
    assert gate["dropped"] == [] and gate["kept"] == gate["items"] > 0 and gate["runs"] == 2
    assert env["evidence"]["level"] == "KICAD-VERIFIED" and env["result"]["plan"]
