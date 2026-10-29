# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""List every model dataclass, field and extension-bag key for the pre-freeze review (change c0218).

    uv run python tools/model_review.py               # the list as Markdown on stdout
    uv run python tools/model_review.py --json        # the same items as JSON
    uv run python tools/model_review.py --out FILE    # write the list to FILE instead

Each item has a stable id (``Track.width``, ``ext.kicad.number``) so that the maintainer can answer keep,
rename or drop item by item (task 1.2 of c0218). The list holds:

- every dataclass defined in a module of ``fenolite.model``, and every dataclass of another package that a
  layer file or a definition file stores (``fenolite.model.schema``), with the files that store it;
- each field with its key on the wire, its type, its default (``required`` without one) and the modules
  other than its own that read an attribute of that name or spell the name as a string. A reader is found
  by name, so the modules are an upper bound, loosest for a name that several model dataclasses share
  (``shared`` > 1); a field that no module names is read only through ``dataclasses.fields``;
- every extension-bag key of each backend: the closed table ``EXT_KEYS`` of the Altium adapter with the
  entities of ``docs/formats/altium/import.md``, "Extension-bag keys"; for KiCad, which has no closed table,
  the keys that the readers put in the bags of the committed KiCad files under ``tests/data`` and
  ``examples`` and the keys that the sources write or read as literals, with the modules of each.

Nothing is decided here: the tool lists, the maintainer decides.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import enum
import importlib
import json
import pkgutil
import re
import sys
import types
import typing
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PACKAGE = SRC / "fenolite"
ALTIUM_TABLE = ROOT / "docs" / "formats" / "altium" / "import.md"
SHOWN_READERS = 6
"""Readers named per item in the Markdown form; the JSON form names every one."""

_KEY = re.compile(r"^[a-z][a-z0-9_]*(?:[.:][a-z0-9_]+)*$")
_KICAD_SUFFIXES = (".kicad_pcb", ".kicad_sch", ".kicad_wks", ".kicad_dru", ".kicad_mod", ".kicad_sym")
SLOT_ITEM = "slot:<locator>:<kind>"
ALTIUM_IMPORT = "fenolite.backends.altium.adapter"
"""The modules that build the Altium bags; another module that names a key of the table reads it."""


# --- dataclasses -------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class FieldItem:
    id: str
    key: str
    type: str
    default: str
    shared: int
    readers: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class ClassItem:
    id: str
    module: str
    stored_in: tuple[str, ...]
    fields: tuple[FieldItem, ...]


@dataclasses.dataclass(frozen=True)
class ExtItem:
    id: str
    backend: str
    key: str
    on: tuple[str, ...]
    source: tuple[str, ...]
    writers: tuple[str, ...]
    readers: tuple[str, ...]


def _model_modules() -> list[types.ModuleType]:
    import fenolite.model as model

    names = sorted(info.name for info in pkgutil.iter_modules(model.__path__))
    return [model, *(importlib.import_module(f"fenolite.model.{name}") for name in names)]


def _load(ref: str) -> type:
    module, _, attr = ref.partition(":")
    found: type = getattr(importlib.import_module(module), attr)
    return found


def _roots() -> dict[str, type]:
    from fenolite.model.schema import (
        LAYER_SCHEMAS,
        LIBRARY_SCHEMA,
        PANEL_SCHEMA,
        SCHEMATIC_SCHEMA,
        SHEET_SCHEMA,
    )

    roots = {name: _load(ref) for name, (_, ref) in LAYER_SCHEMAS.items()}
    for name, _, ref in (LIBRARY_SCHEMA, SHEET_SCHEMA, SCHEMATIC_SCHEMA, PANEL_SCHEMA):
        roots[name] = _load(ref)
    return roots


def _dataclasses_in(tp: Any) -> Iterator[type]:
    """The dataclasses an annotation names, at any depth."""
    if isinstance(tp, type) and dataclasses.is_dataclass(tp):
        yield tp
        return
    for arg in typing.get_args(tp):
        yield from _dataclasses_in(arg)


