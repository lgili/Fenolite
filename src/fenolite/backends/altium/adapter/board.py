# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A PCB document as a design (capability altium-import; ``docs/formats/altium/import.md``; change c0043).

``import_board`` maps the records of ``read.pcb.PcbDocument`` into a ``Design``: layers and stack-up, nets
and net classes, one footprint per component with its pads in the footprint frame, free copper, zones,
graphics, texts, the outline as ``Edge.Cuts`` graphics, the rules that map, and a circuit synthesised from
the pads. It parses no byte and opens no file.
"""

# evidence: see import_evidence

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import PureWindowsPath

from fenolite import __version__
from fenolite.backends.altium.adapter import copper, units
from fenolite.backends.altium.adapter.bodies import component_body
from fenolite.backends.altium.adapter.codes import Census, issue
from fenolite.backends.altium.adapter.context import Context
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import Exact, Ids, bag
from fenolite.backends.altium.adapter.layers import LayerMap, stackup
from fenolite.backends.altium.adapter.pads import pad
from fenolite.backends.altium.adapter.rules import import_rules
from fenolite.backends.altium.read.bodies import BodyRecord, read_bodies
from fenolite.backends.altium.read.pcb import ComponentRecord, PcbDocument
from fenolite.backends.altium.read.pcbprims import PadRecord, RawPrimitive, TextRecord
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.geometry.transform import Transform
from fenolite.model.board import Board, ComponentBody, FootprintAttribute, FootprintInstance, Pad
from fenolite.model.circuit import Circuit, Component, Net, NetClass, Pin, PinRef
from fenolite.model.design import SCHEMA_VERSION, Design, DesignHeader
from fenolite.model.rules import RuleSet

KIND = "altium_pcbdoc"
NET_CLASS_KIND = 0
BODY_STORAGE = "ComponentBodies6"
DECODED_STORAGES = (BODY_STORAGE,)
"""Storages of ``PcbDocument.storages`` that the adapter decodes; every other one that is not empty is
named in ``altium.import.unmapped``."""


@dataclass
class BoardImport:
    """The parts of one imported PCB document, before they are put into a design. ``links`` holds, per
    footprint id, the component record it came from (``None`` for a free pad)."""

    board: Board
    nets: list[Net]
    netclasses: list[NetClass]
    components: list[Component]
    rules: RuleSet
    links: dict[str, ComponentRecord | None] = field(default_factory=lambda: {})
    issues: list[Issue] = field(default_factory=lambda: [])
    census: Census = field(default_factory=Census)


def stem(path: str | None) -> str:
    """The file stem of a library path as an Altium record writes it (``\\`` or ``/`` between folders)."""
    return PureWindowsPath(path).stem if path else ""


def _lib_ref(library: str | None, name: str | None) -> str:
    left = stem(library)
    return f"{left}:{name}" if left and name else (name or "")


def _nets(doc: PcbDocument, ctx: Context) -> dict[str, tuple[str, dict[str, str], str]]:
    """Net name → (id, native ids, locator), and the index tables of ``ctx``. Two records of one name are
    one net, with one warning."""
    found: dict[str, tuple[str, dict[str, str], str]] = {}
    for index, record in enumerate(doc.nets):
        name = record.name
        if name is None:
            ctx.census.skip("nets", "nets")
            continue
        if name in found:
            ctx.issues.append(
                issue("altium.import.duplicate-net", "two net records hold one name; they are one net", name)
            )
            ctx.census.skip("nets", "duplicate-nets")
        else:
            ident, native = ctx.ids.native("net", f"net:{name}")
            found[name] = (ident, native, f"Nets6/Data#{index}")
            ctx.census.map("nets")
        ctx.net_ids[index] = found[name][0]
        ctx.net_names[index] = name
    return found


def _classes(
    doc: PcbDocument, ctx: Context, nets: Mapping[str, object]
) -> tuple[list[NetClass], dict[str, list[str]]]:
    """The net classes, and per net name the names of the classes that list it, sorted."""
    classes: list[NetClass] = []
    membership: dict[str, list[str]] = {}
    seen: set[str] = set()
    for index, record in enumerate(doc.classes):
        if record.kind != NET_CLASS_KIND or record.superclass or not record.name or record.name in seen:
            ctx.census.skip("classes", "classes")
            continue
        seen.add(record.name)
        ident, native = ctx.ids.native("cls", f"class:{record.name}")
        locator = f"Classes6/Data#{index}"
        classes.append(
            NetClass(id=ident, native_ids=native, provenance=ctx.provenance(locator), name=record.name)
        )
        ctx.census.map("classes")
        for member in record.members:
            if member in nets:
                membership.setdefault(member, []).append(record.name)
            else:
                ctx.issues.append(
                    issue("altium.import.unknown-member", "a net class lists a name that is no net", locator)
                )
    return classes, {name: sorted(set(found)) for name, found in membership.items()}


def _position(record: ComponentRecord, exact: Exact) -> Point | None:
    if record.x is None or record.y is None:
        return None
    x, x_exact = units.units_length(record.x)
    y, y_exact = units.units_length(record.y)
    if not x_exact:
        exact.inexact("position.x", str(record.x))
    if not y_exact:
        exact.inexact("position.y", str(record.y))
    return Point(x, -y)


def _texts_of(doc: PcbDocument) -> dict[int, tuple[str, str]]:
    """Component index → its designator text and its comment text (``""`` without one)."""
    found: dict[int, tuple[str, str]] = {}
    for item in doc.texts:
        if not isinstance(item, TextRecord) or item.prefix.component is None:
            continue
        designator, comment = found.get(item.prefix.component, ("", ""))
        if item.is_designator and not designator:
            designator = item.text
        elif item.is_comment and not comment:
            comment = item.text
        found[item.prefix.component] = (designator, comment)
    return found


def _bodies(doc: PcbDocument, ctx: Context) -> dict[int, list[tuple[int, BodyRecord]]]:
    """Component index → its body records with their stream index, from ``ComponentBodies6``."""
    data = doc.storages.get(BODY_STORAGE, {}).get("Data")
    found: dict[int, list[tuple[int, BodyRecord]]] = {}
    if not data:
        return found
    for record in read_bodies(data, storage=BODY_STORAGE, issues=ctx.issues):
        if not record.framed:
            ctx.census.skip("bodies", "raw-primitives")
        elif record.component is None or record.component >= len(doc.components):
            ctx.census.skip("bodies", "bodies")
        else:
            found.setdefault(record.component, []).append((record.index, record))
    return found


def read_board(doc: PcbDocument, *, file: str, sha256: str, ids: Ids) -> BoardImport:
    """Map ``doc`` into its parts with the ids of ``ids`` (``import_board`` and ``import_project`` share
    this function)."""
    layers = LayerMap.from_board(doc.board)
    ctx = Context(ids=ids, layers=layers, file=file, sha256=sha256)
    ctx.issues.extend(layers.issues)
    layers.issues = ctx.issues
    nets = _nets(doc, ctx)
    classes, membership = _classes(doc, ctx, nets)
    class_ids = {c.name: c.id for c in classes}
    texts = _texts_of(doc)
    bodies = _bodies(doc, ctx)
    owned = copper.owned_primitives(doc)
    placed: set[int] = set()
    """The component indexes that became a footprint: their primitives are its items (change c0126)."""

    pads_of: dict[int, list[tuple[int, PadRecord]]] = {}
    free_pads: list[tuple[int, PadRecord]] = []
    for index, item in enumerate(doc.pads):
        if isinstance(item, RawPrimitive):
            ctx.census.skip("pads", "raw-primitives")
            continue
        owner = item.prefix.component
        if owner is None or owner >= len(doc.components):
            free_pads.append((index, item))
        else:
            pads_of.setdefault(owner, []).append((index, item))

    footprints: list[FootprintInstance] = []
    components: list[Component] = []
    members: dict[str, list[PinRef]] = {name: [] for name in nets}
    links: dict[str, ComponentRecord | None] = {}

    def add_pins(component_id: str, native: str, pads: tuple[Pad, ...], locator: str) -> tuple[Pin, ...]:
        pins: list[Pin] = []
        seen: set[str] = set()
        net_names = {ident: name for name, (ident, _n, _l) in nets.items()}
        for item in pads:
            if not item.number:
                continue
            if item.number not in seen:
                seen.add(item.number)
                ident, native_ids = ctx.ids.native("pin", f"{native}:pin:{item.number}")
                pins.append(
                    Pin(
                        id=ident,
                        native_ids=native_ids,
                        provenance=ctx.provenance(locator),
                        number=item.number,
                        name="",
                        etype="unspecified",
                    )  # fmt: skip
                )
            if item.net_id is not None:
                ref = PinRef(component_id, item.number)
                listed = members[net_names[item.net_id]]
                if ref not in listed:
                    listed.append(ref)
        return tuple(pins)

    def make_pads(
        items: list[tuple[int, PadRecord]], fp_native: str, frame: Transform | None, rotation: int
    ) -> tuple[Pad, ...]:
        counts: dict[str, int] = {}
        made: list[Pad] = []
        for index, record in items:
            unique = doc.pad_unique_ids.get(index)
            k = counts.get(record.name, 0)
            counts[record.name] = k + 1
            native = f"pad:{unique}" if unique else f"{fp_native}:pad:{record.name}:{k}"
            made.append(
                pad(
                    record,
                    ctx,
                    locator=f"Pads6/Data#{index}",
                    native=native,
                    frame=frame,
                    footprint_rotation=rotation,
                    net_id=ctx.net(record.prefix.net),
                )  # fmt: skip
            )
            ctx.census.map("pads")
        return tuple(made)

    for index, record in enumerate(doc.components):
        locator = f"Components6/Data#{index}"
        exact = Exact(ctx.census)
        position = _position(record, exact)
        if position is None:
            ctx.issues.append(
                issue("altium.import.bad-length", "the component has no readable position", locator)
            )
            ctx.census.skip("components", "components")
            ctx.census.skip("pads", "footprint-graphics", len(pads_of.get(index, [])))
            continue
        rotation = exact.angle("rotation", record.rotation or 0.0)
        side = "bottom" if (record.layer or "").upper() == "BOTTOM" else "top"
        fp_native = f"fp:{record.unique_id}" if record.unique_id else ""
        if fp_native:
            fp_id, fp_native_ids = ctx.ids.native("fp", fp_native)
        else:
            fp_native = f"fp:#{index}"
            fp_id = ctx.ids.content(
                "fp", "footprints", [position.x, position.y], rotation, side, record.pattern or "", index
            )
            fp_native_ids = {}
        frame = Transform.placement(position, rotation).inverse()
        pads = make_pads(pads_of.get(index, []), fp_native, frame, rotation)
        attributes: tuple[FootprintAttribute, ...] = ()
        if any(p.drill is not None for p in pads):
            attributes = ("through_hole",)
        elif pads:
            attributes = ("smd",)
        made_bodies: list[ComponentBody] = []
        for body_index, body in bodies.get(index, []):
            found = component_body(
                body, frame, ctx, locator=f"{BODY_STORAGE}/Data#{body_index}", section="bodies"
            )
            if found is None:
                ctx.census.skip("bodies", "bodies")
            else:
                made_bodies.append(found)
                ctx.census.map("bodies")
        items = copper.footprint_items(
            owned.get(index, copper.Owned()),
            ctx,
            frame,
            rotation,
            native=fp_native,
            name_on=record.name_on is not False,
            comment_on=record.comment_on is not False,
        )
        placed.add(index)
        designator, comment = texts.get(index, ("", ""))
        # The reference is the designator the board shows. The source designator names the schematic
        # component: the instances of a repeated sheet share it, and a designator changed on the board
        # alone leaves it behind (pcb-read.md, ``H-A-RD-PCB-TEXT-2``).
        ref = designator or record.source_designator or ""
        if record.source_unique_id:
            cmp_native = f"cmp:{record.source_unique_id}"
        elif record.unique_id:
            cmp_native = f"cmp:fp:{record.unique_id}"
        else:
            cmp_native = f"cmp:fp:#{index}"
        cmp_id, cmp_native_ids = ctx.ids.native("cmp", cmp_native)
        lib_ref = _lib_ref(record.source_footprint_library, record.pattern)
        pairs = exact.pairs()
        if record.source_designator:
            pairs.append(("source_designator", record.source_designator))
        if record.source_lib_reference:
            pairs.append(("source_lib_reference", record.source_lib_reference))
        footprints.append(
            FootprintInstance(
                id=fp_id,
                native_ids=fp_native_ids,
                provenance=ctx.provenance(locator),
                ext=bag(pairs),
                component_id=cmp_id,
                lib_ref=lib_ref,
                position=position,
                rotation=rotation,
                side=side,
                locked=bool(record.locked),
                attributes=attributes,
                pads=pads,
                fields=items.fields,
                bodies=tuple(made_bodies),
                graphics=items.graphics,
                texts=items.texts,
            )
        )
        links[fp_id] = record
        symbol = ""
        if record.source_component_library and record.source_lib_reference:
            symbol = _lib_ref(record.source_component_library, record.source_lib_reference)
        components.append(
            Component(
                id=cmp_id,
                native_ids=cmp_native_ids,
                provenance=ctx.provenance(locator),
                ref=ref,
                value=comment,
                lib_symbol_ref=symbol,
                lib_footprint_ref=lib_ref,
                path=ref,
                pins=add_pins(cmp_id, cmp_native_ids["altium"], pads, locator),
            )
        )
        ctx.census.map("components")

    for index, record in free_pads:
        locator = f"Pads6/Data#{index}"
        position = units.pcb_point(record.x, record.y)
        fp_native = f"fp:pad#{index}"
        fp_id, fp_native_ids = ctx.ids.native("fp", fp_native)
        cmp_id, cmp_native_ids = ctx.ids.native("cmp", f"cmp:{fp_native}")
        frame = Transform.placement(position, 0).inverse()
        pads = make_pads([(index, record)], fp_native, frame, 0)
        footprints.append(
            FootprintInstance(
                id=fp_id,
                native_ids=fp_native_ids,
                provenance=ctx.provenance(locator),
                component_id=cmp_id,
                lib_ref="",
                position=position,
                attributes=("board_only",),
                pads=pads,
            )
        )
        links[fp_id] = None
        components.append(
            Component(
                id=cmp_id,
                native_ids=cmp_native_ids,
                provenance=ctx.provenance(locator),
                ref="",
                pins=add_pins(cmp_id, cmp_native_ids["altium"], pads, locator),
            )
        )

    found_tracks, line_graphics = copper.tracks(doc, ctx, placed)
    found_arcs, arc_graphics = copper.arcs(doc, ctx, placed)
    found_vias = copper.vias(doc, ctx)
    found_zones, zone_polygons = copper.zones(doc, ctx)
    shape_graphics = copper.shapes(doc, ctx, zone_polygons, placed)
    found_texts = copper.texts(doc, ctx, placed)
    edge = copper.outline(doc.board.outline, ctx)

    multi = 0
    model_nets: list[Net] = []
    for name, (ident, native, locator) in nets.items():
        listed = membership.get(name, [])
        pairs = [("classes", other) for other in listed[1:]]
        multi += bool(pairs)
        model_nets.append(
            Net(
                id=ident,
                native_ids=native,
                provenance=ctx.provenance(locator),
                ext=bag(pairs),
                name=name,
                netclass_id=class_ids[listed[0]] if listed else None,
                members=tuple(members[name]),
            )
        )
    if multi:
        ctx.issues.append(
            issue(
                "altium.import.multi-class",
                f"{multi} net(s) are in more than one net class; the first class by name is kept and "
                "the others are in the pair classes",
                "Classes6/Data",
            )
        )

    rules = import_rules(
        [r.fields for r in doc.rules],
        ids,
        file=file,
        sha256=sha256,
        issues=ctx.issues,
        layers=layers.copper_layers(),
    )
    for name, streams in sorted(doc.storages.items()):
        if name and name not in DECODED_STORAGES and any(streams.get(s) for s in streams if s != "Header"):
            ctx.census.note(name)

    board_id, board_native = ids.native("brd", ids.kind)
    origin: list[tuple[str, str]] = []
    x_text, y_text = doc.board.record.get("ORIGINX"), doc.board.record.get("ORIGINY")
    if x_text is not None and y_text is not None:
        origin.append(("origin", f"{x_text},{y_text}"))
    board_provenance = ctx.provenance("Board6/Data#0")
    stack = stackup(doc.board, layers, ids, board_provenance, ctx.issues)
    board = Board(
        id=board_id,
        native_ids=board_native,
        provenance=board_provenance,
        ext=bag(origin),
        outline=None,
        layers=layers.entities(ids, board_provenance),
        stackup=stack,
        footprints=tuple(footprints),
        tracks=tuple(found_tracks),
        arcs=tuple(found_arcs),
        vias=tuple(found_vias),
        zones=tuple(found_zones),
        texts=tuple(found_texts),
        graphics=(*edge, *line_graphics, *arc_graphics, *shape_graphics),
    )
    return BoardImport(board, model_nets, classes, components, rules, links, ctx.issues, ctx.census)


def header(ids: Ids, name: str, *, file: str, sha256: str, locator: str = "") -> DesignHeader:
    """The header of an imported design: its native id is the kind that was read."""
    ident, native = ids.native("dsn", ids.kind)
    return DesignHeader(
        id=ident,
        native_ids=native,
        provenance=ids.provenance(file, sha256, locator),
        name=name,
        schema_version=SCHEMA_VERSION,
        fenolite_version=__version__,
    )


def import_board(doc: PcbDocument, *, file: str, sha256: str, issues: list[Issue] | None = None) -> Design:
    """The design of a PCB document read without its schematic: the board, a circuit synthesised from the
    pads (one component per footprint, one pin per pad name, type ``unspecified``) and the rules that map.
    ``file`` is the document's file name without a folder and ``sha256`` its hash; the adapter's issues are
    added to ``issues``."""
    ids = Ids(KIND, EVIDENCE)
    parts = read_board(doc, file=file, sha256=sha256, ids=ids)
    found = [*parts.issues, *parts.census.issues(file)]
    if issues is not None:
        issues.extend(found)
    circuit = Circuit(
        components=tuple(parts.components), nets=tuple(parts.nets), netclasses=tuple(parts.netclasses)
    )
    return Design(
        header=header(ids, stem(file), file=file, sha256=sha256, locator="FileHeaderSix"),
        circuit=circuit,
        board=parts.board,
        rules=parts.rules,
    )


__all__ = ["KIND", "BoardImport", "header", "import_board", "read_board", "stem"]
