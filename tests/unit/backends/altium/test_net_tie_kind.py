# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A net-tie component of a PCB document carries one net-tie group (change c0420, N1;
``docs/formats/altium/pcb-records.md``, "Component kind"). ``COMPONENTKIND`` 3 (net tie in the BOM) and 4
(net tie) give the group of the component's distinct pad numbers in pad order; any other kind, or fewer than
two numbers, none. The records are authored here."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.backends.altium.adapter.board import net_ties
from fenolite.backends.altium.read.pcb import ComponentRecord
from fenolite.backends.altium.read.pcbprops import PropertyRecord
from fenolite.core.coords import Point, Size
from fenolite.model.board import Pad


def _component(kind: str | None) -> ComponentRecord:
    fields = (("PATTERN", "TIE"),) + ((("COMPONENTKIND", kind),) if kind is not None else ())
    return ComponentRecord(
        PropertyRecord(b"", fields), "TOP", Fraction(0), Fraction(0), 0.0, "TIE", False, True, False,
        None, None, None, None, None, None, None,
    )  # fmt: skip


def _pads(*numbers: str) -> tuple[Pad, ...]:
    return tuple(
        Pad(
            id=f"pad-{i}", number=n, shape="rect", size=Size(300_000, 300_000), position=Point(i * 500_000, 0)
        )
        for i, n in enumerate(numbers)
    )


@pytest.mark.parametrize("kind", ["3", "4"])
def test_a_net_tie_kind_gives_one_group(kind: str) -> None:
    assert net_ties(_component(kind), _pads("2", "1", "", "2")) == (("2", "1"),)


@pytest.mark.parametrize("kind", [None, "0", "1", "2", "5", "6"])
def test_other_kinds_give_none(kind: str | None) -> None:
    assert net_ties(_component(kind), _pads("1", "2")) == ()


def test_one_number_gives_none() -> None:
    assert net_ties(_component("4"), _pads("1", "1")) == ()


@pytest.mark.parametrize(
    ("groups", "differs"),
    [
        ((), False),
        ((("1", "2"),), False),
        ((("2", "1"),), False),
        ((("1",),), True),
        ((("1", "2"), ("3", "4")), True),
    ],
)
def test_groups_that_a_net_tie_component_does_not_say_differ(
    groups: tuple[tuple[str, ...], ...], differs: bool
) -> None:
    """Altium marks the whole component: only one group of every distinct pad number is said by the mark;
    every other set of groups is counted changed (change c0420, N1)."""
    from fenolite.backends.altium.lower import net_tie_differs

    pads = _pads("1", "2", "") if len(groups) < 2 else _pads("1", "2", "3", "4")
    assert net_tie_differs(groups, pads) is differs