def _stored(roots: dict[str, type]) -> dict[type, set[str]]:
    """Each dataclass a layer or definition file stores, with the files that store it."""
    stored: dict[type, set[str]] = defaultdict(set)
    for name, root in roots.items():
        todo = [root]
        while todo:
            cls = todo.pop()
            if name in stored[cls]:
                continue
            stored[cls].add(name)
            hints = typing.get_type_hints(cls)
            for f in dataclasses.fields(cls):
                todo.extend(_dataclasses_in(hints[f.name]))
    return stored


def _type_text(tp: Any) -> str:
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if tp is type(None):
        return "None"
    if tp is Any:
        return "Any"
    if origin is typing.Literal:
        return "Literal[" + ", ".join(repr(a) for a in args) + "]"
    if origin in (typing.Union, types.UnionType):
        return " | ".join(_type_text(a) for a in args)
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return f"tuple[{_type_text(args[0])}, ...]"
        return "tuple[" + ", ".join(_type_text(a) for a in args) + "]"
    if origin in (list, dict, set, frozenset):
        return f"{origin.__name__}[" + ", ".join(_type_text(a) for a in args) + "]"
    if isinstance(tp, type):
        return tp.__name__
    return str(tp).replace("typing.", "")


def _default_text(f: dataclasses.Field[Any]) -> str:
    if f.default is not dataclasses.MISSING:
        value = f.default
    elif f.default_factory is not dataclasses.MISSING:
        value = f.default_factory()
    else:
        return "required"
    if isinstance(value, enum.Enum):
        return f"{type(value).__name__}.{value.name}"
    return repr(value)


def _module_name(path: Path) -> str:
    parts = path.relative_to(SRC).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _sources() -> dict[str, ast.Module]:
    return {
        _module_name(path): ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in sorted(PACKAGE.rglob("*.py"))
    }


def _attributes_read(tree: ast.Module) -> set[str]:
    """The attribute names a module reads: ``x.name``, and every string literal, which covers
    ``getattr(x, "name")`` and tables of field names."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    return names


def classes(sources: dict[str, ast.Module]) -> list[ClassItem]:
    """Every dataclass of ``fenolite.model`` and every stored dataclass, in module and source order."""
    stored = _stored(_roots())
    found: dict[type, None] = {}
    for module in _model_modules():
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and dataclasses.is_dataclass(value)
                and value.__module__ == module.__name__
            ):
                found[value] = None
    found.update(dict.fromkeys(stored))
    reads = {name: _attributes_read(tree) for name, tree in sources.items()}
    names: dict[str, int] = defaultdict(int)
    for cls in found:
        for f in dataclasses.fields(cls):
            names[f.name] += 1

    def order(cls: type) -> tuple[str, int]:
        source = sources.get(cls.__module__)
        line = next(
            (
                n.lineno
                for n in (source.body if source else ())
                if isinstance(n, ast.ClassDef) and n.name == cls.__name__
            ),
            0,
        )
        return cls.__module__, line

    items: list[ClassItem] = []
    for cls in sorted(found, key=order):
        hints = typing.get_type_hints(cls)
        fields = tuple(
            FieldItem(
                id=f"{cls.__name__}.{f.name}",
                key=str(f.metadata.get("name", f.name)),
                type=_type_text(hints[f.name]),
                default=_default_text(f),
                shared=names[f.name],
                readers=tuple(m for m in sorted(reads) if f.name in reads[m] and m != cls.__module__),
            )
            for f in dataclasses.fields(cls)
        )
        items.append(ClassItem(cls.__name__, cls.__module__, tuple(sorted(stored.get(cls, ()))), fields))
    return items


# --- extension-bag keys --------------------------------------------------------------------------------


def _altium_table() -> dict[str, str]:
    """``key -> on`` of the table "Extension-bag keys" of the Altium import page."""
    rows: dict[str, str] = {}
    inside = False
    for line in ALTIUM_TABLE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Extension-bag keys"
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if inside and len(cells) >= 2 and cells[0].startswith("`"):
            rows[cells[0].strip("`")] = cells[1]
    return rows


def _touches_bags(tree: ast.Module) -> bool:
    """A module that builds or reads extension bags."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in ("ExtBag", "EXT_KEYS"):
            return True
        if isinstance(node, ast.Attribute) and node.attr in ("ext", "payload", "ExtBag"):
            return True
    return False


