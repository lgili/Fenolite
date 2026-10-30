# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Exact part numbers from ordering-code grammars (change c0263; ``docs/picking.md``, "Families with
ordering codes").

The illustrative grammar families in ``devices/`` describe whole series of an invented manufacturer,
``Example Passive``, by their ordering codes: ``example_mlcc.toml`` (capacitors, value in ``eia3``),
``example_chip_r.toml`` (resistors, ``eia4``, an opaque tail) and ``example_film_r.toml`` (resistors,
``rkm``). The queries below are the ones of change c0254; the build expands each grammar under its query,
picks an exact MPN with its manufacturer and records it in the design lock beside this script.
"""

from fenolite.dsl import Design, Net, capacitor, connect, farad, mm, ohm, pct, resistor, volt

design = Design("families_demo")
design.board(mm(30), mm(20))

vin, out, gnd = Net("VIN"), Net("OUT"), Net("GND")
c_in = design.part(
    name="C_in", device=capacitor(farad("100n"), rating=volt(25), case="0603", dielectric="X7R")
)
connect(vin, c_in[1])
connect(gnd, c_in[2])
r_top = design.part(name="R_top", device=resistor(ohm("10k"), tolerance=pct(1), case="0603"))
connect(vin, r_top[1])
connect(out, r_top[2])
r_led = design.part(name="R_led", device=resistor(ohm("4.7k"), tolerance=pct(5), case="1206"))
connect(out, r_led[1])
connect(gnd, r_led[2])
j1 = design.part("J1", device="Fenolite:Conn_1x2_P2.54", value="VIN")
connect(vin, j1.P1)
connect(gnd, j1.P2)
