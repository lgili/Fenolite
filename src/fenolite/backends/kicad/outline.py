# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board outline as closed rings: ``board_outline`` (capability kicad-file-backend, "Board outline as
rings"; facts: ``docs/formats/kicad/board.md``; change c0022).

A design with a model outline gives its points and cut-outs. A read board gives the root graphics on its
edge layer together with the edge items of its footprints (``frame.footprint_edges``;
``H-K-OUTLINE-FPEDGE``), chained with ``geometry.assemble_rings`` after endpoints closer than
``CHAIN_GAP`` are joined, as KiCad joins them (``H-K-OUTLINE-CHAIN``). ``H-G-EDGE-EXACT``, the earlier
premise that endpoints meet exactly, is refuted by that measurement.

Change c0102 adds the arcs of a model outline (``Outline.arcs``, polygonised here), ``outline_box``, the
build's ring check ``check_outline`` and ``merge_outline``, which decides whether a rebuild keeps the edge
content of an existing board or replaces it with the script's outline (``docs/lens.md``, "Outline
changes"). The edge texts and the uuids that sign an outline are in ``_edgesign``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Protocol, TypeVar

from fenolite.backends.kicad._edgesign import (
    edge_text,
    edge_texts,
    edge_uuid,
    outline_digest,
    outline_edges,
    outline_rings,
    position_uuid,
)
from fenolite.backends.kicad.frame import footprint_edges
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry import (
    DEFAULT_TOL,
    Arc,
    BBox,
    Circle,
    GeometryError,
    Location,
    Segment,
    SegmentRelation,
    Thick,
    area2,
    assemble_rings,
    classify_segments,
    point_in_ring,
    thick_touch,
)
from fenolite.geometry.errors import BRANCHING_CONTOUR
from fenolite.model.board import Arc as ModelArc
from fenolite.model.board import Board, Graphic, Outline, Track, Via, Zone
from fenolite.model.design import Design

EVIDENCE = Evidence(
    Level.INFERRED, hypotheses=("H-G-PLACE-OUTLINE", "H-K-OUTLINE-CHAIN", "H-K-OUTLINE-FPEDGE")
)
"""Raised to ``CORPUS-VERIFIED`` when ``H-G-PLACE-OUTLINE`` is settled."""
CHAIN_GAP = 10_000
"""Edge endpoints closer than this (nm, strictly) are one point. Both majors close an outline across a gap
below 10 µm and report it open above; at exactly 10 µm, 10.0.6 closes and 9.0.9 does not, so Fenolite
says open there: the safe answer for 9.0."""
OutlineSource = Literal["model", "edge"]
OutlineProblem = Literal["", "open-contour", "branching-contour", "no-edge-content"]
PROBLEMS: tuple[str, ...] = ("open-contour", "branching-contour", "no-edge-content")
DEFAULT_EDGE = "Edge.Cuts"
Ring = tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class BoardOutline:
    """The outline of a board: ``rings[0]`` is the board (the ring of largest area) and the others are its
    cut-outs. ``problem`` says why ``rings`` is empty; ``exact`` is false when a curve was polygonised;
    ``joined`` counts the groups of endpoints closer than ``CHAIN_GAP`` that were joined into one point."""

    rings: tuple[Ring, ...] = ()
    source: OutlineSource = "edge"
    problem: OutlineProblem = ""
    exact: bool = True
    joined: int = 0

    def __post_init__(self) -> None:
        if bool(self.rings) == bool(self.problem):
            raise ValueError("a board outline holds rings or a problem, never both and never neither")


def _edge_layers(board: Board) -> frozenset[str]:
    return frozenset(layer.name for layer in board.layers if layer.kind == "edge") or frozenset(
        {DEFAULT_EDGE}
    )


class _EdgeLike(Protocol):
    """What an edge graphic gives: a root ``Graphic`` or a ``frame.EdgeItem``."""

    @property
    def kind(self) -> str: ...

    @property
    def points(self) -> Sequence[Point]: ...


