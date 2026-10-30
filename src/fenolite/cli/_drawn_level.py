# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level S for the commands (capability design-equivalence, "Level S compares drawn schematics"; changes
c0276 and c0278): the KiCad sheets of two sides read, extracted (``backends.kicad.drawn.extract_with_pins``)
and compared by ``checks.equivalence.drawn.compare_drawn``.

A drawn symbol names its component by path. The two sides are joined by reference, as levels 1 and 2 join
them: each reference of side ``b`` names the ``fenolite.path`` of its component (a build carries it), and a
reference of side ``a`` names the path of the same reference on side ``b``, else its own path. A repeated
sheet of side ``a`` is therefore one drawn sheet when side ``b``'s paths make it one. Nothing here runs a
tool or writes a file.
"""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.kicad import drawn as kicad_drawn
from fenolite.backends.kicad import sch
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.checks.equivalence import LevelResult, Tolerances
from fenolite.checks.equivalence.drawn import compare_drawn
from fenolite.core.errors import FenoliteError
from fenolite.model.circuit import Circuit
from fenolite.model.drawn_connect import component_path

DRAWN_EVIDENCE = kicad_drawn.EVIDENCE
"""Level S rests on the extraction and the resolver, ``INFERRED`` until the KiCad job measures them."""
UNREADABLE = "drawn-unavailable"
"""The skip reason of level S when the sheets of a side are not read or not extracted."""


def root_schematic(path: Path) -> Path | None:
    """The root schematic of a KiCad project folder, project file or board: the ``.kicad_sch`` of the
    board's name; ``None`` when there is none."""
    try:
        board = resolve_board(path)
    except (FenoliteError, OSError):
        return None
    root = board.with_suffix(".kicad_sch")
    return root if root.is_file() else None


def components_of(circuit_a: Circuit, circuit_b: Circuit) -> tuple[dict[str, str], dict[str, str]]:
    """Reference → component path for side ``a`` and side ``b``, joined by reference (module docstring)."""
    paths_b = {c.ref: component_path(c) for c in circuit_b.components if c.ref}
    paths_a = {c.ref: paths_b.get(c.ref, component_path(c)) for c in circuit_a.components if c.ref}
    return paths_a, paths_b


def _extract(root_file: Path, components: dict[str, str]) -> kicad_drawn.Extracted:
    tree = sch.sheet_files(root_file)
    root = sch.read_schematic(root_file, file=root_file.name)
    folder = root_file.parent
    children = {f: sch.read_schematic(folder / f, file=f) for f in tree.files[1:]}
    return kicad_drawn.extract_with_pins(root, children, components=components, root_file=root_file.name)


def schematic_level(
    root_a: Path, root_b: Path, circuit_a: Circuit, circuit_b: Circuit, *, tolerances: Tolerances
) -> LevelResult | None:
    """Level S of the sheets under ``root_a`` against those under ``root_b``; ``None`` when a side's sheets
    are not read (the level is then skipped with ``UNREADABLE``). The level's summary also counts the
    issues of both extractions (``extraction_issues``): a symbol that names no component is kept as an
    opaque item and compared as one."""
    paths_a, paths_b = components_of(circuit_a, circuit_b)
    try:
        side_a = _extract(root_a, paths_a)
        side_b = _extract(root_b, paths_b)
    except (FenoliteError, OSError, ValueError):
        return None
    level = compare_drawn(
        side_a.drawn, side_b.drawn, tolerances=tolerances, pins_a=side_a.pins, pins_b=side_b.pins
    )
    summary = {**level.summary, "extraction_issues": len(side_a.issues) + len(side_b.issues)}
    return LevelResult(level.level, level.compared, level.differences, level.excluded, summary, level.notices)


__all__ = ["DRAWN_EVIDENCE", "UNREADABLE", "components_of", "root_schematic", "schematic_level"]
