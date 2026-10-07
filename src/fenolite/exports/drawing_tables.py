# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The blocks of a drawing: the board, stack-up and drill tables and the numbered notes (capability
manufacturing-exports, "Drawing tables and notes"; change c0117; user guide ``docs/drawings.md``).

Every value comes from the model read from the board. A block is sized with a bound of what KiCad draws
(``H-K-DRAW-TEXT``): no glyph of ``GLYPH_SET`` advances more than ``GLYPH_BOUND`` × the text size, and
lines are ``LINE_PITCH`` × the size apart. Fenolite breaks the lines of a note itself, so KiCad never
wraps a cell and no row overflows. All functions are pure.

The stack-up fields that change c0101 adds (``dielectric_kind``, ``color``, ``impedance_controlled`` and
``Stackup.thickness()``) are read when the model has them; before that a dielectric is ``dielectric``,
there is no colour column, and the thickness is the sum of the entries.
"""

from __future__ import annotations

import string
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import cast

from fenolite.backends.base import PlotTable
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.outline import board_outline
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.units import Nm
from fenolite.exports.codes import issue
from fenolite.exports.drawing_spec import DrawingSpec
from fenolite.model.board import Pad, StackLayer, Stackup
from fenolite.model.design import Design

GLYPH_BOUND = Fraction(145, 100)
"""The widest advance of a glyph of ``GLYPH_SET``, as a multiple of the text size (``H-K-DRAW-TEXT``)."""
OTHER_BOUND = Fraction(2)
"""What any other character counts: nothing was measured for it."""
LINE_EXTRA = Fraction(1, 4)
"""What KiCad adds to the advances of a line, as a multiple of the text size: a line of n glyphs of
advance a is n × a + 0.25 × the size long (measured on 10.0.6 at 1, 1.5 and 3 mm, change c0117), so a
bound of the advances alone is too short for a few wide glyphs."""
LINE_PITCH = Fraction(161, 100)
"""The distance between two lines of a text, as a multiple of its size (``H-K-DRAW-TEXT``)."""
GLYPH_SET = frozenset(string.ascii_letters + string.digits + string.punctuation + " ±µ°×ΩÄÖÜßéèçñ–—…")
"""The measured glyphs: printable ASCII and the signs a drawing note usually needs."""
MARGIN = 1_000_000
"""The cell margin on every side."""
STROKE = Fraction(15, 100)
"""The stroke width of generated text, as a multiple of its size."""
_MM = 1_000_000


def _ceil(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def text_width(text: str, size: Nm) -> Nm:
    """An upper bound of the width KiCad draws one line of ``text`` at ``size``: the bound of each
    character's advance, and for a line that holds any character the constant KiCad adds to a line."""
    if not text:
        return 0
    known = sum(1 for char in text if char in GLYPH_SET)
    return _ceil(GLYPH_BOUND * size * known + OTHER_BOUND * size * (len(text) - known) + LINE_EXTRA * size)


def line_pitch(size: Nm) -> Nm:
    return _ceil(LINE_PITCH * size)


def _cut(word: str, width: Nm, size: Nm) -> list[str]:
    """``word`` in pieces that each fit ``width``; a piece holds at least one character."""
    pieces: list[str] = []
    piece = ""
    for char in word:
        if piece and text_width(piece + char, size) > width:
            pieces.append(piece)
            piece = ""
        piece += char
    return [*pieces, piece] if piece else pieces


