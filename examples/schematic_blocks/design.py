# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
"""The exact circuit of grid.py, with explicit functional blocks and presentation-only intent."""

import runpy
from pathlib import Path

namespace = runpy.run_path(str(Path(__file__).with_name("grid.py")))
design = namespace["design"]
design.schematic_layout(mode="blocks", flow="left-to-right")
design.schematic_block("input", members=[namespace["input_connector"]], title="Input")
design.schematic_block(
    "core",
    members=[namespace["core"], namespace["pullup"]],
    title="Signal core",
    anchor=namespace["core"],
    after="input",
)
design.schematic_block("output", members=[namespace["output_connector"]], title="Output", after="core")
