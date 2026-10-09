# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``design.rules.pair()`` and the pair keywords of ``design.rules.netclass()`` (capability design-dsl,
"Pair rules in the DSL" and "Net classes in the DSL"; change c0104)."""

from __future__ import annotations

import pytest
from _buildhelp import blink, build

from fenolite.backends.kicad.lowering import lower_rules
from fenolite.dsl import I2C, USB2, Design, DiffPair, DslError, Net, mm, select, to_model
from fenolite.model.rules import Rule, Selector

USB = Selector("diff_pair", "USB_")


def usb_design() -> tuple[Design, USB2]:
    d = Design("pairs")
    usb = USB2(Net("USB_P"), Net("USB_N"), name="USB")
    return d, usb


def rules_of(d: Design) -> dict[str, Rule]:
    rules = to_model(d).rules
    assert rules is not None
    return {rule.name: rule for rule in rules.rules}


def test_class_with_pair_values() -> None:
    d = Design("classes")
    usb_p, usb_n = Net("USB_P"), Net("USB_N")
    d.rules.netclass(
        "USB", clearance=mm(0.2), diff_pair_width=mm(0.3), diff_pair_gap="0.15mm", nets=(usb_p, usb_n)
    )
    model = to_model(d)
    (usb,) = model.circuit.netclasses
    assert (usb.diff_pair_width, usb.diff_pair_gap, usb.diff_pair_via_gap) == (300_000, 150_000, None)
    assert usb.clearance == 200_000 and model.rules is not None and model.rules.rules == ()
    with pytest.raises(DslError, match="diff_pair_via_gap"):
        d.rules.netclass("BAD", diff_pair_via_gap="wide")


def test_rules_of_a_usb_pair() -> None:
    d, usb = usb_design()
    d.rules.pair(usb, gap_min=mm(0.13), gap_max=mm(0.17), clearance=mm(0.13), skew_max=mm(0.15))
    rules = rules_of(d)
    assert list(rules) == ["pair:USB:gap", "pair:USB:clearance", "pair:USB:skew"]
    gap, clearance, skew = rules.values()
    assert (gap.kind, gap.min, gap.max, gap.selector_a, gap.selector_b) == (
        "diff_pair_gap",
        130_000,
        170_000,
        USB,
        None,
    )
    assert (clearance.kind, clearance.min, clearance.selector_a, clearance.selector_b) == (
        "clearance",
        130_000,
        USB,
        USB,
    )
    assert (skew.kind, skew.max, skew.min) == ("diff_pair_skew", 150_000, None)
    assert {rule.priority for rule in rules.values()} == {1} and {r.severity for r in rules.values()} == {
        "error"
    }
    assert "USB" in d.interfaces and {"USB_P", "USB_N"} <= set(d.nets)


def test_every_group_in_table_order() -> None:
    d, usb = usb_design()
    d.rules.pair(
        usb,
        length_max=mm(60),
        length_min=mm(10),
        skew_max=mm(0.5),
        uncoupled_max=mm(5),
        clearance="0.15mm",
        gap_min=mm(0.13),
        severity="warning",
        priority=3,
    )
    rules = rules_of(d)
    assert [name.rsplit(":", 1)[1] for name in rules] == ["gap", "clearance", "uncoupled", "skew", "length"]
    assert [rule.kind for rule in rules.values()] == [
        "diff_pair_gap",
        "clearance",
        "diff_pair_uncoupled",
        "diff_pair_skew",
        "length",
    ]
    assert rules["pair:USB:uncoupled"].max == 5_000_000 and rules["pair:USB:gap"].max is None
    assert (rules["pair:USB:length"].min, rules["pair:USB:length"].max) == (10_000_000, 60_000_000)
    assert {(r.severity, r.priority) for r in rules.values()} == {("warning", 3)}


def test_built_pair_rules() -> None:
    """Scenario "Rules of a USB pair": the build lowers the pair's rules with the rest."""
    d = blink()
    usb = USB2(Net("USB_P"), Net("USB_N"), name="USB")
    d.rules.pair(usb, gap_min=mm(0.13), gap_max=mm(0.17), clearance=mm(0.13), skew_max=mm(0.15))
    out = build(d, target=10)
    assert not [i for i in out.issues if i.severity == "error"], out.issues
    text = out.files[f"{d.name}.kicad_dru"].decode("utf-8")
    start = text.index('(rule "fenolite_1_pair_usb_gap"')
    block = text[start : text.index("\n)\n", start)]
    assert "(constraint diff_pair_gap (min 0.13mm) (max 0.17mm))" in block
    assert "(condition \"A.inDiffPair('USB_')\")" in block
    assert "(condition \"A.inDiffPair('USB_') && B.inDiffPair('USB_')\")" in text
    assert "(constraint skew (max 0.15mm) (within_diff_pairs))" in text


