# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The clearance in force (capability copper-check, "Clearance in force"; change c0029)."""

from __future__ import annotations

import dataclasses
import random

from _coppercheck import Copper, ident, mm

from fenolite.backends.kicad import rulemap
from fenolite.checks.clearance import UNSET, ZONE_SOURCE, Clearance, ClearanceResolver, rule_precedence
from fenolite.core.coords import Point
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


# --- the zone's own clearance (change c0068, ``H-K-COPPER-ZONECLR``) -------------------------------


def zoned(*, rule: int | None = None) -> Design:
    """Nets ``A`` and ``B`` in the class ``Signal`` (0.2 mm), and optionally the rule ``pair`` on them."""
    made = Copper()
    made.netclass("Signal", mm(0.2))
    made.net("A", "Signal")
    made.net("B", "Signal")
    if rule is not None:
        made.rule("pair", rule, net("A"), net("B"))
    return made.build()


def resolve_zone(design: Design, zone_clearance: int | None, **switches: object) -> Clearance:
    """A fill of ``A`` against a track of ``B``."""
    resolver = ClearanceResolver(design, **switches)  # type: ignore[arg-type]
    ids = {n.name: n.id for n in design.circuit.nets}
    fill = resolver.subject("fill", ids["A"], ref=None, layer="F.Cu")
    track = resolver.subject("track", ids["B"], ref=None, layer="F.Cu")
    found = resolver.resolve(fill, track, zone_clearance=zone_clearance)
    assert resolver.resolve(track, fill, zone_clearance=zone_clearance) == found
    return found


def test_zone_clearance_above_the_class() -> None:
    """Scenario "Zone clearance above the class"."""
    assert resolve_zone(zoned(), 300_000) == Clearance(mm(0.3), "error", ZONE_SOURCE)
    assert resolve_zone(zoned(), 100_000) == Clearance(mm(0.2), "error", "class:Signal")
    assert ZONE_SOURCE == "zone"


def test_zone_clearance_equal_values_name_the_class_then_the_zone() -> None:
    assert resolve_zone(zoned(), mm(0.2)).source == "class:Signal"
    assert resolve_zone(zoned(), mm(0.3), min_clearance=mm(0.3)).source == "zone"


def test_zone_clearance_of_zero_or_none_counts_for_nothing() -> None:
    for value in (None, 0, -5):
        assert resolve_zone(zoned(), value) == Clearance(mm(0.2), "error", "class:Signal")
    bare = Copper()
    bare.net("A")
    bare.net("B")
    assert resolve_zone(bare.build(), None) == UNSET
    assert resolve_zone(bare.build(), mm(0.3)) == Clearance(mm(0.3), "error", "zone")


def test_rule_replaces_the_zone_clearance() -> None:
    """Scenario "Rule replaces the zone clearance"."""
    design = zoned(rule=mm(0.2))
    assert resolve_zone(design, 500_000) == Clearance(mm(0.2), "error", "rule:pair")
    assert resolve_zone(design, 500_000, rules_over_classes=False) == Clearance(mm(0.5), "error", "zone")
    # a rule below the class value: the class is kept where a class value is kept, and the zone above it
    low = zoned(rule=mm(0.1))
    assert resolve_zone(low, 150_000, rules_over_classes=False).source == "class:Signal"
    assert resolve_zone(low, 150_000) == Clearance(mm(0.1), "error", "rule:pair")


def test_zone_clearance_under_an_ignore_rule() -> None:
    made = Copper()
    made.net("A")
    made.net("B")
    made.rule("quiet", mm(0.2), net("A"), net("B"), severity="ignore")
    found = resolve_zone(made.build(), mm(0.5))
    assert found.value is None and found.source == "rule:quiet"


def test_board_minimum_above_the_zone() -> None:
    """Scenario "Board minimum above the zone"."""
    assert resolve_zone(zoned(), 300_000, min_clearance=mm(0.4)) == Clearance(mm(0.4), "error", "floor")
    assert resolve_zone(zoned(), 300_000, min_clearance=mm(0.25)) == Clearance(mm(0.3), "error", "zone")


