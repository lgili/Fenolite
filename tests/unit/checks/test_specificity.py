# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Specificity informs by default and changes precedence only on explicit request."""

from dataclasses import replace

import pytest

from fenolite.checks.clearance import rule_precedence
from fenolite.checks.specificity import explain_rules, rank, shadowed_rules
from fenolite.dsl import Design, Net, mm, select, to_model
from fenolite.model.rules import Selector


@pytest.mark.parametrize(
    "selector,expected",
    [
        (select.ALL, 0),
        (select.netclass("HS"), 2),
        (select.net("CLK"), 5),
        (select.net("CLK*") & select.item("track"), 4),
        (select.net("A") | select.netclass("HS"), 2),
        (~select.ref("U*"), 0),
        (select.ref("U1"), 4),
        (select.area("A"), 1),
    ],
)
def test_ranks(selector, expected: int) -> None:
    assert rank(selector.to_model()) == expected


def design(*, explicit: bool = True, specificity: bool = False):
    script = Design("precedence")
    net = Net("CLK")
    script.add(net)
    script.rules.netclass("HS", nets=(net,))
    if specificity:
        script.rules.precedence("specificity")
    script.rules.rule(
        "net rule", "track_width", where=select.net("CLK"), min=mm(1), **({"priority": 3} if explicit else {})
    )
    script.rules.rule(
        "class rule",
        "track_width",
        where=select.netclass("HS"),
        min=mm(2),
        **({"priority": 1} if explicit else {}),
    )
    return to_model(script)


def test_shadowed_class_over_net() -> None:
    model = design()
    (found,) = shadowed_rules(model)
    assert found.code == "rules.shadowed" and found.severity == "info"
    assert "class rule" in found.message and "rank 2" in found.message
    assert "net rule" in found.message and "rank 5" in found.message
    assert "priority=" in found.hint and 'precedence("specificity")' in found.hint


def test_check_reuses_selected_stage_inputs_for_shadowed_rules() -> None:
    from _topologybench import bench, ident
    from fakes import FakeRulesValidator, project, validation

    from fenolite.checks.stages import run_checks
    from fenolite.model.rules import Rule

    model = bench()
    assert model.rules is not None
    exact = Rule(
        id=ident("rul", "exact"),
        name="exact",
        kind="track_width",
        selector_a=Selector("net", "CLK"),
        min=1,
        priority=3,
    )
    broad = replace(
        exact, id=ident("rul", "broad"), name="broad", selector_a=Selector("net", "*"), priority=1
    )
    model = replace(model, rules=replace(model.rules, rules=(exact, broad)))
    backend = FakeRulesValidator(result=validation(model))
    report = run_checks(
        project=project(),
        stages=("copper.clearance",),
        model=None,
        built=False,
        validator=backend,
        oracle=None,
    )
    assert [kind for kind, _ in backend.asked] == ["rules", "pads"]
    assert len([issue for issue in report.issues if issue.code == "rules.shadowed"]) == 1


def test_specificity_opt_in_preserves_explicit_priority() -> None:
    model = design(explicit=False, specificity=True)
    assert model.rules is not None
    assert rule_precedence(model.rules.rules)[-1].name == "net rule"
    assert not shadowed_rules(model)
    model = design(explicit=True, specificity=True)
    assert model.rules is not None
    assert rule_precedence(model.rules.rules)[-1].name == "class rule"
    assert shadowed_rules(model)


def test_explanation_uses_precedence_and_sorts_rows() -> None:
    model = design()
    rows = explain_rules(model)
    assert len(rows) == 1
    row = rows[0]
    assert (row["subject"], row["kind"], row["rank"]) == ("CLK", "track_width", 2)
    assert row["governing"]["name"] == "class rule"
    assert row["overrides"][0]["name"] == "net rule"
    assert model.rules is not None
    rule = model.rules.rules[0]
    two_sided = replace(rule, selector_b=Selector("netclass", "HS"))
    from fenolite.checks.specificity import rule_rank

    assert rule_rank(two_sided) == 7


def test_area_subjects_use_copper_geometry_and_binary_contexts() -> None:
    from _topologybench import MM, bench, ident

    from fenolite.core.coords import Point
    from fenolite.model.board import Keepout
    from fenolite.model.rules import Rule, RuleSet

    model = bench()
    assert model.board is not None
    area = Keepout(
        id=ident("kpo", "scope"),
        name="scope",
        outline=(Point(-MM, -MM), Point(31 * MM, -MM), Point(31 * MM, MM), Point(-MM, MM)),
        layers=("F.Cu",),
    )
    exact = Rule(
        id=ident("rul", "exact"),
        name="net",
        kind="track_width",
        selector_a=Selector("net", "CLK"),
        min=1,
        priority=3,
    )
    broad = replace(
        exact, id=ident("rul", "area"), name="area", selector_a=Selector("area", "scope"), priority=1
    )
    model = replace(
        model,
        board=replace(model.board, keepouts=(area,)),
        rules=RuleSet(id=ident("rst", "area"), rules=(exact, broad)),
    )
    rows = explain_rules(model)
    assert any(
        row["subject"] == "CLK:track@F.Cu{scope}" and row["governing"]["name"] == "area" for row in rows
    )
    assert len(shadowed_rules(model)) == 1
    binary = replace(broad, kind="clearance", selector_b=Selector("net", "CLK"))
    unary = replace(exact, kind="clearance")
    model = replace(model, rules=replace(model.rules, rules=(unary, binary)))
    rows = explain_rules(model)
    assert any("~" in row["subject"] for row in rows)
