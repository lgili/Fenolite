# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed, hash-bound per-sheet native symbol snapshots (c0327).

This is an authoring input, separate from the model and the drawn schematic schema. Native property
nodes are never projected into a dictionary or sorted to decide compatibility.
"""

# evidence: none, Fenolite-owned context-index validation and hashes; native symbol syntax is read by sch

from __future__ import annotations

import hashlib
import json
import posixpath
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from fenolite.backends.kicad import sch, symembed
from fenolite.backends.kicad._fpmap import node
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind, inspect
from fenolite.core.errors import FormatError
from fenolite.core.schema_ids import accepts_schema
from fenolite.model.circuit import Circuit
from fenolite.model.drawn import DrawnSchematic
from fenolite.model.drawn_connect import component_path, instances
from fenolite.model.schematic import SchematicSheet

FILE = "symbol-contexts.toml"
SCHEMA = "fenolite.symbol-contexts.v0"
ASSETS = "lib/.symbol-contexts/"
PROTECTED = frozenset({"Reference", "Value", "Footprint"})
_FIELDS = ("sheet", "native_id", "asset", "asset_sha256", "definition_sha256", "input", "input_sha256")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def definition_sha(symbol: symembed.EmbeddedSymbol) -> str:
    return sha(dumps(symbol.node, style="compact").encode("utf-8"))


def compatible(first: Node, second: Node) -> bool:
    """Every non-property node and protected full property node must be identical."""

    def core(item: Node) -> tuple[object, ...]:
        return tuple(c for c in item.children if not isinstance(c, Node) or c.name != "property")

    def defaults(item: Node) -> tuple[Node, ...]:
        return tuple(p for p in item.nodes("property") if p.atoms() and p.atoms()[0].value in PROTECTED)

    return core(first) == core(second) and defaults(first) == defaults(second)


def compatible_resolved(first: symembed.EmbeddedSymbol, second: symembed.EmbeddedSymbol) -> bool:
    """The library reader projects legacy global power; source ASTs themselves remain exact.

    S-0043/S-0049 (libraries.md) document the two global forms. No local, repeated, unknown or other
    non-property field is excluded. This comparison never changes the asset or written native node.
    """
    if compatible(first.node, second.node):
        return True
    if first.definition.power != "global" or second.definition.power != "global":
        return False
    for value in (first.node, second.node):
        powers = value.nodes("power")
        if len(powers) != 1 or dumps(powers[0], style="compact") not in ("(power)", "(power global)"):
            return False

    def rest(value: Node) -> Node:
        return value.with_children(tuple(c for c in value.children
                                        if not isinstance(c, Node) or c.name != "power"))  # fmt: skip

    return compatible(rest(first.node), rest(second.node))


def _relative(value: str) -> bool:
    return (
        bool(value)
        and not any(c in value for c in "\\:")
        and value.isprintable()
        and all(p not in ("", ".", "..") for p in value.split("/"))
    )


def source_files(drawn: DrawnSchematic, root_file: str) -> dict[str, str]:
    """Existing drawn keys → original relative file spellings, including repeated references."""
    found = {drawn.root: root_file}
    queue = [drawn.root]
    while queue:
        key = queue.pop(0)
        sheet = drawn.sheet(key)
        if sheet is None:
            raise FormatError(f"context drawing has an unknown sheet {key!r}")
        for ref in sheet.sheet_refs:
            if not ref.file:
                raise FormatError(f"context drawing sheet {ref.sheet!r} has no original file binding")
            file = posixpath.normpath(posixpath.join(posixpath.dirname(found[key]), ref.file))
            if not _relative(file):
                raise FormatError(f"context drawing sheet {ref.sheet!r} escapes the source folder")
            if ref.sheet in found:
                if found[ref.sheet] != file:
                    raise FormatError(f"context drawing sheet {ref.sheet!r} has conflicting input files")
            else:
                found[ref.sheet] = file
                queue.append(ref.sheet)
    return found


def _binding(row: Mapping[str, str], drawing: str, target: int, *, schema: str = SCHEMA) -> str:
    value = {"schema": schema, "drawing": drawing, "target": target, **row}
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def write(
    contexts: Mapping[tuple[str, str], symembed.EmbeddedSymbol],
    inputs: Mapping[str, str],
    drawn: DrawnSchematic,
    *,
    root_file: str,
    drawing: str = "schematic.toml",
    target: int,
) -> dict[str, str]:
    """Complete native assets and deterministic closed index; no original input is read here."""
    if not contexts:
        return {}
    by_file = {file: key for key, file in source_files(drawn, root_file).items()}
    rows: list[dict[str, str]] = []
    files: dict[str, str] = {}
    for (file, lib_id), symbol in contexts.items():
        if file not in by_file or file not in inputs:
            raise FormatError(f"context source {file!r} has no sheet/input digest binding")
        text = symembed.write_symbol_library([symbol], target=target)
        digest = sha(text.encode("utf-8"))
        asset = f"{ASSETS}{digest}.kicad_sym"
        files[asset] = text
        rows.append(
            dict(
                zip(
                    _FIELDS,
                    (by_file[file], lib_id, asset, digest, definition_sha(symbol), file, inputs[file]),
                    strict=True,
                )
            )
        )

    def quote(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    lines = [f"schema = {quote(SCHEMA)}", f"drawing = {quote(drawing)}", f"target = {target}"]
    for row in sorted(rows, key=lambda r: (r["sheet"], r["native_id"])):
        lines += [
            "",
            "[[symbol]]",
            *(f"{key} = {quote(row[key])}" for key in _FIELDS),
            f"binding_sha256 = {quote(_binding(row, drawing, target))}",
        ]
    files[FILE] = "\n".join(lines) + "\n"
    return files


@dataclass(frozen=True)
class Contexts:
    """Validated full definitions and all consumed files; no external CAD dependency during build."""

    symbols: Mapping[tuple[str, str], symembed.EmbeddedSymbol] = field(default_factory=lambda: {})
    paths: tuple[Path, ...] = ()
    definition_digests: Mapping[tuple[str, str], str] = field(default_factory=lambda: {})

    def symbol(self, sheet: str, lib_id: str) -> symembed.EmbeddedSymbol:
        key = (sheet, lib_id)
        found = self.symbols.get(key)
        if found is None:
            raise FormatError(f"required context binding is missing for {sheet!r}, {lib_id!r}")
        if definition_sha(found) != self.definition_digests.get(key):
            raise FormatError(f"wrong full native context binding for {sheet!r}, {lib_id!r}")
        return found

    def validate_used(self, used: set[tuple[str, str]]) -> None:
        expected = used
        if expected != set(self.symbols) or set(self.definition_digests) != set(self.symbols):
            missing = sorted(expected - set(self.symbols))
            extra = sorted(set(self.symbols) - expected)
            raise FormatError(
                f"context bindings do not match all used sheet/native IDs: missing={missing}, unknown={extra}"
            )


def from_source(
    contexts: Mapping[tuple[str, str], symembed.EmbeddedSymbol], drawn: DrawnSchematic, *, root_file: str
) -> Contexts | None:
    """Bind already parsed original snapshots to the existing drawing keys, without file I/O."""
    if not contexts:
        return None
    keys = {file: key for key, file in source_files(drawn, root_file).items()}
    if any(file not in keys for file, _ in contexts):
        raise FormatError("source context is absent from the extracted drawing")
    symbols = {(keys[file], lib_id): value for (file, lib_id), value in contexts.items()}
    return Contexts(
        symbols, definition_digests={key: definition_sha(value) for key, value in symbols.items()}
    )


def check_written(sheet: SchematicSheet, text: str, *, target: int) -> None:
    """Prove every complete selected native AST survived the actual schematic serializer."""
    library = parse(text).find("lib_symbols")
    nodes = library.nodes("symbol") if library else ()
    if any(not item.atoms() for item in nodes):
        raise FormatError("written contextual native AST has a nameless definition")
    actual = {item.atoms()[0].value: item for item in nodes}
    if len(actual) != len(nodes) or set(actual) != {definition.lib_id for definition in sheet.lib_symbols}:
        raise FormatError("written contextual native AST has duplicate/missing/unknown definitions")
    for definition in sheet.lib_symbols:
        expected = symembed.embed_symbol(definition, target=target, show_hidden_power=False)
        if actual.get(expected.lib_id) != expected.node:
            raise FormatError(f"written contextual native AST differs for {expected.lib_id!r}")


def check_native(
    contexts: Contexts,
    drawing: DrawnSchematic,
    sheets: Mapping[str, SchematicSheet],
    circuit: Circuit,
    *,
    root_file: str,
    target: int,
) -> None:
    """Sync may copy drawing edits, but must never silently drop changed native cache metadata."""
    from fenolite.backends.kicad.drawn import opaque_symbol

    components = {component_path(c): c for c in circuit.components}
    expected: dict[str, dict[str, symembed.EmbeddedSymbol]] = {}
    rendered: dict[tuple[str, str, tuple[tuple[str, str], ...]], symembed.EmbeddedSymbol] = {}
    used: set[tuple[str, str]] = set()

    def add(sheet: str, lib_id: str, mapping: tuple[tuple[str, str], ...] = ()) -> None:
        full = contexts.symbol(sheet, lib_id)
        key = (sheet, lib_id, mapping)
        if key not in rendered:
            rendered[key] = symembed.embed_symbol(
                full.definition, target=target, pin_numbers=mapping or None, show_hidden_power=False
            )
        made = rendered[key]
        expected.setdefault(sheet, {})[made.lib_id] = made
        used.add((sheet, lib_id))

    found, issues = instances(drawing)
    if any(i.severity == "error" for i in issues):
        raise FormatError("context drawing has an invalid hierarchy")
    for instance in found:
        sheet = drawing.sheet(instance.sheet)
        if sheet is None or sheet.generated:
            continue
        for symbol in sheet.symbols:
            component = components.get(instance.component(symbol.part))
            if component is None:
                raise FormatError("context drawing has an unknown component")
            add(
                sheet.key,
                symbol.symbol or component.lib_symbol_ref,
                symembed.variant_pairs(component.pin_pad_map),
            )
        for power in sheet.powers:
            add(sheet.key, power.symbol)
        for opaque in sheet.opaques:
            native = opaque_symbol(opaque)
            if native is not None:
                add(sheet.key, native.lib_name or native.lib_ref)
    contexts.validate_used(used)
    for key, file in source_files(drawing, root_file).items():
        sheet = sheets.get(file)
        if sheet is None:
            raise FormatError(f"context native sheet {file!r} is missing")
        actual = {
            symbol.lib_id: symembed.embed_symbol(symbol, target=target, show_hidden_power=False)
            for symbol in sheet.lib_symbols
        }
        wanted = expected.get(key, {})
        if (
            len(actual) != len(sheet.lib_symbols)
            or set(actual) != set(wanted)
            or any(actual[lib_id].node != full.node for lib_id, full in wanted.items())
        ):
            raise FormatError(
                "sync cannot drop changed contextual native definitions; "
                "edit and review the source context assets",
                file=file,
            )


def _checked_path(path: Path, folder: Path) -> Path:
    root = folder.absolute()
    wanted = path.absolute()
    try:
        relative = wanted.relative_to(root)
    except ValueError:
        raise FormatError("context path is outside the project folder") from None
    cursor = root
    for part in ("", *relative.parts):
        cursor = cursor / part
        if cursor.is_symlink():
            raise FormatError("context input or ancestor is a symlink", file=relative.as_posix())
    if not wanted.resolve().is_relative_to(root.resolve()):
        raise FormatError("context input escapes the project folder", file=relative.as_posix())
    return wanted


def _read(path: Path, folder: Path) -> bytes:
    checked = _checked_path(path, folder)
    try:
        return checked.read_bytes()
    except OSError as error:
        raise FormatError(
            f"required context input cannot be read: {error.strerror or error}", file=path.name
        ) from None


def check_paths(paths: Sequence[Path]) -> None:
    """Read-only path validation for new authoring inputs/outputs and exact-byte plan replay."""
    for index in (path for path in paths if path.name == FILE):
        folder = index.absolute().parent
        assets = folder / ASSETS
        bound = [path for path in paths if path.absolute().is_relative_to(assets)]
        if not bound:
            continue  # an ordinary drawing may already have the same basename
        _checked_path(index, folder)
        for path in bound:
            _checked_path(path, folder)


def read(path: Path, *, drawing_path: Path, drawn: DrawnSchematic, project_folder: Path) -> Contexts:
    """Read the closed index and every asset before lowering; malformed input is FEN-3004."""
    if path.name != FILE or path.parent.absolute() != drawing_path.parent.absolute():
        raise FormatError(f"context index must be {FILE} beside the drawn schematic")
    try:
        data = tomllib.loads(_read(path, project_folder).decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise FormatError(f"invalid UTF-8 context index: {error}", file=path.name) from error
    if set(data) != {"schema", "drawing", "target", "symbol"} or not accepts_schema(
        data.get("schema"), SCHEMA
    ):
        raise FormatError("context index has missing/unknown keys or an unsupported schema", file=path.name)
    drawing, target, rows = data["drawing"], data["target"], data["symbol"]
    if not isinstance(drawing, str) or drawing != drawing_path.name or not _relative(drawing):
        raise FormatError("context index names a different drawn schematic", file=path.name)
    if type(target) is not int or target not in (9, 10) or not isinstance(rows, list) or not rows:
        raise FormatError("context index target/list has an invalid type or value", file=path.name)
    originals = source_files(drawn, "root.kicad_sch")
    symbols: dict[tuple[str, str], symembed.EmbeddedSymbol] = {}
    digests: dict[tuple[str, str], str] = {}
    paths = {path.absolute()}
    previous: tuple[str, str] | None = None
    groups: dict[str, list[symembed.EmbeddedSymbol]] = {}
    for raw_row in cast(list[object], rows):
        if not isinstance(raw_row, dict):
            raise FormatError("context row has missing/unknown keys or non-string fields", file=path.name)
        untyped = cast(dict[str, object], raw_row)
        if set(untyped) != {*_FIELDS, "binding_sha256"} or any(
            not isinstance(value, str) for value in untyped.values()
        ):
            raise FormatError("context row has missing/unknown keys or non-string fields", file=path.name)
        row = cast(dict[str, str], untyped)
        key = row["sheet"], row["native_id"]
        if previous is not None and key <= previous:
            raise FormatError("context rows must be sorted and unique", file=path.name)
        previous = key
        lib_id = row["native_id"]
        if lib_id.count(":") != 1 or any(not p or not p.isprintable() for p in lib_id.split(":")):
            raise FormatError("context native ID must be an original library:name", file=path.name)
        if key[0] not in originals or not _relative(row["input"]) or not row["input"].endswith(".kicad_sch"):
            raise FormatError("context row names an unknown sheet or invalid original input", file=path.name)
        if (key[0] != drawn.root and row["input"] != originals[key[0]]) or (
            key[0] == drawn.root and "/" in row["input"]
        ):
            raise FormatError("context row has the wrong original sheet input", file=path.name)
        if any(
            not _HASH.fullmatch(row[k])
            for k in ("asset_sha256", "definition_sha256", "input_sha256", "binding_sha256")
        ):
            raise FormatError("context row has an invalid SHA-256 digest", file=path.name)
        if row["asset"] != f"{ASSETS}{row['asset_sha256']}.kicad_sym" or row["binding_sha256"] != _binding(
            {k: row[k] for k in _FIELDS}, drawing, target, schema=data["schema"]
        ):
            raise FormatError("context row has a wrong asset path or stale binding digest", file=path.name)
        asset = path.parent / row["asset"]
        raw = _read(asset, project_folder)
        if sha(raw) != row["asset_sha256"]:
            raise FormatError("context asset digest is stale", file=row["asset"])
        try:
            text = raw.decode("utf-8")
            root = parse(text)
            version = inspect(root, file=row["asset"])
            if version.kind != FileKind.SYMBOL_LIB or version.major != target:
                raise FormatError("context asset format does not match its target", file=row["asset"])
            native = root.nodes("symbol")
            if (
                len(native) != 1
                or not native[0].atoms()
                or native[0].atoms()[0].value != lib_id.partition(":")[2]
            ):
                raise FormatError(
                    "context asset must hold exactly the bound native symbol", file=row["asset"]
                )
            full = native[0].with_children((Atom.string(lib_id), *native[0].children[1:]))
            wrapper = node(
                "kicad_sch",
                node("version", Atom.integer(FORMAT_VERSIONS[FileKind.SCHEMATIC][target])),
                node("lib_symbols", full),
            )
            definitions = sch.read_schematic(wrapper).lib_symbols
        except (UnicodeDecodeError, ValueError) as error:
            raise FormatError(f"invalid context native asset: {error}", file=row["asset"]) from error
        if len(definitions) != 1 or definitions[0].lib_id != lib_id:
            raise FormatError("context asset must hold exactly the bound native symbol", file=row["asset"])
        embedded = symembed.embed_symbol(definitions[0], target=target, show_hidden_power=False)
        if definition_sha(embedded) != row["definition_sha256"]:
            raise FormatError("context full native AST digest is stale", file=row["asset"])
        symbols[key] = embedded
        digests[key] = row["definition_sha256"]
        groups.setdefault(lib_id, []).append(embedded)
        paths.add(asset.absolute())
    for lib_id, values in groups.items():
        if any(not compatible(values[0].node, value.node) for value in values[1:]):
            raise FormatError(f"context group {lib_id!r} is not a compatible full metadata variant")
    return Contexts(symbols, tuple(sorted(paths)), digests)
