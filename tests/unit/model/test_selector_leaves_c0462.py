# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The selector leaves ``zone``, ``hole`` and ``pad_type`` (change c0462; capability rules-model, "Zone, hole
and pad-type selectors")."""

from __future__ import annotations

import pytest

from fenolite.dsl import select
from fenolite.dsl.errors import DslError
from fenolite.importer.emit.design import _selector  # pyright: ignore[reportPrivateUsage]
from fenolite.model.rules import (
    PAD_TYPE_OF,
    RuleSubject,
    Selector,
    hole_interval,
    hole_value,
    selector_rank,
)

PAD_1_0 = RuleSubject("pad", net="A", hole=1_000_000, pad_type="th")
PAD_1_2 = RuleSubject("pad", net="A", hole=1_200_000, pad_type="th")
TRACK = RuleSubject("track", net="A", layer="F.Cu")
SMD = RuleSubject("pad", net="A", pad_type="smd")
NPTH = RuleSubject("pad", hole=3_200_000, pad_type="npth")
VIA = RuleSubject("via", net="A", hole=300_000)
FILL = RuleSubject("zone", net="GND", zone="GND_Top")


def test_a_hole_interval() -> None:
    """Scenario "A hole interval"."""
    selector = Selector("hole", "1000001..")
    assert [selector.matches(s) for s in (PAD_1_0, PAD_1_2, TRACK)] == [False, True, False]


@pytest.mark.parametrize(
    ("value", "found"),
    [
        ("..1000000", (True, False, False, True)),
        ("1000000..1000000", (True, False, False, False)),
        ("1000000..1200000", (True, True, False, False)),
        ("300000..", (True, True, True, True)),
    ],
)
def test_hole_bounds_are_closed(value: str, found: tuple[bool, ...]) -> None:
    selector = Selector("hole", value)
    assert tuple(selector.matches(s) for s in (PAD_1_0, PAD_1_2, NPTH, VIA)) == found


@pytest.mark.parametrize(("lo", "hi", "text"), [(1, None, "1.."), (None, 5, "..5"), (2, 2, "2..2")])
def test_hole_value_round_trip(lo: int | None, hi: int | None, text: str) -> None:
    assert hole_value(lo, hi) == text
    assert hole_interval(text) == (lo, hi)


@pytest.mark.parametrize("value", ["..", "1", "a..b", "5..1", "-1..", "1..2..3"])
def test_bad_hole_values(value: str) -> None:
    with pytest.raises(ValueError, match="hole"):
        Selector("hole", value)


def test_pad_type() -> None:
    th = Selector("pad_type", "th")
    assert [th.matches(s) for s in (PAD_1_0, SMD, NPTH, VIA, TRACK)] == [True, False, False, False, False]
    assert Selector("pad_type", "npth").matches(NPTH)
    with pytest.raises(ValueError, match="pad_type"):
        Selector("pad_type", "TH")
    assert PAD_TYPE_OF == {"smd": "smd", "thru_hole": "th", "np_thru_hole": "npth"}


def test_zone_is_a_glob_with_letter_case() -> None:
    assert Selector("zone", "GND_Top").matches(FILL)
    assert Selector("zone", "GND_*").matches(FILL)
    assert not Selector("zone", "gnd_top").matches(FILL)
    assert not Selector("zone", "*").matches(TRACK)


def test_old_selectors_unchanged() -> None:
    """A subject without the new fields evaluates every old selector as before, and the new fields change
    no old leaf."""
    old = (
        Selector("net", "A"),
        Selector("item_kind", "pad"),
        Selector("layer", "F.Cu"),
        Selector("not", items=(Selector("net", "*"),)),
        Selector("and", items=(Selector("net", "A"), Selector("item_kind", "track"))),
    )
    plain = RuleSubject("pad", net="A")
    richer = RuleSubject("pad", net="A", hole=1, pad_type="th", zone="Z")
    for selector in old:
        assert selector.matches(plain) == selector.matches(richer), selector


def test_rank_of_the_new_leaves() -> None:
    for leaf in (Selector("zone", "Z"), Selector("hole", "1.."), Selector("pad_type", "smd")):
        assert selector_rank(leaf) == 1
    assert selector_rank(Selector("ref", "U1")) == 4 and selector_rank(Selector("diff_pair", "D")) == 4


def test_dsl_select() -> None:
    assert select.zone("GND_*").to_model() == Selector("zone", "GND_*")
    assert select.hole(lo=1_000_001).to_model() == Selector("hole", "1000001..")
    assert select.hole(lo=1, hi=2).to_model() == Selector("hole", "1..2")
    assert select.pad_type("npth").to_model() == Selector("pad_type", "npth")
    assert (select.pad_type("th") & select.hole(hi=900_000)).to_model() == Selector(
        "and", items=(Selector("pad_type", "th"), Selector("hole", "..900000"))
    )
    for bad in (lambda: select.hole(), lambda: select.hole(lo=5, hi=1), lambda: select.pad_type("via"),
                lambda: select.zone("a'b"), lambda: select.hole(lo=1.5)):  # type: ignore[arg-type]  # fmt: skip
        with pytest.raises(DslError):
            bad()


def test_the_python_emitter_prints_the_leaves() -> None:
    assert _selector(Selector("zone", "GND_Top"), set()) == 'select.zone("GND_Top")'
    assert _selector(Selector("hole", "1000001.."), set()) == "select.hole(lo=1000001)"
    assert _selector(Selector("hole", "..5"), set()) == "select.hole(hi=5)"
    assert _selector(Selector("pad_type", "smd"), set()) == 'select.pad_type("smd")'
    assert _selector(Selector("zone", "a?"), set()) is None
