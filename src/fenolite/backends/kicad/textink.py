# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ink of stroke texts as ``kicad-cli`` draws it (change c0212; capability silkscreen-layout, "Text ink
extents"; facts: ``docs/formats/kicad/text.md``).

``measure_ink`` writes the texts asked for as ``gr_text`` items on ``F.SilkS`` of a scratch board, one per
cell of a grid, runs ``kicad-cli pcb export svg`` on that layer once, and reads each text's ink back from
the plot: KiCad writes the strokes of one text as the ``<path>`` lines of one ``<g class="stroked-text">``
group, with the stroke width in the style of an enclosing group, in millimetres of the board frame
(``H-K-SILK-INK``). ``stroked_texts`` reads those groups from any such plot, so a test can measure a whole
board as well. ``kicad-cli`` runs as a subprocess; nothing of KiCad is read or copied.
"""

from __future__ import annotations

import dataclasses
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point, Size
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.model.board import FieldJustifyH, FieldJustifyV, Outline, Text
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-SILK-INK",))
"""``KICAD-VERIFIED``: the row is ``KICAD-VERIFIED (10.0.x)`` in ``docs/hypotheses.md``; a box read here is
what the tool that drew it drew."""
SVG = "{http://www.w3.org/2000/svg}"
LAYER = "F.SilkS"
ORIGIN = 10_000_000
"""The anchor of the first cell of the scratch grid (10 mm, 10 mm)."""
COLUMNS = 20
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_STROKE = re.compile(r"stroke-width\s*:\s*(-?\d+(?:\.\d+)?)")
_MM = Decimal(1_000_000)


InkRequest = tuple[str, Nm, Nm, Nm, FieldJustifyH, FieldJustifyV]
"""``(text, glyph width, glyph height, stroke, horizontal justification, vertical justification)``."""
Box = tuple[Nm, Nm, Nm, Nm]
"""``(x0, y0, x1, y1)``: a box of ink relative to the text's anchor, in its reading frame."""


class InkParseError(ValueError):
    """A plot that does not hold the stroked texts Fenolite expects."""


