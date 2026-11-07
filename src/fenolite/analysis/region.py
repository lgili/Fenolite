# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A region of a board drawn as SVG from the model, for looking at a crowded area (change c0211; capability
manufacturing-exports, "Region renders"; user guide ``docs/exports.md``, "Region renders").

The drawing is Fenolite's own: no tool runs, and the same board gives the same bytes. It holds, clipped to
the rectangle, the copper of every item whose box meets it (pads, tracks, arcs, vias and zone copper in its
state of ``analysis.pour``: the saved fill, the simulated pour as its cells, or the outline), the holes and
slots, the board edge and its cut-outs, a grid labelled in millimetres of board coordinates, and on request
the pads' net names, the open connections as straight lines and the ways of a barrier cut on each layer.
Every element carries ``class`` and ``data-*`` attributes, so a test or an agent reads the drawing as data.

Board coordinates are written in millimetres with the exact digits of their nanometres; the SVG ``y`` axis
points down, as the board's does.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from xml.sax.saxutils import escape, quoteattr

from fenolite.analysis.boundary import BoardBoundary
from fenolite.analysis.connectivity import ConnectivityReport, OpenConnection
from fenolite.analysis.copper import CopperShape, copper_layers
from fenolite.analysis.crossings import CrossingReport
from fenolite.analysis.pour import Cell, PourCopper, ZoneLayer
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry import Thick, thick_bbox
from fenolite.model.base import Entity
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-REGION-RENDER", "H-G-RENDER-DETERMINISTIC"))
"""The drawing shows the model's own geometry; a simulated pour is drawn to within one cell."""
MM = 1_000_000
STEPS = tuple(n * MM // 10 for n in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000))
"""The grid steps the drawing chooses from, 0.1 mm to 500 mm."""
AUTO_LINES = 10
"""The automatic grid is the smallest step that draws at most this many intervals on the longer side."""
MAX_LINES = 200
"""A grid that would draw more lines than this on one axis is refused."""
LAYER_COLOURS = {"F.Cu": "#c83737", "B.Cu": "#3b6fd6"}
INNER_COLOURS = ("#c8a837", "#37a85c", "#a837c8", "#37a8c8")
EDGE, HOLE, OPEN, CUT, GRID, TEXT, BACK = (
    "#d8c040",
    "#101010",
    "#ffffff",
    "#ff8c00",
    "#444a55",
    "#e8e8e8",
    "#1c1f26",
)


@dataclass(frozen=True, slots=True)
class Region:
    """A rectangle of the board, ``x0 < x1`` and ``y0 < y1``, in nanometres."""

    x0: int
    y0: int
    x1: int
    y1: int

    def __post_init__(self) -> None:
        if self.x0 >= self.x1 or self.y0 >= self.y1:
            raise ValueError(f"a region needs x0 < x1 and y0 < y1, got {self}")

    def meets(self, x0: int, y0: int, x1: int, y1: int) -> bool:
        return x0 <= self.x1 and x1 >= self.x0 and y0 <= self.y1 and y1 >= self.y0

    def holds(self, point: Point) -> bool:
        return self.x0 <= point.x <= self.x1 and self.y0 <= point.y <= self.y1


@dataclass(frozen=True, slots=True)
class RegionDrawing:
    """The SVG and what it holds: the grid step, the counts per element class, the zone layers that meet
    the region with their state, and the open connections drawn."""

    svg: bytes
    grid: int
    counts: Mapping[str, int] = field(default_factory=lambda: {})
    zones: tuple[ZoneLayer, ...] = ()
    open: tuple[tuple[str, OpenConnection], ...] = ()
    highlighted: Mapping[str, int] = field(default_factory=lambda: {})


def mm(value: int) -> str:
    """``value`` nanometres as millimetres with every digit it has: ``1500000`` is ``1.5``."""
    whole, rest = divmod(abs(value), MM)
    text = f"{whole}.{rest:06d}".rstrip("0").rstrip(".")
    return f"-{text}" if value < 0 else text


def auto_grid(region: Region) -> int:
    """The smallest step of ``STEPS`` that draws at most ``AUTO_LINES`` intervals on the longer side."""
    side = max(region.x1 - region.x0, region.y1 - region.y0)
    return next((step for step in STEPS if side <= AUTO_LINES * step), STEPS[-1])


def grid_lines(low: int, high: int, step: int) -> list[int]:
    """The multiples of ``step`` from ``low`` to ``high``, both included."""
    first = -(-low // step) * step
    return list(range(first, high + 1, step))


def check_grid(region: Region, step: int) -> None:
    """Refuse a step of 0 or below, or one that draws more than ``MAX_LINES`` lines on one axis."""
    if step <= 0:
        raise ValueError(f"the grid step must be above 0, got {step} nm")
    lines = max((region.x1 - region.x0) // step, (region.y1 - region.y0) // step) + 1
    if lines > MAX_LINES:
        raise ValueError(f"a grid of {mm(step)} mm draws {lines} lines on one axis, more than {MAX_LINES}")


def layer_colour(layer: str, layers: Sequence[str]) -> str:
    if layer in LAYER_COLOURS:
        return LAYER_COLOURS[layer]
    index = layers.index(layer) if layer in layers else 0
    return INNER_COLOURS[index % len(INNER_COLOURS)]


def _attrs(values: Mapping[str, object]) -> str:
    return "".join(f" {name}={quoteattr(str(value))}" for name, value in values.items())


def _el(tag: str, values: Mapping[str, object], text: str | None = None) -> str:
    """One element: empty, or holding ``text`` (escaped)."""
    return f"<{tag}{_attrs(values)}/>" if text is None else f"<{tag}{_attrs(values)}>{escape(text)}</{tag}>"


def _path(points: Sequence[Point], closed: bool) -> str:
    head, *rest = points
    text = f"M{mm(head.x)} {mm(head.y)}" + "".join(f" L{mm(p.x)} {mm(p.y)}" for p in rest)
    return text + (" Z" if closed else "")


def _shape(shape: Thick, colour: str, data: Mapping[str, object]) -> str:
    """One thick shape: a disc, a filled ring (grown by its width), or a stroked polyline."""
    if len(shape.core) == 1 and not shape.filled:
        (at,) = shape.core
        geometry = {"cx": mm(at.x), "cy": mm(at.y), "r": mm(shape.width // 2), "fill": colour}
        return f"<circle{_attrs({**data, **geometry})}/>"
    if shape.filled:
        geometry: dict[str, object] = {"d": _path(shape.core, True), "fill": colour}
        if shape.width:
            geometry |= {"stroke": colour, "stroke-width": mm(shape.width), "stroke-linejoin": "round"}
        return f"<path{_attrs({**data, **geometry})}/>"
    geometry = {
        "d": _path(shape.core, False),
        "fill": "none",
        "stroke": colour,
        "stroke-width": mm(shape.width),
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
    }
    return f"<path{_attrs({**data, **geometry})}/>"


def _cells_path(cells: Iterable[Cell], grid: int, region: Region) -> str:
    """The cells of a pour that meet the region, as one rectangle per run of cells along a row."""
    rows: dict[int, list[int]] = {}
    for i, j in cells:
        x0, y0 = i * grid, j * grid
        if region.meets(x0, y0, x0 + grid, y0 + grid):
            rows.setdefault(j, []).append(i)
    parts: list[str] = []
    for j in sorted(rows):
        columns = sorted(rows[j])
        start = previous = columns[0]
        for i in [*columns[1:], None]:
            if i is not None and i == previous + 1:
                previous = i
                continue
            x, y, width = start * grid, j * grid, (previous - start + 1) * grid
            parts.append(f"M{mm(x)} {mm(y)} h{mm(width)} v{mm(grid)} h{mm(-width)} Z")
            if i is not None:
                start = previous = i
    return " ".join(parts)


def _meets(region: Region, shape: Thick) -> bool:
    box = thick_bbox(shape)
    return region.meets(box.x0, box.y0, box.x1, box.y1)


def _line_meets(region: Region, a: Point, b: Point) -> bool:
    return region.meets(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y))


def _where(entity: Entity) -> str:
    provenance = entity.provenance
    return provenance.locator if provenance is not None and provenance.locator else entity.id


def _pad_name(record: BoardPad) -> str:
    holder = record.ref or record.footprint_id
    return f"{holder}-{record.number}" if record.number else holder


def whole_region(boundary: BoardBoundary | None) -> Region:
    """The board outline plus one millimetre, with a bounded fallback for an empty outline."""
    points = [p for ring in boundary.rings() for p in ring] if boundary is not None else []
    if not points:
        return Region(-MM, -MM, 11 * MM, 11 * MM)
    return Region(
        min(p.x for p in points) - MM,
        min(p.y for p in points) - MM,
        max(p.x for p in points) + MM,
        max(p.y for p in points) + MM,
    )


def draw_region(
    design: Design,
    *,
    region: Region,
    pads: Sequence[BoardPad] | None,
    boundary: BoardBoundary | None,
    pour: PourCopper,
    grid: int | None = None,
    nets: bool = False,
    opened: ConnectivityReport | None = None,
    crossings: CrossingReport | None = None,
    width_px: int = 1600,
    highlight: Sequence[str] = (),
    layers: Sequence[str] | None = None,
) -> RegionDrawing:
    """The SVG of ``region`` of ``design.board``. ``pour`` is the copper of ``analysis.pour``; ``nets`` adds
    one net label per pad whose position lies in the region; ``opened`` adds the open connections that meet
    the region; ``crossings`` adds each cut and its ways per layer. ``grid`` is the step of the grid
    (``auto_grid`` when ``None``)."""
    board = design.board
    step = auto_grid(region) if grid is None else grid
    check_grid(region, step)
    all_layers = copper_layers(board) if board is not None else ()
    selected_layers = (
        all_layers if layers is None else tuple(layer for layer in all_layers if layer in layers)
    )
    highlighted: dict[str, set[str]] = {kind: set() for kind in ("pads", "tracks", "arcs", "vias", "zones")}

    def marked(data: dict[str, object], kind: str, identity: str) -> dict[str, object]:
        if highlight:
            hi = data.get("data-net") in highlight
            data["class"] = str(data["class"]) + (" net-hi" if hi else " net-dim")
            if hi and kind in highlighted:
                if kind == "zones":
                    highlighted[kind].update(identity.split())
                else:
                    highlighted[kind].add(identity)
        return data

    width, height = region.x1 - region.x0, region.y1 - region.y0
    font = max(width, height) // 60
    counts: dict[str, int] = {}

    def count(name: str) -> None:
        counts[name] = counts.get(name, 0) + 1

    out: list[str] = []
    view = (region.x0 - 4 * font, region.y0 - 2 * font, width + 5 * font, height + 3 * font)
    pixels_high = max(1, width_px * view[3] // view[2])
    out.append(
        '<svg xmlns="http://www.w3.org/2000/svg"'
        + _attrs(
            {
                "viewBox": " ".join(mm(v) for v in view),
                "width": width_px,
                "height": pixels_high,
                "data-region": ",".join(mm(v) for v in (region.x0, region.y0, region.x1, region.y1)),
                "data-grid": mm(step),
                "data-units": "mm",
                "data-render": "fenolite.region.v1",
            }
        )
        + ">"
    )
    out.append("<style>.net-dim{opacity:0.2}.net-hi{opacity:1}</style>")
    out.append(f"<title>region {mm(region.x0)},{mm(region.y0)} to {mm(region.x1)},{mm(region.y1)} mm</title>")
    out.append(
        '<defs><clipPath id="region">'
        f"<rect{_attrs({'x': mm(region.x0), 'y': mm(region.y0), 'width': mm(width), 'height': mm(height)})}/>"
        "</clipPath></defs>"
    )
    out.append(
        _el(
            "rect",
            {
                "class": "background",
                "x": mm(view[0]),
                "y": mm(view[1]),
                "width": mm(view[2]),
                "height": mm(view[3]),
                "fill": BACK,
            },
        )
    )
    # the grid, labelled in millimetres of board coordinates
    out.append('<g id="grid">')
    thin = mm(max(1, font // 12))
    for axis, low, high in (("x", region.x0, region.x1), ("y", region.y0, region.y1)):
        for at in grid_lines(low, high, step):
            if axis == "x":
                ends = {"x1": mm(at), "y1": mm(region.y0), "x2": mm(at), "y2": mm(region.y1)}
                label = {"x": mm(at), "y": mm(region.y0 - font // 2), "text-anchor": "middle"}
            else:
                ends = {"x1": mm(region.x0), "y1": mm(at), "x2": mm(region.x1), "y2": mm(at)}
                label = {
                    "x": mm(region.x0 - font // 2),
                    "y": mm(at),
                    "text-anchor": "end",
                    "dominant-baseline": "central",
                }
            data = {"data-axis": axis, "data-at": at}
            out.append(
                f"<line{_attrs({'class': 'grid', **data, **ends, 'stroke': GRID, 'stroke-width': thin})}/>"
            )
            out.append(
                _el(
                    "text",
                    {"class": "grid-label", **data, **label, "font-size": mm(font), "fill": TEXT},
                    mm(at),
                )
            )
            count("grid")
    out.append("</g>")
    out.append('<g id="board" clip-path="url(#region)">')
    # the copper per layer, the bottom layer first
    by_layer: dict[str, list[tuple[str, CopperShape]]] = {}
    for net, shapes in pour.copper.by_net.items():
        for shape in shapes:
            by_layer.setdefault(shape.layer, []).append((net, shape))
    for shape in pour.loose:
        by_layer.setdefault(shape.layer, []).append(("", shape))
    zones = board.zones if board is not None else ()
    zone_layers: list[ZoneLayer] = []
    for state in pour.zones:
        zone = next((z for z in zones if z.id == state.zone_id), None)
        if zone is None or not zone.outline:
            continue
        xs, ys = [p.x for p in zone.outline], [p.y for p in zone.outline]
        if region.meets(min(xs), min(ys), max(xs), max(ys)):
            zone_layers.append(state)
    for layer in reversed(selected_layers):
        colour = layer_colour(layer, all_layers)
        out.append(f"<g{_attrs({'class': 'layer', 'data-layer': layer, 'opacity': '0.8'})}>")
        for state in zone_layers:
            if state.layer != layer:
                continue
            zone = next(z for z in zones if z.id == state.zone_id)
            data = {
                "class": "zone-outline",
                "data-item": state.zone_id,
                "data-zone": state.where,
                "data-net": state.net,
                "data-layer": layer,
            }
            data = marked(data, "zones", state.zone_id)
            out.append(
                _el(
                    "path",
                    {
                        **data,
                        "d": _path(zone.outline, True),
                        "fill": "none",
                        "stroke": colour,
                        "stroke-width": thin,
                        "stroke-dasharray": mm(max(1, font // 2)),
                    },
                )
            )
        for island in pour.islands:
            if island.layer != layer:
                continue
            path = _cells_path(island.cells, pour.grid, region)
            if path:
                data = {
                    "class": "zone",
                    "data-item": " ".join(island.zones),
                    "data-state": "simulated",
                    "data-zone": " ".join(island.zones),
                    "data-net": island.net,
                    "data-layer": layer,
                }
                data = marked(data, "zones", str(data["data-item"]))
                out.append(f"<path{_attrs({**data, 'd': path, 'fill': colour, 'fill-opacity': '0.5'})}/>")
                count("zone")
        for net, shape in sorted(by_layer.get(layer, ()), key=lambda pair: pair[1].kind != "fill"):
            if shape.kind == "via" or not _meets(region, shape.shape):
                continue
            data: dict[str, object] = {
                "class": shape.kind if shape.kind != "fill" else "zone",
                "data-net": net,
                "data-layer": layer,
                "data-where": shape.where,
                "data-item": shape.entity_id,
            }
            if shape.kind == "fill":
                state = pour.state_of(shape.entity_id, layer) or "saved_fill"
                data |= {"data-state": state, "fill-opacity": "0.5"}
                count("zone")
            else:
                count(shape.kind)
            data = marked(
                data,
                {"fill": "zones", "pad": "pads", "track": "tracks", "arc": "arcs"}.get(shape.kind, ""),
                shape.entity_id,
            )
            out.append(_shape(shape.shape, colour, data))
        out.append("</g>")
    # vias once, then the holes and slots, then the edge
    names = {net.id: net.name for net in design.circuit.nets}
    out.append('<g id="vias">')
    for via in board.vias if board is not None else ():
        disc = Thick((via.position,), via.diameter)
        if not _meets(region, disc) or not any(
            s.entity_id == via.id for layer in selected_layers for _, s in by_layer.get(layer, ())
        ):
            continue
        net = names.get(via.net_id or "", via.net_id or "")
        data = {
            "class": "via",
            "data-net": net,
            "data-item": via.id,
            "data-where": _where(via),
            "data-layers": " ".join(via.layers),
        }
        data = marked(data, "vias", via.id)
        out.append(_shape(disc, "#b0b0b0", data))
        count("via")
    out.append("</g>")
    out.append('<g id="holes">')
    for via in board.vias if board is not None else ():
        hole = Thick((via.position,), via.drill)
        if via.drill > 0 and _meets(region, hole):
            out.append(
                _shape(hole, HOLE, {"class": "hole", "data-where": _where(via), "data-plated": "true"})
            )
            count("hole")
    for record in pads or ():
        if not record.hole or not record.drill:
            continue
        hole = Thick(record.hole, record.drill)
        if not _meets(region, hole):
            continue
        kind = "slot" if len(record.hole) > 1 else "hole"
        plated = "false" if record.kind == "np_thru_hole" else "true"
        out.append(
            _shape(hole, HOLE, {"class": kind, "data-where": _pad_name(record), "data-plated": plated})
        )
        count(kind)
    out.append("</g>")
    out.append('<g id="edge">')
    for index, ring in enumerate(boundary.rings() if boundary is not None else ()):
        if len(ring) < 2:
            continue
        name = "outline" if index == 0 else "cutout"
        out.append(
            _el(
                "path",
                {
                    "class": "edge",
                    "data-ring": name,
                    "d": _path(ring, True),
                    "fill": "none",
                    "stroke": EDGE,
                    "stroke-width": thin,
                },
            )
        )
        count("edge")
    out.append("</g>")
    drawn: list[tuple[str, OpenConnection]] = []
    if opened is not None:
        out.append('<g id="open">')
        for row in opened.nets:
            for link in row.open:
                if not _line_meets(region, link.a.position, link.b.position):
                    continue
                data = {
                    "class": "open",
                    "data-net": row.name,
                    "data-a": link.a.where,
                    "data-b": link.b.where,
                    "data-length": link.length,
                    "x1": mm(link.a.position.x),
                    "y1": mm(link.a.position.y),
                    "x2": mm(link.b.position.x),
                    "y2": mm(link.b.position.y),
                    "stroke": OPEN,
                    "stroke-width": mm(max(1, font // 8)),
                    "stroke-dasharray": mm(max(1, font // 3)),
                }
                out.append(f"<line{_attrs(data)}><title>{escape(row.name)}</title></line>")
                drawn.append((row.name, link))
                count("open")
        out.append("</g>")
    if crossings is not None:
        out.append('<g id="cuts">')
        for row in crossings.rows:
            ends = {"x1": mm(row.a.x), "y1": mm(row.a.y), "x2": mm(row.b.x), "y2": mm(row.b.y)}
            data = {"class": "cut", "data-cut": row.cut, "data-supply": row.supply, "data-open": row.open}
            out.append(f"<line{_attrs({**data, **ends, 'stroke': CUT, 'stroke-width': thin})}/>")
            count("cut")
            for entry in row.layers:
                for way in entry.ways:
                    data = {
                        "class": "way",
                        "data-cut": row.cut,
                        "data-layer": entry.layer,
                        "data-tracks": way.tracks,
                        "data-length": way.length,
                        "x1": mm(way.a.x),
                        "y1": mm(way.a.y),
                        "x2": mm(way.b.x),
                        "y2": mm(way.b.y),
                        "stroke": layer_colour(entry.layer, all_layers),
                        "stroke-width": mm(max(1, font // 4)),
                    }
                    out.append(f"<line{_attrs(data)}/>")
                    count("way")
        out.append("</g>")
    out.append("</g>")
    if nets:
        out.append('<g id="labels">')
        for record in sorted(pads or (), key=lambda r: (_pad_name(r), r.position.x, r.position.y)):
            if record.net is None or not region.holds(record.position):
                continue
            data = {
                "class": "net-label",
                "data-pad": _pad_name(record),
                "data-net": record.net,
                "x": mm(record.position.x),
                "y": mm(record.position.y),
                "font-size": mm(max(1, font * 2 // 3)),
                "text-anchor": "middle",
                "dominant-baseline": "central",
                "fill": TEXT,
            }
            out.append(f"<text{_attrs(data)}>{escape(record.net)}</text>")
            count("label")
        out.append("</g>")
    out.append("</svg>")
    svg = ("\n".join(out) + "\n").encode("utf-8")
    return RegionDrawing(
        svg,
        step,
        dict(sorted(counts.items())),
        tuple(zone_layers),
        tuple(drawn),
        {k: len(v) for k, v in highlighted.items()},
    )


__all__ = [
    "EVIDENCE",
    "MAX_LINES",
    "STEPS",
    "Region",
    "RegionDrawing",
    "auto_grid",
    "check_grid",
    "draw_region",
    "grid_lines",
    "mm",
]
