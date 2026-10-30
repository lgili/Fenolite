# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The sensor board of ``examples/circuit/sensor`` (change c0253; ``docs/contracts.md``).

A bench supply of 12 V ± 10 % (the test rig ``bench``, a record that reaches no output) feeds the input
connector ``J1`` and the rail ``V12``. The block ``buck`` makes ``3V3`` from it with an illustrative regulator
(``devices/`` beside the scripts; not a real product) and records one expectation: the divider sets ``VOUT``.
The header ``J2`` stands for the MCU and the sensor: it draws up to 1.2 A from ``3V3``. The design's derating
policy is its own: ``capacitor_voltage=ratio(50)``. Every value is chosen for the example; none comes from a
datasheet or a derating standard.

``bad=True`` swaps in a 16 V input capacitor (8 V under the policy, 13.2 V applied), a 1 A inductor on the
1.2 A rail, a reference of ± 1 % (the divider's range then overlaps its target without lying in it) and a
1 kΩ bleeder rated 0.1 W across ``V12`` (up to 0.176 W).
"""

from __future__ import annotations

from typing import Any

from fenolite.dsl import (
    Design,
    Ground,
    Rail,
    Symbol,
    amp,
    block,
    connect,
    farad,
    henry,
    mm,
    ohm,
    ratio,
    supply,
    value_of,
    volt,
    within,
)

VOUT = volt("3.3").pct(3)  # the regulator block's promise; chosen for the example
CURRENT = amp(2)  # what the block's output port gives; chosen for the example
SW_CURRENT = amp("1.5")  # the declared current of the switch node; chosen for the example


def buck_symbol() -> Symbol:
    """The symbol the example regulator names: six pins, numbered as its land."""
    made = Symbol("Example", "Buck_6pin", reference="U", value="EXB1820")
    for number, name, y in (("1", "BST", -2.54), ("2", "GND", 0), ("3", "FB", 2.54)):
        made.pin(number, name, at=(mm(-7.62), mm(y)), length=mm(2.54))
    for number, name, y in (("4", "EN", 2.54), ("5", "VIN", 0), ("6", "SW", -2.54)):
        made.pin(number, name, at=(mm(7.62), mm(y)), length=mm(2.54), rotation=180)
    made.rect((mm(-5.08), mm(-5.08)), (mm(5.08), mm(5.08)))
    return made


@block
def buck(b: Any, *, cap: str = "Example:CAP_50V", ind: str = "Example:IND_3A", vref: Any = None) -> None:
    """A 3.3 V step-down stage. Ports: VIN (in), VOUT (out, the promise), GND. It records that its divider
    sets VOUT within the promise, for every user of the block."""
    vin = b.port("VIN", Rail, direction="in")
    out = b.port("VOUT", Rail, direction="out", voltage=VOUT, current=CURRENT)
    gnd = b.port("GND", Ground)
    sw, bst, fb = b.net("SW"), b.net("BST"), b.net("FB")
    u = b.part("U", device="Example:BUCK_18V")
    c_in = b.part("C_in", device=cap, value=farad("10u"))
    c_bst = b.part("Cboot", device="Fenolite:C_0603", value=farad("100n"))
    inductor = b.part("L", device=ind, value=henry("4u7"))
    top = b.part("R_top", device="Example:RES_100MW", value=ohm("45k3").pct(1))
    bot = b.part("R_bot", device="Example:RES_100MW", value=ohm("10k").pct(1))
    c_out = b.part("C_out", device="Fenolite:C_0805", value=farad("22u"))
    connect(vin, u.VIN, u.EN, c_in.P1)
    connect(gnd, u.GND, c_in.P2, bot.P2, c_out.P2)
    connect(bst, u.BST, c_bst.P1)
    connect(sw, u.SW, c_bst.P2, inductor.P1)
    connect(out, inductor.P2, top.P1, c_out.P1)
    connect(fb, u.FB, top.P2, bot.P1)
    b.design.net_role(sw, "switch_node", current=SW_CURRENT)
    b.expect(within(vref * (1 + value_of(top) / value_of(bot)), VOUT), "VOUT set by the divider")
    for part, x, y in ((u, 17, 15), (c_in, 11, 15), (c_bst, 17, 9), (inductor, 23, 15), (top, 23, 21),
                       (bot, 17, 21), (c_out, 29, 15)):  # fmt: skip
        part.place(mm(x), mm(y), rot=90 if part is not u else 0)


def sensor_board(design: Design, *, bad: bool = False, rig: bool = True) -> Design:
    """The board in ``design``; ``bad`` makes the four designed failures, ``rig=False`` leaves out the test
    rig (the outputs are the same: the rig is a record of the rules layer)."""
    design.board(mm(50), mm(30))
    design.add(buck_symbol())
    gnd = design.ground("GND")
    v12 = design.rail("V12", ground=gnd)  # its voltage comes from the rig's bench supply
    v33 = design.rail("3V3", ground=gnd)  # its voltage comes from the source port buck1.VOUT

    j1 = design.part("J1", device="Fenolite:Conn_1x2_P2.54", value="12V IN")
    connect(v12, j1.P1)
    connect(gnd, j1.P2)
    vref = volt("0.6").pct(1 if bad else "0.5")  # the regulator's reference; chosen for the example
    power = design.use(
        buck,
        "buck1",
        cap="Example:CAP_16V" if bad else "Example:CAP_50V",
        ind="Example:IND_1A" if bad else "Example:IND_3A",
        vref=vref,
    )
    connect(v12, power.VIN)
    connect(v33, power.VOUT)
    connect(gnd, power.GND)
    load = design.part("J2", device="Example:LOAD_1A2", value="3V3 LOAD")
    connect(v33, load.supply)
    j1.place(mm(4), mm(15), rot=90, locked=True)
    load.place(mm(44), mm(15), rot=90)
    if bad:
        bleeder = design.part("R9", device="Example:RES_100MW", value=ohm("1k").pct(1))
        connect(v12, bleeder.P1)
        connect(gnd, bleeder.P2)
        bleeder.place(mm(8), mm(24), rot=90)

    design.derating(capacitor_voltage=ratio(50), source="the example's own policy")
    if rig:
        design.rig(supply(v12, gnd, voltage=volt("12").pct(10), current=amp(3), name="bench"))
    return design
