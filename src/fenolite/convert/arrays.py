# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copies of an Altium Embedded Board Array in a conversion to KiCad (capability design-conversion,
"Copies of an embedded board array"; changes c0386 and c0428).

Altium places copy (c, r) of an array (columns and rows counted from 0 at the lower left) so that a point
``P`` of the referenced board lies at ``(X, Y) + T((c * COLSPACING, r * ROWSPACING) + P - O)``, with ``O``
the referenced board's reference point and ``T`` the identity, or a counter-clockwise quarter turn about
``(X, Y)`` for ``ROTATION`` 90 (S-1592, ``docs/formats/altium/pcb-document.md``, "Embedded board arrays").
The rule is measured for an unmirrored array turned by 0 or 90 degrees whose referenced board has its
origin at the lower-left corner of its shape. Change c0428 extends it, each extension a ``changed`` reason
that names it as inferred: a turn of 180 or 270 degrees turns the whole array about ``(X, Y)`` as the
quarter turn does; ``O`` is the board's origin when the array links its location to it (``ORIGINMODE`` 0,
S-0790) and the lower-left corner of the board's shape when it does not. Each placed array's copies join
the converted board: every id derived from the array and the copy, every net named ``B<k>/<name>``, every
designator ``<ref>_B<k>`` and every part in the sheet ``B<k>`` of the generated schematic, with ``k``
counting the copies of all arrays from 1. A copy's zones take the outlines of their records in the
referenced document before they are moved, and its footprints' embedded models are read from that document
(``Copies``). A mirrored array, an angle that is no multiple of 90 degrees and a referenced document that
is not found stay refused ``embedded-board`` losses, the reason naming what is not measured.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path, PureWindowsPath
from typing import Any, Literal, TypeVar, cast

from fenolite.backends.altium.adapter.units import units_length
from fenolite.backends.altium.read.pcbstack import OutlineVertex
from fenolite.convert.report import (
    EMBEDDED_BOARD_ABSOLUTE,
    EMBEDDED_BOARD_ANGLE,
    EMBEDDED_BOARD_CORNER,
    EMBEDDED_BOARD_FOUND,
    EMBEDDED_BOARD_LAYERS,
    EMBEDDED_BOARD_LINKED,
    EMBEDDED_BOARD_MIRRORED,
    EMBEDDED_BOARD_MISSING,
    EMBEDDED_BOARD_ORIGIN,
    EMBEDDED_BOARD_PLACED,
    EMBEDDED_BOARD_REASON,
    EMBEDDED_BOARD_TURNED,
    EMBEDDED_BOARD_UNREADABLE,
)
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.core.ids import derived_id, is_id, parse_id
from fenolite.model import replicate
from fenolite.model.board import FootprintInstance, Layer
from fenolite.model.circuit import Circuit, NetClass
from fenolite.model.design import Design

BACKEND = "altium-array"
"""The backend of the ids of the copies: ``derived_id(<prefix>, BACKEND, "array<n>:<row>.<col>/<id>")``, rows
and columns counted from 1 at the lower left."""
EDGE = "Edge.Cuts"
QUARTER = 90_000_000
TURNS = {0: 0, 90: QUARTER, 180: 2 * QUARTER, 270: 3 * QUARTER}
"""The array rotations whose copies are placed (degrees), and the turn each gives them: 0 and 90 are
measured (S-1592), 180 and 270 inferred from the quarter turn (change c0428)."""
MEASURED_TURNS = frozenset({0, QUARTER})
ORIGIN_TOLERANCE = 1_000
"""How far (nm) the referenced board's origin may lie from its shape's lower-left corner: the measured
boards' origins lie within 1 µm of it (S-1592)."""
STATUS_REASONS = {
    "missing": EMBEDDED_BOARD_MISSING,
    "unreadable": EMBEDDED_BOARD_UNREADABLE,
    "absolute": EMBEDDED_BOARD_ABSOLUTE,
}
FOUND = {
    "project": "relative to the project's folder",
    "name": "by its file name beside the board's document or in the project's folder",
    "stored": "at the absolute path the array stores",
}
"""How a referenced document that is not at its relative path is found (change c0428), as the report
says it."""


@dataclass(frozen=True)
class ArrayItem:
    """One array as the report names it: ``item`` is ``<board>#<n>:<document> <columns>x<rows>``; ``placed``
    tells a placed array (a change) from a refused one (a loss)."""

    item: str
    reason: str
    placed: bool = False


ReferenceStatus = Literal["read", "missing", "unreadable", "absolute"]
"""How the PCB document that an Embedded Board Array references reads (change c0386, task 2.1)."""


def _parts(document: str) -> list[str]:
    return [part for part in re.split(r"[\\/]", document) if part]


