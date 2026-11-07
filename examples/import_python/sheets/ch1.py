# SPDX-License-Identifier: CC0-1.0
# SPDX-FileCopyrightText: 2026 Fenolite contributors
# Converted from https://github.com/lgili/Fenolite@main by Fenolite 0.8.0.dev0 on 2026-10-30;
# modified: format conversion to the Fenolite DSL.
# Authored for Fenolite: imported from tests/data/import_python/two_sheet, authored for Fenolite.

from fenolite.dsl import Module, Net, Part, connect, mm


def sheet(design, *, path, refs=None, **nets):
    module = Module(path.rsplit("/", 1)[-1])
    design.add(module)
    refs = refs or {}
    ch1_a = Net("CH1_A")
    gnd = nets["gnd"]
    vin = nets["vin"]
    d101 = Part(
        refs.get("D101", "D101"),
        "Mini:Mini_LED",
        footprint="Mini:Mini_LED_THT_3mm",
        value="LED",
        name="D101",
    )
    r101 = Part(
        refs.get("R101", "R101"),
        "Mini:Mini_R",
        footprint="Mini:Mini_R_0603",
        value="1k",
        name="R101",
    )
    module.add(d101, r101)
    connect(ch1_a, d101["2"], r101["2"])
    connect(gnd, d101["1"])
    connect(vin, r101["1"])
    d101.place(mm("28"), mm("15"))
    r101.place(mm("20"), mm("15"))
    return module
