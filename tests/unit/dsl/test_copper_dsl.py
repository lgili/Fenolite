# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper intents in the DSL (capability design-dsl, "Copper intents in the DSL"; change c0028): what a
script records, what is refused at the call, and the routed example."""

from __future__ import annotations

import dataclasses
import runpy
from pathlib import Path

import pytest

import fenolite.dsl as dsl
from fenolite.core.coords import Point
from fenolite.dsl import (
    BOARD_ORIGIN,
    Design,
    DslError,
    Net,
    PadEnd,
    PadRef,
    Part,
    StitchIntent,
    TrackIntent,
    ViaIntent,
    ViaStep,
    connect,
    copper,
    mm,
    to_model,
    via_step,
)

ROUTED = Path(__file__).resolve().parents[3] / "examples" / "blink_routed" / "design.py"


def _blink() -> tuple[Design, Part, Part, Net]:
    design = Design("blink")
    design.board(mm(50), mm(30))
    r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603")
    d1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm")
    design.add(r1, d1)
    gnd, led_a = Net("GND"), Net("LED_A")
    connect(gnd, d1[1])
    connect(led_a, r1[2], d1[2])
    return design, r1, d1, gnd


def test_a_track_in_board_coordinates() -> None:
    design, r1, d1, _ = _blink()
    design.track(
        "led_a", r1.pad(2), (mm(36), mm(9)), via_step(mm(36), mm(14), to="B.Cu"), d1.pad(2), width=mm(0.3)
    )
    (intent,) = copper(design)
    assert intent == TrackIntent(
        "led_a",
        (
            PadEnd("R1", "2", None),
            Point(136_000_000, 109_000_000),
            ViaStep(Point(136_000_000, 114_000_000), "B.Cu", None, None),
            PadEnd("D1", "2", None),
        ),
        "F.Cu",
        300_000,
        None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        intent.width = 1  # type: ignore[misc]


def test_pad_references() -> None:
    _, r1, _, _ = _blink()
    assert r1.pad(9) == r1.pad("9") == PadRef(r1, "9", None)
    assert r1.pad("A1", index=0).index == 0
    for number in ("", None, 1.5, True):
        with pytest.raises(DslError, match="pad number"):
            r1.pad(number)  # type: ignore[arg-type]
    for index in (-1, "0", True, 1.0):
        with pytest.raises(DslError, match="pad index"):
            r1.pad(1, index=index)  # type: ignore[arg-type]


def test_via_and_stitch_intents() -> None:
    design, _, _, gnd = _blink()
    design.via("tie", mm(20), mm(10), net=gnd, diameter=mm(0.6), drill="0.3mm")
    design.stitch("fence", net=gnd, pitch=mm(5), along=((mm(16), mm(26)), (mm(36), mm(26))), margin=mm(0.1))
    design.stitch(
        "pour", net=gnd, pitch=mm(2), region=((mm(0), mm(0)), (mm(5), mm(0)), (mm(5), mm(5))),
        origin=(mm(1), mm(1)), clearance=mm(0.25),
    )  # fmt: skip
    fence, pour, tie = copper(design)
    ox, oy = BOARD_ORIGIN.x, BOARD_ORIGIN.y
    assert tie == ViaIntent("tie", Point(ox + 20_000_000, oy + 10_000_000), "GND", 600_000, 300_000)
    assert fence == StitchIntent(
        "fence",
        "GND",
        5_000_000,
        along=(Point(ox + 16_000_000, oy + 26_000_000), Point(ox + 36_000_000, oy + 26_000_000)),
        origin=BOARD_ORIGIN,
        margin=100_000,
    )
    assert isinstance(pour, StitchIntent)
    assert pour.origin == Point(ox + 1_000_000, oy + 1_000_000) and pour.clearance == 250_000
    assert len(pour.region) == 3 and pour.along == () and pour.margin == 0


def test_malformed_intents_fail_at_the_call() -> None:
    design, r1, d1, gnd = _blink()
    with pytest.raises(DslError, match="led a"):
        design.track("led a", r1.pad(1), d1.pad(1))
    with pytest.raises(DslError, match="via step"):
        design.track("k", via_step(mm(1), mm(1), to="B.Cu"), r1.pad(1))
    with pytest.raises(DslError, match=r"path\[1\]\.x"):
        design.track("k2", r1.pad(1), (1, 2))
    with pytest.raises(DslError, match="along and region"):
        design.stitch("s", net=gnd, pitch=mm(2))
    assert copper(design) == ()  # nothing was recorded by a refused call


@pytest.mark.parametrize(
    "call",
    [
        lambda d, r, g: d.track("k", r.pad(1)),
        lambda d, r, g: d.track("k", r.pad(1), "F.Cu"),
        lambda d, r, g: d.track("k", r.pad(1), (mm(1), mm(1), mm(1))),
        lambda d, r, g: d.track("k", (mm(1), mm(1)), (mm(1), mm(1))),
        lambda d, r, g: d.track("k", r.pad(1), r.pad(1)),
        lambda d, r, g: d.track("k", (mm(1), mm(1)), via_step(mm(1), mm(1), to="B.Cu")),
        lambda d, r, g: d.track("k", r.pad(1), (mm(1), mm(1)), layer=""),
        lambda d, r, g: d.track("k", r.pad(1), (mm(1), mm(1)), width=mm(0)),
        lambda d, r, g: d.track("k", r.pad(1), (mm(1), mm(1)), width=5),
        lambda d, r, g: d.track("k", r.pad(1), (mm(1), mm(1)), net="GND"),
        lambda d, r, g: d.track("a/", r.pad(1), (mm(1), mm(1))),
        lambda d, r, g: via_step(mm(1), mm(1), to=""),
        lambda d, r, g: via_step(mm(1), mm(1), to="B.Cu", drill=mm(-1)),
        lambda d, r, g: d.via("k", mm(1), mm(1), net="GND"),
        lambda d, r, g: d.via("k", mm(1), mm(1), net=g, diameter=mm(0)),
        lambda d, r, g: d.via("k", 1, 1, net=g),
        lambda d, r, g: d.stitch("k", net=g, pitch=mm(0), along=((mm(0), mm(0)), (mm(1), mm(0)))),
        lambda d, r, g: d.stitch("k", net=g, pitch=mm(1), along=((mm(0), mm(0)),)),
        lambda d, r, g: d.stitch("k", net=g, pitch=mm(1), region=((mm(0), mm(0)), (mm(1), mm(0)))),
        lambda d, r, g: d.stitch(
            "k", net=g, pitch=mm(1), along=((mm(0), mm(0)), (mm(1), mm(0))), region=((mm(0), mm(0)),) * 3
        ),
        lambda d, r, g: d.stitch(
            "k", net=g, pitch=mm(1), along=((mm(0), mm(0)), (mm(1), mm(0))), margin=mm(-1)
        ),
        lambda d, r, g: d.stitch("k", net=None, pitch=mm(1), along=((mm(0), mm(0)), (mm(1), mm(0)))),
    ],
)
def test_refusals(call: object) -> None:
    design, r1, _, gnd = _blink()
    with pytest.raises(DslError):
        call(design, r1, gnd)  # type: ignore[operator]
    assert design.copper_intents == {}


def test_key_order_and_repeated_keys() -> None:
    design, _, _, gnd = _blink()
    design.via("b", mm(2), mm(2), net=gnd)
    design.via("a", mm(1), mm(1), net=gnd)
    design.track("a/b", (mm(1), mm(1)), (mm(2), mm(1)), net=gnd)
    assert [intent.key for intent in copper(design)] == ["a", "a/b", "b"]
    with pytest.raises(DslError, match="'a'"):
        design.via("a", mm(1), mm(1), net=gnd)
    with pytest.raises(DslError, match="'b'"):
        design.track("b", (mm(1), mm(1)), (mm(2), mm(1)))


def test_part_or_net_not_in_the_design() -> None:
    design, r1, _, _ = _blink()
    r9 = Part("R9", "Mini:Mini_R")
    design.track("k", r9.pad(1), r1.pad(1))
    with pytest.raises(DslError, match="R9"):
        copper(design)
    other, _, _, _ = _blink()
    other.via("v", mm(1), mm(1), net=Net("ORPHAN"))
    with pytest.raises(DslError, match="ORPHAN"):
        copper(other)


def test_component_paths_inside_modules() -> None:
    design = Design("m")
    design.board(mm(20), mm(20))
    module = dsl.Module("io")
    j1 = Part("J1", "Mini:Mini_Conn")
    module.add(j1)
    design.add(module)
    net = Net("SIG")
    connect(net, j1[1])
    design.track("k", j1.pad(1), (mm(5), mm(5)))
    (intent,) = copper(design)
    assert isinstance(intent, TrackIntent) and intent.path[0] == PadEnd("io/J1", "1", None)


def test_to_model_is_unchanged_by_intents() -> None:
    plain, _, _, _ = _blink()
    routed, r1, d1, _ = _blink()
    routed.track("led_a", r1.pad(2), d1.pad(2), width=mm(0.3))
    assert to_model(routed) == to_model(plain)


def test_reexports() -> None:
    names = (
        "PadRef", "via_step", "copper", "PadEnd", "ViaStep", "TrackIntent", "ViaIntent", "StitchIntent",
        "CopperIntent",
    )  # fmt: skip
    for name in names:
        assert name in dsl.__all__ and hasattr(dsl, name)


def test_example_script() -> None:
    design = runpy.run_path(str(ROUTED))["design"]
    intents = copper(design)
    assert [intent.key for intent in intents] == ["gnd", "gnd_fence", "led_a", "led_drv"]
    gnd, fence, led_a, led_drv = intents
    assert isinstance(gnd, TrackIntent) and gnd.width is None and gnd.net is None and len(gnd.path) == 5
    assert isinstance(fence, StitchIntent) and (fence.net, fence.pitch) == ("GND", 5_000_000)
    assert (fence.diameter, fence.drill, fence.clearance) == (600_000, 300_000, None)
    assert isinstance(led_a, TrackIntent) and isinstance(led_drv, TrackIntent)
    assert led_drv.path[0] == PadEnd("U1", "1", None) and led_drv.path[-1] == PadEnd("R1", "1", None)
    steps = [e for intent in (gnd, led_a) for e in intent.path if isinstance(e, ViaStep)]
    assert [(s.layer, s.diameter, s.drill) for s in steps] == [("B.Cu", 600_000, 300_000)] * 2
    text = ROUTED.read_text(encoding="utf-8")
    assert text.startswith("# SPDX-License-Identifier: CC0-1.0\n# Authored for Fenolite as an example")
