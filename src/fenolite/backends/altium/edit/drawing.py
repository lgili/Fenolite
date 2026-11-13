# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board shape of an Altium PCB document and its drawing on a mechanical layer (change c0497, design D3
and D6).

``board_shape`` gives the edges of the ``Board6`` outline (a line or an arc per vertex, ``KIND<k>``) and of
each free board cut-out of ``Regions6`` (``KIND=0``, ``ISBOARDCUTOUT=TRUE``), in document units.
``compare`` matches them with the free tracks and arcs of one mechanical layer, within
``DRAWING_TOLERANCE``: each edge of either side without one on the other gives
``altium.board-drawing.mismatch``. ``check_pcbdoc`` is the stage ``altium.board-drawing`` of ``fenolite
check``: it compares every mechanical layer whose drawing closes a ring on the outline's box.
``outline_less`` cuts a notch out of the outline for ``ops.add_board_cutout``.

The rows are in ``docs/formats/altium/pcb-records.md``, "Edit session board fields"; ``H-A-EDIT-DRAWING`` and
``H-A-EDIT-CUTOUT`` are ``INFERRED`` until Part J cases J-drawing and J-cutout run.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.pcbrecords import LAYER_NAMES
from fenolite.backends.altium.read.pcbprims import ArcRecord, RegionRecord, TrackRecord
from fenolite.backends.altium.read.pcbstack import KeyReader, read_outline
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level

DRAWING_TOLERANCE = 3937
"""0.01 mm in units (1/10 000 mil): a drawn edge within this of a shape edge is that edge."""
MECHANICAL_LAYERS = range(57, 73)
"""The layer bytes of Mechanical 1 to 16."""
CHORD_DEGREES = 5.0
"""The largest sweep of one chord of an outline arc when the outline is cut (shortcut: a fixed step, not the
board's arc resolution; a notch next to an arc gets chords of at most 5°)."""
DRAWING_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {"altium.board-drawing.mismatch": "warning", "altium.board-drawing.none": "info"}
)
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-EDIT-DRAWING",))

Xy = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Edge:
    """A line from ``a`` to ``b``, or an arc of ``centre`` and ``radius`` from ``start`` to ``end`` degrees
    counter-clockwise (``a`` and ``b`` its ends then); document units."""

    a: Xy
    b: Xy
    centre: Xy | None = None
    radius: float = 0.0
    start: float = 0.0
    end: float = 0.0
    what: str = ""

    @property
    def middle(self) -> Xy:
        if self.centre is None:
            return (self.a[0] + self.b[0]) / 2, (self.a[1] + self.b[1]) / 2
        sweep = (self.end - self.start) % 360.0 or 360.0
        return _on(self.centre, self.radius, self.start + sweep / 2)


def _on(centre: Xy, radius: float, degrees: float) -> Xy:
    turn = math.radians(degrees)
    return centre[0] + radius * math.cos(turn), centre[1] + radius * math.sin(turn)


def _arc(centre: Xy, radius: float, start: float, end: float, what: str) -> Edge:
    return Edge(
        _on(centre, radius, start), _on(centre, radius, end), centre, radius, start % 360, end % 360, what
    )


# --- the board shape -------------------------------------------------------------------------------


Vertex = tuple[int, int, dict[str, str] | None]
"""An outline vertex in units with the keys of its arc (``KIND``, ``CX``, ``CY``, ``SA``, ``EA``, ``R``
values) when an arc runs from it to the next vertex, else ``None``."""


def outline_vertices(state: State) -> list[Vertex]:
    """The vertices of the ``Board6`` outline without its repeated last vertex."""
    record = state.properties("Board6")[0]
    out: list[Vertex] = []
    for k, v in enumerate(read_outline(KeyReader(record, "Board6"))[:-1]):
        keys = None
        if v.kind != 0:
            keys = {name: record.get(f"{name}{k}") or "0" for name in ("KIND", "CX", "CY", "SA", "EA", "R")}
        out.append((round(v.x), round(v.y), keys))
    return out


