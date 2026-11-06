# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lowering imported Altium models for KiCad (c0161). No tools or output writes."""

from __future__ import annotations

import dataclasses
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, cast

from fenolite.backends.kicad import layers
from fenolite.convert.report import SCHEMATIC_REFUSED
from fenolite.convert.sources import SourceProject
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.core.libnames import FREE_PAD_PREFIX, library_name
from fenolite.core.units import Nm
from fenolite.model.base import ExtBag
from fenolite.model.board import Board, FootprintInstance, Layer, Pad
from fenolite.model.circuit import Component, Net, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef, ModelPlacement, SymbolDef


class Ledger:
    def __init__(self) -> None:
        self.lost: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        self.changed: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        self.kept: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    def drop(self, kind: str, ident: str, reason: str) -> None:
        self.lost[kind][reason].append(ident)

    def keep(self, kind: str, ident: str, reason: str) -> None:
        """An item the target cannot hold, kept in the model for an Altium write (change c0424)."""
        self.kept[kind][reason].append(ident)

    def change(self, kind: str, ident: str, reason: str) -> None:
        """An entity is counted once per kind: a second change of ``ident`` joins its earlier reason, so
        neither fact is lost (an arc outline flattened and then a mixed pad connection, change c0409)."""
        for earlier, ids in self.changed[kind].items():
            if ident in ids:
                ids.remove(ident)
                if reason not in earlier.split("; "):
                    reason = f"{earlier}; {reason}"
                else:
                    reason = earlier
                break
        self.changed[kind][reason].append(ident)


DRILL_LAYERS = ("Altium.DrillGuide", "Altium.DrillDrawing")
"""The Altium layers of drill guides and drill drawings (``LAYERS`` 55 and 73), which a conversion writes on
KiCad user rows named so (change c0428)."""


def map_layers(design: Design, target: int, ledger: Ledger) -> Design:
    board = design.board
    if board is None:
        raise ValueError("Altium conversion requires a board")
    copper = sorted(
        (layer for layer in board.layers if layer.kind == "copper"), key=lambda layer: layer.ordinal
    )
    count = len(copper)
    count = max(2, count + count % 2)
    table = layers.board_rows(count)
    copper_names = [layer.name for layer in table if layer.kind == "copper"]
    mapping = {layer.name: layer.name for layer in table if layer.kind != "copper"}
    mapped_copper = (
        copper_names
        if len(copper) == count
        else copper_names[: len(copper)]
        if len(copper) < 2
        else [*copper_names[:-2], copper_names[-1]]
    )
    for old, new in zip(copper, mapped_copper, strict=True):
        mapping[old.name] = new
    if len(copper) != count:
        ledger.change(
            "stackup",
            board.stackup.id if board.stackup else board.id,
            "an empty inner copper layer makes the copper count even",
        )
    names = {layer.name for layer in board.layers} | set(layers.item_layer_counts(board))
    mechanical = sorted(
        (n for n in names if re.fullmatch(r"Mech\.\d+", n)), key=lambda n: int(n.split(".")[1])
    )
    # change c0428: the drill drawing and drill guide layers take user rows after the mechanical layers,
    # named as the import names them, as the mechanical layers are
    mechanical += [n for n in DRILL_LAYERS if n in names]
    user = layers.user_rows(min(45, len(mechanical)), target=target)
    extra: list[Layer] = []
    for source_name, row in zip(mechanical, user, strict=False):
        mapping[source_name] = row.name
        pairs = (*row.ext["kicad"].payload, ("user_name", source_name))
        extra.append(
            dataclasses.replace(row, ordinal=len(table) + len(extra), ext={"kicad": ExtBag(None, pairs)})
        )

    def mapped(items: tuple[Any, ...], kind: str) -> tuple[Any, ...]:
        result: list[Any] = []
        for item in items:
            actual = item.layers if hasattr(item, "layers") else (item.layer,)
            unknown = [n for n in actual if n not in mapping]
            if unknown:
                reason = (
                    "a layer outside the stack"
                    if any(n.startswith("Altium.") and n.split(".")[-1].isdigit() for n in unknown)
                    else "a layer without a KiCad row"
                )
                ledger.drop(kind, item.id, reason)
                continue
            values = (
                {"layers": tuple(mapping[n] for n in actual)}
                if hasattr(item, "layers")
                else {"layer": mapping[item.layer]}
            )
            result.append(dataclasses.replace(item, **values))
        return tuple(result)

    footprints: list[FootprintInstance] = []
    for fp in board.footprints:
        footprints.append(
            dataclasses.replace(
                fp,
                pads=mapped(fp.pads, "pad"),
                graphics=mapped(fp.graphics, "footprint-graphic"),
                texts=mapped(fp.texts, "footprint-text"),
                fields=mapped(fp.fields, "footprint-text"),
                keepouts=mapped(fp.keepouts, "keep-out"),
            )
        )
    board = dataclasses.replace(
        board,
        layers=(*table, *extra),
        footprints=tuple(footprints),
        tracks=mapped(board.tracks, "track"),
        arcs=mapped(board.arcs, "arc"),
        vias=mapped(board.vias, "via"),
        zones=mapped(board.zones, "zone"),
        keepouts=mapped(board.keepouts, "keep-out"),
        graphics=mapped(board.graphics, "graphic"),
        texts=mapped(board.texts, "text"),
        dimensions=mapped(board.dimensions, "dimension"),
        stackup=None if len(copper) != count else board.stackup,
    )
    assert not layers.undeclared_layers(board)
    return dataclasses.replace(design, board=board)


