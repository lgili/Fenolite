# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement in code: relative requests, block poses and frame strategies resolved to integer nanometres
(change c0255; capability placement-in-code; ``docs/placement.md``, "Placement in code").

The script records requests as plain data (``fenolite.dsl.relative``); the build measures the footprints
and hands this module a ``Scene``: each part's box and pad boxes in its footprint frame, the frames (the
top and each block instance) with their items in creation order, the absolute and relative requests, the
block poses and strategies, the board's box and the start of the staging row. ``resolve`` gives the code
placement of every part it can place, in the written frame, and records how each relative request was
resolved.

Frames are resolved innermost first, each in its own coordinates: the parts with an absolute request, then
the frame's strategy (or block reuse) for the items that nothing else places, then the relative requests in
topological order of their references, ties by path. A block's box is the union of its placed parts' and
nested blocks' boxes in its frame; its pose puts that frame into the parent frame. World placements are
the frame transforms composed top-down. With ``fixed`` (the placements that the board or the edits file
decided, levels 1 to 3 of "Placement precedence"), the relative requests are resolved again against those
positions, so a follower follows a reference that was moved in KiCad; block poses stay those of the code.

Everything is integer nanometres: a box turned by other than a quarter turn is its bounds rounded
outward (``geometry.Transform.apply_bbox``), a centre is ``(a + b) // 2``, and a turned position rounds half
to even.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, cast

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.trig import ONE
from fenolite.core.units import round_half_even_div
from fenolite.geometry.shapes import BBox
from fenolite.geometry.transform import Transform
from fenolite.placement.codes import RELATIVE_EVIDENCE, layout_issue
from fenolite.placement.strategies import Item, StrategyLike, arrange

EVIDENCE = RELATIVE_EVIDENCE
"""``INFERRED`` with ``H-G-REL-RESOLVE``."""
STAGING_GAP = 2_000_000
"""The gap between two staged boxes, as the build's staging row (``lens.build.STAGING_GAP``)."""


class RefLike(Protocol):
    @property
    def kind(self) -> str: ...

    @property
    def path(self) -> str: ...

    @property
    def pad(self) -> str | None: ...

    @property
    def index(self) -> int | None: ...

    def text(self) -> str: ...


class AxisLike(Protocol):
    @property
    def kind(self) -> str: ...

    @property
    def key(self) -> str: ...

    @property
    def value(self) -> int: ...

    @property
    def ref(self) -> RefLike | None: ...

    @property
    def ref_edge(self) -> str | None: ...


class RequestLike(Protocol):
    """A relative request as ``fenolite.dsl.relative.RelativeRequest`` records it."""

    @property
    def path(self) -> str: ...

    @property
    def subject(self) -> str: ...

    @property
    def frame(self) -> str: ...

    @property
    def x(self) -> AxisLike: ...

    @property
    def y(self) -> AxisLike: ...

    @property
    def rotation(self) -> int: ...

    @property
    def side(self) -> str: ...

    @property
    def locked(self) -> bool: ...

    @property
    def by(self) -> str | None: ...

    @property
    def by_index(self) -> int | None: ...

    def text(self) -> str: ...


class BlockLike(Protocol):
    """A block instance as ``fenolite.dsl.relative.BlockLayout`` records it."""

    @property
    def path(self) -> str: ...

    @property
    def frame(self) -> str: ...

    @property
    def pose(self) -> object: ...

    @property
    def layout(self) -> object: ...

    @property
    def source(self) -> str: ...


@dataclass(frozen=True, slots=True)
class PadBox:
    """A pad in its footprint's frame: its number, its position (its centre) and its box."""

    number: str
    center: Point
    box: BBox


@dataclass(frozen=True, slots=True)
class Footprint:
    """What the resolution measures of a part: its box (the courtyard box, else the pad boxes) and its
    pads, in the footprint's frame."""

    extent: BBox
    pads: tuple[PadBox, ...] = ()


@dataclass(frozen=True, slots=True)
class Absolute:
    """An absolute request in its frame's coordinates, as the script wrote it."""

    x: int
    y: int
    rotation: int
    side: str
    locked: bool


@dataclass(frozen=True, slots=True)
class Placed:
    """A placement in the written frame: position, rotation and side."""

    at: Point
    rotation: int
    side: str


