# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0278: the actual five-part sensor has distinct populated native repeat contexts and imports exactly."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _kicad import cli
from _libs import isolated_kicad_env, kicad

from fenolite.api import run
from fenolite.backends.kicad.netlist import read_netlist

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
SOURCE = Path(__file__).resolve().parents[3] / "tests/data/fidelity/sensor"


def test_sensor_native_repeat_partition(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(SOURCE, source)
    netfile = tmp_path / "sensor.net"
    native = kicad(
        cli(),
        isolated_kicad_env(tmp_path),
        "sch",
        "export",
        "netlist",
        "--format",
        "kicadsexpr",
        "-o",
        netfile,
        source / "sensor.kicad_sch",
    )
    assert native.returncode == 0, native.stdout + native.stderr
    netlist = read_netlist(netfile.read_text())
    assert {p.ref for p in netlist.components} == {"U1", "R1", "D1", "R2", "R3"}
    nets = {
        n.name.lstrip("/"): {(p.ref, p.pin) for p in n.nodes}
        for n in netlist.nets
        if not n.name.startswith("unconnected")
    }
    assert nets == {
        "VIN": {("U1", "9")},
        "GND": {("U1", "10"), ("D1", "1"), ("R2", "2"), ("R3", "2")},
        "SIG": {("U1", "1"), ("R1", "1")},
        "LED": {("R1", "2"), ("D1", "2")},
        "SENSE0": {("U1", "17"), ("R2", "1")},
        "SENSE1": {("U1", "18"), ("R3", "1")},
    }


def test_sensor_import_roundtrip_all_strict_levels(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(SOURCE, source)
    imported = run(
        "import",
        str(source / "sensor.kicad_pro"),
        "--to",
        "python",
        "--out",
        "converted",
        "--licence",
        "CC0-1.0",
        "--confirm",
        cwd=tmp_path,
    )
    assert imported.exit_code == 0, imported.error
    checked = run(
        "verify-source", str(tmp_path / "converted/design.py"), "--against", str(source), cwd=tmp_path
    )
    assert checked.exit_code == 0, checked.error
    assert checked.envelope is not None
    result = checked.envelope["result"]
    assert result["differences"] == [] and result["accepted"] == []
    assert {str(row["level"]): row["status"] for row in result["levels"]} == {
        **{str(n): "equal" for n in range(1, 9)},
        "S": "equal",
    }
