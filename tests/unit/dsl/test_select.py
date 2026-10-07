# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.dsl.select`` (capability design-dsl, "Selectors in the DSL"; change c0071)."""

from __future__ import annotations

import pytest

from fenolite.core.ids import derived_id
from fenolite.dsl import Design, DslError, Net, Part, mm, select, to_model
from fenolite.model.rules import Selector


def test_compound_selector() -> None:
    made = (select.net("A") | select.net("B")) & ~select.item("via")
    assert made.to_model() == Selector(
        "and",
        items=(
            Selector("or", items=(Selector("net", "A"), Selector("net", "B"))),
            Selector("not", items=(Selector("item_kind", "via"),)),
        ),
    )


def test_same_op_is_flattened() -> None:
    made = select.net("A") | select.net("B") | select.net("C")
    assert made.to_model() == Selector("or", items=tuple(Selector("net", n) for n in "ABC"))
    assert (select.net("A") & select.ref("U1")).to_model() == (select.net("A") & select.ref("U1")).to_model()


def test_objects_are_stored_by_name() -> None:
    assert select.net(Net("VBUS")).to_model() == Selector("net", "VBUS")
    assert select.ref(Part("U7", "Mini:Mini_R")).to_model() == Selector("ref", "U7")
    assert select.netclass("PWR_*").to_model() == Selector("netclass", "PWR_*")


@pytest.mark.parametrize(
    "made",
    [
        lambda: select.ALL & select.net("A"),
        lambda: select.net("A") | select.ALL,
        lambda: ~select.ALL,
        lambda: select.net(""),
        lambda: select.ref(" U1"),
        lambda: select.item("footprint"),
        lambda: select.net("A") & "B",
    ],
)
def test_selector_errors(made: object) -> None:
    with pytest.raises(DslError):
        made()  # type: ignore[operator]


def test_select_is_exported() -> None:
    import fenolite.dsl as dsl

    assert dsl.select is select and "select" in dsl.__all__


# --- area selectors (change c0103) ---------------------------------------------------------------------


def _areas() -> Design:
    made = Design("areas")
    made.board(mm(50), mm(30))
    return made


SQUARE = [(mm(0), mm(0)), (mm(10), mm(0)), (mm(10), mm(10)), (mm(0), mm(10))]


def test_neck_down_rule_in_the_model() -> None:
    """Scenario "Neck-down rule in the model": a ``RuleArea`` is stored by its name."""
    d = _areas()
    bga = d.rule_area("BGA", SQUARE)
    d.rules.rule("neck", "track_width", where=select.area(bga), min=mm(0.1))
    rules = to_model(d).rules
    assert rules is not None
    (rule,) = rules.rules
    assert rule.selector_a == Selector("area", "BGA")
    assert rule.id == derived_id("rul", "dsl", "rule:named:neck")


def test_high_voltage_pair() -> None:
    """Scenario "High-voltage pair"."""
    made = (select.area("HV") & select.item("track")).to_model()
    assert made == Selector("and", items=(Selector("area", "HV"), Selector("item_kind", "track")))
    assert (~select.area("H*")).to_model() == Selector("not", items=(Selector("area", "H*"),))


@pytest.mark.parametrize("name", ["", "H'V", 'H"V', "H?", "H[1]", " HV", 7])
def test_refused_area_names(name: object) -> None:
    """Scenario "Refused names"."""
    with pytest.raises(DslError):
        select.area(name)  # type: ignore[arg-type]


def test_no_check_at_the_call() -> None:
    """Scenario "No check at the call": an area may be drawn in KiCad, so the build checks the name."""
    d = _areas()
    d.rules.rule("far", "clearance", where=select.area("NOPE"), between=select.area("ALSO"), min=mm(1))
    rules = to_model(d).rules
    assert rules is not None
    (rule,) = rules.rules
    assert (rule.selector_a, rule.selector_b) == (Selector("area", "NOPE"), Selector("area", "ALSO"))