@dataclass(frozen=True, slots=True)
class Scene:
    """Everything the resolution reads. ``frames`` maps each frame (``""`` the top, else a block path) to
    its items in creation order (``("part", path)`` or ``("block", path)``); ``absolute`` holds the absolute
    requests in frame coordinates; ``reuse`` the placements of a block reuse by block path and block-local
    path, in the block's frame; ``origin`` is the written point of the top frame's ``(0, 0)``; ``board`` the
    outline's box and ``staging`` the start of the staging row, both written."""

    footprints: Mapping[str, Footprint]
    frames: Mapping[str, Sequence[tuple[str, str]]]
    absolute: Mapping[str, Absolute] = field(default_factory=lambda: MappingProxyType({}))
    relative: Mapping[str, RequestLike] = field(default_factory=lambda: MappingProxyType({}))
    turns: Mapping[str, tuple[int, str]] = field(default_factory=lambda: MappingProxyType({}))
    blocks: Mapping[str, BlockLike] = field(default_factory=lambda: MappingProxyType({}))
    origin: Point = Point(0, 0)
    top: StrategyLike | None = None
    board: BBox | None = None
    staging: Point | None = None
    reuse: Mapping[str, Mapping[str, Placed]] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class Resolved:
    """A code placement in the written frame, its lock and where it came from: ``absolute``, ``relative``,
    ``strategy``, ``reuse`` or ``group`` (a strategy group staged as one box: the build reports each of its
    parts as staged)."""

    at: Point
    rotation: int
    side: str
    locked: bool = False
    source: str = "absolute"

    @property
    def staged(self) -> bool:
        return self.source == "group"


@dataclass(frozen=True, slots=True)
class RefUse:
    """A reference as a resolution used it: its text, its box and its centre in the frame of the
    request."""

    ref: str
    box: BBox
    center: Point


@dataclass(frozen=True, slots=True)
class Record:
    """How one relative request was resolved: the subject's path, the request's text, its frame, the
    references used, and the written position, rotation and side."""

    path: str
    request: str
    frame: str
    refs: tuple[RefUse, ...]
    at: Point
    rotation: int
    side: str


@dataclass(frozen=True, slots=True)
class BlockRecord:
    """A block's resolved pose (its frame's origin and turn in the written frame), its layout's text and
    source, and whether it was staged as one box."""

    path: str
    at: Point
    rotation: int
    layout: str = ""
    source: str = ""
    staged: bool = False


@dataclass(frozen=True)
class Resolution:
    """What ``resolve`` gives: the code placements by component path in path order, the records of the
    relative requests, the block records, the issues, the block-local paths of a reuse that its
    reference board lacks (``(block, path)``), and where the build's staging row continues after the
    staged groups (``None`` without a group)."""

    placements: Mapping[str, Resolved]
    records: tuple[Record, ...] = ()
    blocks: Mapping[str, BlockRecord] = field(default_factory=lambda: MappingProxyType({}))
    issues: tuple[Issue, ...] = ()
    missing: tuple[tuple[str, str], ...] = ()
    staging_end: int | None = None
    worlds: Mapping[str, Transform] = field(default_factory=lambda: MappingProxyType({}))

    def digest(self) -> str:
        """The SHA-256 of the resolved relative placements and block poses, as canonical JSON."""
        lines = [
            json.dumps(
                [r.path, r.request, r.at.x, r.at.y, r.rotation, r.side], separators=(",", ":"), sort_keys=True
            )
            for r in self.records
        ]
        lines += [
            json.dumps([b.path, b.at.x, b.at.y, b.rotation], separators=(",", ":"))
            for b in self.blocks.values()
        ]
        return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


# --- measures -------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Measure:
    box: BBox
    center: Point


def _middle(a: int, b: int) -> int:
    return (a + b) // 2


def _box_measure(box: BBox) -> _Measure:
    return _Measure(box, Point(_middle(box.x0, box.x1), _middle(box.y0, box.y1)))


def _placement(at: Point, rotation: int, side: str) -> Transform:
    return Transform.placement(at, rotation, side == "bottom")


def _translation(transform: Transform) -> Point:
    return Point(round_half_even_div(transform.tx_fixed, ONE), round_half_even_div(transform.ty_fixed, ONE))