def _join(pieces: list[Segment | Arc]) -> tuple[list[Segment | Arc], int]:
    """``pieces`` with every group of endpoints closer than ``CHAIN_GAP`` joined into the group's smallest
    point, and the number of groups joined. Distances are compared squared, with integers. A piece whose
    two ends join into one point is left out."""
    points = sorted({end for piece in pieces for end in (piece.start, piece.end)})
    if len(points) < 2:
        return pieces, 0
    parent = {point: point for point in points}

    def root(point: Point) -> Point:
        while parent[point] != point:
            parent[point] = parent[parent[point]]
            point = parent[point]
        return point

    cells: dict[tuple[int, int], list[Point]] = {}
    for point in points:
        cell = (point.x // CHAIN_GAP, point.y // CHAIN_GAP)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in cells.get((cell[0] + dx, cell[1] + dy), ()):
                    gap2 = (point.x - other.x) ** 2 + (point.y - other.y) ** 2
                    if gap2 < CHAIN_GAP * CHAIN_GAP:
                        a, b = root(point), root(other)
                        if a != b:
                            parent[max(a, b)] = min(a, b)
        cells.setdefault(cell, []).append(point)
    moved = {point: root(point) for point in points if root(point) != point}
    if not moved:
        return pieces, 0
    joined: list[Segment | Arc] = []
    for piece in pieces:
        start, end = moved.get(piece.start, piece.start), moved.get(piece.end, piece.end)
        if start == end:
            continue
        if (start, end) == (piece.start, piece.end):
            joined.append(piece)
        elif isinstance(piece, Arc):
            try:
                joined.append(Arc(start, piece.mid, end))
            except (GeometryError, ValueError):
                joined.append(Segment(start, end))
        else:
            joined.append(Segment(start, end))
    return joined, len(set(moved.values()))


def _pieces(graphic: _EdgeLike) -> tuple[list[Segment | Arc], bool]:
    """The pieces of one edge graphic that is not a circle, and whether one of them is an arc."""
    points = graphic.points
    if graphic.kind == "arc" and len(points) == 3:
        try:
            return [Arc(points[0], points[1], points[2])], True
        except (GeometryError, ValueError):
            return [Segment(points[0], points[2])], False
    if graphic.kind == "rect" and len(points) == 2:
        a, b = points
        corners = (a, Point(b.x, a.y), b, Point(a.x, b.y))
        return [Segment(p, q) for p, q in zip(corners, (*corners[1:], corners[0]), strict=True)], False
    if graphic.kind == "polygon":
        return [Segment(p, q) for p, q in zip(points, (*points[1:], points[0]), strict=True)], False
    return [Segment(p, q) for p, q in zip(points, points[1:], strict=False)], False


def _sorted(rings: list[Ring]) -> tuple[Ring, ...]:
    """The ring of largest area first; the others in the order of their smallest point."""
    largest = max(range(len(rings)), key=lambda i: (abs(area2(rings[i])), -i))
    rest = sorted((ring for i, ring in enumerate(rings) if i != largest), key=min)
    return (rings[largest], *rest)


def _ring_points(ring: Sequence[Point], mids: Mapping[int, Point], tol: int) -> tuple[Ring, bool]:
    """The vertices of one model ring with its arcs polygonised at ``tol``, and whether one was."""
    points: list[Point] = []
    curved = False
    for k, start in enumerate(ring):
        end = ring[(k + 1) % len(ring)]
        mid = mids.get(k)
        points.append(start)
        if mid is None or start == end:
            continue
        try:
            arc = Arc(start, mid, end)
        except (GeometryError, ValueError):
            continue
        if arc.is_straight:
            continue
        curved = True
        points += arc.polygonize(tol)[1:-1]
    return tuple(points), curved


def _model_rings(outline: Outline, tol: int) -> tuple[tuple[Ring, ...], bool]:
    """The rings of a model outline, the board ring first, and whether an arc was polygonised. Empty when
    the board ring does not close: fewer than three vertices, or two without an arc."""
    rings: list[Ring] = []
    curved = False
    for r, ring in enumerate(outline_rings(outline)):
        mids = {arc.edge: arc.mid for arc in outline.arcs if arc.ring == r}
        found, bent = (tuple(ring), False) if not mids else _ring_points(ring, mids, tol)
        if len(found) < 3:
            if r == 0:
                return (), False
            continue
        rings.append(found)
        curved = curved or bent
    return tuple(rings), curved


def board_outline(design: Design, *, tol: int = DEFAULT_TOL) -> BoardOutline:
    """The outline of ``design``'s board as rings in the board frame.

    From ``Board.outline`` when the model has one (``source`` ``model``: its points, then its cut-outs,
    the arcs of ``Outline.arcs`` polygonised at ``tol``, which makes ``exact`` false),
    otherwise from the root graphics on the edge layer and the edge items of the footprints (``source``
    ``edge``), with endpoints closer than ``CHAIN_GAP`` joined. Never raises on what it finds: a board
    without a closed outline gets a ``problem``.
    """
    board = design.board
    if board is None:
        return BoardOutline(problem="no-edge-content")
    if board.outline is not None:
        model, curved = _model_rings(board.outline, tol)
        if model:
            return BoardOutline(model, "model", exact=not curved)
    layers = _edge_layers(board)
    rings: list[Ring] = []
    pieces: list[Segment | Arc] = []
    exact = True
    edge_items: list[_EdgeLike] = [graphic for graphic in board.graphics if graphic.layer in layers]
    edge_items += footprint_edges(board, layers)
    for graphic in edge_items:
        if graphic.kind == "circle" and len(graphic.points) == 2:
            circle = Circle.from_kicad(graphic.points[0], graphic.points[1])
            if circle.radius2 > 0:
                rings.append(circle.polygonize(tol))
                exact = False
            continue
        found, curved = _pieces(graphic)
        kept = [piece for piece in found if piece.start != piece.end]
        pieces += kept
        exact = exact and not (curved and kept)
    if not pieces and not rings:
        return BoardOutline(problem="no-edge-content")
    pieces, joined = _join(pieces)
    if pieces:
        try:
            paths = assemble_rings(pieces)
        except GeometryError as error:
            code: OutlineProblem = "branching-contour" if error.code == BRANCHING_CONTOUR else "open-contour"
            return BoardOutline(problem=code)
        for path in paths:
            ring = path.polygonize(tol)
            if len(ring) >= 3 and area2(ring) != 0:
                rings.append(ring)
    if not rings:
        return BoardOutline(problem="open-contour")
    return BoardOutline(_sorted(rings), "edge", exact=exact, joined=joined)


Box = tuple[int, int, int, int]


def _box(points: Sequence[Point]) -> Box:
    return (
        min(p.x for p in points),
        min(p.y for p in points),
        max(p.x for p in points),
        max(p.y for p in points),
    )


def box_points(box: Box) -> tuple[Point, Point, Point, Point]:
    """The rectangle of ``box`` from its top-left corner, in the order of the board rectangle."""
    x0, y0, x1, y1 = box
    return (Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1))


