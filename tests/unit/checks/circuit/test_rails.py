# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The circuit rules (capability verification-loop, "Rail voltage check" to "Split device ports"; change
c0252). The models are written with the DSL, whose blocks and device records state the parameters."""

from __future__ import annotations

from typing import Any

from _sensor_rails import EXAMPLE, sensor_devices

from fenolite.checks.circuit import circuit_issues
from fenolite.cli._script import run_design_script
from fenolite.core.errors import Issue
from fenolite.dsl import (
    I2C,
    Design,
    Logic,
    Net,
    Rail,
    amp,
    between,
    block,
    connect,
    ohm,
    pull_up,
    to_model,
    volt,
)

R = "Fenolite:Resistor"
FP = "Fenolite:Chip_0603"


COUNTS = frozenset({"circuit.value-unknown", "circuit.rating-missing", "circuit.policy-missing"})
"""The info counts of change c0253's contract half, which a model of device parts without ratings gives."""


def issues(design: Design, prefix: str = "circuit.") -> list[Issue]:
    return [i for i in circuit_issues(to_model(design)) if i.code.startswith(prefix)]


@block
def power(
    b: Any, *, direction: str = "in", voltage: Any = None, current: Any = None, share: bool = False
) -> None:
    """One power port with a resistor behind it, so that the port's net holds a pin."""
    port = b.port("VDD", Rail, direction=direction, voltage=voltage, current=current, share=share)
    r = b.part("R", R, footprint=FP)
    connect(port, r[1])


def test_sensor_on_a_5v_rail() -> None:
    d = Design("t")
    rail = d.rail("5V0", voltage=volt("5").pct(5))
    sen = d.use(power, "sen", voltage=between(volt("1.71"), volt("3.6")))
    connect(rail, sen.VDD)
    (found,) = issues(d)
    assert found.code == "circuit.rail-voltage" and found.severity == "error"
    for text in ("5V0", "sen/VDD", "1.71V..3.6V", "4.75V..5.25V"):
        assert text in found.message


def test_over_budget() -> None:
    """The bad variant of ``examples/sensor_rails``: 1.15 A of loads on the 1 A block port ``buck/VOUT``,
    and no finding for the regulator part inside the block."""
    model = to_model(run_design_script(EXAMPLE / "bad.py").design)
    (found,) = [i for i in circuit_issues(model) if i.code == "circuit.rail-current"]
    for text in ("3V3", "1.15A", "1A", "buck/VOUT"):
        assert text in found.message
    assert "U1" not in found.message
    assert not [i for i in circuit_issues(model) if i.code == "circuit.rail-sources"]


def test_load_of_1_2a_on_a_1a_source_fails() -> None:
    """Draws are never added to capacity: one out port of 1 A, one in port of up to 1.2 A and a pass-through
    connector port without current."""
    for draw, expected in (("1.2", 1), ("0.8", 0)):
        d = Design("t")
        rail = d.rail("5V0", voltage=volt("5").pct(5))
        src = d.use(power, "src", direction="out", voltage=volt("5").pct(2), current=amp(1))
        load = d.use(power, "load", current=amp(draw).max())
        connector = d.use(power, "j2", direction="inout")
        connect(rail, src.VDD, load.VDD, connector.VDD)
        found = issues(d, "circuit.rail-current")
        assert len(found) == expected
        if found:
            assert "1.2A" in found[0].message and "exceed sources 1A" in found[0].message


def test_two_regulators_on_one_rail() -> None:
    for shared in (False, True):
        d = Design("t")
        rail = d.rail("5V0", shared=shared)
        one = d.use(power, "buck1", direction="out")
        two = d.use(power, "J2", direction="out")
        connect(rail, one.VDD, two.VDD)
        found = issues(d, "circuit.rail-sources")
        if shared:
            assert found == []
        else:
            (only,) = found
            assert all(text in only.message for text in ("5V0", "buck1/VDD", "J2/VDD"))


def test_no_voltage_to_judge_against() -> None:
    d = Design("t")
    rail = d.rail("3V3")
    sen = d.use(power, "sen", voltage=between(volt("1.71"), volt("3.6")))
    connect(rail, sen.VDD)
    assert [i.code for i in issues(d)] == ["circuit.rail-unset"]
    assert "3V3" in issues(d)[0].message and "sen/VDD" in issues(d)[0].message


@block
def logic(b: Any, *, direction: str = "in") -> None:
    port = b.port("IO", Logic, direction=direction)
    r = b.part("R", R, footprint=FP)
    connect(port, r[1])


def _levels(
    driver: dict[str, Any], reader: dict[str, Any], *, same: bool = False, high: str = "3.3", low: str = "5"
) -> Design:
    d = Design("t")
    drive_rail = d.rail("3V3", voltage=volt(high).pct(3))
    read_rail = drive_rail if same else d.rail("5V0", voltage=volt(low).pct(10))
    out = d.use(logic, "drv", direction="out")
    out.IO.set(reference=drive_rail, **driver)
    inp = d.use(logic, "rdr")
    inp.IO.set(reference=read_rail, **reader)
    connect(Net("IRQ"), out.IO, inp.IO)
    return d


