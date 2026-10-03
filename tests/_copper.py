# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fixtures of the copper tests (change c0028): the built blink, the intents of the routed example, and
short constructors for intents in board coordinates."""

from __future__ import annotations

import runpy
from functools import cache
from pathlib import Path

from _buildhelp import BLINK_DIR, blink, build
from _placed import mm, pt

from fenolite.core.coords import Point
from fenolite.dsl import (
    BOARD_ORIGIN,
    CopperIntent,
    PadEnd,
    StitchIntent,
    TrackIntent,
    ViaIntent,
    ViaStep,
    copper,
)
from fenolite.dsl import Design as DslDesign
from fenolite.model.design import Design

ROUTED_DIR = Path(__file__).resolve().parents[1] / "examples" / "blink_routed"
ROUTED = ROUTED_DIR / "design.py"
SIZES = {"diameter": mm(0.6), "drill": mm(0.3)}


@cache
def built_blink(target: int = 10) -> Design:
    """The blink of ``examples/blink_2layer`` built for ``target``: no copper."""
    output = build(blink(), target, project_dir=BLINK_DIR)
    assert output.files, [i.code for i in output.issues]
    return output.design


def routed_script() -> DslDesign:
    design = runpy.run_path(str(ROUTED))["design"]
    assert isinstance(design, DslDesign)
    return design


@cache
def routed_intents() -> tuple[CopperIntent, ...]:
    """The four intents of ``examples/blink_routed/design.py``, in key order."""
    return copper(routed_script())


def at(x: float, y: float) -> Point:
    """A point in the frame of ``place()``, written in the board frame."""
    return Point(BOARD_ORIGIN.x + mm(x), BOARD_ORIGIN.y + mm(y))


def end(component: str, number: str | int, index: int | None = None) -> PadEnd:
    return PadEnd(component, str(number), index)


def step(x: float, y: float, layer: str = "B.Cu", **sizes: int | None) -> ViaStep:
    chosen = {**SIZES, **sizes}
    return ViaStep(at(x, y), layer, chosen["diameter"], chosen["drill"])


def track(
    key: str, *path: object, layer: str = "F.Cu", width: int | None = 300_000, net: str | None = None
) -> TrackIntent:
    return TrackIntent(key, tuple(path), layer, width, net)  # type: ignore[arg-type]


def via(key: str, point: Point, net: str | None = "GND", **sizes: int | None) -> ViaIntent:
    chosen = {**SIZES, **sizes}
    return ViaIntent(key, point, net, chosen["diameter"], chosen["drill"])  # type: ignore[arg-type]


def stitch(key: str, net: str | None = "GND", pitch: int = 3_000_000, **fields: object) -> StitchIntent:
    values: dict[str, object] = {**SIZES, "clearance": mm(0.2), **fields}
    return StitchIntent(key, net, pitch, **values)  # type: ignore[arg-type]


__all__ = [
    "ROUTED",
    "ROUTED_DIR",
    "SIZES",
    "at",
    "built_blink",
    "end",
    "pt",
    "routed_intents",
    "routed_script",
    "step",
    "stitch",
    "track",
    "via",
]
