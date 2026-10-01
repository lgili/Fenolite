# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad boards (``.kicad_pcb``) as a ``Design``, and the same-version rebuild of a read board.

Facts, the Fenolite choices and their labels: ``docs/formats/kicad/board.md``. Every child of a
modelled item is modelled, projected (an opaque slot whose value is also copied into the model) or
opaque; slot lists persist in ``ext["kicad"]``. A modelled child that the emitters do not reproduce
exactly is kept as written (a projected slot, ``kicad.board.kept-opaque``), so ``rebuild_board`` of
a read board is tree-equal to the file.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from types import MappingProxyType
from typing import Literal, TypeVar, get_args

from fenolite import __version__
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad._fpmap import (
    GR_GRAPHIC_HEADS,
    PAD_FIELDS,
    Ids,
    Items,
    at_node,
    emit_graphic,
    emit_pad,
    layers_node,
    node,
    point_node,
    read_graphic,
    read_pad,
    symbols,
    text_of,
    unrepresentable,
    uuid_items,
)
from fenolite.backends.kicad._libread import (
    Context,
    InexactValueError,
    Source,
    child_locators,
    leading_atoms,
    load_source,
)
from fenolite.backends.kicad.layers import expand_layers, has_wildcard, layer_kind
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps
from fenolite.backends.kicad.versions import FileKind
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import content_hash, content_id, derived_id
from fenolite.core.units import Udeg
from fenolite.model.base import Entity, ExtBag, Modeled, Slot
from fenolite.model.board import (
    Arc,
    Board,
    FootprintAttribute,
    FootprintInstance,
    Graphic,
    Keepout,
    Layer,
    Pad,
    Text,
    Track,
    Via,
    ViaType,
    Zone,
    ZoneFill,
)
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef, PinType
from fenolite.model.design import SCHEMA_VERSION, Design, DesignHeader

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",))
KEPT_CODE = "kicad.board.kept-opaque"
FULL_TURN = 360_000_000
ISLAND_FLAG_VERSION = 20250801
"""From this board version the island flag is ``(island yes|no)``; before it, the bare ``(island)``."""

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.board.inexact-length": "info",
        "kicad.board.inexact-angle": "info",
        "kicad.board.zone-outline-opaque": "info",
        "kicad.board.duplicate-uuid": "warning",
        "kicad.board.unknown-net": "warning",
        KEPT_CODE: "info",
    }
)
PIN_TYPES: Mapping[str, PinType] = MappingProxyType({t: t for t in get_args(PinType)})
FOOTPRINT_ATTRIBUTES: frozenset[str] = frozenset(get_args(FootprintAttribute))
VIA_TYPES: frozenset[str] = frozenset(get_args(ViaType)) - {"through"}

ROOT = ("kicad_pcb",)
FP_ROOT = ("kicad_pcb", "footprint")
ROOT_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "version": "version",
        "generator": "generator",
        "generator_version": "generator_version",
        "layers": "layers",
        "net": "nets",
        "footprint": "footprints",
        "segment": "tracks",
        "arc": "arcs",
        "via": "vias",
        "zone": "zones",
        **{head: f"graphics.{head}" for head in GR_GRAPHIC_HEADS},
        "gr_text": "texts",
    }
)
FOOTPRINT_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "layer": "side",
        "at": "position",
        "uuid": "native_ids",
        "attr": "attributes",
        "pad": "pads",
        "path": "path",
    }
)
FOOTPRINT_POSITIONAL = ("lib_ref",)
BOARD_PAD_FIELDS: Mapping[str, str] = MappingProxyType({**PAD_FIELDS, "net": "net_id"})
TRACK_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "start": "start",
        "mid": "mid",
        "end": "end",
        "width": "width",
        "layer": "layer",
        "net": "net_id",
        "uuid": "native_ids",
    }
)
VIA_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "at": "position",
        "size": "diameter",
        "drill": "drill",
        "layers": "layers",
        "net": "net_id",
        "uuid": "native_ids",
    }
)
VIA_POSITIONAL = ("via_type",)
ZONE_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "net": "net_id",
        "layer": "layers",
        "layers": "layers",
        "uuid": "native_ids",
        "name": "name",
        "priority": "priority",
        "polygon": "outline",
        "filled_polygon": "fills",
        "keepout": "keepout",
    }
)
KEEPOUT_FIELDS: Mapping[str, str] = MappingProxyType(
    {k: v for k, v in ZONE_FIELDS.items() if v not in ("name", "priority", "fills")}
)
"""A rule area has no name, priority or fills in the model; those children stay opaque."""
FILL_FIELDS: Mapping[str, str] = MappingProxyType({"layer": "layer", "island": "island", "pts": "polygon"})
TEXT_FIELDS: Mapping[str, str] = MappingProxyType({"at": "position", "layer": "layer", "uuid": "native_ids"})
TEXT_POSITIONAL = ("text",)
KEEPOUT_SETTINGS = (
    ("tracks", "no_tracks"),
    ("vias", "no_vias"),
    ("pads", "no_pads"),
    ("copperpour", "no_copper_pour"),
    ("footprints", "no_footprints"),
)
NetForm = Literal["numbered", "named"]
E = TypeVar("E", bound=Entity)
_INDEX = re.compile(r"/([^/\[\]]+)\[(\d+)\]$")


def pad_angle_from_board(stored: Udeg, footprint: Udeg) -> Udeg:
    """A board pad's angle relative to its footprint: ``(stored − footprint) mod 360°``."""
    return (stored - footprint) % FULL_TURN


def pad_angle_to_board(relative: Udeg, footprint: Udeg) -> Udeg:
    """The angle a board stores for a pad: ``(relative + footprint) mod 360°``, in [0°, 360°)."""
    return (relative + footprint) % FULL_TURN


# --- emitting -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Nets:
    """How net references are written: the form, and each net's name and table number."""

    form: NetForm
    names: Mapping[str, str]
    numbers: Mapping[str, int]

    def node(self, net_id: str | None, *, pad: bool = False) -> Node:
        if self.form == "named":
            return node("net", Atom.string(self.names[net_id] if net_id is not None else ""))
        if net_id is None:
            return node("net", Atom.integer(0), Atom.string("")) if pad else node("net", Atom.integer(0))
        number = Atom.integer(self.numbers[net_id])
        return node("net", number, Atom.string(self.names[net_id])) if pad else node("net", number)


