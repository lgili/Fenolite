# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Via protection in the DSL (capability design-dsl, "Via protection in the DSL" and "Via protection
defaults in the DSL"; change c0112): ``protect``, ``protection=`` and ``Design.via_protection``."""

from __future__ import annotations

import pytest

import fenolite.dsl as dsl
from fenolite.core.coords import Point
from fenolite.dsl import (
    Design,
    DslError,
    Net,
    Part,
    StitchIntent,
    TrackIntent,
    ViaIntent,
    ViaStep,
    connect,
    copper,
    mm,
    protect,
    to_model,
    via_protection_locked,
    via_step,
)
from fenolite.model.board import ViaProtection


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


def test_values_of_protect() -> None:
    assert protect(tenting="front", plugging=True, filling=True) == ViaProtection(
        tenting_front=True, tenting_back=False, plugging_front=True, plugging_back=True, filling=True
    )
    assert protect() == ViaProtection()
    assert protect(tenting=False, covering="back", capping=False) == ViaProtection(
        tenting_front=False, tenting_back=False, covering_front=False, covering_back=True, capping=False
    )
    assert protect(tenting=True, capping=True) == ViaProtection(True, True, None, None, None, None, True)
    assert "protect" in dsl.__all__ and "via_protection_locked" in dsl.__all__


@pytest.mark.parametrize(
    ("arguments", "words"),
    [
        ({"tenting": "both"}, ("tenting", "'both'")),
        ({"capping": "front"}, ("capping", "'front'")),
        ({"covering": 1}, ("covering", "1")),
        ({"plugging": "none"}, ("plugging", "'none'")),
        ({"filling": 0}, ("filling", "0")),
        ({"tenting": ("front",)}, ("tenting",)),
    ],
)
def test_refused_values(arguments: dict[str, object], words: tuple[str, ...]) -> None:
    with pytest.raises(DslError) as caught:
        protect(**arguments)
    assert all(word in str(caught.value) for word in words)


def test_refused_protection_arguments() -> None:
    design, _, _, gnd = _blink()
    with pytest.raises(DslError, match="via v: protection"):
        design.via("v", mm(1), mm(1), net=gnd, protection="tented")
    with pytest.raises(DslError, match="via_step: protection"):
        via_step(mm(1), mm(1), to="B.Cu", protection=True)
    with pytest.raises(DslError, match="stitch s: protection"):
        design.stitch("s", net=gnd, pitch=mm(1), along=((mm(1), mm(1)), (mm(9), mm(1))), protection={})
    assert copper(design) == ()


def test_intents_carry_the_protection() -> None:
    design, r1, d1, gnd = _blink()
    design.via("tp1", mm(5), mm(5), net=gnd, protection=protect(tenting="back"))
    design.via("tp2", mm(6), mm(5), net=gnd)
    design.track(
        "inner",
        r1.pad(2),
        via_step(mm(8), mm(8), to="B.Cu", protection=protect(filling=True, capping=True)),
        d1.pad(2),
    )
    design.track(
        "led_a", r1.pad(2), (mm(36), mm(9)), via_step(mm(36), mm(14), to="B.Cu"), d1.pad(2), width=mm(0.3)
    )
    region = ((mm(1), mm(1)), (mm(9), mm(1)), (mm(9), mm(9)), (mm(1), mm(9)))
    design.stitch("ep", net=gnd, pitch=mm(1), region=region, protection=protect(plugging=True))
    design.stitch("plain", net=gnd, pitch=mm(1), region=region)
    ep, inner, led_a, plain, tp1, tp2 = copper(design)
    assert isinstance(tp1, ViaIntent) and tp1.protection == ViaProtection(False, True)
    assert isinstance(tp2, ViaIntent) and tp2.protection == ViaProtection()
    assert isinstance(inner, TrackIntent) and isinstance(inner.path[1], ViaStep)
    assert inner.path[1].protection == ViaProtection(filling=True, capping=True)
    assert isinstance(ep, StitchIntent)
    assert ep.protection == ViaProtection(plugging_front=True, plugging_back=True)
    assert isinstance(plain, StitchIntent) and plain.protection == ViaProtection()
    # the field comes last with a default: the values earlier scripts and tests build compare equal
    assert isinstance(led_a, TrackIntent)
    assert led_a.path[2] == ViaStep(Point(136_000_000, 114_000_000), "B.Cu", None, None)
    assert tp2 == ViaIntent("tp2", tp2.at, "GND", None, None, "through", None)
    board = to_model(design).board
    assert board is not None and board.vias == () and board.via_protection is None  # intents are no model


def test_default_in_the_model() -> None:
    design, *_ = _blink()
    assert via_protection_locked(design) is False
    design.via_protection(protect(tenting="front"), locked=True)
    board = to_model(design).board
    assert board is not None
    assert board.via_protection == ViaProtection(tenting_front=True, tenting_back=False)
    assert via_protection_locked(design) is True
    other, *_ = _blink()
    other.via_protection(protect(filling=True))
    assert via_protection_locked(other) is False


def test_refused_default_calls() -> None:
    design, *_ = _blink()
    with pytest.raises(DslError, match="value of protect"):
        design.via_protection("tented")  # type: ignore[arg-type]
    with pytest.raises(DslError, match="locked"):
        design.via_protection(protect(), locked=1)  # type: ignore[arg-type]
    design.via_protection(protect())
    with pytest.raises(DslError, match="once"):
        design.via_protection(protect())
