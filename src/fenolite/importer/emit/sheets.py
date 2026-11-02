# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Source-sheet factories and common-ancestor net placement (c0275, decision 5).

This module only consumes parsed records. A source file, rather than apparent similarity of parts,
identifies a repeated sheet. Its physical instance differences stay explicit in the emitted function.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from fenolite.importer.emit.printer import Call, Dct, Raw, Sub, identifier, statement, string, text
from fenolite.importer.source import Source
from fenolite.model.schematic import SchematicSheet

Scope = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Instance:
    """A source file at one named path, with its symbol identities and boundary pin names."""

    path: Scope
    file: str
    refs: Mapping[str, str]
    pins: tuple[str, ...] = ()


def _stem(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "sheet"


def _symbols(sheet: SchematicSheet, at: str, project: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for symbol in sheet.symbols:
        if not symbol.on_board:
            continue
        uses = [use for use in symbol.uses if use.path == at]
        use = next((u for u in uses if u.project == project), uses[0] if uses else None)
        ref = use.ref if use is not None else symbol.ref
        if ref and not ref.startswith("#"):
            refs[symbol.id] = ref
    return refs


def instances(source: Source, *, include_root: bool = False) -> tuple[Instance, ...]:
    """The source hierarchy in sheet order, including the root; empty for a one-file source."""
    hierarchy = source.hierarchy
    if not hierarchy or (len(hierarchy) <= 1 and not include_root):
        return ()
    root_file = next(iter(hierarchy))
    root = hierarchy[root_file]
    found: list[Instance] = []

    def walk(file: str, path: Scope, at: str, pins: tuple[str, ...], trail: tuple[str, ...]) -> None:
        sheet = hierarchy[file]
        found.append(Instance(path, file, _symbols(sheet, at, source.name), pins))
        taken: set[str] = set()
        for child in sheet.sheets:
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(file), child.file.replace("\\", "/"))
            )
            uuid = child.native_ids.get("kicad")
            if target not in hierarchy or target in trail or not uuid:
                continue
            name = _stem(child.name)
            seed, index = name, 2
            while name in taken:
                name, index = f"{seed}_{index}", index + 1
            taken.add(name)
            walk(target, (*path, name), f"{at}/{uuid}", tuple(p.name for p in child.pins), (*trail, target))

    walk(root_file, (), "/" + root.native_ids.get("kicad", ""), (), (root_file,))
    return tuple(found) if len(found) > 1 or include_root else ()


def _common(paths: Sequence[Scope]) -> Scope:
    if not paths:
        return ()
    prefix = paths[0]
    for path in paths[1:]:
        length = 0
        while length < min(len(prefix), len(path)) and prefix[length] == path[length]:
            length += 1
        prefix = prefix[:length]
    return prefix