def ring_box(outline: Outline) -> Box | None:
    """The box of the board ring's vertices and arc mid points: the box that a zone declared without an
    outline takes (``docs/dsl.md``, "Zones"). ``None`` for an outline without points."""
    if not outline.points:
        return None
    return _box((*outline.points, *(arc.mid for arc in outline.arcs if arc.ring == 0)))


def outline_box(design: Design) -> Box | None:
    """The smallest box ``(x0, y0, x1, y1)`` that holds every ring of the model outline, each arc by its
    true extent (``Arc.bbox``), or, without a model outline, every ring of ``board_outline``. ``None``
    when there is no ring. The build's staging row and the lens's off-board test read it: the box of
    ``Outline.points`` alone collapses for a round board of two arcs."""
    board = design.board
    if board is None:
        return None
    outline = board.outline
    if outline is not None and outline.points:
        boxes: list[BBox] = [BBox.of_points(ring) for ring in outline_rings(outline) if ring]
        for edge in outline_edges(outline):
            if edge.mid is None or edge.start == edge.end:
                continue
            try:
                boxes.append(Arc(edge.start, edge.mid, edge.end).bbox())
            except (GeometryError, ValueError):
                continue
        return (
            min(b.x0 for b in boxes),
            min(b.y0 for b in boxes),
            max(b.x1 for b in boxes),
            max(b.y1 for b in boxes),
        )
    rings = board_outline(design).rings
    if not rings:
        return None
    return _box([point for ring in rings for point in ring])


# --- the build's check of a model outline ---------------------------------------------------------

CHECK_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.outline.invalid": "error",
        "kicad.outline.zone-short": "warning",
    }
)
"""The closed table of ``check_outline``."""
INVALID_HINT = "keep every cut-out inside the board ring and clear of the other rings"


def ring_name(index: int) -> str:
    """``board`` for ring 0 and ``cut-out <k>`` for ring k."""
    return "board" if index == 0 else f"cut-out {index}"


