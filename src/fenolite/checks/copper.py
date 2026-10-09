# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Shorts and clearance of a board's copper, decided exactly and without any external tool (capability
copper-check; user guide ``docs/cli-contract.md``, facts ``docs/formats/kicad/copper.md``).

Every copper item becomes one or more thick shapes (``geometry.thick``), each on one copper layer and one
net: a track is its segment, an arc the polyline of its polygonisation within a stated band, a via a disc
on every layer of its span, a pad the entries of its board-frame record, and a zone fill a filled ring.
Two items of different nets that share a layer are judged: touching copper is a short, and copper closer
than the clearance in force (``checks.clearance``) is a clearance finding. Zone outlines are not copper;
they give one Fenolite rule of their own, the overlap of two outlines of equal priority.

``check_copper`` is a pure function. ``copper_stage`` wraps it as the ``copper.clearance`` stage of
``fenolite check``; the rules and the pads reach it through the injected protocols of
``backends.base``, so this module imports no backend.
"""

from __future__ import annotations

import fnmatch
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.backends.base import BoardFrame, BoardPad, DesignRules, DesignRulesSource, ProjectSet
from fenolite.checks.clearance import (
    ZONE_SOURCE,
    Clearance,
    ClearanceExplanation,
    ClearanceResolver,
    CopperKind,
)
from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.checks.waivers import COPPER_CODES, Candidate, apply_waivers, copper_waivers
from fenolite.checks.waivers import judge as judge_waivers
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, format_length
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import (
    GeometryError,
    Polygon,
    SpatialIndex,
    Thick,
    polygons_intersect,
    thick_bbox,
    thick_closer_than,
    thick_gap_floor,
    thick_touch,
    thick_witness,
)
from fenolite.model.base import Entity
from fenolite.model.board import Board, Keepout, Zone
from fenolite.model.design import Design
from fenolite.model.findings import Waiver
from fenolite.model.rules import RuleSubject

ARC_TOL_NM = 1_000
"""The chord error of a polygonised arc; its band is ``ARC_TOL_NM + 1`` nm."""
EVIDENCE = Evidence(
    Level.INFERRED, hypotheses=("H-K-COPPER-SHAPES", "H-K-COPPER-RESOLVE", "H-K-COPPER-ZONES")
)
"""``INFERRED`` also once the three rows are settled: the canaries cover pair kinds and clearance sources
on benches, and fills on 10.0 only, not every board."""
AREA_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-COPPER-AREA", "H-K-AREA-KEEPOUT"))
"""Joins the report of a board that holds a rule area or a keep-out (change c0103): the two rows cover
benches, recorded for 10.0.6 so far."""
NO_NET = "<no net>"
FORBIDDEN_KINDS: Mapping[str, tuple[str, str]] = {
    "track": ("no_tracks", "tracks"),
    "arc": ("no_tracks", "tracks"),
    "via": ("no_vias", "vias"),
    "pad": ("no_pads", "pads"),
}
"""Kind of a copper item → the keep-out setting that forbids it and that setting's name in a message.
Fills are never reported: KiCad's DRC does not report a stored fill in a copper-pour keep-out and its
filler leaves the area out (``H-K-AREA-KEEPOUT``)."""
APPROXIMATED = " (approximated pad shape)"
_WILDCARDS = ("*", "&")


@dataclass(frozen=True, slots=True)
class CopperRef:
    """One item of a finding: its kind, where it is (``REF-PIN`` for a pad, else the entity's locator or
    id; a fill is located by its zone), its entity id and its net name."""

    kind: CopperKind
    where: str
    entity_id: str
    net: str
    footprint_id: str = ""
    net_id: str | None = None


@dataclass(frozen=True, slots=True)
class CopperFinding:
    """A short, a clearance violation or a zone overlap: the layer, a point, both items, the gap in
    nanometres (0 for a short; a lower bound for arcs) and the clearance in force with its source."""

    code: str
    severity: Severity
    layer: str
    at: Point
    items: tuple[CopperRef, CopperRef]
    gap: Nm
    clearance: Nm | None
    source: str
    message: str
    explanation: ClearanceExplanation | None = None

    @property
    def relation(self) -> str:
        first, second = self.items
        if first.footprint_id and second.footprint_id:
            return "intrinsic" if first.footprint_id == second.footprint_id else "inter_component"
        return "routed_or_free"

    @property
    def where(self) -> str:
        return ", ".join(item.where for item in self.items)

    def to_issue(self) -> Issue:
        return issue(self.code, self.message, severity=self.severity, where=self.where)


@dataclass(frozen=True, slots=True)
class CopperReport:
    """What ``check_copper`` returns: the findings, one issue per finding followed by the other issues,
    the counts, and the evidence."""

    findings: tuple[CopperFinding, ...]
    issues: tuple[Issue, ...]
    summary: Mapping[str, object] = field(default_factory=lambda: {})
    evidence: Evidence = Evidence()


@dataclass(frozen=True, slots=True)
class CopperReviewGroup:
    relation: str
    source: str
    findings: tuple[CopperFinding, ...]


def group_findings(report: CopperReport) -> tuple[CopperReviewGroup, ...]:
    """Group for review without dropping, rewriting or exempting any original finding."""
    groups: dict[tuple[str, str], list[CopperFinding]] = {}
    for finding in report.findings:
        groups.setdefault((finding.relation, finding.source), []).append(finding)
    return tuple(
        CopperReviewGroup(relation, source, tuple(findings))
        for (relation, source), findings in sorted(groups.items())
    )


# --- copper items ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Shape:
    """A thick shape of an item on a layer. ``narrow`` is the shape a short is judged with and ``wide``
    the one a clearance is judged with; they differ only for an arc, by its band."""

    item: int
    narrow: Thick
    wide: Thick
    exact: bool = True

    @property
    def banded(self) -> bool:
        """True for an arc: its two shapes differ by its band."""
        return self.narrow is not self.wide


@dataclass(slots=True)
class _Item:
    ref: CopperRef
    net_id: str | None
    component: str | None = None
    shapes: dict[str, list[_Shape]] = field(default_factory=lambda: {})
    zone_clearance: Nm | None = None
    """For a fill: the own clearance of its zone (``settings.clearance``)."""
    tie: tuple[str, int] | None = None
    """For a pad whose number is in a net-tie group of its footprint: the footprint's id and the index of
    that group (change c0114). Two pads with one ``tie`` are not judged."""


def _sort_key(found: Issue) -> tuple[str, str, str]:
    return found.code, found.where, found.message


def _mm(value: int) -> str:
    return format_length(value)[:-2]


def _point(at: Point) -> str:
    return f"({_mm(at.x)}, {_mm(at.y)}) mm"


def _where(entity: Entity) -> str:
    provenance = entity.provenance
    return provenance.locator if provenance is not None and provenance.locator else entity.id


def copper_layers(board: Board) -> tuple[str, ...]:
    """The copper layers of the board, in table order."""
    return tuple(layer.name for layer in board.layers if layer.kind == "copper")


def _names_copper(layers: Sequence[str], copper: Sequence[str]) -> bool:
    """Whether a pad's layer list names a copper layer of the board (``*.Cu`` and ``F&B.Cu`` included)."""
    known = set(copper)
    for name in layers:
        if name in known:
            return True
        if any(mark in name for mark in _WILDCARDS) and name.endswith(".Cu"):
            pattern = name.replace("F&B", "[FB]")
            if not copper or any(fnmatch.fnmatchcase(layer, pattern) for layer in copper):
                return True
    return False


