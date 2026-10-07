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
import uuid
from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
from types import MappingProxyType
from typing import Literal, TypeVar, get_args

from fenolite import __version__
from fenolite.backends.base import WriteResult
from fenolite.backends.kicad import _pcbwrite, netnames
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad import zones as zonelib
from fenolite.backends.kicad._fpmap import (
    GR_GRAPHIC_HEADS,
    GRAPHIC_FIELDS,
    PAD_FIELDS,
    PAD_POSITIONAL,
    Ids,
    Items,
    at_node,
    emit_graphic,
    emit_pad,
    layers_node,
    node,
    opaque_zone_connects,
    padstack_key,
    point_node,
    projected_zone_connect,
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
from fenolite.backends.kicad.versions import (
    DEFAULT_TARGET,
    FORMAT_VERSIONS,
    GENERATOR,
    TARGET_MAJORS,
    FileKind,
    FormatInfo,
    LegacyEditRefusedError,
    LossyWriteError,
    check_target,
    classify,
    major_for,
    require_editable,
)
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import FENOLITE_NS, content_hash, content_id, derived_id
from fenolite.core.units import Udeg
from fenolite.model.base import Entity, ExtBag, Modeled, Opaque, Slot
from fenolite.model.board import (
    Arc,
    Board,
    FieldJustifyH,
    FieldJustifyV,
    FootprintAttribute,
    FootprintField,
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
from fenolite.model.presentation import PAPER_SIZES, US_SIZES, SheetFrameRef, TitleBlock

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
        "kicad.board.net-name-collision": "info",
        KEPT_CODE: "info",
        "kicad.board.paper-unmodelled": "info",
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
        "property": "fields",
    }
)
FOOTPRINT_POSITIONAL = ("lib_ref",)
FIELD_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "at": "position",
        "layer": "layer",
        "hide": "visible",
        "uuid": "native_ids",
        "effects": "effects",
    }
)
"""The children of a footprint field (a placed ``property``, change c0030); ``effects`` is one modelled
child that carries the size, thickness, justification and mirror."""
FIELD_POSITIONAL = ("name",)
"""Only the name is modelled: the value atom is an opaque slot, projected into the component."""
FIELD_CHAIN = ("kicad_pcb", "footprint", "property")
JUSTIFY_H: frozenset[str] = frozenset(get_args(FieldJustifyH)) - {"center"}
JUSTIFY_V: frozenset[str] = frozenset(get_args(FieldJustifyV)) - {"center"}
BOARD_PAD_FIELDS: Mapping[str, str] = MappingProxyType({**PAD_FIELDS, "net": "net_id"})
TRACK_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "start": "start",
        "mid": "mid",
        "end": "end",
        "width": "width",
        "locked": "locked",
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
        "locked": "locked",
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
        "locked": "locked",
        "connect_pads": "connection",
        "min_thickness": "min_thickness",
        "fill": "fill_settings",
    }
)
ZONE_SETTING_FIELDS: Mapping[str, str] = MappingProxyType(
    {head: ZONE_FIELDS[head] for head in zonelib.SETTING_HEADS}
)
"""The setting children of a copper zone and the slot fields they map to (``zones.py``)."""
KEEPOUT_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        k: v
        for k, v in ZONE_FIELDS.items()
        if v not in ("name", "priority", "fills", *ZONE_SETTING_FIELDS.values())
    }
)
"""A rule area has no name, priority, fills or zone settings in the model; those children stay opaque."""
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
NetForm = Literal["numbered", "named", "neutral"]
"""How emitters write net references; ``neutral`` (the writer's) names every net and lets the net
pass of ``_pcbwrite`` put each reference in the target's form."""
E = TypeVar("E", bound=Entity)
_INDEX = re.compile(r"/([^/\[\]]+)\[(\d+)\]$")


def pad_angle_from_board(stored: Udeg, footprint: Udeg) -> Udeg:
    """A board pad's angle relative to its footprint: ``(stored − footprint) mod 360°``."""
    return (stored - footprint) % FULL_TURN


def pad_angle_to_board(relative: Udeg, footprint: Udeg) -> Udeg:
    """The angle a board stores for a pad: ``(relative + footprint) mod 360°``, in [0°, 360°)."""
    return (relative + footprint) % FULL_TURN


# --- emitting -------------------------------------------------------------------------------------


STORED_KEY = "stored"
"""The pair of a net's ``kicad`` extension bag that keeps the spelling of a stored name with ``{slash}``."""


def stored_net_name(net: Net) -> str:
    """The name ``net`` has in a written board (``kicad-file-backend``, "Net names in KiCad's stored form").

    A net read from a board keeps the spelling of its file. The reader gives a net stored with ``{slash}``
    the name with the slash and keeps the spelling in the net's ``kicad`` bag; every other read net is
    named as stored (KiCad writes the nets of sub-sheets with raw slashes), and its id is derived from
    that name. Every other net is created, and a ``/`` in its name is written ``{slash}``, as KiCad stores
    the net of a label whose text holds a slash.
    """
    kept = _ext_pairs(net).get(STORED_KEY)
    if kept is not None:
        return kept
    if net.id == derived_id("net", "kicad", f"net:{net.name}"):
        return net.name
    return netnames.stored_name(net.name)


@dataclass(frozen=True)
class _Nets:
    """How net references are written: the form, and each net's name and table number."""

    form: NetForm
    names: Mapping[str, str]
    numbers: Mapping[str, int]

    def node(self, net_id: str | None, *, pad: bool = False, zone: bool = False) -> Node | None:
        """The reference to ``net_id``; in the neutral form ``None`` for no net, except on a zone."""
        if self.form == "neutral":
            if net_id is None:
                return node("net", Atom.string("")) if zone else None
            return node("net", Atom.string(self.names[net_id]))
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


def _opt(child: Node | None) -> list[Node | Atom]:
    return [] if child is None else [child]


def field_effects(size: Size, thickness: int | None, h_justify: str, v_justify: str, mirrored: bool) -> Node:
    """``(effects (font (size H W) [(thickness T)]) [(justify [left|right] [top|bottom] [mirror])])``."""
    font: list[Node | Atom] = [node("size", Atom.from_nm(size.h), Atom.from_nm(size.w))]
    if thickness is not None:
        font.append(node("thickness", Atom.from_nm(thickness)))
    words = [w for w in (h_justify, v_justify) if w != "center"] + (["mirror"] if mirrored else [])
    children: list[Node | Atom] = [node("font", *font)]
    if words:
        children.append(node("justify", *(Atom.symbol(w) for w in words)))
    return node("effects", *children)


def _emit_field(field: FootprintField, rotation: Udeg) -> Items:
    """The modelled children of a footprint field; the file holds the board angle, always written."""
    angle = pad_angle_to_board(field.rotation, rotation)
    return {
        "name": [Atom.string(field.name)],
        "position": [at_node(field.position, angle, always=True)],
        "layer": [node("layer", Atom.string(field.layer))],
        "visible": [] if field.visible else [node("hide", Atom.symbol("yes"))],
        "native_ids": uuid_items(field.native_ids),
        "effects": [
            field_effects(field.size, field.thickness, field.h_justify, field.v_justify, field.mirrored)
        ],
    }


def field_justify(effects: Node) -> tuple[FieldJustifyH, FieldJustifyV, bool]:
    """``(h_justify, v_justify, mirrored)`` from the atoms of ``effects/justify``."""
    justify = effects.find("justify")
    words = [a.value for a in justify.atoms()] if justify is not None else []
    h: FieldJustifyH = next((w for w in words if w in JUSTIFY_H), "center")  # type: ignore[assignment]
    v: FieldJustifyV = next((w for w in words if w in JUSTIFY_V), "center")  # type: ignore[assignment]
    return h, v, "mirror" in words


def _is_hide(child: Node | Atom) -> bool:
    return isinstance(child, Atom) and child.kind == AtomKind.SYMBOL and child.value == "hide"


def field_hidden(item: Node) -> bool:
    """Whether a property node is hidden: a ``hide`` child other than ``(hide no)``, or a bare ``hide``
    atom after the value or in its ``effects`` (older spellings)."""
    lists = (item, *(c for c in item.nodes() if c.name == "effects"))
    for index, parent in enumerate(lists):
        skip = 2 if index == 0 else 0
        for child in parent.children[skip:]:
            if _is_hide(child):
                return True
            if isinstance(child, Node) and child.name == "hide" and symbols(child) != ["no"]:
                return True
    return False


def is_placed_property(item: Node) -> bool:
    """A property that holds a name, a value, ``at``, ``layer`` and an ``effects`` with a font ``size``."""
    effects = item.find("effects")
    font = effects.find("font") if effects is not None else None
    return (
        len(leading_atoms(item)) >= 2
        and item.find("at") is not None
        and item.find("layer") is not None
        and font is not None
        and font.find("size") is not None
    )


def _emit_board_pad(pad: Pad, rotation: Udeg, nets: _Nets) -> Items:
    angle = pad_angle_to_board(pad.rotation, rotation)
    return emit_pad(pad, nets.node(pad.net_id, pad=True), angle=angle)


