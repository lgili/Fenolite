# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The buck reference board, bad variant (change c0222; ``docs/roles.md``, "Reference boards"): its designed
faults are a hot loop of about 180 mm², a sense line from the outer end of the shunt's pad and one from the
output pour, and a 0.3 mm track on the 2 A output path."""

from buck_shunt_board import make

design = make("bad")
