# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Ratings and operating ranges of the contract judge (change c0253; capability electrical-contracts,
"Absolute and operating limits", "Voltage ratings", "Pin-pair limits", "Device current by class", "Resistor
power", "Temperature ratings", "Contract severities" and "Strictness of unknown rows"). Every device record is
authored for these tests; no value comes from a datasheet."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import pytest
from _contracts import codes, device, judge, row, two_pin

from fenolite.dsl import (
    Design,
    DslError,
    Net,
    Rail,
    amp,
    between,
    block,
    celsius,
    connect,
    henry,
    ohm,
    ratio,
    supply,
    volt,
)

REGULATOR = device(
    'id = "Test:REG"\nsymbol = "Fenolite:Linear_Regulator"\nfootprint = "Fenolite:SOT23_3"\nground = "GND"\n'
    '[pins]\nGND = "1"\nVOUT = "2"\n'
    'VIN = { pins = ["3"], voltage = { operating = { min = "2.7V", max = "6V" }, abs_max = "6.5V" } }\n'
)
BIG_REGULATOR = device(
    'id = "Test:REG6"\nsymbol = "Fenolite:Linear_Regulator"\nfootprint = "Fenolite:SOT23_3"\nground = "GND"\n'
    '[pins]\nGND = "1"\nVOUT = "2"\nVIN = { pins = ["3"], voltage = { abs_max = "6V" } }\n'
)


def _bench(d: Design, net: Any, gnd: Any, voltage: Any = None) -> None:
    d.rig(supply(net, gnd, voltage=voltage or volt("12").pct(10), current=amp(3), name="bench"))


def _across(d: Design, record: Any, net: Any, gnd: Any, ref: str = "C1", value: Any = "10u") -> Any:
    d.devices(record)
    part = d.part(ref, device=record.id, value=value)
    connect(net, part.P1)
    connect(gnd, part.P2)
    return part


def test_operating_derating_never_loosens_a_minimum() -> None:
    """Scenario "A derating never loosens a minimum"."""
    d = Design("t")
    d.devices(REGULATOR)
    gnd = d.ground("GND")
    vin = d.rail("VIN", voltage=between(volt("2.5"), volt("2.6")), ground=gnd)
    u1 = d.part("U1", device="Test:REG")
    connect(vin, u1.VIN)
    connect(gnd, u1.GND)
    connect(Net("OUT"), u1.VOUT)
    d.derating(pin_voltage=ratio(50))
    result = judge(d)
    (found,) = [i for i in result.issues if i.code == "circuit.operating-range"]
    assert found.severity == "error" and all(t in found.message for t in ("VIN", "2.5V", "2.7V"))
    absolute = row(result, "circuit.rating-voltage:U1:VIN")
    assert absolute.status == "pass" and absolute.limit.source == "policy"
    assert absolute.limit.range.high == Fraction(325, 100)


def test_capacitor_without_a_policy() -> None:
    """Scenario "Input capacitor without a policy"."""
    d = Design("t")
    gnd = d.ground("GND")
    v12 = d.rail("V12", ground=gnd)
    _across(d, two_pin("Test:CAP_10V", 'voltage = { abs_max = "10V" }'), v12, gnd)
    _bench(d, v12, gnd)
    result = judge(d)
    (found,) = [i for i in result.issues if i.code == "circuit.rating-voltage"]
    assert found.severity == "error" and all(t in found.message for t in ("C1", "13.2V", "10V"))
    voltage = row(result, "circuit.rating-voltage:C1:voltage")
    assert (voltage.limit.source, voltage.value.source, voltage.value.basis) == (
        "device",
        "user",
        "rig bench; ground GND",
    )


def test_pin_rating_of_a_regulator() -> None:
    """Scenario "Pin rating of a regulator"."""
    d = Design("t")
    d.devices(BIG_REGULATOR)
    gnd = d.ground("GND")
    v12 = d.rail("V12", ground=gnd)
    u1 = d.part("U1", device="Test:REG6")
    connect(v12, u1.VIN)
    connect(gnd, u1.GND)
    connect(Net("OUT"), u1.VOUT)
    _bench(d, v12, gnd)
    (found,) = [i for i in judge(d).issues if i.code == "circuit.rating-voltage"]
    assert all(t in found.message for t in ("U1", "VIN", "13.2V", "6V"))