KEEPOUT_AREA = "a filled keep-out shape becomes a rule area"
KEEPOUT_BAND = (
    "a keep-out track becomes a rule area of the band its width covers (arc chord error at most 5000 nm)"
)
KEEPOUT_NO_AREA = "a keep-out line that covers no area"
KEEPOUT_NO_OUTLINE = "a keep-out drawing has no supported outline"


def _keepout_rings(graphic: Any) -> list[tuple[Any, ...]] | None:
    """The rings a drawing on the Keep-Out layer keeps out (change c0407): a filled polygon or rectangle (a
    region or a fill) and a closed outline of width 0 their outline; a line, an arc, a circle and each side of
    an outline drawn with a width the band that width covers, one ring per stroke, as KiCad 10.0.6 imports
    keep-out tracks (``pcb-records.md``, "Regions and keep-outs"). ``None`` for a drawing of another kind;
    ``GeometryError`` or ``ValueError`` when it covers no area."""
    from fenolite.core.coords import Point
    from fenolite.geometry.bands import arc_band, segment_band
    from fenolite.geometry.polygon import Polygon

    points = tuple(graphic.points)
    if graphic.kind == "rect" and len(points) == 2:
        a, b = points
        points = (a, Point(b.x, a.y), b, Point(a.x, b.y))
    if graphic.kind in ("polygon", "rect") and (graphic.filled or graphic.width <= 0):
        return [Polygon(points[:-1] if points[0] == points[-1] else points).outer]
    if graphic.kind in ("polygon", "rect"):
        ring = points[:-1] if points[0] == points[-1] else points
        return [segment_band(a, ring[(i + 1) % len(ring)], graphic.width) for i, a in enumerate(ring)]
    if graphic.kind == "line" and len(points) == 2:
        return [segment_band(points[0], points[1], graphic.width)]
    if graphic.kind == "arc" and len(points) == 3:
        return [arc_band(points[0], points[1], points[2], graphic.width)]
    if graphic.kind == "circle" and len(points) == 2:
        centre, edge = points
        dx, dy = edge.x - centre.x, edge.y - centre.y
        far = Point(centre.x - dx, centre.y - dy)
        return [
            arc_band(edge, Point(centre.x - dy, centre.y + dx), far, graphic.width),
            arc_band(far, Point(centre.x + dy, centre.y - dx), edge, graphic.width),
        ]
    return None


ALL_RESTRICTIONS = 0x1F
"""The restrictions of a drawing of the Keep-Out layer whose value is not known (change c0410): all."""
_KEEPOUT_RECORD = re.compile(r"(Tracks6|Arcs6|Fills6|Regions6)/Data#(\d+)")


def _restrictions(value: int) -> tuple[bool, bool, bool, bool]:
    """The restrictions of the rule areas a drawing of the Keep-Out layer gives, from the restrictions value
    of its keep-out record (S-1711, change c0420, N3): 1 vias, 2 tracks, 4 poured copper, 8 and 16 together
    pads (``pcb-records.md``, "Regions and keep-outs"). (vias, tracks, poured copper, pads)."""
    return bool(value & 0x01), bool(value & 0x02), bool(value & 0x04), value & 0x18 == 0x18


def keepout_restrictions(source: SourceProject, design: Design) -> dict[str, int]:
    """The restrictions value of each drawing of the Keep-Out layer (a board's or a footprint's) that is a
    keep-out, by graphic id, read from its record in the source document (change c0420, N2 and N3;
    ``adapter.copper.keepout_layer_restrictions``), as ``zone_outlines`` reads a polygon. A drawing whose
    record is not found, or that is no keep-out, has no entry."""
    from fenolite.backends.altium.adapter.copper import keepout_layer_restrictions

    board = design.board
    if board is None:
        return {}
    drawn = [g for g in board.graphics if g.layer == "Altium.KeepOut"]
    drawn += [g for fp in board.footprints for g in fp.graphics if g.layer == "Altium.KeepOut"]
    found = board_document(source, design)
    documents: dict[str, Any] = {}
    held: dict[str, int] = {}
    for graphic in drawn:
        where = graphic.provenance
        match = _KEEPOUT_RECORD.fullmatch(where.locator if where else "")
        document = _source_document(source, found, where, documents) if match else None
        if document is None or match is None:
            continue
        records = {"Tracks6": document.tracks, "Arcs6": document.arcs, "Fills6": document.fills}
        records["Regions6"] = document.regions
        items, index = records[match.group(1)], int(match.group(2))
        value = keepout_layer_restrictions(items[index]) if index < len(items) else None
        if value is not None:
            held[graphic.id] = value
    return held


