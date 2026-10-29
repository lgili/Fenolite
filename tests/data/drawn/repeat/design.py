# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as a test fixture; no file, value, name or layout comes from any other project.
"""Drawn fixture ``repeat`` (change c0276): two channels ``ch0`` and ``ch1`` shown by one drawn sheet
``channel``. Each channel joins R1 and R2 through the local label ``FB``, which stays on its instance; the
power symbol ``GND`` joins both channels."""

from fenolite.dsl import Design, Module, Net, connect, mm

design = Design("drawn_repeat")
design.board(mm(40), mm(30))
gnd = Net("GND")
for index in range(2):
    channel = Module(f"ch{index}")
    design.add(channel)
    r1 = channel.part(name="R1", prefix="R", lib_id="Mini:Mini_R", footprint="Mini:Mini_R_0603", value="10k")
    r2 = channel.part(name="R2", prefix="R", lib_id="Mini:Mini_R", footprint="Mini:Mini_R_0603", value="10k")
    connect(gnd, r1[1])
    connect(Net(f"FB{index}"), r1[2], r2[1])
design.load_schematic("schematic.toml")
