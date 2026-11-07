# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The buck shunt reference board, good variant, with its power copper made from the net roles (change c0243;
``docs/roles.md``, "Role copper"): the variant without its power, switch-node, ground and high-voltage copper,
and ``design.role_copper()`` in their place."""

from buck_shunt_board import make

from fenolite.dsl import Design

design = make(Design("buck_shunt_good_roles"), "good", power=False)
design.net_role(design.nets["GND"], "ground")
design.role_copper()
