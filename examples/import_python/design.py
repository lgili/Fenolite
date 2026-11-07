# SPDX-License-Identifier: CC0-1.0
# SPDX-FileCopyrightText: 2026 Fenolite contributors
# Converted from https://github.com/lgili/Fenolite@main by Fenolite 0.7.0 on 2026-10-30;
# modified: format conversion to the Fenolite DSL.
# Authored for Fenolite: imported from tests/data/import_python/two_sheet, authored for Fenolite.

import copper
from sheets import ch1 as _sheet_ch1
from sheets import ch2 as _sheet_ch2
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("two_sheet")

design.board(mm("60"), mm("40"))

gnd = Net("GND")
vin = Net("VIN")

j1 = Part("J1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="CONN")

design.add(j1)
_sheet_ch1.sheet(design, path="ch1", refs={"D101": "D101", "R101": "R101"}, gnd=gnd, vin=vin)
_sheet_ch2.sheet(design, path="ch2", refs={"D101": "D201", "R101": "R201"}, gnd=gnd, vin=vin)

ch1_a = design.nets["CH1_A"]
ch2_a = design.nets["CH2_A"]

design.rules.netclass(
    "Default",
    clearance=mm("0.2"),
    track_width=mm("0.2"),
    via_diameter=mm("0.6"),
    via_drill=mm("0.3"),
    diff_pair_width=mm("0.2"),
    diff_pair_gap=mm("0.25"),
    diff_pair_via_gap=mm("0.25"),
    nets=(),
)
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

connect(gnd, j1["2"])
connect(vin, j1["1"])

j1.place(mm("2.54"), mm("10"), rot=90, locked=True)

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

design.load_schematic("schematic.toml")

design.kicad_project(
    "native/project.kicad_pro",
    sha256="c0c49764831dbbb9ab9a54a643153d4fb636b70e8113c56e328e1f431f78173f",
    preserve_minimums=True,
)
