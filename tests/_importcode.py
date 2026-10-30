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
    folder.mkdir(parents=True)
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


TEARDROPS = (
    "(teardrops (best_length_ratio 0.5) (max_length 1) (best_width_ratio 1) (max_width 2) (curved_edges no) "
    "(filter_ratio 0.9) (enabled yes) (allow_two_segments yes) (prefer_zone_connections yes))"
)
"""The teardrop settings of a via as the demo boards of KiCad 9.0 and 10.0 write them (change c0277)."""
TEARDROP_ZONE = (
    '\t(zone (net "GND") (layer "F.Cu") (uuid "0e0e0e0e-0000-4000-8000-000000000002")'
    ' (name "$teardrop_padvia$") (hatch full 0.1) (priority 30000) (attr (teardrop (type {kind})))'
    " (connect_pads yes (clearance 0)) (min_thickness 0.0254) (filled_areas_thickness no)"
    " (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 1) (island_area_min 10))"
    " (polygon (pts (xy 110.3 132.8) (xy 111.2 133) (xy 110.3 133.2))))\n"
)


def teardropped(tmp: Path, settings: str = TEARDROPS, kind: str = "padvia") -> Path:
    """The board whose via at (110, 133) holds ``settings``, whose via at (130, 133) is a blind via over
    both copper layers, as KiCad writes such vias, and which holds a teardrop zone of the type ``kind``
    (c0277)."""
    text = BOARD.read_text(encoding="utf-8")
    first = text.index("(at 110 133)")
    net = text.index('(net "GND")', first)
    text = text[:net] + settings + "\n\t\t" + text[net:]
    second = text.index("(at 130 133)")
    head = text.rindex("(via", 0, second)
    text = text[:head] + "(via blind" + text[head + len("(via") :]
    body = text.rstrip()
    assert body.endswith(")")
    return _variant(tmp, "teardropped", body[:-1] + TEARDROP_ZONE.format(kind=kind) + ")\n")


DRAWN_TEXTS = (
    '\t(gr_text "KNOCK" (at 110 120 0) (layer "F.SilkS" knockout)'
    ' (uuid "0e0e0e0e-0000-4000-8000-000000000011")'
    " (effects (font (size 2 1.25) (thickness 0.275) (bold yes))))\n"
    '\t(gr_text "TWO\\nLINES" (at 120 120 0) (layer "F.SilkS") (uuid "0e0e0e0e-0000-4000-8000-000000000012")'
    " (effects (font (size 1 1) (thickness 0.15))))\n"
    '\t(gr_text "" (at 130 120 0) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000013")'
    " (effects (font (size 1 1) (thickness 0.15))))\n"
    '\t(gr_text "CU" (at 140 120 0) (layer "F.Cu") (uuid "0e0e0e0e-0000-4000-8000-000000000014")'
    " (effects (font (size 1 1) (thickness 0.15))))\n"
    '\t(gr_text "FACE" (at 150 120 0) (layer "F.SilkS") (uuid "0e0e0e0e-0000-4000-8000-000000000015")'
    ' (effects (font (face "KiCad Font") (size 1 1) (thickness 0.15) (italic yes))))\n'
    '\t(gr_text "HIDDEN" (at 150 125 0) (layer "F.SilkS") (uuid "0e0e0e0e-0000-4000-8000-000000000016")'
    " (effects (font (size 1 1) (thickness 0.15)) (hide yes)))\n"
)
"""Board texts of the styles of change c0277, and one hidden text the DSL cannot say."""
DIMENSIONS = (
    '\t(dimension (type aligned) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000021")'
    " (pts (xy 100 140) (xy 120 140)) (height -3)"
    ' (format (prefix "") (suffix "") (units 2) (units_format 1) (precision 4))'
    " (style (thickness 0.2) (arrow_length 1.27) (text_position_mode 0) (arrow_direction outward)"
    " (extension_height 0.58642) (extension_offset 0) (keep_text_aligned yes))"
    ' (gr_text "20.0000 mm" (at 110 137 0) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000021")'
    " (effects (font (size 1.524 1.524) (thickness 0.2)))))\n"
    '\t(dimension (type aligned) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000022")'
    " (pts (xy 100 145) (xy 120 145)) (height -3)"
    ' (format (prefix "") (suffix "") (units 3) (units_format 1) (precision 4))'
    " (style (thickness 0.2) (arrow_length 1.27) (text_position_mode 0) (arrow_direction outward)"
    " (extension_height 0.58642) (extension_offset 0.5) (keep_text_aligned yes))"
    ' (gr_text "20.0000 mm" (at 110 142 0) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000022")'
    " (effects (font (size 1 1) (thickness 0.15)))))\n"
)
"""An aligned dimension of an older demo (extension offset 0) and one in automatic units, which the DSL
cannot say."""


def drawn(tmp: Path) -> Path:
    """The board with ``DRAWN_TEXTS`` and ``DIMENSIONS`` added (change c0277)."""
    body = BOARD.read_text(encoding="utf-8").rstrip()
    assert body.endswith(")")
    return _variant(tmp, "drawn", body[:-1] + DRAWN_TEXTS + DIMENSIONS + ")\n")


def built_for(tmp: Path, major: int) -> Path:
    """The authored two-sheet board built from its script for KiCad ``major`` in ``tmp``."""
    work = tmp / "data" / "src"
    shutil.copytree(DATA / "src", work)
    shutil.copytree(DATA.parent / "libs", tmp / "libs")
    reply = run(
        "build", "two_sheet.py", "--out", "../two_sheet", "--confirm", "--kicad-version", str(major),
        cwd=work, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    return tmp / "data" / "two_sheet" / "two_sheet.kicad_pcb"


def foreign(tmp: Path, board: Path = BOARD) -> Path:
    """The board as another tool would hold it: no ``fenolite.path`` property, and every uuid replaced by
    one that no build derives (version 4 form, from a counter)."""
    text = board.read_text(encoding="utf-8")
    text = re.sub(r'\n\t+\(property "fenolite\.path" "[^"]*"\n(?:\t\t\t.*\n)*?\t\t\)', "", text)
    counter = iter(range(1, 1_000_000))
    stamp = "00000000-0000-4000-8000-"
    text = re.sub(r'\(uuid "[0-9a-f-]{36}"\)', lambda _: f'(uuid "{stamp}{next(counter):012d}")', text)
    assert "fenolite.path" not in text
    return _variant(tmp, "foreign", text)


def sheeted(tmp: Path) -> Path:
    """The ``foreign`` board whose footprints name the KiCad sheets they come from: R101 and D101 the sheet
    ``Power Supply``, R201 and D201 the sheet ``ch2``, J1 the root."""
    text = foreign(tmp / "base").read_text(encoding="utf-8")
    for ref, sheet in (("R101", "Power Supply"), ("D101", "Power Supply"), ("R201", "ch2"), ("D201", "ch2")):
        at = text.index(f'"Reference" "{ref}"')
        path = text.index("\n\t\t(path ", at)
        end = text.index("\n", path + 1)
        stem = sheet.lower().replace(" ", "_")
        extra = f'\n\t\t(sheetname "/{sheet}/")\n\t\t(sheetfile "{stem}.kicad_sch")'
        text = text[:end] + extra + text[end:]
    return _variant(tmp, "sheeted", text)


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
    "built_for",
    "built_board",
    "copy_project",
    "drawn",
    "edited",
    "foreign",
    "grouped",
    "imported",
    "old",
    "sheeted",
    "teardropped",
]
