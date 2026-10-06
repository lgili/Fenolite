# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite roundtrip --level rt2`` on the running ``kicad-cli`` (capability cli-contract, "Roundtrip
command", scenario "RT2 through the tool"; change c0066): the built blink reaches RT2 or RT2 is not
judged, and the project folder is untouched."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from _checkrun import cli_path
from _probes import major
from _projects import tree_snapshot

pytestmark = pytest.mark.needs_kicad
DESIGN = Path(__file__).resolve().parents[3] / "examples" / "blink_2layer" / "design.py"


def _fenolite(cwd: Path, *args: str) -> tuple[int, dict[str, Any], str]:
    command = [sys.executable, "-m", "fenolite", *args, "--json"]
    run = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=900, check=False)
    return run.returncode, json.loads(run.stdout) if run.stdout.strip() else {}, run.stderr


def test_rt2_through_the_tool(tmp_path: Path) -> None:
    for target in [t for t in (9, 10) if t <= major()]:
        out = tmp_path / f"blink-{target}"
        code, _, err = _fenolite(
            tmp_path, "build", str(DESIGN), "--out", str(out), "--kicad-version", str(target), "--confirm"
        )
        assert code == 0, err
        before = tree_snapshot(out)
        code, env, err = _fenolite(out, "roundtrip", str(out), "--level", "rt2", "--kicad-cli", cli_path())
        assert env, err
        result = env["result"]
        assert code == 0, env["issues"]
        assert result["rt0"]["passed"] is True and result["rt1"]["passed"] is True
        rt2 = result["rt2"]
        assert result["level"] == "rt2" or rt2["judged"] is False, rt2
        assert rt2["normalised"] is (major() >= 10)
        assert not [i for i in env["issues"] if i["code"] == "roundtrip.failed"]
        assert tree_snapshot(out) == before


def test_rt2_of_the_schematic_through_the_tool(tmp_path: Path) -> None:
    """The built blink has a schematic (c0061): RT2 also runs KiCad's ERC on it and on its re-dump
    (``KicadOracle.rt2_erc``, c0062). It holds, or it is not judged because ERC did not repeat itself;
    it never fails (task 2.4b)."""
    for target in [t for t in (9, 10) if t <= major()]:
        out = tmp_path / f"blink-{target}"
        code, _, err = _fenolite(
            tmp_path, "build", str(DESIGN), "--out", str(out), "--kicad-version", str(target), "--confirm"
        )
        assert code == 0, err
        assert (out / "blink.kicad_sch").is_file()
        before = tree_snapshot(out)
        code, env, err = _fenolite(out, "roundtrip", str(out), "--level", "rt2", "--kicad-cli", cli_path())
        assert env, err
        assert code == 0, env["issues"]
        sheet = env["result"]["rt2"]["schematic"]
        assert sheet["redumped"] >= 1 and sheet["kept"] == 0, sheet
        assert sheet["passed"] is True or sheet["judged"] is False, sheet
        assert sheet["violations"] == sheet["violations_redump"] or not sheet["passed"], sheet
        if env["result"]["rt2"]["passed"] and sheet["passed"]:
            assert env["result"]["level"] == "rt2"
            assert "H-K-SCH-READ" in env["evidence"]["hypotheses"]
        assert not [i for i in env["issues"] if i["code"] in ("roundtrip.failed", "check.oracle-failed")]
        assert tree_snapshot(out) == before