def break_lines(text: str, width: Nm, size: Nm) -> str:
    """``text`` broken at spaces, greedily, into lines that each fit ``width`` by ``text_width``; a word
    longer than ``width`` is cut, the text's own line feeds are kept, and the lines are joined by a line
    feed."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = f"{line} {word}" if line else word
            if text_width(candidate, size) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
            pieces = _cut(word, width, size) or [""]
            lines += pieces[:-1]
            line = pieces[-1]
        lines.append(line)
    return "\n".join(lines)


def mm_text(value: Nm) -> str:
    """A length in millimetres as an exact decimal with at least three decimals (``0.300``, ``0.2104``)."""
    text = f"{Decimal(value).scaleb(-6):.6f}".rstrip("0")
    whole, _, decimals = text.partition(".")
    return f"{whole}.{decimals.ljust(3, '0')}"


@dataclass(frozen=True, slots=True)
class Block:
    """A table of a drawing: its name, its rows of texts, and the widths and heights that hold every
    text by the bound. A block without ``border`` draws no line."""

    name: str
    rows: tuple[tuple[str, ...], ...]
    column_widths: tuple[Nm, ...]
    row_heights: tuple[Nm, ...]
    text_size: Nm
    border: bool = True

    @property
    def width(self) -> Nm:
        return sum(self.column_widths)

    @property
    def height(self) -> Nm:
        return sum(self.row_heights)

    @property
    def size(self) -> tuple[Nm, Nm]:
        return (self.width, self.height)

    def plot(self, at: Point, layer: str) -> PlotTable:
        """The block as an item of a plot copy, its top-left corner at ``at``."""
        return PlotTable(
            self.name, layer, at, self.column_widths, self.row_heights, self.rows, self.text_size, self.border
        )


def _lines(text: str) -> list[str]:
    return text.split("\n")


def make_block(
    name: str,
    rows: Sequence[Sequence[str]],
    size: Nm,
    *,
    border: bool = True,
    widths: Sequence[Nm | None] = (),
) -> Block:
    """A block whose columns are as wide as their widest line plus the two margins (or as ``widths``
    says) and whose rows are as high as their tallest cell's lines plus the two margins."""
    columns = len(rows[0])
    fixed = [*widths, *([None] * (columns - len(widths)))]
    column_widths = tuple(
        fixed[c]
        if fixed[c] is not None
        else max(text_width(line, size) for row in rows for line in _lines(row[c])) + 2 * MARGIN
        for c in range(columns)
    )
    heights = tuple(max(len(_lines(cell)) for cell in row) * line_pitch(size) + 2 * MARGIN for row in rows)
    return Block(
        name, tuple(tuple(row) for row in rows), cast(tuple[int, ...], column_widths), heights, size, border
    )  # fmt: skip


# -- drill


@dataclass(frozen=True, slots=True)
class DrillRow:
    """The holes of one plating, span, drill and slot length: how many, and what makes them."""

    plated: bool
    first: str
    last: str
    drill: Nm
    slot: Nm | None
    count: int
    kinds: tuple[str, ...]
    through: bool = True


def copper_layers(design: Design) -> tuple[str, ...]:
    layers = design.board.layers if design.board is not None else ()
    return tuple(layer.name for layer in sorted(layers, key=lambda la: la.ordinal) if layer.kind == "copper")


def _slot(pad: Pad | None, hole: Sequence[Point], drill: Nm) -> Nm | None:
    if pad is not None and pad.padstack is not None and pad.padstack.hole_shape == "slot":
        length = pad.padstack.hole_length
        if length is not None and length != drill:
            return length
    if len(hole) == 2 and hole[0] != hole[1]:
        (a, b) = hole
        return abs(a.x - b.x) + abs(a.y - b.y) + drill if a.x == b.x or a.y == b.y else None
    return None


