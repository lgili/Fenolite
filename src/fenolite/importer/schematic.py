# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Source drawings and embedded symbols of a KiCad project import (c0276).

Only the already parsed source is consumed. Native symbol slots remain native; the authored symbol
serializer is deliberately not used for source drawings. No source file is changed here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from fenolite.backends.kicad import drawn, sch, symembed
from fenolite.backends.kicad.sexpr import dumps
from fenolite.backends.kicad.sym import resolve_extends
from fenolite.backends.kicad.symbol_contexts import compatible
from fenolite.core.errors import FormatError, Issue
from fenolite.importer.source import Source
from fenolite.model._drawn_text import write_drawn
from fenolite.model.drawn import FIELD_ROTATIONS, ROTATIONS, DrawnSchematic
from fenolite.model.library import SymbolDef


@dataclass(frozen=True, slots=True)
class SourceSymbols:
    """Slot-preserving definitions by library id and each reference's lowest-unit primary binding."""

    definitions: Mapping[str, symembed.EmbeddedSymbol] = field(default_factory=lambda: {})
    refs: Mapping[str, str] = field(default_factory=lambda: {})
    issues: tuple[Issue, ...] = ()
    contexts: Mapping[tuple[str, str], symembed.EmbeddedSymbol] = field(default_factory=lambda: {})


def symbols(source: Source, *, target: int) -> SourceSymbols:
    """Embedded source definitions, refusing ambiguity instead of replacing a native drawing."""
    if source.backend != "kicad" or not source.hierarchy:
        return SourceSymbols()
    from fenolite.importer.emit.sheets import instances

    definitions: dict[str, symembed.EmbeddedSymbol] = {}
    signatures: dict[str, str] = {}
    references: dict[str, str] = {}
    by_symbol: dict[tuple[str, str], tuple[str, int]] = {}
    issues: list[Issue] = []
    local: dict[tuple[str, str], symembed.EmbeddedSymbol] = {}
    variants: set[str] = set()
    inherited: set[str] = set()
    for file, sheet in source.hierarchy.items():
        available = {definition.lib_id: definition for definition in sheet.lib_symbols}
        if len(available) != len(sheet.lib_symbols):
            raise FormatError("source sheet has duplicate embedded definitions", file=file)
        by_name = {definition.name: definition for definition in sheet.lib_symbols}
        embedded_cache: dict[tuple[str, str], symembed.EmbeddedSymbol] = {}
        for instance in sheet.symbols:
            lib_id = instance.lib_name or instance.lib_ref
            definition = available.get(lib_id)
            if definition is None:
                raise FormatError(f"source symbol {lib_id!r} has no embedded definition", file=file)
            if instance.rotation not in ROTATIONS or instance.body_style != 1:
                raise FormatError(
                    f"source symbol {instance.ref or lib_id}: rotation/body style cannot be represented "
                    "by schematic.toml",
                    file=file,
                )
            if any(pose.rotation not in FIELD_ROTATIONS for pose in sch.symbol_field_poses(instance)):
                raise FormatError(f"source symbol {instance.ref}: unsupported field rotation", file=file)
            canonical_id = drawn.source_symbol_id(definition, instance)
            cache_key = (lib_id, canonical_id)
            if cache_key in embedded_cache:
                by_symbol[(file, instance.id)] = (embedded_cache[cache_key].lib_id, instance.unit)
                continue
            parents: list[SymbolDef] = []
            cursor = definition
            seen = {cursor.name}
            while cursor.extends:
                parent = by_name.get(cursor.extends)
                if parent is None or parent.name in seen:
                    raise FormatError(f"source symbol {lib_id!r}: missing or cyclic base", file=file)
                parents.append(parent)
                seen.add(parent.name)
                cursor = parent
            if parents:
                inherited.add(canonical_id)
            resolved = resolve_extends((definition, *parents))[0] if parents else definition
            embedded = symembed.embed_symbol(
                replace(resolved, library=canonical_id.partition(":")[0]),
                parents=parents,
                target=target,
                issues=issues,
                show_hidden_power=False,
            )
            signature = dumps(embedded.node, style="compact")
            context_key = (file, embedded.lib_id)
            if context_key in local and local[context_key].node != embedded.node:
                raise FormatError(
                    f"source sheet embeds conflicting definitions of {embedded.lib_id!r}", file=file
                )
            local[context_key] = embedded
            if embedded.lib_id in signatures and signatures[embedded.lib_id] != signature:
                if not compatible(definitions[embedded.lib_id].node, embedded.node):
                    raise FormatError(
                        f"source sheets embed conflicting definitions of {embedded.lib_id!r}", file=file
                    )
                variants.add(embedded.lib_id)
            signatures.setdefault(embedded.lib_id, signature)
            definitions.setdefault(embedded.lib_id, embedded)
            embedded_cache[cache_key] = embedded
            by_symbol[(file, instance.id)] = (embedded.lib_id, instance.unit)
    if variants & inherited:
        raise FormatError(
            "conflicting definitions with contextual inheritance cannot preserve all native properties"
        )
    units_by_ref: dict[str, dict[int, str]] = {}
    files_by_ref: dict[str, str] = {}
    for instance in instances(source, include_root=True):
        for symbol, ref in instance.refs.items():
            lib_id, unit = by_symbol[(instance.file, symbol)]
            units = units_by_ref.setdefault(ref, {})
            other = units.setdefault(unit, lib_id)
            if other != lib_id:
                raise FormatError(
                    f"source reference {ref!r} unit {unit} has conflicting symbols", file=instance.file
                )
            files_by_ref.setdefault(ref, instance.file)
    for ref, units in units_by_ref.items():
        primary = units[min(units)]
        for unit, lib_id in units.items():
            if drawn.unit_signature(definitions[primary].definition, unit) != drawn.unit_signature(
                definitions[lib_id].definition, unit
            ):
                raise FormatError(
                    f"source reference {ref!r} unit {unit} has incompatible logical pins",
                    file=files_by_ref[ref],
                )
        references[ref] = primary
    contexts = local if variants else {}
    return SourceSymbols(definitions, references, tuple(issues), contexts)


def drawing(
    source: Source, refs: Mapping[str, str], footprints: Mapping[str, str] = MappingProxyType({})
) -> tuple[str | None, tuple[Issue, ...]]:
    """Canonical source drawing using the emitter's final reference-to-component-path map."""
    value, issues = drawing_value(source, refs, footprints)
    return (write_drawn(value) if value is not None else None), issues


def drawing_value(
    source: Source, refs: Mapping[str, str], footprints: Mapping[str, str] = MappingProxyType({})
) -> tuple[DrawnSchematic | None, tuple[Issue, ...]]:
    """The extracted drawing before serialization, including its unchanged existing sheet keys.

    ``footprints`` maps a reference to the footprint its emitted part builds with (c0414)."""
    if source.backend != "kicad" or not source.hierarchy:
        return None, ()
    root_file = next(iter(source.hierarchy))
    root = source.hierarchy[root_file]
    children = {name: sheet for name, sheet in source.hierarchy.items() if name != root_file}
    value, issues = drawn.extract(root, children, components=refs, root_file=root_file, footprints=footprints)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        raise FormatError("source drawing cannot be imported: " + errors[0].message, file=root_file)
    return value, issues


__all__ = ["SourceSymbols", "drawing", "drawing_value", "symbols"]
