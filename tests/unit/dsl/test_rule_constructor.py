# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``design.rules.rule()`` (capability design-dsl, "Rule constructor in the DSL"; change c0071)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.lowering import lower_rules
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, DslError, mm, select, to_model
from fenolite.model.rules import Selector


def design() -> Design:
    d = Design("rules")
    d.rules.netclass("HV", clearance=mm(2))
    d.rules.netclass("LV", clearance=mm(0.2))
    return d


def test_creepage_rule_in_the_model() -> None:
    d = design()
    d.rules.rule("mains", "creepage", where=select.netclass("HV"), between=select.netclass("LV"), min=mm(6.4))
    (rule,) = to_model(d).rules.rules  # type: ignore[union-attr]
    assert (rule.name, rule.kind, rule.min, rule.severity, rule.priority) == (
        "mains",
        "creepage",
        6_400_000,
        "error",
        0,
    )
    assert rule.selector_a == Selector("netclass", "HV") and rule.selector_b == Selector("netclass", "LV")
    assert rule.id == derived_id("rul", "dsl", "rule:named:mains")


def test_rules_follow_the_minimums_in_call_order() -> None:
    d = design()
    d.rules.rule("zz", "hole_to_hole", min="0.25mm")
    d.rules.minimum(clearance=mm(0.15))
    d.rules.rule(
        "aa", "annular_width", where=select.item("via"), min=mm(0.15), severity="warning", priority=2
    )
    rules = to_model(d).rules.rules  # type: ignore[union-attr]
    assert [r.name for r in rules] == ["min_clearance", "zz", "aa"]
    assert (rules[2].severity, rules[2].priority, rules[2].selector_a) == (
        "warning",
        2,
        Selector("item_kind", "via"),
    )


def test_board_wide_hole_pitch_is_lowered() -> None:
    d = design()
    d.rules.rule("pitch", "hole_to_hole", min="0.25mm")
    text = lower_rules(to_model(d).rules, target=10).text  # type: ignore[arg-type]
    assert '(rule "fenolite_0_pitch"\n\t(constraint hole_to_hole (min 0.25mm))' in text
    assert "condition" not in text


def test_zero_minimum_and_all_limits() -> None:
    d = design()
    d.rules.rule("court", "courtyard_clearance", where=select.ref("U1"), min=mm(0))
    d.rules.rule("w", "track_width", min=mm(0.2), opt=mm(0.25), max=mm(1), layers=("F.Cu",))
    court, width = to_model(d).rules.rules  # type: ignore[union-attr]
    assert court.min == 0
    assert (width.min, width.opt, width.max, width.layers) == (200_000, 250_000, 1_000_000, ("F.Cu",))


@pytest.mark.parametrize(
    ("kwargs", "word"),
    [
        ({"name": "", "kind": "clearance", "min": "1mm"}, "name"),
        ({"name": "x", "kind": "spacing", "min": "1mm"}, "spacing"),
        ({"name": "x", "kind": "clearance"}, "limit"),
        ({"name": "x", "kind": "clearance", "min": 1}, "min"),
        ({"name": "x", "kind": "clearance", "min": "-1mm"}, "negative"),
        ({"name": "x", "kind": "track_width", "max": "0mm"}, "max"),
        ({"name": "x", "kind": "track_width", "min": "1mm", "max": "0.5mm"}, "rise"),
        ({"name": "x", "kind": "track_width", "min": "1mm", "opt": "0.5mm"}, "rise"),
        ({"name": "x", "kind": "clearance", "min": "1mm", "where": "A"}, "where"),
        ({"name": "x", "kind": "clearance", "min": "1mm", "between": "B"}, "between"),
        ({"name": "x", "kind": "hole_clearance", "min": "1mm", "between": select.net("B")}, "hole_clearance"),
        ({"name": "x", "kind": "clearance", "min": "1mm", "layers": ["F.Cu"]}, "layers"),
        ({"name": "x", "kind": "clearance", "min": "1mm", "severity": "fatal"}, "fatal"),
        ({"name": "x", "kind": "clearance", "min": "1mm", "priority": -1}, "priority"),
        ({"name": "x", "kind": "clearance", "min": "1mm", "priority": True}, "priority"),
        ({"name": "x", "kind": "clearance", "min": "1mm", "where": select.netclass("NOPE")}, "NOPE"),
    ],
)
def test_refused_calls_record_nothing(kwargs: dict[str, object], word: str) -> None:
    d = design()
    name, kind = kwargs.pop("name"), kwargs.pop("kind")
    with pytest.raises(DslError, match=word):
        d.rules.rule(name, kind, **kwargs)  # type: ignore[arg-type]
    assert d.rules.named == {}


def test_duplicate_name() -> None:
    d = design()
    d.rules.rule("x", "clearance", min=mm(1))
    with pytest.raises(DslError, match="twice"):
        d.rules.rule("x", "hole_to_hole", min=mm(1))
    assert list(d.rules.named) == ["x"]


def test_default_class_and_globs_need_no_declaration() -> None:
    d = design()
    d.rules.rule("a", "clearance", where=select.netclass("Default"), min=mm(1))
    d.rules.rule("b", "clearance", where=select.netclass("H*"), min=mm(1))
    assert list(d.rules.named) == ["a", "b"]


def test_design_without_rules_is_unchanged() -> None:
    assert to_model(design()).rules.rules == ()  # type: ignore[union-attr]


# -- track layer rules (change c0107)


def test_no_tracks_rule_in_the_model_and_the_rules_file() -> None:
    """Scenario "A class kept on the outer layers"."""
    d = Design("rules")
    d.rules.netclass("SIG", clearance=mm(0.2))
    d.rules.rule("sig-outer", "no_tracks", where=select.netclass("SIG"), layers=("In1.Cu", "In2.Cu"))
    (rule,) = to_model(d).rules.rules  # type: ignore[union-attr]
    assert (rule.kind, rule.selector_a, rule.selector_b) == ("no_tracks", Selector("netclass", "SIG"), None)
    assert rule.layers == ("In1.Cu", "In2.Cu") and (rule.min, rule.opt, rule.max) == (None, None, None)
    text = lower_rules(to_model(d).rules, target=10).text  # type: ignore[arg-type]
    assert text.count("(constraint disallow track)") == 2
    assert '(layer "In1.Cu")' in text and '(layer "In2.Cu")' in text


@pytest.mark.parametrize(
    ("kwargs", "word"),
    [
        ({"layers": ("In1.Cu",), "min": mm(0.1)}, "min"),
        ({"layers": ("In1.Cu",), "opt": mm(0.1)}, "opt"),
        ({"layers": ("In1.Cu",), "max": mm(0.1)}, "max"),
        ({}, "layers"),
        ({"layers": ("In1.Cu",), "between": select.netclass("HV")}, "between"),
    ],
)
def test_no_tracks_malformed(kwargs: dict[str, object], word: str) -> None:
    """Scenario "Malformed track layer rules"."""
    d = design()
    with pytest.raises(DslError, match=word):
        d.rules.rule("x", "no_tracks", **kwargs)  # type: ignore[arg-type]
    assert d.rules.named == {}
