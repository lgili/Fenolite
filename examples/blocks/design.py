# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Blocks (change c0251; ``docs/dsl.md``, "Blocks"): one circuit written once and used twice.

The block ``channel`` declares its ports ``VIN``, ``GND`` and the optional ``EN``, a local net ``FB``, two
parts named locally (``R_EN``, ``C_FB``) and a nested block ``indicator`` (a resistor and an LED). It is used
as ``ch0`` and ``ch1``: the parts get the paths ``ch0/R_EN`` and ``ch1/R_EN``, the local nets the names
``ch0/FB`` and ``ch1/FB``, and the board refs come from ``design.lock``, so no ref is typed by hand. The
parameters of each instance are recorded in the model; the values are plain text, which an Altium
comment can hold (Windows-1252 has no Ω). Every symbol and footprint comes from Fenolite's
own catalog, so the build reads no library.
"""

from fenolite.dsl import Design, Length, Net, Power, block, connect, mm

R_LED = "1k"  # the indicator's series resistor; chosen for the example
R_EN = "10k"  # the divider resistor; chosen for the example
X0 = mm(20)  # the column of the first channel; chosen for the example

design = Design("blocks_demo")
design.board(mm(60), mm(40))


@block
def indicator(b, *, x=X0, r_led=R_LED):
    """A resistor and an LED from VIN to GND. Ports: VIN, GND."""
    vin = b.port("VIN", direction="in")
    gnd = b.port("GND", direction="in")
    anode = b.net("A")
    r = b.part("R", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=r_led)
    # the LED land numbers pad 1 the cathode, while the symbol's pin 1 is the anode
    d = b.part(
        "D",
        "Fenolite:LED",
        footprint="Fenolite:LED0603_Kingbright_APT1608SURCK",
        value="green",
        pad_map={"1": "2", "2": "1"},
    )
    connect(vin, r[1])
    connect(anode, r[2], d["A"])
    connect(gnd, d["K"])
    r.place(x, mm(28))
    d.place(x + mm(5), mm(28))


@block
def channel(b, *, x=X0, r_en=R_EN):
    """A divider with a filter capacitor and an indicator. Ports: VIN, GND, EN (optional)."""
    vin = b.port("VIN", direction="in")
    gnd = b.port("GND", direction="in")
    en = b.port("EN", direction="out", optional=True)
    fb = b.net("FB")
    r = b.part("R_EN", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=r_en)
    c = b.part("C_FB", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="100n")
    connect(vin, r[1])
    connect(fb, r[2], c["A"], en)
    connect(gnd, c["B"])
    led = b.use(indicator, "led", x=x)
    connect(vin, led.VIN)
    connect(gnd, led.GND)
    r.place(x, mm(10))
    c.place(x, mm(18))


def at(n: int) -> Length:
    return X0 + mm(20) * n


j = design.part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="5V")
vin, gnd = Net("VIN"), Net("GND")
connect(vin, j[1])
connect(gnd, j[2])
design.add(Power(vin, gnd))

ch0 = design.use(channel, "ch0", x=at(0))
ch1 = design.use(channel, "ch1", x=at(1), r_en="22k")
connect(vin, ch0.VIN)
connect(gnd, ch0.GND)
connect(vin, ch1.VIN)
connect(gnd, ch1.GND)

j.place(mm(6), mm(20))