def _string_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "text"`` constants, and the key of each ``NAME_PAIR = ("key", "value")``."""
    constants: dict[str, str] = {}
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if not isinstance(target, ast.Name):
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            constants[target.id] = value.value
        elif target.id.endswith("_PAIR") and isinstance(value, ast.Tuple) and value.elts:
            first = value.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                constants[target.id] = first.value
    return constants


def _text(node: ast.expr, constants: dict[str, str]) -> str | None:
    """A string literal, or a module constant named by ``NAME`` or ``module.NAME``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.Attribute):
        return constants.get(node.attr)
    return None


def _named(node: ast.AST, *words: str) -> bool:
    if isinstance(node, ast.Name):
        return any(w in node.id.lower() for w in words)
    if isinstance(node, ast.Attribute):
        return any(w in node.attr.lower() for w in words)
    return False


def _bag_source(node: ast.AST) -> bool:
    """``x.payload``, ``dict(x.payload)``, ``_ext_pairs(x)`` and the like: a mapping of bag pairs."""
    if isinstance(node, ast.Attribute) and node.attr == "payload":
        return True
    if isinstance(node, ast.Name) and "pairs" in node.id.lower():
        return True
    if isinstance(node, ast.Call):
        if _named(node.func, "ext_pairs", "pairs"):
            return True
        if isinstance(node.func, ast.Name) and node.func.id == "dict" and node.args:
            return _bag_source(node.args[0])
    return False


