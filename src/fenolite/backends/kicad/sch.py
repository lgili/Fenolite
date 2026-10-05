# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic files (``.kicad_sch``) as ``SchematicSheet`` definitions, and their same-version rebuild.

Facts, mapping tables and sources: ``docs/formats/kicad/schematic.md`` (capability ``kicad-schematic``,
change c0060). Symbols, labels, no-connect flags, sheet references, embedded symbols, the paper and the
title block are read into the model; every other child (wires, junctions, buses, graphics, pins,
properties, instances) stays an opaque slot at its position, so an unchanged sheet is rebuilt
tree-equal. The reader never derives nets, and nothing here writes a file or runs a tool.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import re
from collections import Counter, deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, get_args

from fenolite.backends.base import RoundTrip, WriteResult
from fenolite.backends.kicad import _pcbwrite, schlayout
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad._fpmap import angle_atom, node, point_node
from fenolite.backends.kicad._libread import (
    Context,
    InexactValueError,
    Source,
    child_locators,
    leading_atoms,
    load_source,
)
from fenolite.backends.kicad.pcb import (
    ModelSource,
    kicad_uuid,
    paper_node,
    project_paper,
    project_title_block,
    title_block_node,
)
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, first_difference, parse, tree_equal
from fenolite.backends.kicad.sym import symbol_from
from fenolite.backends.kicad.versions import (
    DEFAULT_TARGET,
    FORMAT_VERSIONS,
    TARGET_MAJORS,
    FileKind,
    FormatInfo,
    LossyWriteError,
    check_emittable,
    classify,
    major_for,
    require_editable,
)
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import content_hash, content_id, derived_id
from fenolite.model.base import Entity, ExtBag, Modeled, Opaque, Slot
from fenolite.model.canonical import to_data
from fenolite.model.library import SymbolDef
from fenolite.model.presentation import SheetFrameRef
from fenolite.model.schematic import (
    SYMBOL_ROTATIONS,
    LabelKind,
    LabelShape,
    NetLabel,
    NoConnectFlag,
    SchematicSheet,
    SheetPage,
    SheetRef,
    SheetUse,
    SymbolInstance,
    SymbolUse,
)

EVIDENCE = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-K-SCH-READ", "H-K-SCH-COMPONENTS-2"))
KEPT_CODE = "kicad.sch.kept-opaque"
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.sch.kept-opaque": "info",
        "kicad.sch.inexact-length": "info",
        "kicad.sch.inexact-angle": "info",
        "kicad.sch.duplicate-property": "warning",
        "kicad.sch.duplicate-uuid": "warning",
        "kicad.sch.symbol-undefined": "warning",
        "kicad.sch.sheet-file-missing": "warning",
        "kicad.sch.sheet-missing": "warning",
        "kicad.sch.sheet-outside": "info",
        "kicad.sch.sheet-cycle": "error",
    }
)
WRITE_EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-SCH-MINIMAL",))
DROPPED_CODE = "kicad.sch.dropped-too-new"
WRITE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({DROPPED_CODE: "warning"})
"""The codes of ``write_schematic`` and of the symbol embedding (``symembed``)."""
TEXT_SIZE = 1_270_000
"""The height and width of every text a created sheet writes (KiCad's default, 50 mil)."""
FIRST_PROPERTIES: tuple[str, ...] = ("Reference", "Value", "Footprint", "Datasheet", "Description")
VISIBLE_PROPERTIES: frozenset[str] = frozenset({"Reference", "Value"})
INTERSHEET = ("Intersheetrefs", "${INTERSHEET_REFS}")
"""The property KiCad 10 keeps on every global label: the list of the pages that use the label."""

ROOT = ("kicad_sch",)
SYMBOL_CHAIN = ("kicad_sch", "symbol")
SHEET_CHAIN = ("kicad_sch", "sheet")
LIB_CHAIN = ("kicad_sch", "lib_symbols")
EMBEDDED_CHAIN = ("kicad_sch", "lib_symbols", "symbol")
LABEL_HEADS: Mapping[str, LabelKind] = MappingProxyType(
    {"label": "local", "global_label": "global", "hierarchical_label": "hierarchical"}
)
LABEL_SHAPES: frozenset[str] = frozenset(get_args(LabelShape)) - {""}
ROOT_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "uuid": "native_ids",
        "paper": "paper",
        "title_block": "title_block",
        "lib_symbols": "lib_symbols",
        "symbol": "symbols",
        "label": "labels.local",
        "global_label": "labels.global",
        "hierarchical_label": "labels.hierarchical",
        "no_connect": "no_connects",
        "sheet": "sheets",
        "sheet_instances": "pages",
    }
)
"""Root head → slot field. The three label heads share ``SchematicSheet.labels``; each has its own slot
field, so the k-th slot of a field is the k-th item of that head."""
SYMBOL_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "lib_name": "lib_name",
        "lib_id": "lib_ref",
        "at": "position",
        "mirror": "mirror",
        "unit": "unit",
        "body_style": "body_style",
        "convert": "body_style",
        "exclude_from_sim": "exclude_from_sim",
        "in_bom": "in_bom",
        "on_board": "on_board",
        "dnp": "dnp",
        "uuid": "native_ids",
    }
)
LABEL_FIELDS: Mapping[str, str] = MappingProxyType({"shape": "shape", "at": "position", "uuid": "native_ids"})
FLAG_FIELDS: Mapping[str, str] = MappingProxyType({"at": "position", "uuid": "native_ids"})
SHEET_FIELDS: Mapping[str, str] = MappingProxyType({"at": "position", "size": "size", "uuid": "native_ids"})
DEF_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "extends": "extends",
        "power": "power",
        "pin_names": "pin_names_hidden",
        "pin_numbers": "pin_numbers_hidden",
        "in_bom": "in_bom",
        "on_board": "on_board",
        "exclude_from_sim": "exclude_from_sim",
    }
)
"""The slot fields the symbol reader gives an embedded symbol (``sym.SYMBOL_FIELDS``)."""
_CANONICAL: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "kicad_sch": ("native_ids", "paper", "title_block", "lib_symbols"),
        "symbol": (
            "lib_name", "lib_ref", "position", "mirror", "unit", "body_style", "exclude_from_sim",
            "in_bom", "on_board", "dnp", "native_ids",
        ),
        "label": ("name", "shape", "position", "native_ids"),
        "no_connect": ("position", "native_ids"),
        "sheet": ("position", "size", "native_ids"),
        "def": ("name", "extends", "power", "pin_numbers_hidden", "pin_names_hidden",
                "exclude_from_sim", "in_bom", "on_board"),
    }
)  # fmt: skip
_BOOLEANS = {"yes": True, "no": False}
_HEAD = re.compile(r"\(([^\s()\"]+)")
_INDEX = re.compile(r"/([^/\[\]]+)\[(\d+)\]$")
_HEADER = ("version", "generator", "generator_version")
Items = dict[str, list[Node | Atom]]


