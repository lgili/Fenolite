# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The whole-board silkscreen judge of change c0498 (task 3.2; ``silk.board.judge_silk``, design D4): the
committed Altium sample ``blink`` with authored board texts and lines planted on its top silkscreen."""

from __future__ import annotations

import dataclasses

import pytest
from _violations import BLINK

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.core.coords import Point, Size
from fenolite.model.board import Graphic, Text
from fenolite.model.design import Design
from fenolite.silk.board import SilkFinding, judge_silk

MM = 1_000_000
FRAME = AltiumBackend()


@pytest.fixture(scope="module")
def blink() -> Design:
    return FRAME.read(BLINK).design


def text(ident: str, at: Point, value: str = "AB") -> Text:
    return Text(id=ident, text=value, position=at, layer="F.SilkS", size=Size(MM, MM), thickness=150_000)


def planted(design: Design, *, texts: tuple[Text, ...] = (), lines: tuple[Graphic, ...] = ()) -> Design:
    assert design.board is not None
    board = dataclasses.replace(
        design.board, texts=(*design.board.texts, *texts), graphics=(*design.board.graphics, *lines)
    )
    return dataclasses.replace(design, board=board)


def judged(design: Design, **limits: int | None) -> list[SilkFinding]:
    wanted = {"silk": None, "mask": None, "edge": None, **limits}
    return judge_silk(design, pads=FRAME.board_pads(design), edges=FRAME.board_edges(design), **wanted)


def mine(found: list[SilkFinding], name: str) -> list[SilkFinding]:
    return [f for f in found if name in f.items]


def far_corner(design: Design) -> Point:
    """A place inside the board, 3 mm from its first edge ring's least corner."""
    ring = FRAME.board_edges(design)[0]
    return Point(min(p.x for p in ring.points) + 3 * MM, min(p.y for p in ring.points) + 3 * MM)


def test_two_texts_too_close(blink: Design) -> None:
    """Scenario "Two texts too close": two free texts whose boxes are nearer than the Silk To Silk rule."""
    at = far_corner(blink)
    design = planted(blink, texts=(text("txt_a", at), text("txt_b", Point(at.x, at.y + 1_100_000))))
    (found,) = mine(judged(design, silk=200_000), "txt_a")
    assert found.code == "silk.clearance" and set(found.items) == {"txt_a", "txt_b"} and found.side == "top"
    assert found.gap < 200_000 and found.limit == 200_000
    assert mine(judged(design, silk=5_000), "txt_a") == []


def test_a_text_on_a_mask_opening(blink: Design) -> None:
    """Scenario "A text on a mask opening": a free text over a top pad's mask opening."""
    pad = next(p for p in FRAME.board_pads(blink) if any(c.layer == "F.Cu" for c in p.copper))
    centre = next(c for c in pad.copper if c.layer == "F.Cu").core[0]
    design = planted(blink, texts=(text("txt_m", centre),))
    found = [f for f in mine(judged(design, mask=50_000), "txt_m") if f.code == "silk.mask-clearance"]
    assert found and all(f.gap == 0 for f in found)
    assert f"{pad.ref}-{pad.number}" in {f.items[1] for f in found}


def test_silk_over_the_edge(blink: Design) -> None:
    """Scenario "Silk over the edge": a free silkscreen line across the board's first edge."""
    ring = FRAME.board_edges(blink)[0]
    x0 = min(p.x for p in ring.points)
    y = (min(p.y for p in ring.points) + max(p.y for p in ring.points)) // 2
    line = Graphic(
        id="gfx_edge",
        kind="line",
        layer="F.SilkS",
        points=(Point(x0 - MM, y), Point(x0 + MM, y)),
        width=150_000,
    )
    (found,) = mine(judged(planted(blink, lines=(line,)), edge=100_000), "gfx_edge")
    assert found.code == "silk.edge-clearance" and found.items == ("gfx_edge", "edge") and found.gap == 0


def test_no_limit_judges_nothing(blink: Design) -> None:
    assert judged(blink) == []