def _pair_keys(node: ast.AST, constants: dict[str, str]) -> Iterator[str]:
    """The keys of the ``(key, value)`` literals in ``node``."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Tuple) and len(sub.elts) == 2:
            key = _text(sub.elts[0], constants)
            if key is not None:
                yield key


def _bag_keys(tree: ast.Module, constants: dict[str, str]) -> tuple[set[str], set[str]]:
    """The keys a module writes into bags and the keys it reads from them."""
    written: set[str] = set()
    read: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _named(node.func, "extbag"):
            for arg in [*node.args, *(k.value for k in node.keywords)]:
                written.update(_pair_keys(arg, constants))
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(_named(t, "pairs", "payload") for t in targets) and node.value is not None:
                written.update(_pair_keys(node.value, constants))
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Tuple):
                if any(isinstance(t, ast.Name) and t.id.endswith("_PAIR") for t in targets):
                    key = _text(node.value.elts[0], constants) if node.value.elts else None
                    if key is not None:
                        written.add(key)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("append", "extend")
            and _named(node.func.value, "pairs", "payload")
        ):
            for arg in node.args:
                written.update(_pair_keys(arg, constants))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if _bag_source(node.func.value) and node.args:
                key = _text(node.args[0], constants)
                if key is not None:
                    read.add(key)
        elif (
            isinstance(node, ast.Compare)
            and all(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops)
            and any(_bag_source(c) for c in node.comparators)
        ):
            key = _text(node.left, constants)
            if key is not None:
                read.add(key)
        elif isinstance(node, ast.Subscript) and _bag_source(node.value):
            key = _text(node.slice, constants)
            if key is not None:
                read.add(key)
        elif isinstance(node, ast.For) and _bag_source(node.iter):
            names = {n.id for n in ast.walk(node.target) if isinstance(n, ast.Name)}
            for stmt in node.body:
                for cmp in ast.walk(stmt):
                    if (
                        isinstance(cmp, ast.Compare)
                        and isinstance(cmp.left, ast.Name)
                        and cmp.left.id in names
                    ):
                        if all(isinstance(op, (ast.Eq, ast.NotEq)) for op in cmp.ops):
                            for right in cmp.comparators:
                                key = _text(right, constants)
                                if key is not None:
                                    read.add(key)
    pattern = {k for k in written | read if _KEY.match(k)}
    return written & pattern, read & pattern


def _generator_reads(tree: ast.Module, constants: dict[str, str]) -> set[str]:
    """Keys compared with the key of a pair in a generator over a bag (``k == "x" for k, v in b.payload``)."""
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
            for gen in node.generators:
                if not _bag_source(gen.iter):
                    continue
                names = {n.id for n in ast.walk(gen.target) if isinstance(n, ast.Name)}
                for cmp in ast.walk(node):
                    if (
                        isinstance(cmp, ast.Compare)
                        and isinstance(cmp.left, ast.Name)
                        and cmp.left.id in names
                    ):
                        for right in cmp.comparators:
                            key = _text(right, constants)
                            if key is not None and _KEY.match(key):
                                keys.add(key)
    return keys


def _census() -> dict[tuple[str, str], set[str]]:
    """``(backend, key) -> entity classes`` over the committed KiCad files the readers accept."""
    from fenolite.backends.kicad import dru, mod, pcb, sch, sym, wks
    from fenolite.model.base import ExtBag

    def rules(path: Path) -> object:
        return dru.read_rules(path.read_text(encoding="utf-8"), file=str(path))

    readers: dict[str, Callable[[Path], object]] = {
        ".kicad_pcb": pcb.read_board,
        ".kicad_sch": sch.read_schematic,
        ".kicad_wks": wks.read_drawing_sheet,
        ".kicad_dru": rules,
        ".kicad_mod": mod.read_footprint,
        ".kicad_sym": sym.read_symbol_library,
    }
    found: dict[tuple[str, str], set[str]] = defaultdict(set)

    def walk(value: object) -> None:
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            ext: object = getattr(value, "ext", None)
            if isinstance(ext, dict):
                for backend, bag in typing.cast("dict[str, ExtBag]", ext).items():
                    for key, _ in bag.payload:
                        name = SLOT_ITEM if key.startswith("slot:") else key
                        found[(backend, name)].add(type(value).__name__)
            for f in dataclasses.fields(value):
                walk(getattr(value, f.name))
        elif isinstance(value, (tuple, list)):
            for item in typing.cast("Iterable[object]", value):
                walk(item)
        elif isinstance(value, dict):
            for item in typing.cast("dict[object, object]", value).values():
                walk(item)

    paths = [
        p
        for top in ("tests/data", "examples")
        for p in sorted((ROOT / top).rglob("*"))
        if p.suffix in _KICAD_SUFFIXES and p.is_file()
    ]
    for path in paths:
        try:
            walk(readers[path.suffix](path))
        except Exception:  # noqa: BLE001 - a malformed test file is skipped: it makes no bag
            continue
    return found


def _literals(tree: ast.Module) -> set[str]:
    """The string literals of a module, but those of the table ``EXT_KEYS`` itself."""
    skipped: set[int] = set()
    for node in tree.body:
        target = node.target if isinstance(node, ast.AnnAssign) else None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "EXT_KEYS":
            skipped.update(id(n) for n in ast.walk(node))
    return {
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skipped
    }


def _altium_only(name: str, tree: ast.Module) -> bool:
    """A module outside the KiCad backend that names the ``altium`` bag and never the ``kicad`` one."""
    if name.startswith("fenolite.backends.kicad"):
        return False
    named = {
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and n.value in ("altium", "kicad")
    }
    return named == {"altium"}


def ext_keys(sources: dict[str, ast.Module]) -> list[ExtItem]:
    from fenolite.backends.altium.adapter.ids import EXT_KEYS

    constants: dict[str, str] = {}
    for tree in sources.values():
        constants.update(_string_constants(tree))
    bag_modules = {name: tree for name, tree in sources.items() if _touches_bags(tree)}
    items: list[ExtItem] = []

    table = _altium_table()
    literals = {
        name: _literals(tree)
        for name, tree in sources.items()
        if "altium" in name or name.startswith("fenolite.convert")
    }
    for key in EXT_KEYS:
        users = [m for m in sorted(literals) if key in literals[m]]
        writers = tuple(m for m in users if m.startswith(ALTIUM_IMPORT))
        readers = tuple(m for m in users if not m.startswith(ALTIUM_IMPORT))
        on = (table[key],) if key in table else ()
        items.append(ExtItem(f"ext.altium.{key}", "altium", key, on, ("EXT_KEYS",), writers, readers))

    census = _census()
    written: dict[str, set[str]] = defaultdict(set)
    read: dict[str, set[str]] = defaultdict(set)
    for name, tree in bag_modules.items():
        if name.startswith("fenolite.backends.altium") or _altium_only(name, tree):
            continue
        w, r = _bag_keys(tree, constants)
        r |= _generator_reads(tree, constants)
        for key in w:
            written[key].add(name)
        for key in r:
            read[key].add(name)
    slot_users = sorted(
        m for m, tree in bag_modules.items() if "slotlib" in ast.unparse(tree) or m.endswith("slots")
    )
    written[SLOT_ITEM].update(m for m in slot_users if m.startswith("fenolite.backends.kicad"))
    read[SLOT_ITEM].update(slot_users)
    keys = {key for backend, key in census if backend == "kicad"} | set(written) | set(read)
    for key in sorted(keys):
        source = tuple(
            s
            for s, hit in (("census", ("kicad", key) in census), ("source", key in written or key in read))
            if hit
        )
        items.append(
            ExtItem(
                f"ext.kicad.{key}",
                "kicad",
                key,
                tuple(sorted(census.get(("kicad", key), ()))),
                source,
                tuple(sorted(written.get(key, ()))),
                tuple(sorted(read.get(key, ()))),
            )
        )
    for backend, key in sorted(census):
        if backend not in ("kicad", "altium"):
            items.append(
                ExtItem(
                    f"ext.{backend}.{key}",
                    backend,
                    key,
                    tuple(sorted(census[(backend, key)])),
                    ("census",),
                    (),
                    (),
                )
            )
    return items


# --- output --------------------------------------------------------------------------------------------


def _short(module: str) -> str:
    return module.removeprefix("fenolite.")


def _names(modules: tuple[str, ...]) -> str:
    if not modules:
        return "—"
    shown = ", ".join(_short(m) for m in modules[:SHOWN_READERS])
    return shown if len(modules) <= SHOWN_READERS else f"{shown} (+{len(modules) - SHOWN_READERS})"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def markdown(found: list[ClassItem], bags: list[ExtItem], version: str) -> str:
    fields = sum(len(c.fields) for c in found)
    lines = [
        "# Model review (c0218)",
        "",
        f"`SCHEMA_VERSION` {version!r}: {len(found)} dataclasses, {fields} fields, "
        f"{len(bags)} extension-bag keys.",
        "Answer per item id: keep, rename (to what) or drop. Readers are the modules that name the field",
        "(an attribute or a string): an upper bound, loosest when `shared`, the number of model dataclasses",
        "with a field of that name, is above 1.",
        "",
        "## Dataclasses",
    ]
    for cls in found:
        stored = ", ".join(f"`{s}`" for s in cls.stored_in) or "not stored"
        lines += [
            "",
            f"### {cls.id}",
            "",
            f"`{cls.module}`; stored in {stored}.",
            "",
            "| item | type | default | shared | readers |",
            "|---|---|---|---|---|",
        ]
        for f in cls.fields:
            key = f.id if f.key == f.id.split(".", 1)[1] else f"{f.id} (key `{f.key}`)"
            cells = (
                f"`{key}`",
                f"`{_cell(f.type)}`",
                f"`{_cell(f.default)}`",
                str(f.shared),
                _names(f.readers),
            )
            lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## Extension-bag keys"]
    for backend in sorted({b.backend for b in bags}):
        lines += [
            "",
            f"### {backend}",
            "",
            "| item | on | found by | written by | read by |",
            "|---|---|---|---|---|",
        ]
        for b in (b for b in bags if b.backend == backend):
            on = ", ".join(b.on) or "—"
            cells = (f"`{b.id}`", _cell(on), ", ".join(b.source), _names(b.writers), _names(b.readers))
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--json", action="store_true", help="the items as JSON")
    parser.add_argument("--out", type=Path, help="write the list to this file instead of stdout")
    args = parser.parse_args(argv)
    from fenolite.model.design import SCHEMA_VERSION

    sources = _sources()
    found = classes(sources)
    bags = ext_keys(sources)
    if args.json:
        text = (
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "classes": [dataclasses.asdict(c) for c in found],
                    "ext_keys": [dataclasses.asdict(b) for b in bags],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
    else:
        text = markdown(found, bags, SCHEMA_VERSION)
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
