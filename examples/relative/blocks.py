# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Block layout (change c0255; ``docs/dsl.md``, "Block layout"): a block arranged by a strategy, moved as one
piece, and a block placed, with its copper, from a board laid out for it alone.

The block ``channel`` (a capacitor, a resistor and an LED) arranges its parts in a row, in its own frame.
``ch0`` is posed with coordinates and ``ch1`` below it, starting at the same left edge: each moves as one
rigid group. ``ch2`` takes its layout and its two tracks from ``channel.kicad_pcb`` (built from
``bench/channel.py``): its parts are mapped by their block-local paths and its nets by port, so the
``VIN`` track lands on ``V12``, the net joined to ``ch2``'s ``VIN``. The connector holds the board's left
edge. Every symbol and footprint comes from Fenolite's own catalog.
"""

from fenolite.dsl import Design, Net, Power, block, connect, mm, row

design = Design("relative_blocks")
board = design.board(mm(50), mm(30))


@block
def channel(b):
    """A filtered indicator: a capacitor, a resistor and an LED in a row. Ports: VIN, GND."""
    vin = b.port("VIN", direction="in")
    gnd = b.port("GND", direction="in")
    a = b.net("A")
    c = b.part("C", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="100n")
    r = b.part("R", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
    d = b.part(
        "D",
        "Fenolite:LED",
        footprint="Fenolite:LED0603_Kingbright_APT1608SURCK",
        value="green",
        pad_map={"1": "2", "2": "1"},
    )
    connect(vin, c["A"], r[1])
    connect(a, r[2], d["A"])
    connect(gnd, c["B"], d["K"])
    b.layout(row(gap=mm("1.5"), align="center"))


j1 = design.part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54", value="PWR")
vin, v12, gnd = Net("VIN"), Net("V12"), Net("GND")
connect(vin, j1[1])
connect(v12, j1[2])
connect(gnd, j1[3])
design.add(Power(vin, gnd))

ch0 = design.use(channel, "ch0")
ch1 = design.use(channel, "ch1")
ch2 = design.use(channel, "ch2")
for inst, supply in ((ch0, vin), (ch1, vin), (ch2, v12)):
    connect(supply, inst.VIN)
    connect(gnd, inst.GND)

j1.place(left=board.left + mm(2), center_y=board.center_y)
ch0.place(mm(12), mm(6))
ch1.place(below=ch0, gap=mm(3), align="start")
ch2.layout(reuse="channel.kicad_pcb", copper=True)
ch2.place(right_of=ch0, gap=mm(6), align="start")