def _emit_footprint(fp: FootprintInstance, path: str) -> Items:
    return {
        "lib_ref": [Atom.string(fp.lib_ref)],
        "side": [node("layer", Atom.string("B.Cu" if fp.side == "bottom" else "F.Cu"))],
        "position": [at_node(fp.position, fp.rotation)],
        "native_ids": uuid_items(fp.native_ids),
        "attributes": [node("attr", *(Atom.symbol(a) for a in fp.attributes))],
        "path": [node("path", Atom.string(path))],
    }


def _emit_board_pad(pad: Pad, rotation: Udeg, nets: _Nets) -> Items:
    angle = pad_angle_to_board(pad.rotation, rotation)
    return emit_pad(pad, nets.node(pad.net_id, pad=True), angle=angle)


def _emit_track(track: Track | Arc, nets: _Nets) -> Items:
    points: Items = {"start": [point_node("start", track.start)], "end": [point_node("end", track.end)]}
    if isinstance(track, Arc):
        points["mid"] = [point_node("mid", track.mid)]
    return {
        **points,
        "width": [node("width", Atom.from_nm(track.width))],
        "layer": [node("layer", Atom.string(track.layer))],
        "net_id": [nets.node(track.net_id)],
        "native_ids": uuid_items(track.native_ids),
    }


def _emit_via(via: Via, nets: _Nets) -> Items:
    return {
        "via_type": [] if via.via_type == "through" else [Atom.symbol(via.via_type)],
        "position": [point_node("at", via.position)],
        "diameter": [node("size", Atom.from_nm(via.diameter))],
        "drill": [node("drill", Atom.from_nm(via.drill))],
        "layers": [layers_node("layers", via.layers)],
        "net_id": [nets.node(via.net_id)],
        "native_ids": uuid_items(via.native_ids),
    }


def _pts(points: Sequence[Point]) -> Node:
    return node("pts", *(point_node("xy", p) for p in points))


def _emit_zone(zone: Zone | Keepout, nets: _Nets) -> Items:
    layers = zone.layers
    items: Items = {
        "layers": [layers_node("layer" if len(layers) == 1 else "layers", layers)],
        "native_ids": uuid_items(zone.native_ids),
        "outline": [node("polygon", _pts(zone.outline))],
    }
    if isinstance(zone, Zone):
        items["net_id"] = [nets.node(zone.net_id)]
        items["name"] = [node("name", Atom.string(zone.name))]
        items["priority"] = [node("priority", Atom.integer(zone.priority))]
    else:
        items["net_id"] = [nets.node(None)]
        settings = [
            node(head, Atom.symbol("not_allowed" if getattr(zone, attr) else "allowed"))
            for head, attr in KEEPOUT_SETTINGS
        ]
        items["keepout"] = [node("keepout", *settings)]
    return items


def _emit_fill(fill: ZoneFill, version: int) -> Items:
    island: list[Node | Atom] = []
    if version >= ISLAND_FLAG_VERSION:
        island = [node("island", Atom.symbol("yes" if fill.island else "no"))]
    elif fill.island:
        island = [node("island")]
    return {
        "layer": [node("layer", Atom.string(fill.layer))],
        "island": island,
        "polygon": [_pts(fill.polygon)],
    }


def _emit_text(text: Text) -> Items:
    return {
        "text": [Atom.string(text.text)],
        "position": [at_node(text.position, text.rotation, always=True)],
        "layer": [node("layer", Atom.string(text.layer))],
        "native_ids": uuid_items(text.native_ids),
    }


def _ext_pairs(entity: Entity) -> dict[str, str]:
    bag = entity.ext.get("kicad")
    return {} if bag is None else {k: v for k, v in bag.payload if not k.startswith(slotlib.SLOT_PREFIX)}


def _emit_layers(layers: Sequence[Layer]) -> Node:
    """``(layers (N "NAME" TYPE ["USER NAME"]) …)``; each row's head is its number."""
    rows: list[Node | Atom] = []
    for layer in layers:
        pairs = _ext_pairs(layer)
        atoms: list[Node | Atom] = [Atom.string(layer.name), Atom.symbol(pairs.get("type", "user"))]
        if "user_name" in pairs:
            atoms.append(Atom.string(pairs["user_name"]))
        rows.append(Node(Atom.integer(int(pairs["number"])), tuple(atoms)))
    return node("layers", *rows)


def _emit_header(board: Board) -> Items:
    pairs = _ext_pairs(board)
    items: Items = {}
    if "version" in pairs:
        items["version"] = [node("version", Atom.integer(int(pairs["version"])))]
    for key in ("generator", "generator_version"):
        if key in pairs:
            items[key] = [node(key, Atom.string(pairs[key]))]
    items["layers"] = [_emit_layers(board.layers)]
    return items


class ModelSource:
    """A ``slots.SlotSource`` over prepared items: field → the children it emits, in order."""

    def __init__(self, items: Mapping[str, Sequence[Node | Atom]]) -> None:
        self._items = {name: tuple(values) for name, values in items.items()}

    def items(self, field: str) -> Sequence[Node | Atom]:
        return self._items.get(field, ())

    def fields(self) -> Iterable[str]:
        return [name for name, values in self._items.items() if values]


def _index(entity: Entity) -> tuple[str, int]:
    """``(head, index)`` of an entity's own node from its provenance locator (``…/segment[3]``)."""
    locator = entity.provenance.locator if entity.provenance is not None else ""
    match = _INDEX.search(locator)
    return (match.group(1), int(match.group(2))) if match else ("", -1)


def _slots(entity: Entity, rel: str = ".") -> tuple[Slot, ...]:
    bag = entity.ext.get("kicad")
    found = slotlib.from_ext(bag, rel) if bag is not None else ()
    if not found:
        raise ValueError(
            f"{entity.id} has no KiCad slot list ({rel!r}); created content is written by write_board"
        )
    return found


def _modeled(slots: Sequence[Slot]) -> set[str]:
    return {s.field for s in slots if isinstance(s, Modeled)}


