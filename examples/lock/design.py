# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The design lock (change c0249; ``docs/dsl.md``, "Reference designators and the design lock").

A 3.3 V regulator and an indicator LED in two modules. Most parts are written without a ref: their path is
their module path and their reference prefix (``reg/U``, ``led/R``), or their ``name=`` (``reg/c_in``),
and the build gives them refs, per prefix in natural path order with the lowest free number. The connector
keeps its explicit ref ``J1``. The refs are recorded in ``design.lock`` beside this script, which
``fenolite build`` writes through the plan and which a release build checks with ``--frozen``. Every symbol
and footprint comes from Fenolite's own catalog, so the build reads no library.
"""

from fenolite.dsl import Design, Module, Net, connect, mm

design = Design("lock_demo")
design.board(mm(40), mm(30))

j = design.part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="5V")

reg = Module("reg")
design.add(reg)
u = reg.part(lib_id="Fenolite:Linear_Regulator", footprint="Fenolite:SOT223_3_Diodes", value="3V3")
c_in = reg.part(name="c_in", lib_id="Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="10u")
c_out = reg.part(lib_id="Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="22u")

led = Module("led")
design.add(led)
r = led.part(lib_id="Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
# The LED land numbers its pads as the manufacturer does, pad 1 the cathode, while the symbol's pin 1 is the
# anode: the map puts the anode (pin 1) on pad 2 and the cathode (pin 2) on pad 1.
d = led.part(
    lib_id="Fenolite:LED",
    footprint="Fenolite:LED0603_Kingbright_APT1608SURCK",
    value="green",
    pad_map={"1": "2", "2": "1"},
)

vin, v3, gnd, led_a = Net("VIN"), Net("+3V3"), Net("GND"), Net("LED_A")
connect(vin, j[1], u["IN"], c_in["A"])
connect(gnd, j[2], u["GND"], c_in["B"], c_out["B"], d["K"])
connect(v3, u["OUT"], c_out["A"], r[1])
connect(led_a, r[2], d["A"])

j.place(mm(5), mm(15))
u.place(mm(16), mm(15))
c_in.place(mm(12), mm(22))
c_out.place(mm(22), mm(22))
r.place(mm(30), mm(10))
d.place(mm(35), mm(15))
