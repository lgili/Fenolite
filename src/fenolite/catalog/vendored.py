# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Data-only project item resolution (c0266, docs/library-devices.md).

The library downloader owns release validation. This reader independently pairs plain records with
the local item identity, without a catalog → library dependency or a cache/network lookup.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from fenolite.catalog.records import LibraryTree, PartEntry, Record, kind_of, load_tree, parse_header
from fenolite.core.errors import FormatError, Issue

KINDS = {"symbols": "pins", "footprints": "package", "devices": "device"}
ITEM_KINDS = {"pins": "symbol", "package": "footprint", "device": "device"}


@dataclass(frozen=True, slots=True)
class ItemRef:
    kind: str
    id: str
    version: str
    spdx: str
    folder: str

    @property
    def catalog(self) -> str:
        return f"library:{self.kind}/{self.id}@{self.version}"

    def as_json(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.id, "version": self.version}


@dataclass(frozen=True)
class VendoredTree:
    tree: LibraryTree = LibraryTree()
    items: Mapping[tuple[str, str], ItemRef] = field(default_factory=lambda: {})
    files: tuple[Path, ...] = ()
    issues: tuple[Issue, ...] = ()
    families: tuple[tuple[Path, ItemRef], ...] = ()


def load_vendored(script_dir: Path) -> VendoredTree:
    """Read the three item kinds below this project's fenolite_library, never executable code.

    Bad item/record identities fail as bad input; duplicates remain findings naming both folders, so
    a build can report library.item-conflict and plan no writes.
    """
    root = script_dir / "fenolite_library"
    records: list[Record] = []
    owners: dict[tuple[str, str], str] = {}
    items: dict[tuple[str, str], ItemRef] = {}
    files: list[Path] = []
    parts: dict[str, tuple[PartEntry, ...]] = {}
    issues: list[Issue] = []
    families: list[tuple[Path, ItemRef]] = []
    for plural, record_kind in KINDS.items():
        top = root / plural
        if not top.is_dir():
            continue
        for marker in sorted(top.rglob("item.json")):
            folder = marker.parent
            label = folder.relative_to(script_dir).as_posix()
            payload = tuple(sorted(folder.rglob("*")))
            if any(p.is_symlink() or not p.resolve().is_relative_to(root.resolve()) for p in payload):
                raise FormatError(f"{label}: symlink or path outside vendored library", file=label)
            try:
                raw = json.loads(marker.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("item.json must be an object")
                data = cast(dict[str, object], raw)
                for key in ("id", "kind", "version", "spdx"):
                    if not isinstance(data.get(key), str) or not data[key]:
                        raise ValueError(f"item.json needs {key}")
                ref = ItemRef(
                    str(data["kind"]), str(data["id"]), str(data["version"]), str(data["spdx"]), label
                )
                if (
                    ref.kind != ITEM_KINDS[record_kind]
                    or ref.id.startswith("Fenolite:")
                    or ".." in ref.id
                    or any(part in {".", ".."} for part in ref.id.split(":"))
                ):
                    raise ValueError("item kind mismatch or reserved Fenolite namespace")
                tree = load_tree(folder, label=f"{label}/")
                family_files: list[tuple[Path, dict[str, object]]] = []
                for path in folder.glob("*.toml"):
                    raw_record = cast(dict[str, object], tomllib.loads(path.read_text(encoding="utf-8")))
                    if raw_record.get("schema") in {"fenolite.family.v0", "fenolite.family.v1"}:
                        family_files.append((path, raw_record))
                if len(tree.records) + len(family_files) != 1:
                    raise ValueError("an item must hold exactly one record")
                header = (
                    parse_header(family_files[0][1], "device", file=label)
                    if family_files
                    else tree.records[0].header
                )
                actual_kind = "device" if family_files else kind_of(tree.records[0])
                if (actual_kind, header.id, header.version, header.licence) != (
                    record_kind,
                    ref.id,
                    ref.version,
                    ref.spdx,
                ):
                    raise ValueError("record kind/id/version/licence must equal its item")
            except (ValueError, OSError, UnicodeError) as exc:
                raise FormatError(f"{label}: {exc}", file=label) from None
            key = (record_kind, ref.id)
            if key in items:
                issues.append(
                    Issue(
                        "library.item-conflict",
                        "error",
                        f"{ref.id} occurs in both {items[key].folder} and {label}",
                        where=ref.id,
                    )
                )
                continue
            if family_files:
                families.append((family_files[0][0], ref))
                owners[key] = f"{label}/{family_files[0][0].name}"
            else:
                records.extend(tree.records)
            owners.update(tree.files)
            parts.update(tree.parts)
            items[key] = ref
            files.extend(p for p in payload if p.is_file())
    return VendoredTree(
        LibraryTree(tuple(records), owners, parts), items, tuple(files), tuple(issues), tuple(families)
    )


def overlay(authored: LibraryTree, vendored: VendoredTree) -> tuple[LibraryTree, tuple[Issue, ...]]:
    """Authored records win per kind/id, with one explicit finding for each overridden item."""
    keys = {(kind_of(record), record.header.id) for record in authored.records}
    inherited = tuple(
        record for record in vendored.tree.records if (kind_of(record), record.header.id) not in keys
    )
    issues = tuple(
        Issue(
            "library.overrides-item",
            "info",
            f"authored {kind}/{record_id} overrides {vendored.items[(kind, record_id)].catalog}",
            where=record_id,
        )
        for kind, record_id in sorted(keys & set(vendored.items))
    )
    files = {key: value for key, value in vendored.tree.files.items() if key not in keys}
    files.update(authored.files)
    parts = dict(vendored.tree.parts)
    for record in authored.records:
        if kind_of(record) == "device":
            parts[record.header.id] = authored.parts.get(record.header.id, ())
    return LibraryTree((*inherited, *authored.records), files, parts), (*vendored.issues, *issues)
