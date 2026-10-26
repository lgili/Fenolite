# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
"""Authored signal chain for comparing legacy and block composition; no external libraries."""

from fenolite.dsl import Design, Net, Part, connect

design = Design("signal_chain")
input_connector = Part("J1", "Example.SchLib:INPUT", footprint="Example.PcbLib:HEADER", value="Input")
core = Part("U1", "Example.SchLib:CORE", footprint="Example.PcbLib:DEVICE", value="Signal core")
pullup = Part("R1", "Example.SchLib:RES", footprint="Example.PcbLib:RES", value="10k")
output_connector = Part("J2", "Example.SchLib:OUTPUT", footprint="Example.PcbLib:HEADER", value="Output")
design.add(input_connector, core, pullup, output_connector)
source, enable, result = Net("SOURCE"), Net("ENABLE"), Net("RESULT")
connect(source, input_connector[1], core[1])
connect(enable, core[2], pullup[1])
connect(result, core[3], output_connector[1], pullup[2])
