# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Which candidates of a route form differential pairs, with which values (capability routing, "Pair
selection for routing"; change c0110). Net names, classes and values are authored for these tests."""

from __future__ import annotations

import dataclasses
import random

from fenolite.core.ids import derived_id, new_id
from fenolite.model.circuit import Circuit, Net, NetClass
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector
from fenolite.routing.pairs import job_pairs

MM = 1_000_000
NAMES = ("USB_P", "USB_N", "D_P0", "D_N0", "SDA")


def design(
    classes: dict[str, NetClass | None] | None = None,
    *,
    default: NetClass | None = None,
    rules: tuple[Rule, ...] = (),
) -> Design:
    """The nets of ``NAMES``, all in the class ``HS`` (pair width 0.2 mm, gap 0.15 mm) unless ``classes``
    gives a net another class or none."""
    rng = random.Random(110)
    hs = NetClass(id=new_id("cls", rng), name="HS", diff_pair_width=200_000, diff_pair_gap=150_000)
    held = {hs.id: hs}
    if default is not None:
        held[default.id] = default
    nets = []
    for name in NAMES:
        netclass = hs if classes is None or name not in classes else classes[name]
        if netclass is not None:
            held.setdefault(netclass.id, netclass)
        nets.append(Net(id=new_id("net", rng), name=name, netclass_id=netclass.id if netclass else None))
    base = Design.new("pairs-unit", seed=110)
    rule_set = RuleSet(id=derived_id("rst", "test", "pairs"), rules=rules) if rules else None
    return dataclasses.replace(
        base,
        circuit=Circuit(nets=tuple(nets), netclasses=tuple(held.values())),
        rules=rule_set,
    )


def skew(name: str, base: str, maximum: int, *, priority: int = 0, severity: str = "error") -> Rule:
    return Rule(
        id=derived_id("rul", "test", name),
        name=name,
        kind="diff_pair_skew",
        selector_a=Selector("diff_pair", base),
        max=maximum,
        priority=priority,
        severity=severity,  # type: ignore[arg-type]
    )


def test_names_that_pair() -> None:
    """Scenario "Names that pair"."""
    pairs, singles, issues = job_pairs(design(), NAMES)
    assert [(p.name, p.positive, p.negative, p.width, p.gap) for p in pairs] == [
        ("D_P0/D_N0", "D_P0", "D_N0", 200_000, 150_000),
        ("USB_P/USB_N", "USB_P", "USB_N", 200_000, 150_000),
    ]
    assert singles == ("SDA",) and issues == ()
    assert all(p.skew_max is None and p.via_gap is None for p in pairs)
    assert job_pairs(design(), NAMES) == (pairs, singles, issues)


def test_one_net_selected() -> None:
    """Scenario "One net selected"."""
    pairs, singles, issues = job_pairs(design(), ("USB_P", "D_P0", "D_N0", "SDA"))
    assert [p.name for p in pairs] == ["D_P0/D_N0"]
    assert singles == ("SDA",)
    assert [issue.code for issue in issues] == ["route.pair-skipped"]
    assert issues[0].severity == "warning"
    assert "USB_P/USB_N" in issues[0].message and "USB_N" in issues[0].message
    assert "--pairs-as-nets" in (issues[0].hint or "")


def test_two_classes() -> None:
    other = NetClass(
        id=derived_id("cls", "test", "other"), name="Slow", diff_pair_width=200_000, diff_pair_gap=150_000
    )
    pairs, singles, issues = job_pairs(design({"USB_N": other}), NAMES)
    assert [p.name for p in pairs] == ["D_P0/D_N0"] and singles == ("SDA",)
    assert len(issues) == 1 and "HS" in issues[0].message and "Slow" in issues[0].message


def test_values_from_the_default_class() -> None:
    """Scenario "Values from the Default class"."""
    bare = NetClass(id=derived_id("cls", "test", "bare"), name="Bare")
    default = NetClass(
        id=derived_id("cls", "test", "default"),
        name="Default",
        diff_pair_width=200_000,
        diff_pair_gap=250_000,
    )
    both = {"USB_P": bare, "USB_N": bare}
    pairs, _, issues = job_pairs(design(both, default=default), NAMES)
    usb = next(p for p in pairs if p.positive == "USB_P")
    assert (usb.width, usb.gap) == (200_000, 250_000) and issues == ()
    pairs, singles, issues = job_pairs(design(both), NAMES)
    assert [p.name for p in pairs] == ["D_P0/D_N0"] and "USB_P" not in singles
    assert len(issues) == 1 and "gap" in issues[0].message and "width" in issues[0].message


def test_default_class_matched_without_letter_case() -> None:
    default = NetClass(
        id=derived_id("cls", "test", "default"),
        name="DEFAULT",
        diff_pair_width=100_000,
        diff_pair_gap=120_000,
    )
    pairs, _, issues = job_pairs(design({name: None for name in NAMES}, default=default), NAMES)
    assert [(p.width, p.gap) for p in pairs] == [(100_000, 120_000)] * 2 and issues == ()


def test_skew_limit_from_a_rule() -> None:
    """Scenario "Skew limit from a rule"."""
    rules = (skew("usb", "USB_", 100_000, priority=1), skew("every", "*", 500_000))
    pairs, _, _ = job_pairs(design(rules=rules), NAMES)
    assert {p.name: p.skew_max for p in pairs} == {"D_P0/D_N0": 500_000, "USB_P/USB_N": 100_000}


def test_rule_of_severity_ignore_is_not_a_limit() -> None:
    rules = (skew("usb", "USB_", 100_000, priority=1, severity="ignore"), skew("every", "*", 500_000))
    pairs, _, _ = job_pairs(design(rules=rules), NAMES)
    assert {p.name: p.skew_max for p in pairs} == {"D_P0/D_N0": 500_000, "USB_P/USB_N": 500_000}


def test_negative_net_first_and_no_pair_without_the_coupled_net() -> None:
    pairs, singles, issues = job_pairs(design(), ("USB_N", "USB_P", "SDA"))
    assert [(p.positive, p.negative) for p in pairs] == [("USB_P", "USB_N")]
    assert singles == ("SDA",) and issues == ()
    # D_P0 alone in a design without D_N0 is a single net
    trimmed = design()
    trimmed = dataclasses.replace(
        trimmed,
        circuit=dataclasses.replace(
            trimmed.circuit, nets=tuple(n for n in trimmed.circuit.nets if n.name != "D_N0")
        ),
    )
    assert job_pairs(trimmed, ("D_P0",)) == ((), ("D_P0",), ())
