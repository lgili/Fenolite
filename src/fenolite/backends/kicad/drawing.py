# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plot copies of a board for the drawing kinds, and what KiCad's drill report says (capability
manufacturing-exports, "Drawing plot copies" and "Fabrication drawing kind"; change c0117; facts:
``docs/formats/kicad/board.md``, "Drawing items", and ``docs/formats/kicad/cli.md``, "Drawings").

Fenolite draws nothing: it writes tables, texts and dimensions as board items into a copy of the board
text, and ``kicad-cli pcb export pdf`` plots that copy with the drawing sheet. The copy differs from the
board only in its ``paper`` node, the added items and the layer rows a page needs; the board file is
never written.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from fenolite.backends.base import PlotDimension, PlotItem, PlotTable, PlotText
from fenolite.backends.kicad.pcb import paper_node
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, parse
from fenolite.backends.kicad.slots import from_ext, opaque_child
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.model.base import Opaque
from fenolite.model.board import FootprintInstance
from fenolite.model.presentation import PaperSize, SheetFrameRef

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-DRAW-ITEMS", "H-K-DRAW-PAGE", "H-K-DRAW-DRILL"))
"""``KICAD-VERIFIED``, since the three hypotheses hold on 9.0.9 and 10.0.6 (c0117 task 9.2): that KiCad draws
the written items, that a plot puts them where the board does, and that the drill report counts what the
table states."""
NAMESPACE = uuid.UUID("6f0a7d52-1c17-5c0e-9d55-0c0117000000")
"""The namespace of every uuid of a plot copy: one board and one specification give one copy."""
LAYER_ROWS: dict[str, tuple[int, str]] = {
    "Dwgs.User": (17, "User.Drawings"),
    "F.Fab": (35, ""),
    "B.Fab": (33, ""),
}
"""The row a copy gets for a layer its table lacks: number and user name (``H-K-DRAW-LAYER``)."""
COORDINATE_HEADS = frozenset({"at", "start", "end", "mid", "center", "xy"})
MARGIN = 1_000_000
STROKE_PER_SIZE = (15, 100)
LINE_WIDTH = 150_000
REFERENCE_VARIABLE = "${REFERENCE}"
SHEET_MARGIN = 10_000_000
SHEET_BORDER = 12_000_000
TITLE_BLOCK = (120_000_000, 44_000_000)
"""KiCad's default sheet: borders 10 mm and 12 mm inside the page edges, and the title block from
120 mm left of and 44 mm above the inner border's corner (``H-K-DRAW-SHEET``)."""
Box = tuple[Nm, Nm, Nm, Nm]


def _node(head: str, *children: Node | Atom) -> Node:
    return Node(Atom.symbol(head), children)


def _yes(flag: bool) -> Atom:
    return Atom.symbol("yes" if flag else "no")


def _uuid(name: str) -> Node:
    return _node("uuid", Atom.string(str(uuid.uuid5(NAMESPACE, name))))


def _xy(head: str, x: Nm, y: Nm, *extra: Atom) -> Node:
    return _node(head, Atom.from_nm(x), Atom.from_nm(y), *extra)


def _font(size: Nm) -> Node:
    thickness = size * STROKE_PER_SIZE[0] // STROKE_PER_SIZE[1]
    return _node("font", _xy("size", size, size), _node("thickness", Atom.from_nm(thickness)))


def _stroke() -> Node:
    return _node("stroke", _node("width", Atom.from_nm(LINE_WIDTH)), _node("type", Atom.symbol("solid")))


def _table(item: PlotTable, major: int) -> Node:
    layer = _node("layer", Atom.string(item.layer))
    cells: list[Node | Atom] = []
    y = item.at.y
    for r, (height, row) in enumerate(zip(item.row_heights, item.cells, strict=True)):
        x = item.at.x
        for c, (width, text) in enumerate(zip(item.column_widths, row, strict=True)):
            justify = _node("justify", Atom.symbol("left"), Atom.symbol("top"))
            cells.append(
                _node(
                    "table_cell",
                    Atom.string(text),
                    _xy("start", x, y),
                    _xy("end", x + width, y + height),
                    _node("margins", *(Atom.from_nm(MARGIN) for _ in range(4))),
                    _node("span", Atom.integer(1), Atom.integer(1)),
                    layer,
                    _uuid(f"{item.name}:r{r}c{c}"),
                    _node("effects", _font(item.text_size), justify),
                )
            )
            x += width
        y += height
    lined = _yes(item.border)
    children: list[Node | Atom] = [_node("column_count", Atom.integer(len(item.column_widths)))]
    if major >= 10:
        children.append(_uuid(item.name))  # the token inventory has table/uuid since 10.0
    children += [
        layer,
        _node("border", _node("external", lined), _node("header", lined), _stroke()),
        _node("separators", _node("rows", lined), _node("cols", lined), _stroke()),
        _node("column_widths", *(Atom.from_nm(width) for width in item.column_widths)),
        _node("row_heights", *(Atom.from_nm(height) for height in item.row_heights)),
        _node("cells", *cells),
    ]
    return _node("table", *children)


