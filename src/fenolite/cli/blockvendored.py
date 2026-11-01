# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Static discovery and build checks for script-local vendored block records (c0273)."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path

from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl.blockitem import FILE, BlockItem, read_item
from fenolite.dsl.design import Design
from fenolite.dsl.record import BlockRecord
from fenolite.library.items import ItemError
from fenolite.library.items import read_item as read_manifest

ISSUE_CODES: dict[str, Severity] = {
    "blocks.index-stale": "warning",
    "blocks.item-broken": "warning",
    "blocks.namespace-reserved": "error",
    "blocks.upgrade-major": "error",
}
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-BLOCK-PACKAGES",))


@dataclass(frozen=True, slots=True)
class VendoredBlock:
    item: BlockItem
    module: str
    root: Path
    where: str

    @property
    def id(self) -> str:
        return self.item.id

    @property
    def version(self) -> str:
        return self.item.version

    @property
    def namespace(self) -> str:
        return self.item.namespace

    @property
    def record(self) -> BlockRecord:
        return self.item.record

    @property
    def digest(self) -> str:
        return self.item.digest


def find_vendored(script_dir: Path, *, issues: list[Issue] | None = None) -> tuple[VendoredBlock, ...]:
    """Read package records in POSIX path order, without importing any code or namespace package."""
    report = issues if issues is not None else []
    parent = script_dir / "fenolite_library" / "blocks"
    found: list[VendoredBlock] = []
    for root in sorted(parent.glob("*/*"), key=lambda p: p.as_posix()):
        if not root.is_dir():
            continue
        shown = root.relative_to(script_dir).as_posix()
        try:
            if root.is_symlink() or root.parent.is_symlink() or not (root / "__init__.py").is_file():
                raise FormatError("a vendored block is a regular package folder with __init__.py")
            manifest = read_manifest((root / "item.json").read_bytes())
            if manifest.kind != "block" or not manifest.executes:
                raise FormatError("a block item has kind block and executes true")
            item = read_item(
                (root / FILE).read_text(encoding="utf-8"), item_id=manifest.id, item_version=manifest.version
            )
            if item.id != f"{root.parent.name}:{root.name}":
                raise FormatError("the block id must equal its namespace and package folder names")
        except (FormatError, ItemError, OSError, UnicodeDecodeError) as error:
            report.append(
                Issue(
                    "blocks.item-broken",
                    "warning",
                    f"{shown}: {error}",
                    where=shown,
                    hint="restore the item or regenerate block.json with fenolite blocks index",
                )
            )
            continue
        if item.namespace == "Fenolite":
            report.append(
                Issue(
                    "blocks.namespace-reserved",
                    "error",
                    f"{shown}: Fenolite is reserved for the core starter library",
                    where=shown,
                )
            )
            continue
        module = f"fenolite_library.blocks.{item.namespace}.{root.name}"
        found.append(VendoredBlock(item, module, root, shown))
    return tuple(found)


def input_files(script_dir: Path) -> tuple[Path, ...]:
    """Vendored code and records that bind a build or upgrade's reviewed plan."""
    root = script_dir / "fenolite_library/blocks"
    return tuple(
        sorted(
            path
            for path in root.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and (path.suffix == ".py" or path.name in ("block.json", "item.json"))
        )
    )


def check_used(
    design: Design, script_dir: Path, *, records: dict[int, BlockRecord] | None = None
) -> tuple[Issue, ...]:
    """Compare each actually used vendored definition with its stored record, once per definition."""
    from fenolite.dsl._sites import recording
    from fenolite.dsl.block import blocks
    from fenolite.dsl.record import describe, digests

    issues: list[Issue] = []
    items = find_vendored(script_dir, issues=issues)
    seen: set[int] = set()
    versions: dict[str, set[str]] = {}
    for instance in blocks(design):
        definition = instance.definition
        header = definition.header
        if header is None:
            continue
        versions.setdefault(header.id, set()).add(header.version)
        if id(definition) in seen:
            continue
        seen.add(id(definition))
        source = inspect.getsourcefile(definition.function)
        path = None if source is None else Path(source).resolve()
        item = next(
            (item for item in items if path is not None and path.is_relative_to(item.root.resolve())), None
        )
        if item is None and records is None:
            continue
        with recording(script_dir):  # metadata elaboration does not add sites to the caller's design
            current = describe(definition)
        if records is not None:
            records[id(definition)] = current
        if item is not None and digests(current)["record"] != item.digest:
            issues.append(
                Issue(
                    "blocks.index-stale",
                    "warning",
                    f"{item.where}: used block {header.id} differs from block.json; the build uses its code",
                    where=item.where,
                    hint="review the local edit and run fenolite blocks index to update its record",
                )
            )
    for ident, used in sorted(versions.items()):
        if len(used) > 1:
            issues.append(
                Issue(
                    "blocks.duplicate-id",
                    "error",
                    f"{ident} is used at multiple versions: {', '.join(sorted(used))}",
                    where=ident,
                )
            )
    return tuple(issues)