def test_drain_to_source() -> None:
    """Scenario "Drain to source": a pin's voltage is measured from the device's ground function."""
    fet = device(
        'id = "Test:FET"\nsymbol = "Fenolite:MOSFET_N_Channel"\nfootprint = "Fenolite:SOT23_3"\n'
        'ground = "S"\n'
        '[pins]\nG = "1"\nS = "2"\nD = { pins = ["3"], voltage = { abs_max = "40V" } }\n'
    )
    d = Design("t")
    d.devices(fet)
    gnd = d.ground("GND")
    v48 = d.rail("V48", ground=gnd)
    q1 = d.part("Q1", device="Test:FET")
    connect(v48, q1.D)
    connect(gnd, q1.S)
    connect(Net("GATE"), q1.G)
    _bench(d, v48, gnd, volt("48").pct(5))
    result = judge(d)
    (found,) = [i for i in result.issues if i.code == "circuit.rating-voltage"]
    assert all(t in found.message for t in (" D ", "50.4V", "40V"))


def _buck(bounded: bool) -> Design:
    record = device(
        'id = "Test:BUCK"\nsymbol = "Fenolite:Power_Module"\nfootprint = "Fenolite:SOT23_3"\nground = "GND"\n'
        '[pins]\nGND = "1"\nBST = "2"\nSW = "3"\n'
        '[[limits]]\nbetween = ["BST", "SW"]\nvoltage = { abs_max = "6V" }\n'
    )
    d = Design("t")
    d.devices(record)
    gnd = d.ground("GND")
    bst = d.rail("BST", voltage=between(volt(17), volt(19)), ground=gnd)
    sw = d.rail("SW", voltage=between(volt(12), volt("13.2")), ground=gnd) if bounded else Net("SW")
    u1 = d.part("U1", device="Test:BUCK")
    connect(bst, u1.BST)
    connect(sw, u1.SW)
    connect(gnd, u1.GND)
    return d


def test_pair_bootstrap_to_switch_node() -> None:
    """Scenario "Bootstrap to switch node"."""
    found = row(judge(_buck(True)), "circuit.rating-voltage:U1:BST-SW")
    assert found.status == "fail" and found.value.range.high == 7 and found.limit.range.high == 6
    assert row(judge(_buck(False)), "circuit.rating-voltage:U1:BST-SW").status == "unknown"


@block
def _load(b: Any, *, current: Any = None) -> None:
    port = b.port("VDD", Rail, direction="in", current=current)
    gnd = b.port("GND", Net)
    r = b.part("R", device="Fenolite:R_0603", value=ohm("1k"))
    connect(port, r.P1)
    connect(gnd, r.P2)


@block
def _supply(b: Any, *, current: Any = None) -> None:
    port = b.port("VOUT", Rail, direction="out", voltage=volt("3.3").pct(3), current=current)
    r = b.part("R", device="Fenolite:R_0603", value=ohm("1k"))
    connect(port, r.P1)


def _rail_with_loads(d: Design, total: Any) -> tuple[Any, Any]:
    gnd = d.ground("GND")
    v33 = d.rail("3V3", ground=gnd)
    source = d.use(_supply, "src", current=amp(5))
    connect(v33, source.VOUT)
    load = d.use(_load, "load", current=total.max())
    connect(v33, load.VDD)
    connect(gnd, load.GND)
    return v33, gnd


def test_inductor_on_a_busier_rail() -> None:
    """Scenario "Inductor on a busier rail": the smaller of the two nets' bounds."""
    d = Design("t")
    v33, _gnd = _rail_with_loads(d, amp("1.2"))
    sw = Net("SW")
    d.devices(two_pin("Test:IND_1A", 'current = { abs_max = "1A" }', symbol="Fenolite:Inductor"))
    inductor = d.part("L1", device="Test:IND_1A", value=henry("4u7"))
    connect(sw, inductor.P1)
    connect(v33, inductor.P2)
    d.net_role(sw, "switch_node", current=amp("1.5"))
    result = judge(d)
    (found,) = [i for i in result.issues if i.code == "circuit.rating-current"]
    assert all(t in found.message for t in ("L1", "1.2A", "1A"))
    assert row(result, "circuit.rating-current:L1:current").value.basis == "rail 3V3"


