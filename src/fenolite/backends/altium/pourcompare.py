# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The comparison of two pours of one board (change c0215; capability altium-pour, "Pour comparison").

Both sides are readings of the same board (``backends.altium.pour.read_pour``): a document that Fenolite
poured and one that Altium saved, or two saves. Polygons are matched by layer, name and ``POURINDEX``, and
the pour of a polygon is the regions that carry its index. Per polygon, with ``d`` the reference's
``ARCRESOLUTION``:

- **M1** the area of the XOR of the two pours is at most ``d`` times the boundary length of the reference's;
- **M2** no part of the XOR still has area after an inward offset by ``d``: each part that has is one
  ``Difference``, with its centre, its area and the side that holds the copper;
- **M3** the pieces match one to one, each overlapping exactly one piece of the other side by more than half
  the smaller area, with the same number of holes;
- **M4** each matched piece touches the same objects of its net (pads by component reference and position,
  vias, tracks and arcs by position, on a ``GRID`` of 10 µm), and each net's objects form the same groups
  connected through copper, the pours included;
- **M5** both sides agree at every declared ``PourPoint`` of the polygon; a point where both sides
  contradict its declaration is a fault of the probe, not of the comparison.

Nothing is written. The comparison needs the ``geo`` extra (the ``clipper`` backend). It lives in the Altium
backend, beside the engine whose readings it compares, because the modules of ``fenolite.verify`` import the
standard library and ``core`` only (capability verification-evidence); the kit's checks reach it through
``cli._kit``.
"""

# evidence: none, it compares two readings of one board and states nothing of a file format or a tool

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from fenolite.backends.altium.adapter.copper import region_points
from fenolite.backends.altium.pour import (
    LayerObjects,
    PourObject,
    PourPolygon,
    PourReading,
    PourResult,
    area,
    disc,
    polygons_of,
)
from fenolite.core.coords import Point
from fenolite.core.units import Nm
from fenolite.geometry.boolean.clipper import ClipperBackend
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.polygon import Polygon
from fenolite.geometry.predicates import FillRule, Location, floor_sqrt
from fenolite.geometry.shapes import BBox

Criterion = Literal["M1", "M2", "M3", "M4", "M5"]
CRITERIA: tuple[Criterion, ...] = ("M1", "M2", "M3", "M4", "M5")
Side = Literal["candidate", "reference"]
GRID: Nm = 10_000
"""The grid on which M4 compares the positions of objects: two saves of one board may move a coordinate by
the 2.54 nm unit of a document."""
CONNECTED_KINDS = frozenset({"track", "arc", "via", "pad"})
"""The objects of M4: the conductors of a net (a board hole and a keep-out are none)."""

_Key = tuple[object, ...]


@dataclass(frozen=True, slots=True)
class PourPoint:
    """A declared point of a probe (M5): the polygon's name, the point in the frame of the import, and
    whether copper must stay there (``True``) or be gone (``False``)."""

    polygon: str
    at: Point
    copper: bool


@dataclass(frozen=True, slots=True)
class Difference:
    """A part of the XOR that holds a disc of diameter ``2d`` (M2): the centre of what is left of it after
    the inward offset, its area in square nanometres, and the side that holds its copper."""

    center: Point
    area: int
    side: Side


@dataclass(frozen=True, slots=True)
class Failure:
    criterion: Criterion
    message: str
    at: Point | None = None


@dataclass(frozen=True, slots=True)
class PolygonVerdict:
    """The comparison of one polygon: its key, its net, ``d``, the XOR area and its bound (M1), the
    differences of M2 and every failed criterion."""

    layer: str
    name: str
    pour_index: int
    net: str | None
    arc_resolution: Nm
    xor_area: int
    allowed: int
    pieces: tuple[int, int]
    """(candidate, reference) piece counts."""
    differences: tuple[Difference, ...]
    failures: tuple[Failure, ...]

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def ratio(self) -> float:
        """The XOR area over its bound (M1 passes at 1 or less)."""
        if self.allowed:
            return self.xor_area / self.allowed
        return 0.0 if not self.xor_area else float("inf")

    @property
    def failed(self) -> tuple[Criterion, ...]:
        return tuple(c for c in CRITERIA if any(f.criterion == c for f in self.failures))


@dataclass(frozen=True, slots=True)
class PourComparison:
    """Every compared polygon, the polygons of one side that the other does not hold (side, layer, name,
    ``POURINDEX``), and the faults of the probes (M5)."""

    polygons: tuple[PolygonVerdict, ...]
    unmatched: tuple[tuple[Side, str, str, int], ...] = ()
    probe_faults: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.unmatched and all(p.passed for p in self.polygons)

    def polygon(self, name: str) -> PolygonVerdict | None:
        return next((p for p in self.polygons if p.name == name), None)


def pour_pieces(reading: PourReading, index: int) -> tuple[Polygon, ...]:
    """The pieces of the polygon at ``index`` of ``Polygons6``: the regions that carry its index, in the
    frame of the import, each its outline and its holes."""
    found: list[Polygon] = []
    for region in reading.document.regions_of(index):
        outer = region_points(region.outline)
        holes = tuple(ring for ring in (region_points(hole) for hole in region.holes) if len(ring) >= 3)
        try:
            found.append(Polygon(outer, holes))
        except (GeometryError, ValueError):
            continue
    return tuple(found)


def _length(pieces: Iterable[Polygon]) -> float:
    return sum(
        floor_sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)
        for piece in pieces
        for ring in piece.rings()
        for a, b in zip(ring, (*ring[1:], ring[0]), strict=True)
    )


def _size(polys: Iterable[Polygon]) -> int:
    return int(sum((area(p) for p in polys), start=Fraction(0)))


def _inside(pieces: Sequence[Polygon], at: Point) -> bool:
    return any(piece.locate(at, FillRule.EVENODD) != Location.OUTSIDE for piece in pieces)


def _grid(value: int) -> int:
    return round(value / GRID)


def _key(item: PourObject) -> _Key:
    core, _, filled = item.shape
    if item.kind in ("pad", "via"):
        center = item.center
        if center is None:
            box = BBox.of_points(core)
            center = Point((box.x0 + box.x1) // 2, (box.y0 + box.y1) // 2)
        ref = (item.ref or "",) if item.kind == "pad" else ()
        return (item.kind, *ref, _grid(center.x), _grid(center.y))
    ends = sorted(((_grid(core[0].x), _grid(core[0].y)), (_grid(core[-1].x), _grid(core[-1].y))))
    return (item.kind, *ends, filled)


class _Copper:
    """The conductors of the nets of the compared polygons on each side, as polygons."""

    def __init__(self, reading: PourReading, nets: set[str], backend: ClipperBackend, tol: int) -> None:
        self.backend, self.tol = backend, tol
        objects = LayerObjects(reading, tol)
        self.by_layer: dict[str, list[tuple[_Key, str, tuple[Polygon, ...], BBox, Point]]] = {}
        for layer, items in objects.by_layer.items():
            for item in items:
                if item.kind not in CONNECTED_KINDS or item.net not in nets:
                    continue
                shape = self._shape(item)
                if not shape:
                    continue
                box = BBox.of_points([p for poly in shape for p in poly.outer])
                assert item.net is not None
                self.by_layer.setdefault(layer, []).append(
                    (_key(item), item.net, shape, box, self._point(item))
                )

    def _shape(self, item: PourObject) -> tuple[Polygon, ...]:
        core, width, filled = item.shape
        half = width // 2
        try:
            if filled:
                ring = Polygon(core)
                return self.backend.offset((ring,), half, join="round", tol=self.tol) if half > 0 else (ring,)
            if len(set(core)) == 1:
                return (disc(core[0], max(half, 1), self.tol),)
            return self.backend.stroke([core], max(half, 1), tol=self.tol)
        except (GeometryError, ValueError):
            return ()

    @staticmethod
    def _point(item: PourObject) -> Point:
        """A point of the object's copper: its centre, or the start of its centre line."""
        core, _, filled = item.shape
        if item.center is not None:
            return item.center
        if filled:
            return Point(sum(p.x for p in core) // len(core), sum(p.y for p in core) // len(core))
        return core[0]

    def touched(self, layer: str, net: str | None, piece: Polygon) -> frozenset[_Key]:
        """The objects of ``net`` on ``layer`` whose copper meets ``piece``."""
        box = piece.bbox()
        return frozenset(
            key
            for key, owner, shape, found, _ in self.by_layer.get(layer, [])
            if owner == net and found.intersects(box) and self.backend.intersection([piece], shape)
        )

    def groups(self, net: str, pours: Mapping[str, Sequence[Polygon]]) -> frozenset[frozenset[_Key]]:
        """The objects of ``net`` grouped by the copper that connects them, ``pours`` (layer → pieces of the
        net's polygons on that side) included."""
        parent: dict[object, object] = {}

        def find(node: object) -> object:
            parent.setdefault(node, node)
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        keys: set[_Key] = set()
        for layer in sorted(set(self.by_layer) | set(pours)):
            items = [entry for entry in self.by_layer.get(layer, []) if entry[1] == net]
            copper = [poly for entry in items for poly in entry[2]] + list(pours.get(layer, ()))
            regions = self.backend.union(copper) if copper else ()
            for key, _, _, found, point in items:
                keys.add(key)
                find(key)
                for number, region in enumerate(regions):
                    if (
                        region.bbox().intersects(found)
                        and region.locate(point, FillRule.EVENODD) != Location.OUTSIDE
                    ):
                        parent[find(key)] = find((layer, number))
                        break
        grouped: dict[object, set[_Key]] = {}
        for key in keys:
            grouped.setdefault(find(key), set()).add(key)
        return frozenset(frozenset(group) for group in grouped.values())


def _match(
    candidate: Sequence[Polygon], reference: Sequence[Polygon], backend: ClipperBackend
) -> list[tuple[int, int]]:
    """The pairs (candidate piece, reference piece) that overlap by more than half the smaller area."""
    pairs: list[tuple[int, int]] = []
    sizes_a = [area(p) for p in candidate]
    sizes_b = [area(p) for p in reference]
    for i, a in enumerate(candidate):
        for j, b in enumerate(reference):
            if not a.bbox().intersects(b.bbox()):
                continue
            common = sum((area(p) for p in backend.intersection([a], [b])), start=Fraction(0))
            if common * 2 > min(sizes_a[i], sizes_b[j]):
                pairs.append((i, j))
    return pairs


def _center(polys: Sequence[Polygon]) -> Point:
    box = BBox.of_points([p for poly in polys for p in poly.outer])
    return Point((box.x0 + box.x1) // 2, (box.y0 + box.y1) // 2)


@dataclass(frozen=True, slots=True)
class _Entry:
    polygon: PourPolygon
    ours: tuple[Polygon, ...]
    ref: tuple[Polygon, ...]


def _judge(
    candidate: PourReading,
    reference: PourReading,
    entries: Sequence[_Entry],
    points: Sequence[PourPoint],
    criteria: Sequence[Criterion],
    backend: ClipperBackend,
) -> tuple[list[PolygonVerdict], list[str]]:
    """The verdict of each entry (a polygon of the reference with the pieces of both sides), and the
    faults of the probes."""
    connectivity = "M4" in criteria
    nets = {entry.polygon.net for entry in entries if entry.polygon.net is not None}
    tol = max(min((entry.polygon.arc_resolution for entry in entries), default=12_700) // 4, 50)
    copper: tuple[_Copper, _Copper] | None = None
    partitions: dict[str, tuple[frozenset[frozenset[_Key]], frozenset[frozenset[_Key]]]] = {}
    if connectivity and entries:
        copper = (_Copper(candidate, {n for n in nets if n}, backend, tol),
                  _Copper(reference, {n for n in nets if n}, backend, tol))  # fmt: skip
        for net in sorted(n for n in nets if n):
            pours: list[dict[str, list[Polygon]]] = [{}, {}]
            for entry in entries:
                if entry.polygon.net == net:
                    for number, found in enumerate((entry.ours, entry.ref)):
                        pours[number].setdefault(entry.polygon.layer, []).extend(found)
            partitions[net] = (copper[0].groups(net, pours[0]), copper[1].groups(net, pours[1]))
    faults: list[str] = []
    verdicts: list[PolygonVerdict] = []
    for entry in entries:
        polygon, ours, ref = entry.polygon, entry.ours, entry.ref
        d = polygon.arc_resolution
        failures: list[Failure] = []
        xor = backend.xor(ours, ref) if ours or ref else ()
        xor_area = _size(xor)
        allowed = int(d * _length(ref))
        if "M1" in criteria and xor_area > allowed:
            failures.append(
                Failure(
                    "M1",
                    f"the XOR area is {xor_area / allowed if allowed else float('inf'):.2f} times d × the "
                    "boundary",
                )
            )
        differences: list[Difference] = []
        if "M2" in criteria:
            for part in xor:
                left = backend.offset((part,), -d, join="round", tol=max(d // 8, 10))
                if not left:
                    continue
                size = _size((part,))
                held = _size(backend.intersection([part], ours)) if ours else 0
                side: Side = "candidate" if held * 2 > size else "reference"
                found = Difference(_center(left), size, side)
                differences.append(found)
                failures.append(
                    Failure("M2", f"a difference of {size / 1e12:.4f} mm² held by the {side}", found.center)
                )
        pairs = _match(ours, ref, backend) if ("M3" in criteria or connectivity) else []
        if "M3" in criteria:
            by_a = [j for _, j in pairs]
            by_b = [i for i, _ in pairs]
            one_to_one = (
                len(ours) == len(ref) == len(pairs)
                and len(set(by_a)) == len(by_a)
                and len(set(by_b)) == len(by_b)
            )
            if not one_to_one:
                failures.append(
                    Failure("M3", f"{len(ours)} piece(s) against {len(ref)}, {len(pairs)} matched")
                )
            for i, j in pairs:
                if len(ours[i].holes) != len(ref[j].holes):
                    failures.append(
                        Failure(
                            "M3",
                            f"a piece holds {len(ours[i].holes)} hole(s) against {len(ref[j].holes)}",
                            _center((ref[j],)),
                        )  # fmt: skip
                    )
        if connectivity and copper is not None:
            for i, j in pairs:
                a = copper[0].touched(polygon.layer, polygon.net, ours[i])
                b = copper[1].touched(polygon.layer, polygon.net, ref[j])
                if a != b:
                    failures.append(
                        Failure(
                            "M4", f"a piece touches {len(a)} object(s) against {len(b)}", _center((ref[j],))
                        )
                    )
            if polygon.net is not None and polygon.net in partitions:
                found_a, found_b = partitions[polygon.net]
                if found_a != found_b:
                    failures.append(
                        Failure(
                            "M4",
                            f"the net {polygon.net} forms {len(found_a)} connected group(s) against "
                            f"{len(found_b)}",
                        )  # fmt: skip
                    )
        if "M5" in criteria:
            for point in points:
                if point.polygon != polygon.name:
                    continue
                here, there = _inside(ours, point.at), _inside(ref, point.at)
                if here != there:
                    held = "the candidate" if here else "the reference"
                    failures.append(Failure("M5", f"only {held} holds copper at a declared point", point.at))
                elif here != point.copper:
                    state = "copper" if here else "no copper"
                    faults.append(
                        f"probe {polygon.name}: both sides hold {state} at ({point.at.x}, {point.at.y}), "
                        f"which is declared {'copper' if point.copper else 'empty'}"
                    )
        verdicts.append(
            PolygonVerdict(
                layer=polygon.layer,
                name=polygon.name,
                pour_index=polygon.pour_index,
                net=polygon.net,
                arc_resolution=d,
                xor_area=xor_area,
                allowed=allowed,
                pieces=(len(ours), len(ref)),
                differences=tuple(differences),
                failures=tuple(failures),
            )
        )
    return verdicts, faults


def compare_pours(
    candidate: PourReading,
    reference: PourReading,
    *,
    points: Sequence[PourPoint] = (),
    criteria: Sequence[Criterion] = CRITERIA,
    backend: ClipperBackend | None = None,
) -> PourComparison:
    """The comparison of the pours of ``candidate`` with those of ``reference`` (two readings of one board)
    by ``criteria``; ``points`` are the declared points of M5. ``BackendUnavailable`` without the ``geo``
    extra."""
    backend = backend or ClipperBackend()

    def keyed(reading: PourReading) -> dict[tuple[str, str, int], PourPolygon]:
        return {(p.layer, p.name, p.pour_index): p for p in polygons_of(reading)}

    mine, theirs = keyed(candidate), keyed(reference)
    unmatched: list[tuple[Side, str, str, int]] = []
    for key in sorted(set(mine) - set(theirs)):
        unmatched.append(("candidate", *key))
    for key in sorted(set(theirs) - set(mine)):
        unmatched.append(("reference", *key))
    shared = sorted(set(mine) & set(theirs), key=lambda key: theirs[key].index)
    pieces = {
        key: (pour_pieces(candidate, mine[key].index), pour_pieces(reference, theirs[key].index))
        for key in shared
    }
    entries = [_Entry(theirs[key], *pieces[key]) for key in shared]
    verdicts, faults = _judge(candidate, reference, entries, points, criteria, backend)
    return PourComparison(tuple(verdicts), tuple(unmatched), tuple(faults))


def compare_computed(
    reading: PourReading,
    result: PourResult,
    *,
    criteria: Sequence[Criterion] = ("M1", "M2", "M3", "M4"),
    backend: ClipperBackend | None = None,
) -> PourComparison:
    """The engine's pour of ``reading`` (``result``, ``pour.pour_reading``) against the regions that the
    document holds, for every polygon that the engine poured: the census of the public corpus (capability
    altium-verification, "Pour census of the public corpus"). A saved pour may be stale, or poured by
    another version or with AdvancedPour, so a failure here is a finding, not a fault of either side."""
    backend = backend or ClipperBackend()
    polygons = {p.index: p for p in polygons_of(reading)}
    entries = [
        _Entry(polygons[pour.index], pour.pieces, pour_pieces(reading, pour.index))
        for pour in result.polygons
        if pour.poured and pour.index in polygons
    ]
    verdicts, faults = _judge(reading, reading, entries, (), criteria, backend)
    return PourComparison(tuple(verdicts), (), tuple(faults))


__all__ = [
    "CRITERIA",
    "GRID",
    "Criterion",
    "Difference",
    "Failure",
    "PolygonVerdict",
    "PourComparison",
    "PourPoint",
    "compare_computed",
    "compare_pours",
    "pour_pieces",
]