def _clean_ring(points: Sequence[Point]) -> tuple[Point, ...]:
    """A stored polygon without consecutive repeats and without a closing copy of its first point."""
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return tuple(out)


class _Items:
    """The copper items of a board and what was left out."""

    def __init__(self, design: Design, pads: Sequence[BoardPad] | None, arc_tol: int) -> None:
        board = design.board
        assert board is not None
        self.items: list[_Item] = []
        self.unsupported: Counter[str] = Counter()
        self.approximated = 0
        self.kinds: Counter[str] = Counter()
        self.copper = copper_layers(board)
        self._nets = {net.id: net.name for net in design.circuit.nets}
        self._band = arc_tol + 1
        self._ties: dict[str, dict[str, int]] = {}
        for footprint in board.footprints:
            groups: dict[str, int] = {}
            for index, group in enumerate(footprint.net_ties):
                for number in group:
                    groups.setdefault(number, index)
            if groups:
                self._ties[footprint.id] = groups
        self._tracks(board)
        self._arcs(board, arc_tol)
        self._vias(board)
        self._pads(board, pads)
        self._fills(board)

    def net_name(self, net_id: str | None) -> str:
        return NO_NET if net_id is None else self._nets.get(net_id, net_id)

    def _add(self, item: _Item, shapes: Sequence[tuple[str, Thick, Thick, bool]]) -> None:
        index = len(self.items)
        for layer, narrow, wide, exact in shapes:
            item.shapes.setdefault(layer, []).append(_Shape(index, narrow, wide, exact))
        self.items.append(item)
        self.kinds[item.ref.kind] += 1

    def _ref(self, kind: CopperKind, entity: Entity, net_id: str | None) -> CopperRef:
        return CopperRef(kind, _where(entity), entity.id, self.net_name(net_id), net_id=net_id)

    def _tracks(self, board: Board) -> None:
        for track in board.tracks:
            shape = Thick((track.start, track.end), track.width)
            item = _Item(self._ref("track", track, track.net_id), track.net_id)
            self._add(item, [(track.layer, shape, shape, True)])

    def _arcs(self, board: Board, arc_tol: int) -> None:
        for arc in board.arcs:
            try:
                core = GeoArc(arc.start, arc.mid, arc.end).polygonize(arc_tol)
                narrow = Thick(core, max(0, arc.width - 2 * self._band))
                wide = Thick(core, arc.width + 2 * self._band)
            except (GeometryError, ValueError):
                self.unsupported["arc"] += 1
                continue
            item = _Item(self._ref("arc", arc, arc.net_id), arc.net_id)
            self._add(item, [(arc.layer, narrow, wide, True)])

    def span(self, layers: Sequence[str], through: bool) -> tuple[str, ...]:
        """The copper layers a via spans: from ``layers[0]`` to ``layers[1]`` in table order; every copper
        layer for a through via, or when ``layers`` does not name two copper layers of the board."""
        copper = self.copper
        if not copper:
            return tuple(dict.fromkeys(layers))
        if through or len(layers) != 2 or layers[0] not in copper or layers[1] not in copper:
            return copper
        first, last = sorted((copper.index(layers[0]), copper.index(layers[1])))
        return copper[first : last + 1]

    def _vias(self, board: Board) -> None:
        for via in board.vias:
            try:
                shape = Thick((via.position,), via.diameter)
            except (GeometryError, ValueError):
                self.unsupported["via"] += 1
                continue
            item = _Item(self._ref("via", via, via.net_id), via.net_id)
            layers = self.span(via.layers, via.via_type == "through")
            self._add(item, [(layer, shape, shape, True) for layer in layers])

    def _pads(self, board: Board, pads: Sequence[BoardPad] | None) -> None:
        if pads is None:
            for footprint in board.footprints:
                for pad in footprint.pads:
                    if pad.kind != "np_thru_hole" and _names_copper(pad.layers, self.copper):
                        self.unsupported["pad"] += 1
            return
        for record in pads:
            if record.kind == "np_thru_hole":
                continue
            if not record.copper:
                if _names_copper(record.layers, self.copper):
                    self.unsupported["pad"] += 1
                continue
            try:
                shapes = [
                    (entry.layer, Thick(entry.core, entry.width, entry.filled), entry.exact)
                    for entry in record.copper
                ]
            except (GeometryError, ValueError):
                self.unsupported["pad"] += 1
                continue
            self.approximated += sum(1 for _, _, exact in shapes if not exact)
            holder = record.ref or record.footprint_id
            where = f"{holder}-{record.number}" if record.number else holder
            ref = CopperRef(
                "pad", where, record.pad_id, self.net_name(record.net_id), record.footprint_id, record.net_id
            )
            group = self._ties.get(record.footprint_id, {}).get(record.number) if record.number else None
            tie = None if group is None else (record.footprint_id, group)
            item = _Item(ref, record.net_id, record.ref or None, tie=tie)
            self._add(item, [(layer, shape, shape, exact) for layer, shape, exact in shapes])

    def _fills(self, board: Board) -> None:
        for zone in board.zones:
            shapes: list[tuple[str, Thick, Thick, bool]] = []
            for fill in zone.fills:
                try:
                    shape = Thick(_clean_ring(fill.polygon), 0, filled=True)
                except (GeometryError, ValueError):
                    self.unsupported["fill"] += 1
                    continue
                shapes.append((fill.layer, shape, shape, True))
            if shapes:
                item = _Item(
                    CopperRef("fill", _where(zone), zone.id, self.net_name(zone.net_id), net_id=zone.net_id),
                    zone.net_id,
                    zone_clearance=zone.settings.clearance,
                )
                self._add(item, shapes)
                self.kinds["fill"] += len(shapes) - 1  # fills are counted, not zones


