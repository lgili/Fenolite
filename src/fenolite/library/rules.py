# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pure library checks; Fenolite conventions in docs/formats/library/rules.md (c0262)."""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from fenolite.backends import registry
from fenolite.backends.base import BoardFrame
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Level, min_level, parse_level, strength
from fenolite.core.quantities import LengthRange
from fenolite.geometry import (
    Location,
    Polygon,
    Segment,
    SegmentRelation,
    Thick,
    assemble_rings,
    classify_segments,
    dist2_point_segment,
    dist2_segment_segment,
    thick_touch,
)
from fenolite.geometry.errors import GeometryError
from fenolite.model.board import Board, FootprintInstance, Graphic, Layer, Pad
from fenolite.model.design import Design
from fenolite.model.library import DeviceDef, FootprintDef, SymbolDef

if TYPE_CHECKING:
    from fenolite.catalog.footprints.record import Package

LAND_TOLERANCE_NM = 50_000
PIN_GRID_NM = 254_000
PREFERRED_PIN_GRID_NM = 2_540_000
ROW_LETTERS = "ABCDEFGHJKLMNPRTUVWY"
TAB_AREA_RATIO = 2
"""A numbered pad more than this many times the median numbered-pad area is a tab or an exposed pad,
not a lead of the perimeter (``pin_order``, c0385)."""
PIN_ORDER_SOURCE = re.compile(r"\b[SD]-\d{4}\b")
"""A ``library.pin-order`` waiver names the S- or D- source whose top view shows the numbering (c0385)."""
UNWAIVABLE = frozenset({"library.record-invalid", "library.evidence-claim", "library.review-stale"})
RULES: Mapping[str, Severity] = {
    **{
        f"library.{name}": "error"
        for name in (
            "record-invalid",
            "pad-count",
            "pin1-location",
            "pin-order",
            "courtyard-missing",
            "courtyard-containment",
            "pad-clearance",
            "body-span",
            "depopulated",
            "land-mismatch",
            "pin-grid",
            "hidden-power",
            "duplicate-pin",
            "source-unknown",
            "evidence-claim",
            "review-stale",
            "interface-changed",
            "render-failed",
        )
    },
    **{
        f"library.{name}": "warning"
        for name in (
            "pin1-marker",
            "footprint-filter-miss",
            "footprint-filter-broad",
            "pin-group-type",
            "removed",
            "waiver-unused",
        )
    },
    "library.sources-unchecked": "info",
    "library.land-calculator-delta": "info",
}
ISSUE_CODES: Mapping[str, tuple[Severity, ...]] = {
    code: tuple(
        dict.fromkeys(
            (
                severity,
                *(
                    ("warning",)
                    if code in {"library.pin-grid", "library.land-mismatch", "library.pin-order"}
                    else ()
                ),
                *(("info",) if code not in UNWAIVABLE else ()),
            )
        )
    )
    for code, severity in RULES.items()
}


def issue(
    code: str, message: str, record_id: str = "", element: str = "", *, severity: Severity | None = None
) -> Issue:
    return Issue(code, severity or RULES[code], message, ":".join(filter(None, (record_id, element))))


def natural(values: Iterable[str]) -> list[str]:
    """Natural ordering with numeric runs compared as integers."""
    return sorted(
        set(values),
        key=lambda s: tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"(\d+)", s)),
    )


def electrical_pads(footprint: FootprintDef) -> set[str]:
    return {
        p.number
        for p in footprint.pads
        if p.number and p.kind != "np_thru_hole" and any(layer.endswith(".Cu") for layer in p.layers)
    }


def _cross(ax: int, ay: int, bx: int, by: int) -> int:
    return ax * by - ay * bx


def _on_sides(points: Sequence[Point]) -> bool:
    """Whether every lead lies on a side of the leads' bounding box and the leads of each side are one run
    of the numbering, read around (an outline numbered side by side: DIP, SO, QFP, QFN, SOT)."""
    x0, x1 = min(p.x for p in points), max(p.x for p in points)
    y0, y1 = min(p.y for p in points), max(p.y for p in points)
    if any(p.x not in (x0, x1) and p.y not in (y0, y1) for p in points):
        return False
    count = len(points)
    for side in (
        {i for i, p in enumerate(points) if p.x == x0},
        {i for i, p in enumerate(points) if p.x == x1},
        {i for i, p in enumerate(points) if p.y == y0},
        {i for i, p in enumerate(points) if p.y == y1},
    ):
        if 0 < len(side) < count and sum((i + 1) % count not in side for i in side) > 1:
            return False
    return True


