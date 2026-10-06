# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The six rule kinds of change c0071 in the lowering and the reader (capability rules-model, "Rule kinds
and limits", "Closed selector grammar", "Kind support by major" and "Lowering refuses what it cannot
represent"; capability kicad-file-backend, "Custom rules files are read and written"). The KiCad scenarios
are in ``tests/kicad/rules/test_rule_kinds_new.py``."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import get_args

import pytest

from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.dru import RulesLossError, read_rules, write_rules
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.base import Opaque
from fenolite.model.rules import Rule, RuleKind, RuleSet, Selector

ROOT = Path(__file__).resolve().parents[4]
PROBES = ROOT / "docs" / "evidence" / "kicad" / "probes"
NEW_KINDS = (
    "hole_to_hole",
    "hole_clearance",
    "annular_width",
    "courtyard_clearance",
    "silk_clearance",
    "creepage",
)
_COUNTER = itertools.count(1)


def rule(kind: str, a: Selector | None = None, *, name: str = "", **fields: object) -> Rule:
    n = next(_COUNTER)
    values: dict[str, object] = {"min": 300_000} | fields
    return Rule(
        id=derived_id("rul", "test", f"kinds:{n}"),
        name=name or f"k{n}",
        kind=kind,  # type: ignore[arg-type]
        selector_a=a or Selector("all"),
        **values,  # type: ignore[arg-type]
    )


def lowered(*items: Rule, target: int = 10, allow_lossy: bool = False) -> tuple[str, tuple[Issue, ...]]:
    result = lower_rules(
        RuleSet(id=derived_id("rst", "test", "kinds"), rules=items), target=target, allow_lossy=allow_lossy
    )
    return result.text, result.issues


def refused(*items: Rule, target: int = 10, allow_lossy: bool = False) -> RulesLossError:
    with pytest.raises(RulesLossError) as caught:
        lowered(*items, target=target, allow_lossy=allow_lossy)
    return caught.value


def net(value: str) -> Selector:
    return Selector("net", value)


# -- kinds and limits


def test_tables_cover_every_kind() -> None:
    kinds = set(get_args(RuleKind))
    assert set(rulemap.KIND_SUPPORT) == set(rulemap.KIND_SELECTORS) == set(rulemap.KIND_MAP) == kinds
    assert set(rulemap.LIMITS) == kinds and set(NEW_KINDS) < kinds
    for kind in NEW_KINDS:
        assert rulemap.LIMITS[kind] == frozenset({"min"})


def test_hole_to_hole_rule() -> None:
    text, issues = lowered(rule("hole_to_hole", net("PWR"), name="pitch"))
    assert issues == ()
    assert "(condition \"A.NetName == 'PWR'\")" in text
    assert "(constraint hole_to_hole (min 0.3mm))" in text and '(rule "fenolite_0_pitch"' in text


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_board_wide_rule_of_each_kind_round_trips(kind: str) -> None:
    text, _ = lowered(rule(kind, name=kind, min=0))
    assert f"(constraint {kind} (min 0mm))" in text and "condition" not in text
    again = read_rules(text)
    assert [(r.kind, r.min, r.selector_a) for r in again.rules] == [(kind, 0, Selector("all"))]


@pytest.mark.parametrize("limit", ["opt", "max"])
def test_limit_outside_a_new_kind(limit: str) -> None:
    error = refused(rule("annular_width", min=100_000, **{limit: 300_000}))
    assert [i.code for i in error.issues] == ["rules.unsupported-limit"] and not error.droppable


# -- selectors per kind


def test_courtyard_by_reference() -> None:
    selector = Selector("or", items=(Selector("ref", "U1"), Selector("ref", "U2")))
    text, _ = lowered(rule("courtyard_clearance", selector, min=0))
    assert "(condition \"(A.Reference == 'U1' || A.Reference == 'U2')\")" in text
    assert "(constraint courtyard_clearance (min 0mm))" in text and "memberOfFootprint" not in text
    assert read_rules(text).rules[0].selector_a == selector


def test_ref_of_another_kind_stays_a_member() -> None:
    text, _ = lowered(rule("hole_clearance", Selector("ref", "U1")))
    assert "A.memberOfFootprint('U1')" in text


@pytest.mark.parametrize(
    "made",
    [
        lambda: rule("silk_clearance", Selector("ref", "U1")),
        lambda: rule("silk_clearance", net("A")),
        lambda: rule("courtyard_clearance", net("A")),
        lambda: rule("courtyard_clearance", Selector("ref", "U*")),
        lambda: rule("creepage", Selector("ref", "U1")),
        lambda: rule("creepage", Selector("item_kind", "via")),
        lambda: rule("hole_to_hole", net("A"), selector_b=net("B")),
        lambda: rule("annular_width", net("A"), layers=("F.Cu",)),
        lambda: rule("hole_clearance", layers=("F.Cu",)),
        lambda: rule("track_width", net("A"), selector_b=net("B")),
    ],
)
def test_outside_the_grammar_of_a_kind(made: object) -> None:
    error = refused(made(), allow_lossy=True)  # type: ignore[operator]
    assert {i.code for i in error.issues} == {"rules.unsupported-selector"}
    assert not error.droppable and "--allow-lossy" not in (error.hint or "")


