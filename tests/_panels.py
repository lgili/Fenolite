# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The panel fixtures of change c0173 (``tests/data/panels/``): the board ``board.py`` built in-process for
KiCad 9, KiCad 10 or Altium, and the panel scripts that repeat it.

The panel scripts name ``board_t10.kicad_pcb``, the committed board of ``board.py`` built for KiCad 10;
``board_t9.kicad_pcb`` is the one for KiCad 9. ``tests/unit/panel/test_fixture.py`` keeps both equal to a
fresh build (``FENOLITE_PANELS_WRITE=1`` writes them). ``script_for(name, folder, board)`` copies a panel
script into ``folder`` naming another board, as the probes of the 9.0 image do.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
from pathlib import Path

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "tests" / "data" / "panels"
BOARD_SCRIPT = PANELS / "board.py"
SCRIPTS = ("tabs", "vscore", "mixed")
SEED = "250025"
TIMESTAMP = "2026-10-16T00:00:00Z"


def committed_board(major: int) -> Path:
    return PANELS / f"board_t{major}.kicad_pcb"


def run(*args: str) -> tuple[int, dict[str, object], str]:
    """``fenolite <args> --json`` in-process: the exit code, the envelope and stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli_main.main([*args, "--json"])
    text = out.getvalue()
    return code, json.loads(text) if text.strip() else {}, err.getvalue()


def build_board(out: Path, target: str) -> Path:
    """``board.py`` built into ``out`` for ``target`` (``9``, ``10`` or ``altium``); the board file."""
    args = ["build", str(BOARD_SCRIPT), "--out", str(out), "--seed", SEED, "--timestamp", TIMESTAMP]
    if target == "altium":
        args += ["--target", "altium"]
    else:
        args += ["--kicad-version", target]
    code, envelope, err = run(*args, "--confirm", "--no-backup")
    assert code == 0, (envelope.get("issues"), err)
    return out / ("board.PcbDoc" if target == "altium" else "board.kicad_pcb")


def script_for(name: str, folder: Path, board: Path) -> Path:
    """A copy of the panel script ``name`` in ``folder`` whose ``board=`` names ``board`` (copied beside it
    when it lies elsewhere)."""
    folder.mkdir(parents=True, exist_ok=True)
    if board.parent.resolve() != folder.resolve():
        target = folder / board.name
        shutil.copyfile(board, target)
        board = target
    text = (PANELS / f"{name}.py").read_text(encoding="utf-8")
    text = text.replace('board="board_t10.kicad_pcb"', f'board="{board.name}"')
    script = folder / f"{name}.py"
    script.write_text(text, encoding="utf-8")
    return script


__all__ = ["BOARD_SCRIPT", "PANELS", "SCRIPTS", "build_board", "committed_board", "run", "script_for"]