def _lock_items(locked: bool) -> list[Node | Atom]:
    """``(locked yes)`` for a locked track, arc or via; nothing for an unlocked one (``H-K-LOCK-FORM``)."""
    return [node("locked", Atom.symbol("yes"))] if locked else []


def _emit_track(track: Track | Arc, nets: _Nets) -> Items:
    points: Items = {"start": [point_node("start", track.start)], "end": [point_node("end", track.end)]}
    if isinstance(track, Arc):
        points["mid"] = [point_node("mid", track.mid)]
    return {
        **points,
        "width": [node("width", Atom.from_nm(track.width))],
        "locked": _lock_items(track.locked),
        "layer": [node("layer", Atom.string(track.layer))],
        "net_id": _opt(nets.node(track.net_id)),
        "native_ids": uuid_items(track.native_ids),
    }


def _emit_via(via: Via, nets: _Nets) -> Items:
    return {
        "via_type": [] if via.via_type == "through" else [Atom.symbol(via.via_type)],
        "position": [point_node("at", via.position)],
        "diameter": [node("size", Atom.from_nm(via.diameter))],
        "drill": [node("drill", Atom.from_nm(via.drill))],
        "layers": [layers_node("layers", via.layers)],
        "locked": _lock_items(via.locked),
        "net_id": _opt(nets.node(via.net_id)),
        "native_ids": uuid_items(via.native_ids),
    }


def _pts(points: Sequence[Point]) -> Node:
    return node("pts", *(point_node("xy", p) for p in points))


def form_major(version: int) -> int:
    """The major whose zone setting forms a board of format ``version`` uses: the oldest supported major
    that reads it, and the newest one for a version from the future."""
    major = major_for(FileKind.BOARD, version)
    return max(TARGET_MAJORS) if major is None else major


def _emit_zone(zone: Zone | Keepout, nets: _Nets, *, major: int) -> Items:
    """The modelled fields of a zone or rule area; ``major`` picks the form of the setting children."""
    layers = zone.layers
    items: Items = {
        "layers": [layers_node("layer" if len(layers) == 1 else "layers", layers)],
        "native_ids": uuid_items(zone.native_ids),
        "outline": [node("polygon", _pts(zone.outline))],
    }
    if isinstance(zone, Zone):
        items["net_id"] = _opt(nets.node(zone.net_id, zone=True))
        items["name"] = [node("name", Atom.string(zone.name))]
        items["priority"] = [node("priority", Atom.integer(zone.priority))]
        emitted = zonelib.emit_settings(zone.settings, filled=zone.filled, locked=zone.locked, major=major)
        for head, field in ZONE_SETTING_FIELDS.items():
            items[field] = [emitted[head]] if head in emitted else []
    else:
        items["net_id"] = _opt(nets.node(None, zone=True))
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


# --- paper and title block (change c0012; board.md, "Facts") ----------------------------------------

NAMED_PAPERS = ("A0", "A1", "A2", "A3", "A4", "A5")
TITLE_BLOCK_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "title": "title",
        "date": "date",
        "rev": "revision",
        "company": "organization",
        "comment 1": "doc_id",
        "comment 2": "responsible",
        "comment 3": "approver",
    }
)
"""``title_block`` child (``comment N`` with its number) → ``TitleBlock`` field, in write order."""
PAPER_UNMODELLED = "kicad.board.paper-unmodelled"


def project_paper(node: Node, *, issues: list[Issue] | None = None) -> SheetFrameRef | None:
    """``Board.sheet`` for a ``paper`` child; ``None`` with an info for a name or size the model does not
    name (``USLetter``, ``A`` … ``E``, a size that is not whole nm)."""
    atoms = node.atoms()
    name = atoms[0].value if atoms and atoms[0].kind in (AtomKind.STRING, AtomKind.SYMBOL) else ""
    rest = list(atoms[1:])
    portrait = bool(rest) and rest[-1].kind == AtomKind.SYMBOL and rest[-1].text == "portrait"
    if portrait:
        rest = rest[:-1]
    found: SheetFrameRef | None = None
    if name in NAMED_PAPERS and not rest and not node.nodes():
        found = SheetFrameRef(name, portrait=portrait)  # type: ignore[arg-type]
    elif name == "User" and len(rest) == 2 and not portrait and not node.nodes():
        try:
            width, height = rest[0].to_nm(exact=True), rest[1].to_nm(exact=True)
        except ValueError:
            width = height = 0
        if width > 0 and height > 0:
            found = SheetFrameRef("custom", width=width, height=height)
            for us in US_SIZES:
                w, h = PAPER_SIZES[us]
                if (width, height) in ((w, h), (h, w)):
                    found = SheetFrameRef(us, portrait=width < height)  # type: ignore[arg-type]
                    break
    if found is None and issues is not None:
        issues.append(Issue(PAPER_UNMODELLED, ISSUE_CODES[PAPER_UNMODELLED],
                            f"paper {dumps(node, style='compact')} has no model equivalent; kept as written",
                            where="/kicad_pcb/paper[0]"))  # fmt: skip
    return found


def paper_node(sheet: SheetFrameRef | None) -> Node:
    """The ``paper`` child for ``Board.sheet``: a named A size, or ``"User" W H`` for the US sizes and
    custom pages (KiCad's own US names are never written, ``H-K-PCB-PAPER-2``)."""
    if sheet is None:
        return node("paper", Atom.string("A4"))
    if sheet.paper in NAMED_PAPERS:
        extra = (Atom.symbol("portrait"),) if sheet.portrait else ()
        return node("paper", Atom.string(sheet.paper), *extra)
    if sheet.paper == "custom":
        if sheet.width is None or sheet.height is None:
            raise ValueError("a custom paper needs both width and height (model.sheet-size)")
        width, height = sheet.width, sheet.height
    else:
        short, long = PAPER_SIZES[sheet.paper]
        width, height = (short, long) if sheet.portrait else (long, short)
    return node("paper", Atom.string("User"), Atom.from_nm(width), Atom.from_nm(height))


def _title_key(child: Node) -> str | None:
    atoms = child.atoms()
    if child.name == "comment" and atoms and atoms[0].kind == AtomKind.NUMBER:
        key = f"comment {atoms[0].text}"
        return key if key in TITLE_BLOCK_FIELDS else None
    return child.name if child.name in TITLE_BLOCK_FIELDS else None


def _title_value(child: Node) -> str | None:
    atoms = [a for a in child.atoms() if a.kind == AtomKind.STRING]
    return atoms[-1].value if atoms else None


def project_title_block(node: Node) -> TitleBlock:
    """The seven mapped fields of a ``title_block`` child; ``comment 4`` … ``comment 9`` and unknown
    children stay in the fragment unmapped."""
    values: dict[str, str] = {}
    for child in node.nodes():
        key = _title_key(child)
        value = _title_value(child)
        if key is not None and value is not None and TITLE_BLOCK_FIELDS[key] not in values:
            values[TITLE_BLOCK_FIELDS[key]] = value
    return TitleBlock(
        title=values.get("title", ""),
        date=values.get("date", ""),
        revision=values.get("revision", ""),
        organization=values.get("organization", ""),
        doc_id=values.get("doc_id", ""),
        responsible=values.get("responsible", ""),
        approver=values.get("approver", ""),
    )


def _title_child(key: str, value: str) -> Node:
    if key.startswith("comment "):
        return node("comment", Atom.integer(int(key.split()[1])), Atom.string(value))
    return node(key, Atom.string(value))


def title_block_node(block: TitleBlock) -> Node:
    """The non-empty fields of ``block`` in the order ``title``, ``date``, ``rev``, ``company``,
    ``comment 1`` … ``comment 3``."""
    children = [
        _title_child(k, getattr(block, f)) for k, f in TITLE_BLOCK_FIELDS.items() if getattr(block, f)
    ]
    return node("title_block", *children)


def _block_fields(block: TitleBlock | None) -> TitleBlock:
    """``block`` without parameters (they come from the project); ``None`` counts as ``TitleBlock()``."""
    return TitleBlock() if block is None else dataclasses.replace(block, params={})


def has_title(block: TitleBlock | None) -> bool:
    return _block_fields(block) != TitleBlock()


