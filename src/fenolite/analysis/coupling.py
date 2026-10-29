# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The coupling screen: which aggressor nets run beside which victim nets, ranked by a score (change c0204;
capability board-analyses, "Coupling screen"; user guide ``docs/analyses.md``, "Coupling screen").

For each pair of an aggressor net and a victim net, over the pieces of their tracks and arcs (arcs as their
polygonised centre lines):

- two pieces on one layer whose directions differ by at most ``1 / PARALLEL`` in sine run in parallel over
  the overlap of their projections; ``s`` is the edge gap there (the smaller of the gaps at the two ends of
  the overlap, not below 0). A stretch counts when ``s`` is at most ``REACH`` times ``h``, beyond which its
  weight is below 1 %;
- the score of a stretch of length ``ℓ`` is ``ℓ / (1 + (s/h)²)``, rounded down, with ``h`` the depth from
  the layer to the nearest other copper layer that holds a fill, through the stack-up, or the board
  thickness when there is no such layer or no stack-up;
- two pieces on neighbouring copper layers whose centre lines lie closer than the sum of their half-widths
  in plan overlap broadside over the overlap of their projections.

The score ranks pairs. It is not a voltage, a current or a ratio of either; nothing is judged. Each victim
also gets the share of its length that has reference copper under it, from ``analysis.returns``.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from math import floor, isqrt

from fenolite.analysis.codes import issue
from fenolite.analysis.copper import ARC_TOL_NM, CopperShape, copper_layers, net_copper
from fenolite.analysis.returns import analyze_returns
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Board
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PRACTICE-COUPLING",))
PARALLEL = 100
"""Two pieces are parallel when the sine of the angle between them is at most ``1 / PARALLEL``."""
REACH = 10
"""A stretch counts when its gap is at most ``REACH · h``."""
NOTE = "the score ranks pairs; it is not a voltage"

_Piece = tuple[Point, Point, int]


@dataclass(frozen=True, slots=True)
class CouplingRow:
    """One pair: the parallel length on one layer, the narrowest gap of those stretches, the score, the
    broadside overlap on neighbouring layers, and the layers of the parallel stretches."""

    aggressor: str
    victim: str
    parallel: int
    gap: int | None
    score: int | None
    broadside: int
    layers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VictimRow:
    """A victim net: its routed length and the share of it, in per mille, with reference copper under it."""

    net: str
    length: int
    referenced_permille: int | None


@dataclass(frozen=True, slots=True)
class CouplingReport:
    rows: tuple[CouplingRow, ...] = ()
    victims: tuple[VictimRow, ...] = ()
    heights: Mapping[str, int | None] = field(default_factory=lambda: {})
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = EVIDENCE
    summary: Mapping[str, object] = field(default_factory=lambda: {})


def _pieces(shapes: Sequence[CopperShape]) -> dict[str, list[_Piece]]:
    found: dict[str, list[_Piece]] = {}
    seen: set[tuple[str, str]] = set()
    for shape in shapes:
        if shape.kind not in ("track", "arc") or (shape.entity_id, shape.layer) in seen:
            continue
        seen.add((shape.entity_id, shape.layer))
        core = shape.shape.core
        found.setdefault(shape.layer, []).extend(
            (a, b, shape.shape.width) for a, b in zip(core, core[1:], strict=False) if a != b
        )
    return found


def heights(board: Board, layers: Sequence[str], thickness: int | None) -> dict[str, int | None]:
    """``h`` per copper layer: the depth through the stack-up to the nearest other copper layer that holds a
    fill, else the board thickness (``thickness``, else the stack-up's), else ``None``."""
    planes = {fill.layer for zone in board.zones for fill in zone.fills}
    stackup = board.stackup
    total = thickness if thickness is not None else (stackup.thickness() if stackup is not None else None)
    found: dict[str, int | None] = {}
    for layer in layers:
        depths: list[int] = []
        if stackup is not None:
            for plane in planes:
                if plane == layer or plane not in layers:
                    continue
                upper, lower = (layer, plane) if layers.index(layer) < layers.index(plane) else (plane, layer)
                try:
                    depths.append(sum(entry.thickness for entry in stackup.between(upper, lower)))
                except (KeyError, ValueError):
                    continue
        found[layer] = min(depths) if depths else total or None
    return found


def _overlap(a: _Piece, b: _Piece) -> tuple[Fraction, Fraction, Fraction] | None:
    """For two parallel pieces: the length of the overlap of ``b``'s projection on ``a`` and the distances
    between their centre lines at its two ends; ``None`` when they are not parallel or do not overlap."""
    p, q, _ = a
    r, t, _ = b
    ux, uy = q.x - p.x, q.y - p.y
    vx, vy = t.x - r.x, t.y - r.y
    l2, m2 = ux * ux + uy * uy, vx * vx + vy * vy
    cross = ux * vy - uy * vx
    if cross * cross * PARALLEL * PARALLEL > l2 * m2:
        return None
    t1 = (r.x - p.x) * ux + (r.y - p.y) * uy
    t2 = (t.x - p.x) * ux + (t.y - p.y) * uy
    lo, hi = max(min(t1, t2), 0), min(max(t1, t2), l2)
    if hi <= lo or t1 == t2:
        return None
    c1 = ux * (r.y - p.y) - uy * (r.x - p.x)
    c2 = ux * (t.y - p.y) - uy * (t.x - p.x)

    def at(tau: int) -> Fraction:
        lam = Fraction(tau - t1, t2 - t1)
        return abs(c1 + lam * (c2 - c1))

    root = Fraction(isqrt(l2 * 10**12), 10**6)  # |u| to a micro-nanometre, below the exact value
    length = Fraction(hi - lo) / root if root else Fraction(0)
    return length, at(lo) / root, at(hi) / root