def test_narrowed_silk_rule_names_the_kind() -> None:
    error = refused(rule("silk_clearance", Selector("ref", "U1")))
    assert "silk_clearance" in error.issues[0].message


def test_creepage_takes_both_sides() -> None:
    made = rule("creepage", Selector("netclass", "HV"), selector_b=Selector("netclass", "LV"), min=4_000_000)
    text, _ = lowered(made, target=10)
    assert "(condition \"A.NetClass == 'HV' && B.NetClass == 'LV'\")" in text
    assert "(constraint creepage (min 4mm))" in text


# -- kind support by major


def test_creepage_for_target_9() -> None:
    assert rulemap.KIND_SUPPORT["creepage"] == frozenset({10})
    made = rule("creepage", Selector("netclass", "HV"), selector_b=Selector("netclass", "LV"), min=4_000_000)
    error = refused(made, target=9)
    assert error.droppable and [i.code for i in error.issues] == ["rules.kind-unchecked"]
    assert "creepage" in error.issues[0].message and "9" in error.issues[0].message
    assert error.cli_code == "FEN-7001"
    text, issues = lowered(made, target=9, allow_lossy=True)
    assert text == "(version 1)\n" and [i.code for i in issues] == ["rules.dropped-for-target"]


def test_dropped_kind_leaves_the_other_rules() -> None:
    text, issues = lowered(
        rule("creepage", name="creep"), rule("clearance", name="gap"), target=9, allow_lossy=True
    )
    assert "fenolite_0_gap" in text and "creep" not in text
    assert [i.code for i in issues] == ["rules.dropped-for-target"]


def test_unchecked_kind_with_another_error_is_not_droppable() -> None:
    error = refused(rule("creepage"), rule("clearance", min=200_000, max=500_000), target=9)
    assert not error.droppable
    assert {i.code for i in error.issues} == {"rules.kind-unchecked", "rules.unsupported-limit"}


def test_kind_support_follows_the_probe_files() -> None:
    """Each new kind holds exactly the majors whose committed probe file records ``present`` for it."""
    expected: dict[str, set[int]] = {kind: set() for kind in NEW_KINDS}
    for name, major in {"9.0.9": 9, "10.0.6": 10}.items():
        probes: dict[str, str] = json.loads((PROBES / f"{name}.json").read_text(encoding="utf-8"))["probes"]
        for kind in NEW_KINDS:
            if probes.get(f"dru-kind-{kind}") == "present":
                expected[kind].add(major)
    assert {kind: set(rulemap.KIND_SUPPORT[kind]) for kind in NEW_KINDS} == expected  # type: ignore[index]
    for kind in set(get_args(RuleKind)) - set(NEW_KINDS):
        assert rulemap.KIND_SUPPORT[kind] == frozenset({9, 10})


# -- reading


def test_new_kind_lifted() -> None:
    source = "(version 1)\n(rule ring (constraint annular_width (min 0.1mm)))\n"
    issues: list[Issue] = []
    ruleset = read_rules(source, issues=issues)
    assert issues == []
    (ring,) = ruleset.rules
    assert (ring.kind, ring.selector_a, ring.min) == ("annular_width", Selector("all"), 100_000)
    written = write_rules(ruleset, target=10)
    assert '(rule "ring"' in written and "(constraint annular_width (min 0.1mm))" in written
    assert "severity" not in written and read_rules(written).rules[0].min == 100_000


def test_courtyard_rule_by_membership_stays_opaque() -> None:
    line = "(rule c (condition \"A.memberOfFootprint('U1')\") (constraint courtyard_clearance (min 0.5mm)))"
    issues: list[Issue] = []
    ruleset = read_rules(f"(version 1)\n{line}\n", issues=issues)
    assert ruleset.rules == ()
    assert [i.code for i in issues] == ["rules.kept-opaque"] and "memberOfFootprint" in issues[0].message
    assert Opaque(line, "1") in slotlib.from_ext(ruleset.ext["kicad"])


@pytest.mark.parametrize(
    "line",
    [
        "(rule x (condition \"A.Reference == 'U1'\") (constraint clearance (min 0.5mm)))",
        "(rule x (condition \"A.NetName == 'A'\") (constraint silk_clearance (min 0.5mm)))",
        '(rule x (layer "F.Cu") (constraint hole_to_hole (min 0.5mm)))',
        "(rule x (condition \"A.NetName == 'A' && B.NetName == 'B'\") (constraint hole_clearance (min 1mm)))",
        "(rule x (condition \"A.Type == 'Via'\") (constraint creepage (min 0.5mm)))",
        "(rule x (constraint annular_width (max 0.5mm)))",
    ],
)
def test_rules_outside_a_kind_stay_opaque(line: str) -> None:
    issues: list[Issue] = []
    assert read_rules(f"(version 1)\n{line}\n", issues=issues).rules == ()
    assert [i.code for i in issues] == ["rules.kept-opaque"]


def test_reference_reads_as_ref_only_for_courtyards() -> None:
    assert rulemap.parse_condition("A.Reference == 'U1'") is None
    assert rulemap.parse_condition("A.Reference == 'U1'", reference=True) == (Selector("ref", "U1"), None)