@dataclass(frozen=True)
class EmitContext:
    """What the emitters need beyond an entity: the design, the net form and the table numbers."""

    design: Design
    net_form: NetForm
    net_numbers: Mapping[str, int]

    @classmethod
    def of(cls, design: Design) -> EmitContext:
        board = design.board
        pairs = _ext_pairs(board) if board is not None else {}
        form: NetForm = "numbered" if pairs.get("net_form", "numbered") == "numbered" else "named"
        numbers = {
            n.id: int(_ext_pairs(n)["number"]) for n in design.circuit.nets if "number" in _ext_pairs(n)
        }
        return cls(design, form, numbers)

    @cached_property
    def nets(self) -> _Nets:
        return _Nets(self.net_form, {n.id: n.name for n in self.design.circuit.nets}, self.net_numbers)

    @cached_property
    def version(self) -> int:
        board = self.design.board
        return int(_ext_pairs(board).get("version", "0")) if board is not None else 0

    @cached_property
    def pad_rotation(self) -> dict[str, Udeg]:
        board = self.design.board
        return {pad.id: fp.rotation for fp in (board.footprints if board else ()) for pad in fp.pads}


def _rebuild(entity: Entity, head: str, ctx: EmitContext, rel: str = ".") -> Node:
    slots = _slots(entity, rel)
    return slotlib.rebuild(Atom.symbol(head), slots, model_source(entity, ctx))


def _sorted(entities: Iterable[E]) -> list[E]:
    return sorted(entities, key=lambda e: _index(e)[1])


def _net_row(number: int, name: str) -> Node:
    return node("net", Atom.integer(number), Atom.string(name))


def model_source(entity: Entity, ctx: EmitContext) -> ModelSource:
    """The children an entity's modelled fields emit; nested entities are rebuilt from their slots."""
    items: Items
    if isinstance(entity, Board):
        items = _emit_header(entity)
        rows = _sorted(n for n in ctx.design.circuit.nets if n.id in ctx.net_numbers)
        items["nets"] = [_net_row(ctx.net_numbers[n.id], n.name) for n in rows]
        items["footprints"] = [_rebuild(fp, "footprint", ctx) for fp in _sorted(entity.footprints)]
        items["tracks"] = [_rebuild(t, "segment", ctx) for t in _sorted(entity.tracks)]
        items["arcs"] = [_rebuild(a, "arc", ctx) for a in _sorted(entity.arcs)]
        items["vias"] = [_rebuild(v, "via", ctx) for v in _sorted(entity.vias)]
        items["zones"] = [_rebuild(z, "zone", ctx) for z in _sorted(entity.zones)]
        items["keepouts"] = [_rebuild(k, "zone", ctx) for k in _sorted(entity.keepouts)]
        items["texts"] = [_rebuild(t, "gr_text", ctx) for t in _sorted(entity.texts)]
        for head in GR_GRAPHIC_HEADS:
            items[f"graphics.{head}"] = [
                _rebuild(g, head, ctx) for g in _sorted(g for g in entity.graphics if _index(g)[0] == head)
            ]
    elif isinstance(entity, FootprintInstance):
        component = ctx.design.by_id.get(entity.component_id)
        path = component.path if isinstance(component, Component) else ""
        items = _emit_footprint(entity, path)
        items["pads"] = [_rebuild(pad, "pad", ctx) for pad in _sorted(entity.pads)]
    elif isinstance(entity, Pad):
        items = _emit_board_pad(entity, ctx.pad_rotation.get(entity.id, 0), ctx.nets)
    elif isinstance(entity, (Track, Arc)):
        items = _emit_track(entity, ctx.nets)
    elif isinstance(entity, Via):
        items = _emit_via(entity, ctx.nets)
    elif isinstance(entity, (Zone, Keepout)):
        items = _emit_zone(entity, ctx.nets)
        if isinstance(entity, Zone):
            items["fills"] = [_rebuild_fill(entity, k, fill, ctx) for k, fill in enumerate(entity.fills)]
    elif isinstance(entity, Text):
        items = _emit_text(entity)
    elif isinstance(entity, Graphic):
        items = emit_graphic(entity, _index(entity)[0])
    else:
        raise TypeError(f"no KiCad board emitter for {type(entity).__name__}")
    wanted = _modeled(_slots(entity))
    return ModelSource({name: values for name, values in items.items() if name in wanted})


def _rebuild_fill(zone: Zone, k: int, fill: ZoneFill, ctx: EmitContext) -> Node:
    slots = _slots(zone, f"fill[{k}]")
    items = _emit_fill(fill, ctx.version)
    source = ModelSource({name: values for name, values in items.items() if name in _modeled(slots)})
    return slotlib.rebuild(Atom.symbol("filled_polygon"), slots, source)


def rebuild_board(design: Design) -> Node:
    """The ``kicad_pcb`` node of a design read by ``read_board``, from its slots and model values."""
    board = design.board
    if board is None:
        raise ValueError("the design has no board")
    root = _rebuild(board, "kicad_pcb", EmitContext.of(design))
    comments = tuple(v for k, v in board.ext["kicad"].payload if k == "comment")
    return dataclasses.replace(root, comments=comments) if comments else root


def _opaque_fragments(design: Design) -> Iterable[str]:
    for entity in design.entities():
        bag = entity.ext.get("kicad")
        if bag is None:
            continue
        for key, value in bag.payload:
            if key.startswith(slotlib.SLOT_PREFIX) and key.rpartition(":")[2].startswith("opaque"):
                yield value


def opaque_count(design: Design) -> int:
    """The number of opaque slots across every ``kicad`` bag of a design read from KiCad."""
    return sum(1 for _ in _opaque_fragments(design))


def opaque_digests(design: Design) -> Counter[str]:
    """The SHA-256 hex digests of the opaque fragments, as a multiset."""
    return Counter(hashlib.sha256(f.encode("utf-8")).hexdigest() for f in _opaque_fragments(design))


# --- reading --------------------------------------------------------------------------------------


class _Unmodelled(Exception):
    """An item that the model cannot represent; it stays an opaque slot (``kicad.board.kept-opaque``)."""


@dataclass(slots=True)
class _NetEntry:
    id: str
    name: str
    number: int | None
    locator: str