def _candidates(panel: Path, document: str, root: Path | None) -> list[tuple[Path, str]]:
    """Where the document ``document`` of an array of ``panel`` may be, in order, each with how it is
    found: relative to the panel's folder, relative to the project's folder ``root``, by its file name in
    either, and at the absolute path stored. Folder and file names match without letter case, as the
    project reader's do."""
    from fenolite.backends.altium.read.project import locate

    absolute = bool(PureWindowsPath(document).anchor) or document.startswith(("/", "\\"))
    parts = _parts(document)
    found: list[tuple[Path, str]] = []
    folders = [panel.parent, *([root] if root is not None and root != panel.parent else [])]
    if not absolute and parts:
        for n, folder in enumerate(folders):
            hit = locate(folder, "/".join(parts))
            if hit is not None:
                found.append((hit, "relative" if n == 0 else "project"))
    if parts:
        for folder in folders:
            hit = locate(folder, parts[-1])
            if hit is not None:
                found.append((hit, "name"))
    if absolute and Path(document).is_file():
        found.append((Path(document), "stored"))
    return found


def find_document(
    panel: Path, document: str, root: Path | None = None
) -> tuple[Path | None, ReferenceStatus, str]:
    """The PCB document that an array of the board document ``panel`` references by ``DOCUMENTPATH``
    (``document``), how it reads and how it was found (``_candidates``, change c0428): ``read``, ``missing``
    (found nowhere), ``unreadable`` (not a PCB document that Fenolite reads) or ``absolute`` (an absolute
    path that is found nowhere). ``root`` is the project's folder."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc

    candidates = _candidates(panel, document, root)
    if not candidates:
        absolute = not document or PureWindowsPath(document).anchor or document.startswith(("/", "\\"))
        return None, "absolute" if absolute else "missing", ""
    target, how = candidates[0]
    try:
        read_pcbdoc(target.read_bytes(), file=target.name, strict=True)
    except (FormatError, OSError, ValueError):
        return target, "unreadable", how
    return target, "read", how


def referenced_document(
    panel: Path, document: str, root: Path | None = None
) -> tuple[Path | None, ReferenceStatus]:
    """``find_document`` without how the document was found (change c0386)."""
    target, status, _how = find_document(panel, document, root)
    return target, status


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
    """The referenced board's reference point in the model's frame (Y down)."""
    reason: str = ""
    """The inferred reference point's ``changed`` reason; empty when the placement is measured."""
    outlined: tuple[str, ...] = ()
    dropped: tuple[tuple[str, str], ...] = ()
    """The zones that the referenced document's polygon records outline, and those they do not, each with
    its reason."""


def _referenced(target: Path, linked: bool) -> tuple[_Board | None, str | None]:
    """The referenced board, or the reason that refuses its copies. Its reference point is its origin when
    that lies within 1 µm of its shape's lower-left corner (measured, S-1592); else the origin when the array
    links its location to it, and the corner when it does not (inferred, change c0428)."""
    from fenolite.backends.altium.adapter import import_board
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.convert.altium_to_kicad import arc_outlines

    data = target.read_bytes()
    doc = read_pcbdoc(data, file=target.name, strict=True)
    corner = shape_corner(doc.board.outline)
    origin = doc.board.origin
    if corner is None or (origin is None and linked):
        return None, EMBEDDED_BOARD_ORIGIN
    reason = ""
    point = origin
    if origin is None or any(
        abs(_nm(a) - _nm(b)) > ORIGIN_TOLERANCE for a, b in zip(origin, corner, strict=True)
    ):
        point, reason = (origin, EMBEDDED_BOARD_LINKED) if linked else (corner, EMBEDDED_BOARD_CORNER)
    assert point is not None
    design = import_board(doc, file=target.name, sha256=hashlib.sha256(data).hexdigest())
    board = design.board
    if board is None:
        return None, EMBEDDED_BOARD_REASON
    design, outlined, dropped = arc_outlines(design, doc)
    return _Board(design, Point(_nm(point[0]), -_nm(point[1])), reason, outlined, dropped), None