def keepouts(design: Design, ledger: Ledger, restrictions: Mapping[str, int] | None = None) -> Design:
    """The drawings of the Keep-Out layer as rule areas on every copper layer (``_keepout_rings``): a filled
    shape one area, a keep-out track or arc the band of its width (change c0407). A drawing that covers no
    area, or of a kind without an outline, is an explicit loss. Each area forbids tracks, vias, pads and
    poured copper (change c0410): a Keep-Out layer keep-out applies on every copper layer (S-1710), and KiCad
    10.0.6 imports a keep-out track or region there with all four (``pcb-records.md``, "Regions and
    keep-outs"); a drawing whose id ``restrictions`` names (``keepout_restrictions``) forbids only what its
    keep-out record forbids (change c0420, N2 and N3). A drawing of a footprint gives a rule area of that
    footprint, in its pad frame (change c0411); a free drawing one of the board. A track, arc or circle
    without a keep-out record (one ``restrictions`` lacks) names each of its areas with its stroke
    (``keepout_lines.marker``), so the Altium writer gives it back as that stroke (change c0442)."""
    from fenolite.backends.altium import keepout_lines
    from fenolite.geometry.errors import GeometryError
    from fenolite.model.board import Keepout

    board = design.board
    assert board is not None
    copper = tuple(layer.name for layer in board.layers if layer.kind == "copper")

    def areas_of(graphic: Any, kind: str) -> list[Keepout]:
        value = (restrictions or {}).get(graphic.id, ALL_RESTRICTIONS)
        no_vias, no_tracks, no_copper_pour, no_pads = _restrictions(value)
        try:
            rings = _keepout_rings(graphic)
        except (GeometryError, ValueError, IndexError, TypeError):
            ledger.drop(kind, graphic.id, KEEPOUT_NO_AREA)
            return []
        if rings is None:
            ledger.drop(kind, graphic.id, KEEPOUT_NO_OUTLINE)
            return []
        filled = graphic.kind in ("polygon", "rect") and (graphic.filled or graphic.width <= 0)
        ledger.change(kind, graphic.id, KEEPOUT_AREA if filled else KEEPOUT_BAND)
        # a plain stroke (no keep-out record) carries itself in the name of its areas (change c0442)
        plain = restrictions is not None and graphic.id not in restrictions
        return [
            Keepout(
                id=derived_id("kpo", "conversion", graphic.id if index == 0 else f"{graphic.id}:{index}"),
                outline=ring,
                layers=copper,
                no_tracks=no_tracks,
                no_vias=no_vias,
                no_pads=no_pads,
                no_copper_pour=no_copper_pour,
                name=(keepout_lines.marker(graphic, index) or "") if plain else "",
            )
            for index, ring in enumerate(rings)
        ]

    areas = list(board.keepouts)
    for graphic in board.graphics:
        if graphic.layer == "Altium.KeepOut":
            areas.extend(areas_of(graphic, "graphic"))
    footprints: list[FootprintInstance] = []
    for fp in board.footprints:
        drawn = [g for g in fp.graphics if g.layer == "Altium.KeepOut"]
        if not drawn:
            footprints.append(fp)
            continue
        own = [area for g in drawn for area in areas_of(g, "footprint-graphic")]
        footprints.append(
            dataclasses.replace(
                fp,
                graphics=tuple(g for g in fp.graphics if g.layer != "Altium.KeepOut"),
                keepouts=(*fp.keepouts, *own),
            )
        )
    return dataclasses.replace(
        design,
        board=dataclasses.replace(
            board,
            footprints=tuple(footprints),
            graphics=tuple(g for g in board.graphics if g.layer != "Altium.KeepOut"),
            keepouts=tuple(areas),
        ),
    )


ZONE_ARC_REASON = "an outline with arc vertices is written as a polygon (arc chord error at most 5000 nm)"
ZONE_NO_OUTLINE = "a zone outline with arc vertices that the source document does not give"
ZONE_NO_AREA = (
    "not written: its polygon record outlines no area (its vertices coincide), so it pours no copper and "
    "the board made and checked is the same without it"
)
"""A zone whose polygon record is read but whose vertices enclose no area (change c0428): left out as a
``changed`` zone, not a loss, since nothing a board holds differs."""


def _arc_ring(vertices: Any) -> tuple[Any, ...]:
    """The closed outline of Altium polygon ``vertices`` (``KIND<k>``, ``VX<k>`` …), each arc vertex
    flattened at KiCad's default chord error. As for the board outline (``pcb-document.md``), vertex ``k``
    runs to vertex ``k + 1``; an arc vertex is the arc of centre ``CX``, ``CY``, radius ``R`` and angles
    ``SA`` to ``EA`` between them. ``GeometryError`` or ``ValueError`` when it encloses no area."""
    from fenolite.backends.altium.adapter import units
    from fenolite.core.coords import Point
    from fenolite.geometry.polygon import Polygon
    from fenolite.geometry.shapes import Arc

    corners = [Point(units.units_length(v.x)[0], -units.units_length(v.y)[0]) for v in vertices]
    points: list[Point] = []
    for k, vertex in enumerate(vertices):
        a, b = corners[k], corners[(k + 1) % len(corners)]
        if a == b:
            continue
        if vertex.kind == 0 or vertex.radius <= 0:
            points.append(a)
            continue
        start, _ = units.angle(vertex.start_angle)
        end, _ = units.angle(vertex.end_angle)
        _, mid, _ = units.arc_points(vertex.cx, vertex.cy, vertex.radius, start, end)
        points.extend(Arc(a, mid, b).polygonize()[:-1])
    return Polygon(tuple(points)).outer


