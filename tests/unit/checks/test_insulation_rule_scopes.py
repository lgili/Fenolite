# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the guide page ``board-insulation`` says about scoping an exception inside one part (change c0403,
F3 and F4), on an authored design: a part-wide pad rule is a minimum for every pad pair of the part, a rule
per pair of domains reaches only those domains, and a no-connect pin's net is in ``Default``."""

from __future__ import annotations

from fenolite.checks.clearance import ClearanceResolver
from fenolite.dsl import Design, Net, mm, select, to_model
from fenolite.model.rules import RuleSubject


def resolver(*, part_wide: bool) -> ClearanceResolver:
    script = Design("one-part-two-domains")
    bus, phase, a, b = Net("BUS"), Net("PHASE"), Net("LOGIC_A"), Net("LOGIC_B")
    for net in (bus, phase, a, b):
        script.add(net)
    script.rules.netclass("POWER", clearance=mm(3), nets=(bus, phase))
    script.rules.netclass("CTRL", clearance=mm(0.2), nets=(a, b))
    script.rules.rule(
        "power_ctrl", "clearance", where=select.netclass("POWER"), between=select.netclass("CTRL"), min=mm(3)
    )
    if part_wide:
        pads = select.ref("U8") & select.item("pad")
        script.rules.rule("u8_pads", "clearance", where=pads, between=pads, min=mm(2), priority=1)
    else:
        script.rules.rule(
            "u8_power_ctrl",
            "clearance",
            where=select.ref("U8") & select.netclass("POWER"),
            between=select.ref("U8") & select.netclass("CTRL"),
            min=mm(2),
            priority=1,
        )
    return ClearanceResolver(to_model(script))


def pad(net: str, netclass: str) -> RuleSubject:
    return RuleSubject("pad", net, netclass, ref="U8", layer="F.Cu")


def test_a_part_wide_pad_rule_holds_for_its_logic_pins_too() -> None:
    value = resolver(part_wide=True).resolve(pad("LOGIC_A", "CTRL"), pad("LOGIC_B", "CTRL"))
    assert (value.value, value.source) == (mm(2).nm, "rule:u8_pads")


def test_a_rule_per_pair_of_domains_leaves_the_logic_pins_alone() -> None:
    found = resolver(part_wide=False)
    logic = found.resolve(pad("LOGIC_A", "CTRL"), pad("LOGIC_B", "CTRL"))
    assert logic.value == mm(0.2).nm
    across = found.resolve(pad("BUS", "POWER"), pad("LOGIC_A", "CTRL"))
    assert (across.value, across.source) == (mm(2).nm, "rule:u8_power_ctrl")


def test_a_no_connect_pad_is_reached_by_part_not_by_class() -> None:
    found = resolver(part_wide=False)
    no_connect = pad("unconnected-(U8-NC-Pad7)", "Default")
    against_bus = found.resolve(pad("BUS", "POWER"), no_connect)
    assert against_bus.source != "rule:u8_power_ctrl"
    wide = resolver(part_wide=True).resolve(pad("BUS", "POWER"), no_connect)
    assert (wide.value, wide.source) == (mm(2).nm, "rule:u8_pads")
