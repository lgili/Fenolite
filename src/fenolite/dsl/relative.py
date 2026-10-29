# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement in code: relative requests, edge expressions, block poses and layout strategies
(``docs/dsl.md``, "Relative placement" and "Block layout"; change c0255, capability design-dsl).

A script cannot measure a footprint: ``dsl`` imports no geometry and reads no library. So ``place()`` with a
reference (``right_of=u1``, ``left=board.left + mm(2)``, ``by=c5.pad(1)``) records a request as plain data,
and the build resolves it after the footprints are known (``fenolite.placement.relative``). This module
holds the request types, the edge expressions, the board reference, the four strategies and the
conversions that turn a design's requests into plain data keyed by path.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, cast

from fenolite.core.units import Nm, Udeg
from fenolite.dsl.errors import DslError
from fenolite.dsl.units import Length, as_nm, as_udeg

if TYPE_CHECKING:
    from fenolite.dsl.block import Block
    from fenolite.dsl.design import Design
    from fenolite.dsl.part import Part

EDGES: tuple[str, ...] = ("left", "right", "top", "bottom", "center_x", "center_y")
"""The edges of a reference, and the edge keys of ``place()``."""
X_EDGES: tuple[str, ...] = ("left", "right", "center_x")
Y_EDGES: tuple[str, ...] = ("top", "bottom", "center_y")
RELATIONS: tuple[str, ...] = ("right_of", "left_of", "above", "below")
"""The relations of ``place()``: the first two set X, the last two Y."""
X_RELATIONS: tuple[str, ...] = ("right_of", "left_of")
ALIGNS: tuple[str, ...] = ("center", "start", "end")
"""How a relation aligns the subject on the other axis."""
RefKind = Literal["part", "pad", "block", "board"]


class Edges:
    """The six edges of a placement reference as edge expressions (``u1.right``, ``board.left``)."""

    __slots__ = ()

    @property
    def left(self) -> EdgeExpr:
        return EdgeExpr(self, "left", 0)

    @property
    def right(self) -> EdgeExpr:
        return EdgeExpr(self, "right", 0)

    @property
    def top(self) -> EdgeExpr:
        return EdgeExpr(self, "top", 0)

    @property
    def bottom(self) -> EdgeExpr:
        return EdgeExpr(self, "bottom", 0)

    @property
    def center_x(self) -> EdgeExpr:
        return EdgeExpr(self, "center_x", 0)

    @property
    def center_y(self) -> EdgeExpr:
        return EdgeExpr(self, "center_y", 0)


def _length_text(value: int) -> str:
    """``value`` nanometres as millimetres with no trailing zero: ``500000`` is ``0.5mm``."""
    sign = "-" if value < 0 else ""
    whole, rest = divmod(abs(value), 1_000_000)
    if not rest:
        return f"{sign}{whole}mm"
    return f"{sign}{whole}.{str(rest).rjust(6, '0').rstrip('0')}mm"


def _angle_text(value: int) -> str:
    whole, rest = divmod(value, 1_000_000)
    return str(whole) if not rest else f"{whole}.{str(rest).rjust(6, '0').rstrip('0')}"


@dataclass(frozen=True, eq=False)
class EdgeExpr:
    """An edge of a reference plus or minus a length: ``board.left + mm(2)``. Nothing else is an edge
    expression: two references never combine."""

    target: object
    edge: str
    offset: Nm = 0

    def _shift(self, other: object, sign: int, op: str) -> EdgeExpr:
        if isinstance(other, EdgeExpr):
            raise DslError(
                f"{op} of two edges is not an edge expression; write one edge plus or minus a length"
            )
        if not isinstance(other, (Length, str)):
            raise DslError(f"an edge takes {op} a length (mm(2)), not {other!r}")
        return EdgeExpr(self.target, self.edge, self.offset + sign * as_nm(other, name=f"edge {op}"))

    def __add__(self, other: object) -> EdgeExpr:
        return self._shift(other, 1, "+")

    def __sub__(self, other: object) -> EdgeExpr:
        return self._shift(other, -1, "-")

    def _refused(self, *_: object) -> EdgeExpr:
        raise DslError(
            f"an edge expression is an edge plus or minus a length, such as board.left + mm(2); "
            f"{self.edge} cannot be scaled, negated or combined"
        )

    __radd__ = _refused
    __rsub__ = _refused
    __mul__ = _refused
    __rmul__ = _refused
    __truediv__ = _refused
    __floordiv__ = _refused
    __neg__ = _refused


