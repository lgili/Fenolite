# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule kind ``no_tracks`` in the model, the lowering and the reader (capability rules-model, "Rule kinds
and limits" and "Track layer rules"; capability kicad-file-backend, "Track layer rules in rules files"; change
c0107). The KiCad scenario is ``tests/kicad/rules/test_rule_kinds_new.py::test_no_tracks_rule``."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad.dru import RulesLossError, read_rules, write_rules
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.canonical import dumps, loads
from fenolite.model.rules import Rule, RuleKind, RuleSet, Selector

ROOT = Path(__file__).resolve().parents[4]
OLD_RULES = ROOT / "tests" / "data" / "model" / "v0.2.1" / "twelve_kinds.rules.json"
SIG = Selector("netclass", "SIG")
INNER = ("In1.Cu", "In2.Cu")


def rule(name: str = "sig-outer", **fields: object) -> Rule:
    values: dict[str, object] = {"selector_a": SIG, "layers": INNER} | fields
    return Rule(id=derived_id("rul", "test", f"nt:{name}"), name=name, kind="no_tracks", **values)  # type: ignore[arg-type]


def ruleset(*rules: Rule) -> RuleSet:
    return RuleSet(id=derived_id("rst", "test", "nt"), rules=rules)


def refused(*rules: Rule, target: int = 10) -> list[Issue]:
    with pytest.raises(RulesLossError) as caught:
        lower_rules(ruleset(*rules), target=target)
    return list(caught.value.issues)


# -- the model


def test_thirteen_kinds_no_tracks_last() -> None:
    kinds = get_args(RuleKind)
    assert len(kinds) == 13 and kinds[-1] == "no_tracks"
    assert kinds[:12] == (
        "clearance", "track_width", "via_diameter", "via_drill", "hole_size", "edge_clearance",
        "hole_to_hole", "hole_clearance", "annular_width", "courtyard_clearance", "silk_clearance",
        "creepage",
    )  # fmt: skip
    assert set(rulemap.KIND_MAP) == set(rulemap.LIMITS) == set(rulemap.KIND_SELECTORS) == set(kinds)
    assert rulemap.KIND_MAP["no_tracks"] == "disallow" and rulemap.LIMITS["no_tracks"] == frozenset()
    grammar = rulemap.KIND_SELECTORS["no_tracks"]
    assert grammar.leaves == {"net", "netclass"} and grammar.layers and not grammar.side_b


def test_old_document_keeps_its_bytes() -> None:
    """A rules document of the twelve kinds, written by the code before this change, loads and serialises
    to its own bytes; one with a ``no_tracks`` rule holds the new value."""
    text = OLD_RULES.read_bytes().decode("utf-8")
    assert '"no_tracks"' not in text
    old = loads(text, RuleSet)
    assert len(old.rules) == 12
    assert {r.kind for r in old.rules} == set(get_args(RuleKind)[:12])
    assert dumps(old).encode("utf-8") == OLD_RULES.read_bytes()
    new = dumps(ruleset(rule()))
    assert '"kind": "no_tracks"' in new and loads(new, RuleSet) == ruleset(rule())
    for name in ("docs/design-model.md", "CHANGELOG.md"):
        page = " ".join((ROOT / name).read_text(encoding="utf-8").split())
        assert "cannot read a model document that holds a `no_tracks` rule" in page, name


# -- lowering


def test_no_tracks_one_rule_per_layer() -> None:
    """Scenario "A class kept off the inner layers"."""
    result = lower_rules(ruleset(rule()), target=10)
    assert result.issues == ()
    assert result.text == (
        "(version 1)\n"
        '(rule "fenolite_0_sig_outer_in1_cu"\n\t(layer "In1.Cu")\n\t(condition "A.NetClass == \'SIG\'")\n'
        "\t(constraint disallow track)\n\t(severity error)\n)\n"
        '(rule "fenolite_0_sig_outer_in2_cu"\n\t(layer "In2.Cu")\n\t(condition "A.NetClass == \'SIG\'")\n'
        "\t(constraint disallow track)\n\t(severity error)\n)\n"
    )


def test_no_tracks_without_a_limit_is_written_and_clearance_is_not() -> None:
    """Scenario "Thirteen kinds, one without a limit"."""
    text = lower_rules(ruleset(rule("one", selector_a=Selector("all"), layers=("B.Cu",))), target=10).text
    assert (
        '(rule "fenolite_0_one"\n\t(layer "B.Cu")\n\t(constraint disallow track)\n\t(severity error)\n)'
        in text
    )
    bare = Rule(
        id=derived_id("rul", "test", "bare"), name="bare", kind="clearance", selector_a=Selector("all")
    )
    assert [i.code for i in refused(bare)] == ["rules.unsupported-limit"]