def _placed(transform: Transform) -> Placed:
    return Placed(_translation(transform), transform.rot_udeg, "bottom" if transform.mirror else "top")


def _union(boxes: Sequence[BBox]) -> BBox | None:
    if not boxes:
        return None
    found = boxes[0]
    for box in boxes[1:]:
        found = found.union(box)
    return found


def _edge(measure: _Measure, edge: str) -> int:
    box = measure.box
    return {
        "left": box.x0,
        "right": box.x1,
        "top": box.y0,
        "bottom": box.y1,
        "center_x": measure.center.x,
        "center_y": measure.center.y,
    }[edge]


def _is_pose(value: object) -> bool:
    return value is not None and not hasattr(value, "subject")


def _is_reuse(value: object) -> bool:
    return value is not None and hasattr(value, "copper")


def _is_strategy(value: object) -> bool:
    return value is not None and hasattr(value, "kind") and not hasattr(value, "copper")


# --- the state of one pass ------------------------------------------------------------------------


@dataclass
class _State:
    scene: Scene
    part_frame: dict[str, str]
    parts: dict[str, Transform] = field(default_factory=lambda: {})
    """Footprint frame → its frame, per placed part."""
    sources: dict[str, str] = field(default_factory=lambda: {})
    locks: dict[str, bool] = field(default_factory=lambda: {})
    blocks: dict[str, Transform] = field(default_factory=lambda: {})
    """Block frame → parent frame, per placed block."""
    boxes: dict[str, BBox | None] = field(default_factory=lambda: {})
    """Each block's box in its own frame."""
    issues: list[Issue] = field(default_factory=lambda: [])
    records: list[tuple[str, str, str, tuple[RefUse, ...], Transform]] = field(default_factory=lambda: [])
    missing: list[tuple[str, str]] = field(default_factory=lambda: [])
    groups: list[str] = field(default_factory=lambda: [])
    staging_end: int | None = None

    def offset(self, frame: str) -> Point:
        return self.scene.origin if frame == "" else Point(0, 0)

    def climb(self, frame: str, target: str) -> str | None:
        """The block directly in ``target`` on the way up from ``frame`` (``None`` when ``frame`` is
        ``target``); ``"!"`` when ``target`` does not hold ``frame``."""
        child: str | None = None
        current = frame
        while current != target:
            if current == "":
                return "!"
            child = current
            current = self.scene.blocks[current].frame
        return child

    def to_frame(self, frame: str, inner: str) -> Transform | None:
        """The transform of frame ``inner`` into frame ``frame`` (which holds it), or ``None`` when a block
        on the way is not placed."""
        result = Transform()
        current = inner
        while current != frame:
            local = self.blocks.get(current)
            if local is None:
                return None
            result = local.compose(result)
            current = self.scene.blocks[current].frame
        return result

    def measure(self, ref: RefLike, frame: str) -> _Measure | None:
        """A reference measured in ``frame``'s coordinates, or ``None`` when it has no placement."""
        if ref.kind == "board":
            board = self.scene.board
            return None if board is None else _box_measure(board)
        if ref.kind == "block":
            box = self.boxes.get(ref.path)
            outer = self.to_frame(frame, ref.path)
            if box is None or outer is None:
                return None
            return _box_measure(outer.apply_bbox(box))
        local = self.parts.get(ref.path)
        footprint = self.scene.footprints.get(ref.path)
        if local is None or footprint is None:
            return None
        outer = self.to_frame(frame, self.part_frame[ref.path])
        if outer is None:
            return None
        placed = outer.compose(local)
        if ref.kind == "pad":
            pad = _pad(footprint, cast(str, ref.pad), ref.index)
            if pad is None:
                return None
            return _Measure(placed.apply_bbox(pad.box), placed.apply(pad.center))
        return _box_measure(placed.apply_bbox(footprint.extent))


def _pad(footprint: Footprint, number: str, index: int | None) -> PadBox | None:
    found = [pad for pad in footprint.pads if pad.number == number]
    if not found:
        return None
    if index is None:
        return found[0]
    return found[index] if index < len(found) else None


def _strategy_of(scene: Scene, frame: str) -> object:
    if frame == "":
        return scene.top
    return scene.blocks[frame].layout


