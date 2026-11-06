# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Change c0465: ``short`` and ``antenna`` rules lowered to KiCad (rules-model, "Short and antenna rules
lowered to KiCad"; design D6)."""

from __future__ import annotations

import dataclasses
import itertools

import pytest
from _prodesigns import design

from fenolite.backends.kicad import _json, rulemap
from fenolite.backends.kicad.dru import RulesLossError
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

_COUNTER = itertools.count(1)
ALL = Selector("all")


def rule(kind: str, a: Selector = ALL, b: Selector | None = None, **fields: object) -> Rule:
    n = next(_COUNTER)
    return Rule(
        id=derived_id("rul", "test", f"allow:{n}"),
        name=f"a{n}",
        kind=kind,  # type: ignore[arg-type]
        selector_a=a,
        selector_b=b,
        **fields,  # type: ignore[arg-type]
    )


def ruleset(*items: Rule, severities: dict[str, str] | None = None) -> RuleSet:
    return RuleSet(id=derived_id("rst", "test", "allow"), rules=items, severities=severities or {})  # type: ignore[arg-type]


def lowered(rules: RuleSet, *, target: int = 9, allow_lossy: bool = False) -> tuple[str, tuple[Issue, ...]]:
    result = lower_rules(rules, target=target, allow_lossy=allow_lossy)
    return result.text, result.issues


def shorting(rules: RuleSet, target: int) -> object:
    made: Design = dataclasses.replace(design({}, {}), rules=rules)
    text = synthesize_project(made, target=target, board_name="b")
    return _json.loads(text)["board"]["design_settings"]["rule_severities"]["shorting_items"]  # type: ignore[index]


@pytest.mark.parametrize("target", [9, 10])
def test_defaults_are_written_as_nothing(target: int) -> None:
    rules = ruleset(rule("short", ALL, ALL), rule("antenna", Selector("net", "SIG"), max=0),
                    rule("short", Selector("net", "VIN"), ALL))  # fmt: skip
    plain, _ = lowered(ruleset(), target=target)
    text, issues = lowered(rules, target=target)
    assert text == plain and issues == ()
    assert rulemap.board_short(rules) is None  # error rules set no severity
    assert shorting(rules, target) == shorting(ruleset(), target)


@pytest.mark.parametrize(("target", "severity"), [(9, "ignore"), (10, "ignore"), (9, "warning")])
def test_a_whole_board_allowance(target: int, severity: str) -> None:
    """Scenario "A whole-board allowance and a net-pair one", rule set A."""
    allowance = rule("short", ALL, ALL, severity=severity)
    rules = ruleset(allowance)
    plain, _ = lowered(ruleset(), target=target)
    text, issues = lowered(rules, target=target)
    assert text == plain and issues == () and rulemap.board_short(rules) is allowance
    assert shorting(rules, target) == severity


@pytest.mark.parametrize("target", [9, 10])
def test_a_net_pair_allowance_is_a_loss(target: int) -> None:
    """Scenario "A whole-board allowance and a net-pair one", rule set B. On 10 too: the negative clearance
    minimum that silences the short silences the pair's clearance check with it (task 4.2)."""
    rules = ruleset(rule("short", Selector("net", "AGND"), Selector("net", "DGND"), severity="ignore"))
    with pytest.raises(RulesLossError) as caught:
        lowered(rules, target=target)
    assert [i.code for i in caught.value.issues] == ["rules.kind-unchecked"] and caught.value.droppable
    _, issues = lowered(rules, target=target, allow_lossy=True)
    assert [i.code for i in issues] == ["rules.dropped-for-target"]


def test_a_board_allowance_beside_another_short_rule_is_a_loss() -> None:
    allowance = rule("short", ALL, ALL, severity="ignore")
    rules = ruleset(allowance, rule("short", Selector("net", "VIN"), ALL))
    assert rulemap.board_short(rules) is None
    with pytest.raises(RulesLossError) as caught:
        lowered(rules)
    assert [i.code for i in caught.value.issues] == ["rules.kind-unchecked"]


def test_a_board_allowance_that_an_explicit_severity_contradicts_is_a_loss() -> None:
    rules = ruleset(
        rule("short", ALL, ALL, severity="ignore"), severities={"kicad.drc.shorting-items": "error"}
    )
    assert rulemap.board_short(rules) is None
    agreeing = ruleset(
        rule("short", ALL, ALL, severity="ignore"), severities={"kicad.drc.shorting-items": "ignore"}
    )
    assert rulemap.board_short(agreeing) is not None


@pytest.mark.parametrize("target", [9, 10])
def test_an_antenna_tolerance_is_a_loss(target: int) -> None:
    rules = ruleset(rule("antenna", Selector("net", "SIG"), max=1_000_000))
    with pytest.raises(RulesLossError) as caught:
        lowered(rules, target=target)
    assert [i.code for i in caught.value.issues] == ["rules.kind-unchecked"]
    _, issues = lowered(rules, target=target, allow_lossy=True)
    assert [i.code for i in issues] == ["rules.dropped-for-target"]
