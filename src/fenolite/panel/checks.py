# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The panel checks (capability board-panels, "Panel checks"; change c0173, design Decision 6).

``check_panel(panel, layout, board)`` runs before anything is written; an error finding plans no write
(exit 5). The limits are ``panel.limits.resolved(panel.limits)``: each default names its source. Copper is
judged in the board's own frame: a score line or a mouse-bite hole is moved back into the frame of each copy
it touches, and its distance to the board's copper (tracks, arcs, vias, pads and zone fills on every copper
layer, as ``checks.copper`` shapes them) is the exact gap of two thick shapes, rounded down to the
nanometre.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.checks.copper import ARC_TOL_NM
from fenolite.checks.copper import _Items as CopperItems  # pyright: ignore[reportPrivateUsage]
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.units import format_length
from fenolite.geometry.thick import Thick, thick_gap_floor
from fenolite.model.design import Design
from fenolite.model.panel import DEFAULT_GAP, Panel
from fenolite.panel.layout import PanelCopy, PanelLayout, Rect, ScoreLine, board_shape
from fenolite.panel.limits import Limits, resolved

OUTER = ("F.Cu", "B.Cu")
"""The outer copper layers by KiCad's names, which ``checks.copper`` gives every board."""


def _mm(value: int) -> str:
    """``value`` as millimetres with a space before the unit: ``0.3 mm``."""
    return f"{format_length(value)[:-2]} mm"


def _issue(
    code: str, severity: Literal["error", "warning", "info"], message: str, where: str, hint: str = ""
) -> Issue:
    return Issue(code, severity, message, where=where, hint=hint)


def _copy_name(copy: PanelCopy) -> str:
    return f"copy {copy.k} (row {copy.row}, column {copy.col})"


@dataclass(frozen=True, slots=True)
class _Copper:
    """The board's copper shapes by layer, in the board frame."""

    shapes: tuple[tuple[str, Thick], ...]

    def gap(self, probe: Thick, layers: Iterable[str] | None = None) -> tuple[int, str] | None:
        """The least gap from ``probe`` to the copper (of ``layers``, else of every layer), and that layer;
        ``None`` without copper."""
        wanted = None if layers is None else set(layers)
        best: tuple[int, str] | None = None
        for layer, shape in self.shapes:
            if wanted is not None and layer not in wanted:
                continue
            found = thick_gap_floor(probe, shape)
            if best is None or found < best[0]:
                best = (found, layer)
        return best


def copper_of(board: Design) -> _Copper:
    """The copper shapes of ``board`` (tracks, arcs, vias, pads, zone fills) by layer."""
    from fenolite.backends.kicad.frame import board_pads

    items = CopperItems(board, board_pads(board), ARC_TOL_NM)
    shapes: list[tuple[str, Thick]] = []
    for item in items.items:
        for layer, found in item.shapes.items():
            shapes += [(layer, shape.narrow) for shape in found]
    return _Copper(tuple(shapes))


def _span(line: ScoreLine, rect: Rect) -> tuple[Point, Point] | None:
    """The part of ``line`` over the copy ``rect``, or ``None`` when the line runs elsewhere."""
    if line.axis == "x":
        if not rect.x0 <= line.at <= rect.x1:
            return None
        return Point(line.at, rect.y0), Point(line.at, rect.y1)
    if not rect.y0 <= line.at <= rect.y1:
        return None
    return Point(rect.x0, line.at), Point(rect.x1, line.at)