class BoardRef(Edges):
    """The board as a placement reference: what ``Design.board`` returns and ``design.board_ref`` gives.
    Its box is the outline's box in the frame of ``place()``."""

    __slots__ = ("design",)

    def __init__(self, design: Design) -> None:
        self.design = design

    def __repr__(self) -> str:
        return "BoardRef()"


# --- strategies -----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Strategy:
    """A layout strategy of a frame: ``kind`` (``row``, ``column``, ``grid`` or ``pack``), the gap, the
    alignment of a row or column, the columns of a grid, the width of a pack and the origin ``at`` in the
    frame (nanometres)."""

    kind: Literal["row", "column", "grid", "pack"]
    gap: Nm = 0
    align: str = "start"
    columns: int = 0
    width: Nm = 0
    at: tuple[Nm, Nm] = (0, 0)

    def text(self) -> str:
        """The strategy as the script wrote it, canonically: ``row(gap=1mm)``."""
        pieces: list[str] = []
        if self.kind == "grid":
            pieces.append(f"columns={self.columns}")
        if self.kind == "pack":
            pieces.append(f"width={_length_text(self.width)}")
        if self.gap:
            pieces.append(f"gap={_length_text(self.gap)}")
        if self.kind in ("row", "column") and self.align != "start":
            pieces.append(f"align={self.align}")
        if self.at != (0, 0):
            pieces.append(f"at=({_length_text(self.at[0])}, {_length_text(self.at[1])})")
        return f"{self.kind}({', '.join(pieces)})"


@dataclass(frozen=True, slots=True)
class Reuse:
    """A block layout reuse: the reference board as written, the folder it is relative to (the folder of
    the file that defines the block for ``b.layout``; ``None`` for an instance, whose path is relative to
    the script) and whether the copper is copied."""

    path: str
    root: str | None
    copper: bool = False

    def text(self) -> str:
        return f"reuse={self.path}" + (" copper=true" if self.copper else "")


def _gap(value: object, what: str) -> Nm:
    gap = as_nm(value, name=f"{what}: gap")
    if gap < 0:
        raise DslError(f"{what}: gap must not be negative")
    return gap


def _at(value: object, what: str) -> tuple[Nm, Nm]:
    if value is None:
        return (0, 0)
    if not isinstance(value, tuple) or len(cast("tuple[object, ...]", value)) != 2:
        raise DslError(f"{what}: at is a pair of lengths (x, y), not {value!r}")
    pair = cast("tuple[object, object]", value)
    return (as_nm(pair[0], name=f"{what}: at x"), as_nm(pair[1], name=f"{what}: at y"))


def _align(value: object, what: str) -> str:
    if value not in ALIGNS:
        raise DslError(f"{what}: align must be one of {', '.join(ALIGNS)}, not {value!r}")
    return cast(str, value)


def row(gap: object = Length(0), align: str = "start", at: object = None) -> Strategy:
    """The frame's unplaced parts left to right from ``at``, ``gap`` apart, aligned on their top edges
    (``start``), centres or bottom edges (``end``)."""
    return Strategy("row", _gap(gap, "row()"), _align(align, "row()"), at=_at(at, "row()"))


def column(gap: object = Length(0), align: str = "start", at: object = None) -> Strategy:
    """The frame's unplaced parts top to bottom from ``at``, ``gap`` apart, aligned on their left edges
    (``start``), centres or right edges (``end``)."""
    return Strategy("column", _gap(gap, "column()"), _align(align, "column()"), at=_at(at, "column()"))


def grid(columns: int, gap: object = Length(0), at: object = None) -> Strategy:
    """Cells of the largest box's size plus ``gap``, ``columns`` per row, each box centred in its cell."""
    if isinstance(columns, bool) or not isinstance(columns, int) or columns <= 0:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"grid(): columns must be a positive int, not {columns!r}")
    return Strategy("grid", _gap(gap, "grid()"), columns=columns, at=_at(at, "grid()"))


def pack(width: object, gap: object = Length(0), at: object = None) -> Strategy:
    """Shelf packing within ``width``: tallest boxes first, each right of the previous while it fits,
    else on a new shelf."""
    wide = as_nm(width, name="pack(): width")
    if wide <= 0:
        raise DslError("pack(): width must be positive")
    return Strategy("pack", _gap(gap, "pack()"), width=wide, at=_at(at, "pack()"))