# --- rule areas and keep-outs ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Area:
    keepout: Keepout
    shape: Thick
    label: str
    """The area's name, else its locator."""


def _area_on(keepout: Keepout, layer: str) -> bool:
    """Whether ``layer`` is one of the area's layers (``*.Cu`` and ``F&B.Cu`` included)."""
    for name in keepout.layers:
        if name == layer:
            return True
        if any(mark in name for mark in _WILDCARDS) and fnmatch.fnmatchcase(
            layer, name.replace("F&B", "[FB]")
        ):
            return True
    return False


class _Areas:
    """The rule areas of a board whose outline can be shaped, and which items lie in them. An item lies in
    an area on a layer when the layer is one of the area's and its narrow shape touches the area's outline
    taken as a filled polygon: copper, not centre lines (``H-K-AREA-COND``)."""

    def __init__(self, board: Board, items: _Items) -> None:
        self.items = items
        self.areas: list[_Area] = []
        for keepout in board.keepouts:
            try:
                ring = Polygon(_clean_ring(keepout.outline)).outer
                shape = Thick(ring, 0, filled=True)
            except (GeometryError, ValueError):
                items.unsupported["rule-area"] += 1
                continue
            self.areas.append(_Area(keepout, shape, keepout.name or _where(keepout)))
        self.named = sum(1 for area in self.areas if area.keepout.name)
        self._index = SpatialIndex[int].build((thick_bbox(a.shape), i) for i, a in enumerate(self.areas))
        self._memo: dict[tuple[int, str], tuple[int, ...]] = {}

    def of(self, index: int, layer: str) -> tuple[int, ...]:
        """The areas (their positions in ``areas``) that item ``index`` lies in on ``layer``."""
        key = (index, layer)
        found = self._memo.get(key)
        if found is None:
            hits: set[int] = set()
            if self.areas:
                for shape in self.items.items[index].shapes.get(layer, ()):
                    for k in self._index.query(thick_bbox(shape.narrow)):
                        area = self.areas[k]
                        if (
                            k not in hits
                            and _area_on(area.keepout, layer)
                            and thick_touch(shape.narrow, area.shape)
                        ):
                            hits.add(k)
            found = tuple(sorted(hits))
            self._memo[key] = found
        return found

    def names(self, index: int, layer: str) -> frozenset[str]:
        """The names of the rule areas item ``index`` lies in on ``layer``."""
        if not self.named:
            return frozenset()
        return frozenset(
            self.areas[k].keepout.name for k in self.of(index, layer) if self.areas[k].keepout.name
        )

    def findings(self, layers: Sequence[str]) -> list[CopperFinding]:
        """One ``copper.keepout`` per item and keep-out whose settings forbid the item's kind, on the first
        layer, in ``layers`` order, where the item lies in it."""
        forbidding = {k for k, a in enumerate(self.areas) if any(
            getattr(a.keepout, setting) for setting, _ in FORBIDDEN_KINDS.values()
        )}  # fmt: skip
        found: list[CopperFinding] = []
        if not forbidding:
            return found
        for index, item in enumerate(self.items.items):
            rule = FORBIDDEN_KINDS.get(item.ref.kind)
            if rule is None:
                continue
            setting, plural = rule
            seen: set[int] = set()
            for layer in layers:
                if layer not in item.shapes:
                    continue
                for k in self.of(index, layer):
                    area = self.areas[k]
                    if k in seen or k not in forbidding or not getattr(area.keepout, setting):
                        continue
                    seen.add(k)
                    shape = next(s.narrow for s in item.shapes[layer] if thick_touch(s.narrow, area.shape))
                    at = thick_witness(shape, area.shape)
                    ref = CopperRef("keepout", area.label, area.keepout.id, NO_NET)
                    message = (
                        f"{item.ref.kind} of {item.ref.net} lies in the keep-out {area.label}, which forbids "
                        f"{plural}, on {layer} at {_point(at)}"
                    )
                    found.append(
                        CopperFinding(
                            "copper.keepout",
                            "error",
                            layer,
                            at,
                            (item.ref, ref),
                            0,
                            None,
                            f"keepout:{area.label}",
                            message,
                        )
                    )
        return found


