# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board-wide rules lowered to board-setup minimums, and the conflicts reported (capability rules-model,
"Board-wide rules lower to board-setup minimums", "Conflicts with board-setup minimums are reported"
and "Class clearances against board-wide clearance rules are reported"; change c0026)."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from fenolite.backends.kicad import lowering
from fenolite.backends.kicad.lowering import (
    FLOOR_OVER_RULES,
    MINIMUM_KEYS,
    RULES_OVER_CLASSES,
    class_conflicts,
    governing_rule,
    is_board_wide,
    lower_minimums,
)
from fenolite.backends.kicad.proerrors import ISSUE_CODES
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.rules import Rule, RuleSet, Selector

ROOT = Path(__file__).resolve().parents[4]
PROBES = ROOT / "docs" / "evidence" / "kicad" / "probes"
_COUNTER = itertools.count(1)
ALL = Selector("all")
FAB = {
    "min_clearance": 100_000,
    "min_track_width": 127_000,
    "min_via_diameter": 450_000,
    "min_through_hole_diameter": 200_000,
    "min_copper_edge_clearance": 300_000,
}

CLAIMED = {key: frozenset({9, 10}) for key in FAB}
"""``FLOOR_OVER_RULES`` as ``H-K-PRO-MIN-RULE`` claimed it, for the scenarios that name it."""


def rule(kind: str, minimum: int | None, a: Selector = ALL, **fields: object) -> Rule:
    n = next(_COUNTER)
    values: dict[str, object] = {"name": f"r{n}", "min": minimum} | fields
    return Rule(
        id=derived_id("rul", "test", str(n)),
        kind=kind,  # type: ignore[arg-type]
        selector_a=a,
        **values,  # type: ignore[arg-type]
    )


def rules(*items: Rule) -> RuleSet:
    return RuleSet(id=derived_id("rst", "test", "x"), rules=items)


def fab() -> RuleSet:
    return rules(
        rule("clearance", 100_000),
        rule("track_width", 127_000),
        rule("via_diameter", 450_000),
        rule("hole_size", 200_000),
        rule("edge_clearance", 300_000),
    )


def codes(found: list[Issue]) -> list[str]:
    return [i.code for i in found]


def test_tables() -> None:
    for major in (9, 10):
        assert dict(MINIMUM_KEYS[major]) == {
            "clearance": "min_clearance",
            "track_width": "min_track_width",
            "via_diameter": "min_via_diameter",
            "hole_size": "min_through_hole_diameter",
            "edge_clearance": "min_copper_edge_clearance",
        }
    assert set(FLOOR_OVER_RULES) == set(MINIMUM_KEYS[10].values())
    assert all(
        code in ISSUE_CODES for code in ("kicad.project.minimum-kept", "kicad.project.rule-below-minimum")
    )


def test_tables_follow_probes() -> None:
    """``-k tables``: each table holds exactly the majors and kinds that the probe outcomes support."""
    outcomes = {
        major: json.loads((PROBES / name).read_text(encoding="utf-8"))["probes"]
        for major, name in ((9, "9.0.9.json"), (10, "10.0.6.json"))
    }
    for major, probes in outcomes.items():
        kinds = {
            kind
            for kind in MINIMUM_KEYS[10]
            if probes.get(f"pro-min-keys-template-{kind}-t{major}") == "present"
            and probes.get(f"pro-min-keys-lowered-{kind}-t{major}") == "absent"
        }
        assert set(MINIMUM_KEYS[major]) == kinds, major
        if probes.get(f"pro-min-class-t{major}") is not None:
            holds = (
                probes[f"pro-min-class-t{major}"] == "absent"
                and probes[f"pro-min-class-control-t{major}"] == "present"
            )
            assert (major in RULES_OVER_CLASSES) == holds, major
    for kind, key in MINIMUM_KEYS[10].items():
        majors = {
            m
            for m, probes in outcomes.items()
            if probes.get(f"pro-min-rules-template-{kind}-t{m}") == "present"
        }
        assert FLOOR_OVER_RULES[key] == majors, key


def test_fab_rule_set() -> None:
    found: list[Issue] = []
    assert lower_minimums(fab(), target=10, current={}, issues=found) == FAB
    assert found == []


def test_later_rule_lowers() -> None:
    hole = rule("hole_size", 300_000, priority=0)
    drill = rule("via_drill", 200_000, priority=1)
    assert lower_minimums(rules(hole, drill), target=9, current={}) == {"min_through_hole_diameter": 200_000}
    assert governing_rule(rules(hole, drill), "hole_size") == hole


def test_earlier_rule_does_not_count() -> None:
    wide = rule("track_width", 200_000, priority=1)
    sig = rule("track_width", 100_000, a=Selector("net", "SIG"), priority=2)
    assert lower_minimums(rules(wide, sig), target=10, current={}) == {"min_track_width": 200_000}


def test_via_drill_alone() -> None:
    drill = rule("via_drill", 200_000)
    assert not is_board_wide(drill)
    assert lower_minimums(rules(drill), target=10, current={}) == {}


def test_layer_or_second_selector() -> None:
    assert not is_board_wide(rule("clearance", 100_000, layers=("F.Cu",)))
    assert not is_board_wide(rule("clearance", 100_000, selector_b=Selector("netclass", "HV")))
    assert is_board_wide(rule("clearance", 100_000, selector_b=ALL))


