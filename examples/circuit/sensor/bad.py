# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Electrical contracts, the bad variant (change c0253): a 16 V input capacitor limited to 8 V by the
design's policy on a 13.2 V bench (``circuit.rating-voltage``), a 1 A inductor on a rail whose loads reach
1.2 A (``circuit.rating-current``), a divider whose range overlaps its target without lying in it
(``circuit.expect-unsure``) and a 0.1 W bleeder that dissipates up to 0.176 W (``circuit.rating-power``)."""

from contract_board.board import sensor_board

from fenolite.dsl import Design

design = sensor_board(Design("sensor_contracts_bad"), bad=True)