def _arc_of(keys: Mapping[str, str]) -> tuple[Xy, float, float, float]:
    from fenolite.backends.altium.read.pcbprops import parse_mil

    cx, cy, r = parse_mil(keys["CX"]), parse_mil(keys["CY"]), parse_mil(keys["R"])
    return (float(cx or 0), float(cy or 0)), float(r or 0), float(keys["SA"]), float(keys["EA"])


def outline_edges(vertices: Sequence[Vertex]) -> list[Edge]:
    out: list[Edge] = []
    for k, (x, y, keys) in enumerate(vertices):
        nx, ny, _ = vertices[(k + 1) % len(vertices)]
        if keys is None:
            out.append(Edge((x, y), (nx, ny), what="board outline"))
        else:
            centre, radius, start, end = _arc_of(keys)
            out.append(_arc(centre, radius, start, end, "board outline"))
    return out


def cutout_rings(state: State) -> list[list[tuple[int, int]]]:
    """The rings of the free board cut-outs of ``Regions6``, in units."""
    out: list[list[tuple[int, int]]] = []
    for p in state.typed("Regions6") if state.has("Regions6") else []:
        if not isinstance(p, RegionRecord) or p.prefix.polygon is not None or p.prefix.component is not None:
            continue
        keys = dict(p.properties.fields)
        if keys.get("ISBOARDCUTOUT") == "TRUE" and keys.get("KIND", "0") == "0" and p.outline:
            out.append([(round(v.x), round(v.y)) for v in p.outline])
    return out


def board_shape(state: State) -> list[Edge]:
    """The edges of the outline and of every free board cut-out ring."""
    edges = outline_edges(outline_vertices(state))
    for ring in cutout_rings(state):
        edges += [Edge(a, ring[(k + 1) % len(ring)], what="board cut-out") for k, a in enumerate(ring)]
    return edges


def _chords(start: Vertex, end: tuple[int, int]) -> list[tuple[int, int]]:
    """The inner points of the chords of the arc from ``start`` to ``end``, in the ring's direction."""
    assert start[2] is not None
    centre, radius, sa, ea = _arc_of(start[2])
    at = math.degrees(math.atan2(start[1] - centre[1], start[0] - centre[0]))
    forward = abs((at - sa + 180) % 360 - 180) <= abs((at - ea + 180) % 360 - 180)
    sweep = (ea - sa) % 360.0 or 360.0
    steps = max(2, math.ceil(sweep / CHORD_DEGREES))
    first = sa if forward else ea
    sign = 1 if forward else -1
    points = [_on(centre, radius, first + sign * sweep * i / steps) for i in range(1, steps)]
    return [
        (round(x), round(y)) for x, y in points if (round(x), round(y)) not in ((start[0], start[1]), end)
    ]


def polygonised(vertices: Sequence[Vertex]) -> tuple[list[tuple[int, int]], dict[int, list[tuple[int, int]]]]:
    """The outline as a ring of points, arcs as chords, and the chord points of each arc vertex by index."""
    ring: list[tuple[int, int]] = []
    chords: dict[int, list[tuple[int, int]]] = {}
    for k, vertex in enumerate(vertices):
        ring.append((vertex[0], vertex[1]))
        if vertex[2] is not None:
            nxt = vertices[(k + 1) % len(vertices)]
            chords[k] = _chords(vertex, (nxt[0], nxt[1]))
            ring += chords[k]
    return ring, chords


