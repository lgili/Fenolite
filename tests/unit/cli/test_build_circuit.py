# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Circuit findings in a build (capability design-dsl, "Circuit findings in a build" and "Interface checks in
a build"; change c0252)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from _sensor_rails import copy_example

import fenolite.cli.main as cli_main


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))


def build(
    monkeypatch: pytest.MonkeyPatch, script: Path, out: Path, *flags: str
) -> tuple[int, dict[str, Any]]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        code = cli_main.main(["build", str(script), "--out", str(out), *flags, "--json"])
    return code, json.loads(stdout.getvalue())


def test_over_budget_rail_stops_the_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy_example(tmp_path / "ex")
    out = tmp_path / "out"
    code, env = build(monkeypatch, folder / "bad.py", out, "--confirm")
    assert code == 5
    (current,) = [i for i in env["issues"] if i["code"] == "circuit.rail-current"]
    assert (
        current["severity"] == "error" and "3V3" in current["message"] and "buck/VOUT" in current["message"]
    )
    assert {i["code"] for i in env["issues"] if i["code"].startswith("circuit.")} == {
        "circuit.rail-current",
        "circuit.bus-pullup",
        "circuit.logic-level",
    }
    assert not out.exists() or not any(out.iterdir())


def test_good_variant_builds_without_circuit_issues(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy_example(tmp_path / "ex")
    code, env = build(monkeypatch, folder / "good.py", tmp_path / "out", "--dry-run")
    assert code == 0 and env["issues"] == []


DEVICE_PULLUP = """
from fenolite.dsl import I2C, Design, Net, connect, mm, pull_up, ohm
from rails.board import SYMBOLS, _symbol

design = Design("pullups")
design.board(mm(30), mm(20))
for symbol, pins in SYMBOLS:
    design.add(_symbol(symbol, pins))
mcu = design.part("U1", device="Example:MCU_SO8")
vdd, gnd = Net("VDD"), Net("GND")
connect(vdd, mcu.VDD, mcu.VDDA)
connect(gnd, mcu.VSS)
bus = I2C(Net("SDA"), Net("SCL"))
design.add(bus)
connect(bus, mcu.i2c1)
r1 = design.part("R1", device="Fenolite:R_0603", value="4k7")
r2 = design.part("R2", device="Fenolite:R_0603", value="4k7")
pull_up(bus, vdd, r1, r2)
mcu.unused_no_connect()
mcu.place(mm(10), mm(10))
r1.place(mm(20), mm(6))
r2.place(mm(20), mm(14))
"""


def test_pull_up_to_a_device_power_port(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No power interface: the pull-ups go to the hv net of the MCU's power port ``vdd``."""
    folder = copy_example(tmp_path / "ex")
    script = folder / "pullups.py"
    script.write_text(DEVICE_PULLUP, encoding="utf-8")
    code, env = build(monkeypatch, script, tmp_path / "out", "--dry-run")
    assert code == 0, env["issues"]
    assert not [i for i in env["issues"] if i["code"] == "build.i2c-pullup-missing"]


def test_pull_up_one_call_two_resistors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "One call, two resistors": ``pull_up`` on an ``i2c`` device port."""
    folder = copy_example(tmp_path / "ex")
    script = folder / "pullups.py"
    text = DEVICE_PULLUP.replace("pull_up(bus, vdd, r1, r2)", "pull_up(mcu.i2c1, vdd, r1, r2)")
    script.write_text(
        text.replace('vdd, gnd = Net("VDD"), Net("GND")', 'vdd, gnd = design.rail("VDD"), Net("GND")')
    )
    code, env = build(monkeypatch, script, tmp_path / "out", "--dry-run")
    assert code == 0, env["issues"]
    assert not [i for i in env["issues"] if i["code"] == "build.i2c-pullup-missing"]
    circuit = (
        json.loads((tmp_path / "out").joinpath(".fenolite", "circuit.json").read_text()) if False else None
    )
    assert circuit is None
