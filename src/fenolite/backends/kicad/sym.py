# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Symbol libraries (``.kicad_sym`` files and ``.kicad_symdir`` folders) as ``SymbolDef`` definitions.

Facts, mapping tables and sources: ``docs/formats/kicad/libraries.md``. Symbols are read-only
projections: every sub-symbol stays an opaque slot of its symbol, and units and pins are projected
from it. ``read_symbol_library`` returns derived symbols as written; ``resolve_extends`` flattens them.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import replace
from math import isqrt
from pathlib import Path
from types import MappingProxyType
from typing import get_args

from fenolite.backends.kicad import resolver
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad._libread import (
    Context,
    Loaded,
    Source,
    child_locators,
    leading_atoms,
    load_source,
)
from fenolite.backends.kicad.liberrors import lib_error
from fenolite.backends.kicad.sexpr import AtomKind, Node, dumps, parse
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind, check_target, inspect, is_downgrade
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.model.base import Slot
from fenolite.model.circuit import PinType
from fenolite.model.library import (
    PinAlternate,
    PinShape,
    PowerKind,
    SymbolDef,
    SymbolGraphic,
    SymbolPin,
    SymbolUnit,
)

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-LIB-READ",))
WRITE_EVIDENCE = Evidence(Level.UNVERIFIED)
"""``write_symbol_library`` (the symbols a design authors, change c0058) has no row in the register,
so the matrix lists it as experimental (declared by change c0067)."""
TILDE_UNTIL = 20250318
"""Symbol-library version from which ``~`` is a literal tilde instead of empty text (S-0031)."""
SYMBOL_FIELDS: Mapping[str, str] = MappingProxyType(
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
PIN_TYPES: frozenset[str] = frozenset(get_args(PinType))
PIN_SHAPES: frozenset[str] = frozenset(get_args(PinShape))
PIN_ANGLES: frozenset[int] = frozenset({0, 90_000_000, 180_000_000, 270_000_000})
_BOOLEANS = {"yes": True, "no": False}
_CHAIN = ("kicad_symbol_lib", "symbol")


def split_unit_name(parent: str, name: str) -> tuple[int, int]:
    """``("R", "R_1_2") -> (1, 2)``: unit and body style of a sub-symbol (0 means common to all)."""
    prefix = parent + "_"
    parts = name[len(prefix) :].split("_") if name.startswith(prefix) else []
    if len(parts) != 2 or not all(p.isdigit() and p.isascii() for p in parts):
        raise ValueError(f"sub-symbol {name!r} of {parent!r} is not named '{parent}_<unit>_<body style>'")
    return int(parts[0]), int(parts[1])


def write_symbol_library(symbols: Sequence[SymbolDef], *, target: int = 10) -> str:
    """Serialize the simple authored symbol subset as a KiCad symbol library."""

    def q(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def mm(value: Nm) -> str:
        whole, rem = divmod(abs(value), 1_000_000)
        return ("-" if value < 0 else "") + str(whole) + (f".{rem:06d}".rstrip("0") if rem else "")

    def xy(point: Point) -> str:
        return f"(xy {mm(point.x)} {mm(point.y)})"

    def graphic_text(graphic: SymbolGraphic) -> list[str]:
        points = graphic.points
        width = graphic.width or 254_000
        stroke = f"(stroke (width {mm(width)}) (type default))"
        fill = "background" if graphic.filled else "none"
        if graphic.kind == "line":
            body = f"(polyline (pts {xy(points[0])} {xy(points[1])}) {stroke} (fill (type {fill})))"
        elif graphic.kind == "rect":
            body = (
                f"(rectangle (start {mm(points[0].x)} {mm(points[0].y)}) "
                f"(end {mm(points[1].x)} {mm(points[1].y)}) {stroke} (fill (type {fill})))"
            )
        elif graphic.kind == "circle":
            dx, dy = points[1].x - points[0].x, points[1].y - points[0].y
            body = (
                f"(circle (center {mm(points[0].x)} {mm(points[0].y)}) "
                f"(radius {mm(isqrt(dx * dx + dy * dy))}) {stroke} (fill (type {fill})))"
            )
        else:
            closed = points if points[-1] == points[0] else (*points, points[0])
            pts = " ".join(xy(point) for point in closed)
            body = f"(polyline (pts {pts}) {stroke} (fill (type {fill})))"
        return [f"\t\t\t{body}"]

    version = FORMAT_VERSIONS[FileKind.SYMBOL_LIB][target]
    out = ["(kicad_symbol_lib", f"\t(version {version})", '\t(generator "fenolite")']
    for symbol in sorted(symbols, key=lambda item: item.lib_id):
        out += [
            f"\t(symbol {q(symbol.name)}",
            f"\t\t(exclude_from_sim {'yes' if symbol.exclude_from_sim else 'no'})",
            f"\t\t(in_bom {'yes' if symbol.in_bom else 'no'})",
            f"\t\t(on_board {'yes' if symbol.on_board else 'no'})",
        ]
        props = symbol.properties
        for key, default, y in (
            ("Reference", "U", 2_540_000),
            ("Value", symbol.name, 0),
            ("Footprint", "", -2_540_000),
            ("Datasheet", "", -5_080_000),
            ("Description", "", 0),
        ):
            value = props.get(key, default)
            if key == "Description" and not value:
                continue
            out += [
                f"\t\t(property {q(key)} {q(value)}",
                f"\t\t\t(at 0 {mm(y)} 0)",
                "\t\t\t(effects (font (size 1.27 1.27)) (justify left))",
                "\t\t)",
            ]
        out += [
            f"\t\t(pin_names (offset 0.508) (hide {'yes' if symbol.pin_names_hidden else 'no'}))",
            f"\t\t(pin_numbers (hide {'yes' if symbol.pin_numbers_hidden else 'no'}))",
        ]
        out += [f"\t\t(symbol {q(symbol.name + '_0_1')}"]
        if symbol.graphics:
            for graphic in symbol.graphics:
                out.extend(graphic_text(graphic))
        else:
            xs = [pin.position.x for pin in symbol.pins]
            ys = [pin.position.y for pin in symbol.pins]
            margin = 1_270_000
            out.append(
                f"\t\t\t(rectangle (start {mm(min(xs) - margin)} {mm(min(ys) - margin)}) "
                f"(end {mm(max(xs) + margin)} {mm(max(ys) + margin)}) "
                "(stroke (width 0.254) (type default)) (fill (type background)))"
            )
        out += ["\t\t)", f"\t\t(symbol {q(symbol.name + '_1_1')}"]
        for pin in symbol.pins:
            out += [
                f"\t\t\t(pin {pin.etype} {pin.shape}",
                f"\t\t\t\t(at {mm(pin.position.x)} {mm(pin.position.y)} {pin.rotation // 1_000_000})",
                f"\t\t\t\t(length {mm(pin.length)})",
                f"\t\t\t\t(name {q(pin.name)} (effects (font (size 1.27 1.27))))",
                f"\t\t\t\t(number {q(pin.number)} (effects (font (size 1.27 1.27))))",
                "\t\t\t)",
            ]
        out += ["\t\t)", "\t)"]
    return "\n".join(out + [")", ""])


def retarget_symbol_library(
    text: str,
    *,
    target: int,
    downgrade: bool = False,
    allow_lossy: bool = False,
    file: str = "",
    issues: list[Issue] | None = None,
    edits: list[resolver.Edit] | None = None,
) -> str:
    """The text of a ``.kicad_sym`` library read from a file, written for KiCad ``target``.0 (change
    c0162). ``write_symbol_library`` writes the authored subset of the model; a library read from a file
    keeps every symbol as written, so its downgrade is made on its tree: the header of ``target``, and each
    construct newer than ``target`` resolved by ``resolver.resolve`` (a ``design`` loss needs
    ``allow_lossy``). A library of a newer major is refused (``DowngradeRefusedError``) unless
    ``downgrade``; one not newer than ``target`` is returned unchanged. Nothing is written to disk."""
    root = parse(text, file=file)
    info = inspect(root, file=file)
    version = check_target(info, target, downgrade=downgrade)
    if not is_downgrade(info, target):
        return text
    found = resolver.downgraded(
        root, FileKind.SYMBOL_LIB, version, target, allow_lossy=allow_lossy, edits=edits, issues=issues
    )
    return dumps(found)


def _hidden(node: Node) -> bool:
    """Hidden by a bare ``hide`` atom (8.0 grammar) or by ``(hide yes)``."""
    if any(a.kind == AtomKind.SYMBOL and a.text == "hide" for a in node.atoms()):
        return True
    hide = node.find("hide")
    return hide is not None and [a.value for a in hide.atoms()] in ([], ["yes"])


class _Reader:
    def __init__(self, ctx: Context, library: str, chain: tuple[str, ...] = _CHAIN) -> None:
        self.ctx = ctx
        self.library = library
        self.chain = chain
        self.tilde = ctx.version < TILDE_UNTIL

    def text(self, value: str) -> str:
        return "" if self.tilde and value == "~" else value

    def first(self, node: Node | None) -> str:
        atoms = node.atoms() if node is not None else ()
        return self.text(atoms[0].value) if atoms else ""

    def vocab(self, value: str, allowed: frozenset[str], what: str, loc: str, node: Node) -> str:
        if value not in allowed:
            raise self.ctx.error(f"unknown {what} {value!r}", loc, node)
        return value

    def pin(self, node: Node, loc: str, unit: int, style: int) -> SymbolPin:
        ctx = self.ctx
        atoms = leading_atoms(node)
        if len(atoms) < 2:
            raise ctx.error("a pin needs an electrical type and a graphic style", loc, node)
        etype = self.vocab(atoms[0].value, PIN_TYPES, "pin electrical type", loc, node)
        shape = self.vocab(atoms[1].value, PIN_SHAPES, "pin graphic style", loc, node)
        at = node.find("at")
        if at is None:
            raise ctx.error("pin has no position", loc, node)
        at_loc = f"{loc}/at[0]"
        position = ctx.point(at, at_loc)
        values = at.atoms()
        angle = values[2] if len(values) > 2 else None
        rotation = ctx.udeg(angle, at_loc, at) if angle is not None else 0
        if rotation not in PIN_ANGLES:
            raise ctx.error(f"pin angle {angle.text if angle else '0'!r} is not 0, 90, 180 or 270", loc, node)
        length_node = node.find("length")
        length_atoms = length_node.atoms() if length_node is not None else ()
        length = (
            ctx.nm(length_atoms[0], f"{loc}/length[0]", length_node) if length_node and length_atoms else 0
        )
        alternates: list[PinAlternate] = []
        for alt_loc, alt in child_locators(loc, node):
            if isinstance(alt, Node) and alt.name == "alternate":
                parts = alt.atoms()
                if len(parts) < 3:
                    raise ctx.error("an alternate needs a name, an electrical type and a style", alt_loc, alt)
                alternates.append(
                    PinAlternate(
                        self.text(parts[0].value),
                        self.vocab(parts[1].value, PIN_TYPES, "pin electrical type", alt_loc, alt),  # type: ignore[arg-type]
                        self.vocab(parts[2].value, PIN_SHAPES, "pin graphic style", alt_loc, alt),  # type: ignore[arg-type]
                    )
                )
        return SymbolPin(
            number=self.first(node.find("number")),
            name=self.first(node.find("name")),
            etype=etype,  # type: ignore[arg-type]
            position=position,
            shape=shape,  # type: ignore[arg-type]
            rotation=rotation,
            length=length,
            unit=unit,
            body_style=style,
            hidden=_hidden(node),
            alternates=tuple(alternates),
        )

    def graphic(self, node: Node, loc: str) -> SymbolGraphic:
        ctx = self.ctx
        if node.name == "rectangle":
            start, end = node.find("start"), node.find("end")
            if start is None or end is None:
                raise ctx.error("symbol rectangle needs start and end", loc, node)
            points = (ctx.point(start, f"{loc}/start"), ctx.point(end, f"{loc}/end"))
            kind = "rect"
        elif node.name == "circle":
            center, radius = node.find("center"), node.find("radius")
            if center is None or radius is None or not radius.atoms():
                raise ctx.error("symbol circle needs center and radius", loc, node)
            at = ctx.point(center, f"{loc}/center")
            r = ctx.nm(radius.atoms()[0], f"{loc}/radius[0]", radius)
            if r <= 0:
                raise ctx.error("symbol circle radius must be positive", loc, node)
            points, kind = (at, Point(at.x + r, at.y)), "circle"
        else:
            pts = node.find("pts")
            if pts is None:
                raise ctx.error("symbol polyline needs points", loc, node)
            points = tuple(
                ctx.point(child, f"{loc}/pts/{child.name}")
                for _, child in child_locators(f"{loc}/pts", pts)
                if isinstance(child, Node) and child.name == "xy"
            )
            if len(points) < 2:
                raise ctx.error("symbol polyline needs at least two points", loc, node)
            kind = "line" if len(points) == 2 else "polygon"
            if kind == "polygon" and points[0] == points[-1]:
                points = points[:-1]
        stroke = node.find("stroke")
        width_node = stroke.find("width") if stroke is not None else None
        width = (
            ctx.nm(width_node.atoms()[0], f"{loc}/stroke/width[0]", width_node)
            if width_node is not None and width_node.atoms()
            else 254_000
        )
        fill_node = node.find("fill")
        fill_type_node = fill_node.find("type") if fill_node is not None else None
        fill_type = (
            fill_type_node.atoms()[0].value
            if fill_type_node is not None and fill_type_node.atoms()
            else "none"
        )
        return SymbolGraphic(kind, points, width, fill_type in ("background", "outline"))  # type: ignore[arg-type]

    def symbol(
        self, node: Node, loc: str, *, name: str | None = None, native: str | None = None
    ) -> SymbolDef:
        """One symbol node; ``name`` and ``native`` replace what the node's own name gives (a symbol
        embedded in a schematic is named ``<library>:<name>`` and its sub-symbols ``<name>_<u>_<s>``)."""
        ctx = self.ctx
        atoms = leading_atoms(node)
        if not atoms:
            raise ctx.error("symbol has no name", loc, node)
        if name is None:
            name = atoms[0].value
        if native is None:
            native = f"{self.library}:{name}" if self.library else name
        slots: list[Slot] = ctx.split(node, dict(SYMBOL_FIELDS), self.chain, ("name",))
        fields: dict[str, object] = {}
        properties: dict[str, str] = {}
        units: list[SymbolUnit] = []
        pins: list[SymbolPin] = []
        graphics: list[SymbolGraphic] = []
        for index, (child_loc, child) in enumerate(child_locators(loc, node)):
            if not isinstance(child, Node):
                continue
            head = child.name
            values = [a.value for a in child.atoms()]
            if head == "extends":
                fields["extends"] = values[0] if values else ""
            elif head == "power":
                if values in ([], ["global"], ["local"]):
                    fields["power"] = "local" if values == ["local"] else "global"
                else:
                    self.opaque(slots, index, child, child_loc, f"power {' '.join(values)!r} is not modelled")
            elif head == "pin_names":
                offset = child.find("offset")
                if offset is not None and offset.atoms():
                    fields["pin_name_offset"] = ctx.nm(offset.atoms()[0], f"{child_loc}/offset[0]", offset)
                fields["pin_names_hidden"] = _hidden(child)
            elif head == "pin_numbers":
                fields["pin_numbers_hidden"] = _hidden(child)
            elif head in ("in_bom", "on_board", "exclude_from_sim"):
                if len(values) == 1 and values[0] in _BOOLEANS:
                    fields[head] = _BOOLEANS[values[0]]
                else:
                    self.opaque(
                        slots, index, child, child_loc, f"{head} {' '.join(values)!r} is not modelled"
                    )
            elif head == "property":
                head_atoms = leading_atoms(child)
                if len(head_atoms) >= 2:
                    properties[head_atoms[0].value] = self.text(head_atoms[1].value)
            elif head == "symbol":
                sub = child.atoms()[0].value if child.atoms() else ""
                try:
                    unit, style = split_unit_name(name, sub)
                except ValueError as exc:
                    raise ctx.error(str(exc), child_loc, child) from None
                unit_name = child.find("unit_name")
                label = unit_name.atoms()[0].value if unit_name is not None and unit_name.atoms() else ""
                units.append(SymbolUnit(unit, style, label))
                for pin_loc, pin in child_locators(child_loc, child):
                    if isinstance(pin, Node):
                        if pin.name == "pin":
                            pins.append(self.pin(pin, pin_loc, unit, style))
                        elif pin.name in ("polyline", "rectangle", "circle"):
                            graphics.append(self.graphic(pin, pin_loc))
        power: PowerKind = fields.pop("power", "")  # type: ignore[assignment]
        return SymbolDef(
            id=derived_id("sym", "kicad", native),
            native_ids={"kicad": native},
            provenance=ctx.provenance(loc),
            ext={"kicad": slotlib.to_ext(slots)},
            name=name,
            library=self.library,
            power=power,
            properties=properties,
            units=tuple(units),
            pins=tuple(pins),
            graphics=tuple(graphics),
            **fields,  # type: ignore[arg-type]
        )

    def opaque(self, slots: list[Slot], index: int, child: Node, loc: str, why: str) -> None:
        slots[index] = self.ctx.opaque(child, self.chain)
        self.ctx.kept_opaque(why, loc)


def symbol_from(
    node: Node,
    *,
    library: str,
    name: str,
    native: str,
    ctx: Context,
    locator: str = "/symbol[0]",
    chain: tuple[str, ...] = _CHAIN,
) -> SymbolDef:
    """The symbol reader on one node, for a symbol that is not a child of a library root (a symbol
    embedded in a schematic): the caller names the library, the symbol and the native id."""
    return _Reader(ctx, library, chain).symbol(node, locator, name=name, native=native)


def _read_file(source: Source, library: str, file: str, issues: list[Issue]) -> tuple[SymbolDef, ...]:
    return symbols_from(load_source(source, file), library=library, issues=issues)


def symbols_from(loaded: Loaded, *, library: str, issues: list[Issue] | None = None) -> tuple[SymbolDef, ...]:
    """The symbols of one already loaded file (the resolver's parse cache), as written."""
    ctx = Context(loaded, FileKind.SYMBOL_LIB, EVIDENCE, issues if issues is not None else [])
    ctx.check_version("kicad_symbol_lib", FileKind.SYMBOL_LIB)
    reader = _Reader(ctx, library)
    return tuple(
        reader.symbol(child, loc)
        for loc, child in child_locators("/kicad_symbol_lib", loaded.node)
        if isinstance(child, Node) and child.name == "symbol"
    )


def read_symbol_library(
    source: Source, *, library: str | None = None, file: str = "", issues: list[Issue] | None = None
) -> tuple[SymbolDef, ...]:
    """The top-level symbols of a ``.kicad_sym`` file, a symbol folder, file text or a parsed node."""
    sink = issues if issues is not None else []
    if isinstance(source, (str, Node)):
        return _read_file(source, library or "", file, sink)
    path = Path(os.fspath(source))
    name = library if library is not None else path.stem
    if not path.is_dir():
        return _read_file(path, name, file, sink)
    out: list[SymbolDef] = []
    for child in sorted(p for p in path.glob("*.kicad_sym") if p.is_file()):
        label = f"{file}/{child.name}" if file else os.fspath(child)
        out.extend(_read_file(child, name, label, sink))
    return tuple(out)


def resolve_extends(
    symbols: Sequence[SymbolDef], *, issues: list[Issue] | None = None
) -> tuple[SymbolDef, ...]:
    """One flattened definition per input symbol: derived symbols receive their root parent's body."""
    del issues  # flattening reports errors only, raised as LibraryError
    by_name: dict[str, SymbolDef] = {}
    for symbol in symbols:
        by_name.setdefault(symbol.name, symbol)
    flat: dict[str, SymbolDef] = {}

    def resolve(symbol: SymbolDef) -> SymbolDef:
        chain = [symbol]
        while chain[-1].extends and chain[-1].name not in flat:
            parent_name = chain[-1].extends
            if any(s.name == parent_name for s in chain):
                names = " -> ".join([*(s.name for s in chain), parent_name])
                raise lib_error(
                    "kicad.lib.extends-cycle", f"symbol extends chain loops: {names}", where=symbol.lib_id
                )
            parent = by_name.get(parent_name)
            if parent is None:
                raise lib_error(
                    "kicad.lib.missing-parent",
                    f"symbol {chain[-1].name!r} extends {parent_name!r}, which is not in the library",
                    where=chain[-1].lib_id,
                )
            chain.append(parent)
        base = flat.get(chain[-1].name, chain[-1])
        for derived in reversed(chain[:-1]):
            base = replace(
                derived,
                power=base.power,
                in_bom=base.in_bom,
                on_board=base.on_board,
                exclude_from_sim=base.exclude_from_sim,
                pin_names_hidden=base.pin_names_hidden,
                pin_numbers_hidden=base.pin_numbers_hidden,
                pin_name_offset=base.pin_name_offset,
                units=base.units,
                pins=base.pins,
                graphics=base.graphics,
                properties={**base.properties, **derived.properties},
            )
            flat[derived.name] = base
        return base if symbol.extends else symbol

    return tuple(resolve(s) for s in symbols)


__all__ = [
    "EVIDENCE",
    "PIN_ANGLES",
    "PIN_SHAPES",
    "PIN_TYPES",
    "SYMBOL_FIELDS",
    "TILDE_UNTIL",
    "read_symbol_library",
    "retarget_symbol_library",
    "resolve_extends",
    "split_unit_name",
    "symbol_from",
]
