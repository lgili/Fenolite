# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""An LED bar of forty parts: two mini MCUs, each driving nine LEDs through nine resistors, on a
100 mm x 80 mm two-layer board with a ``GND`` zone on both layers.

Build it with ``fenolite build examples/board_40parts/design.py --out build/bar --confirm``. The two
controllers are placed and locked by the script; every other part is left off the board for
``fenolite place --strategy grid``. The board minimums are the script's own, so KiCad's DRC judges the
finished board against them. The libraries come from the authored CC0 mini library
(``tests/data/libs``) through this folder's ``fp-lib-table`` and ``sym-lib-table``.
"""

from fenolite.dsl import Design, Module, Net, Part, Power, connect, mm, no_connect

LEDS_PER_BANK = 9
# The controller pins that drive the LEDs; 9 is the supply and 10 the ground, 17 the enable input.
DRIVE_PINS = (1, 2, 3, 4, 5, 6, 7, 8, 12)
SUPPLY_PIN, GROUND_PIN, ENABLE_PIN = 9, 10, 17
USED_PINS = {*DRIVE_PINS, SUPPLY_PIN, GROUND_PIN, ENABLE_PIN}
PIN_COUNT = 32

design = Design("board_40parts")
design.board(mm(100), mm(80))

vin, gnd = Net("VIN"), Net("GND")


def bank(index: int) -> Part:
    """One module: a controller, nine LEDs with their series resistors and the enable pull-up."""
    module = Module(f"bank{index}")
    first = (index - 1) * LEDS_PER_BANK
    controller = Part(f"U{index}", "Mini:Mini_QFP32_IC", value="MCU")
    pull_up = Part(f"R{2 * LEDS_PER_BANK + index}", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="10k")
    module.add(controller, pull_up)
    connect(vin, controller[SUPPLY_PIN], pull_up[1])
    connect(gnd, controller[GROUND_PIN])
    connect(Net(f"EN{index}"), controller[ENABLE_PIN], pull_up[2])
    no_connect(*(controller[pin] for pin in range(1, PIN_COUNT + 1) if pin not in USED_PINS))
    for offset, pin in enumerate(DRIVE_PINS, start=1):
        number = first + offset
        resistor = Part(f"R{number}", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")
        led = Part(f"D{number}", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")
        module.add(resistor, led)
        connect(Net(f"DRV{number}"), controller[pin], resistor[1])
        connect(Net(f"LED{number}"), resistor[2], led[2])
        connect(gnd, led[1])
    design.add(module)
    return controller


u1, u2 = bank(1), bank(2)
design.add(Power(vin, gnd))

design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))
design.rules.minimum(
    clearance=mm(0.15), track_width=mm(0.15), via_diameter=mm(0.45), via_drill=mm(0.2),
    hole_size=mm(0.3), edge_clearance=mm(0.3),
)  # fmt: skip
design.rules.minimum(clearance=mm(0.2), track_width=mm(0.4), netclass="PWR")
design.zone(gnd, layers=("F.Cu", "B.Cu"), connection="solid")

u1.place(mm(30), mm(40), locked=True)
u2.place(mm(70), mm(40), locked=True)

# One via under each controller ties the copper that the pad ring encloses on the top layer to the
# bottom layer; without it that island can hang on the controller's ground pin alone.
design.via("gnd_u1", mm(30), mm(40), net=gnd, diameter=mm(0.6), drill=mm(0.3))
design.via("gnd_u2", mm(70), mm(40), net=gnd, diameter=mm(0.6), drill=mm(0.3))
