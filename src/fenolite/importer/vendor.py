# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The vendored library of an import (change c0275, design decision 8): the board's footprints brought
back to their own frame through the library derive, one ``lib/<nickname>.pretty`` per source nickname,
one generated symbol per footprint in ``lib/<nickname>.kicad_sym``, and the project tables naming them
under ``${KIPRJMOD}/lib``.

A symbol is drawn by Fenolite from the footprint's pad numbers (one passive pin per number, in natural
order, leaving out a number that no instance puts on a net, change c0281), so every pin a script connects
is a pad of the footprint; the source's own symbols are not copied
until the drawn schematic of c0276 needs them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from fenolite.backends.kicad import symembed
from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
from fenolite.backends.kicad.sexpr import Atom, Node
from fenolite.backends.kicad.sym import read_symbol_library, write_symbol_library
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import derived_id
from fenolite.importer.codes import issue
from fenolite.importer.schematic import SourceSymbols
from fenolite.importer.schematic import symbols as source_symbols
from fenolite.importer.source import Source
from fenolite.library import derive_from_model, nickname_of
from fenolite.model.design import Design
from fenolite.model.library import SymbolDef, SymbolGraphic, SymbolPin, SymbolUnit

DEFAULT_NICKNAME = "Imported"
"""The nickname of footprints whose lib id names no library."""
PITCH = 2_540_000
PIN_LENGTH = 2_540_000
BODY = 5_080_000
_PREFIX = re.compile(r"^[A-Za-z_]+")
LIBRARY_PROPERTIES = frozenset({"reference", "value", "footprint", "datasheet", "description"})
"""The properties a library footprint keeps (case-folded); the others belong to the instance."""


def library_footprint(node: Node) -> Node:
    """A footprint node with only the properties of ``LIBRARY_PROPERTIES``: a part's own properties, its
    path and KiCad's sheet fields are the instance's, not the footprint's."""

    def kept(child: Node | Atom) -> bool:
        if not isinstance(child, Node) or child.name != "property":
            return True
        atoms = child.atoms()
        return bool(atoms) and atoms[0].value.casefold() in LIBRARY_PROPERTIES

    return node.with_children(tuple(child for child in node.children if kept(child)))


@dataclass(frozen=True, slots=True)
class Vendored:
    """The library files by path, each physical definition lookup by ref, each symbol lib id by ref,
    the refs whose footprint is written as a variant ``<name>_2`` and the issues."""

    files: Mapping[str, str] = field(default_factory=lambda: {})
    footprints: Mapping[str, str] = field(default_factory=lambda: {})
    symbols: Mapping[str, str] = field(default_factory=lambda: {})
    variants: tuple[str, ...] = ()
    issues: tuple[Issue, ...] = ()
    native_refs: frozenset[str] = frozenset()
    source_symbols: SourceSymbols = field(default_factory=SourceSymbols)


def natural(text: str) -> tuple[tuple[int, int, str], ...]:
    """A sort key that orders ``2`` before ``10`` and keeps any text."""
    return tuple(
        (0, int(part), "") if part.isdigit() else (1, 0, part) for part in re.findall(r"\d+|\D+", text)
    )


def symbol_for(library: str, name: str, numbers: Sequence[str], reference: str) -> SymbolDef:
    """A one-unit symbol with one passive pin per pad number, down the left side of a box."""
    pins = tuple(
        SymbolPin(
            number, number, "passive", Point(-BODY - PIN_LENGTH, -index * PITCH), "line", 0, PIN_LENGTH, 1, 1
        )
        for index, number in enumerate(numbers)
    )
    low = -(len(numbers) - 1) * PITCH - PITCH
    box = SymbolGraphic("rect", (Point(-BODY, PITCH), Point(BODY, low)))
    return SymbolDef(
        id=derived_id("sym", "import", f"{library}:{name}"),
        name=name,
        library=library,
        properties={"Reference": reference, "Value": name, "Footprint": "", "Description": ""},
        pin_names_hidden=True,
        units=(SymbolUnit(1, 1),),
        pins=pins,
        graphics=(box,),
    )


def _row(nickname: str, kind: str) -> LibRow:
    suffix = ".pretty" if kind == "footprint" else ".kicad_sym"
    return LibRow(nickname, "KiCad", f"${{KIPRJMOD}}/lib/{nickname}{suffix}")