# --- requests -------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RefKey:
    """A placement reference as plain data: a part, one of its pads, a block instance or the board, by
    path."""

    kind: RefKind
    path: str = ""
    pad: str | None = None
    index: int | None = None

    def text(self) -> str:
        if self.kind == "board":
            return "board"
        if self.kind == "pad":
            more = "" if self.index is None else f", index={self.index}"
            return f"{self.path}.pad({self.pad}{more})"
        return self.path

    @property
    def owner(self) -> str:
        """The path of the part or block whose placement the reference needs (``""`` for the board)."""
        return self.path


@dataclass(frozen=True, slots=True)
class Axis:
    """How one axis of a request is set: ``value`` (``x``/``y``: a coordinate of the frame), ``edge`` (an
    edge key at a coordinate, or at an edge of ``ref`` plus ``value``), ``relation`` (a relation to
    ``ref`` with the gap ``value``) or ``align`` (the cross axis of a relation, ``key`` the alignment)."""

    kind: Literal["value", "edge", "relation", "align"]
    key: str
    value: Nm = 0
    ref: RefKey | None = None
    ref_edge: str | None = None

    def text(self) -> str:
        if self.kind == "value":
            return f"{self.key}={_length_text(self.value)}"
        if self.kind == "edge":
            if self.ref is None:
                return f"{self.key}={_length_text(self.value)}"
            shift = ""
            if self.value:
                shift = ("+" if self.value > 0 else "-") + _length_text(abs(self.value))
            return f"{self.key}={self.ref.text()}.{self.ref_edge}{shift}"
        if self.kind == "relation":
            assert self.ref is not None
            return f"{self.key}={self.ref.text()}" + (
                f" gap={_length_text(self.value)}" if self.value else ""
            )
        return "" if self.key == "center" else f"align={self.key}"


@dataclass(frozen=True, slots=True)
class RelativeRequest:
    """A placement request with a reference, as plain data: the subject's path, whether it is a ``part``
    or a ``block`` (a pose), the frame it is written in (the block path, ``""`` at the top), how each axis
    is set, the rotation, the side, the lock and the subject's own pad of ``by``."""

    path: str
    subject: Literal["part", "block"]
    frame: str
    x: Axis
    y: Axis
    rotation: Udeg = 0
    side: Literal["top", "bottom"] = "top"
    locked: bool = False
    by: str | None = None
    by_index: int | None = None

    def references(self) -> tuple[RefKey, ...]:
        """The references of the request, X first, each once."""
        found: list[RefKey] = []
        for axis in (self.x, self.y):
            if axis.ref is not None and axis.ref not in found:
                found.append(axis.ref)
        return tuple(found)

    def text(self) -> str:
        """The request as canonical text: ``right_of=U1.pad(VDD) gap=0.5mm by=pad(1)``."""
        relation = next((a for a in (self.x, self.y) if a.kind == "relation"), None)
        pieces: list[str] = []
        if relation is not None:
            pieces.append(relation.text())
            cross = self.y if relation is self.x else self.x
            if cross.kind == "align" and cross.key != "center":
                pieces.append(cross.text())
        for axis in (self.x, self.y):
            if axis.kind in ("value", "edge"):
                pieces.append(axis.text())
        if self.rotation:
            pieces.append(f"rot={_angle_text(self.rotation)}")
        if self.side != "top":
            pieces.append(f"side={self.side}")
        if self.by is not None:
            more = "" if self.by_index is None else f", index={self.by_index}"
            pieces.append(f"by=pad({self.by}{more})")
        if self.locked:
            pieces.append("locked")
        return " ".join(pieces)


@dataclass(frozen=True, slots=True)
class LiveAxis:
    """An ``Axis`` as the call gave it, the reference still a script object."""

    kind: Literal["value", "edge", "relation", "align"]
    key: str
    value: Nm = 0
    target: object = None
    ref_edge: str | None = None


@dataclass(frozen=True, slots=True)
class LiveRequest:
    """A relative request as the call gave it (``Part.place`` or ``BlockInstance.place``)."""

    x: LiveAxis
    y: LiveAxis
    rotation: Udeg
    side: Literal["top", "bottom"]
    locked: bool
    by: str | None = None
    by_index: int | None = None


