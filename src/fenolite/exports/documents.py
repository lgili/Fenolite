# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What Fenolite checks before ``kicad-cli`` writes a document (capability manufacturing-exports,
"Schematic PDF export sheets" and "Board PDF export page check"; change c0116).

``sch export pdf`` plots an empty page for a sheet whose file is missing and exits 0 with no message,
and ``pcb export pdf`` plots on the board's paper whatever the extent of the board. Neither tells the
reader of the file, so the first is refused before any run and the second is a warning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.projectset import project_set
from fenolite.backends.kicad.sch import sheet_files
from fenolite.core.errors import FormatError, Issue
from fenolite.exports.codes import issue
from fenolite.model.design import Design
from fenolite.model.presentation import PAPER_SIZES, SheetFrameRef

SHEET_CODES = ("kicad.sch.sheet-missing", "kicad.sch.sheet-outside", "kicad.sch.sheet-cycle")
"""The issues of the hierarchy walk that name a sheet the run cannot be given."""
_NAMED = re.compile(r" names (.+?), (?:a file on|outside|which does)")
_MM = 1_000_000


@dataclass(frozen=True, slots=True)
class SchematicFiles:
    """The schematic of a board for a ``sch-pdf`` run: the root file's name, the sheet files of the copy
    set (the root first), and one ``export.sheet-missing`` per sheet the run cannot be given."""

    root: str
    files: tuple[str, ...] = ()
    issues: tuple[Issue, ...] = ()


def _refusal(name: str, why: str) -> Issue:
    return issue(
        "export.sheet-missing",
        f"the schematic PDF is not written: sheet file {name} {why}",
        where=name,
        hint="restore the sheet file inside the project folder, or drop --sch-pdf",
    )


def schematic_files(board: Path) -> SchematicFiles:
    """The root schematic ``<stem>.kicad_sch`` beside ``board``, the sheet files that the copy set of
    ``project_set(board)`` holds for it, and the sheets it cannot give. No second copy set is planned:
    the names are read from that set and from the walk of ``sch.sheet_files``."""
    board = Path(board)
    root = f"{board.stem}.kicad_sch"
    source = board.parent / root
    if not source.is_file():
        return SchematicFiles(root, issues=(_refusal(root, "does not exist"),))
    project = project_set(board)
    try:
        tree = sheet_files(source)
    except (FormatError, OSError, UnicodeDecodeError, ValueError):
        return SchematicFiles(root, (root,))  # KiCad judges a root that Fenolite cannot read
    refused: dict[str, str] = {}
    for found in tree.issues:
        if found.code not in SHEET_CODES:
            continue
        match = _NAMED.search(found.message)
        name = match.group(1) if match is not None else found.where
        why = {
            "kicad.sch.sheet-missing": "does not exist",
            "kicad.sch.sheet-outside": "lies outside the project folder",
            "kicad.sch.sheet-cycle": "is on its own path from the root",
        }[found.code]
        refused.setdefault(name, why)
    sheets = set(tree.files)
    for skipped in project.skipped:
        if skipped.reason == "too-large" and skipped.name in sheets:
            refused.setdefault(skipped.name, "is too large for the copy of the project")
    files = tuple(name for name in tree.files if name in project.files)
    return SchematicFiles(root, files, tuple(_refusal(name, why) for name, why in refused.items()))


def _mm(value: int) -> str:
    whole, rest = divmod(value, _MM)
    return str(whole) if rest == 0 else f"{value / _MM:.2f}".rstrip("0").rstrip(".")


def page_size(design: Design) -> tuple[int, int] | None:
    """Width and height of the board's page in nanometres: the named paper, landscape unless portrait,
    or the custom size. ``None`` for a design without a board or a custom paper without a size."""
    board = design.board
    if board is None:
        return None
    sheet = board.sheet or SheetFrameRef()  # a board without a page setting is on KiCad's A4
    if sheet.paper == "custom":
        if sheet.width is None or sheet.height is None:
            return None
        return (sheet.width, sheet.height)
    short, long = PAPER_SIZES[sheet.paper]
    return (short, long) if sheet.portrait else (long, short)


def page_check(design: Design) -> Issue | None:
    """``export.page-too-small`` when the bounding box of the board outline is not inside the page that
    runs from (0, 0) to the size of the board's paper; ``None`` when it is, or when the board has no
    closed outline."""
    size = page_size(design)
    if size is None or design.board is None:
        return None
    rings = board_outline(design).rings
    if not rings:
        return None
    xs = [point.x for point in rings[0]]
    ys = [point.y for point in rings[0]]
    width, height = size
    if min(xs) >= 0 and min(ys) >= 0 and max(xs) <= width and max(ys) <= height:
        return None
    sheet = design.board.sheet or SheetFrameRef()
    paper = sheet.paper + (" portrait" if sheet.portrait and sheet.paper != "custom" else "")
    return issue(
        "export.page-too-small",
        f"the board outline of {_mm(max(xs) - min(xs))} × {_mm(max(ys) - min(ys))} mm, from "
        f"({_mm(min(xs))}, {_mm(min(ys))}) mm, does not fit its page of {_mm(width)} × {_mm(height)} mm: "
        "the board PDF is cut at the page",
        where="pdf",
        hint=f"the drawing sheet's paper is {paper}; choose a larger paper for the board, or move the "
        "board onto the page",
    )


__all__ = ["SHEET_CODES", "SchematicFiles", "page_check", "page_size", "schematic_files"]
