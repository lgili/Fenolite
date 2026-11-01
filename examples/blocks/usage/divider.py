# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as an example (change c0270).
"""A complete divider design with a connector and an explicit bench voltage."""

import runpy
from pathlib import Path

from fenolite.dsl import Design, Part, connect, mm, supply, volt

divider = runpy.run_path(str(Path(__file__).resolve().parents[1] / "divider.py"))["divider"]
design = Design("divider_usage")
design.board(mm(40), mm(25))
j1 = Part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54")
design.add(j1)
dut = design.use(divider, "sense")
connect(dut.HI, j1[1])
connect(dut.OUT, j1[2])
connect(dut.LO, j1[3])
j1.place(mm(30), mm(10))
design.rig(supply(dut.HI, dut.LO, voltage=volt(12).pct(2), name="bench"))