def rewrite_title_block(fragment: Node, block: TitleBlock | None) -> Node:
    """``fragment`` with each mapped child set from ``block`` in place: changed values replaced, newly set
    fields inserted at the place their order gives among the mapped children, emptied ones removed;
    every other child kept tree-equal at its position."""
    order = list(TITLE_BLOCK_FIELDS)
    wanted = {k: getattr(_block_fields(block), f) for k, f in TITLE_BLOCK_FIELDS.items()}
    children: list[Node | Atom] = []
    present: list[str] = []
    for child in fragment.children:
        key = _title_key(child) if isinstance(child, Node) else None
        if key is None or key in present:
            children.append(child)
            continue
        present.append(key)
        if not wanted[key]:
            continue
        if _title_value(child) != wanted[key]:  # type: ignore[arg-type]
            child = _title_child(key, wanted[key])
        children.append(child)
    for key in order:
        if not wanted[key] or key in present:
            continue
        index = order.index(key)
        before = [k for k in order[:index] if k in present and wanted[k]]
        positions = {
            _title_key(c): i
            for i, c in enumerate(children)
            if isinstance(c, Node) and _title_key(c) is not None
        }
        if before:
            at = positions[before[-1]] + 1
        else:
            after = [positions[k] for k in order[index + 1 :] if k in positions]
            at = min(after) if after else len(children)
        children.insert(at, _title_child(key, wanted[key]))
        present.append(key)
    return fragment.with_children(children)


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
        names = {n.id: stored_net_name(n) for n in self.design.circuit.nets}
        return _Nets(self.net_form, names, self.net_numbers)

    @cached_property
    def version(self) -> int:
        board = self.design.board
        return int(_ext_pairs(board).get("version", "0")) if board is not None else 0

    @cached_property
    def major(self) -> int:
        return form_major(self.version)

    @cached_property
    def pad_rotation(self) -> dict[str, Udeg]:
        board = self.design.board
        return {pad.id: fp.rotation for fp in (board.footprints if board else ()) for pad in fp.pads}

    @cached_property
    def field_rotation(self) -> dict[str, Udeg]:
        board = self.design.board
        return {f.id: fp.rotation for fp in (board.footprints if board else ()) for f in fp.fields}


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
        items["nets"] = [_net_row(ctx.net_numbers[n.id], stored_net_name(n)) for n in rows]
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
        items["fields"] = [_rebuild(f, "property", ctx) for f in _sorted(entity.fields)]
    elif isinstance(entity, FootprintField):
        items = _emit_field(entity, ctx.field_rotation.get(entity.id, 0))
    elif isinstance(entity, Pad):
        items = _emit_board_pad(entity, ctx.pad_rotation.get(entity.id, 0), ctx.nets)
    elif isinstance(entity, (Track, Arc)):
        items = _emit_track(entity, ctx.nets)
    elif isinstance(entity, Via):
        items = _emit_via(entity, ctx.nets)
    elif isinstance(entity, (Zone, Keepout)):
        items = _emit_zone(entity, ctx.nets, major=ctx.major)
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
        fields: list[FootprintField] = []
        names: set[str] = set()
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
                if not is_placed_property(child):
                    self.keep(slots, index, child, FP_ROOT)  # read as before: a projected slot
                    continue
                name = atoms[0].value
                if name in names:
                    self.keep_unmodelled(
                        f"a second property named {name!r}; kept as written",
                        slots,
                        index,
                        child,
                        child_loc,
                        FP_ROOT,
                    )
                    continue
                names.add(name)
                try:
                    fields.append(self.field(child, child_loc, key, rotation))
                except InexactValueError as error:
                    self.keep_inexact(error, slots, index, child, FP_ROOT)
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
                local_rotation = pad_angle_from_board(pad.rotation, rotation)
                pad = dataclasses.replace(pad, rotation=local_rotation)
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
            fields=tuple(fields),
        )
        self.check(item, loc, slots, _emit_footprint(instance, path), FP_ROOT, nested=("pads", "fields"))
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

    def field(self, item: Node, loc: str, key: str, rotation: Udeg) -> FootprintField:
        """A placed ``property`` as a field: placement and appearance only (``board.md``, "Footprint
        fields"). ``key`` is the native id behind the footprint's pad ids."""
        ctx = self.ctx
        slots = ctx.split(item, dict(FIELD_FIELDS), FIELD_CHAIN, FIELD_POSITIONAL)
        name = leading_atoms(item)[0].value
        at, layer, effects, uuid = (
            item.find("at"),
            item.find("layer"),
            item.find("effects"),
            item.find("uuid"),
        )
        assert at is not None and layer is not None and effects is not None
        font = effects.find("font")
        assert font is not None
        size_node, thickness_node = font.find("size"), font.find("thickness")
        assert size_node is not None
        at_loc, font_loc = f"{loc}/at[0]", f"{loc}/effects[0]/font[0]"
        position = ctx.point(at, at_loc)
        values = at.atoms()
        stored = ctx.udeg(values[2], at_loc, at) if len(values) > 2 else 0
        size = ctx.point(size_node, f"{font_loc}/size[0]")
        thickness = (
            self.nm_of(thickness_node, f"{font_loc}/thickness[0]") if thickness_node is not None else None
        )
        h_justify, v_justify, mirrored = field_justify(effects)
        layers = layer.atoms()
        ids = uuid.atoms() if uuid is not None else ()
        field = FootprintField(
            id=derived_id("fld", "kicad", f"{key}:field:{name}"),
            native_ids={"kicad": ids[0].value} if ids else {},
            provenance=ctx.provenance(loc),
            name=name,
            position=position,
            layer=layers[0].value if layers else "",
            size=Size(size.y, size.x),
            rotation=pad_angle_from_board(stored, rotation),
            thickness=thickness,
            visible=not field_hidden(item),
            h_justify=h_justify,
            v_justify=v_justify,
            mirrored=mirrored,
        )
        self.check(item, loc, slots, _emit_field(field, rotation), FIELD_CHAIN)
        return dataclasses.replace(field, ext={"kicad": slotlib.to_ext(slots)})

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
        locked = False
        for index, (child_loc, child) in enumerate(child_locators(loc, item)):
            if not isinstance(child, Node):
                continue
            head = child.name
            if head == "locked":
                locked = symbols(child) != ["no"]
            elif head in ("start", "mid", "end"):
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
                locked=locked,
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
                locked=locked,
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
        locked = False
        for index, (child_loc, child) in enumerate(child_locators(loc, item)):
            if not isinstance(child, Node):
                continue
            head = child.name
            if head == "at":
                position = ctx.point(child, child_loc)
            elif head == "locked":
                locked = symbols(child) != ["no"]
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
            locked=locked,
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
        major = form_major(ctx.version)
        read = zonelib.project_settings(item.nodes() if keepout_node is None else (), major=major)
        for index, (child_loc, child) in enumerate(child_locators(loc, item)):
            if not isinstance(child, Node):
                continue
            head = child.name
            if head in read.reasons:
                # a setting child outside the model: kept as written, its readable values projected
                reason = read.reasons[head]
                if head in read.inexact:
                    what = "angle" if "angle" in reason else "length"
                    self.issue(f"kicad.board.inexact-{what}", f"{reason}; kept as written", child_loc)
                    self.keep(slots, index, child, chain)
                else:
                    self.keep_unmodelled(f"{reason}; kept as written", slots, index, child, child_loc, chain)
            elif head == "net":
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
                settings=read.settings,
                filled=read.filled,
                locked=read.locked,
            )
        emitted = _emit_zone(entity, self.emit_nets, major=major)
        self.check(item, loc, slots, emitted, chain, nested=("fills",))
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
        paper, block = root.find("paper"), root.find("title_block")
        sheet = project_paper(paper, issues=ctx.issues) if paper is not None else None
        title_block = project_title_block(block) if block is not None else None
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
            sheet=sheet,
            title_block=title_block,
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
                ext=self.net_ext(entry),
                name=self.model_net_name(entry),
                members=tuple(members[entry.id]),
            )
            for entry in self.nets.values()
        )

    def net_ext(self, entry: _NetEntry) -> dict[str, ExtBag]:
        """The ``kicad`` bag of a net: its table number, and its stored spelling when the model name
        differs from it."""
        pairs: list[tuple[str, str]] = []
        if entry.number is not None:
            pairs.append(("number", str(entry.number)))
        if self.model_net_name(entry, report=False) != entry.name:
            pairs.append((STORED_KEY, entry.name))
        return {"kicad": ExtBag(None, tuple(pairs))} if pairs else {}

    def model_net_name(self, entry: _NetEntry, *, report: bool = True) -> str:
        """The model name of a net: ``{slash}`` in a stored name is the slash of a label text, unless
        another net of the board already has that name (``kicad.board.net-name-collision``)."""
        if netnames.SLASH not in entry.name:
            return entry.name
        name = netnames.model_name(entry.name)
        if name in self.nets:
            if report:
                self.issue(
                    "kicad.board.net-name-collision",
                    f"net {entry.name!r} would be named {name!r}, which another net of the board is "
                    "named; it keeps its stored spelling",
                    entry.locator,
                )
            return entry.name
        return name


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


# --- writing --------------------------------------------------------------------------------------

