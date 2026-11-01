# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Voltage propagation through links and the origins of applied values (change c0274; capability
verification-loop, "Voltage propagation through links" and "Origins of applied values"; hypothesis
``H-G-CIRCUIT-PROPAGATION``). The example and every record are authored for Fenolite."""

from __future__ import annotations

import shutil
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from _contracts import ROOT, cli, codes, device, judge, row

from fenolite.checks.circuit import judge_circuit
from fenolite.cli._contracts import classes_of, devices_of
from fenolite.cli._script import run_design_script
from fenolite.dsl import Design, connect, henry, ohm, to_model, volt

FERRITE = ROOT / "examples" / "circuit" / "ferrite"
SENSOR = device(
    'id = "Test:SEN"\nsymbol = "Fenolite:Linear_Regulator"\nfootprint = "Fenolite:SOT23_3"\nground = "GND"\n'
    '[pins]\nGND = "1"\nVDDA = "2"\nOUT = "3"\n'
    '[[interfaces]]\nname = "vdda"\nkind = "power"\ndirection = "in"\n'
    'members = { hv = ["VDDA"], lv = ["GND"] }\nvoltage = { min = "1.71V", max = "3.6V" }\n'
)
FB = device(
    'id = "Test:FB"\nsymbol = "Fenolite:Ferrite_Bead"\nfootprint = "Fenolite:Chip_0603"\nclass = "ferrite"\n'
    'ends = ["P1", "P2"]\n[pins]\nP1 = "1"\nP2 = "2"\n'
)


def _example(variant: str) -> Any:
    model = to_model(run_design_script(FERRITE / f"{variant}.py").design)
    devices = devices_of(model, FERRITE)
    return judge_circuit(model, devices=devices, classes=classes_of(model, devices))


def test_an_analog_rail_behind_a_ferrite() -> None:
    """Scenario "An analog rail behind a ferrite"."""
    good = _example("good")
    vdda = row(good, "circuit.rail-voltage:3V3A:U1/vdda")
    assert vdda.status == "pass"
    assert (vdda.value.range.low, vdda.value.range.high) == (Fraction("3.201"), Fraction("3.399"))
    assert not [i for i in good.issues if i.code == "circuit.rail-unset"]
    assert [i for i in good.issues if i.severity != "info"] == []
    bad = _example("bad")
    (unset,) = [i for i in bad.issues if i.code == "circuit.rail-unset"]
    assert unset.where == "3V3A"
    assert not [r for r in bad.rows if r.id.startswith("circuit.rail-voltage:3V3A")]


def test_the_origin_of_a_propagated_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "The origin of a propagated value": through ``fenolite check`` on the built good variant."""
    folder = tmp_path / "ferrite"
    shutil.copytree(FERRITE, folder, ignore=shutil.ignore_patterns("__pycache__"))
    out = folder / "build"
    code, env = cli(monkeypatch, "build", str(folder / "good.py"), "--out", str(out), "--confirm")
    assert code == 0, env["issues"]
    code, env = cli(monkeypatch, "check", str(out), "--stages", "circuit.rules")
    assert code == 0, env["issues"]
    (stage,) = env["result"]["stages"]
    rows = {found["id"]: found for found in stage["summary"]["requirements"]}
    vdda = rows["circuit.rail-voltage:3V3A:U1/vdda"]
    assert vdda["value"]["origin"] == {"from": "3V3", "kind": "propagated", "via": ["FB1"]}
    assert vdda["value"]["basis"] == "propagated via FB1 from 3V3"
    assert rows["circuit.rating-voltage:C1:voltage"]["value"]["origin"]["kind"] == "declared"


def _linked(link: str, *, stated_jumper: bool = False, propagate: bool = True) -> Design:
    """``3V3`` (3.3 V ± 3 %) and a sensor on ``3V3A`` joined by ``link``."""
    d = Design("t")
    d.devices(SENSOR, FB)
    gnd = d.ground("GND")
    v33 = d.rail("3V3", ground=gnd, voltage=volt("3.3").pct(3))
    v33a = d.rail("3V3A", ground=gnd)
    made = {
        "ferrite": lambda: d.part("FB1", device="Test:FB"),
        "zero": lambda: d.part("R1", device="Fenolite:R_0603", value=ohm("0").pct(1)),
        "ten": lambda: d.part("R1", device="Fenolite:R_0603", value=ohm("10")),
        "inductor": lambda: d.part(
            "L1", "Fenolite:Inductor", footprint="Fenolite:Chip_0603", value=henry("1u")
        ),
        "jumper": lambda: d.part("JP1", "Fenolite:Ferrite_Bead", footprint="Fenolite:Chip_0603"),
    }[link]()
    connect(v33, made[1])
    connect(v33a, made[2])
    if stated_jumper:
        d.part_class(made, "jumper")
    sensor = d.part("U1", device="Test:SEN")
    connect(v33a, sensor.vdda)
    connect(gnd, sensor.GND)
    if not propagate:
        d.contracts(propagate=False)
    return d


@pytest.mark.parametrize(
    ("link", "stated", "crossed"),
    [
        ("ferrite", False, True),
        ("zero", False, True),
        ("jumper", True, True),
        ("jumper", False, False),
        ("ten", False, False),
        ("inductor", False, False),
    ],
)
def test_what_is_crossed(link: str, stated: bool, crossed: bool) -> None:
    result = judge(_linked(link, stated_jumper=stated))
    found = [r for r in result.rows if r.id == "circuit.rail-voltage:3V3A:U1/vdda"]
    assert bool(found) is crossed
    assert ("circuit.rail-unset" in codes(result, at_least="warning")) is not crossed


def test_propagation_can_be_turned_off() -> None:
    result = judge(_linked("ferrite", propagate=False))
    assert "circuit.rail-unset" in codes(result, at_least="warning")


def test_linked_stated_nets_that_disagree() -> None:
    """Two stated rails joined by a ferrite whose ranges do not overlap give ``circuit.value-conflict``
    naming the link."""
    d = Design("t")
    d.devices(FB)
    gnd = d.ground("GND")
    v33 = d.rail("3V3", ground=gnd, voltage=volt("3.3").pct(3))
    v50 = d.rail("5V0", ground=gnd, voltage=volt("5").pct(5))
    fb1 = d.part("FB1", device="Test:FB")
    connect(v33, fb1.P1)
    connect(v50, fb1.P2)
    (conflict,) = [i for i in judge(d).issues if i.code == "circuit.value-conflict"]
    assert all(text in conflict.message for text in ("3V3", "5V0", "FB1"))