def test_regulator_judged_by_its_output_port() -> None:
    """Scenario "A regulator judged by its output port"."""
    record = device(
        'id = "Test:LDO"\nsymbol = "Fenolite:Linear_Regulator"\nfootprint = "Fenolite:SOT23_3"\n'
        'ground = "GND"\n'
        '[pins]\nGND = "1"\nVOUT = "2"\nVIN = "3"\n[ratings]\ncurrent = { abs_max = "2A" }\n'
        '[[interfaces]]\nname = "vout"\nkind = "power"\ndirection = "out"\n'
        'members = { hv = ["VOUT"], lv = ["GND"] }\ncurrent = "3A"\n'
    )
    d = Design("t")
    d.devices(record)
    gnd = d.ground("GND")
    v33 = d.rail("3V3", ground=gnd)
    u1 = d.part("U1", device="Test:LDO")
    connect(v33, u1.VOUT)
    connect(gnd, u1.GND)
    connect(Net("IN"), u1.VIN)
    load = d.use(_load, "load", current=amp("2.4").max())
    connect(v33, load.VDD)
    connect(gnd, load.GND)
    (found,) = [i for i in judge(d).issues if i.code == "circuit.rating-current"]
    assert all(t in found.message for t in ("U1", "vout", "2.4A", "2A"))


def test_pull_up_is_not_judged_by_current() -> None:
    """Scenario "A pull-up is not judged by current"."""
    d = Design("t")
    v33, _gnd = _rail_with_loads(d, amp("1.2"))
    d.devices(two_pin("Test:RES", 'current = { abs_max = "10mA" }', symbol="Fenolite:Resistor"))
    r1 = d.part("R1", device="Test:RES", value=ohm("4k7"))
    connect(v33, r1.P1)
    connect(Net("SDA"), r1.P2)
    result = judge(d)
    assert "circuit.rating-current" not in codes(result)
    assert not [r for r in result.rows if r.id.startswith("circuit.rating-current:R1")]


def test_bleeder_across_the_input() -> None:
    """Scenario "A bleeder across the input": 13.2² / 990 = 0.176 W, exactly."""
    d = Design("t")
    gnd = d.ground("GND")
    v12 = d.rail("V12", ground=gnd)
    record = two_pin("Test:RES_0W1", 'power = { abs_max = "0.1W" }', symbol="Fenolite:Resistor")
    _across(d, record, v12, gnd, "R1", ohm("1k").pct(1))
    _bench(d, v12, gnd)
    result = judge(d)
    (found,) = [i for i in result.issues if i.code == "circuit.rating-power"]
    assert all(t in found.message for t in ("R1", "176mW", "100mW"))
    assert row(result, "circuit.rating-power:R1:power").value.range.high == Fraction(176, 1000)


def test_commercial_part_in_a_cold_box() -> None:
    """Scenario "A commercial part in a cold box": both ranges printed in degrees Celsius."""
    d = Design("t")
    record = two_pin("Test:COM", 'temperature = { operating = { min = "0degC", max = "70degC" } }')
    _across(d, record, Net("A"), Net("B"))
    d.operating(ambient=between(celsius(-20), celsius(70)))
    (found,) = [i for i in judge(d).issues if i.code == "circuit.operating-range"]
    assert all(t in found.message for t in ("C1", "-20°C..70°C", "0°C..70°C"))


def _ten_parts() -> Design:
    d = Design("t")
    d.devices(two_pin("Test:CAP_25V", 'voltage = { abs_max = "25V" }'))
    for index in range(1, 11):
        part = d.part(f"C{index}", device="Test:CAP_25V", value="10u")
        connect(Net(f"A{index}"), part.P1)
        connect(Net(f"B{index}"), part.P2)
    return d


def test_unknown_rows_stay_quiet_by_default() -> None:
    """Scenario "Unknown rows stay quiet by default"."""
    result = judge(_ten_parts())
    assert sorted((i.code, i.severity) for i in result.issues) == [
        ("circuit.policy-missing", "info"),
        ("circuit.value-unknown", "info"),
    ]
    assert "10 contract row(s)" in next(i.message for i in result.issues if i.code == "circuit.value-unknown")


def test_a_design_that_states_nothing_does_not_pass_quietly() -> None:
    """Scenario "A design that states nothing does not pass quietly"."""
    d = _ten_parts()
    d.contracts(unknown="warning")
    unknown = [i for i in judge(d).issues if i.code == "circuit.value-unknown"]
    assert len(unknown) == 10 and all(i.severity == "warning" and "voltage of" in i.message for i in unknown)
    with pytest.raises(DslError, match="info, warning"):
        d.contracts(unknown="error")
