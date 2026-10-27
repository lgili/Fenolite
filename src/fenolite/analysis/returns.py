# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Return paths: where a signal track runs without reference copper on a neighbouring layer, and where a
signal via has no reference via near it (capability board-analyses, "Return paths"; user guide
``docs/analyses.md``, "Return paths").

The return current of a signal flows in the nearest plane, under the track. Where the plane has a gap or a
split, the return goes around it, and the loop that forms radiates and picks up noise. This analysis reads
the board's own copper:

- The reference layers of a copper layer are the copper layers next to it in the board's order: one for an
  outer layer, two for an inner one. The reference copper is the stored fill of the reference nets on those
  layers: the nets of ``reference`` when given, else every other net that has a fill there.
- A track or an arc is referenced where its centre line lies over reference copper on at least one
  reference layer. The parts that are not are spans: a ``split`` span lies inside the track, with reference
  copper on both sides along it (the track crosses a gap), an ``edge`` span reaches an end of the track
  (it leaves the plane, toward a connector for example).
- A via of a signal net is paired with the nearest via of a reference net; with ``via_distance``, a farther
  one is a finding.

Positions along a track come from ``CutLine`` of the crossing analysis, rounded outward, so a span is never
shorter than its exact length.
"""

from __future__ import annotations

import fnmatch
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import localcontext
from math import isqrt

from fenolite.analysis.codes import issue
from fenolite.analysis.copper import ARC_TOL_NM, CopperShape, copper_layers, net_copper
from fenolite.analysis.crossings import DIGITS, Cut, CutLine
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-RETURN-PATH",))


@dataclass(frozen=True, slots=True)
class Span:
    """A part of a track without reference copper: its layer, the item, its ends on the board, its length
    in nm, and its kind (``split`` or ``edge``)."""

    layer: str
    where: str
    start: Point
    end: Point
    length: int
    kind: str


@dataclass(frozen=True, slots=True)
class ViaReturn:
    """A via of a signal net and the nearest via of a reference net (``None`` without one), with the
    distance between their centres in nm."""

    where: str
    at: Point
    nearest: str | None
    distance: int | None


@dataclass(frozen=True, slots=True)
class ReturnRow:
    """One signal net: its routed length (centre lines), the length without reference, the spans, and its
    vias."""

    net: str
    length: int
    unreferenced: int
    spans: tuple[Span, ...] = ()
    vias: tuple[ViaReturn, ...] = ()


@dataclass(frozen=True, slots=True)
class ReturnReport:
    rows: tuple[ReturnRow, ...] = ()
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = EVIDENCE
    summary: Mapping[str, int] = field(default_factory=lambda: {})


def _neighbours(layers: Sequence[str]) -> dict[str, tuple[str, ...]]:
    found: dict[str, tuple[str, ...]] = {}
    for index, layer in enumerate(layers):
        found[layer] = tuple(layers[i] for i in (index - 1, index + 1) if 0 <= i < len(layers))
    return found


def _distance(a: Point, b: Point) -> int:
    d2 = (a.x - b.x) ** 2 + (a.y - b.y) ** 2
    return (isqrt(4 * d2) + 1) // 2


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _segment_spans(
    a: Point, b: Point, fills: Sequence[tuple[Point, ...]]
) -> tuple[int, list[tuple[int, int, Point, Point]]]:
    """The length of ``a–b`` and its free intervals (start, end along it, and their points)."""
    line = CutLine(Cut("", a, b))
    covered: list[tuple[int, int]] = []
    for ring in fills:
        for span in line.inside(ring):
            placed = line.along(span)
            if placed is not None:
                covered.append(placed)
    free: list[tuple[int, int, Point, Point]] = []
    at = 0
    for start, end in [*_merge(covered), (line.length, line.length)]:
        if start > at:
            free.append((at, start, line.point(at), line.point(start)))
        at = max(at, end)
    return line.length, free


def analyze_returns(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    nets: Sequence[str],
    reference: Sequence[str] = (),
    via_distance: int | None = None,
    arc_tol: int = ARC_TOL_NM,
) -> ReturnReport:
    """The return-path report of the nets whose name matches a pattern of ``nets``. ``reference`` names
    the reference nets (default: every other net with a fill on the reference layer); ``via_distance``
    makes a signal via farther than it from every reference via a finding."""
    board = design.board
    if board is None:
        return ReturnReport()
    copper = net_copper(design, pads=pads, arc_tol=arc_tol)
    layers = copper_layers(board)
    neighbours = _neighbours(layers)
    selected = sorted(name for name in copper.by_net if any(fnmatch.fnmatchcase(name, g) for g in nets))
    wanted_refs = set(reference)
    fills: dict[tuple[str, str], list[tuple[Point, ...]]] = defaultdict(list)
    for net, shapes in copper.by_net.items():
        for shape in shapes:
            if shape.kind == "fill":
                fills[net, shape.layer].append(shape.shape.core)
    names = {n.id: n.name for n in design.circuit.nets}
    issues: list[Issue] = []
    if not selected:
        issues.append(
            issue(
                "analysis.input-missing",
                f"no net matches {', '.join(nets)}",
                where="returns",
                hint="--net GLOB",
            )
        )
    rows: list[ReturnRow] = []
    with localcontext() as context:
        context.prec = DIGITS
        for net in selected:
            refs = wanted_refs - {net} if wanted_refs else {n for n, _ in fills if n != net}
            total = 0
            unreferenced = 0
            spans: list[Span] = []
            seen: set[tuple[str, str]] = set()
            for shape in copper.by_net[net]:
                if shape.kind not in ("track", "arc") or (shape.entity_id, shape.layer) in seen:
                    continue
                seen.add((shape.entity_id, shape.layer))
                spans += _shape_spans(shape, neighbours.get(shape.layer, ()), refs, fills)
                total += sum(
                    _distance(a, b) for a, b in zip(shape.shape.core, shape.shape.core[1:], strict=False)
                )
            unreferenced = sum(span.length for span in spans)
            vias = _via_returns(design, net, refs, names)
            rows.append(ReturnRow(net, total, unreferenced, tuple(spans), vias))
            for span in spans:
                if span.kind == "split":
                    issues.append(
                        issue(
                            "analysis.return-split",
                            f"{net} crosses a gap of its reference copper for {span.length} nm on "
                            f"{span.layer} ({span.where}, from {span.start.x},{span.start.y} to "
                            f"{span.end.x},{span.end.y})",
                            where=span.where,
                            hint="route around the gap, close the plane under the track, or add a stitching "
                            "capacitor across it",
                        )
                    )
            if via_distance is not None:
                for via in vias:
                    if via.distance is None or via.distance > via_distance:
                        far = (
                            "no reference via"
                            if via.distance is None
                            else f"the nearest at {via.distance} nm"
                        )
                        issues.append(
                            issue(
                                "analysis.return-via",
                                f"the via {via.where} of {net} has {far}, beyond {via_distance} nm",
                                where=via.where,
                                hint="put a reference via next to the signal via, so the return changes "
                                "layer too",
                            )
                        )
    level = Level.UNVERIFIED if copper.unsupported or pads is None else EVIDENCE.level
    summary = {
        "nets": len(rows),
        "split": sum(1 for row in rows for span in row.spans if span.kind == "split"),
        "edge": sum(1 for row in rows for span in row.spans if span.kind == "edge"),
    }
    return ReturnReport(tuple(rows), tuple(issues), Evidence(level, hypotheses=EVIDENCE.hypotheses), summary)


def _shape_spans(
    shape: CopperShape,
    references: Sequence[str],
    nets: set[str],
    fills: Mapping[tuple[str, str], Sequence[tuple[Point, ...]]],
) -> list[Span]:
    """The spans of one track or arc: the parts of its centre line over no reference fill."""
    rings = [ring for layer in references for net in sorted(nets) for ring in fills.get((net, layer), ())]
    core = shape.shape.core
    pieces = list(zip(core, core[1:], strict=False))
    lengths: list[int] = []
    free: list[tuple[int, int, Point, Point]] = []
    offset = 0
    for a, b in pieces:
        length, gaps = _segment_spans(a, b, rings)
        free += [(offset + s, offset + e, p, q) for s, e, p, q in gaps]
        offset += length
        lengths.append(length)
    total = offset
    joined: list[tuple[int, int, Point, Point]] = []
    for start, end, p, q in free:
        if joined and start <= joined[-1][1]:
            joined[-1] = (joined[-1][0], end, joined[-1][2], q)
        else:
            joined.append((start, end, p, q))
    out: list[Span] = []
    for start, end, p, q in joined:
        kind = "edge" if start <= 0 or end >= total else "split"
        out.append(Span(shape.layer, shape.where, p, q, end - start, kind))
    return out


def _via_returns(design: Design, net: str, refs: set[str], names: Mapping[str, str]) -> tuple[ViaReturn, ...]:
    board = design.board
    assert board is not None
    ours = [via for via in board.vias if via.net_id is not None and names.get(via.net_id) == net]
    theirs = [via for via in board.vias if via.net_id is not None and names.get(via.net_id) in refs]
    found: list[ViaReturn] = []
    for via in sorted(ours, key=lambda v: (v.position.x, v.position.y, v.id)):
        where = via.provenance.locator if via.provenance is not None and via.provenance.locator else via.id
        best = min(
            ((_distance(via.position, other.position), other) for other in theirs),
            key=lambda pair: (pair[0], pair[1].id),
            default=None,
        )
        if best is None:
            found.append(ViaReturn(where, via.position, None, None))
        else:
            other = best[1]
            other_where = (
                other.provenance.locator
                if other.provenance is not None and other.provenance.locator
                else other.id
            )
            found.append(ViaReturn(where, via.position, other_where, best[0]))
    return tuple(found)


__all__ = ["EVIDENCE", "ReturnReport", "ReturnRow", "Span", "ViaReturn", "analyze_returns"]