def drill_rows(design: Design) -> tuple[DrillRow, ...]:
    """One row per plating, span, drill and slot length, from the drilled pads and the vias of the
    board: through spans first, plated before unplated, then the other spans in stack order, then by
    drill and slot length."""
    board = design.board
    copper = copper_layers(design)
    if board is None or len(copper) < 2:
        return ()
    order = {name: index for index, name in enumerate(copper)}
    outer = (copper[0], copper[-1])
    found: dict[tuple[bool, str, str, Nm, Nm | None], tuple[int, set[str]]] = {}

    def add(plated: bool, span: tuple[str, str], drill: Nm, slot: Nm | None, kind: str) -> None:
        key = (plated, span[0], span[1], drill, slot)
        count, kinds = found.get(key, (0, set[str]()))
        found[key] = (count + 1, kinds | {kind})

    pads = {pad.id: pad for footprint in board.footprints for pad in footprint.pads}
    for record in board_pads(design):
        if record.drill is None or record.drill <= 0 or record.kind not in ("thru_hole", "np_thru_hole"):
            continue
        slot = _slot(pads.get(record.pad_id), record.hole, record.drill)
        add(record.kind == "thru_hole", outer, record.drill, slot, "pad")
    for via in board.vias:
        named = sorted((name for name in via.layers if name in order), key=order.__getitem__)
        span = (named[0], named[-1]) if len(named) >= 2 and via.via_type != "through" else outer
        add(True, span, via.drill, None, "via")

    def rank(key: tuple[bool, str, str, Nm, Nm | None]) -> tuple[int, ...]:
        plated, first, last, drill, slot = key
        through = (first, last) == outer
        span = (0, 0) if through else (order[first], order[last])
        return (0 if through else 1, *span, 0 if plated else 1, drill, slot or 0)

    rows: list[DrillRow] = []
    for key in sorted(found, key=rank):
        plated, first, last, drill, slot = key
        count, kinds = found[key]
        rows.append(
            DrillRow(
                plated,
                first,
                last,
                drill,
                slot,
                count,
                tuple(sorted(kinds, reverse=True)),
                (first, last) == outer,
            )  # fmt: skip
        )
    return tuple(rows)


def drill_block(rows: Sequence[DrillRow], size: Nm) -> Block | None:
    """The drill table: ``Drill``, ``Slot`` (when a row has one), ``Plated``, ``Layers``, ``Count`` and
    ``Holes``, and a last row with the total count. No block for a board without a hole."""
    if not rows:
        return None
    slots = any(row.slot is not None for row in rows)
    table = [["Drill", "Slot", "Plated", "Layers", "Count", "Holes"]]
    for row in rows:
        table.append(
            [
                mm_text(row.drill),
                "" if row.slot is None else mm_text(row.slot),
                "yes" if row.plated else "no",
                f"{row.first} - {row.last}",
                str(row.count),
                ", ".join(row.kinds),
            ]
        )
    table.append(["Total", "", "", "", str(sum(row.count for row in rows)), ""])
    if not slots:
        table = [[cell for index, cell in enumerate(line) if index != 1] for line in table]
    return make_block("drill", table, size)


# -- board and stack-up


def stackup_thickness(stackup: Stackup) -> Nm:
    """``Stackup.thickness()`` where the model has it (change c0101), else the sum of its entries."""
    method = getattr(stackup, "thickness", None)
    if callable(method):
        return cast(int, method())
    return sum(layer.thickness for layer in stackup.layers)


def _stack_type(layer: StackLayer) -> str:
    if layer.kind != "dielectric":
        return layer.kind
    return str(getattr(layer, "dielectric_kind", None) or "dielectric")


def stackup_block(design: Design, size: Nm) -> Block | None:
    """One row per entry of the stack-up from the top, paste entries left out, a column that is empty in
    every row dropped, and a last row with the total thickness. No block without a stack-up."""
    stackup = design.board.stackup if design.board is not None else None
    if stackup is None:
        return None
    head = ["Layer", "Type", "Material", "Thickness", "Dk", "Df", "Color"]
    entries = [
        [
            layer.name,
            _stack_type(layer),
            layer.material,
            mm_text(layer.thickness) if layer.thickness else "",
            layer.epsilon_r,
            layer.loss_tangent,
            str(getattr(layer, "color", "") or ""),
        ]
        for layer in stackup.layers
        if layer.kind != "solderpaste"
    ]
    always = (0, 1, 3)  # the layer, its type and its thickness are columns of every stack-up table
    kept = [index for index in range(len(head)) if index in always or any(row[index] for row in entries)]
    total = ["Total", "", "", mm_text(stackup_thickness(stackup)), "", "", ""]
    table = [[row[index] for index in kept] for row in (head, *entries, total)]
    return make_block("stackup", table, size)


