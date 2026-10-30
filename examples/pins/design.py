# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Pin assignment at the interface level (change c0257, ``docs/pins.md``).

The MCU (an illustrative device of ``devices/``, not a real product) offers its I2C on two pin sets and its
UART2 on two others. The script names the functions, not the pins: ``mcu.take(I2C)`` and
``mcu.take(UART, option="UART2", name="debug")``. ``fenolite build`` chooses the pins, shows them in
``result.pins`` and records them in the ``[pins]`` section of ``design.lock`` beside the script, so a later
build keeps them and ``--frozen`` refuses to change them.

Build it with ``fenolite build examples/pins/design.py --out build/pins --confirm``.
"""

from __future__ import annotations

from fenolite.dsl import I2C, UART, Design, Net, Symbol, connect, decouple, mm, pull_up


def _symbol(name: str, pins: list[tuple[str, str]]) -> Symbol:
    """A rectangle with the first half of ``pins`` on the left and the rest on the right."""
    made = Symbol("Example", name, reference="U")
    half = (len(pins) + 1) // 2
    for index, (number, pin) in enumerate(pins):
        left = index < half
        y = mm(2.54) * ((index if left else index - half) - half // 2)
        x = mm(-12.7) if left else mm(12.7)
        made.pin(number, pin, at=(x, y), length=mm(2.54), rotation=0 if left else 180)
    top = mm(2.54) * (half // 2 + 1)
    made.rect((mm(-10.16), -top), (mm(10.16), top))
    return made


MCU_PINS = [
    ("1", "VDD"), ("2", "PA0"), ("3", "PA1"), ("4", "PA2"), ("5", "PA3"), ("6", "PA4"), ("7", "PA5"),
    ("8", "PA6"), ("9", "PA7"), ("10", "PB0"), ("11", "PB1"), ("12", "PB2"), ("13", "PB3"), ("14", "PB4"),
    ("15", "PB5"), ("16", "VSS"), ("17", "VDDA"), ("18", "PB6"), ("19", "PB7"), ("20", "PB8"), ("21", "PB9"),
    ("22", "PB10"), ("23", "PB11"), ("24", "PC0"), ("25", "PC1"), ("26", "PC2"), ("27", "PC3"),
    ("28", "PC4"), ("29", "PC5"), ("30", "NRST"), ("31", "BOOT0"), ("32", "VSS"),
]  # fmt: skip
SENSOR_PINS = [("1", "VDD"), ("2", "GND"), ("3", "SDA"), ("4", "SCL"), ("5", "INT"), ("6", "ADDR")]

design = Design("pins")
design.board(mm(40), mm(30))
design.add(_symbol("MCU_32pin", MCU_PINS), _symbol("Sensor_6pin", SENSOR_PINS))

v33, gnd = Net("3V3"), Net("GND")
power = design.part(name="power", device="Fenolite:Conn_1x2_P2.54", value="3V3 IN")
mcu = design.part(name="mcu", device="Example:MCU_QFN32")
sen = design.part(name="sen", device="Example:SENSOR_I2C")
header = design.part(name="header", device="Example:DEBUG_HEADER", value="DEBUG")
connect(v33, power.P1, mcu.VDD, mcu.VDDA, sen.VDD)
connect(gnd, power.P2, mcu.VSS, sen.GND, sen.ADDR, header.GND)

i2c = mcu.take(I2C)  # one of the device's i2c alternatives, chosen at build
connect(i2c, sen.i2c)  # SDA to SDA, SCL to SCL
r_sda = design.part(name="r_sda", device="Fenolite:R_0603", value="4k7")
r_scl = design.part(name="r_scl", device="Fenolite:R_0603", value="4k7")
pull_up(i2c, v33, r_sda, r_scl)

debug = mcu.take(UART, option="UART2", name="debug")
connect(debug, header.uart)  # the MCU's TX to the header's RX, and back

c1 = design.part(name="c1", device="Fenolite:C_0603", value="100n")
decouple(v33, gnd, c1)
mcu.unused_no_connect()  # applied after the solve, on the pins no take was given
sen.unused_no_connect()

power.place(mm(4), mm(15), rot=90, locked=True)
mcu.place(mm(18), mm(15))
sen.place(mm(32), mm(9))
header.place(mm(32), mm(22), rot=90)
r_sda.place(mm(26), mm(5))
r_scl.place(mm(26), mm(9))
c1.place(mm(12), mm(22))