def _row_beside_tab(points: Sequence[Point], tab: Point) -> str | None:
    """The order of leads in one row beside one tab (SOT-89, SOT-223, TO-252): pin 1 to the last lead turns
    counter-clockwise around the tab when the numbering does; ``None`` when the leads are no such row."""
    first, last = points[0], points[-1]
    dx, dy = last.x - first.x, last.y - first.y
    along = [(q.x - first.x) * dx + (q.y - first.y) * dy for q in points]
    turn = _cross(dx, dy, tab.x - first.x, tab.y - first.y)
    tab_along = (tab.x - first.x) * dx + (tab.y - first.y) * dy
    if (
        turn == 0
        or any(b <= a for a, b in zip(along, along[1:], strict=False))
        or not 0 < tab_along < dx * dx + dy * dy
        or any(2 * abs(_cross(dx, dy, q.x - first.x, q.y - first.y)) >= abs(turn) for q in points)
    ):
        return None
    return "clockwise" if turn > 0 else "counter-clockwise"


def _outline(points: Sequence[Point]) -> bool:
    """Whether the leads are numbered side by side around an outline: three leads as a SOT-23 (pins 1 and 2,
    or 2 and 3, on one side and the other lead across, within their span), four as two pairs on opposite
    sides (1-2 and 3-4: SOT-143, a four-pad crystal or LED), five or more on the sides of their bounding box,
    the leads of each side one run of the numbering read around (DIP, SO, QFP, QFN, DFN)."""
    if len(points) == 3:
        for i in (0, 1):
            a, b, c = points[i], points[i + 1], points[2 - 2 * i]
            if a.x == b.x != c.x and min(a.y, b.y) < c.y < max(a.y, b.y):
                return True
            if a.y == b.y != c.y and min(a.x, b.x) < c.x < max(a.x, b.x):
                return True
        return False
    if len(points) == 4:
        a, b, c, d = points
        return (a.x == b.x != c.x == d.x) or (a.y == b.y != c.y == d.y)
    return _on_sides(points)


