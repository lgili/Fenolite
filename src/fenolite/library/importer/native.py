# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Canonical imported definitions at a project build boundary (c0264).

Catalog records remain backend-independent; the CLI calls this adapter to retain the source's KiCad
slots, properties, units and model transforms. References are basenames beside each normalized record.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path

from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends
from fenolite.catalog.records import (
    DeviceRecord,
    ImportOrigin,
    LibraryTree,
    PackageRecord,
    PinsRecord,
    footprint_def,
    kind_of,
)
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import derived_id
from fenolite.library.importer.records import record_edited, with_model_path
from fenolite.model.library import FootprintDef, SymbolDef


@dataclass(frozen=True)
class Native:
    footprints: dict[str, FootprintDef] = field(default_factory=lambda: {})
    symbols: dict[str, SymbolDef] = field(default_factory=lambda: {})
    models: dict[str, dict[str, bytes]] = field(default_factory=lambda: {})
    files: tuple[Path, ...] = ()
    issues: tuple[Issue, ...] = ()


def read_native_definitions(tree: LibraryTree, folder: Path) -> Native:
    """Read imported native sources and model bytes; all returned input paths are inside the project."""
    footprints: dict[str, FootprintDef] = {}
    symbols: dict[str, SymbolDef] = {}
    models: dict[str, dict[str, bytes]] = {}
    files: set[Path] = set()
    issues: list[Issue] = []
    for record in tree.records:
        origin = record.header.origin
        if not isinstance(origin, ImportOrigin):
            continue
        marker = folder / tree.files[(kind_of(record), record.header.id)]
        root = marker.parent
        if isinstance(record, DeviceRecord):
            edited = record_edited(record)
            for output in origin.output:
                source = root / output.file
                if not source.resolve().is_relative_to(folder.resolve()):
                    raise FormatError("imported file resolves outside the project", file=output.file)
                if not source.is_file():
                    raise FormatError("imported file is missing", file=output.file)
                files.add(source)
                edited = edited or hashlib.sha256(source.read_bytes()).hexdigest() != output.sha256
            if edited:
                issues.append(
                    Issue(
                        "device.edited",
                        "info",
                        f"{record.header.id} changed after its import",
                        where=record.header.id,
                    )
                )
            continue
        name = (
            record.symbol_file
            if isinstance(record, PinsRecord)
            else record.footprint
            if isinstance(record, PackageRecord)
            else ""
        )
        if not name:
            continue
        source = root / name
        if not source.resolve().is_relative_to(folder.resolve()):
            raise FormatError("imported definition resolves outside the project", file=name)
        files.add(source)
        text = source.read_text(encoding="utf-8")
        if isinstance(record, PinsRecord):
            found = resolve_extends(read_symbol_library(text, library=record.header.namespace, file=name))
            selected = next((s for s in found if s.name == record.header.name), None)
            if selected is None:
                raise FormatError("imported symbol does not contain the record's name", file=name)
            symbols[record.header.id] = replace(
                selected,
                id=derived_id("sym", "fenolite.catalog", record.header.id),
                native_ids={"fenolite": record.header.id},
            )
        else:
            selected_fp = read_footprint(text, library=record.header.namespace, file=name)
            if selected_fp.name != record.header.name:
                raise FormatError("imported footprint does not contain the record's name", file=name)
            selected_fp = replace(
                selected_fp,
                id=derived_id("fpd", "fenolite.catalog", record.header.id),
                native_ids={"fenolite": record.header.id},
                pads=tuple(
                    replace(p, id=derived_id("pad", "fenolite.catalog", f"{record.header.name}:pad-{index}"))
                    for index, p in enumerate(selected_fp.pads)
                ),
                graphics=tuple(
                    replace(
                        g, id=derived_id("gfx", "fenolite.catalog", f"{record.header.name}:graphic-{index}")
                    )
                    for index, g in enumerate(selected_fp.graphics)
                ),
                bodies=footprint_def(record).bodies if isinstance(record, PackageRecord) else (),
            )
            step = root / f"{record.header.name}.step"
            if step.is_file() and (selected_fp.models or selected_fp.placements):
                if not step.resolve().is_relative_to(folder.resolve()):
                    raise FormatError("imported STEP resolves outside the project", file=step.name)
                relative = f"lib/{record.header.namespace}.3dshapes/{record.header.name}.step"
                selected_fp, _ = with_model_path(selected_fp, "${KIPRJMOD}/" + relative)
                models[record.header.id] = {relative: step.read_bytes()}
                files.add(step)
            footprints[record.header.id] = selected_fp
    return Native(footprints, symbols, models, tuple(sorted(files)), tuple(issues))


__all__ = ["Native", "read_native_definitions"]