def _score(length: Fraction, gap: Fraction, h: int) -> Fraction:
    return length * h * h / (h * h + gap * gap)


def analyze_coupling(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    aggressors: Sequence[str],
    victims: Sequence[str],
    board_thickness: int | None = None,
    arc_tol: int = ARC_TOL_NM,
) -> CouplingReport:
    """The coupling screen of the nets that ``aggressors`` and ``victims`` match (globs), ranked by score."""
    board = design.board
    if board is None:
        return CouplingReport()
    copper = net_copper(design, pads=pads, arc_tol=arc_tol)
    layers = copper_layers(board)
    neighbours = {
        layer: {layers[i] for i in (k - 1, k + 1) if 0 <= i < len(layers)} for k, layer in enumerate(layers)
    }
    h = heights(board, layers, board_thickness)

    def pick(globs: Sequence[str]) -> list[str]:
        return sorted(name for name in copper.by_net if any(fnmatch.fnmatchcase(name, g) for g in globs))

    chosen_a, chosen_v = pick(aggressors), pick(victims)
    issues: list[Issue] = []
    for role, globs, chosen in (("aggressor", aggressors, chosen_a), ("victim", victims, chosen_v)):
        if not chosen:
            issues.append(
                issue(
                    "analysis.input-missing",
                    f"no {role} net matches {', '.join(globs)}",
                    where="coupling",
                    hint=f"--{role} GLOB",
                )
            )
    if any(value is None for value in h.values()):
        issues.append(
            issue(
                "analysis.input-missing",
                "no height to a plane: the board has no stack-up and no thickness, so no stretch is scored",
                where="board thickness",
                hint="--board-thickness 1.6mm, or a stack-up in the board",
            )
        )
    pieces = {net: _pieces(copper.by_net[net]) for net in {*chosen_a, *chosen_v}}
    rows: list[CouplingRow] = []
    for a in chosen_a:
        for v in chosen_v:
            if a == v:
                continue
            rows.append(_pair(a, v, pieces[a], pieces[v], neighbours, h))
    rows.sort(
        key=lambda row: (row.score is None, -(row.score or 0), -row.parallel, row.aggressor, row.victim)
    )
    returns = analyze_returns(design, pads=pads, nets=chosen_v or ["\x00"], arc_tol=arc_tol)
    victims_rows = tuple(
        VictimRow(
            row.net,
            row.length,
            (row.length - row.unreferenced) * 1000 // row.length if row.length else None,
        )
        for row in returns.rows
    )
    level = Level.UNVERIFIED if copper.unsupported or pads is None else EVIDENCE.level
    summary: dict[str, object] = {"pairs": len(rows), "victims": len(victims_rows), "note": NOTE}
    return CouplingReport(
        tuple(rows), victims_rows, h, tuple(issues), Evidence(level, hypotheses=EVIDENCE.hypotheses), summary
    )


def _pair(
    a: str,
    v: str,
    ours: Mapping[str, list[_Piece]],
    theirs: Mapping[str, list[_Piece]],
    neighbours: Mapping[str, set[str]],
    h: Mapping[str, int | None],
) -> CouplingRow:
    parallel = Fraction(0)
    score = Fraction(0)
    broadside = Fraction(0)
    gap: Fraction | None = None
    scored = True
    layers: set[str] = set()
    for layer, held in ours.items():
        height = h.get(layer)
        for piece in held:
            for other in theirs.get(layer, ()):
                found = _overlap(piece, other)
                if found is None:
                    continue
                length, d0, d1 = found
                s = max(min(d0, d1) - Fraction(piece[2] + other[2], 2), Fraction(0))
                if height is None:
                    scored = False
                    continue
                if s > REACH * height:
                    continue
                parallel += length
                score += _score(length, s, height)
                gap = s if gap is None else min(gap, s)
                layers.add(layer)
            for near in neighbours.get(layer, ()):
                for other in theirs.get(near, ()):
                    found = _overlap(piece, other)
                    if found is None:
                        continue
                    length, d0, d1 = found
                    if max(d0, d1) * 2 < piece[2] + other[2]:
                        broadside += length
    return CouplingRow(
        a,
        v,
        floor(parallel),
        None if gap is None else floor(gap),
        floor(score) if scored or score else None,
        floor(broadside),
        tuple(sorted(layers)),
    )


__all__ = ["EVIDENCE", "NOTE", "CouplingReport", "CouplingRow", "VictimRow", "analyze_coupling", "heights"]
