# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copies of an Altium Embedded Board Array in a conversion to KiCad (capability design-conversion,
"Copies of an embedded board array are placed only where measured"; change c0386).

Altium places copy (c, r) of an array (columns and rows counted from 0 at the lower left) so that a point
``P`` of the referenced board lies at ``(X, Y) + T((c * COLSPACING, r * ROWSPACING) + P - O)``, with ``O``
the referenced board's origin and ``T`` the identity, or a counter-clockwise quarter turn about ``(X, Y)``
for ``ROTATION`` 90 (S-1592, ``docs/formats/altium/pcb-document.md``, "Embedded board arrays"). The rule is
measured for an unmirrored array turned by 0 or 90 degrees whose referenced board has its origin at the
lower-left corner of its shape. Each such array's copies join the converted board: every id derived from
the array and the copy, every net named ``B<k>/<name>``, every designator ``<ref>_B<k>`` and every part
in the sheet ``B<k>`` of the generated schematic, with ``k`` counting the copies of all arrays from 1.
Every other array stays a refused ``embedded-board`` loss, its reason naming what is not measured.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path, PureWindowsPath
from typing import Any, Literal, cast

from fenolite.backends.altium.adapter.units import units_length
from fenolite.backends.altium.read.pcbstack import OutlineVertex
from fenolite.convert.report import (
    EMBEDDED_BOARD_ABSOLUTE,
    EMBEDDED_BOARD_ANGLE,
    EMBEDDED_BOARD_CUTOUT,
    EMBEDDED_BOARD_LAYERS,
    EMBEDDED_BOARD_MIRRORED,
    EMBEDDED_BOARD_MISSING,
    EMBEDDED_BOARD_ORIGIN,
    EMBEDDED_BOARD_PLACED,
    EMBEDDED_BOARD_REASON,
    EMBEDDED_BOARD_UNREADABLE,
)
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.core.ids import derived_id, is_id, parse_id
from fenolite.model import replicate
from fenolite.model.board import Layer
from fenolite.model.circuit import Circuit, NetClass
from fenolite.model.design import Design

BACKEND = "altium-array"
"""The backend of the ids of the copies: ``derived_id(<prefix>, BACKEND, "array<n>:<row>.<col>/<id>")``, rows
and columns counted from 1 at the lower left."""
EDGE = "Edge.Cuts"
QUARTER = 90_000_000
TURNS = {0: 0, 90: QUARTER}
"""The array rotations whose placement is measured (degrees), and the turn each gives the copies."""
ORIGIN_TOLERANCE = 1_000
"""How far (nm) the referenced board's origin may lie from its shape's lower-left corner: the measured
boards' origins lie within 1 µm of it (S-1592)."""
STATUS_REASONS = {
    "missing": EMBEDDED_BOARD_MISSING,
    "unreadable": EMBEDDED_BOARD_UNREADABLE,
    "absolute": EMBEDDED_BOARD_ABSOLUTE,
}


@dataclass(frozen=True)
class ArrayItem:
    """One array as the report names it: ``item`` is ``<board>#<n>:<document> <columns>x<rows>``; ``placed``
    tells a placed array (a change) from a refused one (a loss)."""

    item: str
    reason: str
    placed: bool = False


ReferenceStatus = Literal["read", "missing", "unreadable", "absolute"]
"""How the PCB document that an Embedded Board Array references reads (change c0386, task 2.1)."""