@dataclass(frozen=True, slots=True)
class SchComponent:
    """One component of a project as its schematic names it."""

    ref: str
    value: str
    footprint: str


@dataclass(frozen=True, slots=True)
class SheetTree:
    """The schematic files of a hierarchy: ``files`` relative to the root file's folder, the root first;
    ``references`` counts the sheet references that name each file (0 for the root)."""

    files: tuple[str, ...]
    references: Mapping[str, int]
    issues: tuple[Issue, ...] = ()


class _Unmodelled(Exception):
    """An item the model cannot represent; it stays an opaque slot of the root (``kicad.sch.kept-opaque``)."""


# --- emitters -------------------------------------------------------------------------------------


def _yes_no(head: str, value: bool) -> Node:
    return node(head, Atom.symbol("yes" if value else "no"))


def _uuid(entity: Entity) -> list[Node | Atom]:
    value = entity.native_ids.get("kicad")
    return [node("uuid", Atom.string(value))] if value is not None else []


def _at(point: Point, udeg: int | None) -> Node:
    return point_node("at", point, *(() if udeg is None else (angle_atom(udeg),)))


def _emit_symbol(symbol: SymbolInstance) -> tuple[Items, set[str]]:
    """The modelled children of a symbol instance, and the fields that hold their default value."""
    items: Items = {
        "lib_name": [node("lib_name", Atom.string(symbol.lib_name))],
        "lib_ref": [node("lib_id", Atom.string(symbol.lib_ref))],
        "position": [_at(symbol.position, symbol.rotation)],
        "mirror": [node("mirror", Atom.symbol(symbol.mirror))] if symbol.mirror else [],
        "unit": [node("unit", Atom.integer(symbol.unit))],
        "body_style": [node("body_style", Atom.integer(symbol.body_style))],
        "exclude_from_sim": [_yes_no("exclude_from_sim", symbol.exclude_from_sim)],
        "in_bom": [_yes_no("in_bom", symbol.in_bom)],
        "on_board": [_yes_no("on_board", symbol.on_board)],
        "dnp": [_yes_no("dnp", symbol.dnp)],
        "native_ids": _uuid(symbol),
    }
    default = {
        name
        for name, value in (
            ("lib_name", ""), ("unit", 1), ("body_style", 1), ("exclude_from_sim", False),
            ("in_bom", True), ("on_board", True), ("dnp", False),
        )
        if getattr(symbol, name) == value
    }  # fmt: skip
    return items, default


def _emit_label(label: NetLabel) -> tuple[Items, set[str]]:
    items: Items = {
        "name": [Atom.string(label.name)],
        "shape": [node("shape", Atom.symbol(label.shape))] if label.shape else [],
        "position": [_at(label.position, label.rotation)],
        "native_ids": _uuid(label),
    }
    return items, set()


def _emit_flag(flag: NoConnectFlag) -> tuple[Items, set[str]]:
    return {"position": [_at(flag.position, None)], "native_ids": _uuid(flag)}, set()


def _emit_sheet_ref(ref: SheetRef) -> tuple[Items, set[str]]:
    items: Items = {
        "position": [_at(ref.position, None)],
        "size": [node("size", Atom.from_nm(ref.size.w), Atom.from_nm(ref.size.h))],
        "native_ids": _uuid(ref),
    }
    return items, set()


def _embedded_name(symbol: SymbolDef) -> str:
    return f"{symbol.library}:{symbol.name}" if symbol.library else symbol.name


def _emit_def(symbol: SymbolDef) -> tuple[Items, set[str]]:
    """The modelled children of an embedded symbol, in the 10.0 spelling; other spellings stay opaque."""
    hide = [node("hide", Atom.symbol("yes"))]
    offset = symbol.pin_name_offset
    names = ([] if offset is None else [node("offset", Atom.from_nm(offset))]) + (
        hide if symbol.pin_names_hidden else []
    )
    items: Items = {
        "name": [Atom.string(_embedded_name(symbol))],
        "extends": [node("extends", Atom.string(symbol.extends))] if symbol.extends else [],
        "power": [node("power", Atom.symbol(symbol.power))] if symbol.power else [],
        "pin_names_hidden": [node("pin_names", *names)],
        "pin_numbers_hidden": [node("pin_numbers", *(hide if symbol.pin_numbers_hidden else []))],
        "in_bom": [_yes_no("in_bom", symbol.in_bom)],
        "on_board": [_yes_no("on_board", symbol.on_board)],
        "exclude_from_sim": [_yes_no("exclude_from_sim", symbol.exclude_from_sim)],
    }
    default = {"in_bom", "on_board", "exclude_from_sim", "pin_names_hidden", "pin_numbers_hidden"}
    return items, default


def _pages_node(pages: Sequence[SheetPage]) -> Node:
    rows = [node("path", Atom.string(p.path), node("page", Atom.string(p.page))) for p in pages]
    return node("sheet_instances", *rows)


_EMITTERS: Mapping[type, tuple[str, Mapping[str, str], Callable[[Any], tuple[Items, set[str]]]]] = {
    SymbolInstance: ("symbol", SYMBOL_FIELDS, _emit_symbol),
    NetLabel: ("label", LABEL_FIELDS, _emit_label),
    NoConnectFlag: ("no_connect", FLAG_FIELDS, _emit_flag),
    SheetRef: ("sheet", SHEET_FIELDS, _emit_sheet_ref),
    SymbolDef: ("def", DEF_FIELDS, _emit_def),
}


def _head_of(entity: Entity) -> str:
    if isinstance(entity, NetLabel):
        return next(head for head, kind in LABEL_HEADS.items() if kind == entity.kind)
    if isinstance(entity, SymbolDef):
        return "symbol"
    return _EMITTERS[type(entity)][0]


# --- reading --------------------------------------------------------------------------------------


def _first(child: Node | None) -> str | None:
    atoms = child.atoms() if child is not None else ()
    return atoms[0].value if atoms else None


def _native(item: Node) -> dict[str, str]:
    value = _first(item.find("uuid"))
    return {"kicad": value} if value is not None else {}


