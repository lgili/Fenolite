# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Items of the library repository ``fenolite-library`` (change c0279; ``docs/library-repo.md``): kinds,
ids, the manifest ``item.json`` (schema ``fenolite.library-item.v0``), canonical JSON and the tree digest
``fenolite-tree-1`` of an item.

An item lives in ``<kind folder>/<family>/<id path>/`` of the repository. Its id is a record or block id
``<Namespace>:<name>`` for symbols, footprints, devices and blocks, and ``<source>/<name>`` (lower case) for
boards; the id path replaces ``:`` with ``/``. Everything here is pure: a reader takes bytes and a file name
and raises :class:`ItemError` naming the field.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

ITEM_SCHEMA = "fenolite.library-item.v0"
ITEM_FILE = "item.json"
PROVENANCE_FILE = "PROVENANCE.json"
LICENSE_FILE = "LICENSE"
NOTICE_FILE = "NOTICE"
README_FILE = "README.md"
FIXED_FILES: tuple[str, ...] = (ITEM_FILE, PROVENANCE_FILE, LICENSE_FILE, NOTICE_FILE)
"""The files every item folder holds besides its payload."""
ALWAYS_ALLOWED: frozenset[str] = frozenset({*FIXED_FILES, README_FILE})
KINDS: tuple[str, ...] = ("symbol", "footprint", "device", "block", "board")
"""The kinds, as the command line writes them; the folder of a kind is its plural."""
FOLDERS: Mapping[str, str] = {kind: f"{kind}s" for kind in KINDS}
KIND_OF_FOLDER: Mapping[str, str] = {folder: kind for kind, folder in FOLDERS.items()}
EXECUTING: frozenset[str] = frozenset({"block", "board"})
"""The kinds whose payload is Python that runs when a design imports or builds it."""
RECORD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*:[A-Za-z0-9][A-Za-z0-9_.+-]*")
BOARD_PART = r"[a-z0-9][a-z0-9._-]*"
BOARD_ID = re.compile(rf"{BOARD_PART}/{BOARD_PART}")
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
TREE_SCHEME = "fenolite-tree-1"
TREE = re.compile(rf"{TREE_SCHEME}:[0-9a-f]{{64}}")
SHA256 = re.compile(r"[0-9a-f]{64}")


class ItemError(ValueError):
    """A manifest or provenance record that breaks its schema; the message names the file and the field."""


def id_problem(kind: str, ident: object) -> str | None:
    """Why ``ident`` is not a valid id of ``kind``, or ``None``."""
    if kind not in KINDS:
        return f"unknown kind {kind!r}; the kinds are {', '.join(KINDS)}"
    if not isinstance(ident, str):
        return "the id is a string"
    if kind == "board":
        if not BOARD_ID.fullmatch(ident) or ".." in ident:
            return f"a board id is <source>/<name> in lower case ([a-z0-9][a-z0-9._-]*), not {ident!r}"
        return None
    if not RECORD_ID.fullmatch(ident) or ".." in ident:
        return f"a {kind} id is <Namespace>:<name>, not {ident!r}"
    return None


def id_path(ident: str) -> str:
    """The folder path of an id below its family folder: ``Demo:EXB`` → ``Demo/EXB``."""
    return ident.replace(":", "/")


def item_key(kind: str, ident: str) -> str:
    """The key of an item in the lock and in messages: ``device/Demo:EXB``."""
    return f"{kind}/{ident}"


def version_key(version: str) -> tuple[int, int, int]:
    found = VERSION.fullmatch(version)
    if found is None:
        raise ValueError(f"{version!r} is not a semantic version")
    return (int(found.group(1)), int(found.group(2)), int(found.group(3)))


@dataclass(frozen=True, slots=True)
class Depend:
    """An exact dependency of an item: ``kind``, ``id`` and ``version``."""

    kind: str
    id: str
    version: str

    @property
    def key(self) -> str:
        return item_key(self.kind, self.id)

    def as_json(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.id, "version": self.version}