# --- zone outlines --------------------------------------------------------------------------------


def _zone_overlaps(board: Board, items: _Items) -> list[CopperFinding]:
    """One ``copper.zone-overlap`` per pair of zones of different nets, equal priority and a shared copper
    layer whose outlines intersect."""
    usable: list[tuple[Zone, Polygon]] = []
    for zone in board.zones:
        try:
            usable.append((zone, Polygon(_clean_ring(zone.outline))))
        except GeometryError:
            items.unsupported["zone-outline"] += 1
    found: list[CopperFinding] = []
    rank = {name: index for index, name in enumerate(items.copper)}
    for i, (first, outline_a) in enumerate(usable):
        for second, outline_b in usable[i + 1 :]:
            if first.net_id == second.net_id or first.priority != second.priority:
                continue
            shared = sorted(
                set(first.layers) & set(second.layers), key=lambda name: (rank.get(name, len(rank)), name)
            )
            shared = [name for name in shared if not rank or name in rank]
            if not shared or not polygons_intersect(outline_a, outline_b):
                continue
            refs = sorted(
                (
                    CopperRef("zone", _where(z), z.id, items.net_name(z.net_id), net_id=z.net_id)
                    for z in (first, second)
                ),
                key=lambda ref: (ref.kind, ref.where),
            )
            at = thick_witness(Thick(outline_a.outer, 0, filled=True), Thick(outline_b.outer, 0, filled=True))
            message = (
                f"zones of {refs[0].net} and {refs[1].net} of priority {first.priority} overlap on "
                f"{shared[0]} at {_point(at)}: the fill of the overlap depends on the filler's order"
            )
            found.append(
                CopperFinding(
                    "copper.zone-overlap", "warning", shared[0], at, (refs[0], refs[1]), 0, None, "", message
                )
            )
    return found


