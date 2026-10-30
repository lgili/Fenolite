# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The bench of the block ``channel`` of ``../blocks.py`` (change c0255, block layout reuse): one instance on
a small board, which ``fenolite build`` turned into ``../channel.kicad_pcb``.

Its footprints carry the paths ``ch/C``, ``ch/R`` and ``ch/D``, and its nets are named by the block's ports
(``VIN``, ``GND``) and local net (``ch/A``), which is what a reuse maps: parts by their block-local path and
nets by port. The two tracks of the reference board, ``VIN`` from ``C`` to ``R`` and ``A`` from ``R`` to
``D``, were drawn on that board for Fenolite as the block's proven routing.
"""

from fenolite.dsl import Design, Net, Power, block, connect, mm, row

design = Design("channel_bench")
design.board(mm(16), mm(8))


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


vin, gnd = Net("VIN"), Net("GND")
ch = design.use(channel, "ch")
connect(vin, ch.VIN)
connect(gnd, ch.GND)
design.add(Power(vin, gnd))
ch.place(mm(2), mm(3))
