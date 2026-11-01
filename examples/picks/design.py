# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Parts chosen by parameters (change c0254; ``docs/picking.md``).

A small sensor front end whose passives are written by what they must be: the input capacitor ``C_in`` by
value, rating and dielectric (picked from the illustrative project family in ``devices/caps.toml``), a
feedback divider in the block ``buck1``, an RC filter, an LED resistor and the pull-ups of an I2C bus. The
build picks every part from the local catalog (the shipped ``Fenolite:`` families and ``devices/``), writes
each pick to ``design.lock`` beside this script through the plan, and reports what each generator achieved.
"""

from fenolite.dsl import (
    I2C,
    Design,
    Net,
    amp,
    between,
    block,
    capacitor,
    connect,
    farad,
    hertz,
    i2c_pull_ups,
    led_resistor,
    mm,
    pct,
    rc_lowpass,
    volt,
    voltage_divider,
)

design = Design("picks_demo")
design.board(mm(40), mm(30))
design.defaults(resistor={"case": "0603", "tolerance": pct(1)}, capacitor={"dielectric": "X7R"})

vin, v33, gnd = Net("VIN"), Net("V3V3"), Net("GND")
c_in = design.part(name="C_in", device=capacitor(farad("10u"), rating=volt(25), case="0805"))
connect(vin, c_in[1])  # the pins of a query part are 1 and 2 before the pick
connect(gnd, c_in[2])


VOUT = volt("3.3").pct(5)
"""The regulated output and its tolerance: the target of the divider."""


@block
def buck(b, *, vout=VOUT):
    b.defaults(resistor={"series": "E96"})  # block level: between the design's defaults and the call
    out, ground, fb = b.port("VOUT"), b.port("GND"), b.net("FB")
    voltage_divider(
        b, out, fb, ground, target=vout, ref=volt("0.6").pct(1), current=between(amp("40u"), amp("100u"))
    )


regulator = design.use(buck, "buck1")
connect(v33, regulator.VOUT)
connect(gnd, regulator.GND)

sense, filtered = Net("SENSE"), Net("SENSE_F")
rc_lowpass(
    design, sense, filtered, gnd, corner=hertz(1000).pct(10), c=capacitor(farad("10n"), dielectric="C0G")
)

anode = Net("LED_A")
led_resistor(
    design,
    v33,
    anode,
    current=between(amp("2m"), amp("5m")),
    vf=between(volt("1.8"), volt("2.2")),
    vs=volt("3.3").pct(3),
)
d1 = design.part("D1", device="Fenolite:LED_0603")
connect(anode, d1.A)
connect(gnd, d1.K)

bus = I2C(Net("SDA"), Net("SCL"))
i2c_pull_ups(design, bus, v33, bus_capacitance=between(farad("50p"), farad("100p")), vdd=volt("3.3").pct(3))

j1 = design.part("J1", "Fenolite:Connector_4", footprint="Fenolite:Header_1x4_P2.54", value="IO")
connect(sense, j1[1])
connect(filtered, j1[2])
connect(bus.members["sda"], j1[3])
connect(bus.members["scl"], j1[4])
j2 = design.part("J2", device="Fenolite:Conn_1x2_P2.54", value="VIN")
connect(vin, j2.P1)
connect(gnd, j2.P2)