class _Reader:
    """One schematic being read: its context, the embedded symbol names and the uuid census."""

    def __init__(self, ctx: Context, name: str) -> None:
        self.ctx = ctx
        self.name = name
        self.uuids: Counter[str] = Counter()
        self.content: Counter[tuple[str, str]] = Counter()
        self.embedded: set[str] = set()
        self.native = _first(ctx.loaded.node.find("uuid")) or f"file:{name}"

    def issue(self, code: str, message: str, where: str) -> None:
        self.ctx.issues.append(Issue(code, ISSUE_CODES[code], message, where=where))

    def ids(self, prefix: str, item: Node) -> tuple[str, dict[str, str]]:
        value = _first(item.find("uuid"))
        if value is not None:
            repeat = self.uuids[value]
            self.uuids[value] = repeat + 1
            if repeat:
                self.issue("kicad.sch.duplicate-uuid", f"uuid {value} is already used in this file", value)
            return derived_id(prefix, "kicad", value + (f":{repeat}" if repeat else "")), {"kicad": value}
        text = dumps(item, style="compact")
        count = self.content[(item.name, text)]
        self.content[(item.name, text)] = count + 1
        return content_id(prefix, "kicad", self.native, item.name, content_hash(text, count)), {}

    def header(self, entity_slots: list[Slot], prefix: str, item: Node, loc: str) -> dict[str, Any]:
        ident, native_ids = self.ids(prefix, item)
        return {
            "id": ident,
            "native_ids": native_ids,
            "provenance": self.ctx.provenance(loc),
            "ext": {"kicad": slotlib.to_ext(entity_slots)},
        }

    def check(
        self,
        item: Node,
        loc: str,
        slots: list[Slot],
        items: Items,
        chain: tuple[str, ...],
        skip: frozenset[str] = frozenset(),
    ) -> None:
        """Keep as written every modelled child that the emitters do not reproduce exactly."""
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

    def at(self, item: Node, loc: str) -> tuple[Point, int]:
        at = item.find("at")
        if at is None:
            raise _Unmodelled(f"{item.name!r} has no position")
        at_loc = f"{loc}/at[0]"
        atoms = at.atoms()
        position = self.ctx.point(at, at_loc)
        rotation = self.ctx.udeg(atoms[2], at_loc, at) if len(atoms) > 2 else 0
        return position, rotation

    # -- items

    def symbol(self, item: Node, loc: str) -> SymbolInstance:
        ctx = self.ctx
        slots: list[Slot] = ctx.split(item, dict(SYMBOL_FIELDS), SYMBOL_CHAIN)
        position, rotation = self.at(item, loc)
        if rotation not in SYMBOL_ROTATIONS:
            raise _Unmodelled("a symbol angle other than 0, 90, 180 or 270 degrees is not modelled")
        values: dict[str, Any] = {}
        properties: dict[str, str] = {}
        uses: list[SymbolUse] = []
        for child_loc, child in child_locators(loc, item):
            if not isinstance(child, Node):
                continue
            head = child.name
            atoms = [a.value for a in child.atoms()]
            if head == "lib_id":
                values["lib_ref"] = atoms[0] if atoms else ""
            elif head == "lib_name":
                values["lib_name"] = atoms[0] if atoms else ""
            elif head == "mirror":
                if atoms not in (["x"], ["y"]):
                    raise _Unmodelled(f"mirror {' '.join(atoms)!r} is not modelled")
                values["mirror"] = atoms[0]
            elif head in ("unit", "body_style", "convert"):
                if len(atoms) != 1 or not atoms[0].isascii() or not atoms[0].isdigit():
                    raise _Unmodelled(f"{head} {' '.join(atoms)!r} is not a number")
                values["unit" if head == "unit" else "body_style"] = int(atoms[0])
            elif head in ("exclude_from_sim", "in_bom", "on_board", "dnp"):
                if len(atoms) == 1 and atoms[0] in _BOOLEANS:
                    values[head] = _BOOLEANS[atoms[0]]
            elif head == "property":
                named = leading_atoms(child)
                if len(named) >= 2:
                    key = named[0].value
                    if key in properties:
                        self.issue(
                            "kicad.sch.duplicate-property",
                            f"property {key!r} repeats in one symbol; the last text is used",
                            child_loc,
                        )
                    properties[key] = named[1].value
            elif head == "instances":
                for project in child.nodes("project"):
                    name = _first(project) or ""
                    for path in project.nodes("path"):
                        unit = _first(path.find("unit")) or "1"
                        uses.append(
                            SymbolUse(
                                name,
                                _first(path) or "",
                                _first(path.find("reference")) or "",
                                int(unit) if unit.isascii() and unit.isdigit() else 1,
                            )
                        )
        symbol = SymbolInstance(
            lib_ref=values.pop("lib_ref", ""),
            position=position,
            rotation=rotation,
            ref=properties.get("Reference", ""),
            value=properties.get("Value", ""),
            footprint=properties.get("Footprint", ""),
            properties=properties,
            uses=tuple(uses),
            id=derived_id("sci", "kicad", "pending"),
            **values,
        )
        symbol = dataclasses.replace(symbol, native_ids=_native(item))
        self.check(item, loc, slots, _emit_symbol(symbol)[0], SYMBOL_CHAIN)
        key = symbol.lib_name or symbol.lib_ref
        if key not in self.embedded:
            self.issue(
                "kicad.sch.symbol-undefined",
                f"symbol {symbol.ref or symbol.lib_ref!r} names {key!r}, which this file does not embed",
                loc,
            )
        return dataclasses.replace(symbol, **self.header(slots, "sci", item, loc))

    def label(self, item: Node, loc: str) -> NetLabel:
        chain = ("kicad_sch", item.name)
        slots: list[Slot] = self.ctx.split(item, dict(LABEL_FIELDS), chain, ("name",))
        named = leading_atoms(item)
        if not named:
            raise _Unmodelled("a label without a text is not modelled")
        position, rotation = self.at(item, loc)
        shape = _first(item.find("shape")) or ""
        if shape and shape not in LABEL_SHAPES:
            raise _Unmodelled(f"label shape {shape!r} is not modelled")
        label = NetLabel(
            LABEL_HEADS[item.name],
            named[0].value,
            position,
            rotation,
            shape,  # type: ignore[arg-type]
            id=derived_id("lbl", "kicad", "pending"),
            native_ids=_native(item),
        )
        self.check(item, loc, slots, _emit_label(label)[0], chain)
        return dataclasses.replace(label, **self.header(slots, "lbl", item, loc))

    def flag(self, item: Node, loc: str) -> NoConnectFlag:
        chain = ("kicad_sch", "no_connect")
        slots: list[Slot] = self.ctx.split(item, dict(FLAG_FIELDS), chain)
        at = item.find("at")
        if at is None:
            raise _Unmodelled("a no-connect flag without a position is not modelled")
        flag = NoConnectFlag(
            self.ctx.point(at, f"{loc}/at[0]"),
            id=derived_id("ncf", "kicad", "pending"),
            native_ids=_native(item),
        )
        self.check(item, loc, slots, _emit_flag(flag)[0], chain)
        return dataclasses.replace(flag, **self.header(slots, "ncf", item, loc))

    def sheet_ref(self, item: Node, loc: str) -> SheetRef:
        ctx = self.ctx
        slots: list[Slot] = ctx.split(item, dict(SHEET_FIELDS), SHEET_CHAIN)
        at, size = item.find("at"), item.find("size")
        if at is None or size is None:
            raise _Unmodelled("a sheet without a position and a size is not modelled")
        box = ctx.point(size, f"{loc}/size[0]")
        properties: dict[str, str] = {}
        uses: list[SheetUse] = []
        for child in item.nodes():
            if child.name == "property":
                named = leading_atoms(child)
                if len(named) >= 2:
                    properties[named[0].value] = named[1].value
            elif child.name == "instances":
                for project in child.nodes("project"):
                    for path in project.nodes("path"):
                        uses.append(
                            SheetUse(
                                _first(project) or "", _first(path) or "", _first(path.find("page")) or ""
                            )
                        )
        if "Sheetfile" not in properties:
            self.issue("kicad.sch.sheet-file-missing", "the sheet reference has no 'Sheetfile' property", loc)
        ref = SheetRef(
            properties.get("Sheetname", ""),
            properties.get("Sheetfile", ""),
            ctx.point(at, f"{loc}/at[0]"),
            Size(box.x, box.y),
            tuple(uses),
            id=derived_id("shr", "kicad", "pending"),
            native_ids=_native(item),
        )
        self.check(item, loc, slots, _emit_sheet_ref(ref)[0], SHEET_CHAIN)
        return dataclasses.replace(ref, **self.header(slots, "shr", item, loc))

    def lib_symbols(self, item: Node, loc: str) -> tuple[list[SymbolDef], list[Slot]]:
        """The embedded symbols and the slot list of the ``lib_symbols`` node."""
        ctx = self.ctx
        slots: list[Slot] = ctx.split(item, {"symbol": "lib_symbols"}, LIB_CHAIN)
        found: list[SymbolDef] = []
        seen: Counter[str] = Counter()
        for index, (child_loc, child) in enumerate(child_locators(loc, item)):
            if not isinstance(child, Node) or child.name != "symbol":
                continue
            named = leading_atoms(child)
            if not named:
                raise ctx.error("an embedded symbol has no name", child_loc, child)
            full = named[0].value
            library, sep, name = full.partition(":")
            if not sep:
                library, name = "", full
            repeat = seen[full]
            seen[full] += 1
            self.embedded.add(full)
            native = f"sch:{self.native}:{full}" + (f":{repeat}" if repeat else "")
            try:
                symbol = symbol_from(
                    child,
                    library=library,
                    name=name,
                    native=native,
                    ctx=ctx,
                    locator=child_loc,
                    chain=EMBEDDED_CHAIN,
                )
            except InexactValueError as exc:
                self.inexact(exc)
                slots[index] = ctx.opaque(child, LIB_CHAIN)
                continue
            own = list(slotlib.from_ext(symbol.ext["kicad"]))
            self.check(child, child_loc, own, _emit_def(symbol)[0], EMBEDDED_CHAIN)
            found.append(dataclasses.replace(symbol, ext={"kicad": slotlib.to_ext(own)}))
        return found, slots

    def inexact(self, error: InexactValueError) -> None:
        code = "kicad.sch.inexact-angle" if error.what == "angle" else "kicad.sch.inexact-length"
        self.issue(code, f"{error.message}; kept as written", error.locator)

    def pages(self, item: Node) -> tuple[SheetPage, ...]:
        return tuple(
            SheetPage(_first(path) or "", _first(path.find("page")) or "") for path in item.nodes("path")
        )

    # -- the root

    def read(self) -> SchematicSheet:
        ctx = self.ctx
        root = ctx.loaded.node
        slots: list[Slot] = ctx.split(root, dict(ROOT_FIELDS), ROOT)
        children = child_locators("/kicad_sch", root)
        pairs: list[tuple[str, str]] = []
        paper = SheetFrameRef("A4")
        block = None
        lib_symbols: list[SymbolDef] = []
        lib_slots: list[Slot] | None = None
        pages: tuple[SheetPage, ...] = ()
        symbols: list[SymbolInstance] = []
        labels: list[NetLabel] = []
        flags: list[NoConnectFlag] = []
        sheets: list[SheetRef] = []
        for loc, child in children:  # the header and the embedded symbols come first
            if not isinstance(child, Node):
                continue
            if child.name in _HEADER:
                atoms = child.atoms()
                if len(atoms) == 1:
                    pairs.append((child.name, atoms[0].text if child.name == "version" else atoms[0].value))
            elif child.name == "lib_symbols" and lib_slots is None:
                lib_symbols, lib_slots = self.lib_symbols(child, loc)
        seen: set[str] = set()
        for index, (loc, child) in enumerate(children):
            if not isinstance(child, Node) or not isinstance(slots[index], Modeled):
                continue
            head = child.name
            if head in ("uuid", "paper", "title_block", "lib_symbols", "sheet_instances"):
                if head in seen:  # a second one is kept as written
                    slots[index] = ctx.opaque(child, ROOT)
                    ctx.kept_opaque(f"a second {head!r} is kept as written", loc)
                    continue
                seen.add(head)
                if head == "paper":
                    paper = project_paper(child) or paper
                elif head == "title_block":
                    block = project_title_block(child)
                elif head == "sheet_instances":
                    pages = self.pages(child)
                continue
            try:
                if head == "symbol":
                    symbols.append(self.symbol(child, loc))
                elif head in LABEL_HEADS:
                    labels.append(self.label(child, loc))
                elif head == "no_connect":
                    flags.append(self.flag(child, loc))
                else:
                    sheets.append(self.sheet_ref(child, loc))
            except InexactValueError as exc:
                self.inexact(exc)
                slots[index] = ctx.opaque(child, ROOT)
            except _Unmodelled as exc:
                ctx.kept_opaque(f"{exc}; kept as written", loc)
                slots[index] = ctx.opaque(child, ROOT)
        uuid = _first(root.find("uuid"))
        pairs += [("comment", text) for text in root.comments]
        groups: dict[str, Sequence[Slot]] = {".": slots}
        if lib_slots is not None:
            groups["lib_symbols[0]"] = lib_slots
        sheet = SchematicSheet(
            id=derived_id("sch", "kicad", self.native),
            native_ids={"kicad": uuid} if uuid is not None else {},
            provenance=ctx.provenance("/kicad_sch"),
            name=self.name,
            paper=paper,
            title_block=block,
            lib_symbols=tuple(lib_symbols),
            symbols=tuple(symbols),
            labels=tuple(labels),
            no_connects=tuple(flags),
            sheets=tuple(sheets),
            pages=pages,
        )
        self.check(root, "/kicad_sch", slots, _emit_root(sheet, {}), ROOT, _COLLECTIONS)
        ext = slotlib.to_ext(groups, ExtBag(None, tuple(pairs)))
        return dataclasses.replace(sheet, ext={"kicad": ext})