def _vscore(
    panel: Panel, laid: PanelLayout, copper: _Copper, limits: Limits, thickness: int | None
) -> list[Issue]:
    found: list[Issue] = []
    lines = laid.score_lines
    if not lines:
        return found
    # vscore(clearance=…) and limits={"vscore_copper": …} say the same; the limit, when given, governs
    clearance = panel.vscore.clearance if panel.limits.vscore_copper is None else limits.vscore_copper
    for line in lines:
        for copy in laid.copies:
            span = _span(line, copy.rect)
            if span is None:
                continue
            probe = Thick(tuple(copy.unplace(p) for p in span), 0)
            gap = copper.gap(probe)
            if gap is not None and gap[0] < clearance:
                found.append(
                    _issue(
                        "panel.vscore-copper",
                        "error",
                        f"copper of {_copy_name(copy)} on {gap[1]} is {_mm(gap[0])} from the score line "
                        f"{line.boundary}; the limit is {_mm(clearance)} (S-0799)",
                        where=f"{copy.id}, {line.id}",
                        hint="move the copper away from the edge, or tab this edge set instead",
                    )
                )
    if panel.array.gap_x != DEFAULT_GAP and panel.method("columns") == "vscore" and laid.cols > 1:
        found.append(
            _issue(
                "panel.vscore-shape",
                "error",
                "the columns are scored, and a gap of "
                f"{_mm(panel.array.gap_x)} was asked: scored boards touch",
                "columns",
            )
        )
    if panel.array.gap_y != DEFAULT_GAP and panel.method("rows") == "vscore" and laid.rows > 1:
        found.append(
            _issue(
                "panel.vscore-shape",
                "error",
                f"the rows are scored, and a gap of {_mm(panel.array.gap_y)} was asked: scored boards touch",
                "rows",
            )
        )
    for axis in ("x", "y"):
        ats = sorted(line.at for line in lines if line.axis == axis)
        for a, b in zip(ats, ats[1:], strict=False):
            apart = b - a
            if apart < limits.vscore_spacing:
                severity: Literal["error", "warning"] = "error"
                limit, source = limits.vscore_spacing, "S-0796"
            elif apart < limits.vscore_spacing_warn:
                severity, limit, source = "warning", limits.vscore_spacing_warn, "S-0801"
            else:
                continue
            found.append(
                _issue(
                    "panel.vscore-spacing",
                    severity,
                    f"two parallel score lines are {_mm(apart)} apart; the limit is {_mm(limit)} ({source})",
                    where=f"{axis}={_mm(a)}, {axis}={_mm(b)}",
                )
            )
    if thickness is None:
        found.append(
            _issue(
                "panel.vscore-thickness",
                "info",
                "the board states no thickness: V-score needs at least "
                f"{_mm(limits.vscore_thickness)} (S-0794), "
                f"{_mm(limits.vscore_thickness_warn)} for some fabricators (S-0801)",
                "board",
            )
        )
    elif thickness < limits.vscore_thickness:
        found.append(
            _issue(
                "panel.vscore-thickness",
                "error",
                f"the board is {_mm(thickness)} thick; V-score needs at "
                f"least {_mm(limits.vscore_thickness)} (S-0794)",
                "board",
            )
        )
    elif thickness < limits.vscore_thickness_warn:
        found.append(
            _issue(
                "panel.vscore-thickness",
                "warning",
                f"the board is {_mm(thickness)} thick; some fabricators score "
                f"from {_mm(limits.vscore_thickness_warn)} (S-0801)",
                "board",
            )
        )
    return found


