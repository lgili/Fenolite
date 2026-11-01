# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Rails with parameters, the good variant (change c0252): ``rails/board.py`` describes the board; every
rail, logic level and pull-up of it passes the stage ``circuit.rules``.

Build it with ``fenolite build examples/sensor_rails/good.py --out build/sensor_rails --confirm``.
"""

from rails.board import sensor_board

from fenolite.dsl import Design

design = sensor_board(Design("sensor_rails"))
