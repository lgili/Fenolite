# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The two-terminal families ``chip`` and ``molded`` (change c0260, requirement "Pad numbering and
orientation" for two-terminals)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fenolite.catalog.footprints import generate
from fenolite.catalog.footprints.lands import LANDS
from fenolite.catalog.footprints.record import Package

Record = Callable[..., Package]


def test_chip_is_calculated_with_lands_1(record: Record) -> None:
    result = generate(record("chip0603"))
    fp = result.footprint
    assert fp is not None and result.land.source == "calculated" and result.land.evidence == "INFERRED"
    goals = LANDS[1].goals["chip"]
    # Z = L.max + 2 toe, G = L.min - 2 T.max - 2 heel, X = W.max + 2 side (lands/1 is on the 10 µm grid).
    z = 1_700_000 + 2 * goals.toe
    g = 1_500_000 - 2 * 400_000 - 2 * goals.heel
    x = 900_000 + 2 * goals.side
    assert (result.land.z, result.land.g, result.land.x) == (z, g, x)
    one, two = fp.pads
    assert (one.number, two.number) == ("1", "2")
    assert one.position.x == -(z + g) // 4 and two.position.x == (z + g) // 4 and one.position.y == 0
    assert (one.size.w, one.size.h) == ((z - g) // 2, x)
    assert one.shape == "roundrect" and one.corner_ratio == 100_000 * 1_000_000 // min(
        one.size.w, one.size.h
    )  # radius capped at 0.1 mm
    assert fp.kind == "smd" and fp.lib_id == "Local:CHIP0603_B1.6x0.8"
    assert not [g for g in fp.graphics if "polarity" in g.id]  # polarity = "none"
    assert result.stamp == "chip/1 lands/1 drawing/1 nominal"


def test_polarized_molded_puts_the_cathode_on_pad_1(record: Record) -> None:
    result = generate(record("sod123"))
    fp = result.footprint
    assert fp is not None
    one = next(p for p in fp.pads if p.number == "1")
    two = next(p for p in fp.pads if p.number == "2")
    assert one.position.x < 0 < two.position.x
    fab_bars = [g for g in fp.graphics if g.layer == "F.Fab" and g.points[0].x == g.points[1].x]
    body_x0 = -2_650_000 // 2
    assert any(bar.points[0].x == body_x0 + 2_650_000 // 5 for bar in fab_bars)
    silk_bars = [g for g in fp.graphics if g.layer == "F.SilkS" and g.points[0].x == g.points[1].x]
    assert any(bar.points[0].x < one.position.x - one.size.w // 2 for bar in silk_bars)


def test_molded_span_shorter_than_the_body(record: Record) -> None:
    result = generate(record("sod123", lambda raw: raw.update(span="2.0mm..2.2mm")))
    assert result.footprint is None and [i.code for i in result.issues] == ["package.dimensions-inconsistent"]


def test_terminal_longer_than_half_the_chip(record: Record) -> None:
    def long_band(raw: dict[str, Any]) -> None:
        raw["terminal"] = {"length": "0.10mm..0.80mm"}

    result = generate(record("chip0603", long_band))
    assert result.footprint is None and [i.code for i in result.issues] == ["package.dimensions-inconsistent"]