def _reuse_source(scene: Scene, frame: str) -> tuple[str, Transform] | None:
    """The block whose reuse places the parts of ``frame`` and the transform of ``frame`` into that block's
    frame: ``frame`` itself, or an enclosing block reached through blocks with no layout of their own and no
    pose or an absolute one."""
    chain = Transform()
    current = frame
    while current != "":
        held = scene.blocks[current]
        if _is_reuse(held.layout):
            return current, chain
        if held.layout is not None:
            return None
        pose = held.pose
        if pose is not None:
            if not _is_pose(pose):
                return None
            x, y, rotation = (cast(int, getattr(pose, name)) for name in ("x", "y", "rotation"))
            chain = Transform.placement(Point(x, y), rotation).compose(chain)
        parent = held.frame
        if parent == "":
            return None
        current = parent
    return None


# --- one frame ------------------------------------------------------------------------------------


def _subject_measure(
    state: _State, kind: str, path: str, rotation: int, side: str, by: str | None, index: int | None
) -> tuple[_Measure, Transform] | None:
    """The subject's box and centre placed at the frame's origin with its rotation and side, and that
    placement; ``None`` when it cannot be measured."""
    if kind == "block":
        box = state.boxes.get(path)
        if box is None:
            return None
        turn = Transform.rotation(rotation)
        return _box_measure(turn.apply_bbox(box)), turn
    footprint = state.scene.footprints.get(path)
    if footprint is None:
        return None
    at = _placement(Point(0, 0), rotation, side)
    if by is not None:
        pad = _pad(footprint, by, index)
        if pad is None:
            return None
        return _Measure(at.apply_bbox(pad.box), at.apply(pad.center)), at
    return _box_measure(at.apply_bbox(footprint.extent)), at


def _solve(axis: AxisLike, horizontal: bool, own: _Measure, ref: _Measure | None, offset: int) -> int:
    """The translation along one axis that puts the subject where ``axis`` says."""
    lo, hi = (own.box.x0, own.box.x1) if horizontal else (own.box.y0, own.box.y1)
    centre = own.center.x if horizontal else own.center.y
    if axis.kind == "value":
        return offset + axis.value
    if axis.kind == "edge":
        target = offset + axis.value if ref is None else _edge(ref, cast(str, axis.ref_edge)) + axis.value
        edge = axis.key
        if edge in ("left", "top"):
            return target - lo
        if edge in ("right", "bottom"):
            return target - hi
        return target - centre
    assert ref is not None
    rlo, rhi = (ref.box.x0, ref.box.x1) if horizontal else (ref.box.y0, ref.box.y1)
    if axis.kind == "relation":
        if axis.key in ("right_of", "below"):
            return rhi + axis.value - lo
        return rlo - axis.value - hi
    if axis.key == "start":
        return rlo - lo
    if axis.key == "end":
        return rhi - hi
    rcentre = ref.center.x if horizontal else ref.center.y
    return rcentre - centre