WRITE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PCB-WRITE",))
"""Writing arbitrary designs stays ``INFERRED``: ``kicad-cli`` checks only the test boards' shape."""
WRITE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        _pcbwrite.DROPPED_CODE: "warning",
        _pcbwrite.OBSOLETE_CODE: "info",
        _pcbwrite.NET_REF_CODE: "error",
        "kicad.board.projection-read-only": "error",
        "kicad.board.outline-conflict": "error",
        "kicad.board.flip-unsupported": "error",
    }
)
CREATED_ROOT_HEADS: tuple[str, ...] = (
    "version", "generator", "generator_version", "general", "paper", "layers", "setup", "net",
)  # fmt: skip
"""The root head set of a created board: c0007's skeleton (``net`` for target 9 only)."""
FLOOR_HEADS: tuple[str, ...] = (
    "arc", "attr", "center", "comment", "company", "copperpour", "date", "filled_polygon", "footprints",
    "gr_arc", "gr_circle", "gr_line", "gr_poly", "gr_text", "hatch_border_algorithm", "hatch_gap",
    "hatch_min_hole_area", "hatch_orientation", "hatch_smoothing_level", "hatch_smoothing_value",
    "hatch_thickness", "hide", "island", "island_area_min", "island_removal_mode", "justify", "keepout",
    "locked", "mid", "mode", "name", "pads", "path", "priority", "radius", "rev", "smoothing", "title",
    "title_block", "tracks", "vias", "zone_connect",
)  # fmt: skip
"""Names the writer creates that the 8.0 format already has and that neither the token inventory nor
the skeleton holds (``board.md``, S-0021 and S-0033 at tag 8.0.0)."""
CANONICAL_ORDER: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "kicad_pcb": (
            *CREATED_ROOT_HEADS[:5], "title_block", *CREATED_ROOT_HEADS[5:], "footprint", *GR_GRAPHIC_HEADS,
            "gr_text", "segment", "arc", "via", "zone",
        ),
        "title_block": ("title", "date", "rev", "company", "comment"),
        "footprint": (
            *FOOTPRINT_POSITIONAL, "locked", "layer", "uuid", "at", "property", "path", "attr", "pad",
        ),
        "property": ("name", "value", "at", "layer", "hide", "uuid", "effects"),
        "effects": ("font", "justify"),
        "font": ("size", "thickness"),
        "pad": (*PAD_POSITIONAL, "at", "size", "drill", "layers", "net", "zone_connect", "uuid"),
        "segment": ("start", "end", "width", "locked", "layer", "net", "uuid"),
        "arc": ("start", "mid", "end", "width", "locked", "layer", "net", "uuid"),
        "via": (*VIA_POSITIONAL, "at", "size", "drill", "layers", "locked", "net", "uuid"),
        "zone": (
            "net", "net_name", "locked", "layer", "layers", "uuid", "name", "hatch", "priority",
            "connect_pads", "min_thickness", "filled_areas_thickness", "keepout", "fill", "polygon",
            "filled_polygon",
        ),
        "connect_pads": ("connection", "clearance"),
        "fill": (
            "filled", "mode", "thermal_gap", "thermal_bridge_width", "smoothing", "radius",
            "island_removal_mode", "island_area_min", "hatch_thickness", "hatch_gap", "hatch_orientation",
            "hatch_smoothing_level", "hatch_smoothing_value", "hatch_border_algorithm", "hatch_min_hole_area",
        ),
        "polygon": ("pts",),
        "filled_polygon": ("layer", "island", "pts"),
        "keepout": tuple(head for head, _ in KEEPOUT_SETTINGS),
        "pts": ("xy",),
        "gr_line": ("start", "end", "stroke", "layer", "uuid"),
        "gr_arc": ("start", "mid", "end", "stroke", "layer", "uuid"),
        "gr_circle": ("center", "end", "stroke", "fill", "layer", "uuid"),
        "gr_rect": ("start", "end", "stroke", "fill", "layer", "uuid"),
        "gr_poly": ("pts", "stroke", "fill", "layer", "uuid"),
        "stroke": ("width", "type"),
        "gr_text": (*TEXT_POSITIONAL, "at", "layer", "uuid", "effects"),
    }
)  # fmt: skip
"""Per head the writer can create: positional fields, then children in the order KiCad 9.0 and 10.0
write them (``board.md``, observed in KiCad-written boards; never taken from KiCad's code)."""
POSITIONAL: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "footprint": FOOTPRINT_POSITIONAL,
        "property": ("name", "value"),
        "pad": PAD_POSITIONAL,
        "via": VIA_POSITIONAL,
        "connect_pads": ("connection",),
        "fill": ("filled",),
        "gr_text": TEXT_POSITIONAL,
    }
)
"""The entries of ``CANONICAL_ORDER`` that are leading atoms, not child heads."""
FILLED_AREAS_THIN: Node = node("filled_areas_thickness", Atom.symbol("no"))
"""What a created zone writes for target 9, so that its fill polygons are read as areas and not as
outlines drawn with a pen of the minimum thickness (``board.md``, ``H-K-ZONE-FAT9``)."""
DEFAULT_THICKNESS = 1_600_000
"""Board thickness of a created board without a stack-up (the skeleton's value)."""
OUTLINE_WIDTH = 100_000
TEXT_SIZE = Size(1_000_000, 1_000_000)
TEXT_THICKNESS = 150_000
_GRAPHIC_WRITE_FIELDS: Mapping[str, str] = MappingProxyType({**GRAPHIC_FIELDS, "stroke": "width"})
_WRITE_FIELDS: Mapping[str, Mapping[str, str | tuple[str, ...]]] = MappingProxyType(
    {
        "kicad_pcb": {
            **ROOT_FIELDS, "general": "general", "paper": "paper", "title_block": "title_block",
            "setup": "setup", "zone": ("zones", "keepouts"),
        },
        "footprint": {**FOOTPRINT_FIELDS, "locked": "locked", "property": ("fields", "properties")},
        "property": {**FIELD_FIELDS},
        "pad": BOARD_PAD_FIELDS,
        "segment": TRACK_FIELDS,
        "arc": TRACK_FIELDS,
        "via": VIA_FIELDS,
        "zone": ZONE_FIELDS,
        "filled_polygon": FILL_FIELDS,
        **dict.fromkeys(GR_GRAPHIC_HEADS, _GRAPHIC_WRITE_FIELDS),
        "gr_text": {**TEXT_FIELDS, "effects": "effects"},
    }
)  # fmt: skip
_READ_FIELDS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "kicad_pcb": ROOT_FIELDS,
        "footprint": FOOTPRINT_FIELDS,
        "property": FIELD_FIELDS,
        "pad": BOARD_PAD_FIELDS,
        "segment": TRACK_FIELDS,
        "arc": TRACK_FIELDS,
        "via": VIA_FIELDS,
        "zone": ZONE_FIELDS,
        "filled_polygon": FILL_FIELDS,
        **dict.fromkeys(GR_GRAPHIC_HEADS, GRAPHIC_FIELDS),
        "gr_text": TEXT_FIELDS,
    }
)
"""The field maps of the reader: which opaque children stand for a model value."""
COLLECTION_FIELDS: frozenset[str] = frozenset(
    {"nets", "footprints", "tracks", "arcs", "vias", "zones", "keepouts", "texts", "pads", "fills", "fields"}
    | {f"graphics.{head}" for head in GR_GRAPHIC_HEADS}
)
"""Fields that hold whole items; an opaque item never stands for a model value."""
_KIND_HEADS: Mapping[str, str] = MappingProxyType({kind: head for head, kind in GR_GRAPHIC_HEADS.items()})
_FILLED_KINDS = frozenset({"circle", "rect", "polygon"})
READ_ONLY_CODE = "kicad.board.projection-read-only"


def kicad_uuid(entity: Entity, part: str = "") -> str:
    """The KiCad uuid the writer gives ``entity`` (or one of its parts without an id of its own)."""
    if not part:
        native = entity.native_ids.get("kicad")
        if native is not None:
            return native
    return str(uuid.uuid5(FENOLITE_NS, f"kicad-out:{entity.id}" + (f":{part}" if part else "")))


def source_info(design: Design) -> FormatInfo | None:
    """The header of the file a design was read from, or ``None`` for a created design."""
    board = design.board
    pairs = _ext_pairs(board) if board is not None else {}
    if "version" not in pairs:
        return None
    version = int(pairs["version"])
    kind = FileKind.BOARD
    return FormatInfo(
        kind,
        version,
        major_for(kind, version),
        classify(kind, version),
        pairs.get("generator"),
        pairs.get("generator_version"),
    )


def _canonical_fields(head: str) -> tuple[str, ...]:
    """``CANONICAL_ORDER[head]`` in the field names of the writer's sources."""
    order = CANONICAL_ORDER.get(head)
    if order is None:
        raise ValueError(f"no canonical order for head {head!r}")
    fields = _WRITE_FIELDS.get(head, {})
    out: list[str] = []
    for name in order:
        mapped = fields.get(name, name)
        for field in (mapped,) if isinstance(mapped, str) else mapped:
            if field not in out:
                out.append(field)
    return tuple(out)


def _ordered(head: str, items: Mapping[str, Sequence[Node | Atom]]) -> Node:
    """A created node whose children follow ``CANONICAL_ORDER[head]``."""
    order = CANONICAL_ORDER.get(head)
    if order is None:
        raise ValueError(f"no canonical order for head {head!r}")
    for name, values in items.items():
        if values and name not in order:
            raise ValueError(f"{head}: field {name!r} has no position in CANONICAL_ORDER")
    return Node(Atom.symbol(head), tuple(child for name in order for child in items.get(name, ())))


