# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The half-bridge reference board, open variant (change c0244; ``docs/roles.md``, "Critical routes"): the
bad variant without its gate faults and its sense pair, for ``fenolite route --roles critical`` to draw;
the bus via and the switch-node pour on ``In1.Cu`` stay."""

from half_bridge_board import make

from fenolite.dsl import Design

design = make(Design("half_bridge_open"), "open")
