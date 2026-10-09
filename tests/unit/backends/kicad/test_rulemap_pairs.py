# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pair and length rule kinds and the pair leaf in the rules grammar (capability rules-model, "Rule
kinds and limits" and "Closed selector grammar"; change c0104). The support tables are set to both majors
per test, except where a test reads the shipped tables against the probe files."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType
from typing import get_args

import pytest

from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad.dru import RulesLossError, read_rules
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.rules import Rule, RuleKind, RuleSet, Selector

ROOT = Path(__file__).resolve().parents[4]
PROBES = ROOT / "docs" / "evidence" / "kicad" / "probes"
PAIR_KINDS = ("diff_pair_gap", "diff_pair_uncoupled", "skew", "diff_pair_skew", "length")
BOTH = frozenset({9, 10})
USB = Selector("diff_pair", "USB_")


@pytest.fixture(autouse=True)
def proved(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> Iterator[None]:
    if "shipped" not in request.node.name:
        monkeypatch.setattr(
            rulemap, "SELECTOR_SUPPORT", MappingProxyType(dict.fromkeys(rulemap.SELECTOR_KEYS, BOTH))
        )
        monkeypatch.setattr(
            rulemap,
            "KIND_SUPPORT",
            MappingProxyType({**rulemap.KIND_SUPPORT, **dict.fromkeys(PAIR_KINDS, BOTH)}),
        )
    yield


def rule(kind: str, a: Selector = USB, *, name: str = "r", **fields: object) -> Rule:
    return Rule(
        id=derived_id("rul", "test", f"pairs:{name}:{kind}"),
        name=name,
        kind=kind,  # type: ignore[arg-type]
        selector_a=a,
        **fields,  # type: ignore[arg-type]
    )


def lowered(*rules: Rule, target: int = 10) -> str:
    return lower_rules(RuleSet(id=derived_id("rst", "test", "pairs"), rules=rules), target=target).text


def refused(*rules: Rule, target: int = 10) -> RulesLossError:
    with pytest.raises(RulesLossError) as caught:
        lowered(*rules, target=target)
    return caught.value


def lifted(text: str) -> tuple[tuple[Rule, ...], list[Issue]]:
    issues: list[Issue] = []
    return read_rules(text, issues=issues).rules, issues


def same(a: Rule, b: Rule) -> bool:
    """Equal in what a rule states; the lowered name and the id differ."""
    fields = ("kind", "selector_a", "selector_b", "layers", "min", "opt", "max", "severity")
    return all(getattr(a, f) == getattr(b, f) for f in fields)


# -- tables


def test_tables_hold_the_five_kinds() -> None:
    assert get_args(RuleKind)[-5:] == PAIR_KINDS
    assert {k: rulemap.KIND_MAP[k] for k in PAIR_KINDS} == {  # type: ignore[index]
        "diff_pair_gap": "diff_pair_gap",
        "diff_pair_uncoupled": "diff_pair_uncoupled",
        "skew": "skew",
        "diff_pair_skew": "skew",
        "length": "length",
    }
    assert {k: set(rulemap.LIMITS[k]) for k in PAIR_KINDS} == {  # type: ignore[index]
        "diff_pair_gap": {"min", "opt", "max"},
        "diff_pair_uncoupled": {"max"},
        "skew": {"opt", "max"},
        "diff_pair_skew": {"opt", "max"},
        "length": {"min", "opt", "max"},
    }
    assert dict(rulemap.KIND_FLAGS) == {"diff_pair_skew": "within_diff_pairs"}
    for kind in PAIR_KINDS:
        grammar = rulemap.KIND_SELECTORS[kind]  # type: ignore[index]
        assert grammar.leaves == {"diff_pair", "net", "netclass"} and not grammar.side_b
        assert grammar.layers is (kind == "diff_pair_gap")
    assert "diff_pair" in rulemap.KIND_SELECTORS["clearance"].leaves
    assert "diff_pair" not in rulemap.KIND_SELECTORS["creepage"].leaves
    assert "diff_pair" in rulemap.SELECTOR_KEYS


def test_shipped_support_follows_the_probe_files() -> None:
    """``KIND_SUPPORT`` of the five kinds and ``SELECTOR_SUPPORT["diff_pair"]`` hold exactly the majors
    whose committed probe file records ``present`` (``H-K-DRU-PAIR``, ``H-K-DRU-PAIRSEL``)."""
    kinds: dict[str, set[int]] = {kind: set() for kind in PAIR_KINDS}
    leaf: set[int] = set()
    for name, major in {"9.0.9": 9, "10.0.6": 10}.items():
        probes: dict[str, str] = json.loads((PROBES / f"{name}.json").read_text(encoding="utf-8"))["probes"]
        for kind in PAIR_KINDS:
            if probes.get(f"dru-kind-{kind}") == "present":
                kinds[kind].add(major)
        if probes.get("dru-cond-diff_pair") == "present":
            leaf.add(major)
    assert {kind: set(rulemap.KIND_SUPPORT[kind]) for kind in PAIR_KINDS} == kinds  # type: ignore[index]
    assert set(rulemap.SELECTOR_SUPPORT["diff_pair"]) == leaf
    assert 10 in leaf and all(10 in majors for majors in kinds.values())


def test_shipped_kind_outside_its_majors_is_refused() -> None:
    """ "Kind support by major" applies to the pair kinds as written: a major without a recorded probe gives
    ``rules.kind-unchecked``."""
    missing = sorted({9, 10} - set(rulemap.KIND_SUPPORT["length"]))
    for target in missing:
        error = refused(rule("length", Selector("net", "CLK"), max=60_000_000), target=target)
        assert [i.code for i in error.issues] == ["rules.kind-unchecked"] and error.droppable


# -- kinds and limits


def test_pair_gap_rule() -> None:
    text = lowered(rule("diff_pair_gap", min=130_000, max=200_000), target=9)
    assert "(constraint diff_pair_gap (min 0.13mm) (max 0.2mm))" in text
    assert "(condition \"A.inDiffPair('USB_')\")" in text


def test_skew_within_each_pair() -> None:
    every = Selector("diff_pair", "*")
    within = rule("diff_pair_skew", every, max=150_000)
    text = lowered(within)
    assert "(constraint skew (max 0.15mm) (within_diff_pairs))" in text
    (back,), issues = lifted(text)
    assert back.kind == "diff_pair_skew" and same(back, within) and issues == []
    group = rule("skew", every, max=150_000)
    text = lowered(group)
    assert "(constraint skew (max 0.15mm))" in text and "within_diff_pairs" not in text
    (back,), _ = lifted(text)
    assert back.kind == "skew" and same(back, group)


def test_gap_with_a_target_on_one_layer() -> None:
    made = rule(
        "diff_pair_gap", name="usb gap", min=130_000, opt=150_000, max=170_000, layers=("F.Cu",), priority=1
    )
    text = lowered(made, target=9)
    assert '(rule "fenolite_1_usb_gap"' in text and '(layer "F.Cu")' in text
    assert "(constraint diff_pair_gap (min 0.13mm) (opt 0.15mm) (max 0.17mm))" in text
    (back,), _ = lifted(text)
    assert same(back, made)


def test_limit_outside_a_pair_kind() -> None:
    for made in (
        rule("diff_pair_uncoupled", name="unc", min=1_000_000, max=5_000_000),
        rule("skew", name="skw", min=100_000),
        rule("diff_pair_skew", name="dsk", min=100_000, max=200_000),
        rule("length", name="len"),
    ):
        error = refused(made)
        assert [i.code for i in error.issues] == ["rules.unsupported-limit"]
        assert made.name in error.issues[0].message and not error.droppable


@pytest.mark.parametrize("kind", PAIR_KINDS)
def test_each_pair_kind_round_trips(kind: str) -> None:
    limits = {
        name: 1_000_000 * (i + 1)
        for i, name in enumerate(("min", "opt", "max"))
        if name in rulemap.LIMITS[kind]
    }  # type: ignore[index]
    selector = Selector(
        "or",
        items=(
            USB,
            Selector(
                "and", items=(Selector("netclass", "DDR"), Selector("not", items=(Selector("net", "CLK_P"),)))
            ),
        ),
    )
    for target in (9, 10):
        made = rule(kind, selector, **limits)
        (back,), issues = lifted(lowered(made, target=target))
        assert same(back, made) and issues == []


# -- the pair leaf


def test_clearance_inside_a_pair() -> None:
    made = rule("clearance", selector_b=USB, min=100_000)
    text = lowered(made)
    assert "(condition \"A.inDiffPair('USB_') && B.inDiffPair('USB_')\")" in text
    (back,), _ = lifted(text)
    assert back.selector_a == USB and back.selector_b == USB


def test_pair_leaf_outside_a_kinds_grammar() -> None:
    for made, kind in (
        (rule("creepage", name="creep", min=4_000_000), "creepage"),
        (rule("length", Selector("ref", "U1"), name="len", max=5_000_000), "length"),
        (rule("skew", Selector("item_kind", "via"), name="skw", max=5_000_000), "skew"),
        (rule("diff_pair_uncoupled", name="unc", max=5_000_000, layers=("F.Cu",)), "diff_pair_uncoupled"),
        (rule("length", name="len2", selector_b=USB, max=5_000_000), "length"),
    ):
        error = refused(made)
        assert [i.code for i in error.issues] == ["rules.unsupported-selector"], made.name
        assert kind in error.issues[0].message and not error.droppable
        assert "--allow-lossy" not in error.hint


def test_every_pair_and_compounds() -> None:
    star = rule("diff_pair_gap", Selector("diff_pair", "*"), min=100_000)
    assert "(condition \"A.inDiffPair('*')\")" in lowered(star)
    made = rule("track_width", Selector("and", items=(USB, Selector("item_kind", "track"))), min=100_000)
    assert "(condition \"(A.inDiffPair('USB_') && A.Type == 'Track')\")" in lowered(made)
    error = refused(rule("diff_pair_gap", Selector("diff_pair", "it's"), min=1))
    assert [i.code for i in error.issues] == ["rules.unsupported-selector"]


def test_pair_leaf_needs_its_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    table = {**rulemap.SELECTOR_SUPPORT, "diff_pair": frozenset({10})}
    monkeypatch.setattr(rulemap, "SELECTOR_SUPPORT", MappingProxyType(table))
    error = refused(rule("clearance", min=100_000), target=9)
    assert [i.code for i in error.issues] == ["rules.unsupported-selector"]
    assert "'diff_pair'" in error.issues[0].message
    assert "inDiffPair" in lowered(rule("clearance", min=100_000), target=10)


def test_parse_the_pair_condition() -> None:
    assert rulemap.parse_condition("A.inDiffPair('USB_')") == (USB, None)
    both = rulemap.parse_condition("A.inDiffPair('USB_') && B.inDiffPair('*')")
    assert both == (USB, Selector("diff_pair", "*"))
    for text in ("A.inDiffPair('')", "A.inDiffPair(USB)", "AB.isCoupledDiffPair()", "A.inDiffPair('X', 'Y')"):
        assert rulemap.parse_condition(text) is None, text