@dataclass(frozen=True, slots=True)
class Pose:
    """An absolute block pose: a translation and a rotation in the parent frame, and the lock."""

    x: Nm
    y: Nm
    rotation: Udeg
    locked: bool


def parse_request(
    what: str,
    *,
    x: object,
    y: object,
    rot: object,
    side: str,
    locked: bool,
    keys: Mapping[str, object],
    gap: object,
    align: object,
    by: object = None,
    by_owner: object = None,
) -> LiveRequest | None:
    """The request of a ``place()`` call with references, or ``None`` when the call names no relation and
    no edge key (an absolute placement, or a turn only). Decision 3 of change c0255: each axis is set by
    exactly one source; anything else raises ``DslError`` naming the axis or the key."""
    relations = {k: keys[k] for k in RELATIONS if keys.get(k) is not None}
    edges = {k: keys[k] for k in EDGES if keys.get(k) is not None}
    if not relations and not edges:
        if gap is not None or align is not None:
            raise DslError(
                f"{what}: {'gap' if gap is not None else 'align'} belongs to a relation (right_of=...)"
            )
        if by is not None:
            raise DslError(
                f"{what}: by= places the part by one of its pads relative to a reference; give one"
            )
        return None
    if len(relations) > 1:
        raise DslError(f"{what}: one relation per call, not {' and '.join(relations)}")
    if not relations and (gap is not None or align is not None):
        raise DslError(
            f"{what}: {'gap' if gap is not None else 'align'} belongs to a relation (right_of=...)"
        )
    x_sources = [name for name in X_EDGES if name in edges] + [k for k in relations if k in X_RELATIONS]
    y_sources = [name for name in Y_EDGES if name in edges] + [k for k in relations if k not in X_RELATIONS]
    if x is not None:
        x_sources.insert(0, "x")
    if y is not None:
        y_sources.insert(0, "y")
    for axis, sources in (("X", x_sources), ("Y", y_sources)):
        if len(sources) > 1:
            raise DslError(f"{what}: the {axis} axis is set twice ({' and '.join(sources)}); give one source")
    relation = next(iter(relations), None)
    relation_x = relation in X_RELATIONS
    if not x_sources and not (relation is not None and not relation_x):
        raise DslError(f"{what}: nothing sets the X axis; give x, left, right, center_x, right_of or left_of")
    if not y_sources and not (relation is not None and relation_x):
        raise DslError(f"{what}: nothing sets the Y axis; give y, top, bottom, center_y, above or below")
    gap_nm = 0 if gap is None else as_nm(gap, name=f"{what}: gap")
    if gap_nm < 0:
        raise DslError(f"{what}: gap must not be negative")
    mode = "center" if align is None else _align(align, what)
    by_number: str | None = None
    by_index: int | None = None
    if by is not None:
        from fenolite.dsl.intents import PadRef

        if not isinstance(by, PadRef) or by.part is not by_owner:
            raise DslError(f"{what}: by must be a pad of the placed part itself (part.pad(n)), not {by!r}")
        by_number, by_index = by.number, by.index

    def axis_of(name: str, coordinate: object) -> LiveAxis:
        if name in ("x", "y"):
            return LiveAxis("value", name, as_nm(coordinate, name=f"{what}: {name}"))
        if name in RELATIONS:
            target = _target(relations[name], what, name)
            return LiveAxis("relation", name, gap_nm, target)
        given = edges[name]
        if isinstance(given, EdgeExpr):
            return LiveAxis("edge", name, given.offset, _target(given.target, what, name), given.edge)
        if not isinstance(given, (Length, str)):
            raise DslError(f"{what}: {name} takes a length or an edge expression such as board.left + mm(2)")
        return LiveAxis("edge", name, as_nm(given, name=f"{what}: {name}"))

    x_axis = axis_of(x_sources[0], x) if x_sources else None
    y_axis = axis_of(y_sources[0], y) if y_sources else None
    assert relation is not None or (x_axis is not None and y_axis is not None)
    if x_axis is None:
        x_axis = LiveAxis(
            "align", mode, 0, _target(relations[cast(str, relation)], what, cast(str, relation))
        )
    elif y_axis is None:
        y_axis = LiveAxis(
            "align", mode, 0, _target(relations[cast(str, relation)], what, cast(str, relation))
        )
    elif align is not None:
        raise DslError(f"{what}: align has no axis left to set; both axes are given")
    assert y_axis is not None
    if side not in ("top", "bottom"):
        raise DslError(f"{what}: side must be 'top' or 'bottom', not {side!r}")
    if not isinstance(locked, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"{what}: locked must be a bool")
    return LiveRequest(
        x_axis,
        y_axis,
        as_udeg(rot, name=f"{what}: rot"),
        side,
        locked,
        by_number,
        by_index,
    )