def _uuid_node(value: str) -> Node:
    return node("uuid", Atom.string(value))


def _stroke(width: int) -> Node:
    return _ordered(
        "stroke",
        {"width": [node("width", Atom.from_nm(width))], "type": [node("type", Atom.symbol("solid"))]},
    )


def _effects(size: Size, thickness: int, *, mirror: bool) -> Node:
    font = _ordered(
        "font",
        {
            "size": [node("size", Atom.from_nm(size.h), Atom.from_nm(size.w))],
            "thickness": [node("thickness", Atom.from_nm(thickness))],
        },
    )
    justify: list[Node | Atom] = [node("justify", Atom.symbol("mirror"))] if mirror else []
    return _ordered("effects", {"font": [font], "justify": justify})


def _locator(entity: Entity) -> str:
    return entity.provenance.locator if entity.provenance is not None else entity.id


def _child_locator(entity: Entity, slots: Sequence[Slot], index: int, head: str, field: str) -> str:
    """The locator of the opaque child at ``slots[index]``: the entity's, then ``/head[k]`` (k counts the
    earlier children of that head, modelled or opaque)."""
    k = 0
    for slot in slots[:index]:
        if isinstance(slot, Modeled):
            k += slot.field == field
        else:
            k += _fragment_head(slot) == head
    return f"{_locator(entity)}/{head}[{k}]"


def _write_order(entities: Iterable[E]) -> list[E]:
    """Read entities in file order, then created ones in model order."""
    return sorted(entities, key=lambda e: (0, _index(e)[1]) if _index(e)[1] >= 0 else (1, 0))


def _graphic_head(graphic: Graphic) -> str:
    head = _index(graphic)[0]
    return head if head in GR_GRAPHIC_HEADS else _KIND_HEADS[graphic.kind]


def _decimal(atom: Atom) -> Decimal | str:
    return Decimal(atom.text) if atom.kind == AtomKind.NUMBER else atom.value


def _mm(nm: int) -> Decimal:
    return Decimal(nm).scaleb(-6)


def _key(child: Node, copper: Sequence[str]) -> object:
    """What a child means to the model, so a respelled child compares equal to the emitter's."""
    head = child.name
    atoms = child.atoms()
    values = tuple(_decimal(a) for a in atoms)
    if head == "at":
        return values + (Decimal(0),) * (3 - len(values))
    if head == "drill":
        simple = len(atoms) == 1 and atoms[0].kind == AtomKind.NUMBER
        lists = [c.name for c in child.nodes()]
        return values[0] if simple and lists in ([], ["offset"]) else None
    if head == "layers":
        names = tuple(a.value for a in atoms)
        return expand_layers(names, copper) if has_wildcard(names) else names
    if head == "layer":
        return values[:1]
    if head == "fill":
        return {"yes": True, "solid": True, "no": False, "none": False}.get(atoms[0].value) if atoms else None
    if head == "island":
        return symbols(child) in ([], ["yes"])
    if head == "attr":
        return tuple(a.value for a in atoms if a.value in FOOTPRINT_ATTRIBUTES)
    return (head, values, tuple(_key(c, copper) for c in child.nodes()))


def _spelling_only(child: Node, new: Node | None) -> bool:
    """Whether ``child`` holds nothing beyond what the emitter writes for its head, so it can be
    written from the model (Decision 10 of c0017)."""
    head = child.name
    atoms = child.atoms()
    if head == "pts":
        return not atoms and all(c.name == "xy" and _plain_numbers(c, 2) for c in child.nodes())
    if child.nodes():
        return False
    if head == "at":
        return _plain_numbers(child, 2) or _plain_numbers(child, 3)
    if head == "layers":
        names = [a.value for a in atoms]
        return all(a.kind != AtomKind.NUMBER for a in atoms) and not has_wildcard(names)
    if head == "attr":
        return all(a.kind == AtomKind.SYMBOL and a.value in FOOTPRINT_ATTRIBUTES for a in atoms)
    if head == "fill":
        return len(atoms) == 1 and atoms[0].value in ("yes", "solid", "no", "none")
    if new is None:
        return False
    expected = new.atoms()
    if new.nodes() or len(atoms) != len(expected):
        return False
    return all(
        (a.kind == AtomKind.NUMBER) == (b.kind == AtomKind.NUMBER)
        for a, b in zip(atoms, expected, strict=True)
    )


def _plain_numbers(child: Node, count: int) -> bool:
    atoms = child.atoms()
    return not child.nodes() and len(atoms) == count and all(a.kind == AtomKind.NUMBER for a in atoms)


def _at_key(child: Node) -> tuple[Decimal, Decimal, Decimal] | None:
    """``(x, y, angle mod 360)`` of an ``at`` child, so ``-90`` and ``270`` compare equal."""
    atoms = child.atoms()
    if child.nodes() or len(atoms) not in (2, 3) or any(a.kind != AtomKind.NUMBER for a in atoms):
        return None
    x, y = Decimal(atoms[0].text), Decimal(atoms[1].text)
    angle = Decimal(atoms[2].text) if len(atoms) > 2 else Decimal(0)
    return x, y, (angle % 360 + 360) % 360  # Decimal's remainder keeps the sign of the dividend


def _effects_values(
    effects: Node,
) -> tuple[Size, int | None, FieldJustifyH, FieldJustifyV, bool] | None:
    """What the reader projects from a field's ``effects``, or ``None`` when its numbers are not exact."""
    font = effects.find("font")
    size = font.find("size") if font is not None else None
    thickness = font.find("thickness") if font is not None else None
    if font is None or size is None or len(size.atoms()) < 2:
        return None
    try:
        h, w = size.atoms()[0].to_nm(exact=True), size.atoms()[1].to_nm(exact=True)
        stroke = thickness.atoms()[0].to_nm(exact=True) if thickness is not None else None
    except (ValueError, IndexError):
        return None
    h_justify, v_justify, mirrored = field_justify(effects)
    return Size(w, h), stroke, h_justify, v_justify, mirrored


def field_value_slot(slots: Sequence[Slot]) -> int | None:
    """The index of the value atom in a field's slot list: its second leading atom, an opaque slot."""
    leading = 0
    for index, slot in enumerate(slots):
        if isinstance(slot, Modeled):
            if slot.field != "name":
                return None
            leading += 1
            continue
        if not isinstance(slotlib.opaque_child(slot), Atom):
            return None
        if leading == 1:
            return index
        leading += 1
    return None


def field_value(field: FootprintField) -> str | None:
    """The text that a read field's node holds (its value atom), or ``None`` without a slot list."""
    bag = field.ext.get("kicad")
    slots = slotlib.from_ext(bag) if bag is not None else ()
    index = field_value_slot(slots)
    if index is None:
        return None
    child = slotlib.opaque_child(slots[index])  # type: ignore[arg-type]
    return child.value if isinstance(child, Atom) else None