def _source_document(source: SourceProject, found: Path | None, where: Any, documents: dict[str, Any]) -> Any:
    """The PCB document that ``where`` (a provenance) names, read once into ``documents`` by file name;
    ``None`` when it cannot be read or its SHA-256 differs from the one recorded. ``found`` is the board
    document of the project (``board_document``)."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.core.errors import FenoliteError
    from fenolite.core.io import sha256_bytes

    if where is None:
        return None
    path = (
        found
        if found is not None and found.name == where.file
        else source.path
        if source.path.suffix.lower() == ".pcbdoc"
        else source.root / where.file
    )
    if where.file not in documents:
        documents[where.file] = None
        try:
            data = path.read_bytes()
            if not where.file_sha256 or sha256_bytes(data) == where.file_sha256:
                documents[where.file] = read_pcbdoc(data, file=where.file)
        except (OSError, FenoliteError):
            pass
    return documents[where.file]


POLYGON_RECORD = re.compile(r"Polygons6/Data#(\d+)")


def polygon_outline(document: Any, locator: str) -> tuple[tuple[Any, ...], str]:
    """The flattened outline (``_arc_ring``) of the polygon record that ``locator`` names in ``document`` (a
    read PCB document), with an empty reason; or no outline and the reason: ``ZONE_NO_OUTLINE`` when the
    record is not there, ``ZONE_NO_AREA`` when it encloses no area (change c0428)."""
    from fenolite.geometry.errors import GeometryError

    match = POLYGON_RECORD.fullmatch(locator)
    if document is None or match is None or int(match.group(1)) >= len(document.polygons):
        return (), ZONE_NO_OUTLINE
    try:
        ring = _arc_ring(document.polygons[int(match.group(1))].vertices)
    except (GeometryError, ValueError, IndexError, ZeroDivisionError):
        return (), ZONE_NO_AREA
    return (ring, "") if len(ring) >= 3 else ((), ZONE_NO_AREA)


def polygon_ring(document: Any, locator: str) -> tuple[Any, ...]:
    """The outline of ``polygon_outline``; empty when the record is not there or encloses no area."""
    return polygon_outline(document, locator)[0]


def arc_outlines(
    design: Design, document: Any
) -> tuple[Design, tuple[str, ...], tuple[tuple[str, str], ...]]:
    """``design`` whose zones without an outline (an Altium polygon with an arc vertex,
    ``altium.import.zone-arc``) take the flattened outline of their record in ``document``, the PCB document
    they were read from; the ids of the zones outlined, and of those dropped, which no record outlines, each
    with its reason (``polygon_outline``). The
    copies of an Embedded Board Array take their outlines so from the referenced document before they are
    moved (change c0428)."""
    board = design.board
    if board is None or all(len(zone.outline) >= 3 for zone in board.zones):
        return design, (), ()
    zones: list[Any] = []
    outlined: list[str] = []
    dropped: list[tuple[str, str]] = []
    for zone in board.zones:
        if len(zone.outline) >= 3:
            zones.append(zone)
            continue
        ring, why = polygon_outline(document, zone.provenance.locator if zone.provenance else "")
        if not ring:
            dropped.append((zone.id, why))
            continue
        zones.append(dataclasses.replace(zone, outline=ring))
        outlined.append(zone.id)
    board = dataclasses.replace(board, zones=tuple(zones))
    return dataclasses.replace(design, board=board), tuple(outlined), tuple(dropped)


def zone_outlines(source: SourceProject, design: Design, ledger: Ledger) -> Design:
    """Zones whose imported outline is empty (an Altium polygon with an arc vertex,
    ``altium.import.zone-arc``) get the flattened outline of the source document's polygon record; KiCad
    9.0.9 cannot report DRC on a zone without an outline. A zone whose record cannot be found or encloses
    no area is dropped."""
    board = design.board
    assert board is not None
    if all(len(zone.outline) >= 3 for zone in board.zones):
        return design
    from fenolite.model.board import Zone

    documents: dict[str, Any] = {}
    zones: list[Zone] = []
    # a project may keep its board in a subfolder: the board document is found as for the rules (c0371)
    found = board_document(source, design)
    for zone in board.zones:
        if len(zone.outline) >= 3:  # change c0428: an outline of 1 or 2 points is no outline either
            zones.append(zone)
            continue
        where = zone.provenance
        ring: tuple[Any, ...] = ()
        why = ZONE_NO_OUTLINE
        if where is not None and POLYGON_RECORD.fullmatch(where.locator):
            ring, why = polygon_outline(_source_document(source, found, where, documents), where.locator)
        if not ring:
            (ledger.change if why == ZONE_NO_AREA else ledger.drop)("zone", zone.id, why)
            continue
        zones.append(dataclasses.replace(zone, outline=ring))
        ledger.change("zone", zone.id, ZONE_ARC_REASON)
    return dataclasses.replace(design, board=dataclasses.replace(board, zones=tuple(zones)))


def _clean(value: Any) -> Any:
    """A created target has no source-format slots or native ids."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        fields = {
            field.name: _clean(getattr(value, field.name))
            for field in dataclasses.fields(value)
            if field.init
        }
        empties: tuple[tuple[str, Any], ...] = (("ext", {}), ("native_ids", {}), ("provenance", None))
        for key, empty in empties:
            if key in fields:
                fields[key] = empty
        return dataclasses.replace(value, **fields)
    if isinstance(value, tuple):
        return tuple(_clean(item) for item in cast(tuple[Any, ...], value))
    return value


def _name(value: str, *, allow_space: bool = False) -> str:
    return library_name(value, allow_space=allow_space)  # shared with ``equivalent`` (change c0435)


def board_document(source: SourceProject, design: Design) -> Path | None:
    """The PCB document of an Altium source: the file read, or the board's file beside the project."""
    if source.path.suffix.lower() == ".pcbdoc":
        return source.path
    board = design.board
    where = board.provenance if board is not None else None
    if where is None or not where.file:
        return None
    path = source.root / where.file
    if path.is_file():
        return path
    # the provenance names the file alone; a project may keep it in a subfolder (``PCB/Board.PcbDoc``,
    # change c0371): take the PCB document of that name that the project lists and whose bytes the
    # provenance hashed
    from fenolite.backends.altium.read.project import load_project
    from fenolite.core.io import sha256_bytes

    if source.path.suffix.lower() != ".prjpcb":
        return None
    try:
        listed = load_project(source.path).documents
    except (OSError, ValueError):
        return None
    found = [
        item.file
        for item in listed
        if item.document.kind == "pcb"
        and item.present
        and item.file is not None
        and item.file.name == where.file
    ]
    if where.file_sha256:
        found = [
            candidate for candidate in found if sha256_bytes(candidate.read_bytes()) == where.file_sha256
        ]
    return found[0] if len(found) == 1 else None