def test_no_tracks_refusals() -> None:
    """Scenario "Refusals": a limit, a B side, no layer."""
    issues = refused(
        rule("limit", min=100_000),
        rule("side", selector_b=Selector("netclass", "HV")),
        rule("bare", layers=()),
    )
    assert sorted(i.code for i in issues) == [
        "rules.unsupported-layer",
        "rules.unsupported-limit",
        "rules.unsupported-selector",
    ]
    by_code = {i.code: i.message for i in issues}
    assert "limit" in by_code["rules.unsupported-limit"] and "bare" in by_code["rules.unsupported-layer"]
    assert "side" in by_code["rules.unsupported-selector"]


@pytest.mark.parametrize("limit", ["opt", "max"])
def test_no_tracks_takes_no_other_limit(limit: str) -> None:
    assert [i.code for i in refused(rule("x", **{limit: 100_000}))] == ["rules.unsupported-limit"]


@pytest.mark.parametrize(
    "selector",
    [
        Selector("ref", "U1"),
        Selector("item_kind", "via"),
        Selector("and", items=(SIG, Selector("ref", "U1"))),
    ],
)
def test_no_tracks_selector_grammar(selector: Selector) -> None:
    assert {i.code for i in refused(rule("x", selector_a=selector))} == {"rules.unsupported-selector"}


def test_no_tracks_compound_selector_and_severity() -> None:
    selector = Selector("or", items=(Selector("net", "A"), Selector("not", items=(SIG,))))
    text = lower_rules(
        ruleset(rule("x", selector_a=selector, layers=("F.Cu",), severity="warning")), target=10
    ).text
    assert "(condition \"(A.NetName == 'A' || !(A.NetClass == 'SIG'))\")" in text
    assert "(constraint disallow track)\n\t(severity warning)" in text


def test_no_tracks_layer_names() -> None:
    assert [i.code for i in refused(rule("x", layers=("Inner1",)))] == ["rules.unsupported-layer"]


def test_no_tracks_outside_its_majors() -> None:
    """A target outside ``KIND_SUPPORT["no_tracks"]`` gives ``rules.kind-unchecked``."""
    for target in {9, 10} - set(rulemap.KIND_SUPPORT["no_tracks"]):
        issues = refused(rule(), target=target)
        assert [i.code for i in issues] == ["rules.kind-unchecked"] and "no_tracks" in issues[0].message
    assert 10 in rulemap.KIND_SUPPORT["no_tracks"]


# -- reading

FORMS = """(version 1)
(rule "a" (layer "In2.Cu") (condition "A.NetClass == 'SIG'") (constraint disallow track))
(rule "b" (layer inner) (condition "A.NetClass == 'SIG'") (constraint disallow track))
(rule "c" (layer "F.Cu") (constraint disallow via))
(rule "d" (constraint disallow track))
(rule "e" (layer "F.Cu") (constraint disallow track via))
(rule "f" (layer "F.Cu") (condition "A.Type == 'Via'") (constraint disallow track))
(rule "g" (layer "F.Cu") (constraint disallow track (min 1mm)))
"""


def test_no_tracks_lift_and_opaque_forms() -> None:
    """Scenario "Lift and opaque forms"."""
    issues: list[Issue] = []
    found = read_rules(FORMS, issues=issues)
    (a,) = found.rules
    assert (a.name, a.kind, a.selector_a, a.selector_b, a.layers) == (
        "a",
        "no_tracks",
        SIG,
        None,
        ("In2.Cu",),
    )
    assert (a.min, a.opt, a.max, a.severity) == (None, None, None, "error")
    assert [i.code for i in issues] == ["rules.kept-opaque"] * 6
    reasons = [i.message for i in issues]
    assert "layer" in reasons[0] and "disallow via" in reasons[1] and "layer" in reasons[2]
    assert "disallow track via" in reasons[3]
    text = write_rules(found, target=10)
    for line in FORMS.splitlines()[2:]:
        assert f"\n{line}\n" in text, line
    assert '(rule "a"' in text and text.count("(constraint disallow track)") == 4


def test_no_tracks_lowered_and_read_back() -> None:
    made = ruleset(rule(severity="warning"), rule("all", selector_a=Selector("all"), layers=("B.Cu",)))
    issues: list[Issue] = []
    back = read_rules(lower_rules(made, target=10).text, issues=issues)
    assert issues == []
    assert [(r.kind, r.selector_a, r.layers, r.severity) for r in back.rules] == [
        ("no_tracks", Selector("all"), ("B.Cu",), "error"),
        ("no_tracks", SIG, ("In1.Cu",), "warning"),
        ("no_tracks", SIG, ("In2.Cu",), "warning"),
    ]
