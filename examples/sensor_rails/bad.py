# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Rails with parameters, the bad variant (change c0252): a fan of up to 1.1 A overloads the 1 A source
``buck/VOUT`` of ``3V3`` (``circuit.rail-current``, which stops the build), and the bus is pulled up to
``V12`` instead of its reference rail ``3V3`` (``circuit.bus-pullup``, and ``circuit.logic-level`` for the
12 V that the bus ports do not withstand)."""

from rails.board import sensor_board

from fenolite.dsl import Design

design = sensor_board(Design("sensor_rails_bad"), bad=True)
