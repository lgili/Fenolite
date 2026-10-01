# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Corpus boards for the board reader tests: the manifest rows and one cached read per session."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from _corpus import CorpusItem, manifest_items

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad import versions
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import AtomKind, Node, load, walk
from fenolite.core.errors import Issue
from fenolite.model.base import Opaque
from fenolite.model.design import Design

BOARD_ITEMS: list[CorpusItem] = [i for i in manifest_items("rt0") if i.path.suffix == ".kicad_pcb"]
MALFORMED_ITEMS: list[CorpusItem] = [i for i in manifest_items("malformed") if i.path.suffix == ".kicad_pcb"]


def readable(item: CorpusItem) -> bool:
    """True when the board's header is at or above the read floor (KiCad 8.0)."""
    return versions.detect_version(load(item.path)) >= versions.READ_FLOOR[versions.FileKind.BOARD]


def is_readable_row(item: CorpusItem) -> bool:
    """Decided from the manifest alone: the demo rows are 8.0+, the third-party rows are older."""
    return item.origin == "kicad-demos"


READABLE_ITEMS = [i for i in BOARD_ITEMS if is_readable_row(i)]
OLD_ITEMS = [i for i in BOARD_ITEMS if not is_readable_row(i)]


@cache
def read(path: Path) -> tuple[Design, tuple[Issue, ...]]:
    """The design read from ``path`` and the reader's issues (read once per test session)."""
    issues: list[Issue] = []
    design = read_board(path, issues=issues)
    return design, tuple(issues)


# --- census (counts only: origins, manifest ids, head chains and codes, never content) -------------

_INDEX = re.compile(r"\[\d+\]")
_DECIMALS = re.compile(r"\.(\d+)")


@dataclass(frozen=True)
class Entry:
    """One board for the census: its origin and id, the parsed tree, the design and the reader issues."""

    origin: str
    id: str
    root: Node
    design: Design
    issues: tuple[Issue, ...]


def entry(item: CorpusItem) -> Entry:
    design, issues = read(item.path)
    return Entry(item.origin, item.id, load(item.path), design, issues)


def context(locator: str) -> str:
    return _INDEX.sub("", locator.removeprefix("/kicad_pcb/")) or "kicad_pcb"


def _per_origin(counts: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {origin: dict(sorted(c.items())) for origin, c in sorted(counts.items())}


def census_numbers(entries: Iterable[Entry]) -> dict[str, Any]:
    """Numbers the reader kept opaque as inexact, and every over-precise atom of the files, by context."""
    reader: dict[str, Counter[str]] = {}
    atoms: dict[str, Counter[str]] = {}
    for e in entries:
        found = reader.setdefault(e.origin, Counter())
        for issue in e.issues:
            if issue.code in ("kicad.board.inexact-length", "kicad.board.inexact-angle"):
                found[f"{issue.code.rsplit('.', 1)[1]}:{context(issue.where)}"] += 1
        precise = atoms.setdefault(e.origin, Counter())
        for locator, node in walk(e.root):
            for atom in node.atoms():
                if atom.kind != AtomKind.NUMBER:
                    continue
                decimals = _DECIMALS.search(atom.text)
                if "e" in atom.text.lower():
                    precise[f"exponent:{context(locator)}"] += 1
                elif decimals is not None and len(decimals.group(1)) > 6:
                    precise[f"over-6-decimals:{context(locator)}"] += 1
    return {"reader_inexact": _per_origin(reader), "over_precise_atoms": _per_origin(atoms)}


def census_kept_opaque(entries: Iterable[Entry]) -> dict[str, Any]:
    reasons: dict[str, Counter[str]] = {}
    for e in entries:
        found = reasons.setdefault(e.origin, Counter())
        for issue in e.issues:
            if issue.code == "kicad.board.kept-opaque":
                message = re.sub(r"'[^']*'", "'…'", issue.message)
                found[f"{context(issue.where)}: {message}"] += 1
    return _per_origin(reasons)


def census_uuids(entries: Iterable[Entry]) -> dict[str, dict[str, int]]:
    """uuid values repeated inside one file, per board and head (``H-K-PCB-UUID``)."""
    repeats: dict[str, dict[str, int]] = {}
    for e in entries:
        values: Counter[str] = Counter()
        heads: dict[str, set[str]] = {}
        for _, node in walk(e.root):
            uuid = node.find("uuid")
            if uuid is not None and uuid.atoms():
                value = uuid.atoms()[0].value
                values[value] += 1
                heads.setdefault(value, set()).add(node.name)
        per_head: Counter[str] = Counter()
        for value, count in values.items():
            if count > 1:
                per_head["+".join(sorted(heads[value]))] += count - 1
        if per_head:
            repeats[e.id] = dict(per_head)
    return repeats


def census_zones(entries: Iterable[Entry]) -> tuple[dict[str, int], list[str]]:
    """Opaque zone outlines per origin (``H-K-PCB-ZONE``), and the zones that break the rule."""
    counts: Counter[str] = Counter()
    problems: list[str] = []
    for e in entries:
        assert e.design.board is not None
        flagged = {
            i.where.rsplit("/polygon", 1)[0] for i in e.issues if i.code == "kicad.board.zone-outline-opaque"
        }
        counts[e.origin] += len(flagged)
        for zone in (*e.design.board.zones, *e.design.board.keepouts):
            if zone.provenance is None or zone.provenance.locator not in flagged:
                continue
            slots = slotlib.from_ext(zone.ext["kicad"])
            polygons = [s for s in slots if isinstance(s, Opaque) and s.fragment.startswith("(polygon ")]
            if zone.outline != () or not polygons:
                problems.append(f"{e.id}: {zone.provenance.locator}")
    return dict(counts), problems


def census_validation(entries: Iterable[Entry]) -> dict[str, dict[str, int]]:
    """``Design.validate()`` findings by code and severity, per origin (counted, not asserted)."""
    found: dict[str, Counter[str]] = {}
    for e in entries:
        counts = found.setdefault(e.origin, Counter())
        counts.update(f"{i.code}:{i.severity}" for i in e.design.validate())
    return _per_origin(found)


def census_headers(entries: Iterable[Entry]) -> dict[str, list[str]]:
    headers: dict[str, list[str]] = {}
    for e in entries:
        parts: list[str] = []
        for head in ("version", "generator", "generator_version"):
            child = e.root.find(head)
            parts.append(child.atoms()[0].value if child is not None and child.atoms() else "-")
        headers.setdefault(" ".join(parts), []).append(e.id)
    return headers


def census_pintypes(entries: Iterable[Entry]) -> dict[str, dict[str, int]]:
    values: dict[str, Counter[str]] = {}
    for e in entries:
        counts = values.setdefault(e.origin, Counter())
        for _, node in walk(e.root):
            if node.name == "pad":
                pintype = node.find("pintype")
                if pintype is not None and pintype.atoms():
                    counts[pintype.atoms()[0].value] += 1
    return _per_origin(values)