def vendor(design: Design, text: str, *, target: int, source: Source | None = None) -> Vendored:
    """The vendored library of the board ``design`` read from the KiCad text ``text``."""
    board = design.board
    if board is None:
        return Vendored()
    refs = {c.id: c.ref for c in design.circuit.components}
    nicknames = sorted({nickname_of(fp.lib_ref, DEFAULT_NICKNAME) for fp in board.footprints})
    files: dict[str, str] = {}
    by_ref: dict[str, str] = {}
    symbols_by_ref: dict[str, str] = {}
    issues: list[Issue] = []
    variants: list[str] = []
    numbers: dict[tuple[str, str], tuple[str, ...]] = {}
    netted: dict[str, set[str]] = {}
    for footprint in board.footprints:
        found = tuple(sorted({pad.number for pad in footprint.pads if pad.number}, key=natural))
        ref = refs.get(footprint.component_id, "")
        numbers.setdefault((nickname_of(footprint.lib_ref, DEFAULT_NICKNAME), ref), found)
        netted.setdefault(ref, set()).update(
            pad.number for pad in footprint.pads if pad.number and pad.net_id
        )
    prefixes: dict[str, str] = {}
    for nickname in nicknames:
        derived = derive_from_model(design, text, library=nickname, target=target, nickname=nickname,
                                    default=DEFAULT_NICKNAME, prepare=library_footprint)  # fmt: skip
        issues += [found for found in derived.issues if found.code != "library.instances-differ"]
        symbols: list[SymbolDef] = []
        for footprint in derived.footprints:
            files[f"lib/{nickname}.pretty/{footprint.name}.kicad_mod"] = footprint.text
            pads = numbers.get((nickname, footprint.refs[0]), ()) if footprint.refs else ()
            # a pad number on no net in every instance gets no pin: the build leaves it on no net, as the
            # source's own symbol did (a shield or thermal pad; change c0281)
            wired: set[str] = set()
            for ref in footprint.refs:
                wired |= netted.get(ref, set())
            pads = tuple(number for number in pads if number in wired)
            if footprint.name != footprint.source:
                variants += footprint.refs
                issues.append(
                    issue(
                        "import.footprint-variant",
                        f"{', '.join(footprint.refs)}: the footprint differs from the first instance of "
                        f"{footprint.source} and is written as {footprint.name}",
                        where=footprint.refs[0] if footprint.refs else footprint.name,
                    )
                )
            for ref in footprint.refs:
                by_ref[ref] = f"{nickname}:{footprint.name}"
                symbols_by_ref[ref] = f"{nickname}:{footprint.name}"
            first = footprint.refs[0] if footprint.refs else ""
            match = _PREFIX.match(first)
            prefixes[footprint.name] = match.group(0) if match else "U"
            symbols.append(symbol_for(nickname, footprint.name, pads, prefixes[footprint.name]))
        if derived.footprints:
            files[f"lib/{nickname}.kicad_sym"] = write_symbol_library(symbols, target=target)
    used = sorted({lib_id.partition(":")[0] for lib_id in by_ref.values()})
    files["fp-lib-table"] = write_lib_table(LibTable("footprint", tuple(_row(n, "footprint") for n in used)),
                                            target=target)  # fmt: skip
    files["sym-lib-table"] = write_lib_table(LibTable("symbol", tuple(_row(n, "symbol") for n in used)),
                                             target=target)  # fmt: skip
    found = Vendored(files, by_ref, symbols_by_ref, tuple(sorted(variants)), tuple(issues))
    return _with_source(found, source, target) if source is not None else found


def _with_source(found: Vendored, source: Source, target: int) -> Vendored:
    native = source_symbols(source, target=target)
    if not native.definitions:
        return found
    fallback: dict[str, SymbolDef] = {}
    files = dict(found.files)
    for file in tuple(files):
        if file.startswith("lib/") and file.endswith(".kicad_sym"):
            nickname = file.removeprefix("lib/").removesuffix(".kicad_sym")
            fallback.update({s.lib_id: s for s in read_symbol_library(files.pop(file), library=nickname)})
    refs = {ref: native.refs.get(ref, lib_id) for ref, lib_id in found.symbols.items()}
    definitions = dict(native.definitions)
    renamed_ids: dict[str, str] = {}
    for ref, old_id in found.symbols.items():
        if ref in native.refs:
            continue
        if old_id not in native.definitions:
            if old_id not in definitions:
                definitions[old_id] = symembed.embed_symbol(fallback[old_id], target=target)
            continue
        if old_id in renamed_ids:
            refs[ref] = renamed_ids[old_id]
            continue
        # A source may own the id the board-only fallback generator would otherwise take.
        base = fallback[old_id]
        number, name = 1, f"{base.name}_imported"
        while f"{base.library}:{name}" in definitions:
            number += 1
            name = f"{base.name}_imported_{number}"
        renamed = replace(base, name=name, ext={})
        embedded = symembed.embed_symbol(renamed, target=target)
        definitions[embedded.lib_id] = embedded
        renamed_ids[old_id] = embedded.lib_id
        refs[ref] = embedded.lib_id
    libraries: dict[str, list[symembed.EmbeddedSymbol]] = {}
    for definition in definitions.values():
        nickname = definition.nickname
        if (
            not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+ -]*", nickname)
            or nickname.endswith((".", " "))
            or nickname.partition(".")[0].casefold()
            in {
                "con",
                "prn",
                "aux",
                "nul",
                *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10)),
            }
        ):
            raise FormatError(f"source symbol library {nickname!r} cannot name a vendored file")
        libraries.setdefault(nickname, []).append(definition)
    for nickname, definitions_of in sorted(libraries.items()):
        files[f"lib/{nickname}.kicad_sym"] = symembed.write_symbol_library(definitions_of, target=target)
    files["sym-lib-table"] = write_lib_table(
        LibTable("symbol", tuple(_row(nickname, "symbol") for nickname in sorted(libraries))), target=target
    )
    return replace(
        found,
        files=files,
        symbols=refs,
        native_refs=frozenset(native.refs),
        source_symbols=native,
        issues=(*found.issues, *native.issues),
    )


__all__ = ["DEFAULT_NICKNAME", "Vendored", "natural", "symbol_for", "vendor"]