def outline_less(
    vertices: Sequence[Vertex], ring: Sequence[tuple[int, int]]
) -> tuple[list[Vertex], list[tuple[int, int]]]:
    """The outline less ``ring`` (``geo`` extra): its vertices, an arc kept where its chords survive whole,
    and the same ring with every arc as chords. ``ValueError`` unless one ring without a hole results."""
    from fenolite.geometry.boolean import select_backend
    from fenolite.geometry.polygon import Polygon, area2
    from fenolite.geometry.vector import Point

    outer, chords = polygonised(vertices)
    shape = Polygon(tuple(Point(x, y) for x, y in outer))
    cut = Polygon(tuple(Point(x, y) for x, y in ring))
    result = select_backend(operation="difference").difference(shape, cut)
    if len(result) != 1 or result[0].holes:
        raise ValueError(f"the outline less the ring is {len(result)} pieces, not one ring")
    points = [(int(p.x), int(p.y)) for p in result[0].outer]
    if (area2([Point(*p) for p in points]) > 0) != (area2([Point(*p) for p in outer]) > 0):
        points.reverse()
    inner = {p for points in chords.values() for p in points}
    first = next((i for i, p in enumerate(points) if p not in inner), 0)
    points = points[first:] + points[:first]  # a kept arc's chords never wrap past the walk's start
    starts = {(v[0], v[1]): k for k, v in enumerate(vertices) if v[2] is not None}
    out: list[Vertex] = []
    skip: set[int] = set()
    n = len(points)
    for i, p in enumerate(points):
        if i in skip:
            continue
        k = starts.get(p)
        if k is not None:
            nxt = vertices[(k + 1) % len(vertices)]
            run = [*chords[k], (nxt[0], nxt[1])]
            if [points[(i + j + 1) % n] for j in range(len(run))] == run:
                out.append((p[0], p[1], vertices[k][2]))
                skip |= {(i + j + 1) % n for j in range(len(chords[k]))}
                continue
        out.append((p[0], p[1], None))
    return out, points


# --- the drawing -----------------------------------------------------------------------------------


def drawn_edges(state: State, layer: int) -> list[tuple[str, int, Edge]]:
    """The free tracks and arcs on ``layer``: storage, position and edge."""
    from fenolite.backends.altium.edit.ops import on_layer

    out: list[tuple[str, int, Edge]] = []
    for storage in ("Tracks6", "Arcs6"):
        if not state.has(storage):
            continue
        for position, p in enumerate(state.typed(storage)):
            if not isinstance(p, TrackRecord | ArcRecord) or not on_layer(p.raw, layer):
                continue
            if p.prefix.component is not None or p.prefix.polygon is not None:
                continue
            if isinstance(p, TrackRecord):
                out.append((storage, position, Edge((p.x1, p.y1), (p.x2, p.y2), what="drawn track")))
            else:
                out.append(
                    (storage, position, _arc((p.cx, p.cy), p.radius, p.start_angle, p.end_angle, "drawn arc"))
                )
    return out


def _near(a: Xy, b: Xy) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= DRAWING_TOLERANCE


