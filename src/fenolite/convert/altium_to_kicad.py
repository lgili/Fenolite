# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lowering imported Altium models for KiCad (c0161). No tools or output writes."""

from __future__ import annotations

import dataclasses
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, cast

from fenolite.backends.kicad import layers
from fenolite.convert.report import SCHEMATIC_REFUSED
from fenolite.convert.sources import SourceProject
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.base import ExtBag
from fenolite.model.board import FootprintInstance, Layer, Pad
from fenolite.model.circuit import Component, Net, PinRef
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef, ModelPlacement, SymbolDef
from fenolite.model.rules import Rule


class Ledger:
    def __init__(self) -> None:
        self.lost: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        self.changed: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    def drop(self, kind: str, ident: str, reason: str) -> None:
        self.lost[kind][reason].append(ident)

    def change(self, kind: str, ident: str, reason: str) -> None:
        for ids in self.changed[kind].values():
            if ident in ids:
                ids.remove(ident)
        self.changed[kind][reason].append(ident)


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


def keepouts(design: Design, ledger: Ledger) -> Design:
    """The drawings of the Keep-Out layer as rule areas on every copper layer (``_keepout_rings``): a filled
    shape one area, a keep-out track or arc the band of its width (change c0407). A drawing that covers no
    area, or of a kind without an outline, is an explicit loss. Each area forbids tracks, vias, pads and
    poured copper (change c0410): a Keep-Out layer keep-out applies on every copper layer (S-1710), and KiCad
    10.0.6 imports a keep-out track or region there with all four (``pcb-records.md``, "Regions and
    keep-outs")."""
    from fenolite.geometry.errors import GeometryError
    from fenolite.geometry.transform import Transform
    from fenolite.model.board import Keepout

    board = design.board
    assert board is not None
    collected: list[tuple[Any, str]] = [(g, "graphic") for g in board.graphics if g.layer == "Altium.KeepOut"]
    footprints: list[FootprintInstance] = []
    for fp in board.footprints:
        frame = Transform.placement(fp.position, fp.rotation)
        collected.extend(
            (dataclasses.replace(g, points=tuple(frame.apply(p) for p in g.points)), "footprint-graphic")
            for g in fp.graphics
            if g.layer == "Altium.KeepOut"
        )
        footprints.append(
            dataclasses.replace(fp, graphics=tuple(g for g in fp.graphics if g.layer != "Altium.KeepOut"))
        )
    areas = list(board.keepouts)
    copper = tuple(layer.name for layer in board.layers if layer.kind == "copper")
    for graphic, kind in collected:
        try:
            rings = _keepout_rings(graphic)
        except (GeometryError, ValueError, IndexError, TypeError):
            ledger.drop(kind, graphic.id, KEEPOUT_NO_AREA)
            continue
        if rings is None:
            ledger.drop(kind, graphic.id, KEEPOUT_NO_OUTLINE)
            continue
        for index, ring in enumerate(rings):
            areas.append(
                Keepout(
                    id=derived_id("kpo", "conversion", graphic.id if index == 0 else f"{graphic.id}:{index}"),
                    outline=ring,
                    layers=copper,
                    no_tracks=True,
                    no_vias=True,
                    no_pads=True,
                    no_copper_pour=True,
                )
            )
        filled = graphic.kind in ("polygon", "rect") and (graphic.filled or graphic.width <= 0)
        ledger.change(kind, graphic.id, KEEPOUT_AREA if filled else KEEPOUT_BAND)
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