def _invalid(message: str, where: str) -> Issue:
    return Issue(
        "kicad.outline.invalid", CHECK_ISSUE_CODES["kicad.outline.invalid"], message, where, INVALID_HINT
    )


def _form_issues(outline: Outline) -> list[Issue]:
    """What breaks the model's form (capability design-model, "Board outline arcs")."""
    rings = outline_rings(outline)
    issues: list[Issue] = []
    keys = [(arc.ring, arc.edge) for arc in outline.arcs]
    if keys != sorted(set(keys)):
        issues.append(
            _invalid("the arcs of the outline are not sorted by (ring, edge), one per edge", "board")
        )
    arcs_of: dict[int, int] = {}
    for arc in outline.arcs:
        where = f"{ring_name(arc.ring)}, edge {arc.edge}"
        if not 0 <= arc.ring < len(rings) or not 0 <= arc.edge < len(rings[arc.ring]):
            issues.append(_invalid(f"an arc names {where}, which the outline does not hold", "board"))
            continue
        ring = rings[arc.ring]
        start, end = ring[arc.edge], ring[(arc.edge + 1) % len(ring)]
        side = (arc.mid.x - start.x) * (end.y - start.y) - (arc.mid.y - start.y) * (end.x - start.x)
        if arc.mid in (start, end) or side == 0:
            issues.append(
                _invalid(
                    f"the arc of {where} has its mid on the line through its two vertices",
                    ring_name(arc.ring),
                )
            )
            continue
        arcs_of[arc.ring] = arcs_of.get(arc.ring, 0) + 1
    for index, ring in enumerate(rings):
        if len(ring) >= 3 or (len(ring) == 2 and arcs_of.get(index, 0) >= 1):
            continue
        issues.append(
            _invalid(
                f"the ring {ring_name(index)} has {len(ring)} vertices: a ring needs three, or two "
                "with an arc",
                ring_name(index),
            )
        )
    return issues


def _crosses_itself(ring: Ring) -> bool:
    """Two edges of ``ring`` cross or touch, other than consecutive edges at their common vertex."""
    n = len(ring)
    if len(set(ring)) != n or area2(ring) == 0:
        return True
    edges = [(ring[i], ring[(i + 1) % n]) for i in range(n)]
    boxes = [(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y)) for a, b in edges]
    order = sorted(range(n), key=lambda i: boxes[i][0])
    for at, i in enumerate(order):
        a, b = edges[i]
        for j in order[at + 1 :]:
            if boxes[j][0] > boxes[i][2]:
                break
            if boxes[j][3] < boxes[i][1] or boxes[j][1] > boxes[i][3]:
                continue
            c, d = edges[j]
            relation = classify_segments(a, b, c, d)
            if relation is SegmentRelation.DISJOINT:
                continue
            adjacent = (j - i) % n in (1, n - 1)
            if adjacent and relation in (SegmentRelation.TOUCHING, SegmentRelation.COLLINEAR_TOUCH):
                continue
            return True
    return False


def _closed(ring: Ring) -> Thick:
    return Thick((*ring, ring[0]), 0)


def _zone_short(design: Design, outline: Outline) -> list[Issue]:
    assert design.board is not None
    short = ring_box(outline)
    full = outline_box(design)
    if short is None or full is None:
        return []
    if not (full[0] < short[0] or full[1] < short[1] or full[2] > short[2] or full[3] > short[3]):
        return []
    rectangle = box_points(short)
    names = [zone.name or zone.id for zone in design.board.zones if tuple(zone.outline) == rectangle]
    if not names:
        return []
    return [
        Issue(
            "kicad.outline.zone-short",
            CHECK_ISSUE_CODES["kicad.outline.zone-short"],
            f"an arc of the board ring bulges beyond the box of its vertices and mid points, which the "
            f"zone(s) {', '.join(names)} declared without an outline take: the fill stops short of the edge",
            "board",
            "give the zone an outline that holds the arc, or add a vertex at the extreme of the arc",
        )
    ]