class _BoardIds:
    """Ids of root items and footprints: the uuid, with ``:<k>`` for its k-th repetition in the file."""

    def __init__(self, reader: _Reader) -> None:
        self.reader = reader
        self.content: Counter[tuple[str, str]] = Counter()

    def of(self, prefix: str, section: str, node: Node, suffix: str = "") -> tuple[str, dict[str, str]]:
        uuid = node.find("uuid")
        atoms = uuid.atoms() if uuid is not None else ()
        if atoms:
            value = atoms[0].value
            repeat = self.reader.seen_uuid(value)
            return derived_id(prefix, "kicad", value + (f":{repeat}" if repeat else "")), {"kicad": value}
        text = dumps(node, style="compact")
        count = self.content[(node.name, text)]
        self.content[(node.name, text)] = count + 1
        return content_id(prefix, "kicad", "kicad_pcb", node.name, content_hash(text, count)), {}


class _PadIds(Ids):
    """Pad ids scoped by their footprint; every pad uuid also counts for the file's duplicate warning."""

    def __init__(self, native: str, reader: _Reader) -> None:
        super().__init__(native)
        self.reader = reader

    def of(self, prefix: str, section: str, node: Node, suffix: str = "") -> tuple[str, dict[str, str]]:
        uuid = node.find("uuid")
        atoms = uuid.atoms() if uuid is not None else ()
        if atoms and prefix == "pad":
            self.reader.seen_uuid(atoms[0].value)
        return super().of(prefix, section, node, suffix)