# --- pairs ----------------------------------------------------------------------------------------

_Pairs = dict[tuple[int, int], list[tuple[int, _Shape, _Shape]]]


def _judged(a: _Item, b: _Item) -> bool:
    """Two items are judged when their nets differ; two items without a net are not. Two pads of one
    net-tie group of one footprint are not judged either: KiCad's DRC does not judge them
    (``H-K-NETTIE-DRC``), and the footprint joins them on purpose."""
    return a.net_id != b.net_id and (a.tie is None or a.tie != b.tie)


def _net_tie_pairs(items: Sequence[_Item]) -> int:
    """The item pairs that only their net-tie group keeps from being judged: two pads of one group whose
    nets differ, every physical pad of a repeated number counted."""
    groups: dict[tuple[str, int], list[str | None]] = {}
    for item in items:
        if item.tie is not None:
            groups.setdefault(item.tie, []).append(item.net_id)
    count = 0
    for nets in groups.values():
        count += sum(1 for i, a in enumerate(nets) for b in nets[i + 1 :] if a != b)
    return count


def _candidates(items: _Items, layers: Sequence[str], grow: int, *, every_pair: bool) -> tuple[_Pairs, int]:
    """Item pairs to judge, with their shape pairs per layer rank, and the number of candidate shape pairs.
    One index per layer over the shapes' boxes grown by ``grow``; ``every_pair`` skips the index."""
    pairs: _Pairs = {}
    count = 0
    for rank, layer in enumerate(layers):
        shapes = [shape for item in items.items for shape in item.shapes.get(layer, ())]
        if every_pair:
            found = [(p, q) for p in range(len(shapes)) for q in range(p + 1, len(shapes))]
        else:
            index = SpatialIndex[int].build(
                (thick_bbox(s.wide).inflate(grow), i) for i, s in enumerate(shapes)
            )
            found = index.pairs()
        for p, q in found:
            first, second = shapes[p], shapes[q]
            if first.item == second.item or not _judged(items.items[first.item], items.items[second.item]):
                continue
            if first.item > second.item:
                first, second = second, first
            pairs.setdefault((first.item, second.item), []).append((rank, first, second))
            count += 1
    return pairs, count


