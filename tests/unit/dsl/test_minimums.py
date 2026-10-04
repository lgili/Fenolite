# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule minimums in the DSL (capability design-dsl, "Rule minimums in the DSL"; design-model, "Identifier
derivation", scenario "Rule ids from the kind and the class"; change c0054)."""

from __future__ import annotations

from typing import get_args

import pytest

from fenolite.core.ids import derived_id
from fenolite.dsl import KEYS, Design, DslError, Net, mm, to_model
from fenolite.dsl.design import MINIMUM_KINDS, MinimumSpec
from fenolite.model import canonical
from fenolite.model.rules import Rule, RuleKind, Selector


def design() -> Design:
    d = Design("minimums")
    d.rules.netclass("PWR", clearance=mm(0.2), nets=(Net("VIN"), Net("GND")))
    return d


def rules(d: Design) -> tuple[Rule, ...]:
    found = to_model(d).rules
    assert found is not None
    return found.rules


def test_keywords_are_the_model_kinds() -> None:
    assert set(MINIMUM_KINDS) == set(get_args(RuleKind)) and len(MINIMUM_KINDS) == 6
    assert KEYS["rule"] == ("rul", "rule:<kind>[:<net class>]")


def test_no_minimum_gives_an_empty_rule_set() -> None:
    assert rules(design()) == ()


def test_board_and_class_minimums_in_the_model() -> None:
    d = design()
    d.rules.minimum(track_width=mm(0.6), netclass="PWR")
    d.rules.minimum(clearance=mm(0.15), track_width="0.25mm")
    assert d.rules.minimums[("track_width", "PWR")] == MinimumSpec("track_width", "PWR", 600_000)
    clearance, width, pwr = rules(d)
    assert (clearance.name, clearance.kind) == ("min_clearance", "clearance")
    assert clearance.selector_a == Selector("all")
    assert (clearance.min, clearance.priority) == (150_000, 0)
    assert (width.name, width.kind) == ("min_track_width", "track_width")
    assert (width.selector_a, width.min, width.priority) == (Selector("all"), 250_000, 0)
    assert (pwr.name, pwr.kind, pwr.min, pwr.priority) == ("min_track_width_PWR", "track_width", 600_000, 1)
    assert pwr.selector_a == Selector("netclass", "PWR")
    assert pwr.id == derived_id("rul", "dsl", "rule:track_width:PWR")
    for rule in (clearance, width, pwr):
        assert rule.severity == "error" and rule.selector_b is None and rule.layers == ()
        assert rule.opt is None and rule.max is None and rule.provenance is None


def test_every_kind_in_kind_order() -> None:
    d = design()
    d.rules.minimum(
        edge_clearance=mm(0.3),
        hole_size=mm(0.3),
        via_drill=mm(0.3),
        via_diameter=mm(0.6),
        track_width=mm(0.2),
        clearance=mm(0.2),
    )
    assert [r.kind for r in rules(d)] == list(MINIMUM_KINDS)


def test_classes_in_name_order() -> None:
    d = design()
    d.rules.netclass("HV", nets=(Net("MAINS"),))
    d.rules.minimum(clearance=mm(0.3), netclass="PWR")
    d.rules.minimum(clearance=mm(2), netclass="HV")
    d.rules.minimum(clearance=mm(0.2))
    assert [r.name for r in rules(d)] == ["min_clearance", "min_clearance_HV", "min_clearance_PWR"]


def test_call_order_does_not_matter() -> None:
    first, second = design(), design()
    first.rules.minimum(clearance=mm(0.15))
    first.rules.minimum(track_width=mm(0.5), netclass="PWR")
    second.rules.minimum(track_width=mm(0.5), netclass="PWR")
    second.rules.minimum(clearance=mm(0.15))
    texts = [canonical.dump_texts(to_model(d))["rules.json"] for d in (first, second)]
    assert texts[0] == texts[1] and "min_track_width_PWR" in texts[0]


def test_ids_from_the_kind_and_the_class() -> None:
    first, second = design(), design()
    first.rules.minimum(clearance=mm(0.15))
    first.rules.minimum(track_width=mm(0.5), netclass="PWR")
    second.rules.minimum(track_width=mm(0.5), netclass="PWR")
    second.rules.minimum(clearance=mm(0.15))
    wanted = [derived_id("rul", "dsl", "rule:clearance"), derived_id("rul", "dsl", "rule:track_width:PWR")]
    assert [r.id for r in rules(first)] == [r.id for r in rules(second)] == wanted


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({}, "at least one length"),
        ({"clearance": 0.2}, "has no unit"),
        ({"clearance": "0.2"}, "clearance"),
        ({"clearance": mm(0)}, "must be above 0"),
        ({"via_drill": mm(-1)}, "must be above 0"),
        ({"clearance": mm(0.2), "netclass": "HV"}, "'HV' is not a declared net class"),
        ({"clearance": mm(0.3)}, "clearance is declared twice for the board"),
        ({"track_width": mm(0.3), "netclass": "PWR"}, "track_width is declared twice for net class PWR"),
        ({"edge_clearance": mm(0.3), "clearance": mm(0.3)}, "declared twice"),
    ],
)
def test_refused_calls(arguments: dict[str, object], message: str) -> None:
    d = design()
    d.rules.minimum(clearance=mm(0.2))
    d.rules.minimum(track_width=mm(0.5), netclass="PWR")
    before = dict(d.rules.minimums)
    with pytest.raises(DslError, match=message) as error:
        d.rules.minimum(**arguments)  # type: ignore[arg-type]
    assert "minimum()" in str(error.value)
    assert d.rules.minimums == before