def _pcb_document(source: SourceProject, design: Design) -> Any:
    """The source's PCB document as read; ``None`` when it cannot be read."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.core.errors import FenoliteError

    path = board_document(source, design)
    if path is None:
        return None
    try:
        return read_pcbdoc(path.read_bytes(), file=path.name)
    except (OSError, FenoliteError):
        return None


def rule_records(source: SourceProject, design: Design) -> tuple[dict[str, str], ...]:
    """The rule records of the source's PCB document as key-value maps; none when it cannot be read."""
    document = _pcb_document(source, design)
    if document is None:
        return ()
    return tuple({key: value or "" for key, value in record.fields} for record in document.rules)


VIA_MASK_CHANGED = (
    "KiCad opens every untented via by the board's one mask margin; this via's opening differs from the "
    "most frequent one, which the board takes (change c0445)"
)
VIA_RULE_SCOPED = (
    "the via takes its mask from the rules and a SolderMaskExpansion rule of another scope may govern it; "
    "the rule of scope IsVia or All was applied (change c0445)"
)
VIA_MASK_STATE, VIA_MASK_EXPANSION = 66, 54
"""The offsets of a via record's solder-mask cache state and top expansion (``pcb-copper.md``, "Via")."""


def via_margins(
    source: SourceProject, records: Sequence[Mapping[str, str]]
) -> tuple[dict[str, Nm], tuple[str, ...]]:
    """Via id → the growth of its mask opening beyond its copper (change c0445), for each via of the source
    that is untented on a side and whose record or rule gives one (``openings.via_margin``), and the ids of
    those that take the rule while a rule of another scope comes first (``ViaRule.scoped``). A via is found
    by the locator of its provenance in ``Vias6``."""
    import struct

    from fenolite.backends.altium.adapter.units import pcb_length
    from fenolite.backends.altium.read.pcbprims import ViaRecord
    from fenolite.convert import openings

    board = source.design.board
    document = _pcb_document(source, source.design)
    if board is None or document is None:
        return {}, ()
    rule = openings.via_rule(records)
    found: dict[str, Nm] = {}
    scoped: list[str] = []
    for via in board.vias:
        if via.protection.tenting_front and via.protection.tenting_back:
            continue
        locator = via.provenance.locator if via.provenance is not None else ""
        head, _, index = locator.partition("#")
        if head != "Vias6/Data" or not index.isdigit() or int(index) >= len(document.vias):
            continue
        record = document.vias[int(index)]
        if not isinstance(record, ViaRecord) or len(record.tail) <= VIA_MASK_STATE - 31:
            continue
        state = record.tail[VIA_MASK_STATE - 31]
        units = struct.unpack_from("<i", record.tail, VIA_MASK_EXPANSION - 31)[0]
        margin = openings.via_margin(via.diameter, via.drill, state, pcb_length(units), rule)
        if margin is not None:
            found[via.id] = margin
            if rule.scoped and state != openings.VIA_MODE_MANUAL:
                scoped.append(via.id)
    return found, tuple(scoped)


def _mode(margins: Mapping[str, Nm]) -> Nm:
    counts = Counter(margins.values())
    return min(counts, key=lambda value: (-counts[value], value))


def board_mask(board: Board, margins: Mapping[str, Nm], ledger: Ledger, scoped: Sequence[str] = ()) -> Board:
    """``board`` with the mask margin of its untented vias (change c0445): the most frequent of ``margins``
    (the smallest of a tie); each via with another one, and each of ``scoped`` (``via_margins``), is counted
    changed. With a margin other than 0, a pad without a margin of its own gets 0, so it keeps the opening
    it had."""
    if not margins:
        return board
    margin = _mode(margins)
    for ident, value in sorted(margins.items()):
        if value != margin:
            ledger.change("via", ident, VIA_MASK_CHANGED)
        elif ident in scoped:
            ledger.change("via", ident, VIA_RULE_SCOPED)
    if margin == 0:
        return dataclasses.replace(board, mask_margin=margin)

    def kept(pad: Pad) -> Pad:
        masked = any(name.endswith(".Mask") for name in pad.layers)
        return dataclasses.replace(pad, mask_margin=0) if masked and pad.mask_margin is None else pad

    footprints = tuple(
        dataclasses.replace(fp, pads=tuple(kept(pad) for pad in fp.pads)) for fp in board.footprints
    )
    return dataclasses.replace(board, footprints=footprints, mask_margin=margin)


