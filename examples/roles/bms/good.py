# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The battery-management reference board, good variant (change c0222; ``docs/roles.md``, "Reference
boards")."""

from bms_board import make

from fenolite.dsl import Design

design = make(Design("bms_good"), "good")
