# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``select.no_net()``, the items without a net (capability design-dsl, "Selector of items without a net";
change c0409, B7): the model selector ``not(net "*")`` of the frozen ops, what it matches, and the KiCad
condition it is written as and read back from (``docs/formats/kicad/rules.md``, ``H-K-DRU-NONET``)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.rulemap import condition_text, parse_condition
from fenolite.dsl import select
from fenolite.model.rules import NO_NET, Rule, RuleSubject, Selector


def _rule(selector: Selector) -> Rule:
    return Rule(
        id="rul_0c409000-0000-4000-8000-0000000000b7", name="netless", kind="clearance",
        selector_a=selector, min=300_000,
    )  # fmt: skip


def test_the_dsl_name_gives_the_selector() -> None:
    assert select.no_net().to_model() == NO_NET == Selector("not", items=(Selector("net", "*"),))
    assert (select.no_net() & select.item("track")).to_model() == Selector(
        "and", items=(NO_NET, Selector("item_kind", "track"))
    )


def test_matches_the_items_without_a_net() -> None:
    assert NO_NET.matches(RuleSubject("track"))
    assert not NO_NET.matches(RuleSubject("track", net="GND"))
    assert not NO_NET.matches(RuleSubject("pad", net=""))
    assert not Selector("not", items=(NO_NET,)).matches(RuleSubject("pad"))


@pytest.mark.parametrize("kind", ["courtyard_clearance", "silk_clearance"])
def test_refused_where_no_net_selector_is_taken(kind: str) -> None:
    rule = Rule(id="rul_0c409000-0000-4000-8000-0000000000b8", name="x", kind=kind,  # type: ignore[arg-type]
                selector_a=NO_NET, min=300_000)  # fmt: skip
    _, issues = condition_text(rule, target=10)
    assert [issue.code for issue in issues] == ["rules.unsupported-selector"]


@pytest.mark.parametrize("target", [9, 10])
def test_written_as_the_empty_net_name(target: int) -> None:
    text, issues = condition_text(_rule(NO_NET), target=target)
    assert issues == () and text == "A.NetName == ''"


def test_read_back_from_the_condition() -> None:
    assert parse_condition("A.NetName == ''") == (NO_NET, None)