def _emit_root(sheet: SchematicSheet, built: Mapping[str, Sequence[Node | Atom]]) -> Items:
    """The modelled children of the root; ``built`` holds the rebuilt items of the collections (empty
    while reading, when only the scalar children are compared)."""
    items: Items = {
        "native_ids": _uuid(sheet),
        "paper": [paper_node(sheet.paper)],
        "title_block": [title_block_node(sheet.title_block)] if sheet.title_block is not None else [],
        "pages": [_pages_node(sheet.pages)],
    }
    for name, values in built.items():
        items[name] = list(values)
    return items


_COLLECTIONS = frozenset(
    {
        "lib_symbols",
        "symbols",
        "labels.local",
        "labels.global",
        "labels.hierarchical",
        "no_connects",
        "sheets",
    }
)


def read_schematic(source: Source, *, file: str = "", issues: list[Issue] | None = None) -> SchematicSheet:
    """One ``.kicad_sch`` file (a path, file text or a parsed node) as a ``SchematicSheet``."""
    loaded = load_source(source, file)
    ctx = Context(
        loaded, FileKind.SCHEMATIC, EVIDENCE, issues if issues is not None else [], kept_code=KEPT_CODE
    )
    ctx.check_version("kicad_sch", FileKind.SCHEMATIC)
    reader = _Reader(ctx, PurePosixPath(loaded.file.replace("\\", "/")).stem if loaded.file else "")
    return reader.read()


