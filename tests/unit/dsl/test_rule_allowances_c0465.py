# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Change c0465: ``design.rules.rule()`` takes the allowance kinds ``short`` and ``antenna`` (design-dsl,
"Short and antenna rules in the DSL")."""

from __future__ import annotations

from typing import Any

import pytest

from fenolite.dsl import Design, DslError, mm, select, to_model
from fenolite.importer.emit.design import _limits_said  # pyright: ignore[reportPrivateUsage]
from fenolite.model.rules import Rule, Selector


def _rules(d: Design) -> dict[str, Rule]:
    rules = to_model(d).rules
    assert rules is not None
    return {rule.name: rule for rule in rules.rules}


def test_declaring_an_allowance() -> None:
    d = Design("allow")
    d.rules.rule("GND_JOIN", "short", where=select.net("AGND"), between=select.net("DGND"), severity="ignore")
    d.rules.rule("SIG_STUB", "antenna", where=select.net("SIG"), max=mm(1.5))
    d.rules.rule("NO_STUB", "antenna", max=mm(0))
    rules = _rules(d)
    join, stub, none = rules["GND_JOIN"], rules["SIG_STUB"], rules["NO_STUB"]
    assert (join.kind, join.selector_a, join.selector_b, join.severity) == (
        "short",
        Selector("net", "AGND"),
        Selector("net", "DGND"),
        "ignore",
    )
    assert (join.min, join.opt, join.max) == (None, None, None)
    assert (stub.kind, stub.selector_a, stub.selector_b, stub.max) == (
        "antenna",
        Selector("net", "SIG"),
        None,
        1_500_000,
    )
    assert (none.max, none.severity) == (0, "error")


@pytest.mark.parametrize(
    ("kind", "fields", "says"),
    [
        ("short", {"between": select.ALL, "min": mm(0.1)}, "takes no limit"),
        ("short", {"between": select.ALL, "max": mm(0.1)}, "takes no limit"),
        ("short", {}, "needs between"),
        ("antenna", {}, "max alone"),
        ("antenna", {"min": mm(0.1), "max": mm(1)}, "max alone"),
        ("antenna", {"opt": mm(1), "max": mm(1)}, "max alone"),
        ("antenna", {"max": mm(-0.1)}, "must not be negative"),
        ("antenna", {"between": select.ALL, "max": mm(1)}, "between is taken by"),
    ],
)
def test_refused_allowances(kind: str, fields: dict[str, Any], says: str) -> None:
    d = Design("allow")
    with pytest.raises(DslError, match=says):
        d.rules.rule("X", kind, where=select.ALL, **fields)


def test_the_emitter_writes_what_the_builder_takes() -> None:
    """An imported rule of either kind is written as a ``rule()`` call exactly when the builder takes it."""
    rid = "rul_00000000-0000-4000-8000-0000000c0465"
    short = Rule(id=rid, name="s", kind="short", selector_a=Selector("all"), selector_b=Selector("all"))
    antenna = Rule(id=rid, name="a", kind="antenna", selector_a=Selector("net", "SIG"), max=0)
    assert _limits_said(short) and _limits_said(antenna)
