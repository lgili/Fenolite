# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.dsl.select`` (capability design-dsl, "Selectors in the DSL"; change c0071)."""

from __future__ import annotations

import pytest

from fenolite.dsl import DslError, Net, Part, select
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