def _target(value: object, what: str, key: str) -> object:
    """A reference as a script object: a part, a pad, a block (an instance gives its block) or the board."""
    from fenolite.dsl.block import Block, BlockInstance
    from fenolite.dsl.intents import PadRef
    from fenolite.dsl.part import Part

    if isinstance(value, BlockInstance):
        return value.module
    if isinstance(value, (Part, PadRef, Block, BoardRef)):
        return value
    raise DslError(f"{what}: {key} takes a part, a pad, a block instance or the board, not {value!r}")


# --- frames and keys ------------------------------------------------------------------------------


def frame_of(obj: object) -> Block | None:
    """The innermost block holding ``obj`` (a part, or a block for its parent frame), or ``None`` at the
    top."""
    from fenolite.dsl.block import Block

    parent = getattr(obj, "parent", None)
    while parent is not None:
        if isinstance(parent, Block):
            return parent
        parent = getattr(parent, "parent", None)
    return None


def _inside(obj: object, frame: Block) -> bool:
    """Whether ``obj`` (a part or a block) lies inside the block ``frame``."""
    parent = getattr(obj, "parent", None)
    while parent is not None:
        if parent is frame:
            return True
        parent = getattr(parent, "parent", None)
    return False


def _owner(target: object) -> object:
    from fenolite.dsl.intents import PadRef

    return target.part if isinstance(target, PadRef) else target


def _label(obj: object) -> str:
    from fenolite.dsl.part import Part

    if isinstance(obj, Part):
        return obj.label
    if isinstance(obj, BoardRef):
        return "the board"
    return cast(str, getattr(obj, "path", repr(obj)))


def check_frame(subject: object, what: str, request: LiveRequest) -> None:
    """Refuse a reference that does not move with the subject: in a block body, a request references only
    parts and instances of the same block, never the board (decision 7 of change c0255)."""
    frame = frame_of(subject)
    if frame is None:
        return
    for axis in (request.x, request.y):
        target = axis.target
        if target is None:
            continue
        owner = _owner(target)
        if isinstance(owner, BoardRef) or owner is frame or not _inside(owner, frame):
            raise DslError(
                f"{what}: a block's parts reference only parts of the same block; {_label(owner)} is "
                f"outside block {frame.path}, so it would not move with the block"
            )


def _key(target: object) -> RefKey:
    from fenolite.dsl.block import Block
    from fenolite.dsl.intents import PadRef
    from fenolite.dsl.part import Part

    if isinstance(target, BoardRef):
        return RefKey("board")
    if isinstance(target, PadRef):
        return RefKey("pad", target.part.path, target.number, target.index)
    if isinstance(target, Part):
        return RefKey("part", target.path)
    assert isinstance(target, Block)
    return RefKey("block", target.path)


def _axis(live: LiveAxis) -> Axis:
    return Axis(
        live.kind, live.key, live.value, None if live.target is None else _key(live.target), live.ref_edge
    )


def to_request(
    path: str, subject: Literal["part", "block"], frame: str, live: LiveRequest
) -> RelativeRequest:
    """The plain-data request of ``live``."""
    return RelativeRequest(
        path,
        subject,
        frame,
        _axis(live.x),
        _axis(live.y),
        live.rotation,
        live.side,
        live.locked,
        live.by,
        live.by_index,
    )


def _locked(target: object, seen: set[int]) -> bool:
    """Whether a reference is stable without the board: the board, a locked part (absolute or relative,
    recursively) or a pad of one, or a block with a locked pose."""
    from fenolite.dsl.block import Block
    from fenolite.dsl.part import Part

    owner = _owner(target)
    if isinstance(owner, BoardRef):
        return True
    if id(owner) in seen:
        return True  # a cycle is the resolver's finding
    seen.add(id(owner))
    if isinstance(owner, Part):
        if owner.request is not None:
            return owner.request.locked
        live = owner.relative
        if live is None or not live.locked:
            return False
        return all(_locked(a.target, seen) for a in (live.x, live.y) if a.target is not None)
    if isinstance(owner, Block):
        pose = owner.pose
        if isinstance(pose, Pose):
            return pose.locked
        if isinstance(pose, LiveRequest) and pose.locked:
            return all(_locked(a.target, seen) for a in (pose.x, pose.y) if a.target is not None)
    return False


