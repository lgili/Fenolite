# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Test points placed on a board for the nets that a probe cannot reach from one side (capability
assembly-test-features, "Test-point placement" and "Placed test points"; change c0229; user guide
``docs/assembly.md``, "Placing test points").

For each eligible net (``testpoints.report``) without access from ``side``, the search looks at the sites of
a grid of ``grid`` within ``reach`` of an anchor of the net on the side's outer copper layer (a pad centre,
a via, a track or arc end), nearest first, and takes the first site where a probe pad of ``size`` and its
straight track to the anchor keep every clearance:

- the clearance in force (``clearance``) to the copper of other nets on that layer, to every drilled hole
  but the net's own under the track, and to the probes and tracks placed before;
- ``edge_clearance`` to the board edge, the site inside the board's material;
- no contact of the probe with a courtyard face of that side (a courtyard stands for a part's body), nor
  with a rule area of that layer that forbids footprints or pads; no contact of the track with one that
  forbids tracks;
- at least ``min_pitch`` between the centres of two probes.

The probe is the part ``design.test_point`` generates (``footprint``, built by the caller from
``fenolite.dsl.assembly``), placed without ``fenolite.path``: a board-only footprint, which a rebuild keeps
(``docs/lens.md``, "Board-only footprints"), as it keeps the track (a track drawn on the board). Distances
are decided exactly on integer thick shapes (``geometry.thick``); no float is used.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from math import isqrt
from typing import Literal

from fenolite.backends.base import BoardPad, EdgeRing, PlacedExtent
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.fields import set_field
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm, format_length
from fenolite.exports.assembly import natural_key
from fenolite.exports.codes import issue
from fenolite.exports.testpoints import Report
from fenolite.geometry import (
    DEFAULT_TOL,
    Arc,
    BBox,
    GeometryError,
    Location,
    SpatialIndex,
    Thick,
    point_in_ring,
    thick_bbox,
    thick_closer_than,
)
from fenolite.model.board import Board, Side, Track
from fenolite.model.circuit import Component, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

HYPOTHESIS = "H-K-TP-PLACE"
"""The register row that probes placed by this search give KiCad's DRC no new finding."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=(HYPOTHESIS,))
"""``INFERRED`` until ``--drc`` runs: the search is checked on benches, not on every board."""
BACKEND = "fenolite.testpoints"
"""The namespace of the ids and uuids of placed probes and tracks."""
DEFAULT_GRID: Nm = 2_540_000
DEFAULT_REACH: Nm = 5_000_000
DEFAULT_SIZE: Nm = 1_000_000
DEFAULT_MIN_PITCH: Nm = 1_270_000
DEFAULT_WIDTH: Nm = 250_000
"""The track width of a net whose class names none (KiCad's default net class)."""
OUTER: Mapping[str, str] = {"top": "F.Cu", "bottom": "B.Cu"}
_TP = re.compile(r"TP(\d+)")

Kind = Literal["copper", "hole", "edge", "courtyard", "area", "probe", "silk"]


@dataclass(frozen=True, slots=True)
class Settings:
    """What ``place_probes`` is asked: the side, the grid, the reach, the probe size, the least probe pitch,
    the net globs, the clearance in force to other copper and holes, and the edge clearance."""

    side: Side
    grid: Nm = DEFAULT_GRID
    reach: Nm = DEFAULT_REACH
    size: Nm = DEFAULT_SIZE
    min_pitch: Nm = DEFAULT_MIN_PITCH
    nets: tuple[str, ...] = ("*",)
    clearance: Nm = 0
    edge_clearance: Nm = 0


@dataclass(frozen=True, slots=True)
class _Blocker:
    shape: Thick
    box: BBox
    what: str
    kind: Kind
    net: str | None
    gap: Nm
    probe: bool = True
    track: bool = True


@dataclass(frozen=True, slots=True)
class Probe:
    """One placed probe: its reference, net, position, the anchor its track runs to and the track's length
    and width (length 0: the probe sits on the anchor, without a track)."""

    ref: str
    net: str
    position: Point
    anchor: Point
    length: Nm
    width: Nm

    def to_json(self) -> dict[str, object]:
        return {
            "ref": self.ref,
            "net": self.net,
            "position": [self.position.x, self.position.y],
            "anchor": [self.anchor.x, self.anchor.y],
            "track_length": self.length,
            "track_width": self.width,
        }


@dataclass(frozen=True, slots=True)
class Unplaced:
    """A net without a site: the nearest site looked at (``None`` when none was) and what blocks it."""

    net: str
    site: Point | None
    blocker: str

    def to_json(self) -> dict[str, object]:
        at = None if self.site is None else [self.site.x, self.site.y]
        return {"net": self.net, "site": at, "blocker": self.blocker}


@dataclass(frozen=True, slots=True)
class Outcome:
    """The design with the probes and tracks, the probes in placement order, the nets left without a site,
    the issues, and the ids of the written items per probe reference (footprint first, then its track)."""

    design: Design
    probes: tuple[Probe, ...]
    unplaced: tuple[Unplaced, ...]
    issues: tuple[Issue, ...]
    items: Mapping[str, tuple[str, ...]]


def _mm(point: Point) -> str:
    return f"({format_length(point.x)}, {format_length(point.y)})"


def _ring_shape(ring: EdgeRing) -> Thick:
    points: list[Point] = []
    count = len(ring.points)
    for index in range(count):
        start, end = ring.points[index], ring.points[(index + 1) % count]
        mid = ring.mids[index]
        if mid is None:
            points.append(start)
            continue
        try:
            points.extend(Arc(start, mid, end).polygonize(DEFAULT_TOL)[:-1])
        except GeometryError:
            points.extend((start, mid))
    points.append(points[0])
    width = 2 * DEFAULT_TOL + 2 if any(mid is not None for mid in ring.mids) else 0
    return Thick(tuple(points), width)


def _filled(ring: Sequence[Point]) -> Thick | None:
    try:
        return Thick(tuple(ring), 0, filled=True)
    except (GeometryError, ValueError):
        return None


def _spans(layers: Sequence[str], via_type: str, layer: str) -> bool:
    return via_type == "through" or layer in layers


class _Scene:
    """The blockers of one side, indexed by box."""

    def __init__(self, blockers: Iterable[_Blocker]) -> None:
        self.blockers = list(blockers)
        boxes = [(b.box, n) for n, b in enumerate(self.blockers)]
        self.index: SpatialIndex[int] = SpatialIndex[int].build(boxes)
        self.added: list[_Blocker] = []

    def add(self, blocker: _Blocker) -> None:
        self.added.append(blocker)

    def near(self, shape: Thick, reach: Nm) -> list[_Blocker]:
        box = thick_bbox(shape)
        grown = BBox(box.x0 - reach, box.y0 - reach, box.x1 + reach, box.y1 + reach)
        found = [self.blockers[n] for n in sorted(self.index.query_indices(grown))]
        return found + self.added

    def first(self, shape: Thick, net: str, *, track: bool, reach: Nm) -> _Blocker | None:
        """The first blocker that ``shape`` (the probe, or its track with ``track``) of ``net`` meets."""
        for blocker in self.near(shape, reach):
            if not (blocker.track if track else blocker.probe):
                continue
            if blocker.net == net and (blocker.kind != "hole" or track):
                continue
            if blocker.kind in ("courtyard", "area", "silk"):
                if thick_closer_than(shape, blocker.shape, 1):
                    return blocker
            elif thick_closer_than(shape, blocker.shape, blocker.gap):
                return blocker
        return None


def _names(design: Design) -> dict[str, str]:
    return {net.id: net.name for net in design.circuit.nets}


def _scene(
    design: Design,
    pads: Sequence[BoardPad],
    extents: Sequence[PlacedExtent],
    edges: Sequence[EdgeRing] | None,
    settings: Settings,
    ink: Sequence[tuple[Thick, str]],
) -> _Scene:
    board = design.board
    assert board is not None
    layer = OUTER[settings.side]
    names = _names(design)
    gap = settings.clearance
    found: list[_Blocker] = []

    def add(shape: Thick, what: str, kind: Kind, net: str | None, need: Nm, *, probe: bool = True,
            track: bool = True) -> None:  # fmt: skip
        found.append(_Blocker(shape, thick_bbox(shape), what, kind, net, need, probe, track))

    for pad in pads:
        name = f"pad {pad.ref or pad.footprint_id}-{pad.number}" if pad.number else f"a pad of {pad.ref}"
        for entry in pad.copper:
            if entry.layer != layer:
                continue
            try:
                shape = Thick(entry.core, entry.width, entry.filled)
            except (GeometryError, ValueError):
                continue
            add(shape, name, "copper", pad.net, gap)
        if pad.hole and pad.drill:
            add(Thick(tuple(pad.hole), pad.drill), f"the hole of {name}", "hole", pad.net, gap)
    for track in board.tracks:
        if track.layer == layer:
            net = names.get(track.net_id or "")
            add(Thick((track.start, track.end), track.width), "a track", "copper", net, gap)
    for arc in board.arcs:
        if arc.layer != layer:
            continue
        try:
            core = tuple(Arc(arc.start, arc.mid, arc.end).polygonize(DEFAULT_TOL))
        except (GeometryError, ValueError):
            core = (arc.start, arc.mid, arc.end)
        net = names.get(arc.net_id or "")
        add(Thick(core, arc.width + 2 * DEFAULT_TOL + 2), "an arc", "copper", net, gap)
    for via in board.vias:
        net = names.get(via.net_id or "")
        if _spans(via.layers, via.via_type, layer):
            add(Thick((via.position,), via.diameter), "a via", "copper", net, gap)
        add(Thick((via.position,), via.drill), "the hole of a via", "hole", net, gap)
    for zone in board.zones:
        net = names.get(zone.net_id or "")
        for fill in zone.fills:
            if fill.layer == layer and (shape := _filled(fill.polygon)) is not None:
                add(shape, f"the fill of zone {zone.name or zone.id}", "copper", net, gap)
    for keepout in board.keepouts:
        if layer not in keepout.layers and not any(name in ("*.Cu", "F&B.Cu") for name in keepout.layers):
            continue
        shape = _filled(keepout.outline)
        probe = keepout.no_footprints or keepout.no_pads
        if shape is not None and (probe or keepout.no_tracks):
            what = f"rule area {keepout.name or keepout.id}"
            add(shape, what, "area", None, 0, probe=probe, track=keepout.no_tracks)
    refs = {fp.id: _ref(design, fp.id) for fp in board.footprints}
    for extent in extents:
        rings = extent.front if settings.side == "top" else extent.back
        for ring in rings:
            if (shape := _filled(ring)) is not None:
                owner = refs.get(extent.footprint_id, extent.footprint_id)
                add(shape, f"the courtyard of {owner}", "courtyard", None, 0, track=False)
    for shape, what in ink:
        add(shape, what, "silk", None, 0, track=False)
    for ring in edges or ():
        add(_ring_shape(ring), f"the board edge ({ring.name})", "edge", None, settings.edge_clearance)
    return _Scene(found)


def _ref(design: Design, footprint_id: str) -> str:
    board = design.board
    assert board is not None
    components = {c.id: c.ref for c in design.circuit.components}
    for footprint in board.footprints:
        if footprint.id == footprint_id:
            return components.get(footprint.component_id, footprint_id)
    return footprint_id


def _anchors(design: Design, pads: Sequence[BoardPad], net: str, layer: str) -> list[Point]:
    board = design.board
    assert board is not None
    names = _names(design)
    found: set[Point] = set()
    for pad in pads:
        if pad.net == net and any(entry.layer == layer for entry in pad.copper):
            found.add(pad.position)
    for track in board.tracks:
        if track.layer == layer and names.get(track.net_id or "") == net:
            found.update((track.start, track.end))
    for arc in board.arcs:
        if arc.layer == layer and names.get(arc.net_id or "") == net:
            found.update((arc.start, arc.end))
    for via in board.vias:
        if names.get(via.net_id or "") == net and _spans(via.layers, via.via_type, layer):
            found.add(via.position)
    return sorted(found, key=lambda p: (p.y, p.x))


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def sites(anchors: Sequence[Point], grid: Nm, reach: Nm) -> list[tuple[int, Point, Point]]:
    """``(squared distance, site, anchor)`` of every grid site within ``reach`` of an anchor, each with its
    nearest anchor (the first in ``anchors`` order on a tie), nearest first, then by y and x."""
    best: dict[Point, tuple[int, Point]] = {}
    limit = reach * reach
    for anchor in anchors:
        for gx in range(_ceil_div(anchor.x - reach, grid), (anchor.x + reach) // grid + 1):
            for gy in range(_ceil_div(anchor.y - reach, grid), (anchor.y + reach) // grid + 1):
                site = Point(gx * grid, gy * grid)
                d2 = (site.x - anchor.x) ** 2 + (site.y - anchor.y) ** 2
                if d2 <= limit and (site not in best or d2 < best[site][0]):
                    best[site] = (d2, anchor)
    return sorted(((d2, site, anchor) for site, (d2, anchor) in best.items()),
                  key=lambda row: (row[0], row[1].y, row[1].x))  # fmt: skip


def _inside(point: Point, edges: Sequence[EdgeRing] | None) -> bool:
    if not edges:
        return True
    count = sum(1 for ring in edges if point_in_ring(point, ring.points) == Location.INSIDE)
    return count % 2 == 1


def _next_refs(design: Design) -> Iterator[str]:
    taken = {c.ref for c in design.circuit.components}
    numbers = [int(m.group(1)) for ref in taken if (m := _TP.fullmatch(ref))]
    n = max(numbers, default=0)
    while True:
        n += 1
        if f"TP{n}" not in taken:
            yield f"TP{n}"


def place_probes(
    design: Design,
    pads: Sequence[BoardPad],
    extents: Sequence[PlacedExtent],
    edges: Sequence[EdgeRing] | None,
    report: Report,
    settings: Settings,
    *,
    footprint: FootprintDef,
    widths: Mapping[str, Nm],
    ink: Sequence[tuple[Thick, str]] = (),
) -> Outcome:
    """Place one probe for each net of ``report.coverage.uncovered`` that matches ``settings.nets``
    (``report`` taken for ``settings.side``); see the module. ``widths`` gives the track width of a net by
    name (else ``DEFAULT_WIDTH``); ``ink`` is the silkscreen of the side, which a probe does not touch.
    The design comes back with the probes, board-only footprints, and their tracks."""
    board = design.board
    assert board is not None
    layer = OUTER[settings.side]
    scene = _scene(design, pads, extents, edges, settings, ink)
    reach = max(settings.clearance, settings.edge_clearance) + settings.size
    nets = [
        name
        for name in sorted(report.coverage.uncovered, key=natural_key)
        if any(fnmatch.fnmatchcase(name, glob) for glob in settings.nets)
    ]
    refs = _next_refs(design)
    probes: list[Probe] = []
    unplaced: list[Unplaced] = []
    found: list[Issue] = []
    for net in nets:
        width = widths.get(net) or DEFAULT_WIDTH
        anchors = _anchors(design, pads, net, layer)
        candidates = sites(anchors, settings.grid, settings.reach)
        first: tuple[Point, str] | None = None
        chosen: tuple[Point, Point, int] | None = None
        for d2, site, anchor in candidates:
            why = _blocked(scene, probes, site, anchor, net, width, settings, edges, reach)
            if why is None:
                chosen = (site, anchor, d2)
                break
            if first is None:
                first = (site, why)
        if chosen is None:
            if not anchors:
                blocker = f"no copper of the net on {layer}"
            elif first is None:
                blocker = f"no point of the {format_length(settings.grid)} grid within the reach"
            else:
                blocker = first[1]
            site = None if first is None else first[0]
            unplaced.append(Unplaced(net, site, blocker))
            at = "" if site is None else f"; the nearest site, at {_mm(site)}, meets {blocker}"
            found.append(
                issue(
                    "testpoint.no-site",
                    f"net {net} has no site for a {settings.side} probe within "
                    f"{format_length(settings.reach)} of its copper on {layer}" + (at or f": {blocker}"),
                    where=net,
                    hint="raise --reach, lower --size or --grid, or make room near the net's copper",
                )
            )
            continue
        site, anchor, d2 = chosen
        length = 0 if d2 == 0 else isqrt(d2)
        probe = Probe(next(refs), net, site, anchor, length, 0 if d2 == 0 else width)
        probes.append(probe)
        disc = Thick((site,), settings.size)
        scene.add(_Blocker(disc, thick_bbox(disc), f"probe {probe.ref}", "probe", net, settings.clearance))
        scene.add(_Blocker(disc, thick_bbox(disc), f"the courtyard of {probe.ref}", "courtyard", None, 0,
                           track=False))  # fmt: skip
        if d2:
            line = Thick((site, anchor), width)
            scene.add(_Blocker(line, thick_bbox(line), f"the track of {probe.ref}", "copper", net,
                               settings.clearance))  # fmt: skip
    placed, items = write_probes(design, probes, footprint, settings.side)
    return Outcome(placed, tuple(probes), tuple(unplaced), tuple(found), items)


def _blocked(
    scene: _Scene,
    probes: Sequence[Probe],
    site: Point,
    anchor: Point,
    net: str,
    width: Nm,
    settings: Settings,
    edges: Sequence[EdgeRing] | None,
    reach: Nm,
) -> str | None:
    """What keeps a probe of ``net`` from ``site``, or ``None``."""
    if not _inside(site, edges):
        return "the outside of the board"
    for other in probes:
        dx, dy = other.position.x - site.x, other.position.y - site.y
        if dx * dx + dy * dy < settings.min_pitch * settings.min_pitch:
            return f"the pitch of probe {other.ref} ({format_length(settings.min_pitch)})"
    disc = Thick((site,), settings.size)
    hit = scene.first(disc, net, track=False, reach=reach)
    if hit is not None:
        return hit.what
    if site != anchor:
        hit = scene.first(Thick((site, anchor), width), net, track=True, reach=reach)
        if hit is not None:
            return hit.what
    return None


def write_probes(
    design: Design, probes: Sequence[Probe], footprint: FootprintDef, side: Side
) -> tuple[Design, dict[str, tuple[str, ...]]]:
    """``design`` with ``probes`` on ``side``: per probe a board-only footprint of ``footprint`` (its uuids
    derived from the net's name), its designator on the fabrication layer of the side (hidden when the
    board lacks that layer), and its track; and the ids of each probe's footprint, pads and track."""
    layer = OUTER[side]
    board = design.board
    assert board is not None
    by_name = {net.name: net for net in design.circuit.nets}
    copper = tuple(item.name for item in board.layers if item.kind == "copper") or ("F.Cu", "B.Cu")
    footprints = list(board.footprints)
    declared = {item.name for item in board.layers}
    fab = "F.Fab" if side == "top" else "B.Fab"
    tracks: list[Track] = list(board.tracks)
    components = list(design.circuit.components)
    members: dict[str, list[PinRef]] = {}
    items: dict[str, tuple[str, ...]] = {}
    for probe in probes:
        net = by_name[probe.net]
        key = f"{BACKEND}:{probe.net}"
        component = Component(
            id=derived_id("cmp", BACKEND, probe.net),
            ref=probe.ref,
            value="TestPoint",
            lib_footprint_ref=footprint.lib_id,
        )
        placed = place_footprint(
            footprint, component=component, at=probe.position, side=side, key=key, copper=copper
        )
        placed = dataclasses.replace(
            placed, pads=tuple(dataclasses.replace(pad, net_id=net.id) for pad in placed.pads)
        )
        # the designator goes to the fabrication layer, on the probe: off the silkscreen and its DRC
        placed = (
            set_field(placed, "Reference", anchor=probe.position, layer=fab)
            if fab in declared
            else set_field(placed, "Reference", visible=False)
        )
        footprints.append(placed)
        components.append(component)
        members.setdefault(net.id, []).extend(PinRef(component.id, pad.number) for pad in placed.pads)
        ids: tuple[str, ...] = (placed.id, *(pad.id for pad in placed.pads))
        if probe.length:
            track = Track(
                id=derived_id("trk", BACKEND, probe.net),
                start=probe.position,
                end=probe.anchor,
                width=probe.width,
                layer=layer,
                net_id=net.id,
            )
            tracks.append(track)
            ids += (track.id,)
        items[probe.ref] = ids
    nets = tuple(
        dataclasses.replace(net, members=tuple(sorted((*net.members, *members[net.id]))))
        if net.id in members
        else net
        for net in design.circuit.nets
    )
    circuit = dataclasses.replace(design.circuit, components=tuple(components), nets=nets)
    new_board: Board = dataclasses.replace(board, footprints=tuple(footprints), tracks=tuple(tracks))
    return dataclasses.replace(design, circuit=circuit, board=new_board), items


__all__ = [
    "BACKEND",
    "DEFAULT_GRID",
    "DEFAULT_MIN_PITCH",
    "DEFAULT_REACH",
    "DEFAULT_SIZE",
    "DEFAULT_WIDTH",
    "EVIDENCE",
    "HYPOTHESIS",
    "OUTER",
    "Outcome",
    "Probe",
    "Settings",
    "Unplaced",
    "place_probes",
    "sites",
    "write_probes",
]
