# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The clearance in force (capability copper-check, "Clearance in force"; change c0029)."""

from __future__ import annotations

import random

from _coppercheck import Copper, ident, mm

from fenolite.backends.kicad import rulemap
from fenolite.checks.clearance import UNSET, Clearance, ClearanceResolver, rule_precedence
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSubject, Selector


def net(name: str) -> Selector:
    return Selector("net", name)


def hv_lv(*, rule: int | None = None, **rule_fields: object) -> Design:
    """Nets ``HV`` (class ``HighVoltage``, 0.5 mm) and ``LV`` (class ``Logic``, 0.2 mm), and optionally the
    rule ``hv_lv`` between them."""
    made = Copper()
    made.netclass("HighVoltage", mm(0.5))
    made.netclass("Logic", mm(0.2))
    made.net("HV", "HighVoltage")
    made.net("LV", "Logic")
    if rule is not None:
        made.rule("hv_lv", rule, net("HV"), net("LV"), **rule_fields)  # type: ignore[arg-type]
    return made.build()


def pair(resolver: ClearanceResolver, design: Design, layer: str = "F.Cu") -> tuple[RuleSubject, RuleSubject]:
    ids = {n.name: n.id for n in design.circuit.nets}
    track = resolver.subject("track", ids["LV"], ref=None, layer=layer)
    pad = resolver.subject("pad", ids["HV"], ref="U1", layer=layer)
    return track, pad


def resolve(design: Design, **switches: object) -> Clearance:
    resolver = ClearanceResolver(design, **switches)  # type: ignore[arg-type]
    return resolver.resolve(*pair(resolver, design))


# --- subjects -------------------------------------------------------------------------------------


def test_subjects() -> None:
    made = Copper()
    made.netclass("Power", mm(0.3))
    gnd, sig = made.net("GND", "Power"), made.net("SIG")
    resolver = ClearanceResolver(made.build())
    assert resolver.subject("arc", gnd, ref=None, layer="F.Cu") == RuleSubject(
        "track", "GND", "Power", None, "F.Cu"
    )
    assert resolver.subject("fill", sig, ref=None, layer="B.Cu") == RuleSubject(
        "zone", "SIG", "Default", None, "B.Cu"
    )
    assert resolver.subject("pad", gnd, ref="R1", layer="F.Cu").ref == "R1"
    assert resolver.subject("via", None, ref=None, layer="F.Cu") == RuleSubject(
        "via", None, "Default", None, "F.Cu"
    )


# --- rules ----------------------------------------------------------------------------------------


def test_rule_overrides_the_classes() -> None:
    assert resolve(hv_lv(rule=mm(1))) == Clearance(mm(1), "error", "rule:hv_lv")
    assert resolve(hv_lv()) == Clearance(mm(0.5), "error", "class:HighVoltage")


def test_rule_matches_in_either_order() -> None:
    design = hv_lv(rule=mm(1))
    resolver = ClearanceResolver(design)
    track, pad = pair(resolver, design)
    assert (
        resolver.resolve(track, pad)
        == resolver.resolve(pad, track)
        == Clearance(mm(1), "error", "rule:hv_lv")
    )


def test_rule_with_one_selector_matches_either_item() -> None:
    made = Copper()
    hv, lv = made.net("HV"), made.net("LV")
    made.rule("hv_any", mm(0.8), net("HV"))
    resolver = ClearanceResolver(made.build())
    a = resolver.subject("track", lv, ref=None, layer="F.Cu")
    b = resolver.subject("via", hv, ref=None, layer="F.Cu")
    assert resolver.resolve(a, b).value == mm(0.8)
    assert resolver.resolve(a, a) == UNSET


def test_rule_candidates() -> None:
    """Only ``clearance`` rules with a ``min`` on the shared layer are candidates."""
    made = Copper()
    hv, lv = made.net("HV"), made.net("LV")
    made.rule("width", mm(1), kind="track_width")
    made.rule("no_min", None)
    made.rule("back_only", mm(0.7), layers=("B.Cu",))
    resolver = ClearanceResolver(made.build())

    def on(layer: str) -> Clearance:
        return resolver.resolve(
            resolver.subject("track", hv, ref=None, layer=layer),
            resolver.subject("track", lv, ref=None, layer=layer),
        )

    assert on("F.Cu") == UNSET
    assert on("B.Cu") == Clearance(mm(0.7), "error", "rule:back_only")
    assert resolver.max_value == mm(0.7)


def test_rule_on_item_kind_and_ref() -> None:
    made = Copper()
    hv, lv = made.net("HV"), made.net("LV")
    made.rule(
        "pads_of_u", mm(0.4), Selector("and", items=(Selector("item_kind", "pad"), Selector("ref", "U*")))
    )
    resolver = ClearanceResolver(made.build())
    track = resolver.subject("track", lv, ref=None, layer="F.Cu")
    assert resolver.resolve(track, resolver.subject("pad", hv, ref="U7", layer="F.Cu")).value == mm(0.4)
    assert resolver.resolve(track, resolver.subject("pad", hv, ref="R7", layer="F.Cu")) == UNSET
    assert resolver.resolve(track, resolver.subject("via", hv, ref=None, layer="F.Cu")) == UNSET


def test_later_rule_governs() -> None:
    made = Copper()
    hv, lv = made.net("HV"), made.net("LV")
    made.rule("a", mm(0.1), priority=1)
    made.rule("b", mm(0.3), priority=2)
    resolver = ClearanceResolver(made.build())
    found = resolver.resolve(
        resolver.subject("track", hv, ref=None, layer="F.Cu"),
        resolver.subject("track", lv, ref=None, layer="F.Cu"),
    )
    assert found == Clearance(mm(0.1), "error", "rule:a")
    assert [r.name for r in rule_precedence(made.rules)] == ["b", "a"]