def check_outline(design: Design) -> tuple[Issue, ...]:
    """The issues of the model outline of ``design``, with the codes of ``CHECK_ISSUE_CODES`` (capability
    kicad-file-backend, "Outline shape checks"). ``kicad.outline.invalid`` for an outline that breaks the
    model's form, a ring that crosses or touches itself, two rings that cross or touch, a cut-out outside
    the board ring and a cut-out inside another: the first two are what KiCad 10 reports as
    ``invalid_outline`` (``H-K-OUTLINE-INVALID``), and one verdict serves both targets.
    ``kicad.outline.zone-short`` names the zones without an outline that an arc of the board ring bulges
    beyond. A design without a model outline gives no issue."""
    board = design.board
    if board is None or board.outline is None or not board.outline.points:
        return ()
    outline = board.outline
    issues = _form_issues(outline)
    if issues:
        return tuple(issues)
    rings, _ = _model_rings(outline, DEFAULT_TOL)
    if len(rings) != 1 + len(outline.cutouts):
        return (_invalid("a ring of the outline encloses no area", "board"),)
    bad: set[int] = set()
    for index, ring in enumerate(rings):
        if _crosses_itself(ring):
            bad.add(index)
            issues.append(
                _invalid(f"the ring {ring_name(index)} crosses or touches itself", ring_name(index))
            )
    cores = {index: _closed(ring) for index, ring in enumerate(rings) if index not in bad}
    for i in sorted(cores):
        for j in sorted(cores):
            if j <= i:
                continue
            pair = f"{ring_name(i)} and {ring_name(j)}"
            if thick_touch(cores[i], cores[j]):
                issues.append(_invalid(f"the rings {pair} cross or touch", ring_name(j)))
            elif i == 0:
                if point_in_ring(rings[j][0], rings[0]) is not Location.INSIDE:
                    issues.append(
                        _invalid(f"{ring_name(j)} lies outside the {ring_name(0)} ring", ring_name(j))
                    )
            elif (
                point_in_ring(rings[j][0], rings[i]) is Location.INSIDE
                or point_in_ring(rings[i][0], rings[j]) is Location.INSIDE
            ):
                issues.append(_invalid(f"one of {pair} lies inside the other", ring_name(j)))
    return (*issues, *_zone_short(design, outline))


# --- an outline change on a built board -------------------------------------------------------------

MERGE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.outline.forced": "warning",
        "kicad.outline.copper-dropped": "warning",
        "kicad.outline.replaced": "info",
    }
)
"""The closed table of ``merge_outline``."""
OutlineCase = Literal["none", "kept", "resigned", "replaced", "forced"]
_Copper = TypeVar("_Copper", Track, ModelArc, Via)


def edge_graphics(design: Design) -> tuple[Graphic, ...]:
    """The root graphics of ``design``'s board on its layers of kind ``edge``: the edge content that
    ``merge_outline`` signs, compares and replaces. Edge items inside footprints are not part of it."""
    board = design.board
    if board is None:
        return ()
    layers = _edge_layers(board)
    return tuple(graphic for graphic in board.graphics if graphic.layer in layers)


def graphic_text(graphic: Graphic) -> str | None:
    """The edge text of a ``line`` or an ``arc`` graphic, ``None`` for every other kind."""
    points = graphic.points
    if graphic.kind == "line" and len(points) == 2:
        return edge_text(points[0], points[1])
    if graphic.kind == "arc" and len(points) == 3:
        return edge_text(points[0], points[2], points[1])
    return None


def edges_equal(outline: Outline | None, graphics: Sequence[Graphic]) -> bool:
    """Whether ``graphics`` are exactly the edges of ``outline``, lines and arcs compared as edge texts."""
    if outline is None:
        return False
    texts = [graphic_text(graphic) for graphic in graphics]
    if any(text is None for text in texts):
        return False
    return sorted(text for text in texts if text is not None) == sorted(edge_texts(outline))


def _uuid(graphic: Graphic) -> str:
    return graphic.native_ids.get("kicad", "")


def is_signed(outline: Outline, graphics: Sequence[Graphic]) -> bool:
    """Whether ``graphics`` are an outline that Fenolite wrote and nobody changed since: at least one
    graphic, lines and arcs only, and the uuid of each is the one the writer signs its text with under the
    digest of all of them. ``outline`` gives the entity the uuids are derived from."""
    texts = [graphic_text(graphic) for graphic in graphics]
    if not texts or any(text is None for text in texts):
        return False
    found = [text for text in texts if text is not None]
    digest = outline_digest(found)
    return all(
        _uuid(graphic) == edge_uuid(outline, digest, text)
        for graphic, text in zip(graphics, found, strict=True)
    )