class _Writer:
    """One design being written for one target: its emitters, projections and collected errors."""

    def __init__(self, design: Design, target: int) -> None:
        board = design.board
        assert board is not None
        self.design = design
        self.board = board
        self.target = target
        self.version = FORMAT_VERSIONS[FileKind.BOARD][target]
        self.errors: list[Issue] = []
        self.components = {c.id: c for c in design.circuit.components}
        self.nets = _Nets("neutral", {n.id: stored_net_name(n) for n in design.circuit.nets}, {})
        self.pad_rotation = {pad.id: fp.rotation for fp in board.footprints for pad in fp.pads}
        self.field_owner = {f.id: fp for fp in board.footprints for f in fp.fields}
        self.copper = tuple(layer.name for layer in board.layers if layer.kind == "copper")
        self.opaque_ids: set[int] = set()

    def error(self, code: str, message: str, where: str) -> None:
        self.errors.append(Issue(code, WRITE_ISSUE_CODES[code], message, where=where))

    def read_only(self, field: str, where: str, detail: str) -> None:
        self.error(READ_ONLY_CODE, f"field {field!r} cannot be written from the model: {detail}", where)

    def opaque(self, slot: Opaque) -> Node | Atom:
        child = slotlib.opaque_child(slot)
        if isinstance(child, Node):
            self.opaque_ids.add(id(child))
        return child

    def source_table(self) -> dict[int, str]:
        return {
            int(_ext_pairs(n)["number"]): n.name
            for n in self.design.circuit.nets
            if "number" in _ext_pairs(n)
        }

    # -- nodes

    def node(
        self, entity: Entity, head: str, items: Items, slots: Sequence[Slot], absent: Collection[str] = ()
    ) -> Node:
        """``head`` rebuilt from ``slots`` (none for a created entity) and the writer's ``items``.

        A field without a modelled slot is written only when it is not in ``absent``, the fields whose
        model value is the one the reader gives a missing child.
        """
        canonical = _canonical_fields(head)
        slot_list = list(slots)
        if not slot_list:
            covered = set[str]()
        elif isinstance(entity, FootprintField):
            covered = self.reconcile_field(entity, slot_list, items)
        else:
            covered = self.reconcile(entity, head, slot_list, items)
        modeled = _modeled(slot_list)
        skip = covered | modeled | set(absent)
        wanted = modeled | {f for f, v in items.items() if v and f not in skip}
        for field in sorted(wanted - modeled):
            if field not in canonical:
                raise ValueError(f"{head}: field {field!r} has no position in CANONICAL_ORDER")
        source = ModelSource({f: v for f, v in items.items() if f in wanted})
        return slotlib.rebuild(Atom.symbol(head), slot_list, source, canonical=canonical, opaque=self.opaque)

    def entity(self, entity: Entity, head: str) -> Node:
        bag = entity.ext.get("kicad")
        slots = slotlib.from_ext(bag) if bag is not None else ()
        created = not slots
        items = self.items(entity, head, created=created)
        return self.node(entity, head, items, slots, self.absent(entity, created))

    def absent(self, entity: Entity, created: bool) -> set[str]:
        """Fields whose model value is what the reader gives a missing child."""
        if isinstance(entity, Graphic):
            return (
                set()
                if created
                else {f for f, unset in (("width", not entity.width), ("filled", not entity.filled)) if unset}
            )
        if isinstance(entity, Zone):
            unset = {
                f for f, unset in (("name", not entity.name), ("priority", not entity.priority)) if unset
            }
            if created:
                return unset
            # a read zone gains a setting child only when its part of the model left the defaults
            parts = zonelib.setting_parts(entity.settings, filled=entity.filled, locked=entity.locked)
            return unset | {
                field
                for head, field in ZONE_SETTING_FIELDS.items()
                if parts[head] == zonelib.DEFAULT_PARTS[head]
            }
        if isinstance(entity, FootprintInstance):
            component = self.components.get(entity.component_id)
            path = component.path if component is not None else ""
            return {f for f, unset in (("attributes", not entity.attributes), ("path", not path)) if unset}
        if isinstance(entity, FootprintField):
            return set() if "kicad" in entity.native_ids else {"native_ids"}
        return set()

    def items(self, entity: Entity, head: str, *, created: bool) -> Items:
        """Every field the writer can emit for ``entity``, with its current model value."""
        items: Items
        if isinstance(entity, FootprintInstance):
            items = self.footprint(entity, created=created)
        elif isinstance(entity, FootprintField):
            owner = self.field_owner.get(entity.id)
            items = _emit_field(entity, owner.rotation if owner is not None else 0)
        elif isinstance(entity, Pad):
            rotation = self.pad_rotation.get(entity.id, 0)
            net = self.nets.node(entity.net_id, pad=True)
            items = emit_pad(entity, net, angle=pad_angle_to_board(entity.rotation, rotation))
        elif isinstance(entity, (Track, Arc)):
            items = _emit_track(entity, self.nets)
        elif isinstance(entity, Via):
            items = _emit_via(entity, self.nets)
        elif isinstance(entity, (Zone, Keepout)):
            items = _emit_zone(entity, self.nets, major=self.target)
            if isinstance(entity, Zone):
                items["fills"] = [self.fill(entity, k, fill) for k, fill in enumerate(entity.fills)]
                if created:
                    items["hatch"] = [zonelib.HATCH_EDGE]
                    if self.target < 10:
                        items["filled_areas_thickness"] = [FILLED_AREAS_THIN]
        elif isinstance(entity, Text):
            items = _emit_text(entity)
            items["effects"] = [_effects(entity.size, entity.thickness, mirror=entity.layer.startswith("B."))]
        elif isinstance(entity, Graphic):
            items = emit_graphic(entity, head)
            if created:
                items["width"] = [_stroke(entity.width)]
                if entity.kind not in _FILLED_KINDS:
                    items["filled"] = []
        else:
            raise TypeError(f"no KiCad board writer for {type(entity).__name__}")
        items["native_ids"] = [_uuid_node(kicad_uuid(entity))]
        return items

    def footprint(self, fp: FootprintInstance, *, created: bool) -> Items:
        component = self.components.get(fp.component_id)
        path = component.path if component is not None else ""
        items = _emit_footprint(fp, path)
        items["locked"] = [node("locked", Atom.symbol("yes"))] if fp.locked else []
        names = [f.name for f in fp.fields]
        for name in names:
            if names.count(name) > 1:
                raise ValueError(f"{_locator(fp)}: two fields are named {name!r}")
        if created:
            items["fields"] = []
            items["properties"] = self.properties(fp, component)
        else:
            for field in fp.fields:
                bag = field.ext.get("kicad")
                if bag is None or not slotlib.from_ext(bag):
                    raise ValueError(
                        f"{_locator(fp)}: field {field.name!r} has no KiCad slot list; a field cannot be "
                        "added to a footprint read from a board"
                    )
            items["fields"] = [self.entity(f, "property") for f in _write_order(fp.fields)]
            items["properties"] = [] if fp.fields else self.properties(fp, component)
        items["pads"] = [self.entity(pad, "pad") for pad in _write_order(fp.pads)]
        return items

    def properties(self, fp: FootprintInstance, component: Component | None) -> list[Node | Atom]:
        """The properties of a created footprint: Reference, Value, then the others by name. A property
        takes its placement from the field of its name; a field whose name the component lacks is refused."""
        known = {"Reference", "Value", *(component.properties if component is not None else ())}
        for field in fp.fields:
            if component is None or field.name not in known:
                raise ValueError(
                    f"{_locator(fp)}: field {field.name!r} names no property of the footprint's component"
                )
        if component is None:
            return []
        values = {k: v for k, v in component.properties.items() if k not in ("Reference", "Value")}
        rows = [("Reference", component.ref), ("Value", component.value), *sorted(values.items())]
        bottom = fp.side == "bottom"
        fields = {f.name: f for f in fp.fields}
        out: list[Node | Atom] = []
        for name, value in rows:
            field = fields.get(name)
            if field is not None:
                emitted = _emit_field(field, fp.rotation)
                placed: Items = {
                    "name": [Atom.string(name)],
                    "value": [Atom.string(value)],
                    "at": emitted["position"],
                    "layer": emitted["layer"],
                    "hide": emitted["visible"],
                    "uuid": [_uuid_node(kicad_uuid(field))],
                    "effects": emitted["effects"],
                }
                out.append(_ordered("property", placed))
                continue
            layer = ("B." if bottom else "F.") + ("SilkS" if name == "Reference" else "Fab")
            out.append(
                _ordered(
                    "property",
                    {
                        "name": [Atom.string(name)],
                        "value": [Atom.string(value)],
                        "at": [at_node(Point(0, 0), fp.rotation, always=True)],
                        "layer": [node("layer", Atom.string(layer))],
                        "uuid": [_uuid_node(kicad_uuid(fp, f"property:{name}"))],
                        "effects": [_effects(TEXT_SIZE, TEXT_THICKNESS, mirror=bottom)],
                    },
                )
            )
        return out

    def fill(self, zone: Zone, k: int, fill: ZoneFill) -> Node:
        bag = zone.ext.get("kicad")
        slots = slotlib.from_ext(bag, f"fill[{k}]") if bag is not None else ()
        items = _emit_fill(fill, self.version)
        return self.node(zone, "filled_polygon", items, slots, () if fill.island else ("island",))

    def root(self) -> Node:
        board = self.board
        bag = board.ext.get("kicad")
        slots = slotlib.from_ext(bag) if bag is not None else ()
        items: Items = {
            "version": [node("version", Atom.integer(self.version))],
            "generator": [node("generator", Atom.string(GENERATOR))],
            "generator_version": [node("generator_version", Atom.string(f"{self.target}.0"))],
            "layers": [_emit_layers(board.layers)],
        }
        if not slots:
            stack = board.stackup.layers if board.stackup is not None else ()
            thickness = sum(layer.thickness for layer in stack) or DEFAULT_THICKNESS
            general = node(
                "general",
                node("thickness", Atom.from_nm(thickness)),
                node("legacy_teardrops", Atom.symbol("no")),
            )
            items["general"] = [general]
            items["paper"] = [paper_node(board.sheet)]
            if has_title(board.title_block):
                items["title_block"] = [title_block_node(_block_fields(board.title_block))]
            items["setup"] = [node("setup", node("pad_to_mask_clearance", Atom.integer(0)))]
        else:
            slots = _with_title_block(list(slots), board.title_block)
            rows = _sorted(n for n in self.design.circuit.nets if "number" in _ext_pairs(n))
            items["nets"] = [_net_row(int(_ext_pairs(n)["number"]), stored_net_name(n)) for n in rows]
        items["footprints"] = [self.entity(fp, "footprint") for fp in _write_order(board.footprints)]
        items["tracks"] = [self.entity(t, "segment") for t in _write_order(board.tracks)]
        items["arcs"] = [self.entity(a, "arc") for a in _write_order(board.arcs)]
        items["vias"] = [self.entity(v, "via") for v in _write_order(board.vias)]
        items["zones"] = [self.entity(z, "zone") for z in _write_order(board.zones)]
        items["keepouts"] = [self.entity(k, "zone") for k in _write_order(board.keepouts)]
        items["texts"] = [self.entity(t, "gr_text") for t in _write_order(board.texts)]
        for head in GR_GRAPHIC_HEADS:
            graphics = [g for g in _write_order(board.graphics) if _graphic_head(g) == head]
            items[f"graphics.{head}"] = [self.entity(g, head) for g in graphics]
        items["graphics.gr_line"] += self.outline()
        return self.node(board, "kicad_pcb", items, slots)

    def outline(self) -> list[Node | Atom]:
        """One ``gr_line`` on ``Edge.Cuts`` per edge of each ring of ``Board.outline``."""
        board = self.board
        outline = board.outline
        if outline is None or not outline.points:
            return []
        kinds = {layer.name: layer.kind for layer in board.layers}
        edges = [g for g in board.graphics if kinds.get(g.layer, layer_kind(g.layer)) == "edge"]
        if edges:
            self.error(
                "kicad.board.outline-conflict",
                f"the board has an outline and {len(edges)} graphic(s) on an edge layer; remove one of them",
                _locator(edges[0]),
            )
            return []
        lines: list[Node | Atom] = []
        for ring_index, ring in enumerate((outline.points, *outline.cutouts)):
            if len(ring) < 2:
                continue
            for k, start in enumerate(ring):
                end = ring[(k + 1) % len(ring)]
                lines.append(
                    _ordered(
                        "gr_line",
                        {
                            "start": [point_node("start", start)],
                            "end": [point_node("end", end)],
                            "stroke": [_stroke(OUTLINE_WIDTH)],
                            "layer": [node("layer", Atom.string("Edge.Cuts"))],
                            "uuid": [_uuid_node(kicad_uuid(outline, f"outline:{ring_index}:{k}"))],
                        },
                    )
                )
        return lines

    # -- projections

    def reconcile(self, entity: Entity, head: str, slots: list[Slot], items: Items) -> set[str]:
        """Compare every opaque child that stands for a model value with the model (Decision 10).

        Updates ``slots`` (respelled children written from the model, renamed Reference and Value) and
        ``items`` (items of children kept as written), and returns the fields covered by opaque children.
        """
        fields = KEEPOUT_FIELDS if isinstance(entity, Keepout) else _READ_FIELDS.get(head, {})
        where = _locator(entity)
        covered: set[str] = set()
        kept: dict[str, list[str]] = {}
        file_properties: dict[str, str] = {}
        if isinstance(entity, FootprintInstance):
            for field in entity.fields:
                value = field_value(field)
                if value is not None and field.name not in ("Reference", "Value"):
                    file_properties[field.name] = value
        for i, slot in enumerate(slots):
            if not isinstance(slot, Opaque):
                continue
            child = slotlib.opaque_child(slot)
            if isinstance(child, Atom):
                if isinstance(entity, FootprintInstance) and child.value == "locked":
                    covered.add("locked")
                    if not entity.locked:
                        self.read_only("locked", where, "the footprint is locked by a header atom")
                continue
            special = self.projection(entity, child, slots, i, file_properties)
            if special is not None:
                covered.add(special)
                continue
            field = fields.get(child.name)
            if field is None or field in COLLECTION_FIELDS:
                continue
            covered.add(field)
            if field == "net_id" or (
                field == "outline" and isinstance(entity, (Zone, Keepout)) and not entity.outline
            ):
                continue
            new = next(
                (c for c in items.get(field, ()) if isinstance(c, Node) and c.name == child.name), None
            )
            if _key(child, self.copper) == (_key(new, self.copper) if new is not None else None):
                kept.setdefault(field, []).append(child.name)
            elif _spelling_only(child, new):
                slots[i] = Modeled(field)
            else:
                self.read_only(field, where, f"{dumps(child, style='compact')} is kept as written")
        for field, heads in kept.items():
            if any(isinstance(s, Modeled) and s.field == field for s in slots):
                items[field] = [c for c in items[field] if not (isinstance(c, Node) and c.name in heads)]
        if isinstance(entity, FootprintInstance):
            self.check_properties(entity, file_properties, where)
            self.check_removed_fields(entity, slots, where)
        return covered

    def reconcile_field(self, field: FootprintField, slots: list[Slot], items: Items) -> set[str]:
        """The projections of a read field (``board.md``, "The writer", "Fields").

        The value atom takes the component's ``ref`` or ``value`` for Reference and Value. A child that the
        reader kept as written keeps its fragment while the model agrees with it, is written from the model
        when it differs from the emitter's output only in spelling, and gives ``projection-read-only``
        otherwise. Returns the fields covered by opaque children.
        """
        where = _locator(field)
        owner = self.field_owner.get(field.id)
        component = self.components.get(owner.component_id) if owner is not None else None
        covered: set[str] = set()
        value_at = field_value_slot(slots)
        seen_list = False
        for i, slot in enumerate(slots):
            if isinstance(slot, Modeled):
                seen_list = seen_list or slot.field != "name"
                continue
            child = slotlib.opaque_child(slot)
            if isinstance(child, Atom):
                if i == value_at:
                    wanted = (
                        {"Reference": component.ref, "Value": component.value}.get(field.name)
                        if component is not None
                        else None
                    )
                    if wanted is not None and wanted != child.value:
                        slots[i] = Opaque(dumps(Atom.string(wanted), style="compact"), slot.min_version)
                elif not seen_list and i == 0:
                    covered.add("name")
                    if child.value != field.name:
                        slots[i] = Modeled("name")
                elif _is_hide(child):
                    covered.add("visible")
                    if field.visible:
                        self.read_only("visible", where, "the field is hidden by a bare 'hide' atom")
                continue
            seen_list = True
            mapped = FIELD_FIELDS.get(child.name)
            if mapped is None:
                continue
            covered.add(mapped)
            new = next((c for c in items.get(mapped, ()) if isinstance(c, Node)), None)
            detail = f"{dumps(child, style='compact')} is kept as written"
            if mapped == "visible":
                if (symbols(child) != ["no"]) == field.visible:
                    slots[i] = Modeled("visible")
            elif mapped == "position":
                assert new is not None
                if _at_key(child) == _at_key(new):
                    continue
                if _at_key(child) is not None:
                    slots[i] = Modeled("position")
                else:
                    self.read_only("position", where, detail)
            elif mapped == "effects":
                old = _effects_values(child)
                now = (field.size, field.thickness, field.h_justify, field.v_justify, field.mirrored)
                hidden = any(_is_hide(c) for c in child.children)
                if hidden:
                    covered.add("visible")
                if old == now and not (hidden and field.visible):
                    continue
                respelled = old is not None and _key(child, self.copper) == _key(
                    field_effects(*old), self.copper
                )
                if respelled:
                    slots[i] = Modeled("effects")
                else:
                    self.read_only("effects", where, detail)
            elif _key(child, self.copper) == (_key(new, self.copper) if new is not None else None):
                continue
            elif _spelling_only(child, new):
                slots[i] = Modeled(mapped)
            else:
                self.read_only(mapped, where, detail)
        return covered

    def check_removed_fields(self, fp: FootprintInstance, slots: Sequence[Slot], where: str) -> None:
        """A read Reference or Value field removed from the model leaves the component's text without a
        node; other names are found by ``check_properties``."""
        nodes = sum(1 for s in slots if isinstance(s, Modeled) and s.field == "fields")
        component = self.components.get(fp.component_id)
        if component is None or nodes <= len(fp.fields):
            return
        held = {f.name for f in fp.fields}
        for slot in slots:
            if isinstance(slot, Opaque) and slot.fragment.startswith("(property"):
                child = slotlib.opaque_child(slot)
                atoms = leading_atoms(child) if isinstance(child, Node) else []
                if atoms:
                    held.add(atoms[0].value)
        for key in ("Reference", "Value"):
            if key in component.properties and key not in held:
                self.read_only("properties", where, f"property {key!r} has no field to hold it")

    def projection(
        self, entity: Entity, child: Node, slots: list[Slot], i: int, file_properties: dict[str, str]
    ) -> str | None:
        """Handle a child projected into a field that the emitters never write; return that field."""
        name = child.name
        if isinstance(entity, Board) and name in ("paper", "title_block"):
            slot = slots[i]
            assert isinstance(slot, Opaque)
            if name == "paper" and project_paper(child) != entity.sheet:
                slots[i] = Opaque(dumps(paper_node(entity.sheet), style="compact"), slot.min_version)
            elif name == "title_block" and project_title_block(child) != _block_fields(entity.title_block):
                rewritten = rewrite_title_block(child, entity.title_block)
                slots[i] = Opaque(dumps(rewritten, style="compact"), slot.min_version)
            return name
        if isinstance(entity, FootprintInstance) and name == "property":
            atoms = leading_atoms(child)
            if len(atoms) < 2:
                return "properties"
            key, value = atoms[0].value, atoms[1].value
            component = self.components.get(entity.component_id)
            wanted = {"Reference": component.ref, "Value": component.value}.get(key) if component else None
            if wanted is not None and wanted != value:
                renamed = child.with_children([child.children[0], Atom.string(wanted), *child.children[2:]])
                slot = slots[i]
                assert isinstance(slot, Opaque)
                slots[i] = Opaque(dumps(renamed, style="compact"), slot.min_version)
            elif key not in ("Reference", "Value"):
                file_properties[key] = value
            return "properties"
        if isinstance(entity, FootprintInstance) and name == "locked":
            if (symbols(child) != ["no"]) != entity.locked:
                self.read_only(
                    "locked", _locator(entity), f"{dumps(child, style='compact')} is kept as written"
                )
            return "locked"
        if isinstance(entity, (Track, Arc, Via)) and name == "locked":
            # a lock that Fenolite would not write this way (``(locked no)``) is kept as written
            if (symbols(child) != ["no"]) != entity.locked:
                self.read_only(
                    "locked", _locator(entity), f"{dumps(child, style='compact')} is kept as written"
                )
            return "locked"
        if isinstance(entity, Zone) and name in ZONE_SETTING_FIELDS:
            differences = zonelib.projection_differences(
                child, entity.settings, filled=entity.filled, locked=entity.locked, major=self.target
            )
            if "filled" in differences:
                # the fill flag alone is rewritten in place: the rest of the child stays as written
                flagged = zonelib.with_fill_flag(child, entity.filled)
                slot = slots[i]
                if flagged is not None and isinstance(slot, Opaque):
                    slots[i] = Opaque(dumps(flagged, style="compact"), slot.min_version)
                    differences = tuple(d for d in differences if d != "filled")
            for what in differences:
                where = _child_locator(entity, slots, i, name, ZONE_SETTING_FIELDS[name])
                self.read_only(what, where, f"{dumps(child, style='compact')} is kept as written")
            return ZONE_SETTING_FIELDS[name]
        if isinstance(entity, Pad) and name == "zone_connect":
            first = opaque_zone_connects(slots)[0][0]
            if i == first and projected_zone_connect(slots) != entity.zone_connection:
                where = _child_locator(entity, slots, i, name, "zone_connection")
                self.read_only("zone_connection", where, "the zone connection is written as read")
            return "zone_connection"
        if isinstance(entity, Pad) and name == "padstack":
            model = entity.padstack
            expected = (
                tuple((ps.layer, str(ps.shape), ps.size.w, ps.size.h) for ps in model.layers)
                if model
                else None
            )
            if padstack_key(entity, child) != expected:
                self.read_only("padstack", _locator(entity), "per-layer pad shapes are written as read")
            return "padstack"
        if isinstance(entity, Graphic) and name == "stroke":
            width = child.find("width")
            found = tuple(_decimal(a) for a in width.atoms()) if width is not None else (Decimal(0),)
            if found != (_mm(entity.width),):
                self.read_only("width", _locator(entity), "the stroke is written as read")
            return "width"
        if isinstance(entity, Text) and name == "effects":
            font = child.find("font")
            size = font.find("size") if font is not None else None
            thickness = font.find("thickness") if font is not None else None
            found = (
                tuple(_decimal(a) for a in size.atoms()) if size is not None else None,
                tuple(_decimal(a) for a in thickness.atoms()) if thickness is not None else None,
            )
            if found != ((_mm(entity.size.h), _mm(entity.size.w)), (_mm(entity.thickness),)):
                self.read_only("size", _locator(entity), "the text effects are written as read")
            return "effects"
        return None

    def check_properties(self, fp: FootprintInstance, found: Mapping[str, str], where: str) -> None:
        """Properties other than Reference and Value: a value the model changed or added is refused."""
        component = self.components.get(fp.component_id)
        if component is None:
            return
        for key, value in sorted(component.properties.items()):
            if key in ("Reference", "Value") or found.get(key) == value:
                continue
            self.read_only("properties", where, f"property {key!r} differs from the footprint's")