def _copy(
    source: Design, key: str, k: int, place: Any, turn: int, classes: Mapping[str, str]
) -> tuple[Circuit, dict[str, tuple[Any, ...]], dict[str, str]]:
    """One copy of ``source``: its circuit (ids derived from ``key``, nets ``B<k>/``, designators ``_B<k>``,
    component paths in a module ``B<k>``, each net class id replaced by ``classes``), its board items
    moved by ``place`` and ``turn``, the board shape left out and its cut-outs (closed ``Edge.Cuts``
    polygons, change c0428) kept, and the id each source id takes."""
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
            values = tuple(g for g in values if g.layer != EDGE or g.kind == "polygon")
        items[name] = tuple(replicate.moved(replicate.renamed(v, mapping), place, turn) for v in values)
    return circuit, items, mapping


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
        for _ in range(turn // QUARTER):
            dx, dy = dy, -dx  # a counter-clockwise quarter turn on screen, as geometry.transform.rotate_point
        return Point(anchor.x + dx, anchor.y + dy)

    return place


_T = TypeVar("_T")


def _none(kind: type[_T]) -> Mapping[str, _T]:
    """An empty mapping of ``kind`` values (typed for the defaults of ``Copies``)."""
    return {}


@dataclass(frozen=True)
class Copies:
    """What the copies of a board's arrays add to a conversion (change c0428): the design with the copies,
    one item per array, the copied zones outlined from the referenced documents' records and those dropped,
    the copied board cut-outs, the referenced documents by file name, and each copied footprint's source
    footprint, in whose frame the referenced document gives its embedded models."""

    design: Design
    items: tuple[ArrayItem, ...]
    outlined: tuple[str, ...] = ()
    dropped: tuple[tuple[str, str], ...] = ()
    cutouts: tuple[str, ...] = ()
    """The copied board cut-outs (closed ``Edge.Cuts`` polygons of the referenced boards)."""
    documents: Mapping[str, Path] = dataclasses.field(default_factory=lambda: _none(Path))
    frames: Mapping[str, FootprintInstance] = dataclasses.field(
        default_factory=lambda: _none(FootprintInstance)
    )


def array_copies(
    panel: Path, data: bytes, design: Design, root: Path | None = None
) -> tuple[Design, tuple[ArrayItem, ...]]:
    """``copies`` without what the copies add besides the design and the items (change c0386)."""
    found = copies(panel, data, design, root)
    return found.design, found.items


def copies(panel: Path, data: bytes, design: Design, root: Path | None = None) -> Copies:  # noqa: C901, PLR0912, PLR0915
    """``design``, the board of the document ``panel`` (whose bytes are ``data``), with the copies of each
    array that is placed, and one item per array in record order; the document's name alone, refused, when
    its records do not read as arrays (change c0374). ``root`` is the project's folder, where a referenced
    document is also looked for (change c0428)."""
    from fenolite.backends.altium.read.arrays import ArrayError, board_arrays

    try:
        found = board_arrays(data)
    except ArrayError:
        return Copies(design, (ArrayItem(panel.name, EMBEDDED_BOARD_REASON),))
    board = design.board
    if not found or board is None:
        return Copies(design, (ArrayItem(panel.name, EMBEDDED_BOARD_REASON),))
    layers = list(board.layers)
    components, nets = list(design.circuit.components), list(design.circuit.nets)
    netclasses = list(design.circuit.netclasses)
    items: dict[str, list[Any]] = {name: list(getattr(board, name)) for name in replicate.BOARD_ITEMS}
    out: list[ArrayItem] = []
    outlined: list[str] = []
    dropped: list[tuple[str, str]] = []
    cutouts: list[str] = []
    documents: dict[str, Path] = {}
    frames: dict[str, FootprintInstance] = {}
    k = 0
    for n, array in enumerate(found, 1):
        target, status, how = find_document(panel, array.document, root)
        stored = bool(PureWindowsPath(array.document).anchor) or array.document.startswith(("/", "\\"))
        named = _parts(array.document)[-1] if stored and _parts(array.document) else array.document
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
        referenced, reason = _referenced(target, array.linked)
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
        documents[target.name] = target
        for r in range(array.rows):
            for c in range(array.cols):
                k += 1
                step = Point(_nm(c * array.col_pitch), -_nm(r * array.row_pitch))
                place = _placer(anchor, referenced.origin, step, turn)
                key = f"array{n}:{r + 1}.{c + 1}"
                circuit, copied, mapping = _copy(referenced.design, key, k, place, turn, classes)
                components += circuit.components
                nets += circuit.nets
                for name, values in copied.items():
                    items[name] += values
                outlined += [mapping[z] for z in referenced.outlined if z in mapping]
                # a dropped zone left the referenced design: its copy's id is derived as the others' are
                dropped += [
                    (derived_id(parse_id(z)[0], BACKEND, f"{key}/{z}"), why)
                    for z, why in referenced.dropped
                    if is_id(z)
                ]
                cutouts += [g.id for g in copied["graphics"] if g.layer == EDGE]
                frames.update({mapping[fp.id]: fp for fp in source_board.footprints if fp.id in mapping})
        reasons = [EMBEDDED_BOARD_PLACED]
        if how != "relative":
            reasons.append(EMBEDDED_BOARD_FOUND.format(how=FOUND[how]))
        if referenced.reason:
            reasons.append(referenced.reason)
        if turn not in MEASURED_TURNS:
            reasons.append(EMBEDDED_BOARD_TURNED)
        out.append(ArrayItem(item, "; ".join(reasons), placed=True))
    if not any(entry.placed for entry in out):
        return Copies(design, tuple(out))
    circuit = dataclasses.replace(
        design.circuit, components=tuple(components), nets=tuple(nets), netclasses=tuple(netclasses)
    )
    placed = dataclasses.replace(board, layers=tuple(layers), **{name: tuple(v) for name, v in items.items()})
    return Copies(
        dataclasses.replace(design, circuit=circuit, board=placed),
        tuple(out),
        tuple(outlined),
        tuple(dropped),
        tuple(cutouts),
        documents,
        frames,
    )


__all__ = [
    "BACKEND",
    "ORIGIN_TOLERANCE",
    "ArrayItem",
    "Copies",
    "ReferenceStatus",
    "array_copies",
    "copies",
    "find_document",
    "referenced_document",
    "shape_corner",
]
