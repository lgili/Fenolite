# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Change c0465: the rule kinds ``short`` and ``antenna`` and their limits (rules-model, "Short and antenna
rules")."""

from __future__ import annotations

from typing import Any, get_args

import pytest

from fenolite.backends.kicad import rulemap
from fenolite.model import Rule, Selector
from fenolite.model.canonical import dumps, loads
from fenolite.model.rules import RuleKind, RuleSet

AGND = Selector("net", "AGND")
DGND = Selector("net", "DGND")
RST = "rst_00000000-0000-4000-8000-0000000c0465"


def _rule(kind: RuleKind, **fields: Any) -> Rule:
    return Rule(id="rul_00000000-0000-4000-8000-0000000c0465", name="r", kind=kind, selector_a=AGND, **fields)


def test_both_kinds_follow_no_tracks_and_precede_the_pair_kinds() -> None:
    kinds = get_args(RuleKind)
    assert kinds[12:15] == ("no_tracks", "short", "antenna") and len(kinds) == 20
    for table in (rulemap.KIND_SELECTORS, rulemap.KIND_SUPPORT, rulemap.KIND_MAP, rulemap.LIMITS):
        assert {"short", "antenna"} <= set(table)
    assert rulemap.KIND_SUPPORT["antenna"] == frozenset()  # KiCad measures no stub (S-2242)
    assert rulemap.KIND_SELECTORS["short"].side_b and not rulemap.KIND_SELECTORS["antenna"].side_b


def test_a_short_rule_between_two_grounds_builds() -> None:
    rule = _rule("short", selector_b=DGND, severity="ignore")
    assert (rule.min, rule.opt, rule.max, rule.severity) == (None, None, None, "ignore")
    assert loads(dumps(RuleSet(id=RST, rules=(rule,))), RuleSet).rules == (rule,)


@pytest.mark.parametrize(
    "fields",
    [
        {},  # no second side
        {"selector_b": DGND, "min": 100_000},
        {"selector_b": DGND, "max": 0},
    ],
)
def test_a_short_rule_needs_two_sides_and_no_limit(fields: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="short rule"):
        _rule("short", **fields)


def test_an_antenna_rule_holds_max_alone() -> None:
    assert _rule("antenna", max=0).max == 0
    rule = _rule("antenna", max=1_270_000, severity="warning")
    assert loads(dumps(RuleSet(id=RST, rules=(rule,))), RuleSet).rules == (rule,)


@pytest.mark.parametrize(
    "fields",
    [
        {},  # no max
        {"max": -1},
        {"min": 0, "max": 1_000},
        {"opt": 1_000, "max": 1_000},
        {"max": 1_000, "selector_b": DGND},
    ],
)
def test_an_antenna_rule_refuses_other_limits(fields: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="antenna rule"):
        _rule("antenna", **fields)


def test_the_other_kinds_are_unchanged() -> None:
    # the limits of the other kinds are judged where they are declared and lowered, not here
    assert _rule("clearance").min is None
    assert _rule("no_tracks", min=5).min == 5
