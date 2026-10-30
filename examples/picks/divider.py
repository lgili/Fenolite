# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""A feedback divider chosen by ``voltage_divider`` (change c0254; ``docs/picking.md``).

A regulator block ``buck1`` whose output must stay within 3.3 V ± 5 % with a 0.6 V ± 1 % reference: the
build searches the shipped E96 1 % 0603 family for the pair whose worst case lies within the target, writes
both picks to ``divider.lock`` and reports ``gen.achieved``: 61.9 kΩ over 13.7 kΩ, VOUT 3.224694–3.399373 V.
"""

from fenolite.dsl import Design, Net, amp, between, block, connect, mm, pct, volt, voltage_divider

design = Design("divider_demo")
design.board(mm(20), mm(15))
design.defaults(resistor={"case": "0603", "tolerance": pct(1)})


VOUT = volt("3.3").pct(5)
"""The regulated output and its tolerance: the target of the divider."""


@block
def buck(b, *, vout=VOUT):
    b.defaults(resistor={"series": "E96"})
    out, ground, fb = b.port("VOUT"), b.port("GND"), b.net("FB")
    voltage_divider(
        b, out, fb, ground, target=vout, ref=volt("0.6").pct(1), current=between(amp("40u"), amp("100u"))
    )


v33, gnd = Net("V3V3"), Net("GND")
regulator = design.use(buck, "buck1")
connect(v33, regulator.VOUT)
connect(gnd, regulator.GND)
j1 = design.part("J1", device="Fenolite:Conn_1x2_P2.54", value="OUT")
connect(v33, j1.P1)
connect(gnd, j1.P2)