def test_zone_clearance_is_part_of_the_memo_key() -> None:
    design = zoned()
    resolver = ClearanceResolver(design)
    ids = {n.name: n.id for n in design.circuit.nets}
    fill = resolver.subject("fill", ids["A"], ref=None, layer="F.Cu")
    track = resolver.subject("track", ids["B"], ref=None, layer="F.Cu")
    assert resolver.resolve(fill, track, zone_clearance=mm(0.5)).value == mm(0.5)
    assert resolver.resolve(fill, track).value == mm(0.2)
    assert resolver.resolve(fill, track, zone_clearance=mm(0.3)).value == mm(0.3)


def test_max_value_holds_the_clearance_of_zones_with_fills() -> None:
    ring = (Point(0, 0), Point(mm(4), 0), Point(mm(4), mm(4)), Point(0, mm(4)))
    made = Copper()
    made.netclass("Signal", mm(0.2))
    made.zone("A", ring, clearance=mm(0.7))  # no fill: nothing of it is judged
    assert ClearanceResolver(made.build()).max_value == mm(0.2)
    made.zone("A", ring, fills=[ring], clearance=mm(0.6))
    assert ClearanceResolver(made.build()).max_value == mm(0.6)
    made.zone("A", ring, fills=[ring], clearance=0)
    assert ClearanceResolver(made.build()).max_value == mm(0.6)


# --- rules scoped to an area (change c0103) ------------------------------------------------------------


def area_design(value: str = "HV") -> Design:
    made = Copper()
    made.netclass("Signal", mm(0.2))
    made.net("A", "Signal")
    made.net("B", "Signal")
    made.rule("hv", mm(2), Selector("area", value))
    return made.build()


def area_pair(design: Design, *areas: str) -> Clearance:
    resolver = ClearanceResolver(design)
    ids = {n.name: n.id for n in design.circuit.nets}
    first = resolver.subject("track", ids["A"], ref=None, layer="F.Cu", areas=frozenset(areas))
    second = resolver.subject("track", ids["B"], ref=None, layer="F.Cu")
    assert first.areas == frozenset(areas) and second.areas == frozenset()
    assert resolver.resolve(first, second) == resolver.resolve(second, first)
    return resolver.resolve(first, second)


# --- the clearance inside a differential pair (change c0104) ---------------------------------------


def usb_pair(*, clearance: int | None = mm(0.2), gap: int | None = mm(0.1)) -> Copper:
    """Nets ``USB_P``, ``USB_N`` and ``CLK`` in the class ``USB`` with ``clearance`` and the pair gap
    ``gap``."""
    made = Copper()
    made.classes["USB"] = dataclasses.replace(made.netclass("USB", clearance), diff_pair_gap=gap)
    for name in ("USB_P", "USB_N", "CLK"):
        made.net(name, "USB")
    return made


def inside(design: Design, a: str = "USB_P", b: str = "USB_N", **switches: object) -> Clearance:
    resolver = ClearanceResolver(design, **switches)  # type: ignore[arg-type]
    ids = {n.name: n.id for n in design.circuit.nets}
    first = resolver.subject("track", ids[a], ref=None, layer="F.Cu")
    second = resolver.subject("track", ids[b], ref=None, layer="F.Cu")
    assert resolver.resolve(first, second) == resolver.resolve(second, first)
    return resolver.resolve(first, second)


def test_rule_scoped_to_an_area() -> None:
    """Scenario "Rule scoped to an area"."""
    design = area_design()
    assert area_pair(design, "HV") == Clearance(mm(2), "error", "rule:hv")
    assert area_pair(design) == Clearance(mm(0.2), "error", "class:Signal")
    assert area_pair(design, "ANT", "HV").source == "rule:hv"
    assert ClearanceResolver(design).max_value == mm(2)


def test_area_names_keep_their_case() -> None:
    """Scenario "Area names keep their case": other leaves fold, area leaves do not."""
    assert area_pair(area_design(), "hv").source == "class:Signal"
    assert area_pair(area_design("hv"), "HV").source == "class:Signal"
    assert area_pair(area_design("H*"), "HV").source == "rule:hv"
    assert area_pair(area_design("h*"), "HV").source == "class:Signal"


