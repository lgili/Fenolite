# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed rules grammar (capability rules-model; change c0018): values, names, conditions, rule
lists, lifting, the normal form and the order. ``SELECTOR_SUPPORT`` is set per test."""

from __future__ import annotations

import itertools
import json
from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType

import pytest

from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad.rulemap import (
    condition_text,
    format_value,
    lift_rule,
    normal_form,
    parse_condition,
    parse_value,
    rule_nodes,
    rule_order,
    slug,
)
from fenolite.backends.kicad.sexpr import Node, dumps, parse_fragment
from fenolite.core.ids import derived_id
from fenolite.model.rules import Rule, Selector

ROOT = Path(__file__).resolve().parents[4]
PROBES = ROOT / "docs" / "evidence" / "kicad" / "probes"
_COUNTER = itertools.count(1)


def support(**entries: frozenset[int]) -> MappingProxyType[str, frozenset[int]]:
    table = {key: frozenset({9, 10}) for key in rulemap.SELECTOR_KEYS}
    table.update(entries)
    return MappingProxyType(table)


@pytest.fixture
def proved(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(rulemap, "SELECTOR_SUPPORT", support())
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


def net(value: str) -> Selector:
    return Selector("net", value)


def text(node: Node) -> str:
    return dumps(node, style="compact")


def codes(found: object) -> list[str]:
    return [i.code for i in found]  # type: ignore[attr-defined]


# -- values and names


@pytest.mark.parametrize(
    ("value", "nm"), [("0.2mm", 200_000), ("8mil", 203_200), ("0.01in", 254_000), ("1mm", 10**6)]
)
def test_parse_value(value: str, nm: int) -> None:
    assert parse_value(value) == nm


@pytest.mark.parametrize("value", ["1", "1um", "0.2 mm", "1th", "mm", "0.0000001mm"])
def test_parse_value_refused(value: str) -> None:
    with pytest.raises(ValueError):
        parse_value(value)


@pytest.mark.parametrize(
    ("nm", "value"),
    [(250_000, "0.25mm"), (10**6, "1mm"), (203_200, "0.2032mm"), (254_000, "0.254mm"), (300_000, "0.3mm")],
)
def test_format_value(nm: int, value: str) -> None:
    assert format_value(nm) == value


@pytest.mark.parametrize(
    ("name", "expected"),
    [("HV Clearance!", "hv_clearance"), ("F.Cu", "f_cu"), ("!!!", "rule"), ("a__b", "a_b")],
)
def test_slug(name: str, expected: str) -> None:
    assert slug(name) == expected


# -- rule lists and conditions


def test_exact_millimetres(proved: None) -> None:
    nodes, issues = rule_nodes(rule("track_width", min=250_000, opt=300_000, max=1_000_000), target=10)
    assert issues == () and text(nodes[0].find("constraint")) == (  # type: ignore[arg-type]
        "(constraint track_width (min 0.25mm) (opt 0.3mm) (max 1mm))"
    )


def test_via_drill(proved: None) -> None:
    nodes, issues = rule_nodes(rule("via_drill", net("PWR"), min=300_000), target=9)
    assert issues == ()
    assert text(nodes[0].find("constraint")) == "(constraint hole_size (min 0.3mm))"  # type: ignore[arg-type]
    assert nodes[0].find("condition").atoms()[0].value == "A.Type == 'Via' && A.NetName == 'PWR'"  # type: ignore[union-attr]


def test_net_and_class_on_both_sides(proved: None) -> None:
    found, issues = condition_text(rule(a=net("HV"), selector_b=Selector("netclass", "LV")), target=10)
    assert (found, issues) == ("A.NetName == 'HV' && B.NetClass == 'LV'", ())


def test_compound_selector(proved: None) -> None:
    a = Selector("and", items=(net("A"), Selector("not", items=(Selector("item_kind", "via"),))))
    assert condition_text(rule(a=a), target=10) == ("(A.NetName == 'A' && !(A.Type == 'Via'))", ())


def test_all_sides_give_no_condition(proved: None) -> None:
    nodes, _ = rule_nodes(rule(selector_b=Selector("all")), target=10)
    assert nodes[0].find("condition") is None and condition_text(rule(), target=10) == (None, ())


def test_severity_and_name(proved: None) -> None:
    nodes, _ = rule_nodes(rule(name="x y", severity="warning"), target=10)
    assert text(nodes[0]) == '(rule "x y" (constraint clearance (min 0.2mm)) (severity warning))'


def test_two_layers(proved: None) -> None:
    nodes, issues = rule_nodes(rule(name="fenolite_1_hv", layers=("F.Cu", "B.Cu")), target=10)
    assert issues == ()
    assert [(n.atoms()[0].value, n.find("layer").atoms()[0].value) for n in nodes] == [  # type: ignore[union-attr]
        ("fenolite_1_hv_f_cu", "F.Cu"),
        ("fenolite_1_hv_b_cu", "B.Cu"),
    ]


# -- refusals: issue codes, never exceptions


@pytest.mark.parametrize(
    ("made", "code"),
    [
        (lambda: rule(max=500_000), "rules.unsupported-limit"),
        (lambda: rule(min=None), "rules.unsupported-limit"),
        (lambda: rule("hole_size", opt=1), "rules.unsupported-limit"),
        (lambda: rule(a=Selector("layer", "F.Cu")), "rules.unsupported-selector"),
        (lambda: rule(a=net("it's")), "rules.unsupported-selector"),
        (lambda: rule(a=net("A?")), "rules.unsupported-selector"),
        (lambda: rule(a=net("A[1]")), "rules.unsupported-selector"),
        (lambda: rule(a=Selector("item_kind", "keepout")), "rules.unsupported-selector"),
        (lambda: rule(a=Selector("and", items=(net("A"), Selector("all")))), "rules.unsupported-selector"),
        (lambda: rule("track_width", selector_b=net("B")), "rules.unsupported-selector"),
        (lambda: rule(layers=("Copper.Top",)), "rules.unsupported-layer"),
    ],
)
def test_refusals(proved: None, made: object, code: str) -> None:
    nodes, issues = rule_nodes(made(), target=10)  # type: ignore[operator]
    assert nodes == () and codes(issues) == [code]
    assert issues[0].severity == "error"


def test_glob_gated_per_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rulemap, "SELECTOR_SUPPORT", support(glob=frozenset({10})))
    target_9, issues = condition_text(rule(a=net("PWR_*")), target=9)
    assert codes(issues) == ["rules.unsupported-selector"]
    assert condition_text(rule(a=net("PWR_*")), target=10) == ("A.NetName == 'PWR_*'", ())


def test_unproved_op(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rulemap, "SELECTOR_SUPPORT", support(ref=frozenset()))
    _, issues = rule_nodes(rule(a=Selector("ref", "R1")), target=10)
    assert codes(issues) == ["rules.unsupported-selector"] and "'ref'" in issues[0].message


def test_layer_clause_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rulemap, "SELECTOR_SUPPORT", support(layer_clause=frozenset({10})))
    assert codes(rule_nodes(rule(layers=("F.Cu",)), target=9)[1]) == ["rules.unsupported-layer"]
    assert rule_nodes(rule(layers=("F.Cu",)), target=10)[1] == ()


def test_selector_b_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rulemap, "SELECTOR_SUPPORT", support(selector_b=frozenset()))
    assert codes(condition_text(rule(selector_b=net("B")), target=10)[1]) == ["rules.unsupported-selector"]


def test_empty_support_lowers_only_all() -> None:
    assert all(not entry for entry in rulemap.SELECTOR_SUPPORT.values()) or set(
        rulemap.SELECTOR_SUPPORT
    ) == set(rulemap.SELECTOR_KEYS)
    assert rule_nodes(rule(), target=10)[1] == ()


# -- lifting and normal form


@pytest.mark.parametrize(
    "condition",
    [
        "A.NetName == 'HV' && B.NetClass == 'LV'",
        "(A.NetName == 'A' && !(A.Type == 'Via'))",
        "A.memberOfFootprint('R1')",
        "(A.NetName == 'A' || A.NetClass == 'B')",
        "  ( A.NetName ==  'X' ) ",
    ],
)
def test_parse_condition_round_trip(proved: None, condition: str) -> None:
    parsed = parse_condition(condition)
    assert parsed is not None
    a, b = parsed
    again = condition_text(rule(a=a, selector_b=b), target=10)[0]
    assert parse_condition(again or "") == parsed


@pytest.mark.parametrize(
    "condition",
    [
        "A.NetName = 'X'",
        "A.NetName != 'X'",
        "(A.NetName == 'X' || B.NetName == 'Y')",
        "A.insideCourtyard('U1')",
        "A.Type == 'Keepout'",
        "!A.NetName == 'X'",
        "A.NetName == 'X' &&",
        'A.NetName == "X"',
    ],
)
def test_parse_condition_refused(condition: str) -> None:
    assert parse_condition(condition) is None


def test_lift_rule(proved: None) -> None:
    original = rule(
        "track_width", net("N"), name="w", min=100_000, max=200_000, severity="warning", layers=("F.Cu",)
    )
    (node,) = rule_nodes(original, target=10)[0]
    lifted = lift_rule(node)
    assert isinstance(lifted, Rule)
    found = (
        lifted.name,
        lifted.kind,
        lifted.selector_a,
        lifted.layers,
        lifted.min,
        lifted.max,
        lifted.severity,
    )
    assert found == (
        "w", "track_width", net("N"), ("F.Cu",), 100_000, 200_000, "warning"
    )  # fmt: skip


@pytest.mark.parametrize(
    "fragment",
    [
        "(rule x (constraint thermal_spoke_width (min 0.1mm)))",
        "(rule x (layer outer) (constraint clearance (min 0.1mm)))",
        "(rule x (constraint clearance (min 0.1mm)) (severity exclusion))",
        "(rule x (constraint clearance (min 1)))",
        "(rule x (constraint clearance (min 1th)))",
        "(rule x (constraint clearance (max 1mm)))",
        "(rule x (constraint clearance (min 1mm)) (constraint track_width (min 1mm)))",
        "(rule x y (constraint clearance (min 1mm)))",
        "(rule x (condition \"A.NetName == 'X'\") (constraint track_width (min 1mm))"
        " (condition \"A.NetName == 'Y'\"))",
        "(rule x (constraint hole_size (min 1mm)) (condition \"A.NetName == 'X' && B.NetName == 'Y'\"))",
        "(version 1)",
    ],
)
def test_lift_refused(fragment: str) -> None:
    node = parse_fragment(fragment)
    assert isinstance(node, Node) and isinstance(lift_rule(node), str)


def test_via_drill_normal_forms() -> None:
    pwr, hv = net("PWR"), Selector("netclass", "HV")
    forms = [
        normal_form(rule("via_drill", a)).selector_a
        for a in (Selector("all"), pwr, Selector("and", items=(pwr, Selector("not", items=(hv,)))))
    ]
    via = Selector("item_kind", "via")
    assert forms == [
        via,
        Selector("and", items=(via, pwr)),
        Selector("and", items=(via, pwr, Selector("not", items=(hv,)))),
    ]
    assert normal_form(rule("via_drill")).kind == "hole_size"
    assert normal_form(rule(selector_b=Selector("all"))).selector_b is None


def test_via_drill_all_written_and_lifted(proved: None) -> None:
    original = rule("via_drill", min=300_000)
    (node,) = rule_nodes(original, target=10)[0]
    assert node.find("condition").atoms()[0].value == "A.Type == 'Via'"  # type: ignore[union-attr]
    lifted = lift_rule(node)
    assert isinstance(lifted, Rule) and lifted.selector_a == normal_form(original).selector_a


def test_rule_order() -> None:
    rules = [
        rule(name="a", priority=1),
        rule(name="b", priority=3),
        rule(name="c", priority=2),
        rule(name="z", priority=0),
    ]
    assert [r.name for r in rule_order(rules)] == ["z", "b", "c", "a"]
    tied = [rule(name="zeta", priority=2), rule(name="alpha", priority=2)]
    assert [r.name for r in rule_order(tied)] == ["alpha", "zeta"]


# -- the shipped table


def test_support_keys() -> None:
    assert set(rulemap.SELECTOR_SUPPORT) == set(rulemap.SELECTOR_KEYS) == {
        "net", "netclass", "ref", "item_kind", "and", "or", "not", "glob", "selector_b", "layer_clause"
    }  # fmt: skip


def test_support_matches_probe_results() -> None:
    """Each entry holds exactly the majors whose committed probe file records ``present`` for its key."""
    files = {"9.0.9": 9, "10.0.6": 10}
    expected: dict[str, set[int]] = {key: set() for key in rulemap.SELECTOR_KEYS}
    for name, major in files.items():
        path = PROBES / f"{name}.json"
        probes: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))["probes"]
        for key in rulemap.SELECTOR_KEYS:
            if probes.get(f"dru-cond-{key}") == "present":
                expected[key].add(major)
    assert {k: set(v) for k, v in rulemap.SELECTOR_SUPPORT.items()} == expected