def _with_title_block(slots: list[Slot], block: TitleBlock | None) -> list[Slot]:
    """A read board without ``title_block`` gains ``title_block_node(block)`` right after ``paper`` when the
    model sets a field (``board.md``; KiCad writes ``title_block`` right after ``paper``)."""
    if not has_title(block):
        return slots
    heads = [_fragment_head(s) for s in slots]
    if "title_block" in heads:
        return slots
    created = Opaque(dumps(title_block_node(_block_fields(block)), style="compact"))
    at = (
        heads.index("paper") + 1
        if "paper" in heads
        else next(
            (
                i + 1
                for i, s in reversed(list(enumerate(slots)))
                if isinstance(s, Modeled) and s.field in HEADER_FIELDS
            ),
            0,
        )
    )
    return [*slots[:at], created, *slots[at:]]


HEADER_FIELDS = frozenset({"version", "generator", "generator_version"})


def _fragment_head(slot: Slot) -> str | None:
    if not isinstance(slot, Opaque):
        return None
    child = slotlib.opaque_child(slot)
    return child.name if isinstance(child, Node) else None


def write_board(design: Design, *, target: int = DEFAULT_TARGET, allow_lossy: bool = False) -> WriteResult:
    """The text of a ``.kicad_pcb`` for KiCad ``target``.0 (see ``board.md``, "The writer").

    ``WriteResult.issues`` holds warnings and infos; errors raise ``LossyWriteError``,
    ``FutureFormatError``, ``DowngradeRefusedError`` or ``LegacyEditRefusedError``. Nothing is written
    to disk.
    """
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    board = design.board
    if board is None:
        raise ValueError("the design has no board")
    info = source_info(design)
    if info is not None:
        require_editable(info)
        check_target(info, target)
        if major_for(FileKind.BOARD, info.version) == 8:
            raise LegacyEditRefusedError(FileKind.BOARD, info.version)
    if board.holes:
        raise ValueError("a KiCad board holds holes only inside footprints; Board.holes cannot be written")
    writer = _Writer(design, target)
    root = writer.root()
    opaque = _pcbwrite.opaque_locators(root, writer.opaque_ids)
    stored = [stored_net_name(n) for n in design.circuit.nets]
    forms = _pcbwrite.NetForms.of(target, writer.source_table(), stored)
    root = _pcbwrite.convert_nets(root, forms, writer.errors)
    issues: list[Issue] = []
    if target < 10:
        root = _pcbwrite.place_table(root, forms.table())
    else:
        root, obsolete = _pcbwrite.drop_obsolete(root, target)
        issues += obsolete
    droppable, kept, others = _pcbwrite.gate(root, target, opaque)
    errors = [*writer.errors, *kept]
    if errors or droppable:
        lossy = [issue for found in droppable.values() for issue in found]
        if errors or not allow_lossy:
            raise LossyWriteError([*errors, *lossy], droppable=not errors)
        root = _pcbwrite.remove(root, droppable)
        issues += [_pcbwrite.dropped(loc, _pcbwrite.head_at(loc), found) for loc, found in droppable.items()]
        again, left, others = _pcbwrite.gate(root, target, opaque - set(droppable))
        if again or left:
            raise LossyWriteError([*left, *(i for found in again.values() for i in found)], droppable=False)
    issues += others
    comments = (
        tuple(v for k, v in board.ext["kicad"].payload if k == "comment") if "kicad" in board.ext else ()
    )
    if comments:
        root = dataclasses.replace(root, comments=comments)
    return WriteResult(dumps(root, style="kicad"), tuple(issues))