def zone_outlines(source: SourceProject, design: Design, ledger: Ledger) -> Design:
    """Zones whose imported outline is empty (an Altium polygon with an arc vertex,
    ``altium.import.zone-arc``) get the flattened outline of the source document's polygon record; KiCad
    9.0.9 cannot report DRC on a zone without an outline. A zone whose record cannot be found or encloses
    no area is dropped."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.core.errors import FenoliteError
    from fenolite.core.io import sha256_bytes
    from fenolite.geometry.errors import GeometryError

    board = design.board
    assert board is not None
    if all(zone.outline for zone in board.zones):
        return design
    from fenolite.model.board import Zone

    documents: dict[str, Any] = {}
    zones: list[Zone] = []
    # a project may keep its board in a subfolder: the board document is found as for the rules (c0371)
    found = board_document(source, design)
    for zone in board.zones:
        if zone.outline:
            zones.append(zone)
            continue
        where = zone.provenance
        match = re.fullmatch(r"Polygons6/Data#(\d+)", where.locator if where else "")
        ring: tuple[Any, ...] = ()
        if where is not None and match:
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
            document = documents[where.file]
            index = int(match.group(1))
            if document is not None and index < len(document.polygons):
                try:
                    ring = _arc_ring(document.polygons[index].vertices)
                except (GeometryError, ValueError, IndexError, ZeroDivisionError):
                    ring = ()
        if len(ring) < 3:
            ledger.drop("zone", zone.id, ZONE_NO_OUTLINE)
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
    text = re.sub(r"[^\w. -]" if allow_space else r"[^\w.-]", "_", value).strip(". ") or "unnamed"
    if text.upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        text = "_" + text
    return text


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


def rule_records(source: SourceProject, design: Design) -> tuple[dict[str, str], ...]:
    """The rule records of the source's PCB document as key-value maps; none when it cannot be read."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.core.errors import FenoliteError

    path = board_document(source, design)
    if path is None:
        return ()
    try:
        document = read_pcbdoc(path.read_bytes(), file=path.name)
    except (OSError, FenoliteError):
        return ()
    return tuple({key: value or "" for key, value in record.fields} for record in document.rules)


def prepare(source: SourceProject, name: str, target: int, ledger: Ledger) -> Design:
    from fenolite.backends.kicad._fpmap import aligned_slot_pad
    from fenolite.convert import openings

    records = rule_records(source, source.design)
    expansions = openings.RuleExpansions(
        mask=openings.rule_expansion(records, openings.MASK_RULE),
        paste=openings.rule_expansion(records, openings.PASTE_RULE),
    )

    design = map_layers(
        keepouts(_clean(zone_outlines(source, source.design, ledger)), ledger), target, ledger
    )
    board = design.board
    assert board is not None
    refs = {component.id: component.ref for component in design.circuit.components}
    allocated: dict[str, str] = {}
    used: set[str] = set()
    footprints: list[FootprintInstance] = []
    links: dict[str, str] = {}
    for fp in sorted(board.footprints, key=lambda f: (refs.get(f.component_id, ""), f.id)):
        raw = fp.lib_ref or f"FREE_{fp.id}"
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
            opened, reasons = openings.open_pad(aligned, expansions)
            for reason in reasons:
                ledger.drop(openings.KIND, pad.id, reason)
            pads.append(opened)
        for body in fp.bodies:
            ledger.drop("body", body.id, "the imported body has no portable KiCad model file")
        footprints.append(dataclasses.replace(fp, lib_ref=link, pads=tuple(pads), bodies=()))
    for hole in board.holes:
        ledger.drop("hole", hole.id, "a standalone hole has no footprint")
    board = dataclasses.replace(board, footprints=tuple(footprints), holes=())
    from fenolite.convert import altium_zones  # change c0409: the pour settings of the Altium rules

    board = altium_zones.connect_zones(
        board, design, altium_zones.board_styles(source.design.board), refs, ledger
    )
    board = altium_zones.zone_clearances(board, design, ledger)
    from fenolite.convert import altium_strings  # change c0409, B10

    board = altium_strings.board_strings(board, ledger)
    rules = design.rules
    if rules is not None:
        from fenolite.backends.kicad.lowering import lower_rules
        from fenolite.core.errors import FenoliteError

        kept_rules: list[Rule] = []
        for rule in rules.rules:
            try:
                result = lower_rules(
                    dataclasses.replace(rules, rules=(rule,)), target=target, allow_lossy=True
                )
                if any(issue.severity in ("warning", "error") for issue in result.issues):
                    ledger.drop("rule", rule.id, "the target cannot write this imported rule")
                    continue
                kept_rules.append(rule)
            except (FenoliteError, ValueError) as error:
                ledger.drop("rule", rule.id, f"the target cannot write this imported rule: {error}")
        rules = dataclasses.replace(rules, rules=tuple(kept_rules))
    components = tuple(
        dataclasses.replace(c, lib_footprint_ref=links.get(c.id, c.lib_footprint_ref))
        for c in design.circuit.components
    )
    return dataclasses.replace(
        design,
        header=dataclasses.replace(design.header, name=name),
        board=board,
        rules=rules,
        circuit=dataclasses.replace(design.circuit, components=components),
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
    if len(set(references)) != len(references):
        ledger.drop("schematic", design.header.id, "the imported circuit has duplicate designators")
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