def prepare(source: SourceProject, name: str, target: int, ledger: Ledger) -> Design:
    from fenolite.backends.kicad._fpmap import aligned_slot_pad
    from fenolite.convert import openings

    records = rule_records(source, source.design)
    # the pads' own mask and paste modes, read before ``_clean`` empties their bags (change c0440: every pad
    # took the rule's expansion, so a pad with a manual expansion came out with another opening)
    source_board = source.design.board
    own = {
        pad.id: openings.source_pairs(pad)
        for fp in (source_board.footprints if source_board is not None else ())
        for pad in fp.pads
    }
    expansions = openings.RuleExpansions(
        mask=openings.rule_expansion(records, openings.MASK_RULE),
        paste=openings.rule_expansion(records, openings.PASTE_RULE),
    )

    design = map_layers(
        keepouts(
            _clean(zone_outlines(source, source.design, ledger)),
            ledger,
            keepout_restrictions(source, source.design),
        ),
        target,
        ledger,
    )
    board = design.board
    assert board is not None
    refs = {component.id: component.ref for component in design.circuit.components}
    allocated: dict[str, str] = {}
    used: set[str] = set()
    footprints: list[FootprintInstance] = []
    links: dict[str, str] = {}
    source_links: dict[str, str] = {}  # change c0451: the source's link, carried as a KiCad property
    for fp in sorted(board.footprints, key=lambda f: (refs.get(f.component_id, ""), f.id)):
        if fp.lib_ref:
            source_links.setdefault(fp.component_id, fp.lib_ref)
        raw = fp.lib_ref or f"{FREE_PAD_PREFIX}{fp.id}"
        if raw not in allocated:
            candidate = _name(raw.rsplit(":", 1)[-1], allow_space=True)
            base = candidate
            index = 2
            while candidate.casefold() in used:
                candidate = f"{base}_{index}"
                index += 1
            allocated[raw] = candidate
            used.add(candidate.casefold())
        link = f"{name}:{allocated[raw]}"
        links[fp.component_id] = link
        if link != fp.lib_ref:
            ledger.change("footprint", fp.id, "the footprint links the derived project library")
        pads: list[Pad] = []
        for pad in fp.pads:
            try:
                aligned = aligned_slot_pad(pad)
            except ValueError:
                ledger.drop("pad", pad.id, "a slot turned against a pad of this shape")
                continue
            if aligned is not pad:
                ledger.change("pad", pad.id, "the circular pad rotates to its slot axis")
            opened, reasons = openings.open_pad(aligned, expansions, own.get(pad.id, {}))
            for reason in reasons:
                ledger.drop(openings.KIND, pad.id, reason)
            pads.append(opened)
        # change c0423: KiCad holds no body; ``convert.models`` writes each as a model file and reports it
        footprints.append(dataclasses.replace(fp, lib_ref=link, pads=tuple(pads), bodies=()))
    for hole in board.holes:
        ledger.drop("hole", hole.id, "a standalone hole has no footprint")
    board = dataclasses.replace(board, footprints=tuple(footprints), holes=())
    margins, scoped = via_margins(source, records)
    board = board_mask(board, margins, ledger, scoped)  # change c0445: the vias' mask
    from fenolite.convert import altium_zones  # change c0409: the pour settings of the Altium rules

    board = altium_zones.connect_zones(
        board, design, altium_zones.board_styles(source.design.board), refs, ledger
    )
    board = altium_zones.zone_clearances(board, design, ledger)
    from fenolite.convert import altium_strings  # change c0409, B10

    board = altium_strings.board_strings(board, ledger)
    rules = design.rules
    if rules is not None:
        from fenolite.convert import altium_rules  # change c0424: the fate of every rule

        rules = altium_rules.lower_rules(rules, target, ledger, source.design.rules)
    components = tuple(
        dataclasses.replace(c, lib_footprint_ref=links.get(c.id, c.lib_footprint_ref))
        for c in design.circuit.components
    )
    from fenolite.convert import altium_links  # change c0451: the source's links through KiCad

    return altium_links.carry(
        dataclasses.replace(
            design,
            header=dataclasses.replace(design.header, name=name),
            board=board,
            rules=rules,
            circuit=dataclasses.replace(design.circuit, components=components),
        ),
        source_links,
    )


HOLE_PREFIX = "Fenolite_Holes:"
"""The link of a generated hole footprint (``model.holes``; change c0170): it is not derived into the
project's library."""


def footprint_files(
    design: Design,
    text: str,
    name: str,
    target: int,
    ledger: Ledger,
    *,
    holes: Mapping[str, FootprintDef] | None = None,
    placements: Mapping[str, tuple[ModelPlacement, ...]] | None = None,
) -> dict[str, str]:
    """The derived footprint library ``<name>.pretty`` of the board's footprints and the ``fp-lib-table``
    that names it; with ``holes`` (change c0170) the table also names the library of the generated hole
    footprints, ``lib/Fenolite_Holes.pretty``, whose instances are not derived."""
    from fenolite.backends.kicad._fpmap import node
    from fenolite.backends.kicad.embed import local_footprint
    from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
    from fenolite.backends.kicad.mod import read_footprint, write_footprint
    from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
    from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind

    board = design.board
    assert board is not None
    definitions = parse(text).nodes("footprint")
    chosen: dict[str, str] = {}
    files: dict[str, str] = {}
    for fp, root in zip(board.footprints, definitions, strict=True):
        if fp.lib_ref.startswith(HOLE_PREFIX):
            continue
        flip_issues: list[Issue] = []
        local = local_footprint(root, fp.rotation, fp.side, flip_issues)
        if flip_issues:
            raise ValueError("the derived library cannot mirror this footprint")
        local = local.with_children(
            (
                local.children[0],
                node("version", Atom.integer(FORMAT_VERSIONS[FileKind.FOOTPRINT][target])),
                *local.children[1:],
            )
        )
        placed = (placements or {}).get(fp.id, ())
        if placed:  # the board's footprint holds the same models (change c0409); the placements write them
            models = [child for child in local.children if isinstance(child, Node) and child.name == "model"]
            local = local.with_children(child for child in local.children if child not in models)
        definition = read_footprint(dumps(local))
        pattern = fp.lib_ref.rsplit(":", 1)[-1]
        properties = {**definition.properties, "Reference": "REF**", "Value": pattern}
        definition = dataclasses.replace(
            definition,
            name=pattern,
            library=name,
            properties=properties,
            placements=placed,
        )
        written = write_footprint(definition, target=target, allow_lossy=True)
        # Reference/value positions are useful in the library; board-specific identifiers are not.
        signature = re.sub(r'\(uuid "[^"]*"\)', "", written)
        if pattern in chosen:
            if signature != chosen[pattern]:
                ledger.change("footprint", fp.id, "differs from the library footprint")
            continue
        chosen[pattern] = signature
        files[f"{name}.pretty/{pattern}.kicad_mod"] = written
    rows = [LibRow(name, "KiCad", f"${{KIPRJMOD}}/{name}.pretty")]
    if holes:
        library = HOLE_PREFIX.removesuffix(":")
        rows.append(LibRow(library, "KiCad", f"${{KIPRJMOD}}/lib/{library}.pretty"))
    files["fp-lib-table"] = write_lib_table(LibTable("footprint", tuple(rows)), target=target)
    return files