__all__ = [
    "BOARD_PAD_FIELDS",
    "CANONICAL_ORDER",
    "COLLECTION_FIELDS",
    "CREATED_ROOT_HEADS",
    "DEFAULT_THICKNESS",
    "EVIDENCE",
    "FIELD_FIELDS",
    "FIELD_POSITIONAL",
    "FILL_FIELDS",
    "FLOOR_HEADS",
    "FOOTPRINT_FIELDS",
    "ISSUE_CODES",
    "KEEPOUT_FIELDS",
    "PIN_TYPES",
    "ROOT_FIELDS",
    "TEXT_FIELDS",
    "TRACK_FIELDS",
    "POSITIONAL",
    "VIA_FIELDS",
    "WRITE_EVIDENCE",
    "WRITE_ISSUE_CODES",
    "ZONE_FIELDS",
    "ZONE_SETTING_FIELDS",
    "EmitContext",
    "form_major",
    "ModelSource",
    "field_effects",
    "field_hidden",
    "field_justify",
    "is_placed_property",
    "model_source",
    "opaque_count",
    "opaque_digests",
    "pad_angle_from_board",
    "pad_angle_to_board",
    "kicad_uuid",
    "read_board",
    "rebuild_board",
    "source_info",
    "field_value",
    "field_value_slot",
    "write_board",
]
