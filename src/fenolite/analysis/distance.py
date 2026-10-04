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

from collections import Counter
from collections.abc import Sequence
from dataclasses import replace

from fenolite.analysis.boundary import BoardBoundary
from fenolite.analysis.codes import issue
from fenolite.analysis.copper import ARC_TOL_NM, CopperShape, NetCopper, net_copper
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
    Face,
    SurfacePath,
    Terminal,
    boundary_distance,
    surface_distance,
    usable_terminals,
)
from fenolite.backends.base import BoardPad
from fenolite.core.errors import Issue
from fenolite.core.units import Nm
from fenolite.geometry import BBox, SpatialIndex, thick_bbox, thick_gap_floor, thick_touch, thick_witness
from fenolite.model.circuit import Net
from fenolite.model.design import Design

Pair = tuple[str, str]


def _box_gap(a: BBox, b: BBox) -> int:
    """A lower bound of the distance of two boxes: the larger of their separations along the axes."""
    dx = max(a.x0 - b.x1, b.x0 - a.x1, 0)
    dy = max(a.y0 - b.y1, b.y0 - a.y1, 0)
    return max(dx, dy)


def _layer_gap(first: Sequence[CopperShape], second: Sequence[CopperShape], layer: str) -> Measure | None:
    """The smallest gap between the shapes of two nets on one layer, as an interval with its witness."""
    best: tuple[int, int, CopperShape, CopperShape] | None = None  # low, gap, a, b
    boxes_b = [thick_bbox(item.shape) for item in second]
    for one in first:
        box_a = thick_bbox(one.shape)
        for other, box_b in zip(second, boxes_b, strict=True):
            bands = one.band + other.band
            if best is not None and _box_gap(box_a, box_b) - bands > best[0]:
                continue
            gap = 0 if thick_touch(one.shape, other.shape) else thick_gap_floor(one.shape, other.shape)
            low = max(0, gap - bands)
            if best is None or (low, gap) < (best[0], best[1]):
                best = (low, gap, one, other)
    if best is None:
        return None
    low, gap, one, other = best
    touching = gap == 0 and thick_touch(one.shape, other.shape)
    high = 0 if touching else gap + 1 + one.band + other.band
    return Measure(low, high, layer, (thick_witness(one.shape, other.shape),), (one.where, other.where))


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
) -> AnalysisReport:
    """One row per selected pair of nets: the gaps per layer, the clearance through air and the creepage
    along the surface, with the findings against the user's distance rows."""
    copper = net_copper(design, pads=pads, arc_tol=arc_tol)
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
            if opposite and not around:
                # with a common face the pair is still measured there; the count goes to the summary
                if same:
                    faces_alone += 1
                else:
                    missing["board outline" if not usable else "board thickness"] += 1
            named = (name_a, name_b) in named_pairs
            required = [value for value in wanted[:2] if value is not None]
            limit = max(required) if required else (None if named else within)
            if term_a and term_b and (same or around):
                path = surface_distance([t for t, _ in term_a], [t for t, _ in term_b], boundary, limit=limit)
                if path is not None:
                    creepage = _path_measure(path, term_a, term_b, outer)
                elif limit is not None:
                    items = (term_a[0][1].where, term_b[0][1].where)
                    creepage = Measure(limit, None, "/".join(dict.fromkeys(outer)), (), items, True)
            if opposite and around and boundary is not None and boundary.thickness is not None:
                across = _across(term_a, term_b, boundary, outer, creepage, same, limit)
                if across is not None:
                    through_air.append(across)
            if through_air:
                clearance = min(through_air, key=lambda m: (m.low, m.high is None, m.high or 0, m.layer))
        rows.append(DistanceRow(name_a, name_b, tuple(gaps), clearance, creepage))
        pair = (name_a, name_b)
        found_issues = [
            _judge(clearance, wanted[0], "analysis.clearance-below", "analysis.clearance-undecided",
                   "clearance", pair),
            _judge(creepage, wanted[1], "analysis.creepage-below", "analysis.creepage-undecided",
                   "creepage", pair),
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
    ordered = sorted_issues(issues)
    summary: dict[str, object] = {
        "pairs": len(rows),
        "unsupported": dict(copper.unsupported),
        "boundary": boundary.source if boundary is not None else "none",
        "faces_alone": faces_alone,
    }
    return AnalysisReport(tuple(rows), ordered, summary, report_evidence(ordered))


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