@dataclasses.dataclass(frozen=True)
class Part:
    component: Component
    path: str
    symbol: SymbolDef
    footprint: FootprintDef
    parents: tuple[SymbolDef, ...] = ()
    symbol_origin: str = "project"


DUPLICATE_DESIGNATORS = (
    "a designator that several imported parts share is kept by each part on the board and written "
    "<designator>_<n> for each other part (change c0428)"
)

DUPLICATE_PLACED = (
    "several parts on the board share a designator: the generated schematic needs distinct ones, and "
    "renaming them would change the board"
)


def distinct_designators(design: Design, ledger: Ledger) -> Design:
    """``design`` with distinct designators, as a schematic needs (change c0428). Where several components
    share one, each that has a footprint on the board keeps it (or the first, when none has), and each other
    takes ``<designator>_<n>``, ``n`` counting from 2 past the designators in use; its path too when it was
    the designator. The board keeps every footprint's designator, so the written board does not change; the
    schematic and the design that the conversion verifies take the new ones. A ``schematic`` change names
    the rule."""
    groups: dict[str, list[int]] = {}
    components = design.circuit.components
    for index, component in enumerate(components):
        if component.ref:
            groups.setdefault(component.ref, []).append(index)
    if all(len(found) == 1 for found in groups.values()):
        return design
    placed: set[str] = (
        {fp.component_id for fp in design.board.footprints} if design.board is not None else set()
    )
    used = set(groups)
    renamed = list(components)
    for ref, found in groups.items():
        if len(found) == 1:
            continue
        keepers = {i for i in found if components[i].id in placed} or {found[0]}
        n = 2
        for index in found:
            if index in keepers:
                continue
            while f"{ref}_{n}" in used:
                n += 1
            name = f"{ref}_{n}"
            used.add(name)
            component = components[index]
            renamed[index] = dataclasses.replace(
                component, ref=name, path=name if component.path == ref else component.path
            )
    if renamed == list(components):
        return design
    ledger.change("schematic", design.header.id, DUPLICATE_DESIGNATORS)
    return dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=tuple(renamed)))


PAGE_ROUNDS = 7
"""How many times a refused page of a generated schematic is split again (1, 2, 4, … 64 pages)."""


def _source_sheets(parts: list[Part], source: Design) -> list[Part]:
    """``parts`` with each part of a flat circuit on the sheet of its source schematic document, when the
    parts come from several documents: the generator gives each sheet a KiCad sheet of its own. A circuit
    with modules keeps its paths, and a part from no schematic document stays on the root (change c0372).
    The documents are those of the ``source`` design's components: the lowered design holds no provenance."""
    if any("/" in part.path for part in parts):
        return parts
    of = {
        component.id: component.provenance.file
        for component in source.circuit.components
        if component.provenance is not None and component.provenance.file.lower().endswith(".schdoc")
    }
    files = {part.component.id: of[part.component.id] for part in parts if part.component.id in of}
    if len(set(files.values())) < 2:
        return parts
    names: dict[str, str] = {}
    for file in sorted(set(files.values()), key=str.casefold):
        stem = _sheet_name(PurePosixPath(file.replace("\\", "/")).stem)
        name, n = stem, 1
        while name.casefold() in {taken.casefold() for taken in names.values()}:
            n += 1
            name = f"{stem}-{n}"
        names[file] = name
    return [
        dataclasses.replace(part, path=f"{names[files[part.component.id]]}/{part.path}")
        if part.component.id in files
        else part
        for part in parts
    ]


def _sheet_name(stem: str) -> str:
    """A sheet name from a document stem: a ``/`` or ``.`` would split or join module paths."""
    return re.sub(r"[/.]", "_", stem).strip() or "sheet"


