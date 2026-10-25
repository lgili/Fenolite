# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Draftsman drawing reader (capability draftsman-viewer, scenario "An authored document"; change c0180,
task 1.2; ``H-A-DWF-GEOM``).

The document is authored for Fenolite (``tests/_draftsman.py``).
"""

from __future__ import annotations

import math

import pytest
from _draftsman import DOCUMENT, pt, stored
from _draftsman import segment as segment_xml

from fenolite.backends.altium.read.draftsman import NAMESPACE, read_draftsman
from fenolite.backends.altium.read.dwfdraw import contour, place, read_drawing, snap_points

ARC_FULL = "<Radius>2</Radius><Angle1>0</Angle1><Angle2>360</Angle2>"


def close(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return math.dist(a, b) < 1e-6


def test_authored_document() -> None:
    drawing = read_drawing(read_draftsman(stored(DOCUMENT)))
    assert drawing.metric and not drawing.is_panel
    assert drawing.parameters["revision"] == "B"
    assert drawing.fonts["f1"].family == "Arial" and drawing.fonts["f1"].size == 8
    assert drawing.lines["l1"].color == "#ff0000" and drawing.lines["l1"].thickness == 1.5
    (page,) = drawing.pages
    assert (page.width, page.height, page.margin, page.zones) == (1122.5, 793.7, (1, 2, 3, 4), (True, 6, 4))
    text, view = page.items
    assert text.fields["text"] == "=Revision" and text.fields["h"] == "Center"
    assert text.fields["rect"] == (10, 20, 100, 12)
    assert (
        view.fields["location"] == (100, 200)
        and view.fields["scale"] == 0.5
        and view.fields["side"] == "Bottom"
    )
    assert drawing.skipped == {"Callout": 1}


def test_board_copy() -> None:
    board = read_drawing(read_draftsman(stored(DOCUMENT))).board
    assert board.bounds == (0, 0, 96, 144) and board.thickness == 6
    assert close(board.outline[0], (0, 0)) and close(board.outline[-1], (0, 96))
    assert any(close(p, (48, 144)) for p in board.outline)  # the arc's top, counter-clockwise from Angle1
    assert len(board.outline) == 3 + 180 // 5 - 1 + 1
    (hole,) = board.holes
    assert hole.centre == (20, 20) and hole.size == 3.5 and hole.plated
    parts = {part.ref: part for part in board.parts}
    assert close(parts["R1"].pads[0], (45, 60))
    assert close(parts["R2"].pads[0], (60, 45))
    assert close(parts["R3"].pads[0], (55, 60))
    assert parts["R2"].side == "Bottom" and len(parts["R1"].contours[0]) == 4


@pytest.mark.parametrize(
    ("local", "rotation", "bottom", "expected"),
    [
        ((1, 0), 0, False, (1, 0)),
        ((1, 0), 90, False, (0, 1)),
        ((0, 1), 0, True, (0, -1)),
        ((0, 1), 90, True, (1, 0)),
    ],
)
def test_place(
    local: tuple[float, float], rotation: float, bottom: bool, expected: tuple[float, float]
) -> None:
    assert close(place(local, (0, 0), rotation, bottom), expected)


def test_snap_points() -> None:
    assert snap_points("GI|Board Outline|Line: 0, 0, 225.6, 0") == ((0, 0), (225.6, 0))
    assert snap_points("GI|R1|Point: 1.5, -2") == ((1.5, -2),)
    assert snap_points("GI|R1|Arc: 1, 2, 3") == ()


def test_open_stroke_circle() -> None:
    """A lone arc of 0 to 360 degrees in an open stroke is a circle that ends where it starts."""
    import xml.etree.ElementTree as ET

    segment = ET.fromstring(
        f'<Segments xmlns="{NAMESPACE}">{segment_xml("Arc", 2, 0, pt("Center", 0, 0) + ARC_FULL)}</Segments>'
    )
    ring = contour(list(segment), closed=False)
    assert close(ring[0], (2, 0)) and close(ring[-1], (2, 0)) and any(close(p, (-2, 0)) for p in ring)