def _tabs(panel: Panel, laid: PanelLayout, copper: _Copper, limits: Limits) -> list[Issue]:
    found: list[Issue] = []
    by_k = {copy.k: copy for copy in laid.copies}
    inner = sorted({layer for layer, _ in copper.shapes if layer not in OUTER})
    for tab in laid.tabs:
        for k in tab.copies:
            copy = by_k[k]
            worst: tuple[int, str, int] | None = None
            for hole in tab.holes:
                disc = Thick((copy.unplace(hole),), tab.drill)
                for layers, limit in ((OUTER, limits.tab_copper_outer), (inner, limits.tab_copper_inner)):
                    gap = copper.gap(disc, layers) if layers else None
                    if (
                        gap is not None
                        and gap[0] < limit
                        and (worst is None or gap[0] - limit < worst[0] - worst[2])
                    ):
                        worst = (gap[0], gap[1], limit)
            if worst is not None:
                found.append(
                    _issue(
                        "panel.tab-copper",
                        "error",
                        f"copper of {_copy_name(copy)} on {worst[1]} is "
                        f"{_mm(worst[0])} from a mouse-bite hole of "
                        f"tab {tab.edge}:{tab.k}; the limit is {_mm(worst[2])} (S-0799)",
                        where=f"{copy.id}, {tab.id}",
                        hint="move the copper away from the edge, or move the tab with tabs(pitch=…)",
                    )
                )
    gaps = laid.gaps
    used: dict[str, int] = {}
    if laid.cols > 1 and laid.methods.get("columns") == "tabs":
        used["between columns"] = gaps["columns"]
    if laid.rows > 1 and laid.methods.get("rows") == "tabs":
        used["between rows"] = gaps["rows"]
    for side in ("top", "bottom", "left", "right"):
        if gaps.get(side):
            used[f"to the {side} rail"] = gaps[side]
    for where, gap in used.items():
        if gap < limits.gap:
            found.append(
                _issue(
                    "panel.gap",
                    "error",
                    f"the routed gap {where} is {_mm(gap)}; the limit is {_mm(limits.gap)} (S-0795)",
                    where,
                    hint="widen the gap with grid(gap=…)",
                )
            )
        elif gap < limits.gap_warn:
            found.append(
                _issue(
                    "panel.gap",
                    "warning",
                    f"the routed gap {where} is {_mm(gap)}; some fabricators "
                    f"route {_mm(limits.gap_warn)} (S-0798)",
                    where,
                )
            )
    if laid.tabs and 0 < panel.tabs.holes < limits.tab_holes:
        found.append(
            _issue(
                "panel.tab-count",
                "warning",
                f"a mouse bite of {panel.tabs.holes} holes; {limits.tab_holes} or more are advised (S-0795)",
                "tabs",
            )
        )
    held = {copy.k: 0 for copy in laid.copies}
    for tab in laid.tabs:
        for k in tab.copies:
            held[k] += 1
    scored = _scored_sides(laid)
    for copy in laid.copies:
        sides = scored.get(copy.k, 0)
        if held[copy.k] == 0 and sides == 0 and len(laid.copies) + len(laid.rails) > 1:
            found.append(
                _issue(
                    "panel.tab-count",
                    "error",
                    f"{_copy_name(copy)} is held by no tab and no score line",
                    copy.id,
                )
            )
        elif sides == 0 and 0 < held[copy.k] < 2:
            found.append(
                _issue(
                    "panel.tab-count",
                    "warning",
                    f"{_copy_name(copy)} is held by {held[copy.k]} tab; two or more are advised (S-0795)",
                    copy.id,
                )
            )
    edges: dict[str, list[int]] = {}
    for tab in laid.tabs:
        centre = (tab.rect.y0 + tab.rect.y1) // 2 if tab.axis == "y" else (tab.rect.x0 + tab.rect.x1) // 2
        edges.setdefault(tab.edge, []).append(centre)
    for edge, centres in sorted(edges.items()):
        centres.sort()
        apart = max((b - a for a, b in zip(centres, centres[1:], strict=False)), default=0)
        if apart > limits.tab_spacing:
            found.append(
                _issue(
                    "panel.tab-spacing",
                    "warning",
                    f"tabs of edge {edge} are {_mm(apart)} apart; the limit "
                    f"is {_mm(limits.tab_spacing)} (S-0795)",
                    edge,
                    hint="add tabs with tabs(pitch=…)",
                )
            )
    return found


def _scored_sides(laid: PanelLayout) -> dict[int, int]:
    """How many of each copy's sides lie on a score line."""
    count: dict[int, int] = {}
    for copy in laid.copies:
        r = copy.rect
        n = 0
        for line in laid.score_lines:
            if line.axis == "x" and line.at in (r.x0, r.x1) and 0 < line.at < laid.size.w:
                n += 1
            elif line.axis == "y" and line.at in (r.y0, r.y1) and 0 < line.at < laid.size.h:
                n += 1
        count[copy.k] = n
    return count


def _on_rail(laid: PanelLayout, centre: Point, diameter: int) -> bool:
    half = (diameter + 1) // 2
    disc = Rect(centre.x - half, centre.y - half, centre.x + half, centre.y + half)
    return any(rail.contains(disc) for rail in laid.rails)