class _Judge:
    def __init__(
        self, items: _Items, layers: Sequence[str], resolver: ClearanceResolver, areas: _Areas
    ) -> None:
        self.items = items
        self.layers = layers
        self.resolver = resolver
        self.areas = areas
        self.judged = 0
        self.unset = 0
        self._subjects: dict[tuple[int, str], RuleSubject] = {}

    def _subject(self, index: int, layer: str) -> RuleSubject:
        key = (index, layer)
        found = self._subjects.get(key)
        if found is None:
            item = self.items.items[index]
            found = self.resolver.subject(
                item.ref.kind,
                item.net_id,
                ref=item.component,
                layer=layer,
                areas=self.areas.names(index, layer),
            )
            self._subjects[key] = found
        return found

    def _zone_clearance(self, a: int, b: int) -> Nm | None:
        """The own clearance of the zone of a fill, for a pair of one fill and one item that is not a fill;
        ``None`` for every other pair, two fills included (KiCad's DRC judges no pair of fills, and
        nothing measured says which zone's value its filler keeps between two fills)."""
        first, second = self.items.items[a], self.items.items[b]
        if (first.ref.kind == "fill") == (second.ref.kind == "fill"):
            return None
        return first.zone_clearance if first.ref.kind == "fill" else second.zone_clearance

    def _resolve(self, a: int, b: int, layer: str, *, zone: bool = True) -> Clearance:
        return self.resolver.resolve(
            self._subject(a, layer),
            self._subject(b, layer),
            zone_clearance=self._zone_clearance(a, b) if zone else None,
        )

    @staticmethod
    def _too_close(
        first: _Shape, second: _Shape, found: Clearance, base: Clearance | None
    ) -> Clearance | None:
        """The clearance the two shapes break, or ``None``.

        A value that comes from a zone is the distance KiCad's filler cuts to around the true copper. An
        arc is widened by twice its band so that no violation is missed, which would report every fill that
        follows an arc at exactly the zone's value: for such a pair the zone's value is judged against the
        arc narrowed by its band, and ``base``, the value in force without the zone, against the widened
        arc, so no finding of the rule without zones is lost."""
        assert found.value is not None
        if base is None or not (first.banded or second.banded):
            return found if thick_closer_than(first.wide, second.wide, found.value) else None
        if thick_closer_than(first.narrow, second.narrow, found.value):
            return found
        if (
            base.value
            and base.severity is not None
            and thick_closer_than(first.wide, second.wide, base.value)
        ):
            return base
        return None

    def _refs(self, a: int, b: int) -> tuple[CopperRef, CopperRef]:
        first, second = sorted(
            (self.items.items[a].ref, self.items.items[b].ref), key=lambda ref: (ref.kind, ref.where)
        )
        return first, second

    def pair(self, a: int, b: int, shapes: Sequence[tuple[int, _Shape, _Shape]]) -> CopperFinding | None:
        """The one finding of an item pair: a short on its first touching layer, else a clearance finding
        on the first layer where it is too close."""
        ordered = sorted(shapes, key=lambda entry: entry[0])
        refs = self._refs(a, b)
        for rank, first, second in ordered:
            self.judged += 1
            if thick_touch(first.narrow, second.narrow):
                layer = self.layers[rank]
                found = self._resolve(a, b, layer)
                at = thick_witness(first.narrow, second.narrow)
                note = "" if first.exact and second.exact else APPROXIMATED
                message = (
                    f"copper of {refs[0].net} and {refs[1].net} touches on {layer} at {_point(at)}{note}"
                )
                return CopperFinding(
                    "copper.short",
                    "error",
                    layer,
                    at,
                    refs,
                    0,
                    found.value,
                    found.source,
                    message,
                    self.resolver.explain(
                        self._subject(a, layer),
                        self._subject(b, layer),
                        zone_clearance=self._zone_clearance(a, b),
                    ),
                )
        unset = False
        for rank in dict.fromkeys(entry[0] for entry in ordered):
            layer = self.layers[rank]
            found = self._resolve(a, b, layer)
            unset = unset or found.unset
            if not found.value or found.severity is None:
                continue
            base = self._resolve(a, b, layer, zone=False) if found.source == ZONE_SOURCE else None
            closest: tuple[int, _Shape, _Shape, Clearance] | None = None
            for _, first, second in (entry for entry in ordered if entry[0] == rank):
                self.judged += 1
                broken = self._too_close(first, second, found, base)
                if broken is not None:
                    gap = thick_gap_floor(first.wide, second.wide)
                    if closest is None or gap < closest[0]:
                        closest = (gap, first, second, broken)
            if closest is not None:
                gap, first, second, found = closest
                assert found.value is not None and found.severity is not None
                at = thick_witness(first.wide, second.wide)
                message = (
                    f"copper of {refs[0].net} and {refs[1].net} is {_mm(gap)} mm apart on {layer} at "
                    f"{_point(at)}; the clearance is {_mm(found.value)} mm ({found.source})"
                )
                return CopperFinding(
                    "copper.clearance",
                    found.severity,
                    layer,
                    at,
                    refs,
                    gap,
                    found.value,
                    found.source,
                    message,
                    self.resolver.explain(
                        self._subject(a, layer),
                        self._subject(b, layer),
                        zone_clearance=None if found is base else self._zone_clearance(a, b),
                    ),
                )
        self.unset += unset
        return None