def _check_locked(what: str, live: LiveRequest) -> None:
    if not live.locked:
        return
    for axis in (live.x, live.y):
        if axis.target is not None and not _locked(axis.target, set()):
            raise DslError(
                f"{what}: a locked relative placement references only locked parts, locked blocks or the "
                f"board; {_label(_owner(axis.target))} is not locked"
            )


def relative_requests(design: Design) -> Mapping[str, RelativeRequest]:
    """The relative requests of the design's parts, by component path in path order. ``placements(design)``
    holds none of them. A locked request with an unlocked reference raises ``DslError``."""
    out: dict[str, RelativeRequest] = {}
    for path, part in sorted(design.parts.items()):
        live = part.relative
        if live is None:
            continue
        check_frame(part, f"part {part.label}", live)
        _check_locked(f"part {part.label}", live)
        frame = frame_of(part)
        out[path] = to_request(path, "part", "" if frame is None else frame.path, live)
    return MappingProxyType(out)


def turns(design: Design) -> Mapping[str, tuple[Udeg, Literal["top", "bottom"]]]:
    """The parts whose ``place()`` gives only ``rot`` or ``side``: a strategy places them, turned."""
    return MappingProxyType(
        {path: part.turn for path, part in sorted(design.parts.items()) if part.turn is not None}
    )


@dataclass(frozen=True, slots=True)
class BlockLayout:
    """A block instance as the placement sees it: its path, its parent frame, its pose (absolute, relative
    or ``None``), its strategy or reuse (the instance's, else the body's), where that came from, and its
    position among the parent frame's items."""

    path: str
    frame: str
    pose: Pose | RelativeRequest | None
    layout: Strategy | Reuse | None
    source: Literal["instance", "body", ""] = ""
    order: int = 0


@dataclass(frozen=True, slots=True)
class FrameItems:
    """The direct items of a frame (``""`` the top), in creation order: parts (frame ``frame``) and the
    block instances whose parent frame it is, each as ``("part", path)`` or ``("block", path)``."""

    frame: str
    items: tuple[tuple[Literal["part", "block"], str], ...] = field(default=())


def _walk(
    container: object, frame: str, found: dict[str, list[tuple[Literal["part", "block"], str]]]
) -> None:
    from fenolite.dsl.block import Block
    from fenolite.dsl.part import Part

    for child in getattr(container, "children", ()):
        if isinstance(child, Part):
            found.setdefault(frame, []).append(("part", child.path))
        elif isinstance(child, Block):
            found.setdefault(frame, []).append(("block", child.path))
            found.setdefault(child.path, [])
            _walk(child, child.path, found)
        else:
            _walk(child, frame, found)


def frames(design: Design) -> Mapping[str, FrameItems]:
    """Every frame of the design (the top ``""`` and each block instance) with its items in creation
    order; a plain module's parts belong to the frame that holds the module."""
    found: dict[str, list[tuple[Literal["part", "block"], str]]] = {"": []}
    _walk(design, "", found)
    return MappingProxyType({key: FrameItems(key, tuple(items)) for key, items in sorted(found.items())})


def block_layouts(design: Design) -> Mapping[str, BlockLayout]:
    """The pose and strategy of every block instance, by path in path order."""
    from fenolite.dsl.block import blocks

    order: dict[str, int] = {}
    for items in frames(design).values():
        for index, (kind, path) in enumerate(items.items):
            if kind == "block":
                order[path] = index
    out: dict[str, BlockLayout] = {}
    for made in blocks(design):
        frame = frame_of(made)
        frame_path = "" if frame is None else frame.path
        pose = made.pose
        plain: Pose | RelativeRequest | None
        if isinstance(pose, LiveRequest):
            what = f"block {made.path}"
            check_frame(made, what, pose)
            _check_locked(what, pose)
            plain = to_request(made.path, "block", frame_path, pose)
        else:
            plain = pose
        chosen = made.instance_layout if made.instance_layout is not None else made.body_layout
        source: Literal["instance", "body", ""] = (
            "instance" if made.instance_layout is not None else "body" if made.body_layout is not None else ""
        )
        out[made.path] = BlockLayout(made.path, frame_path, plain, chosen, source, order.get(made.path, 0))
    return MappingProxyType(out)