def _is_older(outline: Outline, graphics: Sequence[Graphic]) -> bool:
    """Every graphic carries the position uuid a Fenolite before change c0102 gave its edge."""
    wanted = {
        edge_text(e.start, e.end, e.mid): position_uuid(outline, e.ring, e.edge)
        for e in outline_edges(outline)
    }
    return all(wanted.get(graphic_text(graphic) or "") == _uuid(graphic) for graphic in graphics)


def outline_case(built: Design, board: Design, *, locked: bool = False) -> OutlineCase:
    """Which row of the table of ``merge_outline`` holds for the existing ``board``."""
    graphics = edge_graphics(board)
    outline = built.board.outline if built.board is not None else None
    if not graphics or outline is None or not outline.points:
        return "none"
    if edges_equal(outline, graphics):
        return "resigned" if _is_older(outline, graphics) else "kept"
    if is_signed(outline, graphics):
        return "replaced"
    return "forced" if locked else "kept"


@dataclass(frozen=True)
class OutlineMerge:
    """What ``merge_outline`` decided: the adapted board design, whether its edge content was replaced by
    the built outline, the copper dropped by kind, and the issues."""

    board: Design
    replaced: bool = False
    dropped: Mapping[str, int] = dataclasses.field(default_factory=lambda: MappingProxyType({}))
    issues: tuple[Issue, ...] = ()


def _is_script_copper(item: Track | ModelArc | Via) -> bool:
    # ``copper`` imports this module, so its marker test is imported when it is needed
    from fenolite.backends.kicad.copper import is_copper_uuid

    return is_copper_uuid(item.native_ids.get("kicad", ""))


def _copper_core(item: Track | ModelArc | Via) -> Thick:
    if isinstance(item, Via):
        return Thick((item.position,), item.diameter)
    if isinstance(item, ModelArc):
        try:
            core = Arc(item.start, item.mid, item.end).polygonize(DEFAULT_TOL)
        except (GeometryError, ValueError):
            core = (item.start, item.end)
        return Thick(core, item.width)
    if item.start == item.end:
        return Thick((item.start,), max(item.width, 1))
    return Thick((item.start, item.end), item.width)


def _fits(item: Track | ModelArc | Via, rings: Sequence[Ring], closed: Sequence[Thick]) -> bool:
    """The copper of ``item`` touches no ring, and its first core point lies inside the board ring and
    outside every cut-out."""
    copper = _copper_core(item)
    if any(thick_touch(copper, ring) for ring in closed):
        return False
    first = copper.core[0]
    if point_in_ring(first, rings[0]) is not Location.INSIDE:
        return False
    return all(point_in_ring(first, ring) is Location.OUTSIDE for ring in rings[1:])


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _graphics_box(graphics: Sequence[Graphic]) -> Box | None:
    points = [point for graphic in graphics for point in graphic.points]
    return _box(points) if points else None