def _off(p: Xy, a: Xy, b: Xy) -> tuple[float, float]:
    """The distance of ``p`` from the line ``a–b`` and its place along ``a–b`` (0 at ``a``, units)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    along = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length
    return abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / length, along


def _same_arc(x: Edge, y: Edge) -> bool:
    assert x.centre is not None and y.centre is not None
    if not _near(x.centre, y.centre) or abs(x.radius - y.radius) > DRAWING_TOLERANCE:
        return False
    return (_near(x.a, y.a) and _near(x.b, y.b)) or (_near(x.a, y.b) and _near(x.b, y.a))


def _covered(shape: Edge, drawn: Sequence[Edge]) -> bool:
    """Whether the drawn edges lie on ``shape`` and cover it end to end."""
    if shape.centre is not None:
        return any(d.centre is not None and _same_arc(shape, d) for d in drawn)
    length = math.hypot(shape.b[0] - shape.a[0], shape.b[1] - shape.a[1])
    spans: list[tuple[float, float]] = []
    for d in drawn:
        if d.centre is not None:
            continue
        (oa, ta), (ob, tb) = _off(d.a, shape.a, shape.b), _off(d.b, shape.a, shape.b)
        if oa <= DRAWING_TOLERANCE and ob <= DRAWING_TOLERANCE:
            spans.append((min(ta, tb), max(ta, tb)))
    reach = 0.0
    for low, high in sorted(spans):
        if low - DRAWING_TOLERANCE > reach:
            break
        reach = max(reach, high)
    return (
        bool(spans) and min(s[0] for s in spans) <= DRAWING_TOLERANCE and reach >= length - DRAWING_TOLERANCE
    )


def _lies_on(drawn: Edge, shape: Sequence[Edge]) -> bool:
    for s in shape:
        if drawn.centre is not None or s.centre is not None:
            if drawn.centre is not None and s.centre is not None and _same_arc(drawn, s):
                return True
            continue
        length = math.hypot(s.b[0] - s.a[0], s.b[1] - s.a[1])
        ends = [_off(p, s.a, s.b) for p in (drawn.a, drawn.b)]
        if all(
            o <= DRAWING_TOLERANCE and -DRAWING_TOLERANCE <= t <= length + DRAWING_TOLERANCE for o, t in ends
        ):
            return True
    return False


def compare(state: State, layer: int) -> list[Issue]:
    """One ``altium.board-drawing.mismatch`` per shape edge that ``layer`` does not draw and per drawn edge
    on no shape edge."""
    shape = board_shape(state)
    drawn = [edge for _, _, edge in drawn_edges(state, layer)]
    origin = _origin(state)
    name = LAYER_NAMES.get(layer, str(layer))
    out: list[Issue] = []
    for edge in shape:
        if not _covered(edge, drawn):
            out.append(
                _mismatch(
                    edge, origin, name, f"the {edge.what} edge {_text(edge, origin)} is not drawn on {name}"
                )
            )
    for edge in drawn:
        if not _lies_on(edge, shape):
            out.append(
                _mismatch(
                    edge,
                    origin,
                    name,
                    f"the {edge.what} {_text(edge, origin)} on {name} lies on no edge of the board shape",
                )
            )
    return out


def _origin(state: State) -> Xy:
    from fenolite.backends.altium.read.pcbprops import parse_mil

    board = state.properties("Board6")[0]
    return float(parse_mil(board.get("ORIGINX")) or 0), float(parse_mil(board.get("ORIGINY")) or 0)


def _mm(p: Xy, origin: Xy) -> str:
    return f"({(p[0] - origin[0]) * 254e-8:.3f}, {(p[1] - origin[1]) * 254e-8:.3f}) mm"


def _text(edge: Edge, origin: Xy) -> str:
    return f"{_mm(edge.a, origin)}–{_mm(edge.b, origin)}"


def _mismatch(edge: Edge, origin: Xy, name: str, message: str) -> Issue:
    return Issue("altium.board-drawing.mismatch", "warning", message, f"{name} at {_mm(edge.middle, origin)}",
                 "redraw the layer with Session.draw_board_shape")  # fmt: skip


def _ring_layers(state: State) -> list[int]:
    """The mechanical layers whose free tracks and arcs close a ring on the box of the outline."""
    outline = outline_edges(outline_vertices(state))
    xs = [p[0] for e in outline for p in (e.a, e.b)]
    ys = [p[1] for e in outline for p in (e.a, e.b)]
    found: list[int] = []
    for layer in MECHANICAL_LAYERS:
        edges = [edge for _, _, edge in drawn_edges(state, layer)]
        if len(edges) < 2:
            continue
        ends = [p for e in edges for p in (e.a, e.b)]
        box = (
            min(p[0] for p in ends),
            min(p[1] for p in ends),
            max(p[0] for p in ends),
            max(p[1] for p in ends),
        )
        if any(
            abs(u - v) > DRAWING_TOLERANCE
            for u, v in zip(box, (min(xs), min(ys), max(xs), max(ys)), strict=True)
        ):
            continue
        if all(sum(1 for q in ends if _near(p, q)) >= 2 for p in ends):
            found.append(layer)
    return found


def check_pcbdoc(data: bytes, *, file: str = "") -> list[Issue]:
    """The stage ``altium.board-drawing``: ``compare`` on each mechanical layer that draws the board, or the
    single ``altium.board-drawing.none``."""
    state = State.of(data, file=file)
    layers = _ring_layers(state)
    if not layers:
        message = "no mechanical layer draws a closed ring on the board outline's box"
        return [
            Issue(
                "altium.board-drawing.none", "info", message, "Board6", "compare a layer with drawing.compare"
            )
        ]
    return [issue for layer in layers for issue in compare(state, layer)]


def mechanical(layer: int) -> bool:
    return layer in MECHANICAL_LAYERS


__all__ = [
    "DRAWING_ISSUE_CODES",
    "DRAWING_TOLERANCE",
    "EVIDENCE",
    "Edge",
    "board_shape",
    "check_pcbdoc",
    "compare",
    "drawn_edges",
    "outline_less",
    "outline_vertices",
]
