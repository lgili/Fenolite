# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""An analog rail behind a resistor, the bad variant (change c0274): nothing crosses the 10 Ω resistor ``R1``,
so ``3V3A`` has no voltage and ``circuit.rail-unset`` names it."""

from ferrite_board.board import analog_board

from fenolite.dsl import Design

design = analog_board(Design("ferrite_bad"), resistor=True)
