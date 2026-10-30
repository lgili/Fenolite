# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The buck reference board, open variant (change c0244; ``docs/roles.md``, "Critical routes"): the bad
variant without its two sense lines, for ``fenolite route --roles critical`` to draw; the hot loop and the
0.3 mm output track stay."""

from buck_shunt_board import make

from fenolite.dsl import Design

design = make(Design("buck_shunt_open"), "open")
