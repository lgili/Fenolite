# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Panel fixture: 2 × 4 copies of ``board.py`` held by tabs with mouse bites, rails on all four sides with
three fiducials and four tooling holes (change c0173). Authored for Fenolite. The panel checks find no
error: the planted track lies 0.3 mm from a routed edge, clear of the holes (0.25 mm, S-0799)."""

from fenolite.dsl import Panel, mm

panel = Panel("tabs", board="board_t10.kicad_pcb")
panel.grid(2, 4)
panel.rails(top=mm(5), bottom=mm(5), left=mm(5), right=mm(5))
for between in ("columns", "rows", "rails"):
    panel.separate("tabs", between=between)
panel.fiducials()
panel.tooling_holes()
