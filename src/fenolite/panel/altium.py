# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The flattened Altium panel (capability altium-pcb-writer, "Flattened panel documents"; capability
altium-build, "Panel project of an Altium board"; change c0173, design Decisions 4 and 8).

The panel is written from a model: the board (read from its ``.kicad_pcb`` with its footprints' items
projected, as the conversion to Altium reads it, or imported from its ``.PcbDoc``) is copied once per copy
by ``copy_board``: every id derived from the copy's key, every net renamed ``B<k>/<name>``, every point of
the board frame moved by the copy's exact translation after its quarter turn. Then the panel's own items:
the board shape is the panel's rectangle; the routed gaps (``layout.routes``) are lines on a mechanical
layer named ``Route Tool Path`` and the score lines lines on one named ``V-Cut`` (S-0791, S-0792: no layer
type is written until Part Q measures where it is stored); mouse-bite and tooling holes are free round
non-plated holes; fiducials are free round copper pads on the Top (or Bottom) Layer, their mask opening
the rule's. ``lower.from_design`` lowers it and ``pcbdoc.write_pcbdoc`` writes it; the project lists the
panel document alone.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from fenolite.backends.altium import lower, pcbdoc
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id, is_id, parse_id
from fenolite.core.trig import FULL_TURN
from fenolite.core.units import Nm
from fenolite.model.base import Entity
from fenolite.model.board import (
    Arc,
    Board,
    Dimension,
    FootprintInstance,
    Graphic,
    Hole,
    Keepout,
    Layer,
    Outline,
    Pad,
    Text,
    Track,
    Via,
    Zone,
)
from fenolite.model.circuit import Circuit, Component, Net
from fenolite.model.design import Design
from fenolite.model.panel import Panel
from fenolite.panel import ids
from fenolite.panel.kicad import ORIGIN
from fenolite.panel.layout import PanelCopy, PanelLayout, Rect

if TYPE_CHECKING:
    from fenolite.backends.altium.pour import PourMode

ROUTE_LAYER = "Route Tool Path"
"""The name of the mechanical layer of the routed gaps: older versions find routing data by this name
(S-0792)."""
VCUT_LAYER = "V-Cut"
"""The name of the mechanical layer of the score lines."""
ROUTE_USER, VCUT_USER = "User.1", "User.2"
"""The model layers the two are drawn on; ``lower.KICAD_MECHANICAL`` maps them to Mechanical 1 and 2."""
LINE_WIDTH: Nm = 100_000
EDGE = "Edge.Cuts"
FLATTENED = "altium.panel-flattened"


def _shift(p: Point) -> Point:
    return Point(p.x + ORIGIN.x, p.y + ORIGIN.y)


def _ids(value: Any, found: set[str]) -> None:
    """Every id held by an entity of ``value`` (its ``id`` field), collected into ``found``."""
    if isinstance(value, Entity):
        found.add(value.id)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for f in dataclasses.fields(value):
            _ids(getattr(value, f.name), found)
    elif isinstance(value, (tuple, list)):
        for item in cast("tuple[Any, ...]", value):
            _ids(item, found)


