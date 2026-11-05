# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Coverage of a design's footprints by a house library that the user names (change c0175, task 10.4;
design, "Additions from the survey", package 10).

The library is read from the path the user gives: a KiCad ``.pretty`` folder, a folder that holds such
folders, an Altium ``.PcbLib`` file, or a folder that holds a mix. Each footprint that the design's board
places is then compared with it, by name and by pads:

- ``same``: a library footprint of the same name has the same pads (by number and place, unturned);
- ``renamed``: no footprint of that name has them, but a footprint of another name does, at any quarter turn;
- ``differs``: a footprint of that name exists, and none has the same pads;
- ``missing``: no footprint has the name or the pads.

Pads are compared by number and place: each place rounded to ``GRID`` (1 µm) and taken from the centroid of
the footprint's pads, so two drawings of one land pattern about different origins agree. Pad shapes and sizes
are not compared. The report holds the library's name (the last part of its path) and footprint names only,
never the path or a footprint's content. It reads files and writes nothing.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fenolite.core.errors import Issue
from fenolite.core.units import round_half_even_div
from fenolite.model.board import Pad
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

GRID = 1_000
"""The grid that pad places are rounded to before comparing, in nm (1 µm)."""

CoverageStatus = Literal["same", "renamed", "differs", "missing"]

_Shape = tuple[tuple[str, int, int], ...]


@dataclass(frozen=True, slots=True)
class CoverageRow:
    """One footprint that the board places: its library reference, how many parts place it, its status and
    the name of the library footprint that covers it (``None`` for ``differs`` and ``missing``)."""

    footprint: str
    parts: int
    status: CoverageStatus
    match: str | None = None


@dataclass(frozen=True, slots=True)
class Coverage:
    """The coverage of a design by a library: the library's name, how many footprints it holds, and a row per
    placed footprint, sorted by library reference."""

    library: str
    footprints: int
    rows: tuple[CoverageRow, ...]

    @property
    def counts(self) -> dict[str, int]:
        """The number of rows of each status, every status named."""
        found = Counter(row.status for row in self.rows)
        return {status: found[status] for status in ("same", "renamed", "differs", "missing")}

    def to_json(self) -> dict[str, object]:
        return {
            "library": self.library,
            "footprints": self.footprints,
            "counts": self.counts,
            "rows": [
                {"footprint": row.footprint, "parts": row.parts, "status": row.status, "match": row.match}
                for row in self.rows
            ],
        }


def _turn(shape: Iterable[tuple[str, int, int]]) -> _Shape:
    """A quarter turn counter-clockwise on screen (Y down)."""
    return tuple(sorted((number, y, -x) for number, x, y in shape))


def pad_shapes(pads: Sequence[Pad]) -> tuple[_Shape, ...]:
    """The pads as ``(number, x, y)`` from their centroid, on ``GRID``, sorted, at the four quarter turns
    (unturned first). The centroid is kept exact by scaling every place by the number of pads."""
    if not pads:
        return ((),) * 4
    count = len(pads)
    cx = sum(pad.position.x for pad in pads)
    cy = sum(pad.position.y for pad in pads)
    grid = GRID * count
    shape = tuple(
        sorted(
            (
                pad.number,
                round_half_even_div(pad.position.x * count - cx, grid),
                round_half_even_div(pad.position.y * count - cy, grid),
            )
            for pad in pads
        )
    )
    shapes = [shape]
    for _ in range(3):
        shapes.append(_turn(shapes[-1]))
    return tuple(shapes)


def _name(lib_ref: str) -> str:
    return lib_ref.rsplit(":", 1)[-1]


def coverage(design: Design, library: Sequence[FootprintDef], *, name: str = "") -> Coverage:
    """The coverage of the footprints that ``design`` places by ``library`` (see the module)."""
    by_name: dict[str, list[FootprintDef]] = {}
    unturned: dict[_Shape, list[str]] = {}
    turned: dict[_Shape, list[str]] = {}
    for footprint in library:
        by_name.setdefault(footprint.name, []).append(footprint)
        shapes = pad_shapes(footprint.pads)
        unturned.setdefault(shapes[0], []).append(footprint.name)
        for shape in set(shapes):
            turned.setdefault(shape, []).append(footprint.name)
    placed: dict[str, list[Sequence[Pad]]] = {}
    for instance in design.board.footprints if design.board is not None else ():
        placed.setdefault(instance.lib_ref, []).append(instance.pads)
    rows: list[CoverageRow] = []
    for lib_ref, pad_sets in sorted(placed.items()):
        own = _name(lib_ref)
        shape = pad_shapes(pad_sets[0])[0]
        if any(pad_shapes(candidate.pads)[0] == shape for candidate in by_name.get(own, ())):
            rows.append(CoverageRow(lib_ref, len(pad_sets), "same", own))
            continue
        others = sorted(set(turned.get(shape, ())) - {own})
        if others:
            rows.append(CoverageRow(lib_ref, len(pad_sets), "renamed", others[0]))
        else:
            rows.append(CoverageRow(lib_ref, len(pad_sets), "differs" if own in by_name else "missing"))
    return Coverage(name, len(library), tuple(rows))


def load_library(path: Path, *, issues: list[Issue] | None = None) -> tuple[FootprintDef, ...]:
    """The footprints of the house library at ``path``: every ``.kicad_mod`` of a ``.pretty`` folder and every
    footprint of a ``.PcbLib`` file, found under ``path`` in sorted order (``path`` may be one of them).
    ``FileNotFoundError`` for a path that does not exist; a file that does not read gives its issues."""
    from fenolite.backends.altium.adapter.library import import_footprints
    from fenolite.backends.altium.read.pcblib import read_pcblib
    from fenolite.backends.kicad.mod import read_footprint

    if not path.exists():
        raise FileNotFoundError(path.name)
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    found: list[FootprintDef] = []
    for file in files:
        suffix = file.suffix.casefold()
        if suffix == ".kicad_mod":
            found.append(read_footprint(file, library=file.parent.stem, file=file.name, issues=issues))
        elif suffix == ".pcblib":
            data = file.read_bytes()
            read = read_pcblib(data, file=file.name)
            found.extend(
                import_footprints(
                    read,
                    name=file.stem,
                    file=file.name,
                    sha256=hashlib.sha256(data).hexdigest(),
                    issues=issues,
                ).footprints
            )
    return tuple(found)


def library_coverage(design: Design, path: Path, *, issues: list[Issue] | None = None) -> Coverage:
    """``coverage`` of ``design`` by the library at ``path`` (``load_library``), named by its last part."""
    return coverage(design, load_library(path, issues=issues), name=path.name)


__all__ = [
    "GRID",
    "Coverage",
    "CoverageRow",
    "CoverageStatus",
    "coverage",
    "library_coverage",
    "load_library",
    "pad_shapes",
]
