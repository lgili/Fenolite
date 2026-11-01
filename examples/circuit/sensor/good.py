# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Electrical contracts, the good variant (change c0253): ``contract_board/board.py`` describes the board;
every rating, operating range and expectation of it passes the stage ``circuit.rules``
(``docs/contracts.md``).

Build it with ``fenolite build examples/circuit/sensor/good.py --out examples/circuit/sensor/build
--confirm``: ``fenolite check examples/circuit/sensor/build`` then finds the records in ``devices/`` of the
build folder's parent.
"""

from contract_board.board import sensor_board

from fenolite.dsl import Design

design = sensor_board(Design("sensor_contracts"))