def pin_order(footprint: FootprintDef) -> str | None:
    """``"clockwise"`` or ``"counter-clockwise"``: the turn of the numbered leads in the top view (X right,
    Y down), or ``None`` when the land is not numbered around a perimeter (c0385,
    ``docs/formats/library/rules.md`` row "Pin order").

    Only pads numbered ``1``, ``2``, ... count. A pad more than ``TAB_AREA_RATIO`` times the median area is
    a tab or an exposed pad: it moves the reference centre but is no lead, and a number keeps its smallest
    other pad. A row of leads beside one tab is read against the tab (``_row_beside_tab``). Otherwise the
    leads must be numbered side by side around an outline (``_outline``), and around the centre (the
    middle of the numbered pads' extent) every turn from one lead to the next must have the same sign;
    zig-zag rows, staggered rows (TO-92), single rows and scattered pins have no perimeter order."""
    pads = [
        p
        for p in footprint.pads
        if re.fullmatch(r"[1-9][0-9]*", p.number) and p.number in electrical_pads(footprint)
    ]
    if len({p.number for p in pads}) < 3:
        return None
    areas = sorted(p.size.w * p.size.h for p in pads)
    median = areas[(len(areas) - 1) // 2]
    tabs = [p for p in pads if p.size.w * p.size.h > TAB_AREA_RATIO * median]
    leads: dict[int, Pad] = {}
    for pad in pads:
        if pad in tabs:
            continue
        number = int(pad.number)
        kept = leads.get(number)
        if kept is None or pad.size.w * pad.size.h < kept.size.w * kept.size.h:
            leads[number] = pad
    points = [leads[n].position for n in sorted(leads)]
    if len(points) < 2:
        return None
    if len({(t.position.x, t.position.y) for t in tabs}) == 1:
        beside = _row_beside_tab(points, tabs[0].position)
        if beside is not None:
            return beside
    first = points[0]
    if all(
        _cross(q.x - first.x, q.y - first.y, r.x - first.x, r.y - first.y) == 0
        for q in points
        for r in points
    ):
        return None  # one row without a tab: no order the pads can show
    if not _outline(points):
        return None
    xs, ys = [p.position.x for p in pads], [p.position.y for p in pads]
    cx, cy = min(xs) + max(xs), min(ys) + max(ys)
    vectors = [(2 * q.x - cx, 2 * q.y - cy) for q in points if (2 * q.x, 2 * q.y) != (cx, cy)]
    turns = [_cross(*a, *b) for a, b in zip(vectors, vectors[1:], strict=False)]
    if len(vectors) < 3 or 0 in turns or (min(turns) < 0 < max(turns)):
        return None
    return "clockwise" if turns[0] > 0 else "counter-clockwise"


def _ring(graphic: Graphic) -> tuple[Point, ...] | None:
    points = graphic.points
    if graphic.kind == "rect" and len(points) == 2:
        a, b = points
        return (a, Point(b.x, a.y), b, Point(a.x, b.y))
    if graphic.kind in {"polygon", "polyline"} and len(points) >= 3:
        return points[:-1] if points[0] == points[-1] else points if graphic.filled else None
    return None


def _courtyards(graphics: Sequence[Graphic]) -> list[Polygon]:
    rings: list[Polygon] = []
    segments: list[Segment] = []
    for graphic in graphics:
        ring = _ring(graphic)
        if ring:
            try:
                rings.append(Polygon(ring))
            except GeometryError:
                continue
        elif graphic.kind == "line" and len(graphic.points) == 2:
            segments.append(Segment(*graphic.points))
    if segments:
        try:
            for path in assemble_rings(segments):
                # Courtyard line chains are closed by the geometry assembler.
                rings.append(Polygon(path.polygonize()))
        except GeometryError:
            pass
    return rings


def _contains(court: Polygon, shape: Thick) -> bool:
    if any(court.locate(point) is Location.OUTSIDE for point in shape.core):
        return False
    # Exact core-to-boundary distances also catch circles and oval ends crossing an edge.
    radius2 = shape.width * shape.width
    if radius2:
        for point in shape.core:
            for a, b in zip(court.outer, (*court.outer[1:], court.outer[0]), strict=True):
                if 4 * dist2_point_segment(point, a, b) < radius2:
                    return False
    if len(shape.core) > 1:
        for a, b in zip(shape.core, (*shape.core[1:], shape.core[0]), strict=True):
            mid = Point((a.x + b.x) // 2, (a.y + b.y) // 2)
            if court.locate(mid) is Location.OUTSIDE:
                return False
            for c, d in zip(court.outer, (*court.outer[1:], court.outer[0]), strict=True):
                if classify_segments(a, b, c, d) is SegmentRelation.PROPER:
                    return False
                if radius2 and 4 * dist2_segment_segment(a, b, c, d) < radius2:
                    return False
    return True


def check_footprint(
    footprint: FootprintDef,
    *,
    record_id: str = "",
    pins: int | None = None,
    polarized: bool = False,
    unused_pads: Iterable[str] = (),
    recorded: bool = True,
) -> list[Issue]:
    """Check standalone copper, courtyard and pin-1 geometry, with no external tool.

    ``recorded`` is false for a plain library item with no record: it has no waiver to name the source
    of a clockwise numbering, so ``library.pin-order`` is a warning there (c0385)."""
    record_id = record_id or footprint.lib_id
    found: list[Issue] = []
    numbers = electrical_pads(footprint) - set(unused_pads)
    pads = [p for p in footprint.pads if p.number in numbers]
    if pins is not None and len(numbers) != pins:
        found.append(
            issue(
                "library.pad-count",
                f"expected {pins} terminals; found {len(numbers)}: {natural(numbers)}",
                record_id,
                "pads",
            )
        )
    first = next((p for p in pads if p.number in {"1", "A1"}), None)
    if len(numbers) >= 3 or (len(numbers) == 2 and polarized):
        if first is None:
            found.append(issue("library.pin1-location", "no pad 1 or A1", record_id, "pad 1"))
        else:
            cx, cy, count = sum(p.position.x for p in pads), sum(p.position.y for p in pads), len(pads)
            x, y = first.position.x * count, first.position.y * count
            if x > cx or y > cy or (x == cx and y == cy):
                found.append(
                    issue(
                        "library.pin1-location",
                        "pad 1 is not above-left of the pad centroid",
                        record_id,
                        f"pad {first.number}",
                    )
                )
    if pin_order(replace(footprint, pads=tuple(pads))) == "clockwise":
        found.append(
            issue(
                "library.pin-order",
                "pads are numbered clockwise in the top view; JEDEC/IPC lands number counter-clockwise",
                record_id,
                "pads",
                severity=None if recorded else "warning",
            )
        )
    if first is not None and (len(numbers) >= 3 or polarized):
        marker = False
        for graphic in footprint.graphics:
            if graphic.layer not in {"F.SilkS", "F.Fab", "B.SilkS", "B.Fab"} or not graphic.points:
                continue
            x = min(p.x for p in graphic.points) + max(p.x for p in graphic.points)
            y = min(p.y for p in graphic.points) + max(p.y for p in graphic.points)
            d1 = (x - 2 * first.position.x) ** 2 + (y - 2 * first.position.y) ** 2
            if all(
                d1 < (x - 2 * p.position.x) ** 2 + (y - 2 * p.position.y) ** 2
                for p in pads
                if p.number != first.number
            ):
                marker = True
                break
        if not marker:
            found.append(
                issue("library.pin1-marker", "no silk/fab graphic uniquely marks pad 1", record_id, "pad 1")
            )
    court_layer = (
        "B.CrtYd"
        if pads and all("F.Cu" not in p.layers and "*.Cu" not in p.layers for p in pads)
        else "F.CrtYd"
    )
    courts = _courtyards(footprint.graphics_on(court_layer))
    if not courts:
        found.append(
            issue("library.courtyard-missing", f"no closed outline on {court_layer}", record_id, court_layer)
        )
    backend = registry.get("kicad")
    assert isinstance(backend, BoardFrame)
    instance = FootprintInstance(
        id="review-fp", component_id="", lib_ref=footprint.lib_id, position=Point(0, 0), pads=footprint.pads
    )
    board = Board(
        id="review-board",
        footprints=(instance,),
        layers=(
            Layer(id="front", name="F.Cu", kind="copper", ordinal=0),
            Layer(id="back", name="B.Cu", kind="copper", ordinal=31),
        ),
    )
    design = replace(Design.new("review", seed=0), board=board)
    copper = backend.board_pads(design)
    for pad in copper:
        if pad.kind == "np_thru_hole":
            continue
        if courts and any(
            not any(_contains(court, Thick(c.core, c.width, c.filled)) for court in courts)
            for c in pad.copper
        ):
            found.append(
                issue(
                    "library.courtyard-containment",
                    "copper lies outside the courtyard",
                    record_id,
                    f"pad {pad.number}",
                )
            )
    body_rings = [tuple(body.outline) for body in footprint.bodies if body.outline]
    if not body_rings:
        body_rings = [ring for g in footprint.graphics if g.layer in {"F.Fab", "B.Fab"} if (ring := _ring(g))]
    for ring in body_rings:
        if courts and not any(_contains(court, Thick(ring, 0, filled=True)) for court in courts):
            found.append(
                issue(
                    "library.courtyard-containment",
                    "body outline lies outside the courtyard",
                    record_id,
                    "body",
                )
            )
    for index, left in enumerate(copper):
        for right in copper[index + 1 :]:
            if not left.number or not right.number or left.number == right.number:
                continue
            if any(
                a.layer == b.layer
                and thick_touch(Thick(a.core, a.width, a.filled), Thick(b.core, b.width, b.filled))
                for a in left.copper
                for b in right.copper
            ):
                found.append(
                    issue(
                        "library.pad-clearance",
                        "pads touch or overlap on copper",
                        record_id,
                        f"pads {left.number},{right.number}",
                    )
                )
    return found


def check_device_map(
    device: DeviceDef, symbol: SymbolDef, footprint: FootprintDef, *, record_id: str = ""
) -> list[Issue]:
    """Compare pin and pad sets as well as every edge of the device map."""
    record_id = record_id or device.id
    pins, pads = {p.number for p in symbol.pins}, electrical_pads(footprint) - set(device.unused_pads)
    edges = [edge for pin in device.pins for edge in pin.pin_pads]
    reached_pins, reached_pads = {a for a, _ in edges}, {b for _, b in edges}
    if pins == reached_pins and pads == reached_pads:
        return []
    return [
        issue(
            "library.pad-count",
            f"unmapped pins {natural(pins - reached_pins)}; unknown pins {natural(reached_pins - pins)}; "
            f"unmapped pads {natural(pads - reached_pads)}; unknown pads {natural(reached_pads - pads)}",
            record_id,
            "pin-to-pad map",
        )
    ]


def check_symbol(
    symbol: SymbolDef, *, record_id: str = "", stacked: Iterable[str] = (), footprint: str | None = None
) -> list[Issue]:
    record_id = record_id or symbol.lib_id
    found: list[Issue] = []
    stack = set(stacked)
    seen: dict[tuple[int, int, str], Point] = {}
    for pin in symbol.pins:
        values = (pin.position.x, pin.position.y, pin.length)
        if any(v % PIN_GRID_NM for v in values):
            found.append(
                issue(
                    "library.pin-grid",
                    "connection point or length is off 10 mil",
                    record_id,
                    f"pin {pin.number}",
                )
            )
        elif any(v % PREFERRED_PIN_GRID_NM for v in values):
            found.append(
                issue(
                    "library.pin-grid",
                    "connection point or length is off the preferred 100 mil grid",
                    record_id,
                    f"pin {pin.number}",
                    severity="warning",
                )
            )
        key = (pin.unit, pin.body_style, pin.number)
        if key in seen and (pin.number not in stack or seen[key] != pin.position):
            found.append(
                issue(
                    "library.duplicate-pin",
                    "duplicate number in one unit/body style",
                    record_id,
                    f"pin {pin.number}",
                )
            )
        seen[key] = pin.position
        if (
            pin.hidden
            and pin.etype == "power_in"
            and not any(
                not other.hidden
                and other.position == pin.position
                and other.unit == pin.unit
                and other.body_style == pin.body_style
                for other in symbol.pins
            )
        ):
            found.append(
                issue(
                    "library.hidden-power",
                    "hidden power input is not stacked on a visible pin",
                    record_id,
                    f"pin {pin.number}",
                )
            )
    filters = symbol.properties.get("ki_fp_filters")
    patterns = filters.split() if filters is not None else []
    if filters is not None and (not patterns or any(not pattern.strip("*") for pattern in patterns)):
        found.append(
            issue(
                "library.footprint-filter-broad",
                "footprint filter accepts every name",
                record_id,
                "ki_fp_filters",
            )
        )
    if (
        footprint
        and filters is not None
        and not any(fnmatch.fnmatchcase(footprint.rsplit(":", 1)[-1], pattern) for pattern in patterns)
    ):
        found.append(
            issue(
                "library.footprint-filter-miss",
                f"filters {patterns} do not match {footprint}",
                record_id,
                "ki_fp_filters",
            )
        )
    return found


def check_pin_groups(rows: Iterable[tuple[str, str, str]], *, record_id: str = "") -> list[Issue]:
    return [
        issue(
            "library.pin-group-type", f"group {group} disagrees with type {etype}", record_id, f"pin {number}"
        )
        for number, group, etype in rows
        if (group in {"ground", "supply"} and etype not in {"power_in", "power_out", "passive"})
        or (group == "nc" and etype != "no_connect")
    ]


def row_name(index: int) -> str:
    result = ""
    while index >= 0:
        result = ROW_LETTERS[index % len(ROW_LETTERS)] + result
        index = index // len(ROW_LETTERS) - 1
    return result


@dataclass(frozen=True, slots=True)
class PackageFacts:
    """Normalized family facts supplied by the CLI or an importer."""

    family: str
    ranges: Mapping[str, LengthRange]
    pins: int | None = None
    rows: int = 0
    columns: int = 0
    depopulated: tuple[str, ...] = ()


def check_package(
    package: PackageFacts, footprint: FootprintDef | None = None, *, record_id: str = ""
) -> list[Issue]:
    found: list[Issue] = []
    ranges = package.ranges
    for name, value in sorted(ranges.items()):
        if value.min is not None and value.max is not None and value.min > value.max:
            found.append(issue("library.body-span", "range minimum exceeds maximum", record_id, name))
    width, lead = ranges.get("body.width"), ranges.get("lead.length")
    for name in ("span", "span_x", "span_y"):
        span = ranges.get(name)
        across = ranges.get("body.length") if name == "span_y" else width
        if span is None or across is None:
            continue
        if (
            package.family in {"gullwing", "to", "dip", "molded"}
            and across.max is not None
            and span.min is not None
            and across.max >= span.min
        ):
            found.append(
                issue(
                    "library.body-span", f"body maximum must be below {name} minimum", record_id, "body.width"
                )
            )
        if package.family == "nolead" and (
            (span.max is not None and across.min is not None and span.max < across.min)
            or (span.min is not None and across.max is not None and span.min > across.max)
        ):
            found.append(
                issue("library.body-span", f"{name} must overlap body width", record_id, "body.width")
            )
        if (
            lead is not None
            and lead.min is not None
            and span.max is not None
            and across.min is not None
            and 2 * lead.min >= span.max - across.min + 2 * LAND_TOLERANCE_NM
        ):
            found.append(
                issue("library.body-span", "lead length exceeds the available span", record_id, "lead.length")
            )
    if package.family == "grid":
        grid = {f"{row_name(r)}{c + 1}" for r in range(package.rows) for c in range(package.columns)}
        removed = set(package.depopulated)
        actual = electrical_pads(footprint) if footprint is not None else grid - removed
        count = len(grid) - len(removed)
        if (
            removed - grid
            or actual & removed
            or actual - grid
            or (package.pins is not None and count != package.pins)
            or len(removed) != len(package.depopulated)
        ):
            found.append(
                issue(
                    "library.depopulated",
                    f"{count} positions for {package.pins} pins; "
                    f"outside {natural((removed | actual) - grid)}; "
                    f"populated exclusions {natural(actual & removed)}",
                    record_id,
                    "depopulated",
                )
            )
    return found


def manufacturer_land(package: Package, footprint: FootprintDef) -> FootprintDef:
    """Resolve the manufacturer's pad dimensions/row positions independently of the generator."""
    assert package.land is not None
    land = package.land
    dimensions = land.table("pad")
    diameter = land.length("pad_diameter")
    ep = package.keys.text("ep_number") or str((package.keys.count("pins") or 0) + 1)
    tab = package.keys.table("tab")
    excluded: set[str] = {ep} if package.keys.table("ep") else set()
    if tab and tab.text("number"):
        excluded.add(tab.text("number") or "")
    pads: list[Pad] = []
    for pad in footprint.pads:
        if not pad.number or pad.number in excluded:
            pads.append(pad)
            continue
        position, size = pad.position, pad.size
        if dimensions:
            length, width = dimensions.length("length"), dimensions.length("width")
            if length and width and length.nominal is not None and width.nominal is not None:
                sx = land.length("row_spacing_x") or land.length("row_spacing")
                sy = land.length("row_spacing_y") or land.length("row_spacing")
                top_bottom = package.keys.text("arrangement") == "quad" and (
                    abs(position.y) * ((sx.nominal if sx else None) or 1)
                    > abs(position.x) * ((sy.nominal if sy else None) or 1)
                )
                size = (
                    Size(width.nominal, length.nominal) if top_bottom else Size(length.nominal, width.nominal)
                )
                spacing = land.length("row_spacing_y" if top_bottom else "row_spacing_x") or land.length(
                    "row_spacing"
                )
                if spacing and spacing.nominal is not None:
                    axis = position.y if top_bottom else position.x
                    shifted = (-1 if axis < 0 else 1) * spacing.nominal // 2
                    position = Point(position.x, shifted) if top_bottom else Point(shifted, position.y)
        elif diameter and diameter.nominal is not None:
            size = Size(diameter.nominal, diameter.nominal)
        pads.append(replace(pad, position=position, size=size))
    return replace(footprint, pads=tuple(pads))


def check_land_pattern(
    actual: FootprintDef, expected: FootprintDef, *, generated: bool = False, record_id: str = ""
) -> list[Issue]:
    """Compare numbered electrical pads with the manufacturer's resolved pattern."""

    def pads(fp: FootprintDef) -> dict[str, list[tuple[int, ...]]]:
        values: dict[str, list[tuple[int, ...]]] = {}
        for pad in fp.pads:
            if pad.number in electrical_pads(fp):
                values.setdefault(pad.number, []).append(
                    (pad.position.x, pad.position.y, pad.size.w, pad.size.h, pad.rotation)
                )
        return {key: sorted(value) for key, value in values.items()}

    a, b = pads(actual), pads(expected)
    differences: list[str] = []
    tolerance = 0 if generated else LAND_TOLERANCE_NM
    for number in natural(set(a) | set(b)):
        left, right = a.get(number, []), b.get(number, [])
        if len(left) != len(right) or any(
            any(abs(x - y) > tolerance for x, y in zip(p[:4], q[:4], strict=True)) or p[4] != q[4]
            for p, q in zip(left, right, strict=False)
        ):
            differences.append(number)
    if not differences:
        return []
    return [
        issue(
            "library.land-mismatch",
            f"manufacturer land differs at pads {differences}",
            record_id or actual.lib_id,
            "land",
            severity="error" if generated else "warning",
        )
    ]


def check_envelope(
    evidence: str,
    sources: Iterable[str],
    register: set[str] | None,
    *,
    reviewed: bool = False,
    record_id: str = "",
) -> list[Issue]:
    found: list[Issue] = []
    level = parse_level(evidence)
    if strength(level) > strength(Level.CORPUS_VERIFIED) or (level is Level.CORPUS_VERIFIED and not reviewed):
        found.append(
            issue(
                "library.evidence-claim",
                "evidence exceeds the supported human review claim",
                record_id,
                "evidence",
            )
        )
    if register is None:
        found.append(issue("library.sources-unchecked", "no source register found", record_id, "sources"))
    elif missing := sorted(set(sources) - register):
        found.append(issue("library.source-unknown", f"unknown source ids {missing}", record_id, "sources"))
    return found


def apply_waivers(
    findings: Sequence[Issue],
    waivers: Mapping[str, str],
    *,
    record_id: str = "",
    selected: set[str] | None = None,
) -> tuple[list[Issue], set[str]]:
    for code, reason in waivers.items():
        if code in UNWAIVABLE or not reason.strip() or code not in RULES:
            raise FormatError(f"invalid or forbidden waiver {code!r}", locator="waiver")
        if code == "library.pin-order" and not PIN_ORDER_SOURCE.search(reason):
            raise FormatError(
                "a library.pin-order waiver names the S- or D- source whose top view numbers the pads "
                "clockwise",
                locator="waiver",
            )
    used = {finding.code for finding in findings if finding.code in waivers}
    found = [
        replace(finding, severity="info", hint=f"waived: {waivers[finding.code]}")
        if finding.code in used
        else finding
        for finding in findings
    ]
    for code in sorted(set(waivers) - used):
        if selected is None or code in selected:
            found.append(
                issue("library.waiver-unused", f"waiver {code} produced no finding", record_id, "waiver")
            )
    return found, used


def effective_evidence(
    evidence: str,
    dependencies: Iterable[str] = (),
    *,
    stale: bool = False,
    reviewed: bool = False,
    previous_evidence: str = "UNVERIFIED",
) -> str:
    level = parse_level(evidence)
    if level is Level.CORPUS_VERIFIED and (stale or not reviewed):
        level = parse_level(previous_evidence)
    if strength(level) > strength(Level.CORPUS_VERIFIED):
        level = Level.UNVERIFIED
    return min_level(level, *(parse_level(label) for label in dependencies)).value