def test_33v_output_into_a_18v_input() -> None:
    d = _levels(
        {"output_high_min": volt("2.9"), "output_low_max": volt("0.4")},
        {
            "abs_max": between(volt("-0.3"), volt("1.98")),
            "input_high_min": volt("1.17"),
            "input_low_max": volt("0.63"),
        },
        low="1.8",
    )
    (found,) = issues(d)
    assert found.code == "circuit.logic-level"
    assert all(text in found.message for text in ("drv/IO", "rdr/IO", "3V3", "3.399V", "1.98V"))


WEAK = {"output_high_min": volt("2.4"), "output_low_max": volt("0.4")}
FIVE = {
    "input_high_min": volt("3.5"),
    "input_low_max": volt("1.5"),
    "abs_max": between(volt("-0.5"), volt("5.5")),
}


def test_a_weak_high_level() -> None:
    (found,) = issues(_levels(WEAK, FIVE))
    assert found.code == "circuit.logic-level" and "2.4V" in found.message and "3.5V" in found.message


def test_thresholds_not_stated() -> None:
    (found,) = issues(_levels({"output_low_max": volt("0.4")}, FIVE))
    assert found.code == "circuit.logic-unknown"
    assert "drv/IO output_high_min" in found.message


def test_same_reference_passes() -> None:
    assert issues(_levels(WEAK, FIVE, same=True)) == []


@block
def chip(b: Any, *, sinks: Any = None) -> None:
    port = b.port("I2C", I2C, requires=("pullup",), output_current_max=sinks)
    sda = b.part("R_SDA", R, footprint=FP)
    scl = b.part("R_SCL", R, footprint=FP)
    connect(port.sda, sda[1])
    connect(port.scl, scl[1])


def _bus(pull_to: str, value: Any, *, sinks: Any = None, scl: bool = True) -> Design:
    d = Design("t")
    v33 = d.rail("3V3", voltage=volt("3.3").pct(3))
    v50 = d.rail("5V0", voltage=volt("5").pct(5))
    bus = I2C(Net("SDA"), Net("SCL"), reference=v33)
    d.add(bus)
    sen = d.use(chip, "sen", sinks=sinks)
    sen.I2C.set(reference=v33)
    connect(bus, sen.I2C)
    resistors = [d.part(f"R{n}", R, footprint=FP, value=value) for n in (1, 2)]
    rail = v33 if pull_to == "3V3" else v50
    if scl:
        pull_up(bus, rail, *resistors)
    else:
        pull_up(bus.members["sda"], rail, resistors[0])
    return d


def test_pulled_up_to_the_wrong_rail() -> None:
    found = issues(_bus("5V0", ohm("4k7")), "circuit.bus-pullup")
    assert len(found) == 2
    assert {"SDA", "SCL"} == {i.message.split()[0] for i in found}
    assert all("5V0" in i.message and "3V3" in i.message for i in found)


def test_a_pullup_stronger_than_a_port_sinks() -> None:
    found = issues(_bus("3V3", ohm("470").pct(1), sinks=amp("0.003")), "circuit.bus-pullup")
    assert len(found) == 2
    assert all("sen/I2C" in i.message and "3mA" in i.message and "7.30" in i.message for i in found)


def test_a_sensor_without_pullups() -> None:
    (found,) = issues(_bus("3V3", ohm("4k7"), scl=False), "circuit.requires-missing")
    assert "sen/I2C" in found.message and "pullup" in found.message and "SCL" in found.message


def test_a_device_sensor_without_pullups_has_its_supply() -> None:
    d = Design("t")
    d.devices(*sensor_devices())
    v33 = d.rail("3V3")
    src = d.use(power, "buck", direction="out", voltage=volt("3.3").pct(3), current=amp(1))
    mcu = d.part("U2", device="Example:MCU_SO8")
    sen = d.part("U3", device="Example:SENSOR_I2C")
    connect(v33, src.VDD, mcu.vdd, sen.vdd)
    connect(I2C(Net("SDA"), Net("SCL")), mcu.i2c1, sen.i2c)
    r1 = d.part("R1", R, footprint=FP, value="4k7")
    connect(mcu.i2c1.sda, r1[1])
    connect(v33, r1[2])
    (found,) = issues(d, "circuit.requires-missing")
    assert "U3.i2c" in found.message and "pullup" in found.message and "SCL" in found.message


def test_vdd_and_vdda_split() -> None:
    d = Design("t")
    d.devices(*sensor_devices())
    mcu = d.part("U2", device="Example:MCU_SO8")
    v33 = d.rail("3V3", voltage=volt("5"))
    connect(v33, mcu.VDD)
    connect(Net("3V3A"), mcu.VDDA)
    found = [i for i in issues(d) if i.code not in COUNTS]
    assert [i.code for i in found] == ["circuit.port-split"]
    assert all(text in found[0].message for text in ("U2", "vdd", "3V3", "3V3A"))


def test_good_variant_has_no_finding() -> None:
    model = to_model(run_design_script(EXAMPLE / "good.py").design)
    assert [i for i in circuit_issues(model) if i.code not in COUNTS] == []  # c0253's counts are info
