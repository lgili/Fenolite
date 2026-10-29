# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The half-bridge reference board, bad variant (change c0222; ``docs/roles.md``, "Reference boards")."""

from half_bridge_board import make

from fenolite.dsl import Design

design = make(Design("half_bridge_bad"), "bad")