@dataclass(frozen=True, slots=True)
class Item:
    """The manifest ``item.json`` of one item."""

    kind: str
    id: str
    version: str
    title: str
    summary: str
    spdx: str
    tags: tuple[str, ...]
    files: tuple[str, ...]
    depends: tuple[Depend, ...]
    executes: bool

    @property
    def key(self) -> str:
        return item_key(self.kind, self.id)

    def as_json(self) -> dict[str, object]:
        return {
            "schema": ITEM_SCHEMA,
            "kind": self.kind,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "summary": self.summary,
            "spdx": self.spdx,
            "tags": list(self.tags),
            "files": list(self.files),
            "depends": [depend.as_json() for depend in self.depends],
            "executes": self.executes,
        }


ITEM_KEYS: tuple[str, ...] = (
    "schema",
    "kind",
    "id",
    "version",
    "title",
    "summary",
    "spdx",
    "tags",
    "files",
    "depends",
    "executes",
)


def _fail(file: str, field: str, message: str) -> ItemError:
    return ItemError(f"{file}: {field}: {message}")


def load_json(data: bytes, file: str) -> dict[str, Any]:
    """The JSON object in ``data``; ``ItemError`` for anything else."""
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ItemError(f"{file}: not valid UTF-8 JSON: {exc}") from None
    if not isinstance(value, dict):
        raise ItemError(f"{file}: the document is a JSON object")
    return cast(dict[str, Any], value)


def _text(table: Mapping[str, Any], key: str, file: str, *, empty: bool = False) -> str:
    value = table.get(key)
    if not isinstance(value, str) or (not empty and not value):
        raise _fail(file, key, "a non-empty string" if not empty else "a string")
    return value


def safe_relative(path: str) -> bool:
    """Whether ``path`` is a relative POSIX path that stays inside its folder."""
    if not path or path.startswith("/") or "\\" in path or ":" in path.split("/")[0]:
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))


def read_item(data: bytes, file: str = ITEM_FILE) -> Item:
    """The manifest in ``data``, checked against ``fenolite.library-item.v0``."""
    table = load_json(data, file)
    unknown = sorted(set(table) - set(ITEM_KEYS))
    if unknown:
        raise _fail(file, unknown[0], f"unknown key; the keys are {', '.join(ITEM_KEYS)}")
    if table.get("schema") != ITEM_SCHEMA:
        raise _fail(file, "schema", f"must be {ITEM_SCHEMA!r}")
    kind = _text(table, "kind", file)
    ident = table.get("id")
    problem = id_problem(kind, ident)
    if problem is not None:
        raise _fail(file, "kind" if kind not in KINDS else "id", problem)
    version = _text(table, "version", file)
    if not VERSION.fullmatch(version):
        raise _fail(file, "version", f"a semantic version MAJOR.MINOR.PATCH, not {version!r}")
    title = _text(table, "title", file)
    summary = _text(table, "summary", file, empty=True)
    spdx = _text(table, "spdx", file, empty=True)
    tags = table.get("tags", [])
    if not isinstance(tags, list) or not all(
        isinstance(tag, str) and tag for tag in cast(list[object], tags)
    ):
        raise _fail(file, "tags", "a list of non-empty strings")
    files = table.get("files")
    if not isinstance(files, list) or not all(isinstance(f, str) for f in cast(list[object], files)):
        raise _fail(file, "files", "a list of relative paths")
    listed = cast(list[str], files)
    for name in listed:
        if not safe_relative(name):
            raise _fail(file, "files", f"{name!r} is not a relative path inside the item")
        if name in ALWAYS_ALLOWED:
            raise _fail(file, "files", f"{name} is a fixed file and is not listed")
    if listed != sorted(set(listed)):
        raise _fail(file, "files", "sorted, without repeats")
    raw_depends = table.get("depends", [])
    if not isinstance(raw_depends, list):
        raise _fail(file, "depends", "a list of {kind, id, version}")
    depends: list[Depend] = []
    for index, raw in enumerate(cast(list[object], raw_depends)):
        where = f"depends[{index}]"
        if not isinstance(raw, dict) or set(cast(dict[str, object], raw)) != {"kind", "id", "version"}:
            raise _fail(file, where, "an object of kind, id and version")
        entry = cast(dict[str, object], raw)
        dep_kind, dep_id, dep_version = entry["kind"], entry["id"], entry["version"]
        problem = id_problem(str(dep_kind), dep_id)
        if problem is not None:
            raise _fail(file, where, problem)
        if not isinstance(dep_version, str) or not VERSION.fullmatch(dep_version):
            raise _fail(file, where, "version is an exact semantic version")
        depends.append(Depend(str(dep_kind), str(dep_id), dep_version))
    executes = table.get("executes")
    if not isinstance(executes, bool):
        raise _fail(file, "executes", "true or false")
    return Item(
        kind=kind,
        id=cast(str, ident),
        version=version,
        title=title,
        summary=summary,
        spdx=spdx,
        tags=tuple(cast(list[str], tags)),
        files=tuple(listed),
        depends=tuple(depends),
        executes=executes,
    )


