# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Inputs and runs of ``fenolite import`` for the tests of change c0275.

The authored project ``tests/data/import_python/two_sheet`` is the one committed input; the other boards
of the tests (no schematic, a group, an edited instance, an old format version) are made from its board
here, in the test's temporary folder, so no copy of it can go stale.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from fenolite.api import Reply, read_board, run

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data" / "import_python"
TWO_SHEET = DATA / "two_sheet"
PROJECT = TWO_SHEET / "two_sheet.kicad_pro"
BOARD = TWO_SHEET / "two_sheet.kicad_pcb"
STAMP = "2026-10-30T00:00:00Z"
OLD_VERSION = 20221018


def copy_project(tmp: Path, name: str = "src") -> Path:
    """A copy of the two-sheet project in ``tmp/name``; its project file."""
    target = tmp / name
    shutil.copytree(TWO_SHEET, target)
    return target / "two_sheet.kicad_pro"


def board_only(tmp: Path) -> Path:
    """The two-sheet board alone, without project file or schematic."""
    folder = tmp / "board_only"
    folder.mkdir()
    target = folder / "board_only.kicad_pcb"
    target.write_bytes(BOARD.read_bytes())
    return target


def _variant(tmp: Path, name: str, text: str) -> Path:
    folder = tmp / name
    folder.mkdir()
    target = folder / f"{name}.kicad_pcb"
    target.write_text(text, encoding="utf-8")
    return target


def grouped(tmp: Path) -> Path:
    """The board with a ``group`` holding the footprint of J1, which the DSL cannot say."""
    text = BOARD.read_text(encoding="utf-8")
    at = text.index('"J1"')
    start = text.rindex("(footprint ", 0, at)
    member = re.search(r'\(uuid "([0-9a-f-]+)"\)', text[start:])
    assert member is not None
    uuid = "0e0e0e0e-0000-4000-8000-000000000001"
    group = f'\t(group ""\n\t\t(uuid "{uuid}")\n\t\t(members "{member.group(1)}")\n\t)\n'
    body = text.rstrip()
    assert body.endswith(")")
    return _variant(tmp, "grouped", body[:-1] + group + ")\n")


def edited(tmp: Path) -> Path:
    """The board with pad 1 of R201 moved 0.1 mm: an instance that differs from R101's footprint."""
    text = BOARD.read_text(encoding="utf-8")
    at = text.index('"R201"')
    pad = text.index('(pad "1"', at)
    old = "(at -0.8 0 180)"
    where = text.index(old, pad)
    return _variant(tmp, "edited", text[:where] + "(at -0.9 0 180)" + text[where + len(old) :])


def old(tmp: Path) -> Path:
    """The board with the format version of KiCad 7, below the read floor."""
    text = BOARD.read_text(encoding="utf-8").replace("(version 20260206)", f"(version {OLD_VERSION})", 1)
    return _variant(tmp, "old", text)


def imported(tmp: Path, source: Path | str, *args: str, out: str = "out") -> Reply:
    """``fenolite import SOURCE --to python --out OUT`` in ``tmp`` with ``--timestamp``; ``--dry-run`` unless
    ``--confirm`` is given."""
    mode = () if "--confirm" in args else ("--dry-run",)
    return run("import", str(source), "--to", "python", "--out", out, *mode, *args, cwd=tmp, timestamp=STAMP)


def build(folder: Path, *args: str) -> Reply:
    """``fenolite build design.py --out built --confirm`` in ``folder``."""
    mode = () if "--dry-run" in args else ("--confirm",)
    return run("build", "design.py", "--out", "built", *mode, *args, cwd=folder, timestamp=STAMP)


def built_board(folder: Path, name: str = "two_sheet"):  # noqa: ANN201  (a fenolite.api.Board)
    return read_board(folder / "built" / f"{name}.kicad_pcb")


__all__ = [
    "BOARD",
    "DATA",
    "PROJECT",
    "STAMP",
    "TWO_SHEET",
    "board_only",
    "build",
    "built_board",
    "copy_project",
    "edited",
    "grouped",
    "imported",
    "old",
]
