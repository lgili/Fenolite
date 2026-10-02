# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The SVG reader of the drawing-sheet oracle, on authored snippets (capability kicad-oracle, "Drawing
sheets are judged by what KiCad draws"; change c0012). No ``kicad-cli`` is run."""

from __future__ import annotations

from decimal import Decimal

import pytest
from _svg import Segment, read_sheet_svg

D = Decimal

SNIPPET = """<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="297.0022mm" height="210.0072mm"
  viewBox="0.0000 0.0000 297.0022 210.0072">
<g style="fill:none">
<path d="M10 10 L20 10" />
<text x="35.0000" y="11.6500" font-size="1.7333" text-anchor="start" opacity="0">Alpha</text>
<g class="stroked-text"><desc>Alpha</desc><path d="M35 11 L36 12" /></g>
<text x="50.5" y="20" font-size="2.6667" text-anchor="middle" opacity="0">Bravo</text>
<text x="1" y="1" font-size="1">visible, not a hidden text</text>
</g>
</svg>
"""


def test_authored_snippet() -> None:
    svg = read_sheet_svg(SNIPPET)
    assert (svg.width_mm, svg.height_mm) == (D("297.0022"), D("210.0072"))
    assert [(t.text, t.x, t.y, t.anchor) for t in svg.texts] == [
        ("Alpha", D("35.0000"), D("11.6500"), "start"),
        ("Bravo", D("50.5"), D("20"), "middle"),
    ]
    assert svg.paths == (Segment(D(10), D(10), D(20), D(10)),)
    assert svg.strings() == ["Alpha", "Bravo"]


def _svg(d: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"><path d="{d}"/></svg>'


@pytest.mark.parametrize(
    ("d", "segments"),
    [
        ("M1 1 L2 1 L2 2 L1 1", [(1, 1, 2, 1), (2, 1, 2, 2), (2, 2, 1, 1)]),
        ("M1 1 2 1", [(1, 1, 2, 1)]),
        ("m1 1 l1 0 l0 1", [(1, 1, 2, 1), (2, 1, 2, 2)]),
        ("M1 1 H3 V4 h-1 v-1", [(1, 1, 3, 1), (3, 1, 3, 4), (3, 4, 2, 4), (2, 4, 2, 3)]),
        ("M0 0 L1 0 L1 1 Z", [(0, 0, 1, 0), (1, 0, 1, 1), (1, 1, 0, 0)]),
        ("M0 0 L1 0 L0 0 Z", [(0, 0, 1, 0), (1, 0, 0, 0)]),
    ],
)
def test_path_commands(d: str, segments: list[tuple[int, int, int, int]]) -> None:
    found = read_sheet_svg(_svg(d)).paths
    assert [(s.x1, s.y1, s.x2, s.y2) for s in found] == [tuple(D(v) for v in s) for s in segments]


def test_page_size_in_millimetres_only() -> None:
    with pytest.raises(ValueError, match="width"):
        read_sheet_svg('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="10mm"/>')


def test_curves_refused() -> None:
    with pytest.raises(ValueError, match="unsupported path command"):
        read_sheet_svg(_svg("M0 0 C1 1 2 2 3 3"))