def _run(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    min_clearance: Nm | None,
    rules_over_classes: bool,
    floor_over_rules: bool,
    arc_tol: int,
    inputs: Sequence[Evidence],
    every_pair: bool = False,
) -> CopperReport:
    if type(arc_tol) is not int or arc_tol < 1:
        raise ValueError(f"arc_tol is an int of at least 1 nm, got {arc_tol!r}")
    board = design.board
    resolver = ClearanceResolver(
        design,
        min_clearance=min_clearance,
        rules_over_classes=rules_over_classes,
        floor_over_rules=floor_over_rules,
    )
    findings: list[CopperFinding] = []
    others: list[Issue] = []
    summary: dict[str, object] = {"arc_tol": arc_tol, "max_clearance": resolver.max_value}
    counts = {"pairs": 0, "judged": 0, "unset_pairs": 0, "approximated": 0, "net_tie_pairs": 0}
    layers: tuple[str, ...] = ()
    kinds: Counter[str] = Counter()
    unsupported: Counter[str] = Counter()
    rule_areas = 0
    if board is not None:
        items = _Items(design, pads, arc_tol)
        used = {layer for item in items.items for layer in item.shapes}
        layers = tuple(name for name in items.copper if name in used) + tuple(
            sorted(used - set(items.copper))
        )
        pairs, counts["pairs"] = _candidates(
            items, layers, (resolver.max_value + 1) // 2, every_pair=every_pair
        )
        areas = _Areas(board, items)
        rule_areas = areas.named
        judge = _Judge(items, layers, resolver, areas)
        for (a, b), shapes in sorted(pairs.items()):
            found = judge.pair(a, b, shapes)
            if found is not None:
                findings.append(found)
        findings += areas.findings(layers)
        findings += _zone_overlaps(board, items)
        counts.update(
            judged=judge.judged,
            unset_pairs=judge.unset,
            approximated=items.approximated,
            net_tie_pairs=_net_tie_pairs(items.items),
        )
        kinds, unsupported = items.kinds, items.unsupported
    for kind, count in sorted(unsupported.items()):
        if kind == "zone-outline":
            continue
        why = "no board frame was given" if kind == "pad" and pads is None else "they could not be shaped"
        others.append(
            issue(
                "copper.item-unsupported",
                f"{count} {kind} item(s) left out of the copper check: {why}",
                where=kind,
            )
        )
    if counts["unset_pairs"]:
        others.append(
            issue(
                "copper.clearance-unset",
                f"{counts['unset_pairs']} item pair(s) judged for shorts only: no clearance is in force "
                "for them",
            )
        )
    findings.sort(key=lambda f: (f.code, f.where, f.message))
    by_code = Counter(f.code for f in findings)
    summary.update(
        layers=list(layers),
        items=dict(sorted(kinds.items())),
        shorts=by_code["copper.short"],
        clearance=by_code["copper.clearance"],
        zone_overlaps=by_code["copper.zone-overlap"],
        keepouts=by_code["copper.keepout"],
        rule_areas=rule_areas,
        unsupported=dict(sorted(unsupported.items())),
        **counts,
    )
    issues = (*(f.to_issue() for f in findings), *sorted(others, key=_sort_key))
    with_areas = board is not None and bool(board.keepouts)
    evidence = Evidence.combine(EVIDENCE, *((AREA_EVIDENCE,) if with_areas else ()), *inputs)
    if any(i.code in LOWERING_CODES for i in issues):
        evidence = Evidence(Level.UNVERIFIED, hypotheses=evidence.hypotheses)
    return CopperReport(
        tuple(findings), tuple(sorted(issues, key=_sort_key)), dict(sorted(summary.items())), evidence
    )


LOWERING_CODES = frozenset({"copper.rules-incomplete", "copper.item-unsupported"})
"""Codes that lower a report or a stage to ``UNVERIFIED``: part of the copper or of the rules went
unjudged."""


def check_copper(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    min_clearance: Nm | None = None,
    rules_over_classes: bool = True,
    floor_over_rules: bool = False,
    arc_tol: int = ARC_TOL_NM,
    inputs: Sequence[Evidence] = (),
) -> CopperReport:
    """The shorts, clearance violations and zone overlaps of the copper of ``design.board``.

    ``pads`` are the board-frame pad records of ``BoardFrame.board_pads(design)``, or ``None`` when no
    frame is available (pads are then left out and reported). ``min_clearance``, ``rules_over_classes`` and
    ``floor_over_rules`` go to ``ClearanceResolver``; callers take them from ``DesignRules``. ``inputs`` are
    the evidence of what the caller read. Nothing is read, run or written.
    """
    return _run(
        design,
        pads=pads,
        min_clearance=min_clearance,
        rules_over_classes=rules_over_classes,
        floor_over_rules=floor_over_rules,
        arc_tol=arc_tol,
        inputs=inputs,
    )


STAGE = "copper.clearance"


