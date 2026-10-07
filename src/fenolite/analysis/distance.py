# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Clearance and creepage between pairs of nets (capability board-analyses, "Clearance on a layer",
"Creepage on the board surface" and "Clearance across the board edge"; ``docs/analyses.md``).

Per pair and copper layer, the gap is the smallest exact gap between a shape of one net and a shape of the
other (``geometry.thick``). The clearance is the distance through air: the smallest gap on the two outer
layers, or the interval across the board edge for copper on opposite faces. Gaps on inner layers are
distances inside the laminate and are reported apart. The creepage is the shortest path along the
surface (``analysis.surface``). Every value is an interval with its location; a finding exists only
against a requirement of the user.
"""

from __future__ import annotations

import heapq
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace

from fenolite.analysis import grooves as groove_module
from fenolite.analysis import insulation as insulation_module
from fenolite.analysis.boundary import BoardBoundary
from fenolite.analysis.codes import issue
from fenolite.analysis.copper import ARC_TOL_NM, CopperShape, NetCopper, loose_copper, net_copper
from fenolite.analysis.grooves import GrooveResult, bridge_grooves, passes_groove
from fenolite.analysis.insulation import insulation_between, layer_depths, plan_gap
from fenolite.analysis.network import graphic_issue
from fenolite.analysis.report import (
    AnalysisReport,
    DistanceRow,
    Measure,
    judge,
    mm,
    point_text,
    report_evidence,
    sorted_issues,
)
from fenolite.analysis.requirements import Requirements
from fenolite.analysis.surface import (
    BRIDGE_EVIDENCE,
    Face,
    SurfacePath,
    Terminal,
    boundary_distance,
    conductor_chain,
    surface_distance,
    usable_terminals,
)
from fenolite.backends.base import BoardPad
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm
from fenolite.geometry import BBox, SpatialIndex, thick_bbox, thick_gap_floor, thick_touch
from fenolite.model.circuit import Net
from fenolite.model.design import Design

Pair = tuple[str, str]


_layer_gap = plan_gap


def _by_layer(shapes: Sequence[CopperShape]) -> dict[str, list[CopperShape]]:
    found: dict[str, list[CopperShape]] = {}
    for shape in shapes:
        found.setdefault(shape.layer, []).append(shape)
    return found


def _close_pairs(copper: NetCopper, within: Nm) -> set[Pair]:
    """Every pair of nets with a gap on a layer below ``within``, found with one index per layer."""
    pairs: set[Pair] = set()
    entries: dict[str, list[tuple[str, CopperShape]]] = {}
    for name, shapes in copper.by_net.items():
        for shape in shapes:
            entries.setdefault(shape.layer, []).append((name, shape))
    for items in entries.values():
        boxes = [thick_bbox(shape.shape) for _, shape in items]
        index = SpatialIndex[int].build((box, i) for i, box in enumerate(boxes))
        for i, (name, shape) in enumerate(items):
            box = boxes[i]
            reach = within + shape.band
            grown = BBox(box.x0 - reach, box.y0 - reach, box.x1 + reach, box.y1 + reach)
            for j in index.query(grown):
                other_name, other = items[j]
                if j <= i or other_name == name:
                    continue
                pair = (name, other_name) if name < other_name else (other_name, name)
                if pair in pairs:
                    continue
                touching = thick_touch(shape.shape, other.shape)
                gap = 0 if touching else thick_gap_floor(shape.shape, other.shape)
                if max(0, gap - shape.band - other.band) < within:
                    pairs.add(pair)
    return pairs


def _close_through(copper: NetCopper, depths: insulation_module.Depths, within: Nm) -> set[Pair]:
    """Every pair of nets with copper on two layers whose distance through the laminate is below
    ``within``: per two layers closer than ``within``, one index over the shapes of the lower one."""
    pairs: set[Pair] = set()
    entries: dict[str, list[tuple[str, CopperShape]]] = {}
    for name, shapes in copper.by_net.items():
        for shape in shapes:
            if shape.layer in depths:
                entries.setdefault(shape.layer, []).append((name, shape))
    order = sorted(entries, key=lambda layer: depths[layer])
    for i, upper in enumerate(order):
        for lower in order[i + 1 :]:
            height = depths[lower][0] - depths[upper][1]
            if height < 0 or height >= within:
                continue
            items = entries[lower]
            boxes = [thick_bbox(shape.shape) for _, shape in items]
            index = SpatialIndex[int].build((box, k) for k, box in enumerate(boxes))
            for name, shape in entries[upper]:
                box = thick_bbox(shape.shape)
                reach = within + shape.band
                grown = BBox(box.x0 - reach, box.y0 - reach, box.x1 + reach, box.y1 + reach)
                for k in index.query(grown):
                    other_name, other = items[k]
                    pair = (name, other_name) if name < other_name else (other_name, name)
                    if other_name == name or pair in pairs:
                        continue
                    touching = thick_touch(shape.shape, other.shape)
                    gap = 0 if touching else thick_gap_floor(shape.shape, other.shape)
                    gap = max(0, gap - shape.band - other.band)
                    if gap * gap + height * height < within * within:
                        pairs.add(pair)
    return pairs


def _terminals(shapes: Sequence[CopperShape], outer: tuple[str, str]) -> list[tuple[Terminal, CopperShape]]:
    found: list[tuple[Terminal, CopperShape]] = []
    for shape in shapes:
        faces: list[Face] = []
        if shape.layer == outer[0]:
            faces.append("top")
        if shape.layer == outer[1] and (outer[1] != outer[0] or not faces):
            faces.append("bottom")
        for face in faces:
            found.append((Terminal(shape.shape, face, shape.band), shape))
    return found


def _path_measure(
    path: SurfacePath,
    first: Sequence[tuple[Terminal, CopperShape]],
    second: Sequence[tuple[Terminal, CopperShape]],
    outer: tuple[str, str],
) -> Measure:
    faces = list(dict.fromkeys(face for _, face in path.points))
    names = {"top": outer[0], "bottom": outer[1]}
    layer = "/".join(names[face] for face in faces)
    items = (first[path.ends[0]][1].where, second[path.ends[1]][1].where)
    return Measure(
        max(0, path.length - path.band),
        path.length + path.band + 2,
        layer,
        tuple(point for point, _ in path.points),
        items,
    )


_Conductor = tuple[Terminal, CopperShape, str | None, int]  # terminal, shape, net, id of the conductor


def _conductors(
    copper: NetCopper, loose: Sequence[CopperShape], boundary: BoardBoundary | None
) -> list[_Conductor]:
    """Every shape on the two outer copper layers as a conductor that a path may cross, with its net
    (``None`` for copper without one); the shapes of one item are one conductor."""
    outer = copper.outer
    if outer is None:
        return []
    ids: dict[str, int] = {}
    found: list[_Conductor] = []
    groups: list[tuple[str | None, Sequence[CopperShape]]] = [*copper.by_net.items(), (None, loose)]
    for net, shapes in groups:
        for terminal, shape in _terminals(shapes, outer):
            found.append((terminal, shape, net, ids.setdefault(shape.entity_id, len(ids))))
    kept, _ = usable_terminals([entry[0] for entry in found], boundary)
    usable = {id(terminal) for terminal in kept}
    return [entry for entry in found if id(entry[0]) in usable]


NEAR_CONDUCTORS = 500
"""The number of conductors within the reach of one net of a pair above which the conductors of that pair
are not searched: the two nets then lie far apart on a dense board, the pair is counted in one
``analysis.item-unsupported`` warning naming ``conductors``, and its values are those without conductors,
upper bounds of the values over them."""


class _Field:
    """The conductors of the board with one index over their boxes, built once for all pairs. For a pair
    it gives the conductors that a path shorter than a reach can use: those that a chain of boxes, each
    within the reach of the one before, joins to both nets. A box is never farther than its copper, so
    no conductor that can help is left out."""

    def __init__(self, conductors: Sequence[_Conductor]) -> None:
        self.by_id: dict[int, list[_Conductor]] = {}
        for entry in conductors:
            self.by_id.setdefault(entry[3], []).append(entry)
        self.boxes: dict[int, BBox] = {}
        for key, entries in self.by_id.items():
            found = [thick_bbox(entry[0].shape) for entry in entries]
            self.boxes[key] = BBox(
                min(box.x0 for box in found), min(box.y0 for box in found),
                max(box.x1 for box in found), max(box.y1 for box in found),
            )  # fmt: skip
        self.index = SpatialIndex[int].build((box, key) for key, box in self.boxes.items())
        self.through = [
            entries[0][2] for entries in self.by_id.values() if len({entry[0].face for entry in entries}) == 2
        ]

    def joins_faces(self, skip: Pair) -> bool:
        """Whether a conductor of another net, or of none, has copper on both outer layers."""
        return any(net not in skip for net in self.through)

    def near(
        self,
        term_a: Sequence[tuple[Terminal, CopperShape]],
        term_b: Sequence[tuple[Terminal, CopperShape]],
        reach: Nm | None,
        skip: Pair,
    ) -> tuple[list[_Conductor], bool]:
        """The conductors that can help, and whether all of them were found: with more than
        ``NEAR_CONDUCTORS`` within the reach of one net the search is given up, and none is returned."""

        def closure(terminals: Sequence[tuple[Terminal, CopperShape]]) -> set[int] | None:
            seen: set[int] = set()
            queue = [thick_bbox(terminal.shape) for terminal, _ in terminals]
            if reach is None:
                seen = {key for key, entries in self.by_id.items() if entries[0][2] not in skip}
                return seen if len(seen) <= NEAR_CONDUCTORS else None
            while queue:
                box = queue.pop()
                grown = BBox(box.x0 - reach, box.y0 - reach, box.x1 + reach, box.y1 + reach)
                for key in self.index.query(grown):
                    if key not in seen and self.by_id[key][0][2] not in skip:
                        seen.add(key)
                        queue.append(self.boxes[key])
                if len(seen) > NEAR_CONDUCTORS:
                    return None
            return seen

        first = closure(term_a)
        second = closure(term_b) if first is not None else None
        if first is None or second is None:
            return [], False
        return [entry for key in sorted(first & second) for entry in self.by_id[key]], True


def _air_chain(
    term_a: Sequence[tuple[Terminal, CopperShape]],
    term_b: Sequence[tuple[Terminal, CopperShape]],
    others: Sequence[_Conductor],
    outer: tuple[str, str],
    below: Nm | None,
) -> tuple[Measure | None, tuple[str | None, ...], bool]:
    """The shortest chain through air from one net to the other over at least one conductor: links of
    gaps on one face, a conductor crossed at no length and from one face to the other when it has copper
    on both. Only a chain whose low end is below ``below`` is returned, with the nets of its conductors."""
    if not term_a or not term_b or not others:
        return None, (), True
    by_id: dict[int, list[_Conductor]] = {}
    for entry in others:
        by_id.setdefault(entry[3], []).append(entry)
    order = sorted(by_id)
    stations = [[entry[0] for entry in by_id[key]] for key in order]
    set_a, set_b = [t for t, _ in term_a], [t for t, _ in term_b]
    from_a, _, complete = conductor_chain(set_a, set_b, stations, limit=below)
    if not from_a:
        return None, (), complete
    names = {"top": outer[0], "bottom": outer[1]}

    def shapes_of(node: int) -> Sequence[tuple[Terminal, CopperShape]]:
        if node == -1:
            return term_a
        if node == -2:
            return term_b
        return [(entry[0], entry[1]) for entry in by_id[order[node]]]

    def link(first: int, second: int) -> Measure | None:
        best: Measure | None = None
        for face in ("top", "bottom"):
            one = [shape for terminal, shape in shapes_of(first) if terminal.face == face]
            two = [shape for terminal, shape in shapes_of(second) if terminal.face == face]
            found = plan_gap(one, two, names[face]) if one and two else None
            if found is not None and (best is None or found.low < best.low):
                best = found
        return best

    dist: dict[int, int] = {-1: 0}
    before: dict[int, tuple[int, Measure]] = {}
    done: set[int] = set()
    heap: list[tuple[int, int]] = [(0, -1)]
    while heap:
        here, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        if node == -2:
            break
        targets = sorted(k for k in from_a if k not in done)
        for other in targets if node == -1 else [-2, *targets]:
            found = link(node, other)
            if found is None or (below is not None and here + found.low >= below):
                continue
            total = here + found.low
            if other not in dist or total < dist[other]:
                dist[other] = total
                before[other] = (node, found)
                heapq.heappush(heap, (total, other))
    if -2 not in dist:
        return None, (), complete
    links: list[Measure] = []
    crossed: list[int] = []
    node = -2
    while node != -1:
        node, found = before[node]
        links.append(found)
        if node >= 0:
            crossed.append(node)
    links.reverse()
    crossed.reverse()
    highs = [found.high for found in links]
    high = None if any(value is None for value in highs) else sum(value or 0 for value in highs)
    layer = "/".join(dict.fromkeys(found.layer for found in links))
    over = tuple(by_id[order[k]][0][1].where for k in crossed)
    measure = Measure(
        dist[-2],
        high,
        layer,
        tuple(point for found in links for point in found.points),
        (links[0].items[0], links[-1].items[1]),
        False,
        over,
    )
    return measure, tuple(by_id[order[k]][0][2] for k in crossed), complete


def _judge(
    measure: Measure | None,
    required: Nm | None,
    code: str,
    undecided: str,
    what: str,
    pair: Pair,
) -> Issue | None:
    if measure is None or required is None:
        return None
    verdict = judge(measure, required)
    if verdict is None:
        return None
    where = ", ".join(measure.items)
    at = f" at {point_text(measure.points[0])}" if measure.points else ""
    if measure.high is None:
        value = f"at least {mm(measure.low)} mm (the search stopped at its limit)"
    elif measure.high - measure.low <= 2:
        value = f"{mm(measure.low)} mm"
    else:
        value = f"between {mm(measure.low)} mm and {mm(measure.high)} mm"
    text = (
        f"{what} between {pair[0]} and {pair[1]} is {value} on {measure.layer}{at}; "
        f"{mm(required)} mm is required"
    )
    if verdict == "error":
        return issue(code, text, where=where)
    return issue(undecided, text + "; the measure does not decide", where=where)


def analyze_distances(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    boundary: BoardBoundary | None,
    pairs: Sequence[Pair] = (),
    within: Nm | None = None,
    requirements: Requirements | None = None,
    arc_tol: int = ARC_TOL_NM,
    groove: Nm | None = None,
    insulation: bool = False,
) -> AnalysisReport:
    """One row per selected pair of nets: the gaps per layer, the clearance through air and the creepage
    along the surface, with the findings against the user's distance rows. ``groove`` is the width below
    which a groove is bridged on the creepage path; with ``insulation`` each row also holds the distance
    through the laminate between two layers."""
    copper = net_copper(design, pads=pads, arc_tol=arc_tol)
    field = _Field(_conductors(copper, loose_copper(design, pads=pads, arc_tol=arc_tol), boundary))
    depths = layer_depths(design.board) if insulation and design.board is not None else None
    circuit = design.circuit
    nets: dict[str, Net] = {net.name: net for net in circuit.nets}
    issues: list[Issue] = []
    for kind, count in copper.unsupported.items():
        issues.append(
            issue(
                "analysis.item-unsupported",
                f"{count} {kind}(s) could not be shaped and are left out of the distance analysis"
                + ("; the backend gives no board-frame pads" if kind == "pad" and pads is None else ""),
                where=kind,
            )
        )

    graphics = graphic_issue(design, "the conductors of the distance analysis")
    if graphics is not None:
        issues.append(graphics)

    selected: set[Pair] = set()
    for a, b in pairs:
        if a != b:
            selected.add((a, b) if a < b else (b, a))
    if requirements is not None:
        names = sorted(nets)
        for index, row in enumerate(requirements.distances):
            matched = False
            for i, a in enumerate(names):
                for b in names[i + 1 :]:
                    if row.matches(nets[a], nets[b], circuit):
                        selected.add((a, b))
                        matched = True
            if not matched:
                issues.append(
                    issue(
                        "analysis.requirement-unmatched",
                        f"distance row {index} ({row.text()}) matches no pair of nets of the design",
                        where=f"distance[{index}]",
                    )
                )
            elif requirements.values(row) is None:
                issues.append(
                    issue(
                        "analysis.requirement-unmatched",
                        f"distance row {index}: {row.millivolts} mV is above every step of the table, so "
                        "the row gives no requirement",
                        where=f"distance[{index}]",
                    )
                )
    if within is not None:
        selected |= _close_pairs(copper, within)
        if depths:
            selected |= _close_through(copper, depths, within)
    if not pairs and within is None and (requirements is None or not requirements.distances):
        issues.append(
            issue(
                "analysis.input-missing",
                "pair selection not given: name pairs, give a distance row or a search distance",
                where="pair selection",
            )
        )

    usable = boundary is not None and boundary.source != "none"
    named_pairs = {(a, b) if a < b else (b, a) for a, b in pairs}
    outer = copper.outer
    rows: list[DistanceRow] = []
    missing: Counter[str] = Counter()
    outside = 0
    faces_alone = 0
    bridged: dict[Nm, GrooveResult] = {}
    no_width = 0
    partly = 0
    no_stackup = 0
    measured_through = False
    for name_a, name_b in sorted(selected):
        shapes_a, shapes_b = copper.by_net.get(name_a, ()), copper.by_net.get(name_b, ())
        layers_a, layers_b = _by_layer(shapes_a), _by_layer(shapes_b)
        order = copper.layers or tuple(sorted(set(layers_a) | set(layers_b)))
        gaps: list[Measure] = []
        for layer in order:
            if layer in layers_a and layer in layers_b:
                found = _layer_gap(layers_a[layer], layers_b[layer], layer)
                if found is not None:
                    gaps.append(found)
        net_a, net_b = nets.get(name_a), nets.get(name_b)
        wanted: tuple[Nm | None, Nm | None, Nm | None] = (None, None, None)
        if requirements is not None and net_a is not None and net_b is not None:
            wanted = requirements.distance_for(net_a, net_b, circuit)
        clearance: Measure | None = None
        creepage: Measure | None = None
        third: set[str] = set()
        whole_search = True
        if outer is not None:
            through_air = [gap for gap in gaps if gap.layer in outer]
            term_a, term_b = _terminals(shapes_a, outer), _terminals(shapes_b, outer)
            kept_a, lost_a = usable_terminals([t for t, _ in term_a], boundary)
            kept_b, lost_b = usable_terminals([t for t, _ in term_b], boundary)
            outside += lost_a + lost_b
            term_a = [entry for entry in term_a if entry[0] in kept_a]
            term_b = [entry for entry in term_b if entry[0] in kept_b]
            faces_a = {t.face for t, _ in term_a}
            faces_b = {t.face for t, _ in term_b}
            same = bool(faces_a & faces_b)
            opposite = ("top" in faces_a and "bottom" in faces_b) or (
                "bottom" in faces_a and "top" in faces_b
            )
            around = usable and boundary is not None and boundary.thickness is not None
            named = (name_a, name_b) in named_pairs
            joins_faces = field.joins_faces((name_a, name_b))
            if opposite and not around and same:
                # with a common face the pair is still measured there; the count goes to the summary
                faces_alone += 1
            required = [value for value in wanted[:2] if value is not None]
            limit = max(required) if required else (None if named else within)
            widths = [groove] if groove else []
            if requirements is not None and net_a is not None and net_b is not None:
                own = requirements.groove_for(net_a, net_b, circuit)
                widths += [own] if own else []
            surface = boundary
            if widths and usable and boundary is not None:
                if max(widths) not in bridged:
                    bridged[max(widths)] = bridge_grooves(boundary, max(widths))
                surface = bridged[max(widths)].boundary
            if term_a and term_b and (same or around or joins_faces):
                # first without conductors: that path bounds the conductors that can shorten it
                set_a, set_b = [t for t, _ in term_a], [t for t, _ in term_b]
                path = surface_distance(set_a, set_b, surface, limit=limit) if same or around else None
                reach = limit if path is None else path.length + path.band + 2
                others, found_all = field.near(term_a, term_b, reach, (name_a, name_b))
                whole_search = found_all
                if others:
                    path = surface_distance(
                        set_a,
                        set_b,
                        surface,
                        limit=limit,
                        bridges=[entry[0] for entry in others],
                        conductors=[entry[3] for entry in others],
                    )
                if path is not None:
                    whole_search = whole_search and path.complete
                    creepage = _path_measure(path, term_a, term_b, outer)
                    crossed = list(dict.fromkeys(path.over))
                    creepage = replace(creepage, over=tuple(others[k][1].where for k in crossed))
                    third.update(others[k][2] or "" for k in crossed)
                    if not widths and wanted[1] is not None and usable and boundary is not None:
                        no_width += passes_groove(creepage.points, boundary)
                elif limit is not None:
                    items = (term_a[0][1].where, term_b[0][1].where)
                    creepage = Measure(limit, None, "/".join(dict.fromkeys(outer)), (), items, True)
            if opposite and around and boundary is not None and boundary.thickness is not None:
                across = _across(term_a, term_b, boundary, outer, creepage, same, limit)
                if across is not None:
                    through_air.append(across)
            if through_air:
                clearance = min(through_air, key=lambda m: (m.low, m.high is None, m.high or 0, m.layer))
            below = None if clearance is None else clearance.low
            beside, found_all = (
                field.near(term_a, term_b, below, (name_a, name_b)) if term_a and term_b else ([], True)
            )
            chain, nets_crossed, searched = _air_chain(term_a, term_b, beside, outer, below)
            searched = searched and found_all
            partly += not (searched and whole_search)
            if chain is not None:
                clearance = chain
                third.update(net or "" for net in nets_crossed)
            if opposite and not around and not same and creepage is None and clearance is None:
                missing["board outline" if not usable else "board thickness"] += 1
        third.discard("")
        if third:
            nets_text = ", ".join(sorted(third))
            select = "; ".join(f"{name} and {other}" for other in sorted(third) for name in (name_a, name_b))
            issues.append(
                issue(
                    "analysis.creepage-over",
                    f"the clearance or the creepage between {name_a} and {name_b} crosses copper of "
                    f"{nets_text} at no length; the distances from each net of the pair to that copper are "
                    "the ones its voltage acts across",
                    where=f"{name_a}, {name_b}",
                    hint=f"select the pairs {select}",
                )
            )
        through: Measure | None = None
        sheets: int | None = None
        needed: Nm | None = None
        if insulation:
            if requirements is not None and net_a is not None and net_b is not None:
                needed = requirements.insulation_for(net_a, net_b, circuit)
            crossed = {(a, b) for a in layers_a for b in layers_b if a != b}
            known = depths or {}
            if crossed and (depths is None or any(a not in known or b not in known for a, b in crossed)):
                no_stackup += 1
            elif crossed and design.board is not None:
                through, sheets = insulation_between(
                    shapes_a, shapes_b, depths=known, stackup=design.board.stackup
                )
                measured_through = measured_through or through is not None
        rows.append(DistanceRow(name_a, name_b, tuple(gaps), clearance, creepage, through, sheets))
        pair = (name_a, name_b)
        found_issues = [
            _judge(clearance, wanted[0], "analysis.clearance-below", "analysis.clearance-undecided",
                   "clearance", pair),
            _judge(creepage, wanted[1], "analysis.creepage-below", "analysis.creepage-undecided",
                   "creepage", pair),
            _judge(through, needed, "analysis.insulation-below", "analysis.insulation-undecided",
                   "insulation through the laminate", pair),
        ]  # fmt: skip
        if outer is not None:
            for gap in gaps:
                if gap.layer not in outer:
                    found_issues.append(
                        _judge(gap, wanted[2], "analysis.embedded-below", "analysis.clearance-undecided",
                               "gap inside the laminate", pair)
                    )  # fmt: skip
        issues += [found for found in found_issues if found is not None]

    for name, count in sorted(missing.items()):
        issues.append(
            issue(
                "analysis.input-missing",
                f"{name} not given: {count} pair(s) with copper only on opposite faces cannot be joined "
                "around the board edge and have no clearance and no creepage",
                where=name,
                hint="Fenolite assumes no value; give --board-thickness, or draw a closed outline",
            )
        )
    if outside:
        issues.append(
            issue(
                "analysis.item-unsupported",
                f"{outside} conductor(s) lie outside the board outline or inside a cut-out and are left "
                "out of the surface search",
                where="outside the board",
            )
        )
    if partly:
        issues.append(
            issue(
                "analysis.item-unsupported",
                f"the conductors of {partly} pair(s) were not all searched: the two nets lie far apart among "
                "many conductors, and the search stopped at its budget; their clearance and creepage are "
                "upper bounds of the values over conductors",
                where="conductors",
                hint="such a pair is seldom the one a distance requirement is about; name closer pairs",
            )
        )
    if no_width:
        issues.append(
            issue(
                "analysis.input-missing",
                f"groove width not given: the creepage path of {no_width} pair(s) with a creepage "
                "requirement bends at a cut-out or a notch or crosses its wall, and every groove counts "
                "whatever its width",
                where="groove width",
                hint="give --groove-width, or groove_nm in the distance row, if narrow grooves do not count",
            )
        )
    if no_stackup:
        issues.append(
            issue(
                "analysis.input-missing",
                f"stack-up not given: {no_stackup} pair(s) with copper on two layers have no distance "
                "through the laminate, because the board holds no depth for those layers",
                where="stack-up",
                hint="Fenolite assumes no thickness; the depths come from the stack-up of the board",
            )
        )
    ordered = sorted_issues(issues)
    summary: dict[str, object] = {
        "pairs": len(rows),
        "unsupported": dict(copper.unsupported),
        "boundary": boundary.source if boundary is not None else "none",
        "faces_alone": faces_alone,
    }
    used: list[Evidence] = [BRIDGE_EVIDENCE]
    if bridged:
        summary["grooves"] = {
            str(width): {"bridged": found.bridged, "counted": found.counted}
            for width, found in sorted(bridged.items())
        }
        used.append(groove_module.EVIDENCE)
    if measured_through:
        used.append(insulation_module.EVIDENCE)
    return AnalysisReport(tuple(rows), ordered, summary, report_evidence(ordered, *used))


def _across(
    term_a: Sequence[tuple[Terminal, CopperShape]],
    term_b: Sequence[tuple[Terminal, CopperShape]],
    boundary: BoardBoundary,
    outer: tuple[str, str],
    creepage: Measure | None,
    same: bool,
    limit: Nm | None,
) -> Measure | None:
    """The clearance across the board edge for copper on opposite faces: at least the two distances to
    the boundary plus the thickness, at most the surface path between the opposite faces."""
    assert boundary.thickness is not None
    lows: list[tuple[int, CopperShape, CopperShape]] = []
    for face_a, face_b in (("top", "bottom"), ("bottom", "top")):
        near_a = [(boundary_distance(t.shape, boundary), s) for t, s in term_a if t.face == face_a]
        near_b = [(boundary_distance(t.shape, boundary), s) for t, s in term_b if t.face == face_b]
        if near_a and near_b:
            d_a, d_b = min(near_a, key=lambda item: item[0]), min(near_b, key=lambda item: item[0])
            lows.append((d_a[0] + d_b[0] + boundary.thickness, d_a[1], d_b[1]))
    if not lows:
        return None
    low, item_a, item_b = min(lows, key=lambda item: item[0])
    layer = f"{outer[0]}/{outer[1]}"
    if not same and creepage is not None:
        upper = creepage
    else:
        paths: list[Measure] = []
        for face_a, face_b in (("top", "bottom"), ("bottom", "top")):
            only_a = [entry for entry in term_a if entry[0].face == face_a]
            only_b = [entry for entry in term_b if entry[0].face == face_b]
            if only_a and only_b:
                path = surface_distance([t for t, _ in only_a], [t for t, _ in only_b], boundary, limit=limit)
                if path is not None:
                    paths.append(_path_measure(path, only_a, only_b, outer))
        upper = min(paths, key=lambda m: m.high or 0) if paths else None
    if upper is None or upper.high is None:
        return Measure(low, None, layer, (), (item_a.where, item_b.where), True)
    return replace(upper, low=min(low, upper.low), layer=layer)


__all__ = ["analyze_distances"]