def merge_outline(built: Design, board: Design, *, locked: bool = False) -> OutlineMerge:
    """Decide whether a rebuild keeps the edge content of the existing ``board`` or replaces it with the
    outline of ``built`` (capability layout-lens, "Outline changes across rebuilds").

    =====================  ==========================  ====================================================
    the board's edges      against the built outline   result
    =====================  ==========================  ====================================================
    none                   —                           unchanged: the built outline is used
    any                    equal                       kept; re-signed when every uuid is a position uuid
    signed                 different                   replaced, ``kicad.outline.replaced``
    not signed             different, ``locked``       replaced, ``kicad.outline.forced``
    not signed             different, not locked       kept (the lens gives ``layout.outline-kept``)
    =====================  ==========================  ====================================================

    Replaced and re-signed boards lose their edge graphics and take the built outline, which the writer
    signs. When the content is replaced, the tracks, arcs and vias that are not script copper and do not
    fit the new board are dropped (``kicad.outline.copper-dropped``), and a zone that was declared without
    an outline takes the box of the new board ring. Edge items inside footprints are left alone; the
    message names their footprints. Footprints never move.
    """
    case = outline_case(built, board, locked=locked)
    if case in ("none", "kept") or board.board is None or built.board is None:
        return OutlineMerge(board)
    outline = built.board.outline
    assert outline is not None
    graphics = edge_graphics(board)
    gone = {graphic.id for graphic in graphics}
    kept_graphics = tuple(graphic for graphic in board.board.graphics if graphic.id not in gone)
    adapted = dataclasses.replace(board.board, graphics=kept_graphics, outline=outline)
    if case == "resigned":
        return OutlineMerge(dataclasses.replace(board, board=adapted))
    issues: list[Issue] = []
    refs = {c.id: c.ref for c in board.circuit.components}
    owners = sorted(
        {
            refs.get(by_id[item.footprint].component_id, "?")
            for by_id in ({fp.id: fp for fp in board.board.footprints},)
            for item in footprint_edges(board.board, _edge_layers(board.board))
            if item.footprint in by_id
        }
    )
    kept_note = (
        f"; the edge items inside the footprint(s) {', '.join(owners)} stay and remain part of the outline"
        if owners
        else ""
    )
    if case == "forced":
        issues.append(
            Issue(
                "kicad.outline.forced",
                MERGE_ISSUE_CODES["kicad.outline.forced"],
                "the board's edge content was changed in KiCad, or was not written by Fenolite; the locked "
                f"board() replaces it with the script's outline{kept_note}",
                "board",
                "remove locked=True from board() to keep the outline of the board",
            )
        )
    else:
        issues.append(
            Issue(
                "kicad.outline.replaced",
                MERGE_ISSUE_CODES["kicad.outline.replaced"],
                f"the board's own unchanged outline is replaced by the script's new one{kept_note}",
                "board",
            )
        )
    # copper that no longer fits
    new = board_outline(built)
    dropped = {"tracks": 0, "arcs": 0, "vias": 0}
    tracks, arcs, vias = board.board.tracks, board.board.arcs, board.board.vias
    if new.rings:
        closed = [_closed(ring) for ring in new.rings]
        net_names = {net.id: net.name for net in board.circuit.nets}
        nets: set[str] = set()

        def fitting(items: Sequence[_Copper], kind: str) -> tuple[_Copper, ...]:
            out: list[_Copper] = []
            for item in items:
                if _is_script_copper(item) or _fits(item, new.rings, closed):
                    out.append(item)
                    continue
                dropped[kind] += 1
                nets.add(net_names.get(item.net_id or "", "") or "no net")
            return tuple(out)

        tracks = fitting(tracks, "tracks")
        arcs = fitting(arcs, "arcs")
        vias = fitting(vias, "vias")
        if any(dropped.values()):
            issues.append(
                Issue(
                    "kicad.outline.copper-dropped",
                    MERGE_ISSUE_CODES["kicad.outline.copper-dropped"],
                    f"{_plural(dropped['tracks'], 'track')}, {_plural(dropped['arcs'], 'arc')} and "
                    f"{_plural(dropped['vias'], 'via')} on {', '.join(sorted(nets))} do not fit the new "
                    "outline and are dropped",
                    "board",
                    "run fenolite route to close the connections that reopened",
                )
            )
    # a zone declared without an outline follows the board
    old_box, new_box = _graphics_box(graphics), ring_box(outline)
    zones = board.board.zones
    if old_box is not None and new_box is not None and old_box != new_box:
        built_zones = {kicad_uuid(zone): zone for zone in built.board.zones}
        old_points, new_points = box_points(old_box), box_points(new_box)
        followed: list[Zone] = []
        for zone in zones:
            script = built_zones.get(zone.native_ids.get("kicad", ""))
            if (
                script is not None
                and tuple(zone.outline) == old_points
                and tuple(script.outline) == new_points
            ):
                zone = dataclasses.replace(zone, outline=new_points)
            followed.append(zone)
        zones = tuple(followed)
    adapted = dataclasses.replace(adapted, tracks=tracks, arcs=arcs, vias=vias, zones=zones)
    return OutlineMerge(
        dataclasses.replace(board, board=adapted), True, MappingProxyType(dict(dropped)), tuple(issues)
    )


__all__ = [
    "CHAIN_GAP",
    "CHECK_ISSUE_CODES",
    "EVIDENCE",
    "MERGE_ISSUE_CODES",
    "PROBLEMS",
    "BoardOutline",
    "OutlineMerge",
    "board_outline",
    "box_points",
    "check_outline",
    "edge_graphics",
    "edge_text",
    "edge_texts",
    "edge_uuid",
    "edges_equal",
    "graphic_text",
    "is_signed",
    "merge_outline",
    "outline_box",
    "outline_case",
    "outline_digest",
    "position_uuid",
    "ring_box",
    "ring_name",
]