def waived_issues(
    report: CopperReport, waivers: Sequence[Waiver]
) -> tuple[tuple[Issue, ...], dict[str, int]]:
    """The issues of ``report`` with every finding that a copper waiver of ``waivers`` accepts marked
    (``checks.waivers.apply_waivers``: severity ``info``, the waiver's name and reason), and the number of
    findings each waiver matched. The names of a finding are the ``where`` of its two items, and its gap is
    ``CopperFinding.gap``. The other issues of the report follow unchanged."""
    candidates = [
        Candidate(found.to_issue(), tuple(item.where for item in found.items), found.gap)
        for found in report.findings
        if found.code in COPPER_CODES  # a ``copper.keepout`` finding takes no waiver and follows unchanged
    ]
    marked, counts = apply_waivers(copper_waivers(waivers), candidates)
    others = tuple(found for found in report.issues if found.code not in COPPER_CODES)
    return (*marked, *others), counts


def rules_issues(rules: DesignRules | None) -> list[Issue]:
    """The ``copper.rules-incomplete`` warnings of a rules source's answer (``None``: no source), and one
    ``copper.item-unsupported`` per kind of copper it left out."""
    if rules is None:
        return [
            issue(
                "copper.rules-incomplete",
                "no rules source was given: the board is judged with the rules of its own model only",
            )
        ]
    found: list[Issue] = []
    if rules.opaque_clearance_rules:
        found.append(
            issue(
                "copper.rules-incomplete",
                f"{rules.opaque_clearance_rules} clearance rule(s) outside the closed grammar were not "
                "applied",
            )
        )
    for name, message in rules.unread:
        found.append(issue("copper.rules-incomplete", f"{name} was not read: {message}", where=name))
    for kind, count, reason in rules.left_out:
        found.append(
            issue(
                "copper.item-unsupported",
                f"{count} {kind} item(s) left out of the copper check: {reason}",
                where=kind,
            )
        )
    return found


def rules_summary(rules: DesignRules | None) -> dict[str, object]:
    """``{min_clearance, opaque_clearance_rules, unread}`` of a rules source's answer."""
    if rules is None:
        return {"min_clearance": None, "opaque_clearance_rules": 0, "unread": []}
    return {
        "min_clearance": rules.min_clearance,
        "opaque_clearance_rules": rules.opaque_clearance_rules,
        "unread": [name for name, _ in rules.unread],
    }


def copper_stage(
    design: Design | None,
    *,
    project: ProjectSet,
    rules_source: DesignRulesSource | None,
    frame: BoardFrame | None,
    evidence: Evidence,
    waivers: Sequence[Waiver] = (),
) -> StageResult:
    """The ``copper.clearance`` stage: ``check_copper`` on the board model that ``run_checks`` read
    (``design``; ``None`` when that read was refused), with the rules of the project's own files from
    ``rules_source`` and the pads of ``frame``. ``evidence`` is the evidence of the board read. No tool
    runs, and nothing is written.

    ``waivers`` are the design's waivers (change c0114): a finding that a ``copper.*`` waiver accepts is
    kept as ``info``, a copper waiver that matched nothing gives ``check.waiver-unmatched``, and
    ``summary.waivers`` says which matched. Waivers change no evidence."""
    if design is None:
        return skipped(STAGE, "read-refused")
    rules = rules_source.design_rules(design, project) if rules_source is not None else None
    checked = rules.design if rules is not None else design
    pads = frame.board_pads(checked) if frame is not None else None
    inputs = [evidence] if rules is None else [evidence, rules.evidence]
    report = check_copper(
        checked,
        pads=pads,
        min_clearance=rules.min_clearance if rules is not None else None,
        rules_over_classes=rules.rules_over_classes if rules is not None else True,
        floor_over_rules=rules.floor_over_rules if rules is not None else False,
        inputs=inputs,
    )
    summary: dict[str, object] = {**report.summary, "rules": rules_summary(rules)}
    own = copper_waivers(waivers)
    found, counts = waived_issues(report, own)
    issues = [*found, *rules_issues(rules)]
    if own:
        outcome, stale = judge_waivers(own, counts)
        issues += stale
        summary["waivers"] = {key: value for key, value in outcome.to_json().items() if key != "declared"}
    level = report.evidence
    if any(found.code in LOWERING_CODES for found in issues):
        level = Evidence(Level.UNVERIFIED, hypotheses=level.hypotheses)
    return ran(STAGE, issues, level, summary)


__all__ = [
    "ARC_TOL_NM",
    "AREA_EVIDENCE",
    "EVIDENCE",
    "LOWERING_CODES",
    "STAGE",
    "CopperFinding",
    "CopperKind",
    "CopperRef",
    "CopperReport",
    "CopperReviewGroup",
    "group_findings",
    "check_copper",
    "copper_layers",
    "copper_stage",
    "rules_issues",
    "rules_summary",
    "waived_issues",
]
