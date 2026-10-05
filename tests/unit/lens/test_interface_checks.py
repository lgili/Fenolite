# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Interface checks of a build (capability design-dsl, "Interface checks in a build" and "Interfaces in the
DSL"; altium-build, "Typed interfaces in an Altium build"; change c0073)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _altium import sample
from _buildhelp import blink, build
from _rulesdesign import script

import fenolite.cli.main as cli_main
from fenolite.core.errors import Issue
from fenolite.dsl import I2C, UART, USB2, Design, DiffPair, Net, Part, connect, ohm, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import is_pair, pair_hint

PAIRS = (("X_P", "X_N"), ("X+", "X-"), ("X_DP", "X_DN"), ("XP", "XN"))
"""The names KiCad pairs, as the probes of ``tests/kicad/rules/test_diffpair_names.py`` record."""
NOT_PAIRS = (("X_DP", "X_DM"), ("X_p", "X_n"), ("X_P", "X-"), ("X_N", "X_P"), ("X_P", "Y_N"), ("P", "N2"))


def found(design: Design, code: str) -> list[Issue]:
    return [i for i in build(design).issues if i.code == code]


def test_pair_rule() -> None:
    assert all(is_pair(*pair) for pair in PAIRS)
    assert not any(is_pair(*pair) for pair in NOT_PAIRS)
    assert "USB_DN" in pair_hint("USB_DP", "USB_DM") and "CLK-" in pair_hint("CLK+", "CLKN")
    assert "DATA_P and DATA_N" in pair_hint("DATA", "DATA_B")


def test_usb2_names_that_kicad_does_not_pair() -> None:
    d = blink()
    d.add(USB2(Net("USB_DP"), Net("USB_DM")))
    (warning,) = found(d, "build.diff-pair-name")
    assert warning.severity == "warning" and "USB_DP" in warning.message and "USB_DM" in warning.message
    assert "USB_DN" in warning.hint and warning.where == "USB_DP/USB_DM"
    (info,) = found(d, "build.interface-not-lowered")
    assert "USB_DP/USB_DM" in info.message


def test_names_that_kicad_pairs() -> None:
    d = blink()
    d.add(USB2(Net("USB_P"), Net("USB_N")), DiffPair(Net("CLK+"), Net("CLK-")))
    assert found(d, "build.diff-pair-name") == []
    assert len(found(d, "build.interface-not-lowered")) == 2


def test_diff_pair_names_checked() -> None:
    d = blink()
    d.add(DiffPair(Net("CLK_P"), Net("CLKN")))
    (info,) = found(d, "build.interface-not-lowered")
    (warning,) = found(d, "build.diff-pair-name")
    assert "CLK_P/CLKN" in info.message and "CLK_P" in warning.message and "CLKN" in warning.message
    assert "CLK_N" in warning.hint


def i2c_design(*, pull_scl: bool) -> Design:
    d = blink()
    u1, vin = d.parts["U1"], d.nets["VIN"]
    sda, scl = Net("SDA"), Net("SCL")
    bus = I2C(sda, scl)
    d.add(bus)
    bus.attach(u1, sda=2, scl=3)
    lines = [("R2", sda)] + ([("R3", scl)] if pull_scl else [])
    for ref, line in lines:
        pull = Part(ref, "Mini:Mini_R", footprint="Mini:Mini_R_0603", value=ohm("4k7"))
        d.add(pull)
        connect(line, pull[1])
        connect(vin, pull[2])
    return d


def test_missing_pull_up() -> None:
    (warning,) = found(i2c_design(pull_scl=False), "build.i2c-pullup-missing")
    assert warning.severity == "warning" and "SDA/SCL" in warning.message and "scl" in warning.message
    assert warning.where == "SDA/SCL" and "two pins" in warning.hint


def test_both_lines_pulled_up() -> None:
    d = i2c_design(pull_scl=True)
    out = build(d)
    assert [i for i in out.issues if i.code == "build.i2c-pullup-missing"] == []
    assert {c.ref: c.value for c in out.design.circuit.components}["R2"] == "4.7kΩ"


def test_pull_up_needs_a_power_interface() -> None:
    d = i2c_design(pull_scl=True)
    d.interfaces.pop("VIN/GND")
    assert len(found(d, "build.i2c-pullup-missing")) == 2


def test_no_interface_no_code_and_same_files() -> None:
    plain = build(blink())
    assert not {"build.diff-pair-name", "build.i2c-pullup-missing"} & {i.code for i in plain.issues}
    d = blink()
    d.add(UART(Net("A_TX"), Net("A_RX")), USB2(Net("USB_P"), Net("USB_N")))
    with_buses = build(d)
    outside = {name for name in plain.files if not name.startswith(".fenolite/")}
    assert outside and all(with_buses.files[name] == plain.files[name] for name in outside)
    model = json.loads(with_buses.files[".fenolite/circuit.json"])
    assert {i["kind"] for i in model["interfaces"]} == {"power", "uart", "usb2"}


def test_build_command_reports_the_pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    append = (
        "from fenolite.dsl import USB2\n"
        'usb_dp, usb_dm = Net("USB_DP"), Net("USB_DM")\n'
        "design.add(USB2(usb_dp, usb_dm))\n"
    )
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    args = ["build", str(script(tmp_path, append)), "--out", str(tmp_path / "B"), "--dry-run", "--json"]
    assert cli_main.main(args) == 0
    issues = json.loads(stdout.getvalue())["issues"]
    pair = [i for i in issues if i["code"] == "build.diff-pair-name"]
    assert len(pair) == 1 and "USB_DN" in pair[0]["hint"]
    assert len([i for i in issues if i["code"] == "build.interface-not-lowered"]) == 1


def test_i2c_in_an_altium_build() -> None:
    plain_design = sample()
    plain = build_altium(to_model(plain_design), name=plain_design.name)
    design = sample()
    first, second = sorted(design.nets)[:2]
    design.add(I2C(design.nets[first], design.nets[second]))
    built = build_altium(to_model(design), name=design.name)
    outside = {name for name in plain.files if not name.startswith(".fenolite/")}
    assert outside and set(built.files) == set(plain.files)
    assert all(built.files[name] == plain.files[name] for name in outside)
    extra = [i for i in built.issues if i not in plain.issues]
    assert [(i.code, i.severity, i.where) for i in extra] == [("altium.not-lowered", "info", "interfaces")]
    assert f"{first}/{second} (i2c)" in extra[0].message