def test_area_beside_a_folded_leaf() -> None:
    made = Copper()
    made.net("GND")
    made.net("B")
    made.rule("hv", mm(2), Selector("and", items=(Selector("area", "HV"), Selector("net", "gnd"))))
    design = made.build()
    resolver = ClearanceResolver(design)
    ids = {n.name: n.id for n in design.circuit.nets}
    inside = resolver.subject("track", ids["GND"], ref=None, layer="F.Cu", areas=frozenset({"HV"}))
    other = resolver.subject("track", ids["B"], ref=None, layer="F.Cu")
    assert resolver.resolve(inside, other).source == "rule:hv"
    outside = resolver.subject("track", ids["GND"], ref=None, layer="F.Cu")
    assert resolver.resolve(outside, other) == UNSET


def test_pair_subjects_carry_their_base() -> None:
    design = usb_pair().build()
    resolver = ClearanceResolver(design)
    ids = {n.name: n.id for n in design.circuit.nets}
    assert resolver.subject("track", ids["USB_P"], ref=None, layer="F.Cu").diff_pair == "USB_"
    assert resolver.subject("via", ids["USB_N"], ref=None, layer="F.Cu").diff_pair == "USB_"
    assert resolver.subject("track", ids["CLK"], ref=None, layer="F.Cu").diff_pair is None
    assert resolver.subject("track", None, ref=None, layer="F.Cu").diff_pair is None


def test_pair_below_its_class_clearance() -> None:
    design = usb_pair().build()
    assert inside(design) == Clearance(mm(0.1), "error", "pair-gap:USB")
    assert inside(design, "USB_P", "CLK") == Clearance(mm(0.2), "error", "class:USB")
    assert ClearanceResolver(design).max_value == mm(0.2)


def test_pair_gap_applies_only_below_the_class_clearance() -> None:
    assert inside(usb_pair(gap=mm(0.25)).build()).source == "class:USB"
    assert inside(usb_pair(gap=mm(0.2)).build()).source == "class:USB"
    assert inside(usb_pair(gap=None).build()).source == "class:USB"
    assert inside(usb_pair(clearance=None).build()) == UNSET


def test_pair_gap_needs_one_class_and_one_pair() -> None:
    made = usb_pair()
    made.netclass("OTHER", mm(0.2))
    made.net("DAT_P", "USB")
    made.net("DAT_N", "OTHER")
    made.net("AUX_P", "USB")
    made.net("AUX_N0", "USB")
    design = made.build()
    assert inside(design, "DAT_P", "DAT_N").source in ("class:OTHER", "class:USB")
    assert inside(design, "AUX_P", "AUX_N0").source == "class:USB"
    assert inside(design, "USB_P", "USB_P").source == "class:USB"


def test_rules_over_the_pair_gap() -> None:
    made = usb_pair()
    made.rule("board", mm(0.2))
    assert inside(made.build(), rules_over_classes=True) == Clearance(mm(0.2), "error", "rule:board")
    pair_leaf = Selector("diff_pair", "USB_")
    made.rule("inside", mm(0.1), pair_leaf, pair_leaf, priority=1)
    design = made.build()
    assert inside(design, rules_over_classes=True) == Clearance(mm(0.1), "error", "rule:inside")
    assert inside(design, "USB_P", "CLK", rules_over_classes=True).source == "rule:board"


def test_rule_below_the_pair_gap_where_classes_stay() -> None:
    made = usb_pair()
    made.rule("low", mm(0.05))
    assert inside(made.build(), rules_over_classes=False) == Clearance(mm(0.1), "error", "pair-gap:USB")


def test_board_minimum_above_the_pair_gap() -> None:
    design = usb_pair().build()
    assert inside(design, min_clearance=mm(0.12)) == Clearance(mm(0.12), "error", "floor")
    assert inside(design, min_clearance=mm(0.05)).source == "pair-gap:USB"


def test_letter_case_of_the_pair_leaf() -> None:
    made = usb_pair()
    made.rule("lower", mm(0.5), Selector("diff_pair", "usb_"))
    assert inside(made.build()) == Clearance(mm(0.1), "error", "pair-gap:USB")
    made.rule("every", mm(0.3), Selector("diff_pair", "*"), priority=1)
    assert inside(made.build()).source == "rule:every"
    other = usb_pair()
    other.rule("net_name", mm(0.4), Selector("net", "usb_p"))  # the other leaves compare without case
    assert inside(other.build()).source == "rule:net_name"