def _marks(laid: PanelLayout, limits: Limits) -> list[Issue]:
    found: list[Issue] = []
    w, h = laid.size.w, laid.size.h
    per_side: dict[str, int] = {}
    for f in laid.fiducials:
        per_side[f.side] = per_side.get(f.side, 0) + 1
        if not _on_rail(laid, f.at, f.mask):
            found.append(
                _issue(
                    "panel.fiducial-place",
                    "warning",
                    f"fiducial {f.ref} at ({_mm(f.at.x)}, {_mm(f.at.y)}) is not on a rail (S-0796)",
                    f.id,
                )
            )
        edge = min(f.at.x, f.at.y, w - f.at.x, h - f.at.y)
        if edge < limits.fiducial_edge:
            found.append(
                _issue(
                    "panel.fiducial-place",
                    "warning",
                    f"fiducial {f.ref}'s centre is {_mm(edge)} from the panel's edge; "
                    f"the limit is {_mm(limits.fiducial_edge)} (S-0794)",
                    f.id,
                )
            )
    for side, n in sorted(per_side.items()):
        if n < limits.fiducial_count:
            found.append(
                _issue(
                    "panel.fiducial-place",
                    "warning",
                    f"{n} fiducial(s) on the {side} side; "
                    f"{limits.fiducial_count} in an L are advised (S-0797)",
                    side,
                    hint="add fiducials() or fiducial(ref, x, y)",
                )
            )
    for hole in laid.tooling_holes:
        if not _on_rail(laid, hole.at, hole.drill):
            found.append(
                _issue(
                    "panel.tooling-place",
                    "warning",
                    f"tooling hole {hole.ref} at ({_mm(hole.at.x)}, "
                    f"{_mm(hole.at.y)}) is not wholly on a rail (S-0800)",
                    hole.id,
                )
            )
    return found


def _size(laid: PanelLayout, limits: Limits) -> list[Issue]:
    found: list[Issue] = []
    w, h = laid.size.w, laid.size.h
    for side, value in (("width", w), ("height", h)):
        if value < limits.size_min:
            found.append(
                _issue(
                    "panel.size",
                    "warning",
                    f"the panel's {side} is {_mm(value)}; the limit is {_mm(limits.size_min)} (S-0800)",
                    side,
                )
            )
        elif value > limits.size_max:
            found.append(
                _issue(
                    "panel.size",
                    "warning",
                    f"the panel's {side} is {_mm(value)}; keep it under {_mm(limits.size_max)} (S-0795)",
                    side,
                )
            )
    if laid.score_lines and (w < limits.vscore_size_min or h < limits.vscore_size_min):
        found.append(
            _issue(
                "panel.size",
                "warning",
                f"a scored panel of {_mm(w)} × {_mm(h)}; V-score panels start at "
                f"{_mm(limits.vscore_size_min)} a side (S-0794)",
                "size",
            )
        )
    return found


def renamed_nets(names: Sequence[str], copies: int) -> dict[str, str]:
    """``B<k>/<name>`` of every net name of every copy, keyed by the new name; ``ValueError`` naming the
    first collision."""
    found: dict[str, str] = {}
    for k in range(1, copies + 1):
        for name in names:
            new = f"B{k}/{name}"
            if new in found:
                raise ValueError(new)
            found[new] = name
    return found


def check_panel(panel: Panel, laid: PanelLayout, board: Design) -> tuple[Issue, ...]:
    """Every finding of ``panel`` laid out as ``laid`` over ``board``: the layout's own, then the copper,
    tabs, fiducials, tooling holes and size, sorted by code, place and message."""
    found = list(laid.issues)
    if not laid.copies:
        return tuple(found)
    limits = resolved(panel.limits)
    copper = copper_of(board)
    shape = board_shape(board)
    found += _vscore(panel, laid, copper, limits, shape.thickness if shape else None)
    found += _tabs(panel, laid, copper, limits)
    found += _marks(laid, limits)
    found += _size(laid, limits)
    try:
        renamed_nets([net.name for net in board.circuit.nets], len(laid.copies))
    except ValueError as error:
        found.append(
            _issue(
                "panel.net-collision", "error", f"two copies' nets would both be named {error}", str(error)
            )
        )
    return tuple(sorted(found, key=lambda i: (i.code, i.where, i.message)))


__all__ = ["check_panel", "copper_of", "renamed_nets"]