def canonical_json(value: object) -> bytes:
    """``value`` as canonical JSON: keys sorted, two-space indentation, UTF-8, one final newline."""
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


# -- the tree digest fenolite-tree-1 (the scheme of fenolite.backends.kicad.libcache.tree_hash)


def tree_digest(files: Mapping[str, bytes] | Iterable[tuple[str, int, str]]) -> str:
    """``fenolite-tree-1:<hex>`` of a set of files: one line ``<sha256 hex> <size> <path>\\n`` per file,
    sorted by the UTF-8 bytes of the path. ``files`` maps relative POSIX paths to bytes, or yields
    ``(path, size, sha256)`` rows."""
    rows: list[tuple[str, int, str]]
    if isinstance(files, Mapping):
        content = cast(Mapping[str, bytes], files)
        rows = [(path, len(data), hashlib.sha256(data).hexdigest()) for path, data in content.items()]
    else:
        rows = list(files)
    total = hashlib.sha256()
    for path, size, digest in sorted(rows, key=lambda row: row[0].encode("utf-8")):
        total.update(f"{digest} {size} ".encode("ascii") + path.encode("utf-8") + b"\n")
    return f"{TREE_SCHEME}:{total.hexdigest()}"


def folder_files(folder: Path, *, exclude: Iterable[str] = ()) -> dict[str, bytes]:
    """Every regular file below ``folder`` (relative POSIX path → bytes), without the paths of
    ``exclude`` and the files below a folder of ``exclude`` (written ``name/``). A symlink or a special
    file raises ``ItemError``."""
    skipped = set(exclude)
    found: dict[str, bytes] = {}
    pending = [folder]
    while pending:
        current = pending.pop()
        for entry in os.scandir(current):
            path = Path(entry.path)
            relative = path.relative_to(folder).as_posix()
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode):
                raise ItemError(f"{relative}: an item holds no symbolic link")
            if stat.S_ISDIR(mode):
                if relative + "/" not in skipped:
                    pending.append(path)
            elif stat.S_ISREG(mode):
                if relative not in skipped:
                    found[relative] = path.read_bytes()
            else:
                raise ItemError(f"{relative}: neither a regular file nor a folder")
    return dict(sorted(found.items()))


def item_folder(kind: str, ident: str) -> str:
    """Where a vendored item lives below the script folder: ``fenolite_library/devices/Demo/EXB``."""
    return f"{VENDOR_FOLDER}/{FOLDERS[kind]}/{id_path(ident)}"


VENDOR_FOLDER = "fenolite_library"
"""The folder beside the design script that holds vendored items (a valid Python identifier)."""


__all__ = [
    "ALWAYS_ALLOWED",
    "BOARD_ID",
    "EXECUTING",
    "FIXED_FILES",
    "FOLDERS",
    "ITEM_FILE",
    "ITEM_SCHEMA",
    "KINDS",
    "KIND_OF_FOLDER",
    "LICENSE_FILE",
    "NOTICE_FILE",
    "PROVENANCE_FILE",
    "README_FILE",
    "RECORD_ID",
    "SHA256",
    "TREE",
    "TREE_SCHEME",
    "VENDOR_FOLDER",
    "VERSION",
    "Depend",
    "Item",
    "ItemError",
    "canonical_json",
    "folder_files",
    "id_path",
    "id_problem",
    "item_folder",
    "item_key",
    "load_json",
    "read_item",
    "safe_relative",
    "tree_digest",
    "version_key",
]
