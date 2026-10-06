# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.1 acceptance loop through the CLI: ``build``, ``place``, ``route``, ``fill``, ``check``,
``export`` and ``render`` on an example design (capability release-gate, "Acceptance loop"; change c0025).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {"blink_2layer": "blink", "board_40parts": "board_40parts"}
ROUTER = "freerouting"
ROUTER_LIMIT = 600
SEED = "250025"
TIMESTAMP = "2026-10-04T00:00:00Z"
STEPS = ("build", "place", "route", "fill", "check", "export", "render")


@dataclass(frozen=True, slots=True)
class LoopRun:
    """One loop: the project folder, the board, and the envelope of every step."""

    project: Path
    board: Path
    envelopes: dict[str, dict[str, object]]

    def result(self, step: str) -> dict[str, object]:
        found = self.envelopes[step]["result"]
        assert isinstance(found, dict)
        return found


def run_cli(folder: Path, *args: str, timeout: int = 900) -> tuple[int, dict[str, object], str]:
    """``fenolite <args> --json`` in ``folder``: the exit code, the envelope and stderr."""
    process = subprocess.run(
        [sys.executable, "-m", "fenolite", *args, "--json"],
        cwd=folder,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    envelope: dict[str, object] = json.loads(process.stdout) if process.stdout.strip() else {}
    return process.returncode, envelope, process.stderr


def build_args(example: str, project: Path, target: int) -> list[str]:
    script = ROOT / "examples" / example / "design.py"
    return [
        "build", str(script), "--out", str(project), "--kicad-version", str(target),
        "--seed", SEED, "--timestamp", TIMESTAMP, "--confirm", "--no-backup",
    ]  # fmt: skip


def run_loop(folder: Path, example: str, target: int) -> LoopRun:
    """Run the seven steps for ``example`` and the KiCad major ``target`` under ``folder``. Every step must
    exit 0; the caller judges the results."""
    project = folder / "project"
    board = project / f"{EXAMPLES[example]}.kicad_pcb"
    outputs = folder / "outputs"
    common = ["--seed", SEED, "--timestamp", TIMESTAMP, "--confirm", "--no-backup"]
    name = board.name
    steps: dict[str, tuple[Path, list[str]]] = {
        "build": (folder, build_args(example, project, target)),
        "place": (project, ["place", name, "--strategy", "grid", "--margin", "3mm", "--gap", "2mm", *common]),
        "route": (
            project,
            [
                "route",
                name,
                "--router",
                ROUTER,
                "--timeout",
                str(ROUTER_LIMIT),
                *common,
            ],
        ),
        "fill": (project, ["fill", name, *common]),
        "check": (project, ["check", name]),
        "export": (project, ["export", name, "-o", str(outputs / "fab"), "--all", "--manifest", *common]),
        "render": (project, ["render", name, "-o", str(outputs / "views"), "--svg", "--png", *common]),
    }
    envelopes: dict[str, dict[str, object]] = {}
    for step in STEPS:
        cwd, args = steps[step]
        code, envelope, error = run_cli(cwd, *args, timeout=ROUTER_LIMIT + 300)
        found = [issue for issue in envelope.get("issues", []) if issue.get("severity") == "error"]  # type: ignore[union-attr]
        assert code == 0, (
            f"{step} exited {code} for {example} (KiCad {target}): {error or envelope}; errors: {found}"
        )
        assert envelope.get("ok") is True, (step, envelope)
        envelopes[step] = envelope
    return LoopRun(project, board, envelopes)


__all__ = [
    "EXAMPLES",
    "ROOT",
    "ROUTER",
    "ROUTER_LIMIT",
    "STEPS",
    "LoopRun",
    "build_args",
    "run_cli",
    "run_loop",
]
