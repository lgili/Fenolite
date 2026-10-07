# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The symbol definitions a generated schematic embeds, and the project libraries that hold the same
definitions (capability ``kicad-schematic``, "Embedded symbols of a generated sheet"; change c0061).

A definition is built from the children its library file holds (the slots of the resolved ``SymbolDef``):
a derived symbol is flattened onto its root parent, the pins of a component with a ``pin_pad_map`` take
their pad numbers under a variant name, and a hidden power-input pin is shown, because KiCad joins hidden
power inputs of one name into one global net whatever label they carry (``H-K-SCH-POWER``). The embedded
copy and the library copy are one node under two names, so KiCad's ERC finds them equal
(``H-K-SCH-LIBTABLE``). ``power_flag`` is authored for Fenolite; nothing of any KiCad library is in it.
"""

# evidence: see schgen

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from fenolite.backends.kicad import sch
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad._fpmap import node
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, parse
from fenolite.backends.kicad.sym import TILDE_UNTIL, split_unit_name
from fenolite.backends.kicad.sym import write_symbol_library as write_authored_library
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, TARGET_MAJORS, FileKind
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import content_hash
from fenolite.model.base import Opaque
from fenolite.model.library import SymbolDef

FLAG_LIBRARY = "fenolite"
"""The nickname of the library that holds Fenolite's own symbols; a design may not use it."""
FLAG_NAME = "PWR_FLAG"
FLAG_REFERENCE = "#FLG"
SHOWN_CODE = "kicad.sch.power-pin-shown"
STACKED_TYPE = "passive"
"""The electrical type of a stacked pin, the pin that stands for a further pad of a pin bonded to several
(change c0123). ``passive`` joins any pin without an ERC conflict; a second ``power_in`` or ``output`` of
the pin's own type is the other choice, and this constant is its one place."""
STACKED_HIDDEN = True
"""A stacked pin is hidden: the sheet shows the first pad of the pin, and the others are in the symbol's
pin table. ``False`` draws every number, on top of each other."""
_HIDDEN = "(at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))"
_FLAG_DESCRIPTION = (
    "Power flag authored for Fenolite: it tells the electrical rules check that its net is driven"
)
_FLAG_TEXT = f"""(symbol "PWR_FLAG"
	(power)
	(pin_numbers (hide yes))
	(pin_names (offset 0) (hide yes))
	(exclude_from_sim no)
	(in_bom no)
	(on_board no)
	(property "Reference" "#FLG" (at 0 5.08 0) (effects (font (size 1.27 1.27)) (hide yes)))
	(property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
	(property "Footprint" "" {_HIDDEN})
	(property "Datasheet" "" {_HIDDEN})
	(property "Description" "{_FLAG_DESCRIPTION}" {_HIDDEN})
	(symbol "PWR_FLAG_0_1"
		(polyline (pts (xy 0 0) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
		(rectangle (start 0 2.54) (end 2.54 1.27) (stroke (width 0) (type default)) (fill (type none)))
	)
	(symbol "PWR_FLAG_1_1"
		(pin power_out line (at 0 0 90) (length 0)
			(name "pwr" (effects (font (size 1.27 1.27))))
			(number "1" (effects (font (size 1.27 1.27))))
		)
	)
)"""
"""A staff with a small rectangular flag and one power-output pin at the origin: drawn for Fenolite."""


@dataclass(frozen=True, slots=True)
class EmbeddedSymbol:
    """One definition of a generated sheet. ``node`` is named ``<nickname>:<name>``; ``definition`` is
    that node as the schematic reader models it, which ``sch.write_schematic`` writes back; ``authored``
    holds the design's own definition when the symbol is authored and has no pin-pad variant."""

    lib_id: str
    nickname: str
    name: str
    node: Node
    definition: SymbolDef
    authored: SymbolDef | None = None


def variant_name(name: str, pin_pad_map: Sequence[tuple[str, str]]) -> str:
    """``<name>_<8 hex digits>``: the name of ``name`` with the pin numbers of ``pin_pad_map``."""
    return f"{name}_{content_hash([list(pair) for pair in variant_pairs(pin_pad_map)])[:8]}"