def top_layout(design: Design) -> Strategy | None:
    """The strategy of ``design.layout(...)``, or ``None``."""
    return design.top_strategy


def has_layout(design: Design) -> bool:
    """Whether the design asks for anything this module resolves: a relative request, a turn without a
    position, a block pose or a strategy."""
    from fenolite.dsl.block import blocks

    if design.top_strategy is not None:
        return True
    if any(part.relative is not None or part.turn is not None for part in design.parts.values()):
        return True
    return any(
        b.pose is not None or b.body_layout is not None or b.instance_layout is not None
        for b in blocks(design)
    )


def set_layout(
    current: Strategy | Reuse | None,
    strategy: object,
    reuse: object,
    copper: object,
    *,
    what: str,
    root: str | None,
    allow_reuse: bool = True,
) -> Strategy | Reuse:
    """The strategy or reuse of one ``layout()`` call; a second one on the same frame, both forms in one
    call, or a wrong type raises ``DslError``."""
    if current is not None:
        raise DslError(f"{what}: a frame has one strategy; layout() was already called ({current.text()})")
    if not isinstance(copper, bool):
        raise DslError(f"{what}: copper must be a bool, not {copper!r}")
    if reuse is not None:
        if not allow_reuse:
            raise DslError(f"{what}: reuse= belongs to a block (b.layout or inst.layout)")
        if strategy is not None:
            raise DslError(f"{what}: a frame has one strategy; give a strategy or reuse=, not both")
        if not isinstance(reuse, (str, Path)) or not str(reuse):
            raise DslError(f"{what}: reuse is the path of a board file, not {reuse!r}")
        return Reuse(Path(reuse).as_posix(), root, copper)
    if copper:
        raise DslError(f"{what}: copper=True belongs to reuse=")
    if not isinstance(strategy, Strategy):
        raise DslError(f"{what}: layout() takes row(), column(), grid(), pack() or reuse=, not {strategy!r}")
    return strategy


def block_root(block: Block) -> str | None:
    """The folder of the file that defines ``block``'s function, which ``b.layout(reuse=...)`` is
    relative to."""
    try:
        source = inspect.getsourcefile(block.definition.function)
    except TypeError:
        return None
    return None if source is None else str(Path(source).resolve().parent)


def port_nets(design: Design, block_path: str) -> Mapping[str, str]:
    """The nets of a block instance as a reference board of the block names them, after ``to_model``: each
    port of one member by its name (``VIN``), each member of a port of several as ``PORT.member``, each
    local net by its local name (``FB``) and each local net of a nested instance by its block-local path
    (``led/A``), mapped to the net name of the design (change c0255, block layout reuse)."""
    from fenolite.dsl.block import Block, blocks

    found: dict[str, str] = {}
    held = design.modules.get(block_path)
    if not isinstance(held, Block):
        return MappingProxyType(found)
    for name, port in sorted(held.ports.items()):
        members = port.members
        for member, net in members.items():
            found[name if len(members) == 1 else f"{name}.{member}"] = net.name
    for made in blocks(design):
        if made.path != block_path and not made.path.startswith(f"{block_path}/"):
            continue
        prefix = made.path[len(block_path) + 1 :]
        for name, net in sorted(made.local_nets.items()):
            found[f"{prefix}/{name}" if prefix else name] = net.name
    return MappingProxyType(dict(sorted(found.items())))


def owner_part(target: object) -> Part | None:
    """The part of a part or pad reference."""
    from fenolite.dsl.part import Part

    owner = _owner(target)
    return owner if isinstance(owner, Part) else None


__all__ = [
    "ALIGNS",
    "EDGES",
    "RELATIONS",
    "Axis",
    "BlockLayout",
    "BoardRef",
    "EdgeExpr",
    "Edges",
    "FrameItems",
    "LiveRequest",
    "Pose",
    "RefKey",
    "RelativeRequest",
    "Reuse",
    "Strategy",
    "block_layouts",
    "column",
    "frames",
    "grid",
    "has_layout",
    "pack",
    "parse_request",
    "port_nets",
    "relative_requests",
    "row",
    "top_layout",
    "turns",
]
