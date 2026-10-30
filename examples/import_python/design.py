# SPDX-License-Identifier: CC0-1.0
# SPDX-FileCopyrightText: 2026 Fenolite contributors
# Converted from https://github.com/lgili/Fenolite@main by Fenolite 0.7.0.dev0 on 2026-10-30;
# modified: format conversion to the Fenolite DSL.
# Authored for Fenolite: imported from tests/data/import_python/two_sheet, authored for Fenolite.

import copper
from fenolite.dsl import Design, Module, Net, Part, connect, mm

design = Design("two_sheet")

design.board(mm("60"), mm("40"))

ch1_a = Net("CH1_A")
ch2_a = Net("CH2_A")
gnd = Net("GND")
vin = Net("VIN")

design.rules.netclass(
    "Power",
    clearance=mm("0.2"),
    track_width=mm("0.5"),
    via_diameter=mm("0.6"),
    via_drill=mm("0.3"),
    diff_pair_width=mm("0.2"),
    diff_pair_gap=mm("0.25"),
    diff_pair_via_gap=mm("0.25"),
    nets=(gnd, vin),
)

j1 = Part("J1", "Mini:Mini_LED_THT_3mm", footprint="Mini:Mini_LED_THT_3mm", value="CONN")
d101 = Part("D101", "Mini:Mini_LED_THT_3mm", footprint="Mini:Mini_LED_THT_3mm", value="LED")
r101 = Part("R101", "Mini:Mini_R_0603", footprint="Mini:Mini_R_0603", value="1k")
d201 = Part("D201", "Mini:Mini_LED_THT_3mm", footprint="Mini:Mini_LED_THT_3mm", value="LED", name="D101")
r201 = Part("R201", "Mini:Mini_R_0603", footprint="Mini:Mini_R_0603", value="1k", name="R101")

ch1 = Module("ch1")
ch2 = Module("ch2")

ch1.add(d101, r101)
ch2.add(d201, r201)
design.add(j1, ch1, ch2)

connect(ch1_a, d101["2"], r101["2"])
connect(ch2_a, d201["2"], r201["2"])
connect(gnd, d101["1"], d201["1"], j1["2"])
connect(vin, j1["1"], r101["1"], r201["1"])

j1.place(mm("2.54"), mm("10"), rot=90, locked=True)
d101.place(mm("28"), mm("15"))
r101.place(mm("20"), mm("15"))
d201.place(mm("28"), mm("25"), side="bottom")
r201.place(mm("20"), mm("25"), rot=180)

design.zone(
    gnd,
    layers=("B.Cu",),
    outline=((mm("35"), mm("12")), (mm("55"), mm("12")), (mm("55"), mm("28")), (mm("35"), mm("28"))),
)

design.rule_area(
    "ANT",
    ((mm("52"), mm("14")), (mm("58"), mm("14")), (mm("58"), mm("20")), (mm("52"), mm("20"))),
    forbid=("vias",),
)

design.line("F.SilkS/line/1", (mm("40"), mm("5")), (mm("50"), mm("5")), layer="F.SilkS", width=mm("0.15"))
design.text(
    "F.SilkS/text/1",
    "IMPORT",
    (mm("45"), mm("3")),
    layer="F.SilkS",
    size=mm("1"),
    thickness=mm("0.15"),
)

copper.apply(design, {"CH1_A": ch1_a, "CH2_A": ch2_a, "GND": gnd, "VIN": vin})
