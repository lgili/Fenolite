# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as test data of fenolite import (change c0275); no file, value, name or layout comes
# from any other project.
"""Two channels of a resistor and an LED, each a module (a sheet of the built schematic), a connector, the
net class ``Power``, a ``GND`` zone, a keep-out, a silkscreen note and 40 track segments, 3 arcs and 6 vias
on two nets. ``tests/unit/importer/test_data.py`` keeps ``two_sheet/`` equal to a fresh build of it."""

from fenolite.dsl import Design, Module, Net, Part, connect, mm

design = Design("two_sheet")
design.board(mm(60), mm(40))
gnd, vin = Net("GND"), Net("VIN")
design.rules.netclass("Power", clearance=mm("0.2"), track_width=mm("0.5"), nets=(gnd, vin))


def channel(name: str, number: int) -> tuple[Part, Part]:
    module = Module(name)
    resistor = Part(f"R{number}", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k", name="R101")
    led = Part(f"D{number}", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED", name="D101")
    module.add(resistor, led)
    connect(vin, resistor[1])
    connect(Net(f"{name.upper()}_A"), resistor[2], led[2])
    connect(gnd, led[1])
    design.add(module)
    return resistor, led


r1, d1 = channel("ch1", 101)
r2, d2 = channel("ch2", 201)
j1 = Part("J1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="CONN")
design.add(j1)
connect(vin, j1[1])
connect(gnd, j1[2])

j1.place(mm("2.54"), mm(10), rot=90, locked=True)
r1.place(mm(20), mm(15))
d1.place(mm(28), mm(15))
r2.place(mm(20), mm(25), rot=180)
d2.place(mm(28), mm(25), side="bottom")

design.zone(
    gnd, layers=("B.Cu",), outline=[(mm(35), mm(12)), (mm(55), mm(12)), (mm(55), mm(28)), (mm(35), mm(28))]
)
design.rule_area(
    "ANT", [(mm(52), mm(14)), (mm(58), mm(14)), (mm(58), mm(20)), (mm(52), mm(20))], forbid=("vias",)
)
design.text("note", "IMPORT", (mm(45), mm(3)), layer="F.SilkS")
design.line("bar", (mm(40), mm(5)), (mm(50), mm(5)), layer="F.SilkS", width=mm("0.15"))

# 20 segments of VIN on F.Cu along the top edge and 20 of GND on B.Cu along the bottom edge, in zigzags
vin_rows = tuple(
    (10_000_000 + 2_000_000 * i, 6_000_000 + 1_000_000 * (i % 2), 12_000_000 + 2_000_000 * i,
     6_000_000 + 1_000_000 * ((i + 1) % 2))
    for i in range(20)
)  # fmt: skip
gnd_rows = tuple(
    (10_000_000 + 2_000_000 * i, 33_000_000 + 1_000_000 * (i % 2), 12_000_000 + 2_000_000 * i,
     33_000_000 + 1_000_000 * ((i + 1) % 2))
    for i in range(20)
)  # fmt: skip
design.track_table("vin", net=vin, layer="F.Cu", width=mm("0.5"), rows_nm=vin_rows)
design.track_table("gnd", net=gnd, layer="B.Cu", width=mm("0.5"), rows_nm=gnd_rows, locked=True)
design.arc_table(
    "gnd_arcs",
    net=gnd,
    layer="B.Cu",
    width=mm("0.3"),
    rows_nm=(
        (5_000_000, 30_000_000, 6_000_000, 31_000_000, 7_000_000, 30_000_000),
        (7_000_000, 30_000_000, 8_000_000, 29_000_000, 9_000_000, 30_000_000),
        (9_000_000, 30_000_000, 10_000_000, 31_000_000, 11_000_000, 30_000_000),
    ),
)
design.via_table(
    "vin_vias", net=vin, diameter=mm("0.6"), drill=mm("0.3"),
    rows_nm=((10_000_000, 6_000_000), (30_000_000, 6_000_000), (50_000_000, 6_000_000)),
)  # fmt: skip
design.via_table(
    "gnd_vias", net=gnd, diameter=mm("0.8"), drill=mm("0.4"),
    rows_nm=((10_000_000, 33_000_000), (30_000_000, 33_000_000), (50_000_000, 33_000_000)),
)  # fmt: skip