def _pages(parts: list[Part], pages: Mapping[str, int]) -> tuple[list[Part], dict[str, str]]:
    """``parts`` with the parts of each module that ``pages`` splits spread, in the natural order of their
    paths, over that many sibling modules ``<module>-<n>`` (``page-<n>`` for the root); and the module of
    each page → the module it splits."""
    from fenolite.backends.kicad.schlayout import natural_key

    by_module: dict[str, list[Part]] = defaultdict(list)
    for part in parts:
        by_module[part.path.rpartition("/")[0]].append(part)
    out: list[Part] = []
    split: dict[str, str] = {}
    for module, members in by_module.items():
        count = pages.get(module, 1)
        if count <= 1:
            out += members
            split[module] = module
            continue
        members = sorted(members, key=lambda part: natural_key(part.path))
        parent, _, leaf = module.rpartition("/")
        for n in range(count):
            page = f"{leaf}-{n + 1}" if module else f"page-{n + 1}"
            page = f"{parent}/{page}" if parent else page
            split[page] = module
            chunk = members[n * len(members) // count : (n + 1) * len(members) // count]
            out += [
                dataclasses.replace(part, path=f"{page}/{part.path.rpartition('/')[2]}") for part in chunk
            ]
    return out, split


def _paged_schematic(design: Design, parts: list[Part], name: str, target: int, generate: Any) -> Any:
    """The generated schematic of ``parts``; a sheet that no page size fits is split into pages, twice as
    many each round, until every page fits, a page holds one part, or ``PAGE_ROUNDS`` ends (change c0372)."""
    sizes: dict[str, int] = defaultdict(int)
    for part in parts:
        sizes[part.path.rpartition("/")[0]] += 1
    pages: dict[str, int] = {}
    generated = None
    for _ in range(PAGE_ROUNDS):
        laid, split = _pages(parts, pages)
        generated = generate(design, laid, name=name, target=target, layout="readable", allow_lossy=True)
        errors = [issue for issue in generated.issues if issue.severity == "error"]
        refused = {
            split.get("" if issue.where == name else issue.where)
            for issue in errors
            if issue.code == "build.schematic-too-large"
        }
        if (
            not errors
            or any(issue.code != "build.schematic-too-large" for issue in errors)
            or None in refused
        ):
            break
        grow = {module for module in refused if module is not None and pages.get(module, 1) < sizes[module]}
        if not grow:
            break
        for module in grow:
            pages[module] = min(2 * pages.get(module, 1), sizes[module])
    return generated


def schematic_files(
    source: SourceProject, design: Design, name: str, target: int, ledger: Ledger
) -> tuple[dict[str, str], tuple[Issue, ...]]:
    import hashlib

    from fenolite.backends.altium.adapter.library import import_symbols
    from fenolite.backends.altium.read.schlib import read_schlib
    from fenolite.backends.kicad import sch, symembed
    from fenolite.backends.kicad.libs import LibTable, write_lib_table
    from fenolite.backends.kicad.schgen import generate_schematic
    from fenolite.core.coords import Point
    from fenolite.model.library import FootprintDef, SymbolDef, SymbolGraphic, SymbolPin

    known: dict[tuple[str, str], SymbolDef] = {}
    for path in source.files.values():
        if path.suffix.lower() != ".schlib" or not path.is_file():
            continue
        data = path.read_bytes()
        library = import_symbols(
            read_schlib(data), name=path.stem, file=path.name, sha256=hashlib.sha256(data).hexdigest()
        )
        for definition in library.symbols:
            known[(path.name.casefold(), definition.name)] = definition
    parts: list[Part] = []
    for index, component in enumerate(design.circuit.components):
        if not component.ref:
            continue
        file, _, symbol = component.lib_symbol_ref.rpartition(":")
        definition = known.get((file.casefold(), symbol))
        symbol_name = f"SYM_{_name(component.ref)}_{index}"
        if definition is None:
            pins = tuple(
                SymbolPin(
                    number=pin.number,
                    name=pin.name,
                    etype=pin.etype,
                    position=Point(-2540000, n * 2540000),
                    length=2540000,
                    unit=1,
                    body_style=1,
                )
                for n, pin in enumerate(component.pins)
            )
            definition = SymbolDef(
                id=derived_id("sym", "conversion", component.id),
                name=symbol_name,
                library=name,
                properties={"Reference": "U", "Value": component.value},
                pins=pins,
                graphics=(
                    SymbolGraphic(
                        kind="rect",
                        points=(Point(0, -1270000), Point(5080000, max(1270000, len(pins) * 2540000))),
                        width=254000,
                    ),
                ),
            )
        definition = dataclasses.replace(definition, name=symbol_name, library=name)
        footprint = FootprintDef(
            id=derived_id("fpd", "conversion", component.id),
            name=component.lib_footprint_ref.rsplit(":", 1)[-1],
            library=name,
        )
        parts.append(Part(component, component.path or component.ref, definition, footprint))
    references = [part.component.ref for part in parts]
    if len(set(references)) != len(references):  # several parts on the board share one (change c0428)
        ledger.drop("schematic", design.header.id, DUPLICATE_PLACED)
        return {}, ()
    winners = {member: net.id for net in design.circuit.nets for member in net.members}
    nets: list[Net] = []
    for net in design.circuit.nets:
        members = tuple(member for member in net.members if winners[member] == net.id)
        for member in net.members:
            if winners[member] != net.id:
                ident = f"{member.component_id}:{member.pin}"
                # A report counts affected pins once, even with several aliases.
                if not any(ident in ids for ids in ledger.lost["pin-net"].values()):
                    ledger.drop(
                        "pin-net",
                        ident,
                        "the schematic retains the last imported net of a multiply assigned pin",
                    )
        nets.append(dataclasses.replace(net, members=members))
    connected = {member for net in nets for member in net.members}
    flags = set(design.circuit.no_connects)
    flags.update(
        PinRef(part.component.id, pin.number)
        for part in parts
        for pin in part.symbol.pins
        if PinRef(part.component.id, pin.number) not in connected
    )
    design = dataclasses.replace(
        design,
        circuit=dataclasses.replace(
            design.circuit,
            nets=tuple(nets),
            no_connects=tuple(sorted(flags, key=lambda member: (member.component_id, member.pin))),
        ),
    )
    generated = _paged_schematic(
        design, _source_sheets(parts, source.design), name, target, generate_schematic
    )
    if any(issue.severity == "error" for issue in generated.issues):
        # a declared loss that needs --allow-lossy, not an error finding that blocks the board (change c0372)
        ledger.drop("schematic", design.header.id, SCHEMATIC_REFUSED)
        return {}, tuple(issue for issue in generated.issues if issue.severity != "error")
    files = {f"{name}.kicad_sch": sch.write_schematic(generated.sheet, target=target, allow_lossy=True).text}
    for file, sheet in generated.children.items():
        files[file] = sch.write_schematic(sheet, target=target, allow_lossy=True).text
    for nickname, definitions in generated.libraries.items():
        files[f"lib/{nickname}.kicad_sym"] = symembed.write_symbol_library(definitions, target=target)
    files["sym-lib-table"] = write_lib_table(LibTable("symbol", generated.rows), target=target)
    ledger.change("schematic", design.header.id, "positions and wires are regenerated from the circuit")
    return files, generated.issues
