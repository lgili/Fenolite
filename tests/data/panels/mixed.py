# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Panel fixture: 2 × 2 copies of ``board.py``, scored between the rows and to the top and bottom rails,
tabbed between the columns (change c0173). Authored for Fenolite. The panel checks find no error: the
planted track faces the tabbed gap between the columns."""

from fenolite.dsl import Panel, mm

panel = Panel("mixed", board="board_t10.kicad_pcb")
panel.grid(2, 2)
panel.rails(top=mm(5), bottom=mm(5))
panel.separate("vscore", between="rows")
panel.separate("vscore", between="rails")
panel.separate("tabs", between="columns")
