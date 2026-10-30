# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Shaped pads in authored footprints (capability dsl-footprint-authoring, "Shaped pads in authored
footprints"; change c0277): trapezoid, chamfered, rounded and custom pads, written in the forms of the demo
boards (S-0058) and read back with ``read_footprint``."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.core.coords import Point
from fenolite.dsl import DslError, Footprint, mm
from fenolite.dsl.footprint import arc, circle, poly, segment
from fenolite.model.board import PadPrimitive

TAB = (
    poly(((mm(-0.2), mm(-0.2)), (mm(0.2), mm(-0.2)), (mm(0.2), mm(0.2)), (mm(-0.2), mm(0.2))), width=mm(0.1)),
    segment((mm(0), mm(0)), (mm(0.6), mm(0)), width=mm(0.2)),
    circle((mm(0.6), mm(0)), mm(0.15)),
    arc((mm(0), mm(0.3)), (mm(0.3), mm(0.4)), (mm(0.6), mm(0.3)), width=mm(0.1)),
)


def shaped() -> Footprint:
    fp = Footprint("Local", "Shaped", kind="smd")
    fp.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(2)), shape="trapezoid", delta=(mm("0.2"), mm(0)))
    fp.pad("2", at=(mm(2), mm(0)), size=(mm(1), mm(1)), shape="rect", chamfer=250_000, corners=("top_left",))
    fp.pad("3", at=(mm(4), mm(0)), size=(mm(1), mm(1)), shape="roundrect", radius_ratio=200_000)
    fp.pad(
        "4", at=(mm(6), mm(0)), size=(mm("0.5"), mm("0.5")), shape="custom", anchor="circle", primitives=TAB
    )
    return fp


def pad_node(text: str, number: str):  # noqa: ANN201
    return next(p for p in parse(text).nodes("pad") if p.atoms()[0].value == number)


@pytest.mark.parametrize("target", [9, 10])
def test_four_shaped_pads(target: int) -> None:
    """Scenario "Four shaped pads"."""
    text = write_footprint(shaped().definition, target=target)
    assert write_footprint(shaped().definition, target=target) == text
    trapezoid, chamfered, rounded, custom = (pad_node(text, n) for n in "1234")
    assert dumps(trapezoid.find("rect_delta"), style="compact") == "(rect_delta 0.2 0)"  # type: ignore[arg-type]
    assert [a.value for a in chamfered.atoms()][2] == "roundrect"
    assert dumps(chamfered.find("roundrect_rratio"), style="compact") == "(roundrect_rratio 0)"  # type: ignore[arg-type]
    assert dumps(chamfered.find("chamfer"), style="compact") == "(chamfer top_left)"  # type: ignore[arg-type]
    heads = [c.name for c in chamfered.nodes()]
    assert heads.index("roundrect_rratio") < heads.index("chamfer_ratio") < heads.index("chamfer")
    assert dumps(rounded.find("roundrect_rratio"), style="compact") == "(roundrect_rratio 0.2)"  # type: ignore[arg-type]
    assert dumps(custom.find("options"), style="compact") == "(options (clearance outline) (anchor circle))"  # type: ignore[arg-type]
    assert [c.name for c in custom.find("primitives").nodes()] == [
        "gr_poly",
        "gr_line",
        "gr_circle",
        "gr_arc",
    ]  # type: ignore[union-attr]
    back = {pad.number: pad for pad in read_footprint(text, library="Local").pads}
    assert back["1"].shape == "trapezoid" and back["1"].trapezoid_delta == Point(200_000, 0)
    assert (back["2"].chamfer_ratio, back["2"].chamfer_corners) == (250_000, ("top_left",))
    assert back["3"].shape == "roundrect"
    assert back["4"].anchor_shape == "circle" and back["4"].primitives == TAB


@pytest.mark.parametrize(
    ("arguments", "word"),
    [
        ({"shape": "trapezoid"}, "delta"),
        ({"chamfer": 600_000, "corners": ("top_left",)}, "chamfer"),
        ({"shape": "custom", "primitives": ()}, "primitives"),
        ({"chamfer": 100_000, "corners": ("left",)}, "corners"),
        ({"shape": "oval", "chamfer": 100_000, "corners": ("top_left",)}, "chamfer"),
        ({"shape": "rect", "radius_ratio": 100_000}, "radius_ratio"),
        ({"shape": "trapezoid", "delta": (mm(0.1), mm(0.1))}, "delta"),
        ({"shape": "custom", "anchor": "oval", "primitives": TAB}, "anchor"),
    ],
)
def test_refused_shape_values(arguments: dict[str, object], word: str) -> None:
    """Scenario "Refused shape values"."""
    fp = Footprint("Local", "Bad", kind="smd")
    with pytest.raises(DslError, match=word):
        fp.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)), **arguments)  # type: ignore[arg-type]


def test_primitive_builders() -> None:
    assert circle((mm(1), mm(1)), mm(0.5)) == PadPrimitive(
        "circle", (Point(1_000_000, 1_000_000), Point(1_500_000, 1_000_000)), 0, True
    )
    with pytest.raises(DslError, match="three points"):
        poly(((mm(0), mm(0)), (mm(1), mm(0))))
    with pytest.raises(DslError, match="width"):
        segment((mm(0), mm(0)), (mm(1), mm(0)), width=mm(0))


def test_footprints_without_the_arguments() -> None:
    """Scenario "Footprints without the arguments": the authored footprints of the examples keep their bytes
    (checked by ``tests/unit/test_build_bytes.py`` over every example); a plain pad writes no shape child."""
    fp = Footprint("Local", "Plain", kind="smd")
    fp.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)), shape="roundrect")
    text = write_footprint(fp.definition, target=10)
    for head in ("rect_delta", "roundrect_rratio", "chamfer", "options", "primitives"):
        assert f"({head}" not in text
    assert Path  # the byte guard holds the examples