def _renamed(value: Any, mapping: Mapping[str, str]) -> Any:
    """``value`` with every string equal to an old id replaced by its new id, recursively."""
    if isinstance(value, str):
        return mapping.get(value, value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        changes = {}
        for f in dataclasses.fields(value):
            old = getattr(value, f.name)
            new = _renamed(old, mapping)
            if new is not old:
                changes[f.name] = new
        return dataclasses.replace(value, **changes) if changes else value
    if isinstance(value, tuple):
        items = cast("tuple[Any, ...]", value)
        new_items = tuple(_renamed(item, mapping) for item in items)
        return new_items if any(a is not b for a, b in zip(items, new_items, strict=True)) else items
    if isinstance(value, dict):
        table = cast("dict[Any, Any]", value)
        return {key: _renamed(item, mapping) for key, item in table.items()}
    return value


def _turn(angle: int, rotation: int) -> int:
    return (angle + rotation) % FULL_TURN


def _moved(item: Any, copy: PanelCopy) -> Any:  # noqa: C901, PLR0911
    """A board item with its board-frame points moved into the panel and its absolute angle turned."""

    def at(p: Point) -> Point:
        return _shift(copy.place(p))

    def ring(points: tuple[Point, ...]) -> tuple[Point, ...]:
        return tuple(at(p) for p in points)

    turn = copy.rotation
    if isinstance(item, FootprintInstance):
        return dataclasses.replace(item, position=at(item.position), rotation=_turn(item.rotation, turn))
    if isinstance(item, Track):
        return dataclasses.replace(item, start=at(item.start), end=at(item.end))
    if isinstance(item, Arc):
        return dataclasses.replace(item, start=at(item.start), mid=at(item.mid), end=at(item.end))
    if isinstance(item, Via):
        return dataclasses.replace(item, position=at(item.position))
    if isinstance(item, Zone):
        fills = tuple(dataclasses.replace(f, polygon=ring(f.polygon)) for f in item.fills)
        return dataclasses.replace(item, outline=ring(item.outline), fills=fills)
    if isinstance(item, Keepout):
        return dataclasses.replace(item, outline=ring(item.outline))
    if isinstance(item, Text):
        return dataclasses.replace(item, position=at(item.position), rotation=_turn(item.rotation, turn))
    if isinstance(item, Graphic):
        return dataclasses.replace(item, points=ring(item.points))
    if isinstance(item, Dimension):
        return dataclasses.replace(item, start=at(item.start), end=at(item.end))
    if isinstance(item, Hole):
        return dataclasses.replace(
            item, position=at(item.position), rotation=_turn(item.rotation, turn) if item.length else 0
        )
    return item


def _on_box(graphic: Graphic, box: Rect) -> bool:
    if graphic.layer != EDGE or graphic.kind not in ("line", "rect", "polygon"):
        return False
    points = graphic.points
    if graphic.kind == "line":
        a, b = points[0], points[-1]
        return (a.x == b.x and a.x in (box.x0, box.x1)) or (a.y == b.y and a.y in (box.y0, box.y1))
    return all(p.x in (box.x0, box.x1) or p.y in (box.y0, box.y1) for p in points)


def copy_board(board_design: Design, laid: PanelLayout) -> tuple[Circuit, tuple[Board, ...], list[Issue]]:
    """The circuit of every copy (components, renamed nets) and each copy's board items, moved; the
    issues name what a flattened panel cannot hold (a copy's cut-outs: ``panel.altium-cutout``)."""
    board = board_design.board
    assert board is not None
    issues: list[Issue] = []
    outline = board.outline
    inner = [g for g in board.graphics if g.layer == EDGE and not _on_box(g, laid.board)]
    if inner or (outline is not None and (outline.cutouts or outline.slots)):
        issues.append(
            Issue(
                "panel.altium-cutout",
                "error",
                "the board has cut-outs or slots, which a flattened Altium panel does not hold yet",
                where="board",
                hint="panel the board for KiCad (--target 9 or 10)",
            )
        )
    source_ids: set[str] = set()
    _ids(board_design.circuit, source_ids)
    _ids(board, source_ids)
    components: list[Component] = []
    nets: list[Net] = []
    boards: list[Board] = []
    items = (
        "footprints",
        "tracks",
        "arcs",
        "vias",
        "zones",
        "keepouts",
        "texts",
        "graphics",
        "dimensions",
        "holes",
    )
    for copy in laid.copies:
        mapping = {
            old: ids.item_id(parse_id(old)[0], copy.row, copy.col, old) for old in source_ids if is_id(old)
        }
        circuit = cast(Circuit, _renamed(board_design.circuit, mapping))
        components += circuit.components
        nets += [
            dataclasses.replace(net, name=f"B{copy.k}/{net.name}") if net.name else net
            for net in circuit.nets
        ]
        moved: dict[str, tuple[Any, ...]] = {}
        for name in items:
            values = cast("tuple[Any, ...]", getattr(board, name))
            if name == "graphics":
                values = tuple(g for g in values if g.layer != EDGE)
            moved[name] = tuple(_moved(_renamed(v, mapping), copy) for v in values)
        boards.append(dataclasses.replace(board, **moved))
    circuit = Circuit(components=tuple(components), nets=tuple(nets))
    return circuit, tuple(boards), issues


def _lines(rings: tuple[tuple[Point, ...], ...], layer: str, key: str) -> list[Graphic]:
    found: list[Graphic] = []
    for r, ring in enumerate(rings):
        for e, start in enumerate(ring):
            end = ring[(e + 1) % len(ring)]
            found.append(
                Graphic(
                    id=derived_id("gfx", ids.BACKEND, f"{key}:{r}:{e}"),
                    kind="line",
                    layer=layer,
                    points=(_shift(start), _shift(end)),
                    width=LINE_WIDTH,
                )
            )
    return found


def panel_design(panel: Panel, laid: PanelLayout, board_design: Design) -> tuple[Design, list[Issue]]:
    """The model of the flattened panel: the copies, the panel's rectangle as the outline, the routed gaps
    and score lines on ``User.1`` and ``User.2``, the holes and the fiducials."""
    source = board_design.board
    assert source is not None
    circuit, boards, issues = copy_board(board_design, laid)
    # a board imported from a .PcbDoc names its mechanical layers Mech.<n>: the panel, written as a new
    # document, knows them by the names of lower.KICAD_MECHANICAL; Mechanical 1 and 2 are the panel's own
    by_id = {ident: name for name, ident in lower.KICAD_MECHANICAL.items()}
    mech = {f"Mech.{n}": by_id[56 + n] for n in range(3, 17) if 56 + n in by_id}
    boards = tuple(cast(Board, _renamed(b, mech)) for b in boards)
    names = {layer.name for layer in source.layers}
    layers = list(source.layers)
    for n, name in enumerate((ROUTE_USER, VCUT_USER)):
        if name not in names:
            layers.append(
                Layer(
                    id=derived_id("lay", ids.BACKEND, f"layer:{name}"),
                    name=name,
                    kind="user",
                    ordinal=900 + n,
                )
            )
    graphics = [g for b in boards for g in b.graphics]
    graphics += _lines(laid.routes, ROUTE_USER, "route")
    graphics += [
        Graphic(
            id=derived_id("gfx", ids.BACKEND, f"vscore:{line.id}"),
            kind="line",
            layer=VCUT_USER,
            points=tuple(_shift(p) for p in line.points()),
            width=panel.vscore.line_width,
        )
        for line in laid.score_lines
    ]
    holes = [h for b in boards for h in b.holes]
    for tab in laid.tabs:
        for n, hole in enumerate(tab.holes):
            holes.append(
                Hole(
                    id=derived_id("hol", ids.BACKEND, f"{tab.id}:{n}"), position=_shift(hole), drill=tab.drill
                )
            )
    for tooling in laid.tooling_holes:
        holes.append(
            Hole(
                id=derived_id("hol", ids.BACKEND, tooling.id),
                position=_shift(tooling.at),
                drill=tooling.drill,
            )
        )
    footprints = [fp for b in boards for fp in b.footprints]
    for fiducial in laid.fiducials:
        layers_of = ("F.Cu", "F.Mask") if fiducial.side == "top" else ("B.Cu", "B.Mask")
        pad = Pad(
            id=derived_id("pad", ids.BACKEND, f"{fiducial.id}:pad"),
            number="",
            shape="circle",
            size=Size(fiducial.copper, fiducial.copper),
            position=Point(0, 0),
            layers=layers_of,
            fab_property="fiducial_global",
        )
        footprints.append(
            FootprintInstance(
                id=derived_id("fp", ids.BACKEND, fiducial.id),
                component_id=derived_id("cmp", ids.BACKEND, fiducial.id),
                lib_ref="",
                position=_shift(fiducial.at),
                pads=(pad,),
                locked=True,
            )
        )
    frame = Rect(0, 0, laid.size.w, laid.size.h)
    outline = Outline(
        id=derived_id("out", ids.BACKEND, "outline"), points=tuple(_shift(p) for p in frame.corners())
    )
    board = Board(
        id=derived_id("brd", ids.BACKEND, "board"),
        outline=outline,
        layers=tuple(layers),
        stackup=source.stackup,
        footprints=tuple(footprints),
        tracks=tuple(t for b in boards for t in b.tracks),
        arcs=tuple(a for b in boards for a in b.arcs),
        vias=tuple(v for b in boards for v in b.vias),
        zones=tuple(z for b in boards for z in b.zones),
        keepouts=tuple(k for b in boards for k in b.keepouts),
        texts=tuple(t for b in boards for t in b.texts),
        graphics=tuple(graphics),
        holes=tuple(holes),
        dimensions=tuple(d for b in boards for d in b.dimensions),
        via_protection=source.via_protection,
    )
    header = dataclasses.replace(
        board_design.header, id=derived_id("dsn", ids.BACKEND, "design"), name=panel.name
    )
    rules = board_design.rules
    return Design(header=header, circuit=circuit, board=board, rules=rules), issues


def _named_layers(spec: pcbdoc.PcbDocSpec) -> pcbdoc.PcbDocSpec:
    """``spec`` with Mechanical 1 and 2 named ``Route Tool Path`` and ``V-Cut``, their graphics with them."""
    names = {ROUTE_USER: ROUTE_LAYER, VCUT_USER: VCUT_LAYER}
    ids_ = {name: ident for name, ident in spec.layer_ids.items() if name not in names}
    for user, name in names.items():
        if user in spec.layer_ids:
            ids_[name] = spec.layer_ids[user]
    graphics = tuple(
        dataclasses.replace(g, layer=names[g.layer]) if g.layer in names else g for g in spec.graphics
    )
    return dataclasses.replace(spec, layer_ids=ids_, graphics=graphics)


def project_file(document: str) -> bytes:
    """A project that lists the panel document alone: ``[Design]``, ``Version=1.0`` and ``[Document1]``."""
    lines = ["[Design]", "Version=1.0", "", "[Document1]", f"DocumentPath={document}"]
    return b"".join(line.encode("ascii") + b"\r\n" for line in lines)


def flat_files(
    panel: Panel,
    laid: PanelLayout,
    board_design: Design,
    *,
    pour: PourMode | None = None,
    pour_results: list[pcbdoc.PcbDocResult] | None = None,
) -> tuple[dict[str, bytes], list[Issue]]:
    """``<name>.PcbDoc`` and ``<name>.PrjPcb`` of the flattened panel, and the issues of the write (each
    item the Altium writer leaves out is reported as the conversion reports it). ``pour`` is the pour mode
    of the document (change c0215), as in ``lower.write_design``: ``None`` is ``computed``, written as
    ``outline`` with one ``altium.pour-unavailable`` warning without the ``geo`` extra; ``pour_results``,
    when given, receives the result of the write."""
    import fenolite.backends.altium.connectstyle as connectstyle
    from fenolite.backends.altium.pour import BackendUnavailable

    design, issues = panel_design(panel, laid, board_design)
    if any(i.severity == "error" for i in issues):
        return {}, issues
    found: list[Issue] = []
    inputs = lower.from_design(design, issues=found)
    assert inputs.pcb is not None
    spec = _named_layers(inputs.pcb)
    name = panel.name
    document = f"{name}.PcbDoc"
    try:
        written = pcbdoc.write_pcbdoc_result(spec, filename=document, pour=pour or "computed")
    except BackendUnavailable:
        if pour is not None:
            raise
        written = pcbdoc.write_pcbdoc_result(spec, filename=document, pour="outline")
        found.append(
            Issue(
                lower.POUR_UNAVAILABLE,
                "warning",
                lower.POUR_UNAVAILABLE_TEXT,
                where=document,
                hint="pip install 'fenolite[geo]'",
            )  # fmt: skip
        )
    if written.pour is not None:
        found += [*written.pour.issues(document), *written.issues, *connectstyle.pad_overrides(design.board)]
    if pour_results is not None:
        pour_results.append(written)
    files = {document: written.data, f"{name}.PrjPcb": project_file(document)}
    return files, [*issues, *found]


__all__ = [
    "FLATTENED",
    "ROUTE_LAYER",
    "VCUT_LAYER",
    "copy_board",
    "flat_files",
    "panel_design",
    "project_file",
]
