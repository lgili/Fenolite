# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What a ``silk_clearance`` rule reaches in ``kicad-cli pcb drc`` (hypothesis H-K-SILK-REACH; change c0493,
task 3.3). The bench holds, each in its own row, two footprints' silkscreen lines 0.05 mm apart, a
footprint's silkscreen line 0.05 mm from a track, crossed by a track, 0.05 mm from a via, 0.05 mm from a
zone, 0.05 mm from another footprint's courtyard, 0.05 mm from another footprint's visible fabrication
field, and 0.05 mm from another footprint's pad. Every field but that one is hidden.

A rule with no condition at 0.1 mm reports the silkscreen against the tracks, the zone, the courtyard and
the fabrication field too; the two rules a conversion writes for Altium's Silk To Silk and Silk To Solder
Mask Clearance (``rulemap.SILK_CONDITIONS``) report the silkscreen pair and the pad only. 10.0.6 reports a
pad as ``silk_over_copper``, 9.0.9 as ``silk_overlap``."""

from __future__ import annotations

import dataclasses
from functools import cache

import _kindcases as kc
import _rulebench as rb
import pytest

from fenolite.backends.kicad.lowering import lower_rules
from fenolite.core.coords import Point
from fenolite.model.rules import Rule, RuleSet, Selector

pytestmark = pytest.mark.needs_kicad

MM = rb.MM
X = 15 * MM
LINE = 550_000 + 60_000
"""The outer edge of ``Mini_R_0603``'s silkscreen lines from the footprint's centre."""
GAP = 50_000
MINIMUM = 100_000
SILK = frozenset({"silk_overlap", "silk_over_copper"})
COPPER = ("track", "crossing", "via", "zone")


def _pad_type() -> set[str]:
    """The type of a silkscreen finding against a pad: 10.0.6 ``silk_over_copper``, 9.0.9 ``silk_overlap``."""
    return {"silk_over_copper"} if kc.target() >= 10 else {"silk_overlap"}


def _part(made: rb.Builder, ref: str, at: Point, keep: str = "") -> None:
    placed = made.part(ref, ref, at, target=kc.target(), nets={})
    fields = tuple(dataclasses.replace(f, visible=f.name == keep) for f in placed.fields)
    made.footprints[-1] = dataclasses.replace(placed, fields=fields)


@cache
def _bench() -> rb.Bench:
    made = rb.builder()
    made.silk_pair("silk", ("SS1", "SS2"), gap=GAP, target=kc.target())
    y = made.row()
    _part(made, "TR1", Point(X, y))
    made.track("track", "T", y - LINE - GAP - rb.WIDTH // 2, x0=X - 2 * MM, x1=X + 2 * MM)
    y = made.row()
    _part(made, "TO1", Point(X, y))
    made.track("crossing", "TO", y - 550_000, x0=X - 2 * MM, x1=X + 2 * MM)
    y = made.row()
    _part(made, "VI1", Point(X, y))
    made.via("via", "V", Point(X, y - LINE - GAP - 300_000))
    y = made.row()
    _part(made, "ZN1", Point(X, y))
    made.filled_zone("zone", "Z", y + LINE + GAP, x0=X - 2 * MM, x1=X + 2 * MM, clearance=0)
    y = made.row()  # CB1's courtyard (0.75 mm from its centre) is 0.05 mm from CA1's lower line
    _part(made, "CA1", Point(X, y))
    _part(made, "CB1", Point(X, y + LINE + GAP + 750_000))
    y = made.row()  # FA1's value field (1 mm high at 1.45 mm, stroke 0.15 mm) is 0.05 mm from FB1's line
    _part(made, "FA1", Point(X, y), keep="Value")
    _part(made, "FB1", Point(X, y + 875_000 + GAP + LINE))
    y = made.row()  # PB1's lower line is 0.05 mm above PA1's pad 2 (0.95 mm high)
    _part(made, "PA1", Point(X, y))
    _part(made, "PB1", Point(X + 800_000, y - 475_000 - GAP - LINE))
    return made.build()


def _between(result: kc.Run, refs: tuple[str, str]) -> set[str]:
    assert result.report is not None
    found = rb.violations_between(result.report, result.inside[refs[0]], result.inside[refs[1]])
    return {v.type for v in found if v.type in SILK}


def _of(result: kc.Run, label: str) -> set[str]:
    assert result.report is not None
    return {v.type for v in rb.violations_of(result.report, result.bench.uuids(label)) if v.type in SILK}


def _run(rules: str) -> kc.Run:
    result = kc.run(_bench(), kc.rules_text(rules))
    rb.require_canary(result.report, result.bench)
    return result


@cache
def _plain() -> kc.Run:
    return _run(kc.rule_text("silk", "silk_clearance", MINIMUM))


@cache
def _translated() -> kc.Run:
    made = (("silk_clearance", "silk"), ("silk_mask_clearance", "mask"))
    rules = tuple(
        Rule(id=f"rul_{n}", name=n, kind=k, selector_a=Selector("all"), min=MINIMUM)  # type: ignore[arg-type]
        for k, n in made
    )
    text = lower_rules(RuleSet(id="rst_silk", rules=rules), target=kc.target()).text
    return _run(text.removeprefix("(version 1)\n"))


def test_a_rule_without_a_condition_reaches_every_item() -> None:
    result = _plain()
    assert _between(result, ("SS1", "SS2")) == {"silk_overlap"}
    for label in ("track", "crossing", "zone"):
        assert _of(result, label) == {"silk_overlap"}, label
    assert "silk_overlap" in _between(result, ("CA1", "CB1")), "courtyard"
    assert "silk_overlap" in _between(result, ("FA1", "FB1")), "fabrication field"
    assert _pad_type() <= _between(result, ("PA1", "PB1")), "pad"


def test_translated_silk_rules_judge_silkscreen_and_pads_only() -> None:
    result = _translated()
    assert _between(result, ("SS1", "SS2")) == {"silk_overlap"}, "silkscreen pair"
    assert _between(result, ("PA1", "PB1")) == _pad_type(), "pad"
    for label in COPPER:
        assert not _of(result, label), label
    assert not _between(result, ("CA1", "CB1")), "courtyard"
    assert not _between(result, ("FA1", "FB1")), "fabrication field"
