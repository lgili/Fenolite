# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The loop block of the agent guide closes the loop on the running ``kicad-cli`` (capability
release-gate, "Agent guide is executable", scenario "Ten commands close the loop"; capability agent-guide,
"Starter projects", the oracle proof; hypothesis H-K-GUIDE-STARTER; change c0079).

The lines run as written, in an empty folder, with only Fenolite and ``kicad-cli``: once for KiCad 9
projects and once for KiCad 10 projects. A target-10 run is skipped on ``kicad-cli`` 9.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from _probes import major

from fenolite.exports.manifest import FILE_NAME as MANIFEST

pytestmark = pytest.mark.needs_kicad

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "src" / "fenolite" / "agent" / "skill" / "SKILL.md"
BLOCK = re.compile(r"^```fenolite-loop\n(.*?)^```$", re.MULTILINE | re.DOTALL)
GERBER = ".gbr"


def block_lines() -> list[str]:
    blocks = BLOCK.findall(SKILL.read_text(encoding="utf-8"))
    assert len(blocks) == 1
    lines = [line for line in blocks[0].splitlines() if line.strip()]
    assert 1 <= len(lines) <= 10
    return lines


def _run(words: list[str], cwd: Path) -> tuple[int, dict[str, Any], str]:
    process = subprocess.run(
        [sys.executable, "-m", "fenolite", *words],
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=900,
        check=False,
    )
    try:
        envelope = json.loads(process.stdout)
    except json.JSONDecodeError:
        envelope = {}
    return process.returncode, envelope, process.stderr or process.stdout


@pytest.mark.parametrize("target", [9, 10])
def test_block(tmp_path: Path, target: int) -> None:
    """Scenario "Ten commands close the loop"."""
    if target > major():
        pytest.skip(f"target {target} on kicad-cli {major()}")
    envelopes: dict[str, dict[str, Any]] = {}
    for line in block_lines():
        words = shlex.split(line)
        assert words[0] == "fenolite", line
        code, envelope, said = _run([*words[1:], "--kicad-version", str(target)], tmp_path)
        assert code == 0, f"{line}\n{said}"
        assert envelope["evidence"]["level"], line
        envelopes[f"{words[1]}{' dry-run' if '--dry-run' in words else ''}"] = envelope

    assert list(envelopes) == [
        *("capabilities", "init", "build dry-run", "build", "place"),
        *("route", "fill", "check", "export", "render"),
    ]
    assert envelopes["capabilities"]["result"]["tools"]["kicad-cli"] is not None
    assert envelopes["route"]["result"]["unrouted"] == []
    check = envelopes["check"]
    assert [issue for issue in check["issues"] if issue["severity"] == "error"] == []
    stages = {stage["name"]: stage for stage in check["result"]["stages"]}
    assert stages["drc.kicad"]["status"] == "ok", stages["drc.kicad"]
    drc = stages["drc.kicad"]["summary"]
    assert drc["violations"] == 0 and drc["unconnected"] == 0, drc
    fab = tmp_path / "blink" / "fab"
    names = [path.name for path in fab.rglob("*") if path.is_file()]
    assert (fab / MANIFEST).is_file(), names
    assert any(name.lower().endswith(GERBER) for name in names), names
