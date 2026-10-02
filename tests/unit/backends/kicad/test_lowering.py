# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lowering the model's rules (capability rules-model; change c0018). ``SELECTOR_SUPPORT`` is set per
test; the KiCad scenarios are in ``tests/kicad/rules/``."""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType

import pytest

from fenolite.backends.base import WriteResult
from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad.dru import RulesLossError, RulesSelfCheckError, read_rules, write_rules
from fenolite.backends.kicad.lowering import EVIDENCE, LoweredRules, lower_rules, lowered_names
from fenolite.cli.errors import REGISTRY
from fenolite.core.errors import Issue
from fenolite.core.evidence import Level
from fenolite.core.ids import derived_id
from fenolite.model.rules import Rule, RuleSet, Selector

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src" / "fenolite" / "backends" / "kicad"
RULES = ROOT / "tests" / "data" / "kicad" / "rules"
_COUNTER = itertools.count(1)
PRODUCED: list[Issue] = []


@pytest.fixture(autouse=True)
def proved(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(
        rulemap, "SELECTOR_SUPPORT", MappingProxyType({k: frozenset({9, 10}) for k in rulemap.SELECTOR_KEYS})
    )
    yield


def rule(kind: str = "clearance", a: Selector | None = None, **fields: object) -> Rule:
    n = next(_COUNTER)
    values: dict[str, object] = {"name": f"r{n}", "min": 200_000} | fields
    return Rule(
        id=derived_id("rul", "test", str(n)),
        kind=kind,  # type: ignore[arg-type]
        selector_a=a or Selector("all"),
        **values,  # type: ignore[arg-type]
    )


def rules(*items: Rule) -> RuleSet:
    return RuleSet(id=derived_id("rst", "test", "x"), rules=items)


def lowered(*items: Rule, target: int = 10, allow_lossy: bool = False) -> LoweredRules:
    result = lower_rules(rules(*items), target=target, allow_lossy=allow_lossy)
    PRODUCED.extend(result.issues)
    return result


def refused(*items: Rule, target: int = 10, allow_lossy: bool = False) -> RulesLossError:
    with pytest.raises(RulesLossError) as caught:
        lower_rules(rules(*items), target=target, allow_lossy=allow_lossy)
    PRODUCED.extend(caught.value.issues)
    return caught.value


def names(text: str) -> list[str]:
    return re.findall(r'^\(rule "([^"]+)"', text, flags=re.MULTILINE)


# -- Fenolite lowers only the design's rules


def test_empty_rule_set() -> None:
    assert lowered() == WriteResult("(version 1)\n", ())
    assert LoweredRules is WriteResult


def test_one_rule_gives_one_rule_list() -> None:
    text = lowered(rule(a=Selector("net", "HV"), min=2_000_000), target=9).text
    assert text.count("(rule ") == 1 and "(constraint clearance (min 2mm))" in text


def test_rule_set_read_from_a_file_refused() -> None:
    ruleset = read_rules((RULES / "comments.kicad_dru").read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="write_rules"):
        lower_rules(ruleset)


def test_no_shipped_rule_values() -> None:
    """Fenolite ships no rule tables or defaults: the lowering writes only what the rule set holds."""
    text = lowered(rule(name="only")).text
    assert names(text) == ["fenolite_0_only"]


# -- priority


def test_priority_one_last() -> None:
    text = lowered(rule(name="a", priority=1), rule(name="b", priority=3), rule(name="c", priority=2)).text
    assert names(text) == ["fenolite_3_b", "fenolite_2_c", "fenolite_1_a"]


def test_ties_by_name() -> None:
    text = lowered(rule(name="zeta", priority=2), rule(name="alpha", priority=2)).text
    assert names(text) == ["fenolite_2_alpha", "fenolite_2_zeta"]


# -- kinds and limits


def test_exact_millimetres() -> None:
    text = lowered(rule("track_width", min=250_000, opt=300_000, max=1_000_000)).text
    assert "(constraint track_width (min 0.25mm) (opt 0.3mm) (max 1mm))" in text
    assert "(severity error)" in text


def test_via_drill() -> None:
    text = lowered(rule("via_drill", Selector("net", "PWR"), min=300_000)).text
    assert "(constraint hole_size (min 0.3mm))" in text
    assert "(condition \"A.Type == 'Via' && A.NetName == 'PWR'\")" in text


def test_clearance_with_a_maximum() -> None:
    error = refused(rule(name="clr", max=500_000))
    assert [i.code for i in error.issues] == ["rules.unsupported-limit"] and "clr" in error.issues[0].message


@pytest.mark.parametrize("kind", sorted(rulemap.KIND_MAP))
def test_each_kind_lowers(kind: str) -> None:
    text = lowered(rule(kind, min=100_000)).text
    assert f"(constraint {rulemap.KIND_MAP[kind]} (min 0.1mm))" in text  # type: ignore[index]


# -- selectors


def test_net_and_class_on_both_sides() -> None:
    text = lowered(rule(a=Selector("net", "HV"), selector_b=Selector("netclass", "LV"))).text
    assert "(condition \"A.NetName == 'HV' && B.NetClass == 'LV'\")" in text


def test_compound_selector() -> None:
    a = Selector("and", items=(Selector("net", "A"), Selector("not", items=(Selector("item_kind", "via"),))))
    assert "(condition \"(A.NetName == 'A' && !(A.Type == 'Via'))\")" in lowered(rule(a=a)).text


def test_layer_op_refused() -> None:
    error = refused(rule(a=Selector("layer", "F.Cu")))
    assert [i.code for i in error.issues] == ["rules.unsupported-selector"]
    assert error.droppable is False and "--allow-lossy" not in error.hint


def test_quote_inside_a_net_name() -> None:
    error = refused(rule(a=Selector("net", "it's")))
    assert [i.code for i in error.issues] == ["rules.unsupported-selector"] and "it's" in error.issues[
        0
    ].message


def test_glob_refused_where_not_proved(monkeypatch: pytest.MonkeyPatch) -> None:
    table = {k: frozenset({9, 10}) for k in rulemap.SELECTOR_KEYS} | {"glob": frozenset({10})}
    monkeypatch.setattr(rulemap, "SELECTOR_SUPPORT", MappingProxyType(table))
    error = refused(rule(a=Selector("net", "PWR_*")), target=9)
    assert [i.code for i in error.issues] == ["rules.unsupported-selector"]
    assert "(condition \"A.NetName == 'PWR_*'\")" in lowered(rule(a=Selector("net", "PWR_*"))).text


def test_unproved_op_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    table = {k: frozenset({9, 10}) for k in rulemap.SELECTOR_KEYS} | {"ref": frozenset()}
    monkeypatch.setattr(rulemap, "SELECTOR_SUPPORT", MappingProxyType(table))
    error = refused(rule(a=Selector("ref", "R1")))
    assert [i.code for i in error.issues] == ["rules.unsupported-selector"] and "ref" in error.issues[
        0
    ].message
    assert "--allow-lossy" not in error.hint


def test_all_needs_no_support(monkeypatch: pytest.MonkeyPatch) -> None:
    """With every entry empty (the table before any probe passed), a rule on ``all`` still lowers."""
    monkeypatch.setattr(
        rulemap, "SELECTOR_SUPPORT", MappingProxyType({k: frozenset() for k in rulemap.SELECTOR_KEYS})
    )
    assert lowered(rule()).text.count("(rule ") == 1


# -- layers and names


def test_generated_name() -> None:
    assert names(lowered(rule(name="HV Clearance!", priority=2)).text) == ["fenolite_2_hv_clearance"]


def test_two_layers_give_two_rules() -> None:
    text = lowered(rule(name="hv", priority=1, layers=("F.Cu", "B.Cu"))).text
    assert names(text) == ["fenolite_1_hv_f_cu", "fenolite_1_hv_b_cu"]
    assert text.index('(layer "F.Cu")') < text.index('(layer "B.Cu")')


def test_unknown_layer() -> None:
    assert [i.code for i in refused(rule(layers=("Copper.Top",))).issues] == ["rules.unsupported-layer"]


def test_repeated_names() -> None:
    text = lowered(rule(name="x", priority=1), rule(name="X", priority=1), rule(name="x!", priority=1)).text
    assert sorted(names(text)) == ["fenolite_1_x", "fenolite_1_x_2", "fenolite_1_x_3"]
    assert lowered_names([rule(name="a b", layers=("F.Cu", "B.Cu")), rule(name="a b f cu")]) == (
        "fenolite_0_a_b",
        "fenolite_0_a_b_f_cu_2",
    )


# -- refusals


def test_several_errors_reported_together() -> None:
    error = refused(rule(a=Selector("layer", "F.Cu")), rule(max=1), allow_lossy=True)
    assert error.droppable is False
    assert sorted(i.code for i in error.issues) == ["rules.unsupported-limit", "rules.unsupported-selector"]


def test_error_code_in_the_cli_registry() -> None:
    error = refused(rule(a=Selector("layer", "F.Cu")))
    assert error.cli_code == "FEN-7001" and REGISTRY["FEN-7001"].exit_code == 7


# -- self-check


def test_writer_and_reader_disagree(monkeypatch: pytest.MonkeyPatch) -> None:
    original = rulemap.condition_text

    def broken(r: Rule, *, target: int) -> tuple[str | None, tuple[Issue, ...]]:
        text, issues = original(r, target=target)
        return (text or "").replace("==", "="), issues

    monkeypatch.setattr(rulemap, "condition_text", broken)
    with pytest.raises(RulesSelfCheckError) as caught:
        lower_rules(rules(rule(a=Selector("net", "X"))))
    assert caught.value.step == "lift" and caught.value.cli_code == "FEN-1001"


def test_normal_form_of_a_via_drill_rule() -> None:
    original = rule("via_drill", Selector("net", "PWR"), min=300_000)
    (lifted,) = read_rules(lowered(original).text).rules
    via, pwr = Selector("item_kind", "via"), Selector("net", "PWR")
    assert lifted.kind == "hole_size" and lifted.selector_a == Selector("and", items=(via, pwr))
    assert lifted.selector_a == rulemap.normal_form(original).selector_a


def test_via_drill_normal_forms() -> None:
    (lifted,) = read_rules(lowered(rule("via_drill", min=300_000)).text).rules
    assert lifted.selector_a == Selector("item_kind", "via")


def test_evidence() -> None:
    assert EVIDENCE.level is Level.KICAD_VERIFIED
    assert set(EVIDENCE.hypotheses) == {"H-K-DRU-DIALECT", "H-K-DRU-ORDER", "H-K-DRU-COND", "H-K-DRU-KIND"}


# -- the closed set of codes


def test_codes() -> None:
    found: list[Issue] = []
    read_rules((RULES / "opaque.kicad_dru").read_text(encoding="utf-8"), issues=found)
    write_rules(
        read_rules((RULES / "ten_only.kicad_dru").read_text(encoding="utf-8")),
        target=9,
        allow_lossy=True,
        issues=found,
    )
    for issue in [*PRODUCED, *found]:
        if issue.code.startswith(("kicad.token.", "kicad.version.")):
            continue
        assert rulemap.RULE_ISSUE_CODES[issue.code] == issue.severity, issue
    literals: set[str] = set()
    for path in SRC.glob("*.py"):
        literals |= set(re.findall(r'"(rules\.[a-z0-9-]+)"', path.read_text(encoding="utf-8")))
    assert literals == set(rulemap.RULE_ISSUE_CODES)
    assert {i.code for i in [*PRODUCED, *found]} >= {"rules.kept-opaque", "rules.dropped-for-target"}