# --- rebuild --------------------------------------------------------------------------------------


def _pairs(entity: Entity) -> dict[str, str]:
    bag = entity.ext.get("kicad")
    return {k: v for k, v in bag.payload if not k.startswith(slotlib.SLOT_PREFIX)} if bag else {}


def source_info(sheet: SchematicSheet) -> FormatInfo | None:
    """The header of the file a sheet was read from, or ``None`` for a created sheet."""
    pairs = _pairs(sheet)
    if "version" not in pairs:
        return None
    version = int(pairs["version"])
    kind = FileKind.SCHEMATIC
    return FormatInfo(
        kind,
        version,
        major_for(kind, version),
        classify(kind, version),
        pairs.get("generator"),
        pairs.get("generator_version"),
    )


def _slots(entity: Entity, rel: str = ".") -> tuple[Slot, ...]:
    bag = entity.ext.get("kicad")
    found = slotlib.from_ext(bag, rel) if bag is not None else ()
    if not found:
        raise ValueError(
            f"{entity.id} has no KiCad slot list ({rel!r}); created sheets are written by another change"
        )
    return found


def _held(slots: Sequence[Slot], fields: Mapping[str, str]) -> set[str]:
    """The fields whose child is kept as an opaque fragment."""
    held: set[str] = set()
    for slot in slots:
        if isinstance(slot, Opaque):
            match = _HEAD.match(slot.fragment)
            if match is not None and match.group(1) in fields:
                held.add(fields[match.group(1)])
    return held


def _entity_node(entity: Entity) -> Node:
    key, fields, emit = _EMITTERS[type(entity)]
    slots = _slots(entity)
    items, default = emit(entity)
    modeled = {s.field for s in slots if isinstance(s, Modeled)}
    held = _held(slots, fields)
    wanted = {
        name: values
        for name, values in items.items()
        if name in modeled or (name not in held and name not in default and values)
    }
    return slotlib.rebuild(
        Atom.symbol(_head_of(entity)), slots, ModelSource(wanted), canonical=_CANONICAL[key]
    )


def _index(entity: Entity) -> int:
    locator = entity.provenance.locator if entity.provenance is not None else ""
    match = _INDEX.search(locator)
    if match is None:
        raise ValueError(f"{entity.id} has no source locator; created sheets are written by another change")
    return int(match.group(2))


def _collections(sheet: SchematicSheet) -> dict[str, list[Entity]]:
    groups: dict[str, list[Entity]] = {
        "symbols": list(sheet.symbols),
        "no_connects": list(sheet.no_connects),
        "sheets": list(sheet.sheets),
        "lib_symbols": list(sheet.lib_symbols),
    }
    for kind in LABEL_HEADS.values():
        groups[f"labels.{kind}"] = [label for label in sheet.labels if label.kind == kind]
    return groups


def _count(slots: Sequence[Slot], name: str) -> int:
    return sum(1 for s in slots if isinstance(s, Modeled) and s.field == name)


def _model_fields(entity: Any) -> dict[str, Any]:
    skip = {
        "id",
        "native_ids",
        "provenance",
        "ext",
        "lib_symbols",
        "symbols",
        "labels",
        "no_connects",
        "sheets",
    }
    return {f.name: getattr(entity, f.name) for f in dataclasses.fields(entity) if f.name not in skip}


def _compare(old: Any, new: Any) -> None:
    """Refuse a value that the rebuilt node does not carry (a projection, or a child kept as written)."""
    before, after = _model_fields(old), _model_fields(new)
    for name, value in before.items():
        if after[name] != value:
            raise ValueError(
                f"{old.id}: field {name!r} was changed, but its source is kept as written; "
                f"the rebuilt file still says {after[name]!r}"
            )


def rebuild_schematic(sheet: SchematicSheet) -> Node:
    """The ``kicad_sch`` node of a sheet read by ``read_schematic``, at the sheet's own format version.

    Modelled fields are emitted from the model and opaque fragments verbatim. A changed projection (a
    property text, a use, a sheet name) and an added or removed entity raise ``ValueError``.
    """
    info = source_info(sheet)
    if info is None:
        raise ValueError(
            f"{sheet.id} was not read from a KiCad file; created sheets are written by another change"
        )
    file = sheet.provenance.file if sheet.provenance is not None else ""
    require_editable(info, file=file)
    slots = _slots(sheet)
    groups = _collections(sheet)
    lib_slots = slotlib.from_ext(sheet.ext["kicad"], "lib_symbols[0]")
    built: dict[str, list[Node | Atom]] = {}
    for name, entities in groups.items():
        expected = _count(lib_slots if name == "lib_symbols" else slots, name)
        if len(entities) != expected:
            shown = name.partition(".")[0]
            raise ValueError(
                f"{sheet.id}: collection {shown!r} has {len(entities)} item(s) of this kind and the "
                f"source has {expected}; adding and removing entities belongs to the writer of created sheets"
            )
        entities.sort(key=_index)
        built[name] = [_entity_node(entity) for entity in entities]
    if _count(slots, "lib_symbols"):
        defs = ModelSource({"lib_symbols": built["lib_symbols"]})
        built["lib_symbols"] = [slotlib.rebuild(Atom.symbol("lib_symbols"), lib_slots, defs)]
    items = _emit_root(sheet, built)
    modeled = {s.field for s in slots if isinstance(s, Modeled)}
    wanted = {name: values for name, values in items.items() if name in modeled}
    root = slotlib.rebuild(Atom.symbol("kicad_sch"), slots, ModelSource(wanted))
    comments = tuple(v for k, v in sheet.ext["kicad"].payload if k == "comment")
    if comments:
        root = dataclasses.replace(root, comments=comments)
    again = read_schematic(root, file=file)
    _compare(sheet, again)
    reread = {name: sorted(found, key=_index) for name, found in _collections(again).items()}
    for name, entities in groups.items():
        if len(reread[name]) != len(entities):
            raise ValueError(
                f"{sheet.id}: a changed value of collection {name.partition('.')[0]!r} cannot be written "
                "exactly (a length that is not whole nm, or a value the model does not hold)"
            )
        for old, new in zip(entities, reread[name], strict=True):
            _compare(old, new)
    return root