def _text(item: PlotText) -> Node:
    effects: list[Node | Atom] = [_font(item.size)]
    if item.layer.startswith("B."):
        effects.append(_node("justify", Atom.symbol("mirror")))
    return _node(
        "gr_text",
        Atom.string(item.text),
        _xy("at", item.at.x, item.at.y, Atom.integer(0)),
        _node("layer", Atom.string(item.layer)),
        _uuid(item.name),
        _node("effects", *effects),
    )


def dimension_value(item: PlotDimension) -> str:
    """The length an orthogonal dimension measures, in millimetres with its precision, rounded half
    away from zero. KiCad recomputes this text on load; the written one is a cache."""
    length = (
        abs(item.end.x - item.start.x) if item.direction == "horizontal" else abs(item.end.y - item.start.y)
    )
    quantum = Decimal(1).scaleb(-item.precision)
    return f"{(Decimal(length).scaleb(-6)).quantize(quantum, rounding=ROUND_HALF_UP)} mm"


def _dimension(item: PlotDimension) -> Node:
    layer = _node("layer", Atom.string(item.layer))
    thickness = Atom.from_nm(LINE_WIDTH)
    middle = Point((item.start.x + item.end.x) // 2, (item.start.y + item.end.y) // 2)
    return _node(
        "dimension",
        _node("type", Atom.symbol("orthogonal")),
        layer,
        _uuid(item.name),
        _node("pts", _xy("xy", item.start.x, item.start.y), _xy("xy", item.end.x, item.end.y)),
        _node("height", Atom.from_nm(item.offset)),
        _node("orientation", Atom.integer(0 if item.direction == "horizontal" else 1)),
        _node(
            "format",
            _node("prefix", Atom.string("")),
            _node("suffix", Atom.string("")),
            _node("units", Atom.integer(2)),
            _node("units_format", Atom.integer(1)),
            _node("precision", Atom.integer(item.precision)),
        ),
        _node(
            "style",
            _node("thickness", thickness),
            _node("arrow_length", Atom.from_nm(1_270_000)),
            _node("text_position_mode", Atom.integer(0)),
            _node("arrow_direction", Atom.symbol("outward")),
            _node("extension_height", Atom.from_nm(586_420)),
            _node("extension_offset", Atom.from_nm(500_000)),
            _node("keep_text_aligned", Atom.symbol("yes")),
        ),
        _node(
            "gr_text",
            Atom.string(dimension_value(item)),
            _xy("at", middle.x, middle.y, Atom.integer(0)),
            layer,
            _uuid(f"{item.name}:text"),
            _node("effects", _font(item.text_size)),
        ),
    )


def item_nodes(items: Sequence[PlotItem], *, major: int) -> tuple[Node, ...]:
    """One root node per item: a ``table``, a ``gr_text`` or an orthogonal ``dimension``, in the form
    the probes of ``H-K-DRAW-ITEMS`` load on both majors. A table carries its ``uuid`` for major 10
    only. Every uuid is the ``uuid5`` of the item's name (and the cell's place)."""
    nodes: list[Node] = []
    for item in items:
        if isinstance(item, PlotTable):
            nodes.append(_table(item, major))
        elif isinstance(item, PlotText):
            nodes.append(_text(item))
        else:
            nodes.append(_dimension(item))
    return tuple(nodes)


def _layer_row(name: str) -> Node:
    number, user = LAYER_ROWS[name]
    extra = (Atom.string(user),) if user else ()
    return Node(Atom.integer(number), (Atom.string(name), Atom.symbol("user"), *extra))


def plot_copy(
    board_text: str,
    items: Sequence[PlotItem],
    *,
    paper: str,
    portrait: bool = False,
    major: int,
    layers: Sequence[str] = (),
) -> str:
    """The text of a copy of the board for one page: its ``paper`` set, a row added for each of
    ``layers`` that its layer table lacks, and the nodes of ``items`` appended. Equal arguments give
    equal texts; everything else of the board is kept as it is."""
    root = parse(board_text)
    page = paper_node(SheetFrameRef(cast(PaperSize, paper), portrait=portrait))
    children: list[Node | Atom] = []
    papered = False
    for child in root.children:
        if isinstance(child, Node) and child.name == "paper":
            children.append(page)
            papered = True
        elif isinstance(child, Node) and child.name == "layers":
            if not papered:
                children.append(page)
                papered = True
            present = {atom.value for row in child.nodes() for atom in row.atoms()[:1]}
            rows = [_layer_row(name) for name in layers if name in LAYER_ROWS and name not in present]
            children.append(child.with_children([*child.children, *rows]))
        else:
            children.append(child)
    children += item_nodes(items, major=major)
    return dumps(root.with_children(children))


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.nodes():
        yield from _walk(child)


def _on_layer(node: Node, layer: str) -> bool:
    found = node.find("layer")
    return found is not None and any(atom.value == layer for atom in found.atoms())


def layer_extent(board_text: str, layer: str) -> Box | None:
    """The bounding box of every coordinate (``at``, ``start``, ``end``, ``mid``, ``center``, ``xy``) of
    the root items on ``layer``; ``None`` when no root item is on it. Footprints are not root items of a
    layer: their graphics are bounded by their courtyards."""
    xs: list[Nm] = []
    ys: list[Nm] = []
    for item in parse(board_text).nodes():
        if item.name == "footprint" or not _on_layer(item, layer):
            continue
        for node in _walk(item):
            if node.name not in COORDINATE_HEADS:
                continue
            numbers = [atom for atom in node.atoms() if atom.kind == AtomKind.NUMBER]
            if len(numbers) >= 2:
                xs.append(numbers[0].to_nm(exact=False))
                ys.append(numbers[1].to_nm(exact=False))
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _hidden(node: Node) -> bool:
    for found in _walk(node):
        if found.name == "hide" and not any(atom.value == "no" for atom in found.atoms()):
            return True
        if found.name in ("effects", "fp_text", "property") and any(a.value == "hide" for a in found.atoms()):
            return True
    return False


def shows_reference(footprint: FootprintInstance, layer: str) -> bool:
    """Whether the footprint shows its reference on ``layer``: a ``Reference`` field that is visible
    there, or a text holding ``${REFERENCE}`` that is not hidden."""
    for field in footprint.fields:
        if field.name == "Reference" and field.layer == layer and field.visible:
            return True
    bag = footprint.ext.get("kicad")
    for slot in from_ext(bag) if bag is not None else ():
        if not isinstance(slot, Opaque):
            continue
        child = opaque_child(slot)
        if not isinstance(child, Node) or child.name != "fp_text" or not _on_layer(child, layer):
            continue
        if any(REFERENCE_VARIABLE in atom.value for atom in child.atoms()) and not _hidden(child):
            return True
    return False


def default_sheet_obstacles(width: Nm, height: Nm) -> tuple[Box, tuple[Box, ...]]:
    """The margin box and the obstacles of KiCad's default sheet on a ``width`` × ``height`` page: the
    page less 10 mm, the band from there to the border 12 mm inside each edge, and the title block."""
    outer, inner = SHEET_MARGIN, SHEET_BORDER
    margin = (outer, outer, width - outer, height - outer)
    bands = (
        (outer, outer, width - outer, inner),
        (outer, height - inner, width - outer, height - outer),
        (outer, outer, inner, height - outer),
        (width - inner, outer, width - outer, height - outer),
    )
    title = (width - TITLE_BLOCK[0], height - TITLE_BLOCK[1], width - inner, height - inner)
    return margin, (*bands, title)


# -- the drill report


@dataclass(frozen=True, slots=True)
class DrillFile:
    """One drill file of a report: its name, whether its holes are plated (``None`` when the report
    does not say), the layer pair of a file that is not through, and per tool the diameter and the
    hole count. KiCad counts a slot with the round holes of its width."""

    name: str
    plated: bool | None
    span: tuple[str, str] | None
    tools: tuple[tuple[Nm, int], ...]


@dataclass(frozen=True, slots=True)
class DrillReport:
    files: tuple[DrillFile, ...] = ()


_FILE = re.compile(r"^\s*Drill file '([^']+)' contains")
_PAIR = re.compile(r"layer pair:\s*'(.+?) and (.+?)'")
_TOOL = re.compile(r"^\s*T\d+\s+(\d+(?:\.\d+)?)mm\s+\S+\s+\((\d+) holes?\)")


def read_drill_report(text: str) -> DrillReport:
    """The drill files of a report that ``pcb export drill --generate-report`` wrote. A tool line may
    close with one or two parentheses (9.0 and 10.0) and may name its slots after the count."""
    files: list[DrillFile] = []
    name: str | None = None
    plated: bool | None = None
    span: tuple[str, str] | None = None
    tools: list[tuple[Nm, int]] = []

    def close() -> None:
        if name is not None:
            files.append(DrillFile(name, plated, span, tuple(tools)))

    for line in text.splitlines():
        started = _FILE.match(line)
        if started is not None:
            close()
            opened = started.group(1)
            name, span, tools = opened, None, []
            plated = False if opened.endswith("-NPTH.drl") else True if opened.endswith("-PTH.drl") else None
            continue
        if name is None:
            continue
        pair = _PAIR.search(line)
        if pair is not None:
            plated, span = True, (pair.group(1), pair.group(2))
        elif "unplated through holes" in line:
            plated = False
        elif "plated through holes" in line:
            plated = True
        tool = _TOOL.match(line)
        if tool is not None:
            diameter = int((Decimal(tool.group(1)) * 1_000_000).to_integral_value())
            tools.append((diameter, int(tool.group(2))))
    close()
    return DrillReport(tuple(files))


__all__ = [
    "EVIDENCE",
    "LAYER_ROWS",
    "DrillFile",
    "DrillReport",
    "default_sheet_obstacles",
    "dimension_value",
    "item_nodes",
    "layer_extent",
    "plot_copy",
    "read_drill_report",
    "shows_reference",
]
