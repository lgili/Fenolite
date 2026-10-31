# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper guard of a build reads the net of a copper graphic that the written board keeps in its slots
(change c0277): a graphic of ``GND`` under a ``GND`` via is no short, one of ``VIN`` is, on both targets."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run

LINES = (
    'design.polygon("art/gnd", [(mm(4), mm(24)), (mm(9), mm(24)), (mm(9), mm(28)), (mm(4), mm(28))],'
    ' layer="B.Cu", width=None, fill=True, net=gnd)\n'
    'design.via("tv", mm(5), mm(26), net=gnd, diameter=mm("0.6"), drill=mm("0.3"))\n'
    'design.polygon("art/vin", [(mm(20), mm(24)), (mm(24), mm(24)), (mm(24), mm(28))],'
    ' layer="B.Cu", width=None, fill=True, net=vin)\n'
    'design.via("tv2", mm(22), mm(25), net=gnd, diameter=mm("0.6"), drill=mm("0.3"))\n'
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("target", [9, 10])
def test_graphic_nets_in_the_copper_guard(tmp_path: Path, target: int) -> None:
    script = blink_variant(tmp_path / "src", append=LINES)
    reply = run(
        "build", str(script), "--out", str(tmp_path / "out"), "--kicad-version", str(target), "--dry-run",
        cwd=script.parent, timestamp="2026-10-30T00:00:00Z",
    )  # fmt: skip
    shorts = [i["message"] for i in reply.envelope["issues"] if i["code"] == "copper.short"]  # type: ignore[index]
    assert len(shorts) == 1 and "VIN and GND" in shorts[0] and "(122, 125)" in shorts[0]
