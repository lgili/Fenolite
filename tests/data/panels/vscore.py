# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Panel fixture: 2 × 2 copies of ``board.py`` scored both ways, with scored rails on the top and the
bottom (change c0173). Authored for Fenolite. The planted track lies 0.3 mm from each copy's right edge, so
the copies of the left column face the score line between the columns with copper nearer than 0.45 mm:
two ``panel.vscore-copper`` errors."""

from fenolite.dsl import Panel, mm

panel = Panel("vscore", board="board_t10.kicad_pcb")
panel.grid(2, 2)
panel.rails(top=mm(5), bottom=mm(5))
for between in ("columns", "rows", "rails"):
    panel.separate("vscore", between=between)