def variant_pairs(pin_pad_map: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """The pairs of a map in the order that names and keys a variant: sorted by pin, the pads of one pin in
    map order, since the first is the one the symbol shows. For a map of one pad per pin these are the
    sorted pairs."""
    return tuple(sorted(((str(pin), str(pad)) for pin, pad in pin_pad_map), key=lambda pair: pair[0]))


def pad_groups(pin_pad_map: Sequence[tuple[str, str]]) -> dict[str, tuple[str, ...]]:
    """Pin → its pads in map order (``Component.pin_pads`` of the pairs)."""
    found: dict[str, list[str]] = {}
    for pin, pad in pin_pad_map:
        found.setdefault(str(pin), []).append(str(pad))
    return {pin: tuple(pads) for pin, pads in found.items()}


def _stacked(pin: Node, number: str) -> Node:
    """The pin that stands for the further pad ``number`` of ``pin``: at its place, with its length and
    name, of type ``STACKED_TYPE``, hidden when ``STACKED_HIDDEN``, and without alternates."""
    children: list[Node | Atom] = [Atom.symbol(STACKED_TYPE), Atom.symbol("line")]
    for child in pin.children:
        if isinstance(child, Atom) or _is_hide(child) or child.name == "alternate":
            continue
        children.append(_set_text(child, number) if child.name == "number" else child)
        if child.name == "length" and STACKED_HIDDEN:
            children.append(node("hide", Atom.symbol("yes")))
    return pin.with_children(children)


def _yes_no(head: str, value: bool) -> Node:
    return node(head, Atom.symbol("yes" if value else "no"))


def _modelled(symbol: SymbolDef, field: str, target: int) -> list[Node | Atom]:
    """The child of a library symbol that the reader modelled as ``field``, in the form ``target`` reads."""
    if field == "name":
        return [Atom.string(symbol.name)]
    if field == "extends":
        return [node("extends", Atom.string(symbol.extends))] if symbol.extends else []
    if field == "power":
        if not symbol.power:
            return []
        return [node("power", *((Atom.symbol(symbol.power),) if target >= 10 else ()))]
    hide = node("hide", Atom.symbol("yes"))
    if field == "pin_names_hidden":
        offset = symbol.pin_name_offset
        children = ([] if offset is None else [node("offset", Atom.from_nm(offset))]) + (
            [hide] if symbol.pin_names_hidden else []
        )
        return [node("pin_names", *children)]
    if field == "pin_numbers_hidden":
        return [node("pin_numbers", _yes_no("hide", symbol.pin_numbers_hidden))]
    if field in ("in_bom", "on_board", "exclude_from_sim"):
        return [_yes_no(field, getattr(symbol, field))]
    raise ValueError(f"symbol {symbol.lib_id} has a slot for the unknown field {field!r}")


def _own_node(symbol: SymbolDef, target: int) -> Node:
    """The node of one symbol as its library file holds it, modelled children in the target's form. A
    symbol without slots (one that a design authors) gets the node of ``sym.write_symbol_library``."""
    bag = symbol.ext.get("kicad")
    slots = slotlib.from_ext(bag) if bag is not None else ()
    if not slots:
        root = parse(write_authored_library([symbol], target=target))
        found = root.find("symbol")
        assert found is not None
        return found
    children: list[Node | Atom] = []
    for slot in slots:
        if isinstance(slot, Opaque):
            children.append(slotlib.opaque_child(slot))
        else:
            children += _modelled(symbol, slot.field, target)
    return Node(Atom.symbol("symbol"), tuple(children))


def _key(prop: Node) -> str:
    atoms = prop.atoms()
    return atoms[0].value if atoms else ""


def _renamed(item: Node, name: str) -> Node:
    """``item`` with its first atom replaced by the string ``name``."""
    children = list(item.children)
    index = next(i for i, child in enumerate(children) if isinstance(child, Atom))
    children[index] = Atom.string(name)
    return item.with_children(children)


def _flatten(chain: Sequence[Node], names: Sequence[str]) -> Node:
    """The node of ``chain[0]`` with the body of its root parent ``chain[-1]``: the root's children,
    each property replaced by the nearest derived symbol that has it, and the properties only derived
    symbols have after the root's own."""
    if len(chain) == 1:
        return chain[0]
    root, own_name, root_name = chain[-1], names[0], names[-1]
    properties: dict[str, Node] = {}
    for item in reversed(chain):
        for prop in item.nodes("property"):
            properties[_key(prop)] = prop
    inherited = {_key(prop) for prop in root.nodes("property")}
    extra = [prop for key, prop in properties.items() if key not in inherited]
    children: list[Node | Atom] = []
    last = max(
        (i for i, c in enumerate(root.children) if isinstance(c, Node) and c.name == "property"), default=-1
    )
    for index, child in enumerate(root.children):
        if isinstance(child, Atom):
            children.append(Atom.string(own_name) if not children else child)
        elif child.name == "property":
            children.append(properties[_key(child)])
        elif child.name == "symbol":
            unit, style = split_unit_name(root_name, child.atoms()[0].value)
            children.append(_renamed(child, f"{own_name}_{unit}_{style}"))
        elif child.name != "extends":
            children.append(child)
        if index == last:
            children += extra
    if last < 0:
        children += extra
    return Node(Atom.symbol("symbol"), tuple(children))


def _is_hide(child: Node | Atom) -> bool:
    if isinstance(child, Atom):
        return child.kind == AtomKind.SYMBOL and child.text == "hide"
    return child.name == "hide" and [a.value for a in child.atoms()] in ([], ["yes"])


def _first_text(item: Node | None) -> str:
    atoms = item.atoms() if item is not None else ()
    return atoms[0].value if atoms else ""


def _set_text(item: Node, text: str) -> Node:
    return _renamed(item, text)


def _pins(
    symbol: Node,
    name: str,
    numbers: Mapping[str, tuple[str, ...]],
    empty: set[tuple[str, str]],
    shown: list[str],
) -> Node:
    """``symbol`` with its sub-symbols renamed to ``name`` and their pins rewritten: mapped numbers (the
    first pad of a pin, and one stacked pin after it for each further pad), power inputs shown, and ``~``
    as the empty name where the library meant it (``empty`` holds the (number, name) pairs the reader gave
    an empty name)."""
    old = _first_text(symbol)
    children: list[Node | Atom] = []
    for child in symbol.children:
        if not isinstance(child, Node) or child.name != "symbol":
            children.append(child)
            continue
        unit, style = split_unit_name(old, _first_text(child))
        body: list[Node | Atom] = []
        for item in _renamed(child, f"{name}_{unit}_{style}").children:
            if not isinstance(item, Node) or item.name != "pin":
                body.append(item)
                continue
            number = _first_text(item.find("number"))
            pin_children = list(item.children)
            kinds = [a.value for a in item.atoms()]
            if kinds[:1] == ["power_in"] and any(_is_hide(c) for c in pin_children):
                pin_children = [c for c in pin_children if not _is_hide(c)]
                shown.append(number)
            for index, part in enumerate(pin_children):
                if not isinstance(part, Node):
                    continue
                if part.name == "name" and _first_text(part) == "~" and (number, "name") in empty:
                    pin_children[index] = _set_text(part, "")
                elif part.name == "number" and number in numbers:
                    pin_children[index] = _set_text(part, numbers[number][0])
            written = item.with_children(pin_children)
            body.append(written)
            body += [_stacked(written, pad) for pad in numbers.get(number, ())[1:]]
        children.append(child.with_children(body))
    return _renamed(symbol.with_children(children), name)


def _untilde(symbol: Node, definition: SymbolDef) -> Node:
    """Property texts written ``~`` that the reader took as empty become empty."""
    children: list[Node | Atom] = []
    for child in symbol.children:
        if isinstance(child, Node) and child.name == "property":
            atoms = [c for c in child.children if isinstance(c, Atom)]
            if len(atoms) >= 2 and atoms[1].value == "~" and definition.properties.get(atoms[0].value) == "":
                parts = list(child.children)
                parts[parts.index(atoms[1])] = Atom.string("")
                child = child.with_children(parts)
        children.append(child)
    return symbol.with_children(children)


def _modelled_copy(item: Node, nickname: str, name: str, target: int) -> SymbolDef:
    """``item`` as the schematic reader models an embedded symbol of a sheet in ``target``'s format."""
    version = FORMAT_VERSIONS[FileKind.SCHEMATIC][target]
    root = node("kicad_sch", node("version", Atom.integer(version)), node("lib_symbols", item))
    sheet = sch.read_schematic(root, file="")
    if len(sheet.lib_symbols) != 1:
        raise FormatError(
            f"symbol {nickname}:{name} holds a length or an angle that is not exact and cannot be embedded"
        )
    return sheet.lib_symbols[0]


def _finish(
    item: Node,
    nickname: str,
    name: str,
    target: int,
    allow_lossy: bool,
    issues: list[Issue] | None,
    authored: SymbolDef | None = None,
) -> EmbeddedSymbol:
    lib_id = f"{nickname}:{name}" if nickname else name
    named = _renamed(item, lib_id)
    version = FORMAT_VERSIONS[FileKind.SCHEMATIC][target]
    root = node("kicad_sch", node("version", Atom.integer(version)), node("lib_symbols", named))
    found: list[Issue] = []
    root = sch.gate_created(root, target, allow_lossy, found)
    if issues is not None:
        issues += found
    lib = root.find("lib_symbols")
    assert lib is not None
    named = lib.nodes("symbol")[0]
    return EmbeddedSymbol(
        lib_id, nickname, name, named, _modelled_copy(named, nickname, name, target), authored
    )


def embed_symbol(
    definition: SymbolDef,
    *,
    parents: Sequence[SymbolDef] = (),
    target: int,
    pin_numbers: Sequence[tuple[str, str]] | None = None,
    allow_lossy: bool = False,
    issues: list[Issue] | None = None,
) -> EmbeddedSymbol:
    """The definition a generated sheet embeds for ``definition``.

    ``definition`` is the resolved symbol (its own children as slots) and ``parents`` the symbols it
    extends as their library holds them, the nearest first. ``pin_numbers`` is a component's
    ``pin_pad_map``: its pins take those numbers (a pin of several pads its first, with one stacked pin
    per further pad) and the name of ``variant_name``. A token that ``target``
    does not read raises ``LossyWriteError``, or is dropped with a warning when ``allow_lossy`` is set.
    """
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    chain = [definition, *parents]
    flat = _flatten([_own_node(item, target) for item in chain], [item.name for item in chain])
    name = variant_name(definition.name, pin_numbers) if pin_numbers else definition.name
    literal = FORMAT_VERSIONS[FileKind.SCHEMATIC][target] >= TILDE_UNTIL
    empty: set[tuple[str, str]] = set()
    if literal:
        empty = {(pin.number, "name") for pin in definition.pins if not pin.name}
    shown: list[str] = []
    flat = _pins(_renamed(flat, definition.name), name, pad_groups(pin_numbers or ()), empty, shown)
    if literal:
        flat = _untilde(flat, definition)
    authored = definition if not definition.ext.get("kicad") and not pin_numbers and not shown else None
    if shown and issues is not None:
        issues.append(
            Issue(
                SHOWN_CODE,
                "info",
                f"symbol {definition.lib_id}: the hidden power input pin(s) {', '.join(sorted(set(shown)))} "
                "are embedded visible, so each connects by its label and not by its name",
                where=definition.lib_id,
            )
        )
    return _finish(flat, definition.library, name, target, allow_lossy, issues, authored)


def flag_library(libraries: Sequence[str]) -> str:
    """The library that holds the power flag of a design whose symbol libraries are ``libraries``: the
    first of them, in sorted order, whose name differs from ``FLAG_LIBRARY`` in letter case only, else
    ``FLAG_LIBRARY``. Two library files whose names differ only in case cannot lie in one folder on every
    file system, so the flag joins such a library (the built-in catalog's ``Fenolite``; change c0143)."""
    folded = FLAG_LIBRARY.casefold()
    return min((name for name in libraries if name.casefold() == folded), default=FLAG_LIBRARY)


def is_power_flag(lib_id: str) -> bool:
    """Whether ``lib_id`` names Fenolite's power flag: ``PWR_FLAG`` of a library named ``fenolite`` in any
    letter case."""
    library, _, name = lib_id.partition(":")
    return name == FLAG_NAME and library.casefold() == FLAG_LIBRARY.casefold()


def power_flag(target: int, library: str = FLAG_LIBRARY) -> EmbeddedSymbol:
    """``fenolite:PWR_FLAG``: a symbol flagged ``power`` with one power-output pin, authored for Fenolite.
    ``library`` is the library that holds it (``flag_library``)."""
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    item = parse(_FLAG_TEXT)
    if target >= 10:
        item = item.with_children(
            node("power", Atom.symbol("global")) if isinstance(c, Node) and c.name == "power" else c
            for c in item.children
        )
    return _finish(item, library, FLAG_NAME, target, False, None)


def write_symbol_library(symbols: Sequence[EmbeddedSymbol], *, target: int) -> str:
    """The text of a ``.kicad_sym`` file holding ``symbols`` under their bare names, sorted by name.

    A library whose symbols are all authored by the design is the text of ``sym.write_symbol_library``,
    so it has the same bytes whether a schematic is written or not.
    """
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    ordered = sorted(symbols, key=lambda s: s.name)
    if ordered and all(s.authored is not None for s in ordered):
        return write_authored_library([s.authored for s in ordered if s.authored is not None], target=target)
    version = FORMAT_VERSIONS[FileKind.SYMBOL_LIB][target]
    root = node(
        "kicad_symbol_lib",
        node("version", Atom.integer(version)),
        node("generator", Atom.string("fenolite")),
        node("generator_version", Atom.string(f"{target}.0")),
        *(_renamed(s.node, s.name) for s in ordered),
    )
    return dumps(root)


__all__ = [
    "FLAG_LIBRARY",
    "FLAG_NAME",
    "FLAG_REFERENCE",
    "SHOWN_CODE",
    "EmbeddedSymbol",
    "embed_symbol",
    "flag_library",
    "is_power_flag",
    "power_flag",
    "variant_name",
    "write_symbol_library",
]
