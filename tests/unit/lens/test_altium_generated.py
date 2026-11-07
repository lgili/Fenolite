# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated copper in an Altium build (change c0243, decision 13; capability design-dsl, scenario
"Generated copper reaches Altium"; altium-build, "Script copper in an Altium build").

A blink variant with a ``band`` and a ``stitch_pieces`` call is built for ``--target altium --dry-run``: the
in-memory KiCad build resolves the calls, and the band's polygon and the stitching vias reach
``result.copper``. With ``--copper-from`` the board wins, so the calls would be lost:
``kicad.generate.altium`` refuses the build. ``kicad-cli`` is not run.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from _buildhelp import blink_variant

import fenolite.cli.main as cli_main

LINES = (
    'design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3))\n'
    'design.zone(gnd, name="GND_TOP", layers=("F.Cu",), clearance=mm(0.3),'
    " outline=((mm(20), mm(18)), (mm(30), mm(18)), (mm(30), mm(28)), (mm(20), mm(28))))\n"
    'design.band(vin, ((mm(26), mm(24.5)), (mm(46), mm(24.5))), width=mm(3), layers=("B.Cu",))\n'
    "design.stitch_pieces(gnd, pitch=mm(2), diameter=mm(0.6), drill=mm(0.3))\n"
)


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _build(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any]]:
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(stdout.getvalue() or "{}")


def test_generated_copper_reaches_altium(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Generated copper reaches Altium"."""
    _isolate(monkeypatch, tmp_path)
    script = blink_variant(tmp_path / "src", append="\n" + LINES)
    out = tmp_path / "altium"
    code, env = _build(monkeypatch, str(script), "--out", str(out), "--target", "altium", "--dry-run")
    codes = [found["code"] for found in env["issues"]]
    assert code == 0, codes
    assert "kicad.generate.altium" not in codes
    copper = env["result"]["copper"]
    assert copper["source"] == "script"
    # the two declared pours and the band's polygon, and the stitching vias between the two pours
    assert copper["zones"] == 3
    assert copper["vias"] >= 2

    kicad = tmp_path / "kicad"
    code, env = _build(monkeypatch, str(script), "--out", str(kicad), "--confirm")
    assert code == 0, [found["code"] for found in env["issues"]]
    board = kicad / "blink.kicad_pcb"
    assert board.is_file()
    flags = ("--target", "altium", "--dry-run", "--copper-from", str(board))
    code, env = _build(monkeypatch, str(script), "--out", str(tmp_path / "from"), *flags)
    refused = [found for found in env["issues"] if found["code"] == "kicad.generate.altium"]
    assert code == 5
    assert len(refused) == 1 and refused[0]["where"] == "band.VIN, stitch_pieces.GND"