def referenced_document(panel: Path, document: str) -> tuple[Path | None, ReferenceStatus]:
    """The PCB document that an array of the board document ``panel`` references by ``DOCUMENTPATH``
    (``document``), taken relative to ``panel``'s folder with either separator, and how it reads: ``read``,
    ``missing`` (no file there), ``unreadable`` (not a PCB document that Fenolite reads) or ``absolute`` (a
    drive, share or root path, which is not followed: S-1422 measured relative paths only)."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc

    if not document or PureWindowsPath(document).anchor or document.startswith(("/", "\\")):
        return None, "absolute"
    target = panel.parent.joinpath(*(part for part in re.split(r"[\\/]", document) if part))
    if not target.is_file():
        return None, "missing"
    try:
        read_pcbdoc(target.read_bytes(), file=target.name, strict=True)
    except (FormatError, OSError, ValueError):
        return target, "unreadable"
    return target, "read"


def _nm(units: Fraction) -> int:
    return units_length(units)[0]


def shape_corner(vertices: Sequence[OutlineVertex]) -> tuple[Fraction, Fraction] | None:
    """The lower-left corner (units, Y up) of the board shape ``vertices``: the least x and y of its
    vertices and of the quarter points that its arcs pass through; ``None`` for fewer than three vertices."""
    if len(vertices) < 3:
        return None
    xs = [v.x for v in vertices]
    ys = [v.y for v in vertices]
    for v in vertices:
        if v.kind == 0 or v.radius <= 0:
            continue
        sweep = (v.end_angle - v.start_angle) % 360 or 360
        for angle, (dx, dy) in ((0, (1, 0)), (90, (0, 1)), (180, (-1, 0)), (270, (0, -1))):
            if (angle - v.start_angle) % 360 <= sweep:
                xs.append(v.cx + dx * v.radius)
                ys.append(v.cy + dy * v.radius)
    return min(xs), min(ys)


def _turn(rotation: float) -> int | None:
    for degrees, turn in TURNS.items():
        if abs((rotation - degrees + 180) % 360 - 180) < 1e-9:
            return turn
    return None


@dataclass(frozen=True)
class _Board:
    design: Design
    origin: Point
    """The referenced board's origin in the model's frame (Y down)."""


def _referenced(target: Path) -> tuple[_Board | None, str | None]:
    """The referenced board, or the reason that refuses its copies."""
    from fenolite.backends.altium.adapter import import_board
    from fenolite.backends.altium.read.pcb import read_pcbdoc

    data = target.read_bytes()
    doc = read_pcbdoc(data, file=target.name, strict=True)
    corner = shape_corner(doc.board.outline)
    origin = doc.board.origin
    if corner is None or origin is None:
        return None, EMBEDDED_BOARD_ORIGIN
    if any(abs(_nm(a) - _nm(b)) > ORIGIN_TOLERANCE for a, b in zip(origin, corner, strict=True)):
        return None, EMBEDDED_BOARD_ORIGIN
    design = import_board(doc, file=target.name, sha256=hashlib.sha256(data).hexdigest())
    board = design.board
    if board is None or any(g.layer == EDGE and g.kind == "polygon" for g in board.graphics):
        return None, EMBEDDED_BOARD_CUTOUT
    return _Board(design, Point(_nm(origin[0]), -_nm(origin[1]))), None


def _copy(
    source: Design, key: str, k: int, place: Any, turn: int, classes: Mapping[str, str]
) -> tuple[Circuit, dict[str, tuple[Any, ...]]]:
    """One copy of ``source``: its circuit (ids derived from ``key``, nets ``B<k>/``, designators ``_B<k>``,
    component paths in a module ``B<k>``, each net class id replaced by ``classes``) and its board items
    moved by ``place`` and ``turn``, the board shape left out."""
    board = source.board
    assert board is not None
    found: set[str] = set()
    replicate.entity_ids(source.circuit, found)
    replicate.entity_ids(board, found)
    mapping = {old: derived_id(parse_id(old)[0], BACKEND, f"{key}/{old}") for old in found if is_id(old)}
    mapping.update(classes)
    circuit = cast(Circuit, replicate.renamed(source.circuit, mapping))
    circuit = dataclasses.replace(
        circuit,
        components=tuple(
            dataclasses.replace(c, ref=f"{c.ref}_B{k}" if c.ref else c.ref, path=f"B{k}/{c.path or c.ref}")
            for c in circuit.components
        ),
        nets=tuple(dataclasses.replace(n, name=f"B{k}/{n.name}") if n.name else n for n in circuit.nets),
    )
    items: dict[str, tuple[Any, ...]] = {}
    for name in replicate.BOARD_ITEMS:
        values = cast("tuple[Any, ...]", getattr(board, name))
        if name == "graphics":
            values = tuple(g for g in values if g.layer != EDGE)
        items[name] = tuple(replicate.moved(replicate.renamed(v, mapping), place, turn) for v in values)
    return circuit, items


def _classes(source: Sequence[NetClass], held: list[NetClass], key: str) -> dict[str, str]:
    """The id each net class of a referenced board takes in the converted board: the board's own class of
    the same name, else the class added once to ``held`` with an id derived from the array's ``key``."""
    by_name = {netclass.name: netclass.id for netclass in held}
    found: dict[str, str] = {}
    for netclass in source:
        if netclass.name not in by_name:
            added = dataclasses.replace(
                netclass, id=derived_id(parse_id(netclass.id)[0], BACKEND, f"{key}/{netclass.id}")
            )
            held.append(added)
            by_name[netclass.name] = added.id
        found[netclass.id] = by_name[netclass.name]
    return found


