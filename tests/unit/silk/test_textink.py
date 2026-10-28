# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reading the ink of stroke texts from a ``pcb export svg`` plot (change c0212;
``fenolite.backends.kicad.textink``; ``docs/formats/kicad/text.md``). Hermetic: the plots are authored here
in the form the format page records, and the tool is a stand-in that draws a fixed box at each anchor."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.textink import (
    InkParseError,
    InkRequest,
    StrokedText,
    measure_ink,
    stroked_texts,
)

PLOT = """<?xml version="1.0" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 100 100">
<g style="fill:none; stroke:#000000; stroke-width:0.1500; stroke-linecap:round;">
<text x="10.0000" y="10.5000" opacity="0">AB</text>
<g class="stroked-text"><desc>AB</desc>
<path d="M9.5000 10.2500
L10.5000 9.7500
" />
<path d="M9.2500 10.0000
L9.2500 10.0000
" />
</g>
<g class="stroked-text"><desc>empty</desc>
</g>
</g>
<g style="stroke-width:0.1000"><g class="stroked-text"><desc>C</desc><path d="M1 2 L3 4" /></g></g>
</svg>
"""


def test_stroked_texts() -> None:
    """Each group gives its text, the box of its strokes' centre lines and the width of the enclosing
    style; a group without strokes is left out."""
    first, second = stroked_texts(PLOT)
    assert first == StrokedText("AB", 9_250_000, 9_750_000, 10_500_000, 10_250_000, 150_000)
    assert first.ink == (9_175_000, 9_675_000, 10_575_000, 10_325_000)
    assert second == StrokedText("C", 1_000_000, 2_000_000, 3_000_000, 4_000_000, 100_000)


@pytest.mark.parametrize(
    "plot",
    [
        "<svg",
        '<svg xmlns="http://www.w3.org/2000/svg"><g class="stroked-text"><path d="M1 2" /></g></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><g style="stroke-width:0.1"><g class="stroked-text">'
        '<path d="M1 2 L3" /></g></g></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><g style="stroke-width:0.1"><g class="stroked-text">'
        '<path d="M1.00000001 2 L3 4" /></g></g></svg>',
    ],
)
def test_plots_that_are_refused(plot: str) -> None:
    with pytest.raises(InkParseError):
        stroked_texts(plot)


class _Tool:
    """Reads the scratch board it is given and draws a skeleton of 1 mm x 0.5 mm right of each anchor."""

    def major(self) -> int:
        return 10

    def export_layers_svg(
        self, board: Path, layers: Sequence[str], *, files: Mapping[str, Path | bytes] | None = None
    ) -> str:
        assert layers == ["F.SilkS"] and files is not None
        data = files[Path(board).name]
        assert isinstance(data, bytes)
        design = read_board(data.decode("utf-8"), file="textink.kicad_pcb")
        assert design.board is not None
        groups: list[str] = []
        for text in design.board.texts:
            if not text.text.strip():
                continue
            x, y = text.position.x / 1e6, text.position.y / 1e6
            groups.append(
                f'<g class="stroked-text"><desc>{text.text}</desc>'
                f'<path d="M{x:.4f} {y - 0.25:.4f} L{x + 1:.4f} {y + 0.25:.4f}" /></g>'
            )
        body = "".join(groups)
        return f'<svg xmlns="http://www.w3.org/2000/svg"><g style="stroke-width:0.2">{body}</g></svg>'


def test_measure_ink_maps_each_text_to_its_cell() -> None:
    """Many texts on one scratch board: each box comes back relative to its own anchor."""
    requests: list[InkRequest] = [
        (f"T{n}", 1_000_000, 1_000_000, 150_000, "center", "center") for n in range(45)
    ]
    requests.append((" ", 1_000_000, 1_000_000, 150_000, "left", "top"))
    found = measure_ink(_Tool(), requests)  # type: ignore[arg-type]
    for request in requests[:-1]:
        assert found[request] == (-100_000, -350_000, 1_100_000, 350_000)
    assert found[requests[-1]] is None
    assert measure_ink(_Tool(), []) == {}  # type: ignore[arg-type]
