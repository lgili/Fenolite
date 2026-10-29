# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The half bridge reference board, good variant, with its power copper made from the net roles (change c0243;
``docs/roles.md``, "Role copper"): the variant without its power, switch-node, ground and high-voltage copper,
and ``design.role_copper()`` in their place."""

from half_bridge_board import make

from fenolite.dsl import Design, amp

design = make(Design("half_bridge_good_roles"), "good", power=False)
design.net_role(design.nets["GND"], "ground")
design.net_role(design.nets["SRC"], "power", current=amp(5))
design.net_role(design.nets["SW"], "switch_node", current=amp(5))
design.role_limits(net=design.nets["GND"], milliamps_per_via=amp(4))
design.role_copper(requirements="requirements.toml")
