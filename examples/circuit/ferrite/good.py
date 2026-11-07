# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""An analog rail behind a ferrite, the good variant (change c0274): ``3V3A`` takes 3.201 V to 3.399 V from
``3V3`` through ``FB1`` (origin ``propagated via FB1 from 3V3``), and the sensor's ``vdda`` passes."""

from ferrite_board.board import analog_board

from fenolite.dsl import Design

design = analog_board(Design("ferrite_good"))
