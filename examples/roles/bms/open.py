# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The battery-management reference board, open variant (change c0244; ``docs/roles.md``, "Critical
routes"): the bad variant without its sense lines, the monitor's inputs on the sense nets, for ``fenolite
route --roles critical`` to draw; the narrow pack neck and the slot in the ground plane stay."""

from bms_board import make

from fenolite.dsl import Design

design = make(Design("bms_open"), "open")