def _copper(layers: Iterable[Layer]) -> set[str]:
    return {layer.name for layer in layers if layer.kind == "copper"}


def _placer(anchor: Point, origin: Point, step: Point, turn: int) -> Any:
    def place(p: Point) -> Point:
        dx, dy = p.x + step.x - origin.x, p.y + step.y - origin.y
        if turn:
            dx, dy = dy, -dx  # a counter-clockwise quarter turn on screen, as geometry.transform.rotate_point
        return Point(anchor.x + dx, anchor.y + dy)

    return place


def array_copies(panel: Path, data: bytes, design: Design) -> tuple[Design, tuple[ArrayItem, ...]]:
    """``design``, the board of the document ``panel`` (whose bytes are ``data``), with the copies of each
    array whose placement is measured, and one item per array in record order; the document's name alone,
    refused, when its records do not read as arrays (change c0374)."""
    from fenolite.backends.altium.read.arrays import ArrayError, board_arrays

    try:
        found = board_arrays(data)
    except ArrayError:
        return design, (ArrayItem(panel.name, EMBEDDED_BOARD_REASON),)
    board = design.board
    if not found or board is None:
        return design, (ArrayItem(panel.name, EMBEDDED_BOARD_REASON),)
    layers = list(board.layers)
    components, nets = list(design.circuit.components), list(design.circuit.nets)
    netclasses = list(design.circuit.netclasses)
    items: dict[str, list[Any]] = {name: list(getattr(board, name)) for name in replicate.BOARD_ITEMS}
    out: list[ArrayItem] = []
    k = 0
    for n, array in enumerate(found, 1):
        target, status = referenced_document(panel, array.document)
        named = re.split(r"[\\/]", array.document)[-1] if status == "absolute" else array.document
        item = f"{panel.name}#{n}:{named} {array.cols}x{array.rows}"
        turn = _turn(array.rotation)
        if status != "read" or target is None:
            out.append(ArrayItem(item, STATUS_REASONS[status]))
            continue
        if array.mirrored:
            out.append(ArrayItem(item, EMBEDDED_BOARD_MIRRORED))
            continue
        if turn is None:
            out.append(ArrayItem(item, EMBEDDED_BOARD_ANGLE))
            continue
        referenced, reason = _referenced(target)
        if referenced is None:
            out.append(ArrayItem(item, reason or EMBEDDED_BOARD_REASON))
            continue
        source_board = referenced.design.board
        assert source_board is not None
        if not _copper(source_board.layers) <= _copper(layers):
            out.append(ArrayItem(item, EMBEDDED_BOARD_LAYERS))
            continue
        held = {layer.name for layer in layers}
        layers += [
            dataclasses.replace(layer, id=derived_id(parse_id(layer.id)[0], BACKEND, f"array{n}/{layer.id}"))
            for layer in source_board.layers
            if layer.name not in held
        ]
        classes = _classes(referenced.design.circuit.netclasses, netclasses, f"array{n}")
        anchor = Point(_nm(array.x), -_nm(array.y))
        for r in range(array.rows):
            for c in range(array.cols):
                k += 1
                step = Point(_nm(c * array.col_pitch), -_nm(r * array.row_pitch))
                place = _placer(anchor, referenced.origin, step, turn)
                key = f"array{n}:{r + 1}.{c + 1}"
                circuit, copied = _copy(referenced.design, key, k, place, turn, classes)
                components += circuit.components
                nets += circuit.nets
                for name, values in copied.items():
                    items[name] += values
        out.append(ArrayItem(item, EMBEDDED_BOARD_PLACED, placed=True))
    if not any(entry.placed for entry in out):
        return design, tuple(out)
    circuit = dataclasses.replace(
        design.circuit, components=tuple(components), nets=tuple(nets), netclasses=tuple(netclasses)
    )
    placed = dataclasses.replace(board, layers=tuple(layers), **{name: tuple(v) for name, v in items.items()})
    return dataclasses.replace(design, circuit=circuit, board=placed), tuple(out)


__all__ = [
    "BACKEND",
    "ORIGIN_TOLERANCE",
    "ArrayItem",
    "ReferenceStatus",
    "array_copies",
    "referenced_document",
    "shape_corner",
]
