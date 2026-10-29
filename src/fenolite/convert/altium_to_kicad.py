# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lowering imported Altium models for KiCad (c0161). No tools or output writes."""

from __future__ import annotations

import dataclasses
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from fenolite.backends.kicad import layers
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


def keepouts(design: Design, ledger: Ledger) -> Design:
    """Closed connected Keep-Out outlines become rule areas; open/branching outlines are explicit losses."""
    from fenolite.geometry.errors import GeometryError
    from fenolite.geometry.polygon import Polygon, assemble_rings
    from fenolite.geometry.shapes import Arc, Segment
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
    pending: list[tuple[Arc | Segment, Any, str]] = []
    for graphic, kind in collected:
        if graphic.kind in ("polygon", "rect"):
            points = graphic.points
            if graphic.kind == "rect" and len(points) == 2:
                a, b = points
                from fenolite.core.coords import Point

                points = (a, Point(b.x, a.y), b, Point(a.x, b.y))
            try:
                points = Polygon(points[:-1] if points[0] == points[-1] else points).outer
            except (GeometryError, IndexError):
                ledger.drop(kind, graphic.id, "a keep-out line that encloses no area")
                continue
            areas.append(
                Keepout(
                    id=derived_id("kpo", "conversion", graphic.id),
                    outline=points,
                    layers=copper,
                    no_tracks=True,
                    no_vias=True,
                    no_copper_pour=True,
                )
            )
            ledger.change(kind, graphic.id, "a closed keep-out outline becomes a rule area")
        elif graphic.kind in ("line", "arc") and len(graphic.points) in (2, 3):
            try:
                piece = Segment(*graphic.points) if graphic.kind == "line" else Arc(*graphic.points)
                pending.append((piece, graphic, kind))
            except (GeometryError, TypeError):
                ledger.drop(kind, graphic.id, "a keep-out line that encloses no area")
        else:
            ledger.drop(kind, graphic.id, "a keep-out drawing has no supported outline")
    # Partition disconnected contours so one dangling segment never discards a separate closed ring.
    while pending:
        group = [pending.pop(0)]
        ends = {group[0][0].start, group[0][0].end}
        changed = True
        while changed:
            changed = False
            for item in pending[:]:
                if {item[0].start, item[0].end} & ends:
                    pending.remove(item)
                    group.append(item)
                    ends.update((item[0].start, item[0].end))
                    changed = True
        try:
            rings = assemble_rings(item[0] for item in group)
            for ring in rings:
                areas.append(
                    Keepout(
                        id=derived_id("kpo", "conversion", group[0][1].id + str(len(areas))),
                        outline=ring.polygonize(),
                        layers=copper,
                        no_tracks=True,
                        no_vias=True,
                        no_copper_pour=True,
                    )
                )
            for _, graphic, kind in group:
                ledger.change(
                    kind,
                    graphic.id,
                    "a closed keep-out outline becomes a rule area (arc chord error at most 5000 nm)",
                )
        except GeometryError:
            for _, graphic, kind in group:
                ledger.drop(kind, graphic.id, "a keep-out line that encloses no area")
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
    for zone in board.zones:
        if zone.outline:
            zones.append(zone)
            continue
        where = zone.provenance
        match = re.fullmatch(r"Polygons6/Data#(\d+)", where.locator if where else "")
        ring: tuple[Any, ...] = ()
        if where is not None and match:
            path = source.path if source.path.suffix.lower() == ".pcbdoc" else source.root / where.file
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


def _name(value: str) -> str:
    text = re.sub(r"[^\w.-]", "_", value).strip(". ") or "unnamed"
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
    return path if path.is_file() else None


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
            candidate = _name(raw.rsplit(":", 1)[-1])
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
    from fenolite.backends.kicad.sexpr import Atom, dumps, parse
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
        definition = read_footprint(dumps(local))
        pattern = fp.lib_ref.rsplit(":", 1)[-1]
        properties = {**definition.properties, "Reference": "REF**", "Value": pattern}
        definition = dataclasses.replace(
            definition,
            name=pattern,
            library=name,
            properties=properties,
            placements=(placements or {}).get(fp.id, ()),
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
    generated = generate_schematic(
        design, parts, name=name, target=target, layout="readable", allow_lossy=True
    )
    if any(issue.severity == "error" for issue in generated.issues):
        ledger.drop("schematic", design.header.id, "the schematic generator refused the imported circuit")
        return {}, generated.issues
    files = {f"{name}.kicad_sch": sch.write_schematic(generated.sheet, target=target, allow_lossy=True).text}
    for file, sheet in generated.children.items():
        files[file] = sch.write_schematic(sheet, target=target, allow_lossy=True).text
    for nickname, definitions in generated.libraries.items():
        files[f"lib/{nickname}.kicad_sym"] = symembed.write_symbol_library(definitions, target=target)
    files["sym-lib-table"] = write_lib_table(LibTable("symbol", generated.rows), target=target)
    ledger.change("schematic", design.header.id, "positions and wires are regenerated from the circuit")
    return files, generated.issues