def test_nothing_given() -> None:
    d, usb = usb_design()
    with pytest.raises(DslError, match=r"pair\(\)"):
        d.rules.pair(usb)
    assert d.rules.named == {} and "USB" not in d.interfaces


def test_a_refused_rule_records_nothing() -> None:
    d, usb = usb_design()
    with pytest.raises(DslError, match=r"pair\(\).*rise"):
        d.rules.pair(usb, uncoupled_max=mm(5), gap_min=mm(0.3), gap_max=mm(0.2))
    with pytest.raises(DslError, match=r"pair\(\)"):
        d.rules.pair(usb, gap_min=mm(0.1), skew_max=mm(0))
    with pytest.raises(DslError, match=r"pair\(\).*severity"):
        d.rules.pair(usb, gap_min=mm(0.1), severity="fatal")
    assert d.rules.named == {} and d.interfaces == {}
    d.rules.pair(usb, gap_min=mm(0.1))
    with pytest.raises(DslError, match=r"pair\(\).*twice"):
        d.rules.pair(usb, skew_max=mm(0.1), gap_max=mm(0.2))
    assert list(d.rules.named) == ["pair:USB:gap"]


def test_what_pair_takes() -> None:
    d = Design("pairs")
    with pytest.raises(DslError, match=r"pair\(\).*USB_DN"):
        d.rules.pair(USB2(Net("USB_DP"), Net("USB_DM")), gap_min=mm(0.1))
    with pytest.raises(DslError, match=r"pair\(\)"):
        d.rules.pair(I2C(Net("SDA"), Net("SCL")), gap_min=mm(0.1))
    with pytest.raises(DslError, match=r"pair\(\)"):
        d.rules.pair("USB_", gap_min=mm(0.1))  # type: ignore[arg-type]
    assert d.rules.named == {} and d.interfaces == {} and d.nets == {}
    clk = DiffPair(Net("CLK+"), Net("CLK-"))
    d.rules.pair(clk, uncoupled_max=mm(3))
    (rule,) = rules_of(d).values()
    assert rule.name == "pair:CLK+/CLK-:uncoupled" and rule.selector_a == Selector("diff_pair", "CLK")


def test_pair_rule_after_a_class_minimum() -> None:
    d, usb = usb_design()
    d.rules.netclass("USB", clearance=mm(0.2), nets=tuple(usb.members.values()))
    d.rules.minimum(clearance=mm(0.2), netclass="USB")
    d.rules.pair(usb, clearance=mm(0.13))
    rules = to_model(d).rules
    assert rules is not None
    text = lower_rules(rules, target=10).text
    assert text.index("fenolite_1_min_clearance_usb") < text.index("fenolite_1_pair_usb_clearance")


def test_rule_on_a_pair_selector() -> None:
    d, usb = usb_design()
    d.rules.rule("usb width", "track_width", where=select.pair(usb), min=mm(0.15), opt=mm(0.2), max=mm(0.3))
    d.rules.rule("gap target", "diff_pair_gap", where=select.pair("*"), opt=mm(0.15))
    rules = rules_of(d)
    assert rules["usb width"].selector_a == USB and rules["gap target"].selector_a == Selector(
        "diff_pair", "*"
    )