def _cycles(nodes: Sequence[str], edges: Mapping[str, Sequence[str]]) -> list[list[str]]:
    """The strongly connected components of ``nodes`` that hold a cycle, each in path order (Tarjan)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    found: list[list[str]] = []
    counter = [0]

    def visit(node: str) -> None:
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on.add(node)
        for nxt in edges.get(node, ()):
            if nxt not in index:
                visit(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            component: list[str] = []
            while True:
                top = stack.pop()
                on.discard(top)
                component.append(top)
                if top == node:
                    break
            if len(component) > 1 or node in edges.get(node, ()):
                found.append(sorted(component))

    for node in sorted(nodes):
        if node not in index:
            visit(node)
    return sorted(found)


def _frame(
    state: _State,
    frame: str,
    *,
    fixed: Mapping[str, Transform],
    frozen: Mapping[str, Transform] | None,
) -> None:
    scene = state.scene
    items = list(scene.frames.get(frame, ()))
    offset = state.offset(frame)
    parts = [path for kind, path in items if kind == "part"]
    blocks = [path for kind, path in items if kind == "block"]
    for path in parts:
        if path in fixed:
            state.parts[path] = fixed[path]
            state.sources[path] = "fixed"
        elif path in scene.absolute:
            request = scene.absolute[path]
            at = Point(offset.x + request.x, offset.y + request.y)
            state.parts[path] = _placement(at, request.rotation, request.side)
            state.sources[path] = "absolute"
            state.locks[path] = request.locked
    pending_blocks: list[str] = []
    for path in blocks:
        held = scene.blocks[path]
        if frozen is not None:
            if path in frozen:
                state.blocks[path] = frozen[path]
            continue
        pose = held.pose
        if pose is None:
            pending_blocks.append(path)
        elif _is_pose(pose):
            x, y, rotation = (cast(int, getattr(pose, name)) for name in ("x", "y", "rotation"))
            state.blocks[path] = Transform.placement(Point(offset.x + x, offset.y + y), rotation)
    strategy = _strategy_of(scene, frame)
    if _is_strategy(strategy):
        chosen = cast(StrategyLike, strategy)
        laid: list[Item] = []
        turned: dict[str, Transform] = {}
        for kind, path in items:
            if kind == "part":
                # a part kept from the board (``fixed``) keeps its slot, so the others do not move
                if path in scene.absolute or path in scene.relative or path not in scene.footprints:
                    continue
                rotation, side = scene.turns.get(path, (0, "top"))
                at = _placement(Point(0, 0), rotation, side)
                turned[path] = at
                laid.append(Item(path, at.apply_bbox(scene.footprints[path].extent)))
            elif path in pending_blocks:
                box = state.boxes.get(path)
                if box is not None:
                    laid.append(Item(path, box))
        arranged = arrange(chosen, laid, (offset.x, offset.y))
        for key, (dx, dy) in arranged.moves:
            move = Transform.translation(dx, dy)
            if key in turned:
                if key not in fixed:
                    state.parts[key] = move.compose(turned[key])
                    state.sources[key] = "strategy"
            else:
                state.blocks[key] = move
                pending_blocks.remove(key)
        for key in arranged.overflow:
            state.issues.append(
                layout_issue(
                    "layout.strategy-overflow",
                    f"{key} is wider than the pack width of {frame or 'the top'} and takes a shelf of "
                    "its own",
                    key,
                    "widen the pack, turn the part, or place it with place()",
                )
            )
    source = _reuse_source(scene, frame) if frame else None
    if source is not None:
        owner, chain = source
        reference = scene.reuse.get(owner)
        if reference is not None:
            back = chain.inverse()
            for path in parts:
                if path in state.parts or path in scene.relative or path in scene.absolute:
                    continue
                local = path[len(owner) + 1 :]
                found = reference.get(local)
                if found is None:
                    state.missing.append((owner, local))
                    continue
                state.parts[path] = back.compose(_placement(found.at, found.rotation, found.side))
                state.sources[path] = "reuse"
    if frame == "" and scene.top is None and scene.staging is not None and frozen is None:
        cursor = scene.staging.x
        for path in list(pending_blocks):
            held = scene.blocks[path]
            box = state.boxes.get(path)
            if held.layout is None or box is None:
                continue
            state.blocks[path] = Transform.translation(cursor - box.x0, scene.staging.y - box.y0)
            pending_blocks.remove(path)
            state.groups.append(path)
            cursor += box.width + STAGING_GAP
            state.staging_end = cursor
    for path in pending_blocks:
        state.blocks[path] = Transform.translation(offset.x, offset.y)
    nodes: dict[str, RequestLike] = {}
    for path in parts:
        if path in scene.relative and path not in state.parts:
            nodes[path] = scene.relative[path]
    if frozen is None:
        for path in blocks:
            pose = scene.blocks[path].pose
            if pose is not None and not _is_pose(pose):
                nodes[path] = cast(RequestLike, pose)
    edges: dict[str, list[str]] = {}
    for path, request in nodes.items():
        wanted: list[str] = []
        for axis in (request.x, request.y):
            ref = axis.ref
            if ref is None or ref.kind == "board":
                continue
            home = state.part_frame.get(ref.path, "") if ref.kind in ("part", "pad") else ref.path
            if ref.kind in ("part", "pad"):
                child = state.climb(home, frame)
                node = ref.path if child is None else child
            else:
                child = state.climb(scene.blocks[ref.path].frame, frame) if ref.path in scene.blocks else "!"
                node = ref.path if child is None else child
            if node in nodes and node not in wanted:
                wanted.append(node)
        edges[path] = wanted
    remaining = dict(edges)
    done: set[str] = set()
    while True:
        ready = sorted(p for p, deps in remaining.items() if all(d in done for d in deps))
        if not ready:
            break
        path = ready[0]
        del remaining[path]
        done.add(path)
        _resolve_node(state, frame, path, nodes[path], offset)
    if remaining:
        cycles = _cycles(list(remaining), remaining)
        in_cycle = {p for component in cycles for p in component}
        for component in cycles:
            state.issues.append(
                layout_issue(
                    "layout.relative-cycle",
                    f"the relative placements of {', '.join(component)} reference each other in a cycle",
                    ", ".join(component),
                    "place one of them with x and y, or break the chain of references",
                )
            )
        for path in sorted(set(remaining) - in_cycle):
            state.issues.append(
                layout_issue(
                    "layout.relative-unresolved",
                    f"{path} references a placement caught in a cycle; it is staged",
                    path,
                    "break the cycle of relative placements",
                )
            )
    if frame:
        boxes: list[BBox] = []
        for kind, path in items:
            if kind == "part":
                local = state.parts.get(path)
                footprint = scene.footprints.get(path)
                if local is not None and footprint is not None:
                    boxes.append(local.apply_bbox(footprint.extent))
            else:
                local = state.blocks.get(path)
                box = state.boxes.get(path)
                if local is not None and box is not None:
                    boxes.append(local.apply_bbox(box))
        state.boxes[frame] = _union(boxes)


def _resolve_node(state: _State, frame: str, path: str, request: RequestLike, offset: Point) -> None:
    measured = _subject_measure(
        state, request.subject, path, request.rotation, request.side, request.by, request.by_index
    )
    if measured is None:
        what = "its pad " + str(request.by) if request.by is not None else "its box"
        state.issues.append(
            layout_issue(
                "layout.relative-unresolved",
                f"{path} cannot be measured ({what} is unknown); it is staged",
                path,
                "check the footprint and the pad number of by=",
            )
        )
        return
    own, turned = measured
    used: list[RefUse] = []
    solved: list[int] = []
    for axis, horizontal in ((request.x, True), (request.y, False)):
        ref_measure: _Measure | None = None
        if axis.ref is not None:
            ref_measure = state.measure(axis.ref, frame)
            if ref_measure is None:
                state.issues.append(
                    layout_issue(
                        "layout.relative-unresolved",
                        f"{path} is placed relative to {axis.ref.text()}, which has no placement; "
                        f"{path} is staged",
                        f"{path}, {axis.ref.path or axis.ref.text()}",
                        f"place {axis.ref.text()}, or give {path} a position",
                    )
                )
                return
            text = axis.ref.text()
            if all(u.ref != text for u in used):
                used.append(RefUse(text, ref_measure.box, ref_measure.center))
        solved.append(_solve(axis, horizontal, own, ref_measure, offset.x if horizontal else offset.y))
    move = Transform.translation(solved[0], solved[1])
    placed = move.compose(turned)
    if request.subject == "block":
        state.blocks[path] = placed
    else:
        state.parts[path] = placed
        state.sources[path] = "relative"
        state.locks[path] = request.locked
    state.records.append((path, request.text(), frame, tuple(used), placed))


def _beyond(scene: Scene, part_frame: Mapping[str, str], placements: Mapping[str, Resolved]) -> list[Issue]:
    """One ``layout.strategy-overflow`` per frame whose strategy put a part beyond the outline's box (a
    staged group is meant to lie beside the board)."""
    board = scene.board
    if board is None:
        return []
    frames: dict[str, list[str]] = {}
    for path, placed in placements.items():
        if placed.source != "strategy" or path not in scene.footprints:
            continue
        transform = _placement(placed.at, placed.rotation, placed.side)
        if not board.contains_bbox(transform.apply_bbox(scene.footprints[path].extent)):
            frames.setdefault(part_frame[path], []).append(path)
    return [
        layout_issue(
            "layout.strategy-overflow",
            f"the strategy of {frame or 'the top'} puts {', '.join(paths)} beyond the outline",
            frame or "top",
            "pose the block elsewhere, choose another strategy, or enlarge the board",
        )
        for frame, paths in sorted(frames.items())
    ]


def _depth(scene: Scene, frame: str) -> int:
    depth = 0
    while frame:
        frame = scene.blocks[frame].frame
        depth += 1
    return depth


def _pass(
    scene: Scene,
    fixed: Mapping[str, Placed],
    worlds: Mapping[str, Transform] | None,
    frozen: Mapping[str, Transform] | None,
) -> tuple[_State, dict[str, Transform]]:
    part_frame = {
        path: frame for frame, items in scene.frames.items() for kind, path in items if kind == "part"
    }
    state = _State(scene, part_frame)
    order = sorted(scene.frames, key=lambda f: (-_depth(scene, f), f))
    fixed_local: dict[str, Transform] = {}
    if worlds is not None:
        for path, placed in fixed.items():
            frame = part_frame.get(path)
            world = worlds.get(frame) if frame is not None else None
            if world is not None:
                fixed_local[path] = world.inverse().compose(
                    _placement(placed.at, placed.rotation, placed.side)
                )
    for frame in order:
        _frame(state, frame, fixed=fixed_local, frozen=frozen)
    found: dict[str, Transform] = {"": Transform()}
    for frame in sorted(scene.frames, key=lambda f: (_depth(scene, f), f)):
        if frame == "":
            continue
        parent = found.get(scene.blocks[frame].frame)
        local = state.blocks.get(frame)
        if parent is not None and local is not None:
            found[frame] = parent.compose(local)
    return state, found


def resolve(scene: Scene, fixed: Mapping[str, Placed] | None = None) -> Resolution:
    """The code placement of every part that an absolute request, a relative request, a strategy or a block
    reuse places, composed with its blocks' poses, in the written frame. With ``fixed`` the relative
    requests are resolved against those placements (``docs/lens.md``, "Placement precedence")."""
    code, worlds = _pass(scene, {}, None, None)
    state = code
    if fixed:
        state, _again = _pass(scene, fixed, worlds, dict(code.blocks))
        state.groups = code.groups
        state.staging_end = code.staging_end
    placements: dict[str, Resolved] = {}
    grouped = set(code.groups)
    for path in sorted(code.part_frame):
        chosen = code if fixed and path in fixed else state
        local = chosen.parts.get(path)
        if local is None:
            continue
        frame = code.part_frame[path]
        world = worlds.get(frame)
        if world is None:
            continue
        placed = _placed(world.compose(local))
        source = chosen.sources.get(path, "absolute")
        top = frame
        while top and scene.blocks[top].frame:
            top = scene.blocks[top].frame
        if top in grouped and source != "fixed":
            source = "group"
        placements[path] = Resolved(
            placed.at, placed.rotation, placed.side, chosen.locks.get(path, False), source
        )
    records: list[Record] = []
    held = list(state.records)
    if fixed:
        # a part that the board or the edits file placed keeps the record of its code resolution
        held += [entry for entry in code.records if entry[0] in fixed]
    for path, text, frame, used, local in held:
        if path not in placements and path not in scene.blocks:
            continue
        world = worlds.get(frame)
        if world is None:
            continue
        if path in scene.blocks:
            placed = _placed(world.compose(local))
        else:
            target = placements[path]
            placed = Placed(target.at, target.rotation, target.side)
        records.append(Record(path, text, frame, used, placed.at, placed.rotation, placed.side))
    block_records: dict[str, BlockRecord] = {}
    for path in sorted(scene.blocks):
        world = worlds.get(path)
        if world is None:
            continue
        held = scene.blocks[path]
        layout = held.layout
        text = cast(str, layout.text()) if layout is not None and hasattr(layout, "text") else ""  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
        placed = _placed(world)
        block_records[path] = BlockRecord(
            path, placed.at, placed.rotation, text, held.source, path in grouped
        )
    issues = sorted(
        [*state.issues, *_beyond(scene, code.part_frame, placements)],
        key=lambda i: (i.code, i.where, i.message),
    )
    return Resolution(
        MappingProxyType(placements),
        tuple(sorted(records, key=lambda r: r.path)),
        MappingProxyType(block_records),
        tuple(issues),
        tuple(sorted(set(state.missing))),
        state.staging_end,
        MappingProxyType(worlds),
    )


__all__ = [
    "EVIDENCE",
    "STAGING_GAP",
    "Absolute",
    "BlockRecord",
    "Footprint",
    "PadBox",
    "Placed",
    "Record",
    "RefUse",
    "Resolution",
    "Resolved",
    "Scene",
    "resolve",
]
