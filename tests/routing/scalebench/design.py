# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scale bench of change c0109, task 1.2: a board of one hundred parts for measuring the external
routers again (``docs/evidence/routing.md``, "Scale (c0109)").

Authored for Fenolite under that task on 2026-10-09: the circuit, the net names, the sizes and the layout
are round values chosen here and come from no existing board. Every part is from the built-in catalog, so
the bench needs no KiCad library. Build it with
``fenolite build tests/routing/scalebench/design.py --out <folder> --confirm``.

- A 76 mm by 92 mm board of four copper layers; ``GND`` is the plane of ``In1.Cu`` and ``VCC`` that of
  ``In2.Cu``, each with a zone over the board (class ``PWR``: 0.4 mm track, 0.2 mm clearance).
- Six cells of 38 mm by 28 mm, each: a controller (``SOIC_8``, ``VCC`` on pin 8 and ``GND`` on pin 4), two
  decoupling capacitors, a pull-up of pin 1, and six channels: the pin's net ``U<i>_P<k>``, a series
  resistor, the net ``CH<i>_<k>`` and a filter capacitor to ``GND`` (class ``SIG``: 0.2 mm track, 0.15 mm
  clearance).
- Four headers along the lower edge: the first two channels of each controller leave on ``J1`` to ``J3``,
  and ``J4`` carries ``VCC`` and ``GND``.

Six controllers, 12 decoupling and 36 filter capacitors, 42 resistors and 4 headers: 100 parts; 74 nets.
"""

from fenolite.dsl import Design, Net, Part, connect, mm

CELLS = 6
CHANNEL_PINS = (1, 2, 3, 5, 6, 7)
CELL_WIDTH, CELL_HEIGHT = 38, 28

design = Design("scalebench")
gnd, vcc = Net("GND"), Net("VCC")
design.board(mm(76), mm(92), copper=4, planes={"In1.Cu": gnd, "In2.Cu": vcc})

signals: list[Net] = []
outputs: list[Net] = []
resistor = capacitor = 0


def chip(prefix: str, symbol: str, value: str, x: float, y: float) -> Part:
    """One 0603 part, numbered in order, placed at ``x``, ``y`` millimetres."""
    global resistor, capacitor
    if prefix == "R":
        resistor += 1
        ref = f"R{resistor}"
    else:
        capacitor += 1
        ref = f"C{capacitor}"
    part = Part(ref, symbol, footprint="Fenolite:Chip_0603", value=value)
    design.add(part)
    part.place(mm(x), mm(y))
    return part


for cell in range(CELLS):
    index = cell + 1
    left, top = (cell % 2) * CELL_WIDTH, 2 + (cell // 2) * CELL_HEIGHT
    controller = Part(f"U{index}", "Fenolite:Microcontroller", footprint="Fenolite:SOIC_8", value="MCU")
    design.add(controller)
    controller.place(mm(left + 10), mm(top + 13))
    connect(vcc, controller[8])
    connect(gnd, controller[4])
    for y in (top + 5, top + 21):
        decoupling = chip("C", "Fenolite:Capacitor", "100n", left + 4, y)
        connect(vcc, decoupling[1])
        connect(gnd, decoupling[2])
    for channel, pin in enumerate(CHANNEL_PINS):
        y = top + 3 + channel * 4
        near, far = Net(f"U{index}_P{pin}"), Net(f"CH{index}_{channel + 1}")
        series = chip("R", "Fenolite:Resistor", "33", left + 21, y)
        filter_cap = chip("C", "Fenolite:Capacitor", "1n", left + 30, y)
        connect(near, controller[pin], series[1])
        connect(far, series[2], filter_cap[1])
        connect(gnd, filter_cap[2])
        signals += [near, far]
        if channel < 2:
            outputs.append(far)
    pull_up = chip("R", "Fenolite:Resistor", "10k", left + 10, top + 23)
    connect(vcc, pull_up[1])
    connect(signals[-12], pull_up[2])  # the net of pin 1, the first channel's

for number in range(1, 5):
    header = Part(f"J{number}", "Fenolite:Connector_4", footprint="Fenolite:Header_1x4_P2.5", value="IO")
    design.add(header)
    header.place(mm(10 + (number - 1) * 18.5), mm(88), rot=90)
    if number < 4:
        for pin in range(1, 5):
            connect(outputs[(number - 1) * 4 + pin - 1], header[pin])
    else:
        connect(vcc, header[1], header[2])
        connect(gnd, header[3], header[4])

design.rules.netclass(
    "PWR", clearance=mm(0.2), track_width=mm(0.4), via_diameter=mm(0.6), via_drill=mm(0.3), nets=(gnd, vcc)
)
design.rules.netclass(
    "SIG", clearance=mm(0.15), track_width=mm(0.2), via_diameter=mm(0.6), via_drill=mm(0.3), nets=signals
)
design.zone(gnd, layers=("In1.Cu",))
design.zone(vcc, layers=("In2.Cu",))
