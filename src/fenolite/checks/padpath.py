# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic shortest centre-line paths between pads, without measuring zone copper.

Tracks split at junctions and pads, arcs keep the geometry kernel's exact integer length, and a via
joins only its spanned layers. Pad copper is supplied through the neutral BoardPad geometry contract.
"""

from __future__ import annotations

import fnmatch
import heapq
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from fenolite.backends.base import BoardPad, PadCopper
from fenolite.core.coords import Point
from fenolite.geometry import (
    Arc as Curve,
)
from fenolite.geometry import (
    GeometryError,
    Location,
    Thick,
    Transform,
    arc_length_to,
    dist2_point_segment,
    intersection_point,
    point_in_ring,
    round_point,
    segment_length,
    thick_touch,
)
from fenolite.model.board import Arc, Track
from fenolite.model.design import Design


@dataclass(frozen=True, slots=True)
class Step:
    """One centre-line portion or via crossing of a measured path."""

    id: str
    kind: str
    layer: str
    length_nm: int = 0


@dataclass(frozen=True, slots=True)
class Path:
    """A measured copper path or a reason it cannot be measured."""

    status: str
    steps: tuple[Step, ...] = ()
    vertices: tuple[str, ...] = ()
    pads: tuple[str, ...] = ()

    @property
    def length_nm(self) -> int:
        return sum(step.length_nm for step in self.steps)


def _layers(patterns: Sequence[str], layers: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        layer
        for layer in layers
        if any(fnmatch.fnmatchcase(layer, pattern.replace("F&B", "[FB]")) for pattern in patterns)
    )


def _copper_entry(
    layer: str, core: tuple[Point, ...], width: int, *, filled: bool = False
) -> PadCopper | None:
    """A ``PadCopper``, or ``None`` for a core that no copper record holds (a disc of diameter 0), as the
    backends' pad frames drop it (change c0364)."""
    try:
        return PadCopper(layer, core, width, filled=filled)
    except ValueError:
        return None


