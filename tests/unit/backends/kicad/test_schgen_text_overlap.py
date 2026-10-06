# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The texts of a readable sheet are clear of each other (capability kicad-schematic, "Readable sheet
layout", scenario "Texts of a turned satellite"; change c0070). Hermetic: no tool runs.

The boxes are estimated from the written sheet files by ``_schtext``: one font size per character and a
line of 2 mm for a Reference or a Value, the text plus 2.54 mm and 1.27 mm to each side for a label, and
both sides of the point for a justified text of a turned symbol, because KiCad may flip it."""

from __future__ import annotations

import _gendesigns
import _schtext
import pytest
from _buildhelp import ROOT, blink, build

from fenolite.backends.kicad import schlayout
from fenolite.backends.kicad.schlayout import GRID, ORIGIN_STEP
from fenolite.core.coords import Point
from fenolite.dsl import Design
from fenolite.lens.build import BuildOutput

ACCEPTANCE = ROOT / "tests" / "data" / "lens" / "acceptance" / "design.py"


def acceptance_design() -> Design:
    """The lens acceptance design of c0069, as ``tests/kicad/schematic/_hiercases.py`` loads it."""
    scope: dict[str, object] = {"__name__": "design"}
    exec(compile(ACCEPTANCE.read_text(encoding="utf-8"), str(ACCEPTANCE), "exec"), scope)  # noqa: S102
    design = scope["design"]
    assert isinstance(design, Design)
    return design


def sheets(output: BuildOutput) -> dict[str, str]:
    """The text of every schematic file of a build, by its path."""
    assert output.schematic is not None, [i.message for i in output.issues if i.severity == "error"]
    found = {rel: data.decode("utf-8") for rel, data in output.files.items() if rel.endswith(".kicad_sch")}
    assert len(found) == 1 + len(output.schematic.children)
    return found


def problems(output: BuildOutput) -> list[str]:
    return [
        f"{rel}: {line}" for rel, text in sorted(sheets(output).items()) for line in _schtext.overlaps(text)
    ]


@pytest.mark.parametrize("target", [9, 10])
def test_blink_texts_are_clear(target: int) -> None:
    output = build(blink(), target)
    assert output.schematic is not None and output.schematic.satellites >= 1
    assert problems(output) == []


@pytest.mark.parametrize("target", [9, 10])
def test_acceptance_texts_are_clear(target: int) -> None:
    assert problems(build(acceptance_design(), target)) == []


@pytest.mark.parametrize("modules", [True, False])
def test_generated_texts_are_clear(modules: bool) -> None:
    """The 25 generated designs of each seed: the ones with modules and satellites, and the flat ones."""
    seed = _gendesigns.MODULE_SEED if modules else _gendesigns.SEED
    satellites = turned = 0
    found: list[str] = []
    for index in range(_gendesigns.COUNT):
        output = build(_gendesigns.design(seed, index, modules=modules))
        found += [f"design {index}: {line}" for line in problems(output)]
        made = output.schematic
        assert made is not None
        satellites += made.satellites
        for sheet in (made.sheet, *made.children.values()):
            turned += sum(1 for symbol in sheet.symbols if symbol.rotation)
    assert found == []
    assert satellites >= 5 and turned >= 5, "the designs hold turned satellites, so the rule is measured"


def test_turned_satellite_texts_lie_beside_the_label_of_the_pair() -> None:
    """R1 of the blink lies left of pin 1 of U1, turned on its side; the label of the pair points up at
    its near pin. Its Reference and Value are written level and centred, above the resistor, between that
    label and the label of the far pin."""
    output = build(blink())
    (text,) = sheets(output).values()
    made = output.schematic
    assert made is not None
    r1 = next(s for s in made.sheet.symbols if s.ref == "R1")
    assert r1.rotation in (90_000_000, 270_000_000)
    wire = next(w for w in made.sheet.wires if w.end.y == r1.position.y and w.end.x > r1.position.x)
    pair = next(label for label in made.sheet.labels if label.position == wire.end)
    assert pair.rotation == 90_000_000
    found = _schtext.drawn(text)
    body = next(item.box for item in found if item.kind == "body" and item.name == "R1")
    for key in ("Reference", "Value"):
        _, y0, x1, y1 = next(item.box for item in found if item.name == f"R1 {key}")
        assert y1 - y0 == _schtext.LINE, "drawn level"
        assert x1 <= wire.end.x - GRID, "left of the room of the label that points up"
        assert y1 <= body[1], "above the resistor and the room of the label at its far pin"
        _, angle, justify = _schtext.written(text, "R1", key)
        assert angle == 90, "KiCad turns the field with the symbol: 90 degrees is drawn level"
        assert justify == "", "centred: no side for KiCad to flip"
    reference, value = _schtext.written(text, "R1", "Reference")[0], _schtext.written(text, "R1", "Value")[0]
    assert reference.x == value.x and value.y - reference.y == ORIGIN_STEP


def test_unturned_texts_keep_their_place() -> None:
    """A symbol that is not turned keeps the left-justified texts of c0061, at angle 0."""
    (text,) = sheets(build(blink())).values()
    for key in ("Reference", "Value"):
        assert _schtext.written(text, "U1", key)[1:] == (0, "left")


def test_room_of_a_turned_unit() -> None:
    """``turned_text_room``: above from the left edge without a crossing label, beside the label on its
    side with one, and to the right of a unit with a pin that leaves it upwards."""
    bounds = (-3_810_000, -1_016_000, 3_810_000, 1_016_000)
    ends = [Point(-3_810_000, 0), Point(3_810_000, 0)]
    length = 3 * schlayout.CHAR_ROOM
    room = schlayout.turned_text_room
    assert room(bounds, ends, Point(0, 0), False, length) == (
        -3_810_000,
        -GRID - 2 * ORIGIN_STEP,
        -3_810_000 + length,
        -GRID,
    )
    up = room(bounds, ends, Point(0, 0), False, length, (ends[1], 90))
    assert up == (3_810_000 - ORIGIN_STEP - length, -GRID - 2 * ORIGIN_STEP, 3_810_000 - ORIGIN_STEP, -GRID)
    down = room(bounds, ends, Point(0, 0), False, length, (ends[0], 270))
    assert down == (-3_810_000 + ORIGIN_STEP, GRID, -3_810_000 + ORIGIN_STEP + length, GRID + 2 * ORIGIN_STEP)
    right = room((-1_016_000, -3_810_000, 1_016_000, 3_810_000), [], Point(0, 0), True, length)
    assert right == (1_016_000 + ORIGIN_STEP, -ORIGIN_STEP, 1_016_000 + ORIGIN_STEP + length, ORIGIN_STEP)