def test_no_rules() -> None:
    found: list[Issue] = []
    assert lower_minimums(None, target=10, current={"min_track_width": 200_000}, issues=found) == {}
    assert found == []
    assert lower_minimums(rules(), target=10, current={}) == {}


def test_bad_target() -> None:
    with pytest.raises(ValueError, match="unsupported target"):
        lower_minimums(fab(), target=8, current={})


def test_only_rule_values() -> None:
    """Every returned value is the ``min`` of a rule; a later ``max``-only rule adds nothing."""
    wide = rule("track_width", 150_000)
    capped = rule("track_width", None, a=Selector("net", "X"), max=1_000_000, priority=1)
    assert lower_minimums(rules(wide, capped), target=10, current={}) == {"min_track_width": 150_000}


def test_narrower_rule_below_template_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the claim of ``H-K-PRO-MIN-RULE`` (every key on both majors); the probes refuted it."""
    monkeypatch.setattr(lowering, "FLOOR_OVER_RULES", CLAIMED)
    sig = rule("track_width", 100_000, a=Selector("netclass", "SIG"))
    found: list[Issue] = []
    assert lower_minimums(rules(sig), target=10, current={"min_track_width": 200_000}, issues=found) == {}
    assert codes(found) == ["kicad.project.rule-below-minimum"]
    message = found[0].message
    assert sig.name in message and "0.1" in message and "min_track_width" in message and "0.2" in message
    assert found[0].severity == "warning" and "board-wide" in found[0].hint
    table = dict(CLAIMED) | {"min_track_width": frozenset({9})}
    monkeypatch.setattr(lowering, "FLOOR_OVER_RULES", table)
    found = []
    lower_minimums(rules(sig), target=10, current={"min_track_width": 200_000}, issues=found)
    assert found == []


def test_governing_rule_of_severity_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lowering, "FLOOR_OVER_RULES", CLAIMED)
    wide = rule("track_width", 100_000, severity="warning")
    found: list[Issue] = []
    assert lower_minimums(rules(wide), target=9, current={"min_track_width": 200_000}, issues=found) == {}
    assert codes(found) == ["kicad.project.minimum-kept", "kicad.project.rule-below-minimum"]
    assert "warning" in found[0].message and all(wide.name in i.message for i in found)


def test_governing_rule_without_min() -> None:
    found: list[Issue] = []
    assert (
        lower_minimums(rules(rule("track_width", None, max=500_000)), target=10, current={}, issues=found)
        == {}
    )
    assert codes(found) == ["kicad.project.minimum-kept"] and "no min" in found[0].message


def test_measured_tables_report_no_floor() -> None:
    """The shipped ``FLOOR_OVER_RULES`` is empty, so a narrower rule below a minimum is not reported."""
    sig = rule("track_width", 100_000, a=Selector("netclass", "SIG"))
    found: list[Issue] = []
    lower_minimums(rules(sig), target=10, current={"min_track_width": 200_000}, issues=found)
    assert found == [] and all(not majors for majors in FLOOR_OVER_RULES.values())
    assert RULES_OVER_CLASSES == {9, 10}


def test_written_minimum_reports_nothing() -> None:
    found: list[Issue] = []
    lower_minimums(fab(), target=10, current={"min_track_width": 200_000}, issues=found)
    assert found == []


def hv_inputs() -> tuple[RuleSet, dict[str, int]]:
    return rules(rule("clearance", 100_000, priority=0)), {"Default": 200_000, "HV": 2_000_000}


def test_class_shadowed() -> None:
    ruleset, clearances = hv_inputs()
    found: list[Issue] = []
    class_conflicts(ruleset, target=10, clearances=clearances, model_names={"HV"}, issues=found)
    assert codes(found) == ["kicad.project.class-shadowed"]
    assert (
        "HV" in found[0].message and "2 mm" in found[0].message and ruleset.rules[0].name in found[0].message
    )
    restore = rule("clearance", 2_000_000, a=Selector("netclass", "HV"), priority=1)
    found = []
    class_conflicts(
        rules(*ruleset.rules, restore), target=10, clearances=clearances, model_names={"HV"}, issues=found
    )
    assert found == []


def test_model_default_is_shadowed_too() -> None:
    ruleset, clearances = hv_inputs()
    found: list[Issue] = []
    class_conflicts(ruleset, target=9, clearances=clearances, model_names={"HV", "Default"}, issues=found)
    assert sorted(i.message.split("'")[1] for i in found) == ["Default", "HV"]


def test_default_over_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lowering, "RULES_OVER_CLASSES", frozenset())
    ruleset, clearances = hv_inputs()
    found: list[Issue] = []
    class_conflicts(ruleset, target=10, clearances=clearances, model_names={"HV"}, issues=found)
    assert codes(found) == ["kicad.project.default-over-rule"]
    assert "0.2" in found[0].message and "0.1" in found[0].message and "Default" in found[0].hint
    found = []
    class_conflicts(ruleset, target=10, clearances=clearances, model_names={"HV", "Default"}, issues=found)
    assert found == []


def test_no_board_wide_clearance() -> None:
    narrow = rule("clearance", 100_000, a=Selector("net", "X"))
    found: list[Issue] = []
    class_conflicts(rules(narrow), target=10, clearances={"HV": 2_000_000}, model_names={"HV"}, issues=found)
    class_conflicts(None, target=10, clearances={"HV": 2_000_000}, model_names={"HV"}, issues=found)
    assert found == []
