# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Clearance rules lowered into a Specctra design file in KiCad's order (change c0403, F8): the governing
rule of a class pair, the last in ``rule_precedence`` order, sets the pair's value, and a class against
itself may go below the class's own clearance. Hermetic: an authored board of four classes built through
the model API."""

from __future__ import annotations

import dataclasses

from _placed import Part, design_of, mm
from _specctra import DEFAULTS, Bench, bench

from fenolite.backends.specctra.dsn import DsnResult
from fenolite.backends.specctra.lexer import SNode, dumps, parse
from fenolite.core.ids import derived_id
from fenolite.model.circuit import NetClass
from fenolite.model.rules import Rule, RuleSet, Selector

CLASSES = ("CTRL", "PHASE_U", "PHASE_V")


def netclass(name: str, clearance: int) -> NetClass:
    return NetClass(
        id=derived_id("cls", "test", f"rule-order:{name}"),
        name=name,
        clearance=clearance,
        track_width=DEFAULTS.width,
    )


def board(*rules: Rule, phase_u: int = mm(0.2), unclassed: bool = False) -> Bench:
    """Two nets of ``PHASE_U`` (clearance ``phase_u``), one of ``CTRL`` and one of ``PHASE_V`` (0.2 mm), each
    between two resistors; with ``unclassed`` a fifth net ``N`` has no class."""
    nets = {"U1": "PHASE_U", "U2": "PHASE_U", "C1": "CTRL", "V1": "PHASE_V"}
    names = [*nets, *(("N",) if unclassed else ())]
    parts = [
        Part(f"R{2 * i + side + 1}", "Mini_R_0603", 4 + 5 * i, 4 + 8 * side, nets={"1": name, "2": name})
        for i, name in enumerate(names)
        for side in (0, 1)
    ]
    classes = tuple(netclass(name, phase_u if name == "PHASE_U" else mm(0.2)) for name in CLASSES)
    design = design_of(*parts, classes=classes, class_of=nets)
    if rules:
        design = dataclasses.replace(
            design, rules=RuleSet(id=derived_id("rst", "test", "rule-order"), rules=rules)
        )
    return bench(design, selected=tuple(names))


def rule(name: str, a: Selector, b: Selector | None, minimum: int, priority: int = 0) -> Rule:
    return Rule(
        id=derived_id("rul", "test", f"rule-order:{name}"),
        name=name,
        kind="clearance",
        selector_a=a,
        selector_b=b,
        min=minimum,
        priority=priority,
    )


def cls(name: str) -> Selector:
    return Selector("netclass", name)


def flat(node: SNode) -> str:
    return " ".join(dumps(node).split()).replace("( ", "(").replace(" )", ")")


def network(result: DsnResult, head: str) -> list[str]:
    node = parse(result.text).first("network")
    assert node is not None
    return [flat(child) for child in node.lists if child.head == head]


def class_clearance(result: DsnResult, name: str) -> str:
    (found,) = [text for text in network(result, "class") if text.split()[1] == name]
    return found.rsplit("(clearance ", 1)[1].split(")")[0]


def widened(result: DsnResult) -> list[str]:
    return [i.message for i in result.issues if i.code == "specctra.rule-widened"]


def test_higher_priority_pair_rule_governs_a_one_sided_rule() -> None:
    """(a) A one-sided 3 mm rule on ``PHASE_U`` and a higher-priority (CTRL, PHASE_U) rule of 1.85 mm: the
    pair takes 1.85 mm, every other pair of ``PHASE_U`` 3 mm (before c0403: 3 mm everywhere, the maximum)."""
    result = board(
        rule("phase-any", cls("PHASE_U"), None, mm(3), priority=2),
        rule("ctrl-phase", cls("CTRL"), cls("PHASE_U"), mm(1.85), priority=1),
    ).write()
    assert network(result, "class_class") == [
        "(class_class (classes CTRL PHASE_U) (rule (clearance 1850)))",
        "(class_class (classes PHASE_U PHASE_V) (rule (clearance 3000)))",
    ]
    assert widened(result) == []
    # the one-sided rule governs when it comes later
    later = board(
        rule("phase-any", cls("PHASE_U"), None, mm(3), priority=1),
        rule("ctrl-phase", cls("CTRL"), cls("PHASE_U"), mm(1.85), priority=2),
    ).write()
    assert "(class_class (classes CTRL PHASE_U) (rule (clearance 3000)))" in network(later, "class_class")


def test_self_rule_lowers_a_class_and_keeps_it_from_the_others() -> None:
    """(b) A (PHASE_U, PHASE_U) rule of 0.3 mm on a class of 3 mm: the class's rule says 0.3 mm, and a
    ``class_class`` per other class keeps 3 mm (before c0403: 3 mm, the class's value a floor)."""
    result = board(rule("phase-self", cls("PHASE_U"), cls("PHASE_U"), mm(0.3)), phase_u=mm(3)).write()
    assert class_clearance(result, "PHASE_U") == "300"
    assert class_clearance(result, "CTRL") == "200"
    assert network(result, "class_class") == [
        "(class_class (classes CTRL PHASE_U) (rule (clearance 3000)))",
        "(class_class (classes PHASE_U PHASE_V) (rule (clearance 3000)))",
    ]
    assert widened(result) == []


def test_self_rule_keeps_a_governing_pair_rule() -> None:
    """A pair that a rule governs keeps that rule's value when its class is lowered against itself."""
    result = board(
        rule("phase-self", cls("PHASE_U"), cls("PHASE_U"), mm(0.3)),
        rule("phase-ctrl", cls("PHASE_U"), cls("CTRL"), mm(1)),
        phase_u=mm(3),
    ).write()
    assert class_clearance(result, "PHASE_U") == "300"
    assert network(result, "class_class") == [
        "(class_class (classes CTRL PHASE_U) (rule (clearance 1000)))",
        "(class_class (classes PHASE_U PHASE_V) (rule (clearance 3000)))",
    ]


def test_self_rule_with_nets_without_a_class_keeps_the_floor() -> None:
    """(c) With a net without a class, which would take the lower value against ``PHASE_U``, the class keeps
    3 mm and one ``specctra.rule-widened`` names the rule and the class."""
    result = board(
        rule("phase-self", cls("PHASE_U"), cls("PHASE_U"), mm(0.3)), phase_u=mm(3), unclassed=True
    ).write()
    assert class_clearance(result, "PHASE_U") == "3000"
    assert network(result, "class_class") == []
    (message,) = widened(result)
    assert "'phase-self'" in message and "PHASE_U" in message and "without a class" in message
    assert "asks 0.3 mm" in message and "3 mm is written" in message


def test_board_wide_rule_stays_a_floor_for_a_self_rule() -> None:
    """A board-wide rule stays a floor: the self rule is written at the floor, with ``rule-widened``."""
    result = board(
        rule("phase-self", cls("PHASE_U"), cls("PHASE_U"), mm(0.3)),
        rule("wide", Selector("all"), None, mm(0.5)),
        phase_u=mm(3),
    ).write()
    assert class_clearance(result, "PHASE_U") == "500"
    assert class_clearance(result, "CTRL") == "500"
    assert network(result, "class_class") == [
        "(class_class (classes CTRL PHASE_U) (rule (clearance 3000)))",
        "(class_class (classes PHASE_U PHASE_V) (rule (clearance 3000)))",
    ]
    (message,) = widened(result)
    assert "'phase-self'" in message and "PHASE_U" in message and "0.5 mm is written" in message


def test_equal_priorities_are_ordered_by_name_whatever_the_input_order() -> None:
    """(d) Two rules of one priority on one pair: the later by name governs (``beta``, 0.5 mm, below
    ``alpha``'s 1 mm), and the file does not depend on the order of the design's rules."""
    alpha = rule("alpha", cls("CTRL"), cls("PHASE_U"), mm(1))
    beta = rule("beta", cls("PHASE_U"), cls("CTRL"), mm(0.5))
    first, second = board(alpha, beta).write(), board(beta, alpha).write()
    assert first.text == second.text and first.issues == second.issues
    assert network(first, "class_class") == ["(class_class (classes CTRL PHASE_U) (rule (clearance 500)))"]
