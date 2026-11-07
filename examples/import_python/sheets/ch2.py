# SPDX-License-Identifier: CC0-1.0
# SPDX-FileCopyrightText: 2026 Fenolite contributors
# Converted from https://github.com/lgili/Fenolite@main by Fenolite 0.7.0 on 2026-10-30;
# modified: format conversion to the Fenolite DSL.
# Authored for Fenolite: imported from tests/data/import_python/two_sheet, authored for Fenolite.

from fenolite.dsl import Module, Net, Part, connect, mm


def sheet(design, *, path, refs=None, **nets):
    module = Module(path.rsplit("/", 1)[-1])
    design.add(module)
    refs = refs or {}
    ch2_a = Net("CH2_A")
    gnd = nets["gnd"]
    vin = nets["vin"]
    d201 = Part(
        refs.get("D101", "D201"),
        "Mini:Mini_LED",
        footprint="Mini:Mini_LED_THT_3mm",
        value="LED",
        name="D101",
    )
    r201 = Part(
        refs.get("R101", "R201"),
        "Mini:Mini_R",
        footprint="Mini:Mini_R_0603",
        value="1k",
        name="R101",
    )
    module.add(d201, r201)
    connect(ch2_a, d201["2"], r201["2"])
    connect(gnd, d201["1"])
    connect(vin, r201["1"])
    d201.place(mm("28"), mm("25"), side="bottom")
    r201.place(mm("20"), mm("25"), rot=180)
    return module
