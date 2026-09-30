# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import random

import pytest

from fenolite.core.ids import new_id
from fenolite.model import Rule, RuleSubject, Selector

PWR_TRACK = RuleSubject(item_kind="track", net="PWR_3V3", netclass="power", ref=None, layer="F.Cu")
SIG_VIA = RuleSubject(item_kind="via", net="SDA", netclass="default", ref=None, layer="B.Cu")
U1_PAD = RuleSubject(item_kind="pad", net="GND", netclass="default", ref="U1", layer="F.Cu")


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        (Selector("all"), (True, True, True)),
        (Selector("net", "PWR_*"), (True, False, False)),
        (Selector("netclass", "default"), (False, True, True)),
        (Selector("ref", "U*"), (False, False, True)),
        (Selector("layer", "B.Cu"), (False, True, False)),
        (Selector("item_kind", "via"), (False, True, False)),
        (
            Selector("and", items=(Selector("layer", "F.Cu"), Selector("item_kind", "pad"))),
            (False, False, True),
        ),
        (Selector("or", items=(Selector("net", "SDA"), Selector("net", "GND"))), (False, True, True)),
        (Selector("not", items=(Selector("item_kind", "track"),)), (False, True, True)),
    ],
)
def test_selector_truth_table(selector: Selector, expected: tuple[bool, bool, bool]) -> None:
    assert tuple(selector.matches(s) for s in (PWR_TRACK, SIG_VIA, U1_PAD)) == expected


@pytest.mark.parametrize(
    "build",
    [
        lambda: Selector("and", items=(Selector("all"),)),
        lambda: Selector("not"),
        lambda: Selector("net"),
        lambda: Selector("all", items=(Selector("all"), Selector("all"))),
    ],
)
def test_invalid_selectors(build: object) -> None:
    with pytest.raises(ValueError):
        build()  # type: ignore[operator]


def test_rule_fields() -> None:
    rule = Rule(
        id=new_id("rul", random.Random(1)),
        name="hv",
        kind="clearance",
        selector_a=Selector("netclass", "mains"),
        selector_b=Selector("netclass", "isolated_lv"),
        min=2_500_000,
        priority=1,
    )
    assert rule.severity == "error" and rule.min == 2_500_000