class Hierarchy:
    """The import's real sheet instances, canonical part keys and net scopes."""

    def __init__(self, source: Source) -> None:
        self.instances: dict[Scope, Instance] = {}
        for instance in instances(source):
            native = {
                ref: source.sheet_origins[ref]
                for ref in instance.refs.values()
                if ref in source.sheet_origins
            }
            if native and len({file for file, _ in native.values()}) == 1:
                instance = replace(
                    instance,
                    file=next(iter(native.values()))[0],
                    refs={element: ref for ref, (_, element) in native.items()},
                )
            self.instances[instance.path] = instance
        self.paths: dict[str, Scope] = {}
        self.files: dict[str, str] = {}
        first: dict[str, Mapping[str, str]] = {}
        taken: set[str] = {"__init__"}
        for instance in self.instances.values():
            sheet = source.hierarchy.get(instance.file)
            authored = (
                {
                    symbol.id: symbol.properties.get("fenolite.path", "").rsplit("/", 1)[-1]
                    for symbol in sheet.symbols
                }
                if sheet is not None
                else {}
            )
            authored = {
                symbol: key for symbol, key in authored.items() if re.fullmatch(r"[A-Za-z0-9_.+-]+", key)
            }
            keys = first.setdefault(
                instance.file, {symbol: authored.get(symbol) or ref for symbol, ref in instance.refs.items()}
            )
            for symbol, ref in instance.refs.items():
                self.paths[ref] = (*instance.path, keys.get(symbol, ref))
            if instance.path and instance.file not in self.files:
                self.files[instance.file] = identifier(
                    PurePosixPath(instance.file).stem, taken, prefix="sheet"
                )

    def owners(
        self, members: Mapping[str, Mapping[tuple[str, str], None]], paths: Mapping[str, Scope]
    ) -> dict[str, Scope]:
        """The deepest sheet containing all pins of each net, with unknown scopes kept at the root."""
        return {
            net: _common([paths[ref][:-1] for ref, _ in pins if ref in paths])
            for net, pins in members.items()
        }

    def incoming(self, scope: Scope, net: str) -> str:
        """A deterministic boundary keyword, preferring the matching source sheet pin."""
        instance = self.instances[scope]
        pin = next((p for p in instance.pins if p == net), None)
        pin = pin or next((p for p in instance.pins if p == net.rsplit("/", 1)[-1]), net)
        return identifier(pin, set(), prefix="net")

    def emit(
        self,
        *,
        paths: Mapping[str, Scope],
        part_vars: Mapping[str, str],
        parts: Mapping[str, Call],
        places: Mapping[str, Call],
        members: Mapping[str, Mapping[tuple[str, str], None]],
        net_vars: Mapping[str, str],
        header: Sequence[str],
    ) -> tuple[dict[str, str], list[list[str]], list[list[str]]]:
        """Factory files, root factory calls, and aliases of locally constructed nets for board items."""
        owners = self.owners(members, paths)
        needed: dict[Scope, set[str]] = {scope: set() for scope in self.instances}
        held: dict[Scope, list[str]] = {scope: [] for scope in self.instances}
        for ref, path in paths.items():
            if ref in part_vars:
                held.setdefault(path[:-1], []).append(ref)
        for net, pins in members.items():
            if net not in net_vars:
                continue
            for ref, _ in pins:
                if ref in paths:
                    scope = paths[ref][:-1]
                    for depth in range(len(owners[net]), len(scope) + 1):
                        needed.setdefault(scope[:depth], set()).add(net)
        # Keywords may collide after sanitization; allocate all boundary names in a stable order.
        keywords: dict[tuple[Scope, str], str] = {}
        for scope in self.instances:
            taken: set[str] = {"design", "path", "refs"}
            for net in sorted(needed[scope]):
                if owners.get(net, ()) != scope:
                    keywords[scope, net] = identifier(self.incoming(scope, net), taken, prefix="net")

        def child_call(scope: Scope, parent: str) -> Call:
            instance = self.instances[scope]
            mapping = tuple((paths[ref][-1], text(ref)) for ref in sorted(held[scope]))
            arguments = [("path", text("/".join(scope))), ("refs", Dct(mapping))]
            arguments += [
                (keywords[scope, net], Raw(net_vars[net]))
                for net in sorted(needed[scope])
                if owners.get(net, ()) != scope
            ]
            return Call(f"_sheet_{self.files[instance.file]}.sheet", (Raw(parent),), tuple(arguments))

        def body(scope: Scope, depth: int) -> list[str]:
            rows: list[str] = []
            for net in sorted(needed[scope]):
                value = (
                    Call("Net", (text(net),))
                    if owners.get(net, ()) == scope
                    else Sub("nets", text(keywords[scope, net]))
                )
                rows += statement(value, depth, target=net_vars[net])
            for ref in sorted(held[scope], key=lambda r: paths[r]):
                key = paths[ref][-1]
                part = parts[ref]
                kwargs = tuple((k, v) for k, v in part.kwargs if k != "name") + (("name", text(key)),)
                call = replace(
                    part, args=(Raw(f"refs.get({string(key)}, {string(ref)})"), *part.args[1:]), kwargs=kwargs
                )
                rows += statement(call, depth, target=part_vars[ref])
            if held[scope]:
                rows += statement(Call("module.add", tuple(Raw(part_vars[r]) for r in held[scope])), depth)
            for net, pins in sorted(members.items()):
                local = [
                    Sub(part_vars[r], text(p))
                    for r, p in sorted(pins)
                    if r in part_vars and paths[r][:-1] == scope
                ]
                if local and net in net_vars:
                    rows += statement(Call("connect", (Raw(net_vars[net]), *local)), depth)
            for ref in sorted(held[scope], key=lambda r: paths[r]):
                rows += statement(places[ref], depth)
            for child in sorted(self.instances):
                if child and child[:-1] == scope:
                    rows += statement(child_call(child, "module"), depth)
            return rows

        files: dict[str, str] = {"sheets/__init__.py": "\n".join((*header, ""))}
        for file, name in self.files.items():
            scopes = [scope for scope, instance in self.instances.items() if scope and instance.file == file]
            children = {
                self.files[instance.file]
                for scope, instance in self.instances.items()
                if scope and scope[:-1] in scopes
            }
            lines = [
                "def sheet(design, *, path, refs=None, **nets):",
                '    module = Module(path.rsplit("/", 1)[-1])',
                "    design.add(module)",
                "    refs = refs or {}",
            ]
            for index, scope in enumerate(scopes):
                if len(scopes) > 1:
                    lines.append(f"    {'if' if index == 0 else 'elif'} path == {string('/'.join(scope))}:")
                rows = body(scope, 2 if len(scopes) > 1 else 1)
                lines += rows or (["        pass"] if len(scopes) > 1 else [])
            if len(scopes) > 1:
                lines += ["    else:", '        raise ValueError(f"unknown source sheet instance: {path}")']
            lines.append("    return module")
            imports = ["Module"] + [
                name for name in ("Net", "Part", "connect", "mm") if any(f"{name}(" in line for line in lines)
            ]
            lines = [
                *header,
                "",
                f"from fenolite.dsl import {', '.join(imports)}",
                *[f"from sheets import {child} as _sheet_{child}" for child in sorted(children)],
                "",
                "",
                *lines,
            ]
            files[f"sheets/{name}.py"] = "\n".join(lines) + "\n"
        calls = [
            statement(child_call(scope, "design")) for scope in sorted(self.instances) if len(scope) == 1
        ]
        aliases = [
            statement(Sub("design.nets", text(net)), target=var)
            for net, var in sorted(net_vars.items())
            if owners.get(net, ())
        ]
        return files, calls, aliases


__all__ = ["Hierarchy", "Instance", "instances"]
