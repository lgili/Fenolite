# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The analog rail of ``examples/circuit/ferrite`` (change c0274; ``docs/contracts.md``, "Propagation through
links").

The rail ``3V3`` is set to 3.3 V ± 3 % (3.201 V to 3.399 V). An analog sensor (an illustrative device of
``devices/`` beside the scripts, not a real product) takes its supply port ``vdda`` (1.71 V to 3.6 V) from the
net ``3V3A``, which has no voltage of its own: it is fed from ``3V3`` through the ferrite ``FB1``. The stage
``circuit.rules`` carries the voltage of ``3V3`` across the ferrite, so ``vdda`` is judged with it.
``resistor=True`` puts a 10 Ω resistor in the ferrite's place: nothing crosses a resistor above 0 Ω, so
``3V3A`` keeps no voltage and ``circuit.rail-unset`` names it. Every value is chosen for the example.
"""

from __future__ import annotations

from fenolite.dsl import Design, Symbol, connect, mm, ohm, volt

V33 = volt("3.3").pct(3)  # the rail's voltage; chosen for the example


def sensor_symbol() -> Symbol:
    """The symbol the example sensor names: six pins, numbered as its land."""
    made = Symbol("Example", "Sensor_6pin", reference="U")
    for number, name, y in (("1", "VDDA", -2.54), ("2", "GND", 0), ("3", "OUT", 2.54)):
        made.pin(number, name, at=(mm(-7.62), mm(y)), length=mm(2.54))
    for number, name, y in (("4", "REF", 2.54), ("5", "EN", 0), ("6", "NC", -2.54)):
        made.pin(number, name, at=(mm(7.62), mm(y)), length=mm(2.54), rotation=180)
    made.rect((mm(-5.08), mm(-5.08)), (mm(5.08), mm(5.08)))
    return made


def analog_board(design: Design, *, resistor: bool = False) -> Design:
    """The board in ``design``; ``resistor`` replaces the ferrite by a 10 Ω resistor."""
    design.board(mm(30), mm(20))
    design.add(sensor_symbol())
    gnd = design.ground("GND")
    v33 = design.rail("3V3", ground=gnd, voltage=V33)
    v33a = design.rail("3V3A", ground=gnd)  # no voltage: it comes through the link
    j1 = design.part("J1", device="Fenolite:Conn_1x2_P2.54", value="3V3 IN")
    connect(v33, j1.P1)
    connect(gnd, j1.P2)
    c1 = design.part("C1", device="Example:CAP_10V", value="1u")
    connect(v33, c1.P1)
    connect(gnd, c1.P2)
    if resistor:
        link = design.part("R1", device="Fenolite:R_0603", value=ohm("10").pct(1))
    else:
        link = design.part("FB1", device="Example:FB_600R", value="600R")
    connect(v33, link.P1)
    connect(v33a, link.P2)
    sensor = design.part("U1", device="Example:SENSOR_ANALOG")
    connect(v33a, sensor.vdda)
    connect(gnd, sensor.GND)
    sensor.unused_no_connect()
    for part, x, y in ((j1, 4, 10), (c1, 10, 14), (link, 14, 10), (sensor, 22, 10)):
        part.place(mm(x), mm(y), rot=90 if part is j1 else 0)
    return design