def model_pads(design: Design) -> tuple[BoardPad, ...]:
    """Exact common pad shapes for model-only callers. Backend BoardPad geometry covers other shapes.

    As in the KiCad and Altium pad frames, an ``np_thru_hole`` pad has no copper entries and an entry that
    no copper record can hold is left out; the pad itself stays (change c0364)."""
    if design.board is None:
        return ()
    copper = tuple(layer.name for layer in design.board.layers if layer.kind == "copper")
    components = {part.id: part for part in design.circuit.components}
    nets = {net.id: net.name for net in design.circuit.nets}
    found: list[BoardPad] = []
    for footprint in design.board.footprints:
        component = components.get(footprint.component_id)
        for pad in footprint.pads:
            placement = Transform.placement(footprint.position, footprint.rotation)
            at = placement.apply(pad.position)
            transform = Transform.placement(at, footprint.rotation + pad.rotation)
            shapes: list[PadCopper | None] = []
            for layer in () if pad.kind == "np_thru_hole" else _layers(pad.layers, copper):
                w, h = pad.size.w, pad.size.h
                if pad.shape == "circle":
                    shapes.append(_copper_entry(layer, (at,), min(w, h)))
                elif pad.shape == "rect":
                    points = tuple(
                        transform.apply(Point(x, y))
                        for x, y in (
                            (-w // 2, -h // 2),
                            (w // 2, -h // 2),
                            (w // 2, h // 2),
                            (-w // 2, h // 2),
                        )
                    )
                    shapes.append(_copper_entry(layer, points, 0, filled=True))
                elif pad.shape == "oval":
                    half = abs(w - h) // 2
                    local = (Point(-half, 0), Point(half, 0)) if w >= h else (Point(0, -half), Point(0, half))
                    shapes.append(
                        _copper_entry(layer, tuple(transform.apply(point) for point in local), min(w, h))
                    )
            found.append(
                BoardPad(
                    footprint.id,
                    component.ref if component else footprint.id,
                    component.path if component else "",
                    pad.id,
                    pad.number,
                    pad.kind,
                    at,
                    footprint.rotation + pad.rotation,
                    footprint.side,
                    pad.layers,
                    pad.net_id,
                    nets.get(pad.net_id or ""),
                    tuple(shape for shape in shapes if shape is not None),
                )
            )
    return tuple(found)


class CopperGraph:
    """An integer graph with stable ordering; no backend, external program or geometry extra is used."""

    def __init__(self, design: Design, *, pads: Sequence[BoardPad] | None = None) -> None:
        self.design = design
        self.adj: dict[str, list[tuple[str, Step]]] = {}
        self.positions: dict[str, tuple[str, str, Point]] = {}
        self.pads: dict[str, tuple[str, ...]] = {}
        self.pad_names: dict[str, str] = {}
        self.net_names = {net.id: net.name for net in design.circuit.nets}
        self._pad_records = model_pads(design) if pads is None else tuple(pads)
        board = design.board
        if board is None:
            return
        copper = tuple(layer.name for layer in board.layers if layer.kind == "copper")
        candidates: dict[tuple[str, str], set[Point]] = {}

        def add(net: str | None, layer: str, point: Point) -> None:
            if net is not None and layer in copper:
                candidates.setdefault((net, layer), set()).add(point)

        pieces: tuple[Track | Arc, ...] = (*board.tracks, *board.arcs)
        for piece in pieces:
            add(piece.net_id, piece.layer, piece.start)
            add(piece.net_id, piece.layer, piece.end)
        for via in board.vias:
            for layer in self._via_layers(via.layers, copper):
                add(via.net_id, layer, via.position)
        for pad in self._pad_records:
            for shape in pad.copper:
                if shape.exact:
                    add(pad.net_id, shape.layer, pad.position)
        # An intersection inside both straight centre lines is an actual junction, even when neither
        # source segment has an endpoint there. Fractional-nm intersections use kernel rounding.
        for index, a in enumerate(board.tracks):
            for b in board.tracks[index + 1 :]:
                if a.net_id is not None and a.net_id == b.net_id and a.layer == b.layer:
                    crossing = intersection_point(a.start, a.end, b.start, b.end)
                    if crossing is not None:
                        add(a.net_id, a.layer, round_point(*crossing))
        for (net, layer), points in sorted(candidates.items()):
            for point in sorted(points):
                self._vertex(net, layer, point)
        for piece in sorted(pieces, key=lambda piece: piece.id):
            if piece.net_id is None or piece.layer not in copper:
                continue
            points = candidates[(piece.net_id, piece.layer)]
            if isinstance(piece, Track):
                on = [point for point in points if dist2_point_segment(point, piece.start, piece.end) == 0]
                ordered = sorted(
                    on,
                    key=lambda point: (
                        (point.x - piece.start.x) ** 2 + (point.y - piece.start.y) ** 2,
                        point,
                    ),
                )
                distances = [segment_length(piece.start, point) for point in ordered]
            else:
                arc = piece
                try:
                    curve = Curve(arc.start, arc.mid, arc.end)
                    centre, radius2 = curve.centre, curve.radius2
                    on = [
                        point
                        for point in points
                        if (centre is None and dist2_point_segment(point, piece.start, piece.end) == 0)
                        or (
                            centre is not None
                            and (Fraction(point.x) - centre[0]) ** 2 + (Fraction(point.y) - centre[1]) ** 2
                            == radius2
                            and curve.contains_point_on_circle(point)
                        )
                    ]
                    ordered = sorted(
                        on, key=lambda point: (arc_length_to(arc.start, arc.mid, arc.end, point), point)
                    )
                except GeometryError:
                    ordered = [piece.start, piece.end]
                distances = [arc_length_to(piece.start, piece.mid, piece.end, point) for point in ordered]
            for index in range(len(ordered) - 1):
                a = self._vertex(piece.net_id, piece.layer, ordered[index])
                b = self._vertex(piece.net_id, piece.layer, ordered[index + 1])
                self._edge(
                    a,
                    b,
                    Step(
                        piece.id,
                        "arc" if isinstance(piece, Arc) else "track",
                        piece.layer,
                        distances[index + 1] - distances[index],
                    ),
                )
        for via in sorted(board.vias, key=lambda via: via.id):
            if via.net_id is None:
                continue
            layers = self._via_layers(via.layers, copper)
            for index, layer in enumerate(layers):
                for other in layers[index + 1 :]:
                    self._edge(
                        self._vertex(via.net_id, layer, via.position),
                        self._vertex(via.net_id, other, via.position),
                        Step(via.id, "via", ""),
                    )
        components = {part.id: part for part in design.circuit.components}
        footprints = {footprint.id: footprint for footprint in board.footprints}
        for pad in sorted(self._pad_records, key=lambda pad: pad.pad_id):
            if pad.kind == "np_thru_hole" or pad.net_id is None:
                continue
            vertex = "pad:" + pad.pad_id
            self.adj.setdefault(vertex, [])
            for shape in pad.copper:
                if not shape.exact:
                    continue
                thick = Thick(shape.core, shape.width, shape.filled)
                for candidate, (net, layer, point) in sorted(self.positions.items()):
                    if net == pad.net_id and layer == shape.layer and thick_touch(thick, Thick((point,), 1)):
                        self._edge(vertex, candidate, Step(pad.pad_id, "pad", layer))
            names = {f"{pad.ref}-{pad.number}"}
            footprint = footprints.get(pad.footprint_id)
            component = components.get(footprint.component_id) if footprint else None
            if component is not None:
                names.update(
                    f"{component.ref}-{pin.number}"
                    for pin in component.pins
                    if pad.number in component.pads_of(pin.number)
                )
            for name in sorted(names):
                self.pads[name] = (*self.pads.get(name, ()), vertex)
            self.pad_names[vertex] = f"{pad.ref}-{pad.number}"
        for neighbours in self.adj.values():
            neighbours.sort(key=lambda row: (row[0], row[1].id, row[1].kind))

    @staticmethod
    def _via_layers(span: Sequence[str], copper: Sequence[str]) -> tuple[str, ...]:
        if len(span) != 2 or any(layer not in copper for layer in span):
            return ()
        a, b = sorted(copper.index(layer) for layer in span)
        return tuple(copper[a : b + 1])

    def _vertex(self, net: str, layer: str, point: Point) -> str:
        key = f"{net}:{layer}:{point.x}:{point.y}"
        self.positions[key] = (net, layer, point)
        self.adj.setdefault(key, [])
        return key

    def _edge(self, a: str, b: str, step: Step) -> None:
        if a == b:
            return
        self.adj.setdefault(a, []).append((b, step))
        self.adj.setdefault(b, []).append((a, step))

    def _shortest(self, starts: Sequence[str], ends: Sequence[str], *, zones: bool = False) -> Path:
        wanted = set(ends)
        distances = {start: 0 for start in starts}
        previous: dict[str, tuple[str, Step]] = {}
        queue = [(0, start) for start in starts]
        heapq.heapify(queue)
        while queue:
            distance, vertex = heapq.heappop(queue)
            if distances[vertex] != distance:
                continue
            if vertex in wanted:
                vertices = [vertex]
                steps: list[Step] = []
                while vertex in previous:
                    parent, step = previous[vertex]
                    vertices.append(parent)
                    steps.append(step)
                    vertex = parent
                vertices.reverse()
                steps.reverse()
                pad_vertices = {
                    neighbour
                    for value in vertices
                    for neighbour, step in self.adj[value]
                    if step.kind == "pad"
                }
                names = tuple(
                    sorted(self.pad_names[value] for value in pad_vertices if value in self.pad_names)
                )
                return Path(
                    "path-through-zone" if zones and any(step.kind == "zone" for step in steps) else "ok",
                    tuple(step for step in steps if step.kind != "pad"),
                    tuple(vertices),
                    names,
                )
            for other, step in self.adj[vertex]:
                if step.kind == "zone" and not zones:
                    continue
                total = distance + step.length_nm
                if total < distances.get(other, total + 1):
                    distances[other] = total
                    previous[other] = (vertex, step)
                    heapq.heappush(queue, (total, other))
        return Path("unrouted")

    def shortest(self, a: str, b: str) -> Path:
        """Prefer a measurable continuous routed path; report zone connectivity only when needed."""
        starts, ends = self.pads.get(a, ()), self.pads.get(b, ())
        if not starts or not ends:
            return Path("unrouted")
        result = self._shortest(starts, ends)
        if result.status == "ok":
            return result
        board = self.design.board
        if board is not None:
            for zone in board.zones:
                for index, fill in enumerate(zone.fills):
                    touched = [
                        key
                        for key, (net, layer, point) in self.positions.items()
                        if net == zone.net_id
                        and layer == fill.layer
                        and point_in_ring(point, fill.polygon) != Location.OUTSIDE
                    ]
                    if touched:
                        key = f"zone:{zone.id}:{index}"
                        for vertex in touched:
                            self._edge(key, vertex, Step(zone.id, "zone", fill.layer))
        return self._shortest(starts, ends, zones=True)


__all__ = ["CopperGraph", "Path", "Step", "model_pads"]