def _entities(sheet: SchematicSheet) -> Iterable[Entity]:
    yield sheet
    yield from sheet.lib_symbols
    yield from sheet.symbols
    yield from sheet.labels
    yield from sheet.no_connects
    yield from sheet.sheets


def _opaque_fragments(sheet: SchematicSheet) -> Iterable[str]:
    for entity in _entities(sheet):
        bag = entity.ext.get("kicad")
        if bag is None:
            continue
        for key, value in bag.payload:
            if key.startswith(slotlib.SLOT_PREFIX) and key.rpartition(":")[2].startswith("opaque"):
                yield value


def opaque_count(sheet: SchematicSheet) -> int:
    """The number of opaque slots of the sheet and of every entity in it, embedded symbols included."""
    return sum(1 for _ in _opaque_fragments(sheet))


def opaque_heads(sheet: SchematicSheet) -> Counter[str]:
    """The heads of the opaque slots of the sheet root, counted: what the root holds that the model does
    not (``wire``, ``junction``, ``bus``, ``text`` and so on). A sheet that was not read from a file has no
    slot and gives an empty count."""
    bag = sheet.ext.get("kicad")
    heads: Counter[str] = Counter()
    for slot in slotlib.from_ext(bag, ".") if bag is not None else ():
        if isinstance(slot, Opaque):
            match = _HEAD.match(slot.fragment)
            heads[match.group(1) if match is not None else ""] += 1
    return heads


def opaque_digests(sheet: SchematicSheet) -> Counter[str]:
    """The SHA-256 hex digests of the opaque fragments, as a multiset."""
    return Counter(hashlib.sha256(f.encode("utf-8")).hexdigest() for f in _opaque_fragments(sheet))


