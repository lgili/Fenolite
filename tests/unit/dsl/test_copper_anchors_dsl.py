# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper anchors in the DSL (capability design-dsl, "Copper anchors in the DSL"; change c0111): what
``part.at`` and ``part.pad(n).at`` record, where they are accepted, and what is refused at the call."""

from __future__ import annotations

import dataclasses

import pytest
from _buildhelp import blink

import fenolite.dsl as dsl
from fenolite.core.coords import Point
from fenolite.dsl import (
    BOARD_ORIGIN,
    Anchor,
    AnchorRef,
    ArcStep,
    Design,
    DslError,
    Net,
    PadEnd,
    Part,
    StitchIntent,
    TrackIntent,
    ViaIntent,
    ViaStep,
    arc_to,
    copper,
    mm,
    to_model,
    via_step,
)
from fenolite.model import canonical

SIZES = {"diameter": mm(0.6), "drill": mm(0.3)}


def _parts(design: Design) -> tuple[Part, Part, Net, Net]:
    return design.parts["U1"], design.parts["R1"], design.nets["VIN"], design.nets["GND"]


def test_anchors_recorded() -> None:
    """Scenario "Anchors recorded"."""
    design = blink()
    u1, r1, vin, _ = _parts(design)
    design.via("fan9", u1.pad(9).at(mm(0), mm(1)), net=vin, **SIZES)
    design.track("stub", r1.pad(2), r1.pad(2).at(mm(1)), width=mm(0.3))
    stub, via = copper(design)[-1], copper(design)[0]
    assert via == ViaIntent("fan9", Anchor("U1", "9", None, Point(0, 1_000_000)), "VIN", 600_000, 300_000)
    assert stub == TrackIntent(
        "stub", (PadEnd("R1", "2", None), Anchor("R1", "2", None, Point(1_000_000, 0))), "F.Cu", 300_000, None
    )


def test_what_at_returns() -> None:
    design = blink()
    u1, _, _, _ = _parts(design)
    assert u1.at() == AnchorRef(u1, None, None, Point(0, 0))
    assert u1.at(dy=mm(2)) == AnchorRef(u1, None, None, Point(0, 2_000_000))
    assert u1.at("1mm", "-0.5mm").offset == Point(1_000_000, -500_000), "lengths as the DSL reads them"
    ref = u1.pad(33, index=1).at(mm(-1), mm(0.25))
    assert ref == AnchorRef(u1, "33", 1, Point(-1_000_000, 250_000)), "the number and index of the reference"
    assert ref.component == "U1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.offset = Point(0, 0)  # type: ignore[misc]


def test_a_thermal_stitch_recorded() -> None:
    """Scenario "A thermal stitch recorded"."""
    design = blink()
    u1, _, _, gnd = _parts(design)
    design.stitch("ep", net=gnd, pitch=mm(1), region=u1.pad(33), margin=mm(0.1), **SIZES)
    (intent,) = copper(design)
    assert isinstance(intent, StitchIntent)
    assert intent.region == PadEnd("U1", "33", None) and intent.along == ()
    assert intent.origin == BOARD_ORIGIN, "the default origin, which the stitch rule reads as the pad"
    assert (intent.pitch, intent.margin, intent.diameter, intent.drill) == (
        1_000_000,
        100_000,
        600_000,
        300_000,
    )


def test_anchors_in_a_stitch() -> None:
    design = blink()
    u1, r1, _, gnd = _parts(design)
    design.stitch(
        "line", net=gnd, pitch=mm(2), along=(u1.at(mm(-5)), (mm(40), mm(5)), r1.pad(1).at()), **SIZES
    )
    ring = (u1.at(mm(-5), mm(-5)), u1.at(mm(5), mm(-5)), u1.at(mm(5), mm(5)), (mm(1), mm(2)))
    design.stitch("ring", net=gnd, pitch=mm(1), region=ring, origin=u1.at(), **SIZES)
    design.stitch("ep", net=gnd, pitch=mm(1), region=u1.pad(10), origin=u1.pad(10).at(mm(0.5)), **SIZES)
    ep, line, ringed = copper(design)
    assert (
        isinstance(ep, StitchIntent) and isinstance(line, StitchIntent) and isinstance(ringed, StitchIntent)
    )
    assert line.along == (
        Anchor("U1", None, None, Point(-5_000_000, 0)),
        Point(BOARD_ORIGIN.x + 40_000_000, BOARD_ORIGIN.y + 5_000_000),
        Anchor("R1", "1", None, Point(0, 0)),
    )
    assert ringed.origin == Anchor("U1", None, None, Point(0, 0))
    assert isinstance(ringed.region, tuple) and ringed.region[0] == Anchor(
        "U1", None, None, Point(-5_000_000, -5_000_000)
    )
    assert ringed.region[3] == Point(BOARD_ORIGIN.x + 1_000_000, BOARD_ORIGIN.y + 2_000_000)
    assert ep.region == PadEnd("U1", "10", None) and ep.origin == Anchor("U1", "10", None, Point(500_000, 0))


def test_one_argument_points_and_earlier_forms() -> None:
    """Scenario "One-argument points and earlier forms"."""
    design = blink()
    u1, _, _, gnd = _parts(design)
    steps = (
        via_step(mm(36), mm(14), to="B.Cu"),
        via_step((mm(36), mm(14)), to="B.Cu"),
        via_step(u1.at(mm(2)), to="B.Cu"),
    )
    for n, step in enumerate(steps):
        design.track(f"t{n}", (mm(30), mm(14)), step, (mm(40), mm(20)), net=gnd)
    found = [intent.path[1] for intent in copper(design) if isinstance(intent, TrackIntent)]
    assert found[0] == found[1] == ViaStep(Point(136_000_000, 114_000_000), "B.Cu", None, None)
    assert isinstance(found[2], ViaStep)
    assert found[2].at == Anchor("U1", None, None, Point(2_000_000, 0))
    assert (found[2].layer, found[2].kind) == ("B.Cu", "through")
    design.via("pair", (mm(5), mm(6)), net=gnd)
    design.via("two", mm(5), mm(6), net=gnd)
    pair, two = (i for i in copper(design) if isinstance(i, ViaIntent))
    assert pair.at == two.at == Point(BOARD_ORIGIN.x + 5_000_000, BOARD_ORIGIN.y + 6_000_000)


def test_anchors_in_an_arc_step() -> None:
    design = blink()
    u1, _, _, gnd = _parts(design)
    design.track(
        "bend", u1.at(mm(6)), arc_to(u1.at(mm(7), mm(1)), (mm(30), mm(20))), (mm(31), mm(21)), net=gnd
    )
    (intent,) = copper(design)
    assert isinstance(intent, TrackIntent)
    assert intent.path[0] == Anchor("U1", None, None, Point(6_000_000, 0))
    assert intent.path[1] == ArcStep(
        Anchor("U1", None, None, Point(7_000_000, 1_000_000)),
        Point(BOARD_ORIGIN.x + 30_000_000, BOARD_ORIGIN.y + 20_000_000),
    )


def test_a_blind_via_at_an_anchor() -> None:
    """Scenario "A blind via at an anchor"."""
    design = blink()
    u1, _, vin, _ = _parts(design)
    design.via("esc", u1.pad(9).at(mm(0), mm(1)), net=vin, kind="blind", layers=("F.Cu", "In1.Cu"))
    (intent,) = copper(design)
    assert isinstance(intent, ViaIntent)
    assert intent.at == Anchor("U1", "9", None, Point(0, 1_000_000))
    assert intent.kind == "blind" and intent.layers == ("F.Cu", "In1.Cu")
    step = via_step(u1.pad(9).at(), to="In1.Cu", kind="micro", **SIZES)
    assert (step.kind, step.diameter, step.drill) == ("micro", 600_000, 300_000)


def test_refused_anchor_calls() -> None:
    """Scenario "Refused anchor calls", and the other refusals of the requirement."""
    design = blink()
    u1, r1, _, gnd = _parts(design)
    with pytest.raises(DslError, match="unit"):
        u1.at(1, 2)
    with pytest.raises(DslError, match="unit"):
        u1.pad(1).at(mm(1), 2.5)
    with pytest.raises(DslError, match=r"\.at\(\)"):
        design.via("v", u1.pad(1), net=gnd)
    with pytest.raises(DslError, match="one argument or as two lengths"):
        via_step(u1.at(), mm(1), to="B.Cu")
    with pytest.raises(DslError, match="one argument or as two lengths"):
        design.via("v", (mm(1), mm(2)), mm(3), net=gnd)
    with pytest.raises(DslError, match="alone"):
        via_step(mm(1), to="B.Cu")
    with pytest.raises(DslError, match="alone"):
        design.via("v", "U1", net=gnd)
    with pytest.raises(DslError, match="board point"):
        design.stitch("s", net=gnd, pitch=mm(1), region=u1.pad(33), origin=(mm(1), mm(1)))
    with pytest.raises(DslError, match="same point"):
        design.track("t", u1.at(mm(1)), u1.at(mm(1)), net=gnd)
    for call in (
        lambda: via_step(u1.pad(1), to="B.Cu"),
        lambda: arc_to(u1.pad(1), (mm(1), mm(1))),
        lambda: arc_to((mm(1), mm(1)), r1.pad(1)),
        lambda: design.stitch("s", net=gnd, pitch=mm(1), along=(u1.pad(1), (mm(1), mm(1)))),
        lambda: design.stitch("s", net=gnd, pitch=mm(1), region=(u1.pad(1), (mm(1), mm(1)), (mm(2), mm(5)))),
        lambda: design.stitch(
            "s", net=gnd, pitch=mm(1), along=((mm(0), mm(0)), (mm(1), mm(1))), origin=u1.pad(1)
        ),
        lambda: design.stitch("s", net=gnd, pitch=mm(1), region=u1.pad(33), origin=u1.pad(33)),
    ):
        with pytest.raises(DslError, match=r"\.at\(\)"):
            call()
    with pytest.raises(DslError, match="exactly one"):
        design.stitch("s", net=gnd, pitch=mm(1), region=u1.pad(33), along=((mm(1), mm(1)), (mm(2), mm(2))))
    with pytest.raises(DslError, match="region is"):
        design.stitch("s", net=gnd, pitch=mm(1), region=u1.at())
    assert not design.copper_intents, "a refused call records nothing"


def test_part_not_in_the_design() -> None:
    """Scenario "Part not in the design"."""
    for record in (
        lambda d, p, n: d.via("v", p.pad(1).at(), net=n),
        lambda d, p, n: d.track("t", (mm(1), mm(1)), p.at(mm(1)), net=n),
        lambda d, p, n: d.track("t", (mm(1), mm(1)), via_step(p.at(), to="B.Cu"), (mm(3), mm(3)), net=n),
        lambda d, p, n: d.track("t", (mm(1), mm(1)), arc_to((mm(2), mm(1)), p.at()), (mm(9), mm(9)), net=n),
        lambda d, p, n: d.stitch("s", net=n, pitch=mm(1), region=p.pad(1)),
        lambda d, p, n: d.stitch(
            "s", net=n, pitch=mm(1), along=((mm(1), mm(1)), (mm(5), mm(5))), origin=p.at()
        ),
    ):
        design = blink()
        r9 = Part("R9", "Mini:Mini_R", footprint="Mini:Mini_R_0603")
        record(design, r9, design.nets["GND"])
        with pytest.raises(DslError, match="R9"):
            copper(design)


def test_reexports_and_the_model_is_untouched() -> None:
    assert dsl.Anchor is Anchor and dsl.AnchorRef is AnchorRef
    assert {"Anchor", "AnchorRef"} <= set(dsl.__all__)
    plain, anchored = blink(), blink()
    u1, _, vin, _ = _parts(anchored)
    anchored.via("fan9", u1.pad(9).at(mm(0), mm(1)), net=vin, **SIZES)
    assert canonical.dump_texts(to_model(anchored)) == canonical.dump_texts(to_model(plain))