def outline_box(design: Design) -> tuple[Nm, Nm, Nm, Nm] | None:
    """The bounding box of the first ring of the board's outline, or ``None`` without a closed outline."""
    rings = board_outline(design).rings
    if not rings:
        return None
    xs, ys = [point.x for point in rings[0]], [point.y for point in rings[0]]
    return (min(xs), min(ys), max(xs), max(ys))


def board_block(design: Design, size: Nm, rows: Sequence[DrillRow] | None = None) -> Block | None:
    """The board table: copper layers, the outline's width and height, with a stack-up its thickness,
    finish and whether it is impedance-controlled, and the smallest drill."""
    board = design.board
    if board is None:
        return None
    table = [["Board", "Value"], ["Copper layers", str(len(copper_layers(design)))]]
    box = outline_box(design)
    if box is not None:
        table.append(["Outline", f"{mm_text(box[2] - box[0])} x {mm_text(box[3] - box[1])}"])
    if board.stackup is not None:
        table.append(["Thickness", mm_text(stackup_thickness(board.stackup))])
        table.append(["Finish", board.stackup.finish])
        controlled = bool(getattr(board.stackup, "impedance_controlled", False))
        table.append(["Impedance controlled", "yes" if controlled else "no"])
    holes = drill_rows(design) if rows is None else rows
    if holes:
        table.append(["Smallest drill", mm_text(min(row.drill for row in holes))])
    return make_block("board", table, size)


def impedance_block(design: Design, size: Nm = 0) -> Block | None:
    """No block: the model holds no impedance target (the change that adds them gives this block its
    rows). The table name stays valid in a specification."""
    del design, size
    return None


def notes_block(notes: Sequence[str], width: Nm, size: Nm) -> Block | None:
    """One row per note, numbered ``1.``, ``2.``, …; the note column is ``width`` wide and its lines are
    broken by ``break_lines``. No border and no separator; no block without a note."""
    if not notes:
        return None
    inner = max(width - 2 * MARGIN, text_width("M", size))
    rows = [[f"{index}.", break_lines(note, inner, size)] for index, note in enumerate(notes, 1)]
    return make_block("notes", rows, size, border=False, widths=(None, inner + 2 * MARGIN))


def fab_blocks(design: Design, spec: DrawingSpec) -> tuple[tuple[Block, ...], tuple[Issue, ...]]:
    """The blocks of the fabrication page that have content, in the order they are placed, and the
    infos about a table that could not be built."""
    size = spec.page.text_size
    rows = drill_rows(design)
    wanted = spec.fab.tables
    blocks: list[Block | None] = []
    issues: list[Issue] = []
    if "board" in wanted:
        blocks.append(board_block(design, size, rows))
    if "stackup" in wanted:
        block = stackup_block(design, size)
        blocks.append(block)
        if block is None:
            issues.append(
                issue(
                    "drawing.stackup-missing",
                    "the board has no stack-up: the fabrication drawing has no stack-up table",
                    where="stackup",
                    hint="define the stack-up in the board (Board Setup in KiCad, or design.stackup() in "
                    "the script)",
                )
            )
    if "drill" in wanted:
        blocks.append(drill_block(rows, size))
    if "impedance" in wanted:
        blocks.append(impedance_block(design, size))
    if "notes" in wanted:
        blocks.append(notes_block(spec.fab.notes, spec.page.notes_width, size))
    return tuple(block for block in blocks if block is not None), tuple(issues)


__all__ = [
    "GLYPH_BOUND",
    "GLYPH_SET",
    "LINE_EXTRA",
    "LINE_PITCH",
    "MARGIN",
    "STROKE",
    "Block",
    "DrillRow",
    "board_block",
    "break_lines",
    "copper_layers",
    "drill_block",
    "drill_rows",
    "fab_blocks",
    "impedance_block",
    "line_pitch",
    "make_block",
    "mm_text",
    "notes_block",
    "outline_box",
    "stackup_block",
    "stackup_thickness",
    "text_width",
]