def _without_provenance(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_provenance(v) for k, v in value.items() if k != "provenance"}  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, list):
        return [_without_provenance(v) for v in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def roundtrip_schematic(text: str, *, file: str = "") -> RoundTrip:
    """The RT1 verdict of one schematic text; the reader's errors are raised unchanged."""
    sheet = read_schematic(text, file=file)
    rebuilt = rebuild_schematic(sheet)
    original = parse(text, file=file)
    tree_ok = tree_equal(rebuilt, original)
    again = read_schematic(dumps(rebuilt), file=file)
    model_ok = _without_provenance(to_data(again)) == _without_provenance(to_data(sheet))
    opaque_ok = opaque_count(again) == opaque_count(sheet) and opaque_digests(again) == opaque_digests(sheet)
    if not tree_ok:
        difference = first_difference(rebuilt, original) or f"/{original.name}"
    elif not model_ok:
        difference = "model"
    elif not opaque_ok:
        difference = "opaque"
    else:
        difference = ""
    return RoundTrip(
        level="RT1",
        passed=tree_ok and model_ok and opaque_ok,
        tree_equal=tree_ok,
        model_equal=model_ok,
        opaque_equal=opaque_ok,
        opaque_count=opaque_count(sheet),
        difference=difference,
    )


# --- writing created sheets -----------------------------------------------------------------------


def gate_created(root: Node, target: int, allow_lossy: bool, issues: list[Issue]) -> Node:
    """``root`` after the emit check for ``target``: a token the target does not read raises
    ``LossyWriteError``, or with ``allow_lossy`` its node is removed with one ``kicad.sch.dropped-too-new``
    warning. Warnings of the check are appended to ``issues``."""
    found = check_emittable(root, FileKind.SCHEMATIC, target)
    too_new = {i.where for i in found if i.code == _pcbwrite.TOO_NEW}
    droppable, errors, others = _pcbwrite.gate(root, target, too_new, FileKind.SCHEMATIC)
    if errors or droppable:
        lossy = [issue for group in droppable.values() for issue in group]
        if errors or not allow_lossy:
            raise LossyWriteError([*errors, *lossy], droppable=not errors)
        root = _pcbwrite.remove(root, droppable)
        issues += [
            _pcbwrite.dropped(loc, _pcbwrite.head_at(loc), group, DROPPED_CODE)
            for loc, group in droppable.items()
        ]
        again, left, others = _pcbwrite.gate(root, target, (), FileKind.SCHEMATIC)
        if left or again:
            raise LossyWriteError([*left, *(i for group in again.values() for i in group)], droppable=False)
    issues += others
    return root


def _font(*extra: Node) -> Node:
    size = node("size", Atom.from_nm(TEXT_SIZE), Atom.from_nm(TEXT_SIZE))
    return node("effects", node("font", size), *extra)


def _property(key: str, text: str, at: Point, *, ten: bool, hidden: bool, justify: str = "") -> Node:
    """One ``property`` of a created item: ``hide`` is a child of the property for target 10 and a child
    of ``effects`` for target 9, and target 10 also gets ``show_name`` and ``do_not_autoplace``."""
    hide = [_yes_no("hide", True)] if hidden else []
    side = [node("justify", Atom.symbol(justify))] if justify else []
    children: list[Node | Atom] = [Atom.string(key), Atom.string(text), _at(at, 0)]
    if ten:
        children += [_yes_no("show_name", False), _yes_no("do_not_autoplace", False), *hide, _font(*side)]
    else:
        children.append(_font(*side, *hide))
    return node("property", *children)


def _text_anchor(symbol: SymbolInstance, definition: SymbolDef | None) -> tuple[Point, Point]:
    """Where the Reference and the Value of a created instance are written: above the unit, or to its
    right when a pin of the unit leaves it upwards. A cosmetic choice; nothing connects to a text."""
    origin = symbol.position
    if definition is None:
        return Point(origin.x, origin.y - 2 * TEXT_SIZE), Point(origin.x, origin.y + 2 * TEXT_SIZE)
    rotation = symbol.rotation // 1_000_000
    pins = definition.pins_of(symbol.unit, symbol.body_style)
    points = [schlayout.pin_point(origin, pin.position, rotation, symbol.mirror) for pin in pins]
    for graphic in definition.graphics:
        points += [schlayout.pin_point(origin, p, rotation, symbol.mirror) for p in graphic.points]
    if not points:
        points = [origin]
    left, right = min(p.x for p in points), max(p.x for p in points)
    top = min(p.y for p in points)
    upwards = any(
        schlayout.label_angle(pin.rotation // 1_000_000, rotation, symbol.mirror) == 90 for pin in pins
    )
    if upwards:
        x = right + 2 * TEXT_SIZE
        return Point(x, origin.y - TEXT_SIZE), Point(x, origin.y + TEXT_SIZE)
    return Point(left, top - 3 * TEXT_SIZE), Point(left, top - TEXT_SIZE)


def _created_symbol(symbol: SymbolInstance, definition: SymbolDef | None, ten: bool) -> Node:
    items, _ = _emit_symbol(symbol)
    children: list[Node | Atom] = []
    if symbol.lib_name:
        children += items["lib_name"]
    children += [*items["lib_ref"], *items["position"], *items["mirror"], *items["unit"]]
    if ten:
        children += items["body_style"]
    children += [*items["exclude_from_sim"], *items["in_bom"], *items["on_board"]]
    if ten:
        children.append(_yes_no("in_pos_files", symbol.on_board))
    children += [*items["dnp"], node("uuid", Atom.string(kicad_uuid(symbol)))]
    reference, value = _text_anchor(symbol, definition)
    names = [k for k in FIRST_PROPERTIES if k in symbol.properties]
    names += sorted(k for k in symbol.properties if k not in FIRST_PROPERTIES)
    for key in names:
        at = {"Reference": reference, "Value": value}.get(key, symbol.position)
        visible = key in VISIBLE_PROPERTIES
        children.append(
            _property(
                key,
                symbol.properties[key],
                at,
                ten=ten,
                hidden=not visible,
                justify="left" if visible else "",
            )
        )
    if definition is not None:
        seen: set[str] = set()
        for pin in definition.pins_of(symbol.unit, symbol.body_style):
            if pin.number in seen:
                continue
            seen.add(pin.number)
            pin_uuid = kicad_uuid(symbol, f"pin:{pin.number}")
            children.append(node("pin", Atom.string(pin.number), node("uuid", Atom.string(pin_uuid))))
    projects: dict[str, list[Node]] = {}
    for use in symbol.uses:
        projects.setdefault(use.project, []).append(
            node(
                "path",
                Atom.string(use.path),
                node("reference", Atom.string(use.ref)),
                node("unit", Atom.integer(use.unit)),
            )
        )
    if projects:
        children.append(
            node("instances", *(node("project", Atom.string(p), *paths) for p, paths in projects.items()))
        )
    return node("symbol", *children)


def _created_label(label: NetLabel, ten: bool) -> Node:
    head = next(h for h, kind in LABEL_HEADS.items() if kind == label.kind)
    justify = "left" if label.rotation in (0, 90_000_000) else "right"
    children: list[Node | Atom] = [Atom.string(label.name)]
    if label.shape:
        children.append(node("shape", Atom.symbol(label.shape)))
    children += [
        _at(label.position, label.rotation),
        _font(node("justify", Atom.symbol(justify))),
        node("uuid", Atom.string(kicad_uuid(label))),
    ]
    if ten and label.kind == "global":
        children.append(_property(*INTERSHEET, label.position, ten=True, hidden=True, justify=justify))
    return node(head, *children)


def _created_def(symbol: SymbolDef, target: int) -> Node:
    """The node of an embedded symbol of a created sheet, from the slots its reader kept."""
    bag = symbol.ext.get("kicad")
    if bag is None or not slotlib.from_ext(bag):
        raise ValueError(
            f"embedded symbol {symbol.lib_id} has no KiCad slot list; build it with symembed.embed_symbol"
        )
    built = _entity_node(symbol)
    if target >= 10:
        return built
    spelled = (Atom.symbol("global"),)
    children = [
        node("power") if isinstance(c, Node) and c.name == "power" and c.atoms() == spelled else c
        for c in built.children
    ]
    return built.with_children(children)


def write_schematic(
    sheet: SchematicSheet, *, target: int = DEFAULT_TARGET, allow_lossy: bool = False
) -> WriteResult:
    """The text of a ``.kicad_sch`` file for KiCad ``target``.0 from a created sheet; no file is written.

    The root holds the header, the sheet's uuid, paper and title block, the embedded symbols, then the
    no-connect flags, the labels and the symbol instances, each kind in the order of its collection, and
    the page list. Target 10 writes what KiCad 10 keeps on a re-save (``body_style``, ``in_pos_files``,
    ``show_name``, ``do_not_autoplace``, ``hide`` as a child of a property, ``Intersheetrefs``); target 9
    writes what 9.0.9 loads (``hide`` inside ``effects``, no ``body_style``, ``embedded_fonts``). A sheet
    read from a file is refused: ``rebuild_schematic`` writes it at its own version.
    """
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    if source_info(sheet) is not None:
        raise ValueError(
            f"{sheet.id} was read from a KiCad file; rebuild_schematic writes it at its own format version"
        )
    if sheet.sheets:
        raise ValueError(f"{sheet.id}: sheet references of a created sheet are not written yet")
    ten = target >= 10
    definitions = {_embedded_name(d): d for d in sheet.lib_symbols}
    children: list[Node | Atom] = [
        node("version", Atom.integer(FORMAT_VERSIONS[FileKind.SCHEMATIC][target])),
        node("generator", Atom.string("fenolite")),
        node("generator_version", Atom.string(f"{target}.0")),
        node("uuid", Atom.string(kicad_uuid(sheet))),
        paper_node(sheet.paper),
    ]
    if sheet.title_block is not None:
        children.append(title_block_node(sheet.title_block))
    children.append(node("lib_symbols", *(_created_def(d, target) for d in sheet.lib_symbols)))
    for flag in sheet.no_connects:
        children.append(
            node("no_connect", _at(flag.position, None), node("uuid", Atom.string(kicad_uuid(flag))))
        )
    children += [_created_label(label, ten) for label in sheet.labels]
    for symbol in sheet.symbols:
        definition = definitions.get(symbol.lib_name or symbol.lib_ref)
        children.append(_created_symbol(symbol, definition, ten))
    children.append(_pages_node(sheet.pages))
    if not ten:
        children.append(_yes_no("embedded_fonts", False))
    issues: list[Issue] = []
    root = gate_created(Node(Atom.symbol("kicad_sch"), tuple(children)), target, allow_lossy, issues)
    return WriteResult(dumps(root), tuple(issues))


# --- queries --------------------------------------------------------------------------------------


@dataclass(slots=True)
class _Walk:
    files: list[str] = field(default_factory=lambda: [])
    references: dict[str, int] = field(default_factory=lambda: {})
    issues: list[Issue] = field(default_factory=lambda: [])


def _relative(path: Path, base: Path) -> str | None:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return None


def sheet_files(root_file: str | os.PathLike[str]) -> SheetTree:
    """The schematic files of the hierarchy under ``root_file``, breadth first.

    Each sheet reference is resolved against the folder of the file that holds it. A file is read once;
    a reference to a file on its own path from the root is a cycle and is not followed.
    """
    root = Path(os.fspath(root_file))
    base = Path(os.path.normpath(root.parent.absolute()))
    start = base / root.name
    walk = _Walk([root.name], {root.name: 0})
    queue: deque[tuple[Path, tuple[Path, ...]]] = deque([(start, (start,))])
    read: set[Path] = {start}
    while queue:
        path, trail = queue.popleft()
        label = _relative(path, base) or path.as_posix()
        sheet = read_schematic(path, file=label)
        for ref in sheet.sheets:
            if not ref.file:
                continue
            target = Path(os.path.normpath(path.parent / PurePosixPath(ref.file.replace("\\", "/"))))
            name = _relative(target, base)
            shown = name if name is not None else PurePosixPath(os.path.relpath(target, base)).as_posix()
            shown = shown.replace(os.sep, "/")
            where = f"{label}:{ref.name}"
            if target in trail:
                walk.issues.append(
                    Issue(
                        "kicad.sch.sheet-cycle",
                        ISSUE_CODES["kicad.sch.sheet-cycle"],
                        f"sheet {ref.name!r} of {label} names {shown}, a file on its own path from the root",
                        where=where,
                    )
                )
                continue
            if name is None:
                walk.references[shown] = walk.references.get(shown, 0) + 1
                if shown not in walk.files:
                    walk.files.append(shown)
                    walk.issues.append(
                        Issue(
                            "kicad.sch.sheet-outside",
                            ISSUE_CODES["kicad.sch.sheet-outside"],
                            f"sheet {ref.name!r} of {label} names {shown}, outside the root file's folder; "
                            "it is listed and not read",
                            where=where,
                        )
                    )
                continue
            if not target.is_file():
                walk.issues.append(
                    Issue(
                        "kicad.sch.sheet-missing",
                        ISSUE_CODES["kicad.sch.sheet-missing"],
                        f"sheet {ref.name!r} of {label} names {shown}, which does not exist",
                        where=where,
                    )
                )
                continue
            walk.references[name] = walk.references.get(name, 0) + 1
            if target not in read:
                read.add(target)
                walk.files.append(name)
                queue.append((target, (*trail, target)))
    return SheetTree(tuple(walk.files), MappingProxyType(dict(walk.references)), tuple(walk.issues))


def components(
    sheets: Iterable[SchematicSheet], *, project: str, on_board_only: bool = False
) -> tuple[SchComponent, ...]:
    """One component per reference of the uses of ``project``, sorted by reference.

    References that start with ``#`` are left out. The units of one symbol count once, with the value
    and footprint of the instance with the lowest unit. No file is read and no net is derived.
    """
    best: dict[str, tuple[int, SchComponent]] = {}
    for sheet in sheets:
        for symbol in sheet.symbols:
            if on_board_only and not symbol.on_board:
                continue
            for use in symbol.uses:
                if use.project != project or not use.ref or use.ref.startswith("#"):
                    continue
                known = best.get(use.ref)
                if known is None or use.unit < known[0]:
                    best[use.ref] = (use.unit, SchComponent(use.ref, symbol.value, symbol.footprint))
    return tuple(best[ref][1] for ref in sorted(best))


def hierarchy_components(
    root_file: str | os.PathLike[str], *, on_board_only: bool = False
) -> tuple[SchComponent, ...]:
    """One component per reference of the hierarchy under ``root_file``, as KiCad resolves it.

    The hierarchy is walked from the root: the root sheet has the instance path ``/<root uuid>``, and a
    sheet reference with uuid ``U`` gives its file the path ``<parent path>/U``, once per reference. A
    symbol takes the reference and unit of its use with that path (the use of the project named after
    the root file when several projects hold the path, else the first one), and the reference of its
    ``Reference`` property when no use has the path. The rules of ``components`` apply afterwards:
    references that start with ``#`` are left out and the lowest unit gives value and footprint. Files
    outside the root file's folder, missing files and cycles are not followed (``sheet_files`` reports
    them). No net is derived.
    """
    root = Path(os.fspath(root_file))
    base = Path(os.path.normpath(root.parent.absolute()))
    start = base / root.name
    project = root.stem
    sheets: dict[Path, SchematicSheet] = {}
    best: dict[str, tuple[int, SchComponent]] = {}
    queue: deque[tuple[Path, str | None, tuple[Path, ...]]] = deque([(start, None, (start,))])
    while queue:
        path, at, trail = queue.popleft()
        sheet = sheets.get(path)
        if sheet is None:
            sheet = sheets[path] = read_schematic(path, file=_relative(path, base) or path.as_posix())
        here = at if at is not None else "/" + sheet.native_ids.get("kicad", "")
        for symbol in sheet.symbols:
            if on_board_only and not symbol.on_board:
                continue
            uses = [use for use in symbol.uses if use.path == here]
            use = next((u for u in uses if u.project == project), uses[0] if uses else None)
            ref, unit = (use.ref, use.unit) if use is not None else (symbol.ref, symbol.unit)
            if not ref or ref.startswith("#"):
                continue
            known = best.get(ref)
            if known is None or unit < known[0]:
                best[ref] = (unit, SchComponent(ref, symbol.value, symbol.footprint))
        for ref_ in sheet.sheets:
            uuid = ref_.native_ids.get("kicad")
            if not ref_.file or uuid is None:
                continue
            target = Path(os.path.normpath(path.parent / PurePosixPath(ref_.file.replace("\\", "/"))))
            if target in trail or _relative(target, base) is None or not target.is_file():
                continue
            queue.append((target, f"{here}/{uuid}", (*trail, target)))
    return tuple(best[ref][1] for ref in sorted(best))


__all__ = [
    "EVIDENCE",
    "ISSUE_CODES",
    "KEPT_CODE",
    "SchComponent",
    "SheetTree",
    "WRITE_EVIDENCE",
    "WRITE_ISSUE_CODES",
    "components",
    "gate_created",
    "hierarchy_components",
    "opaque_count",
    "opaque_digests",
    "opaque_heads",
    "read_schematic",
    "rebuild_schematic",
    "roundtrip_schematic",
    "sheet_files",
    "source_info",
    "write_schematic",
]
