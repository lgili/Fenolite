# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The sensor board of ``examples/sensor_rails`` (change c0252; ``docs/dsl.md``, "Rails, grounds and logic").

A 12 V input feeds the block ``buck``, whose port ``VOUT`` promises 3.3 V ± 3 % at 1 A. An MCU and an I2C
sensor (illustrative devices of ``devices/`` beside the scripts, not real products) declare their interface
ports in their records: ``vdd``, ``i2c1``/``i2c``, ``pa3`` and ``int_``. The script joins whole interfaces
(``connect(bus, mcu.i2c1, sen.i2c)``), and ``fenolite build`` and ``fenolite check`` judge the rails, the
logic levels and the pull-ups from the model alone. ``bad=True`` adds a fan of up to 1.1 A on ``3V3``, which
overloads the regulator, and pulls the bus up to ``V12`` instead of its reference rail ``3V3``. Every value is
chosen for the example.
"""

from __future__ import annotations

from typing import Any

from fenolite.dsl import (
    I2C,
    Design,
    Ground,
    Logic,
    Net,
    Rail,
    Symbol,
    amp,
    between,
    block,
    connect,
    decouple,
    mm,
    ohm,
    pull_up,
    volt,
)

VOUT = volt("3.3").pct(3)  # the regulator block's promise; chosen for the example
CURRENT = amp(1)  # what the block's source port guarantees; chosen for the example
VIN = volt("12").pct(10)  # the input rail; chosen for the example
PULLUP = between(ohm("1k"), ohm("10k"))  # the pull-up range the bus accepts; chosen for the example


def _symbol(name: str, pins: list[tuple[str, str]]) -> Symbol:
    """A rectangle with the first half of ``pins`` on the left and the rest on the right."""
    made = Symbol("Example", name, reference="U")
    half = (len(pins) + 1) // 2
    for index, (number, pin) in enumerate(pins):
        left = index < half
        y = mm(2.54) * ((index if left else index - half) - 1)
        x = mm(-10.16) if left else mm(10.16)
        made.pin(number, pin, at=(x, y), length=mm(2.54), rotation=0 if left else 180)
    made.rect((mm(-7.62), mm(-5.08)), (mm(7.62), mm(7.62)))
    return made


SYMBOLS = (
    ("MCU_8pin", [("1", "VDD"), ("2", "VDDA"), ("3", "VSS"), ("4", "PA3"), ("5", "PB6"), ("6", "PB7"),
                  ("7", "PA0"), ("8", "PA1")]),
    ("Sensor_6pin", [("1", "VDD"), ("2", "GND"), ("3", "SDA"), ("4", "SCL"), ("5", "INT"), ("6", "ADDR")]),
    ("Reg_5pin", [("1", "VIN"), ("2", "GND"), ("3", "EN"), ("4", "NC"), ("5", "VOUT")]),
)  # fmt: skip


@block
def buck(b: Any, *, vout: Any = VOUT, current: Any = CURRENT) -> None:
    """A 3.3 V regulator with its two capacitors. Ports: VIN (in), VOUT (out, the promise), GND."""
    vin = b.port("VIN", Rail, direction="in")
    out = b.port("VOUT", Rail, direction="out", voltage=vout, current=current)
    gnd = b.port("GND", Ground)
    reg = b.part("U", device="Example:REG_3V3_1A")
    c_in = b.part("C_IN", device="Fenolite:C_0805", value="10u")
    c_out = b.part("C_OUT", device="Fenolite:C_0805", value="22u")
    connect(vin, reg.vin)  # hv and lv, member by member
    connect(out, reg.vout)
    connect(gnd, reg.GND)
    decouple(vin, gnd, c_in)
    decouple(out, gnd, c_out)
    reg.unused_no_connect()
    reg.place(mm(17), mm(15))
    c_in.place(mm(11), mm(15), rot=90)
    c_out.place(mm(23), mm(15), rot=90)


def sensor_board(design: Design, *, bad: bool = False) -> Design:
    """The board in ``design``; ``bad`` adds the overload and the wrong pull-up rail."""
    design.board(mm(50), mm(30))
    for symbol, pins in SYMBOLS:
        design.add(_symbol(symbol, pins))

    gnd = design.ground("GND")
    v12 = design.rail("V12", voltage=VIN, ground=gnd)
    v33 = design.rail("3V3", ground=gnd)  # its voltage comes from the source port buck.VOUT

    j1 = design.part("J1", device="Fenolite:Conn_1x2_P2.54", value="12V IN")
    connect(v12, j1.P1)
    connect(gnd, j1.P2)
    power = design.use(buck, "buck")
    connect(v12, power.VIN)
    connect(v33, power.VOUT)
    connect(gnd, power.GND)

    mcu = design.part("U2", device="Example:MCU_SO8")
    sen = design.part("U3", device="Example:SENSOR_I2C")
    connect(v33, mcu.vdd, sen.vdd)
    bus = I2C(Net("SDA"), Net("SCL"), reference=v33, pullup=PULLUP)
    irq = Logic(Net("INT"), reference=v33)
    design.add(bus, irq)
    connect(bus, mcu.i2c1, sen.i2c)  # SDA to SDA, SCL to SCL
    connect(irq, sen.int_, mcu.pa3)
    connect(gnd, sen.ADDR)
    r_sda = design.part("R1", device="Fenolite:R_0603", value="4k7")
    r_scl = design.part("R2", device="Fenolite:R_0603", value="4k7")
    pull_up(mcu.i2c1, v12 if bad else v33, r_sda, r_scl)
    c1 = design.part("C1", device="Fenolite:C_0603", value="100n")
    decouple(v33, gnd, c1)
    mcu.unused_no_connect()

    j1.place(mm(4), mm(15), rot=90, locked=True)
    mcu.place(mm(30), mm(12))
    sen.place(mm(42), mm(12))
    r_sda.place(mm(36), mm(22))
    r_scl.place(mm(40), mm(22))
    c1.place(mm(30), mm(22))
    if bad:
        fan = design.part("J2", device="Example:FAN_HEADER", value="FAN")
        connect(v33, fan.supply)
        fan.place(mm(46), mm(25), rot=90)
    return design