@dataclass(frozen=True, slots=True)
class StrokedText:
    """One ``stroked-text`` group of a plot: its ``desc`` text, the box of its skeleton (the stroke
    centre lines) and its stroke width, in nm of the board frame."""

    text: str
    x0: Nm
    y0: Nm
    x1: Nm
    y1: Nm
    stroke: Nm

    @property
    def ink(self) -> tuple[Nm, Nm, Nm, Nm]:
        """The box of the ink: the skeleton grown by half the stroke (rounded up for an odd stroke)."""
        half = -(-self.stroke // 2)
        return self.x0 - half, self.y0 - half, self.x1 + half, self.y1 + half


def _nm(text: str) -> Nm:
    try:
        value = Decimal(text) * _MM
    except InvalidOperation as error:
        raise InkParseError(f"not a number in the plot: {text!r}") from error
    if value != value.to_integral_value():
        raise InkParseError(f"a plot coordinate finer than a nanometre: {text!r}")
    return int(value)


def _walk(element: ET.Element, stroke: str | None) -> Iterator[tuple[ET.Element, str | None]]:
    style = element.get("style") or ""
    found = _STROKE.search(style)
    here = found.group(1) if found else stroke
    yield element, here
    for child in element:
        yield from _walk(child, here)


def stroked_texts(svg: str) -> tuple[StrokedText, ...]:
    """Every ``<g class="stroked-text">`` group of a ``pcb export svg`` plot, in document order."""
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as error:
        raise InkParseError(f"the plot is not XML: {error}") from error
    found: list[StrokedText] = []
    for element, stroke in _walk(root, None):
        if element.tag != f"{SVG}g" or element.get("class") != "stroked-text":
            continue
        desc = element.find(f"{SVG}desc")
        xs: list[Nm] = []
        ys: list[Nm] = []
        for path in element.iter(f"{SVG}path"):
            numbers = [_nm(n) for n in _NUMBER.findall(path.get("d") or "")]
            if len(numbers) % 2:
                raise InkParseError(f"an odd count of coordinates in a path: {path.get('d')!r}")
            xs.extend(numbers[0::2])
            ys.extend(numbers[1::2])
        if not xs:
            continue
        if stroke is None:
            raise InkParseError("a stroked text without a stroke width")
        text = desc.text if desc is not None and desc.text is not None else ""
        found.append(StrokedText(text, min(xs), min(ys), max(xs), max(ys), _nm(stroke)))
    return tuple(found)


@dataclass(frozen=True, slots=True)
class _Grid:
    pitch_x: Nm
    pitch_y: Nm

    def anchor(self, index: int) -> Point:
        return Point(ORIGIN + (index % COLUMNS) * self.pitch_x, ORIGIN + (index // COLUMNS) * self.pitch_y)

    def cell(self, x: Nm, y: Nm) -> int | None:
        column = (x - ORIGIN + self.pitch_x // 2) // self.pitch_x
        line = (y - ORIGIN + self.pitch_y // 2) // self.pitch_y
        if not 0 <= column < COLUMNS or line < 0:
            return None
        return line * COLUMNS + column


def _grid(keys: Sequence[InkRequest]) -> _Grid:
    """Cells that hold any of the texts with room around it: no glyph advances by twice its width
    (``docs/formats/kicad/board.md``: at most 1.45 x the size), and no line is taller than twice its
    height, so twice those on each side of the anchor, plus 2 mm, separate two cells."""
    span_x, span_y = 0, 0
    for text, width, height, stroke, _, _ in keys:
        lines = text.split("\n")
        span_x = max(span_x, 2 * width * max(len(line) for line in lines) + 2 * height + stroke)
        span_y = max(span_y, 2 * height * len(lines) + stroke)
    return _Grid(2 * span_x + 2_000_000, 2 * span_y + 2_000_000)


def scratch_board(keys: Sequence[InkRequest], *, major: int) -> tuple[str, _Grid]:
    """The text of a board that holds each key as a ``gr_text`` on ``F.SilkS`` at its grid anchor."""
    grid = _grid(keys)
    texts = tuple(
        Text(
            id=derived_id("txt", "fenolite.textink", str(index)),
            text=text,
            position=grid.anchor(index),
            layer=LAYER,
            size=Size(width, height),
            thickness=stroke,
            h_justify=h_justify,
            v_justify=v_justify,
        )
        for index, (text, width, height, stroke, h_justify, v_justify) in enumerate(keys)
    )
    rows = -(-len(keys) // COLUMNS)
    w = 2 * ORIGIN + COLUMNS * grid.pitch_x
    h = 2 * ORIGIN + rows * grid.pitch_y
    base = Design.new("textink", seed=0)
    assert base.board is not None
    board = dataclasses.replace(
        base.board,
        outline=Outline(
            id=derived_id("out", "fenolite.textink", "outline"),
            points=(Point(0, 0), Point(w, 0), Point(w, h), Point(0, h)),
        ),
        layers=created_layers(2),
        texts=texts,
    )
    return write_board(dataclasses.replace(base, board=board), target=major).text, grid


def measure_ink(
    cli: KicadCli, keys: Sequence[InkRequest], *, major: int | None = None
) -> dict[InkRequest, Box | None]:
    """The ink of each key as ``cli`` draws it (``KICAD-VERIFIED``): one scratch board, one plot. A key
    whose text draws nothing gets ``None``. ``major`` is the board format to write (default: the tool's)."""
    unique = list(dict.fromkeys(keys))
    if not unique:
        return {}
    text, grid = scratch_board(unique, major=cli.major() if major is None else major)
    name = "textink.kicad_pcb"
    svg = cli.export_layers_svg(Path(name), [LAYER], files={name: text.encode("utf-8")})
    found: dict[InkRequest, Box | None] = dict.fromkeys(unique)
    for item in stroked_texts(svg):
        x0, y0, x1, y1 = item.ink
        index = grid.cell((x0 + x1) // 2, (y0 + y1) // 2)
        if index is None or index >= len(unique):
            raise InkParseError(f"a stroked text {item.text!r} outside the grid of the scratch board")
        anchor = grid.anchor(index)
        key = unique[index]
        box = (x0 - anchor.x, y0 - anchor.y, x1 - anchor.x, y1 - anchor.y)
        held = found[key]
        found[key] = (
            box
            if held is None
            else (min(held[0], box[0]), min(held[1], box[1]), max(held[2], box[2]), max(held[3], box[3]))
        )
    return found


def board_texts(
    cli: KicadCli, board: Path, layers: Sequence[str], *, files: Mapping[str, Path | bytes] | None = None
) -> tuple[StrokedText, ...]:
    """Every stroked text that ``cli`` draws on ``layers`` of ``board``, in the board frame."""
    return stroked_texts(cli.export_layers_svg(board, layers, files=files))


__all__ = [
    "EVIDENCE",
    "Box",
    "InkParseError",
    "InkRequest",
    "StrokedText",
    "board_texts",
    "measure_ink",
    "scratch_board",
    "stroked_texts",
]
