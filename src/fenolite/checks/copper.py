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
from fenolite.checks.clearance import Clearance, ClearanceResolver, CopperKind
from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran, skipped
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
from fenolite.model.board import Board, Zone
from fenolite.model.design import Design
from fenolite.model.rules import RuleSubject

ARC_TOL_NM = 1_000
"""The chord error of a polygonised arc; its band is ``ARC_TOL_NM + 1`` nm."""
EVIDENCE = Evidence(
    Level.INFERRED, hypotheses=("H-K-COPPER-SHAPES", "H-K-COPPER-RESOLVE", "H-K-COPPER-ZONES")
)
"""``INFERRED`` also once the three rows are settled: the canaries cover pair kinds and clearance sources
on benches, and fills on 10.0 only, not every board."""
NO_NET = "<no net>"
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


# --- copper items ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Shape:
    """A thick shape of an item on a layer. ``narrow`` is the shape a short is judged with and ``wide``
    the one a clearance is judged with; they differ only for an arc, by its band."""

    item: int
    narrow: Thick
    wide: Thick
    exact: bool = True


@dataclass(slots=True)
class _Item:
    ref: CopperRef
    net_id: str | None
    component: str | None = None
    shapes: dict[str, list[_Shape]] = field(default_factory=lambda: {})


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
        return CopperRef(kind, _where(entity), entity.id, self.net_name(net_id))

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
            ref = CopperRef("pad", where, record.pad_id, self.net_name(record.net_id))
            item = _Item(ref, record.net_id, record.ref or None)
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
                    CopperRef("fill", _where(zone), zone.id, self.net_name(zone.net_id)), zone.net_id
                )
                self._add(item, shapes)
                self.kinds["fill"] += len(shapes) - 1  # fills are counted, not zones


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
                (CopperRef("zone", _where(z), z.id, items.net_name(z.net_id)) for z in (first, second)),
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
    """Two items are judged when their nets differ; two items without a net are not."""
    return a.net_id != b.net_id


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
    def __init__(self, items: _Items, layers: Sequence[str], resolver: ClearanceResolver) -> None:
        self.items = items
        self.layers = layers
        self.resolver = resolver
        self.judged = 0
        self.unset = 0
        self._subjects: dict[tuple[int, str], RuleSubject] = {}

    def _subject(self, index: int, layer: str) -> RuleSubject:
        key = (index, layer)
        found = self._subjects.get(key)
        if found is None:
            item = self.items.items[index]
            found = self.resolver.subject(item.ref.kind, item.net_id, ref=item.component, layer=layer)
            self._subjects[key] = found
        return found

    def _resolve(self, a: int, b: int, layer: str) -> Clearance:
        return self.resolver.resolve(self._subject(a, layer), self._subject(b, layer))

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
                    "copper.short", "error", layer, at, refs, 0, found.value, found.source, message
                )
        unset = False
        for rank in dict.fromkeys(entry[0] for entry in ordered):
            layer = self.layers[rank]
            found = self._resolve(a, b, layer)
            unset = unset or found.unset
            if not found.value or found.severity is None:
                continue
            closest: tuple[int, _Shape, _Shape] | None = None
            for _, first, second in (entry for entry in ordered if entry[0] == rank):
                self.judged += 1
                if thick_closer_than(first.wide, second.wide, found.value):
                    gap = thick_gap_floor(first.wide, second.wide)
                    if closest is None or gap < closest[0]:
                        closest = (gap, first, second)
            if closest is not None:
                gap, first, second = closest
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
    counts = {"pairs": 0, "judged": 0, "unset_pairs": 0, "approximated": 0}
    layers: tuple[str, ...] = ()
    kinds: Counter[str] = Counter()
    unsupported: Counter[str] = Counter()
    if board is not None:
        items = _Items(design, pads, arc_tol)
        used = {layer for item in items.items for layer in item.shapes}
        layers = tuple(name for name in items.copper if name in used) + tuple(
            sorted(used - set(items.copper))
        )
        pairs, counts["pairs"] = _candidates(
            items, layers, (resolver.max_value + 1) // 2, every_pair=every_pair
        )
        judge = _Judge(items, layers, resolver)
        for (a, b), shapes in sorted(pairs.items()):
            found = judge.pair(a, b, shapes)
            if found is not None:
                findings.append(found)
        findings += _zone_overlaps(board, items)
        counts.update(judged=judge.judged, unset_pairs=judge.unset, approximated=items.approximated)
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
        unsupported=dict(sorted(unsupported.items())),
        **counts,
    )
    issues = (*(f.to_issue() for f in findings), *sorted(others, key=_sort_key))
    evidence = Evidence.combine(EVIDENCE, *inputs)
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


def rules_issues(rules: DesignRules | None) -> list[Issue]:
    """The ``copper.rules-incomplete`` warnings of a rules source's answer (``None``: no source)."""
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
) -> StageResult:
    """The ``copper.clearance`` stage: ``check_copper`` on the board model that ``run_checks`` read
    (``design``; ``None`` when that read was refused), with the rules of the project's own files from
    ``rules_source`` and the pads of ``frame``. ``evidence`` is the evidence of the board read. No tool
    runs, and nothing is written."""
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
    issues = [*report.issues, *rules_issues(rules)]
    level = report.evidence
    if any(found.code in LOWERING_CODES for found in issues):
        level = Evidence(Level.UNVERIFIED, hypotheses=level.hypotheses)
    return ran(STAGE, issues, level, {**report.summary, "rules": rules_summary(rules)})


__all__ = [
    "ARC_TOL_NM",
    "EVIDENCE",
    "LOWERING_CODES",
    "STAGE",
    "CopperFinding",
    "CopperKind",
    "CopperRef",
    "CopperReport",
    "check_copper",
    "copper_layers",
    "copper_stage",
    "rules_issues",
    "rules_summary",
]