class _Reader:
    """One board being read: its context, net table, copper layers and uuid census."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.uuids: Counter[str] = Counter()
        self.ids = _BoardIds(self)
        self.nets: dict[str, _NetEntry] = {}
        self.table: dict[int, str] = {}
        self.copper: tuple[str, ...] = ()
        self.form: NetForm = "named"
        self._nets_cache: _Nets | None = None

    # -- shared helpers

    def issue(self, code: str, message: str, where: str) -> None:
        self.ctx.issues.append(Issue(code, ISSUE_CODES[code], message, where=where))

    def seen_uuid(self, value: str) -> int:
        repeat = self.uuids[value]
        self.uuids[value] = repeat + 1
        if repeat:
            self.issue("kicad.board.duplicate-uuid", f"uuid {value} is already used in this file", value)
        return repeat

    def keep(self, slots: list[Slot], index: int, child: Node, chain: tuple[str, ...]) -> None:
        slots[index] = self.ctx.opaque(child, chain)

    def keep_inexact(
        self, error: InexactValueError, slots: list[Slot], index: int, child: Node, chain: tuple[str, ...]
    ) -> None:
        code = "kicad.board.inexact-angle" if error.what == "angle" else "kicad.board.inexact-length"
        self.issue(code, f"{error.message}; kept as written", error.locator)
        self.keep(slots, index, child, chain)

    def keep_unmodelled(
        self, why: str, slots: list[Slot], index: int, child: Node, loc: str, chain: tuple[str, ...]
    ) -> None:
        self.ctx.kept_opaque(why, loc)
        self.keep(slots, index, child, chain)

    @property
    def emit_nets(self) -> _Nets:
        if self._nets_cache is None:
            names = {entry.id: entry.name for entry in self.nets.values()}
            numbers = {e.id: e.number for e in self.nets.values() if e.number is not None}
            self._nets_cache = _Nets(self.form, names, numbers)
        return self._nets_cache

    def check(
        self,
        item: Node,
        loc: str,
        slots: list[Slot],
        items: Mapping[str, Sequence[Node | Atom]],
        chain: tuple[str, ...],
        nested: Iterable[str] = (),
    ) -> None:
        """Keep as written every modelled child that the emitters do not reproduce exactly."""
        skip = set(nested)
        taken: Counter[str] = Counter()
        for index, ((child_loc, child), slot) in enumerate(
            zip(child_locators(loc, item), slots, strict=True)
        ):
            if not isinstance(slot, Modeled) or slot.field in skip:
                continue
            k = taken[slot.field]
            taken[slot.field] += 1
            emitted = items.get(slot.field, ())
            if k < len(emitted) and emitted[k] == child:
                continue
            slots[index] = self.ctx.opaque(child, chain)
            what = child.name if isinstance(child, Node) else child.text
            self.ctx.kept_opaque(
                f"{what!r} is not written the way Fenolite writes it; kept as written", child_loc
            )

    # -- nets

    def net(self, child: Node, loc: str) -> tuple[str | None, bool]:
        """``(net id, modelled)`` of a net reference in either form."""
        atoms = child.atoms()
        if not atoms or child.nodes():
            return None, False
        first = atoms[0]
        if first.kind == AtomKind.NUMBER:
            try:
                number = first.to_int()
            except ValueError:
                return None, False
            if number == 0:
                return None, True
            name = self.table.get(number)
            if name is None:
                self.issue("kicad.board.unknown-net", f"net {number} is not in the net table", loc)
                return None, False
            return self.nets[name].id, True
        if first.kind != AtomKind.STRING:
            return None, False
        name = first.value
        if not name:
            return None, True
        entry = self.nets.get(name)
        if entry is None:
            entry = self.nets[name] = _NetEntry(derived_id("net", "kicad", f"net:{name}"), name, None, loc)
            self._nets_cache = None
        return entry.id, True

    def net_row(self, child: Node, loc: str) -> bool:
        """Register a table row ``(net N "NAME")``; true when it is modelled (N ≥ 1)."""
        atoms = child.atoms()
        if len(atoms) != 2 or atoms[0].kind != AtomKind.NUMBER or atoms[1].kind != AtomKind.STRING:
            raise self.ctx.error('a net table row is (net N "NAME")', loc, child)
        number, name = atoms[0].to_int(), atoms[1].value
        if number == 0:
            return False
        self.table[number] = name
        self.nets[name] = _NetEntry(derived_id("net", "kicad", f"net:{name}"), name, number, loc)
        self._nets_cache = None
        return True

    # -- layers

    def layers(self, child: Node, loc: str) -> list[Layer]:
        layers: list[Layer] = []
        for ordinal, (row_loc, row) in enumerate(child_locators(loc, child)):
            if not isinstance(row, Node):
                raise self.ctx.error("unexpected atom in the layer table", loc, child)
            atoms = row.atoms()
            if row.head.kind != AtomKind.NUMBER or len(atoms) < 2 or row.nodes():
                raise self.ctx.error('a layer row is (N "NAME" TYPE ["USER NAME"])', row_loc, row)
            name, row_type = atoms[0].value, atoms[1].value
            pairs = [("number", row.head.text), ("type", row_type)]
            if len(atoms) > 2:
                pairs.append(("user_name", atoms[2].value))
            layers.append(
                Layer(
                    id=derived_id("lay", "kicad", f"layer:{name}"),
                    provenance=self.ctx.provenance(row_loc),
                    ext={"kicad": ExtBag(None, tuple(pairs))},
                    name=name,
                    kind=layer_kind(name, row_type),
                    ordinal=ordinal,
                )
            )
        self.copper = tuple(layer.name for layer in layers if layer.kind == "copper")
        return layers

    def expand(self, names: tuple[str, ...]) -> tuple[str, ...] | None:
        return expand_layers(names, self.copper) if has_wildcard(names) else None

    # -- footprints

    def footprint(self, item: Node, loc: str) -> tuple[FootprintInstance, Component, list[Pad]]:
        ctx = self.ctx
        slots = ctx.split(item, dict(FOOTPRINT_FIELDS), FP_ROOT, FOOTPRINT_POSITIONAL)
        header = leading_atoms(item)
        lib_ref = header[0].value if header else ""
        locked = any(a.kind == AtomKind.SYMBOL and a.value == "locked" for a in header[1:])
        at = item.find("at")
        if at is None:
            raise ctx.error("a board footprint needs (at X Y [ANGLE])", loc, item)
        at_loc = f"{loc}/at[0]"
        position = ctx.point(at, at_loc)
        values = at.atoms()
        rotation = ctx.udeg(values[2], at_loc, at) if len(values) > 2 else 0
        ident, native_ids = self.ids.of("fp", "footprint", item)
        key = native_ids.get("kicad", ident)
        pad_ids = _PadIds(key, self)
        side: Literal["top", "bottom"] = "top"
        attributes: list[FootprintAttribute] = []
        properties: dict[str, str] = {}
        path = ""
        pads: list[tuple[Pad, Node, str]] = []
        for index, (child_loc, child) in enumerate(child_locators(loc, item)):
            if not isinstance(child, Node):
                continue
            head = child.name
            if head == "layer":
                side = "bottom" if text_of(child) == "B.Cu" else "top"
            elif head == "attr":
                attributes = self.attributes(child, child_loc, slots, index)
            elif head == "property":
                atoms = leading_atoms(child)
                if len(atoms) >= 2:
                    properties[atoms[0].value] = atoms[1].value
            elif head == "locked":
                locked = symbols(child) != ["no"]
            elif head == "path":
                path = text_of(child)
            elif head == "pad":
                try:
                    pad = read_pad(
                        ctx,
                        child,
                        child_loc,
                        pad_ids,
                        root=FP_ROOT,
                        fields=BOARD_PAD_FIELDS,
                        expand=self.expand,
                        net=self.net,
                    )
                except InexactValueError as error:
                    self.keep_inexact(error, slots, index, child, FP_ROOT)
                    continue
                pad = dataclasses.replace(pad, rotation=pad_angle_from_board(pad.rotation, rotation))
                pad_slots = list(slotlib.from_ext(pad.ext["kicad"]))
                emitted = _emit_board_pad(pad, rotation, self.emit_nets)
                self.check(child, child_loc, pad_slots, emitted, (*FP_ROOT, "pad"))
                pad = dataclasses.replace(pad, ext={"kicad": slotlib.to_ext(pad_slots)})
                pads.append((pad, child, child_loc))
        component_id = derived_id("cmp", "kicad", f"fp:{key}")
        instance = FootprintInstance(
            id=ident,
            native_ids=native_ids,
            provenance=ctx.provenance(loc),
            component_id=component_id,
            lib_ref=lib_ref,
            position=position,
            rotation=rotation,
            side=side,
            locked=locked,
            attributes=tuple(attributes),
            pads=tuple(pad for pad, _, _ in pads),
        )
        self.check(item, loc, slots, _emit_footprint(instance, path), FP_ROOT, nested=("pads",))
        instance = dataclasses.replace(instance, ext={"kicad": slotlib.to_ext(slots)})
        component = Component(
            id=component_id,
            provenance=ctx.provenance(loc),
            ref=properties.get("Reference", ""),
            value=properties.get("Value", ""),
            dnp="dnp" in attributes,
            lib_footprint_ref=lib_ref,
            properties=dict(sorted(properties.items())),
            path=path,
            pins=self.pins(key, pads),
        )
        return instance, component, [pad for pad, _, _ in pads]

    def attributes(self, child: Node, loc: str, slots: list[Slot], index: int) -> list[FootprintAttribute]:
        known: list[FootprintAttribute] = []
        others: list[str] = []
        for part in child.children:
            if isinstance(part, Atom) and part.kind == AtomKind.SYMBOL and part.value in FOOTPRINT_ATTRIBUTES:
                known.append(part.value)  # type: ignore[arg-type]
            else:
                others.append(dumps(part, style="compact"))
        if others:
            self.keep_unmodelled(
                f"attr {' '.join(others)} is not a modelled attribute; kept as written",
                slots,
                index,
                child,
                loc,
                FP_ROOT,
            )
        return known

    def pins(self, key: str, pads: Sequence[tuple[Pad, Node, str]]) -> tuple[Pin, ...]:
        pins: list[Pin] = []
        seen: set[str] = set()
        for pad, pad_node, pad_loc in pads:
            if not pad.number or pad.number in seen:
                continue
            seen.add(pad.number)
            function, pintype = pad_node.find("pinfunction"), pad_node.find("pintype")
            type_text = text_of(pintype) if pintype is not None else "passive"
            etype = PIN_TYPES.get(type_text)
            pins.append(
                Pin(
                    id=derived_id("pin", "kicad", f"{key}:pin:{pad.number}"),
                    provenance=self.ctx.provenance(pad_loc),
                    ext={} if etype is not None else {"kicad": ExtBag(None, (("pintype", type_text),))},
                    number=pad.number,
                    name=text_of(function) if function is not None else "",
                    etype=etype if etype is not None else "unspecified",
                )
            )
        return tuple(pins)

    # -- copper items

    def nm_of(self, child: Node, loc: str) -> int:
        atoms = child.atoms()
        if not atoms:
            raise self.ctx.error(f"{child.name!r} needs a value", loc, child)
        return self.ctx.nm(atoms[0], loc, child)

    def track(self, item: Node, loc: str) -> Track | Arc:
        ctx = self.ctx
        chain = (*ROOT, item.name)
        slots = ctx.split(item, dict(TRACK_FIELDS), chain)
        points: dict[str, Point] = {}
        width: int | None = None
        layer: str | None = None
        net_id: str | None = None
        for index, (child_loc, child) in enumerate(child_locators(loc, item)):
            if not isinstance(child, Node):
                continue
            head = child.name
            if head in ("start", "mid", "end"):
                points[head] = ctx.point(child, child_loc)
            elif head == "width":
                width = self.nm_of(child, child_loc)
            elif head == "layer":
                layer = text_of(child)
            elif head == "net":
                net_id, modelled = self.net(child, child_loc)
                if not modelled:
                    self.keep(slots, index, child, chain)
        needed = ("start", "mid", "end") if item.name == "arc" else ("start", "end")
        missing = [n for n in needed if n not in points] + (["width"] if width is None else [])
        if missing or layer is None:
            raise ctx.error(f"{item.name} has no {(missing or ['layer'])[0]}", loc, item)
        assert width is not None
        provenance = ctx.provenance(loc)
        start, end = points["start"], points["end"]
        if item.name == "arc":
            ident, native_ids = self.ids.of("arc", "arc", item)
            entity: Track | Arc = Arc(
                id=ident,
                native_ids=native_ids,
                provenance=provenance,
                start=start,
                mid=points["mid"],
                end=end,
                width=width,
                layer=layer,
                net_id=net_id,
            )
        else:
            ident, native_ids = self.ids.of("trk", "segment", item)
            entity = Track(
                id=ident,
                native_ids=native_ids,
                provenance=provenance,
                start=start,
                end=end,
                width=width,
                layer=layer,
                net_id=net_id,
            )
        self.check(item, loc, slots, _emit_track(entity, self.emit_nets), chain)
        return dataclasses.replace(entity, ext={"kicad": slotlib.to_ext(slots)})

    def via(self, item: Node, loc: str) -> Via:
        ctx = self.ctx
        chain = (*ROOT, "via")
        leading = leading_atoms(item)
        via_type: ViaType = "through"
        if leading:
            first = leading[0]
            if len(leading) > 1 or first.kind != AtomKind.SYMBOL or first.value not in VIA_TYPES:
                raise ctx.error(f"unknown via type {' '.join(a.text for a in leading)!r}", loc, item)
            via_type = first.value  # type: ignore[assignment]
        slots = ctx.split(item, dict(VIA_FIELDS), chain, VIA_POSITIONAL)
        position: Point | None = None
        diameter: int | None = None
        drill: int | None = None
        layers: tuple[str, ...] = ()
        net_id: str | None = None
        for index, (child_loc, child) in enumerate(child_locators(loc, item)):
            if not isinstance(child, Node):
                continue
            head = child.name
            if head == "at":
                position = ctx.point(child, child_loc)
            elif head == "size":
                diameter = self.nm_of(child, child_loc)
            elif head == "drill":
                drill = self.nm_of(child, child_loc)
            elif head == "layers":
                layers = tuple(symbols(child))
            elif head == "net":
                net_id, modelled = self.net(child, child_loc)
                if not modelled:
                    self.keep(slots, index, child, chain)
        if position is None or diameter is None or drill is None:
            missing = "at" if position is None else "size" if diameter is None else "drill"
            raise ctx.error(f"via has no {missing}", loc, item)
        ident, native_ids = self.ids.of("via", "via", item)
        via = Via(
            id=ident,
            native_ids=native_ids,
            provenance=ctx.provenance(loc),
            position=position,
            diameter=diameter,
            drill=drill,
            layers=layers,
            net_id=net_id,
            via_type=via_type,
        )
        self.check(item, loc, slots, _emit_via(via, self.emit_nets), chain)
        return dataclasses.replace(via, ext={"kicad": slotlib.to_ext(slots)})

    # -- zones

    def zone(self, item: Node, loc: str) -> Zone | Keepout:
        ctx = self.ctx
        chain = (*ROOT, "zone")
        keepout_node = item.find("keepout")
        fields = ZONE_FIELDS if keepout_node is None else KEEPOUT_FIELDS
        slots = ctx.split(item, dict(fields), chain)
        net_id: str | None = None
        layers: tuple[str, ...] = ()
        name, priority = "", 0
        polygons: list[tuple[int, str, Node]] = []
        fills: list[ZoneFill] = []
        groups: dict[str, Sequence[Slot]] = {}
        settings = dict.fromkeys((attr for _, attr in KEEPOUT_SETTINGS), False)
        for index, (child_loc, child) in enumerate(child_locators(loc, item)):
            if not isinstance(child, Node):
                continue
            head = child.name
            if head == "net":
                found, modelled = self.net(child, child_loc)
                if keepout_node is not None and found is not None:
                    self.keep_unmodelled("a rule area with a net", slots, index, child, child_loc, chain)
                elif not modelled:
                    self.keep(slots, index, child, chain)
                else:
                    net_id = found
            elif head in ("layer", "layers"):
                layers = tuple(symbols(child))
                expanded = self.expand(layers)
                if expanded is not None:
                    layers = expanded
                    self.keep(slots, index, child, chain)
            elif head == "name" and keepout_node is None:
                name = text_of(child)
            elif head == "priority" and keepout_node is None:
                atoms = child.atoms()
                if len(atoms) != 1 or atoms[0].kind != AtomKind.NUMBER:
                    raise ctx.error("zone priority is an integer", child_loc, child)
                priority = atoms[0].to_int()
            elif head == "polygon":
                polygons.append((index, child_loc, child))
            elif head == "filled_polygon" and keepout_node is None:
                try:
                    fill, fill_slots = self.fill(child, child_loc)
                except InexactValueError as error:
                    self.keep_inexact(error, slots, index, child, chain)
                    continue
                except _Unmodelled as why:
                    self.keep_unmodelled(str(why), slots, index, child, child_loc, chain)
                    continue
                groups[f"fill[{len(fills)}]"] = fill_slots
                fills.append(fill)
            elif head == "keepout":
                if not self.keepout(child, settings):
                    self.keep_unmodelled(
                        "keepout settings outside the model", slots, index, child, child_loc, chain
                    )
        outline = self.outline(polygons, slots, chain)
        ident, native_ids = self.ids.of("kpo" if keepout_node is not None else "zon", "zone", item)
        provenance = ctx.provenance(loc)
        if keepout_node is not None:
            entity: Zone | Keepout = Keepout(
                id=ident,
                native_ids=native_ids,
                provenance=provenance,
                outline=outline,
                layers=layers,
                no_tracks=settings["no_tracks"],
                no_vias=settings["no_vias"],
                no_pads=settings["no_pads"],
                no_copper_pour=settings["no_copper_pour"],
                no_footprints=settings["no_footprints"],
            )
        else:
            entity = Zone(
                id=ident,
                native_ids=native_ids,
                provenance=provenance,
                outline=outline,
                layers=layers,
                net_id=net_id,
                priority=priority,
                fills=tuple(fills),
                name=name,
            )
        self.check(item, loc, slots, _emit_zone(entity, self.emit_nets), chain, nested=("fills",))
        return dataclasses.replace(entity, ext={"kicad": slotlib.to_ext({".": slots, **groups})})

    def keepout(self, child: Node, settings: dict[str, bool]) -> bool:
        heads = {head: attr for head, attr in KEEPOUT_SETTINGS}
        for part in child.children:
            if (
                not isinstance(part, Node)
                or part.name not in heads
                or symbols(part) not in (["allowed"], ["not_allowed"])
            ):
                return False
            settings[heads[part.name]] = symbols(part) == ["not_allowed"]
        return True

    def points(self, pts: Node, loc: str) -> tuple[Point, ...] | None:
        """The points of a points-only ``pts`` list, or ``None`` when it holds anything else."""
        if pts.atoms() or any(c.name != "xy" for c in pts.nodes()):
            return None
        return tuple(self.ctx.point(c, f"{loc}/xy[{i}]") for i, c in enumerate(pts.nodes()))

    def outline(
        self, polygons: list[tuple[int, str, Node]], slots: list[Slot], chain: tuple[str, ...]
    ) -> tuple[Point, ...]:
        if len(polygons) == 1:
            index, poly_loc, poly = polygons[0]
            pts = poly.find("pts")
            if pts is not None and len(poly.children) == 1:
                try:
                    found = self.points(pts, f"{poly_loc}/pts[0]")
                except InexactValueError as error:
                    self.keep_inexact(error, slots, index, poly, chain)
                    return ()
                if found is not None:
                    return found
        for index, _poly_loc, poly in polygons:
            self.keep(slots, index, poly, chain)
        if polygons:
            self.issue(
                "kicad.board.zone-outline-opaque",
                "zone outline with arcs or several polygons; kept as written",
                polygons[0][1],
            )
        return ()

    def fill(self, item: Node, loc: str) -> tuple[ZoneFill, list[Slot]]:
        chain = (*ROOT, "zone", "filled_polygon")
        slots = self.ctx.split(item, dict(FILL_FIELDS), chain)
        layer: str | None = None
        island = False
        polygon: tuple[Point, ...] | None = None
        for index, (child_loc, child) in enumerate(child_locators(loc, item)):
            if not isinstance(child, Node):
                continue
            if child.name == "layer":
                layer = text_of(child)
            elif child.name == "island":
                flag = symbols(child)
                if flag not in ([], ["yes"], ["no"]):
                    self.keep_unmodelled(f"island flag {flag}", slots, index, child, child_loc, chain)
                island = flag in ([], ["yes"])
            elif child.name == "pts":
                polygon = self.points(child, child_loc)
                if polygon is None:
                    raise _Unmodelled("a zone fill with arcs or other items in its points")
        if layer is None or polygon is None:
            raise _Unmodelled("a zone fill without a layer or points")
        fill = ZoneFill(layer, polygon, island)
        self.check(item, loc, slots, _emit_fill(fill, self.ctx.version), chain)
        return fill, slots

    # -- graphics and texts

    def text(self, item: Node, loc: str) -> Text:
        ctx = self.ctx
        chain = (*ROOT, "gr_text")
        effects = item.find("effects")
        font = effects.find("font") if effects is not None else None
        size_node = font.find("size") if font is not None else None
        thickness_node = font.find("thickness") if font is not None else None
        leading = leading_atoms(item)
        at, layer_node = item.find("at"), item.find("layer")
        if size_node is None or thickness_node is None or not leading or at is None or layer_node is None:
            raise _Unmodelled("a text without its string, position, layer, font size or thickness")
        slots = ctx.split(item, dict(TEXT_FIELDS), chain, TEXT_POSITIONAL)
        at_loc = f"{loc}/at[0]"
        values = at.atoms()
        font_loc = f"{loc}/effects[0]/font[0]"
        size = ctx.point(size_node, f"{font_loc}/size[0]")
        ident, native_ids = self.ids.of("txt", "gr_text", item)
        text = Text(
            id=ident,
            native_ids=native_ids,
            provenance=ctx.provenance(loc),
            text=leading[0].value,
            position=ctx.point(at, at_loc),
            rotation=ctx.udeg(values[2], at_loc, at) if len(values) > 2 else 0,
            layer=layer_node.atoms()[0].value if layer_node.atoms() else "",
            size=Size(size.y, size.x),
            thickness=self.nm_of(thickness_node, f"{font_loc}/thickness[0]"),
        )
        self.check(item, loc, slots, _emit_text(text), chain)
        return dataclasses.replace(text, ext={"kicad": slotlib.to_ext(slots)})

    def graphic(self, item: Node, loc: str) -> Graphic:
        kind = GR_GRAPHIC_HEADS[item.name]
        reason = unrepresentable(item, kind)
        if reason is not None:
            raise _Unmodelled(f"{item.name}: {reason}")
        graphic = read_graphic(self.ctx, item, loc, kind, self.ids, root=ROOT)
        slots = list(slotlib.from_ext(graphic.ext["kicad"]))
        self.check(item, loc, slots, emit_graphic(graphic, item.name), (*ROOT, item.name))
        return dataclasses.replace(graphic, ext={"kicad": slotlib.to_ext(slots)})

    # -- the board

    def read(self, name: str) -> Design:
        ctx = self.ctx
        root = ctx.loaded.node
        slots = ctx.split(root, dict(ROOT_FIELDS), ROOT)
        children = child_locators("/kicad_pcb", root)
        pairs: list[tuple[str, str]] = []
        layers: list[Layer] = []
        self.form = "numbered" if root.find("net") is not None else "named"
        for index, (loc, child) in enumerate(children):  # the header, layers and net table come first
            if not isinstance(child, Node):
                continue
            if child.name in ("version", "generator", "generator_version"):
                atoms = child.atoms()
                if len(atoms) == 1:
                    pairs.append((child.name, atoms[0].text if child.name == "version" else atoms[0].value))
            elif child.name == "layers":
                layers = self.layers(child, loc)
            elif child.name == "net" and not self.net_row(child, loc):
                self.keep(slots, index, child, ROOT)
        footprints: list[FootprintInstance] = []
        components: list[Component] = []
        board_pads: list[tuple[Component, Pad]] = []
        collections: dict[str, list[Entity]] = {
            "tracks": [], "arcs": [], "vias": [], "zones": [], "keepouts": [], "texts": [], "graphics": []
        }  # fmt: skip
        for index, (loc, child) in enumerate(children):
            if not isinstance(child, Node) or not isinstance(slots[index], Modeled):
                continue
            head = child.name
            try:
                if head == "footprint":
                    instance, component, pads = self.footprint(child, loc)
                    footprints.append(instance)
                    components.append(component)
                    board_pads.extend((component, pad) for pad in pads)
                elif head in ("segment", "arc"):
                    collections["arcs" if head == "arc" else "tracks"].append(self.track(child, loc))
                elif head == "via":
                    collections["vias"].append(self.via(child, loc))
                elif head == "zone":
                    attr = child.find("attr")
                    if attr is not None and attr.find("teardrop") is not None:
                        self.keep(slots, index, child, ROOT)
                        continue
                    zone = self.zone(child, loc)
                    target = "keepouts" if isinstance(zone, Keepout) else "zones"
                    collections[target].append(zone)
                    slots[index] = Modeled(target)
                elif head in GR_GRAPHIC_HEADS:
                    collections["graphics"].append(self.graphic(child, loc))
                elif head == "gr_text":
                    collections["texts"].append(self.text(child, loc))
            except InexactValueError as error:
                self.keep_inexact(error, slots, index, child, ROOT)
            except _Unmodelled as why:
                self.keep_unmodelled(f"{why}; kept as written", slots, index, child, loc, ROOT)
        nets = self.circuit_nets(board_pads)
        board = Board(
            id=derived_id("brd", "kicad", "kicad_pcb"),
            provenance=ctx.provenance("/kicad_pcb"),
            ext={"kicad": ExtBag(None, (*pairs, ("net_form", self.form)))},
            layers=tuple(layers),
            footprints=tuple(footprints),
            tracks=tuple(collections["tracks"]),  # type: ignore[arg-type]
            arcs=tuple(collections["arcs"]),  # type: ignore[arg-type]
            vias=tuple(collections["vias"]),  # type: ignore[arg-type]
            zones=tuple(collections["zones"]),  # type: ignore[arg-type]
            keepouts=tuple(collections["keepouts"]),  # type: ignore[arg-type]
            texts=tuple(collections["texts"]),  # type: ignore[arg-type]
            graphics=tuple(collections["graphics"]),  # type: ignore[arg-type]
        )
        header_items = _emit_header(board)
        header_items["nets"] = [
            _net_row(e.number, e.name) for e in self.nets.values() if e.number is not None
        ]
        nested = [f for f in set(ROOT_FIELDS.values()) | {"keepouts"} if f not in header_items]
        self.check(root, "/kicad_pcb", slots, header_items, ROOT, nested=nested)
        comments = tuple(("comment", c) for c in root.comments)
        base = ExtBag(None, (*pairs, ("net_form", self.form), *comments))
        board = dataclasses.replace(board, ext={"kicad": slotlib.to_ext(slots, base)})
        header = DesignHeader(
            id=derived_id("dsn", "kicad", "kicad_pcb"),
            provenance=ctx.provenance("/kicad_pcb"),
            name=name,
            schema_version=SCHEMA_VERSION,
            fenolite_version=__version__,
        )
        return Design(header=header, circuit=Circuit(components=tuple(components), nets=nets), board=board)

    def circuit_nets(self, board_pads: Sequence[tuple[Component, Pad]]) -> tuple[Net, ...]:
        members: dict[str, list[PinRef]] = {entry.id: [] for entry in self.nets.values()}
        for component, pad in board_pads:
            if pad.net_id is None or not pad.number:
                continue
            ref = PinRef(component.id, pad.number)
            if ref not in members[pad.net_id]:
                members[pad.net_id].append(ref)
        return tuple(
            Net(
                id=entry.id,
                provenance=self.ctx.provenance(entry.locator),
                ext={"kicad": ExtBag(None, (("number", str(entry.number)),))}
                if entry.number is not None
                else {},
                name=entry.name,
                members=tuple(members[entry.id]),
            )
            for entry in self.nets.values()
        )


def read_board(source: Source, *, file: str = "", issues: list[Issue] | None = None) -> Design:
    """A board from a ``.kicad_pcb`` path, file text or a parsed node (see ``board.md``).

    Warnings and infos are appended to ``issues``; errors are raised. The header name is the file
    stem for a path and ``""`` otherwise.
    """
    loaded = load_source(source, file)
    ctx = Context(loaded, FileKind.BOARD, EVIDENCE, issues if issues is not None else [], kept_code=KEPT_CODE)
    ctx.check_version("kicad_pcb", FileKind.BOARD)
    name = loaded.path.stem if loaded.path is not None else ""
    return _Reader(ctx).read(name)


__all__ = [
    "BOARD_PAD_FIELDS",
    "EVIDENCE",
    "FILL_FIELDS",
    "FOOTPRINT_FIELDS",
    "ISSUE_CODES",
    "KEEPOUT_FIELDS",
    "PIN_TYPES",
    "ROOT_FIELDS",
    "TEXT_FIELDS",
    "TRACK_FIELDS",
    "VIA_FIELDS",
    "ZONE_FIELDS",
    "EmitContext",
    "ModelSource",
    "model_source",
    "opaque_count",
    "opaque_digests",
    "pad_angle_from_board",
    "pad_angle_to_board",
    "read_board",
    "rebuild_board",
]