def test_letter_case_ignored() -> None:
    made = Copper()
    gnd, sig = made.net("GND"), made.net("Sig")
    made.rule("gnd", mm(0.6), net("gnd"), Selector("netclass", "default"))
    resolver = ClearanceResolver(made.build())
    found = resolver.resolve(
        resolver.subject("track", gnd, ref=None, layer="F.Cu"),
        resolver.subject("track", sig, ref=None, layer="F.Cu"),
    )
    assert found == Clearance(mm(0.6), "error", "rule:gnd")


def test_rule_precedence_equals_the_writer_order() -> None:
    """``rule_precedence`` re-implements ``rulemap.rule_order`` (``checks`` cannot import a backend)."""
    rng = random.Random(29)
    for _ in range(200):
        rules = [
            Rule(
                id=ident("rul", rng.randint(1, 10**6)),
                name=rng.choice(("a", "b", "c", "Z", "a_2", "")) or "x",
                kind="clearance",
                selector_a=Selector("all"),
                min=rng.randint(1, 10**6),
                priority=rng.choice((0, 0, 1, 2, 3, 7)),
            )
            for _ in range(rng.randint(0, 12))
        ]
        assert rule_precedence(rules) == rulemap.rule_order(rules)


# --- classes, the floor and the switches ----------------------------------------------------------


def test_classes_above_a_rule_where_kicad_keeps_them() -> None:
    design = hv_lv(rule=mm(0.1))
    assert resolve(design, rules_over_classes=True) == Clearance(mm(0.1), "error", "rule:hv_lv")
    assert resolve(design, rules_over_classes=False) == Clearance(mm(0.5), "error", "class:HighVoltage")
    assert resolve(design) == resolve(design, rules_over_classes=True)


def test_floor_and_ignore() -> None:
    design = hv_lv(rule=mm(0.1))
    assert resolve(design, min_clearance=mm(0.15)) == Clearance(mm(0.1), "error", "rule:hv_lv")
    assert resolve(design, min_clearance=mm(0.15), floor_over_rules=True) == Clearance(
        mm(0.15), "error", "floor"
    )
    ignored = resolve(hv_lv(rule=mm(0.1), severity="ignore"), min_clearance=mm(0.15), floor_over_rules=True)
    assert ignored == Clearance(None, None, "rule:hv_lv")
    assert not ignored.unset


def test_warning_rule_keeps_its_severity_only_when_it_governs() -> None:
    design = hv_lv(rule=mm(0.1), severity="warning")
    assert resolve(design) == Clearance(mm(0.1), "warning", "rule:hv_lv")
    assert resolve(design, rules_over_classes=False).severity == "error"


def test_floor_raises_the_classes_and_applies_alone() -> None:
    assert resolve(hv_lv(), min_clearance=mm(0.6)) == Clearance(mm(0.6), "error", "floor")
    assert resolve(hv_lv(), min_clearance=mm(0.5)) == Clearance(mm(0.5), "error", "class:HighVoltage")
    assert resolve(hv_lv(), min_clearance=0) == Clearance(mm(0.5), "error", "class:HighVoltage")
    made = Copper()
    a, b = made.net("A"), made.net("B")
    resolver = ClearanceResolver(made.build(), min_clearance=mm(0.2))
    subjects = [resolver.subject("track", n, ref=None, layer="F.Cu") for n in (a, b)]
    assert resolver.resolve(*subjects) == Clearance(mm(0.2), "error", "floor")
    assert resolver.max_value == mm(0.2)


def test_default_class_for_a_net_without_one() -> None:
    made = Copper()
    made.netclass("Default", mm(0.2))
    made.netclass("Wide", mm(0.4))
    a, b, c = made.net("A"), made.net("B"), made.net("C", "Wide")
    resolver = ClearanceResolver(made.build())
    one, two, three = (resolver.subject("track", n, ref=None, layer="F.Cu") for n in (a, b, c))
    assert resolver.resolve(one, two) == Clearance(mm(0.2), "error", "class:Default")
    assert resolver.resolve(one, three) == Clearance(mm(0.4), "error", "class:Wide")
    netless = resolver.subject("track", None, ref=None, layer="F.Cu")
    assert resolver.resolve(netless, one) == Clearance(mm(0.2), "error", "class:Default")


def test_unset_and_max_value() -> None:
    made = Copper()
    a, b = made.net("A"), made.net("B")
    resolver = ClearanceResolver(made.build())
    found = resolver.resolve(*(resolver.subject("track", n, ref=None, layer="F.Cu") for n in (a, b)))
    assert found == UNSET and found.unset and found.value is None
    assert resolver.max_value == 0
    assert ClearanceResolver(hv_lv(rule=mm(1)), min_clearance=mm(0.3)).max_value == mm(1)
    assert ClearanceResolver(hv_lv(rule=mm(1), severity="ignore")).max_value == mm(0.5)


def test_design_without_rules_layer() -> None:
    import dataclasses

    design = dataclasses.replace(hv_lv(), rules=None)
    assert resolve(design).value == mm(0.5)


def test_resolution_is_memoised() -> None:
    design = hv_lv(rule=mm(1))
    resolver = ClearanceResolver(design)
    track, pad = pair(resolver, design)
    assert resolver.resolve(track, pad) is resolver.resolve(track, pad) is resolver.resolve(pad, track)
