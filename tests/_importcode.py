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


def _uuid_of_j1(text: str) -> str:
    at = text.index('"J1"')
    start = text.rindex("(footprint ", 0, at)
    member = re.search(r'\(uuid "([0-9a-f-]+)"\)', text[start:])
    assert member is not None
    return member.group(1)


def grouped(tmp: Path) -> Path:
    """The board with a ``group`` holding the footprint of J1 and a track, which the code cannot say: the
    tracks are rows of copper tables (change c0277)."""
    text = BOARD.read_text(encoding="utf-8")
    track = re.search(r'\(segment\b[^()]*(?:\([^()]*\)\s*)*?\(uuid "([0-9a-f-]+)"\)', text)
    assert track is not None
    uuid = "0e0e0e0e-0000-4000-8000-000000000001"
    members = f'"{_uuid_of_j1(text)}" "{track.group(1)}"'
    group = f'\t(group ""\n\t\t(uuid "{uuid}")\n\t\t(members {members})\n\t)\n'
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
    ' (format (prefix "~") (suffix "") (units 2) (units_format 1) (precision 4))'
    " (style (thickness 0.2) (arrow_length 1.27) (text_position_mode 0) (arrow_direction outward)"
    " (extension_height 0.58642) (extension_offset 0.5) (keep_text_aligned yes))"
    ' (gr_text "~20.0000 mm" (at 110 142 0) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000022")'
    " (effects (font (size 1 1) (thickness 0.15)))))\n"
)
"""An aligned dimension of an older demo (extension offset 0) and one with a prefix, which the DSL cannot
say."""


def drawn(tmp: Path) -> Path:
    """The board with ``DRAWN_TEXTS`` and ``DIMENSIONS`` added (change c0277)."""
    body = BOARD.read_text(encoding="utf-8").rstrip()
    assert body.endswith(")")
    return _variant(tmp, "drawn", body[:-1] + DRAWN_TEXTS + DIMENSIONS + ")\n")


SPECIAL_DIMENSIONS = (
    '\t(dimension (type radial) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000031")'
    " (pts (xy 100 150) (xy 103 154)) (leader_length 2.5)"
    ' (format (prefix "R ") (suffix "") (units 2) (units_format 1) (precision 4))'
    " (style (thickness 0.1) (arrow_length 1.27) (text_position_mode 0) (extension_offset 0.5)"
    " (keep_text_aligned yes))"
    ' (gr_text "R 5.0000 mm" (at 104.5 156 306.87) (layer "Dwgs.User")'
    ' (uuid "0e0e0e0e-0000-4000-8000-000000000031") (effects (font (size 1 1) (thickness 0.15)))))\n'
    '\t(dimension (type leader) (layer "Cmts.User") (uuid "0e0e0e0e-0000-4000-8000-000000000032")'
    " (pts (xy 110 150) (xy 113 147))"
    ' (format (prefix "") (suffix "") (units 2) (units_format 0) (precision 4)'
    ' (override_value "0.3mm Thickness"))'
    " (style (thickness 0.1) (arrow_length 1.27) (text_position_mode 0) (text_frame 0)"
    " (extension_offset 0.5))"
    ' (gr_text "0.3mm Thickness" (at 125.7 147 0) (layer "Cmts.User")'
    ' (uuid "0e0e0e0e-0000-4000-8000-000000000032") (effects (font (size 1 1) (thickness 0.15)))))\n'
    '\t(dimension (type center) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000033")'
    " (pts (xy 120 150) (xy 122 150))"
    " (style (thickness 0.1) (arrow_length 1.27) (text_position_mode 0) (extension_offset 0.5)))\n"
    '\t(dimension (type radial) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000034")'
    " (pts (xy 130 150) (xy 132 150)) (leader_length 2)"
    ' (format (prefix "4x R ") (suffix "") (units 3) (units_format 1) (precision 2))'
    " (style (thickness 0.1) (arrow_length 1.27) (text_position_mode 0) (extension_offset 0.5)"
    " (keep_text_aligned yes))"
    ' (gr_text "4x R 2.00 mm" (at 134 150 0) (layer "Dwgs.User")'
    ' (uuid "0e0e0e0e-0000-4000-8000-000000000034") (effects (font (size 1 1) (thickness 0.15)))))\n'
)
"""A radial dimension, a leader and a centre mark in the forms the build writes (the leader's text placed
by hand), and a radial dimension with a prefix of its own, which the DSL cannot say (change c0277)."""


def dimensioned(tmp: Path) -> Path:
    """The board with ``SPECIAL_DIMENSIONS`` added (change c0277)."""
    body = BOARD.read_text(encoding="utf-8").rstrip()
    assert body.endswith(")")
    return _variant(tmp, "dimensioned", body[:-1] + SPECIAL_DIMENSIONS + ")\n")


def unfitted(tmp: Path) -> Path:
    """The board with R101 not populated (``dnp``) and a net tie joining the two pads of R201 (c0277)."""
    text = BOARD.read_text(encoding="utf-8")
    for ref, extra in (("R101", " dnp)"), ("R201", ')\n\t\t(net_tie_pad_groups "1, 2")')):
        at = text.index(f'"Reference" "{ref}"')
        attr = text.index("(attr smd)", at)
        end = attr + len("(attr smd)")
        text = text[: end - 1] + extra + text[end:]
    return _variant(tmp, "unfitted", text)


GROUPS = (
    '\t(group "logo" (uuid "0e0e0e0e-0000-4000-8000-000000000031") (locked yes)'
    ' (members "{j1}" "0e0e0e0e-0000-4000-8000-000000000011" "0e0e0e0e-0000-4000-8000-000000000021"))\n'
    '\t(group "" (uuid "0e0e0e0e-0000-4000-8000-000000000032")'
    ' (members "0e0e0e0e-0000-4000-8000-000000000031" "0e0e0e0e-0000-4000-8000-000000000012"))\n'
    '\t(group "lost" (uuid "0e0e0e0e-0000-4000-8000-000000000033")'
    ' (members "0e0e0e0e-0000-4000-8000-000000000016"))\n'
)
"""A locked group of J1, a text and a dimension; an unnamed group holding it and a text; and a group of the
hidden text, which the code does not write (change c0277)."""


def drawn_grouped(tmp: Path) -> Path:
    """The ``drawn`` board with ``GROUPS`` added (change c0277)."""
    body = BOARD.read_text(encoding="utf-8").rstrip()
    assert body.endswith(")")
    groups = GROUPS.replace("{j1}", _uuid_of_j1(body))
    return _variant(tmp, "drawn", body[:-1] + DRAWN_TEXTS + DIMENSIONS + groups + ")\n")


def shared(tmp: Path) -> Path:
    """The board with R201 renamed R101 and J1 renamed ``REF**``: references a script cannot give a part
    (change c0277)."""
    text = BOARD.read_text(encoding="utf-8")
    assert text.count('"Reference" "R201"') == 1 and text.count('"Reference" "J1"') == 1
    text = text.replace('"Reference" "R201"', '"Reference" "R101"').replace(
        '"Reference" "J1"', '"Reference" "REF**"'
    )
    return _variant(tmp, "shared", text)


ITEMS = (
    '\t(gr_rect (start 100 150) (end 104 152) (stroke (width 0.2) (type solid)) (fill yes) (layer "F.Cu")'
    ' (net "GND") (uuid "0e0e0e0e-0000-4000-8000-000000000051"))\n'
    "\t(gr_poly (pts (xy 120 150) (xy 124 150) (xy 122 153)) (stroke (width -0.000001) (type solid))"
    ' (fill yes) (layer "F.SilkS") (uuid "0e0e0e0e-0000-4000-8000-000000000052"))\n'
    '\t(gr_text "NOTE" (at 130 150 0) (layer "User.2") (uuid "0e0e0e0e-0000-4000-8000-000000000053")'
    " (effects (font (size 1 1) (thickness 0.15))))\n"
    '\t(dimension (type aligned) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000054")'
    " (pts (xy 100 160) (xy 120 160)) (height -3)"
    ' (format (prefix "") (suffix "") (units 3) (units_format 1) (precision 4))'
    " (style (thickness 0.2) (arrow_length 1.27) (text_position_mode 2) (arrow_direction outward)"
    " (extension_height 0.58642) (extension_offset 0.5) (keep_text_aligned yes))"
    ' (gr_text "20.0000 mm" (at 112 156 0) (layer "Dwgs.User") (uuid "0e0e0e0e-0000-4000-8000-000000000054")'
    " (effects (font (size 1.524 1.524) (thickness 0.2)))))\n"
)
"""Board items of change c0277: a copper rectangle of GND, a filled polygon without an outline, a text on a
user layer and a dimension in automatic units whose text is placed by hand."""


def itemized(tmp: Path) -> Path:
    """The board with ``ITEMS``, user layers ``User.1`` and ``User.2`` (named ``notes``), its via at
    (110, 133) free and its GND zone smoothed with fillets of 0.5 mm (change c0277)."""
    text = BOARD.read_text(encoding="utf-8")
    fab = '\t\t(33 "B.Fab" user)\n'
    assert text.count(fab) == 1
    text = text.replace(fab, fab + '\t\t(39 "User.1" user)\n\t\t(41 "User.2" user "notes")\n')
    via = '(at 110 133)\n\t\t(size 0.8)\n\t\t(drill 0.4)\n\t\t(layers "F.Cu" "B.Cu")\n'
    assert text.count(via) == 1
    text = text.replace(via, via + "\t\t(free yes)\n")
    fill = "\t\t\t(thermal_bridge_width 0.5)\n\t\t\t(island_removal_mode 0)\n"
    assert text.count(fill) == 1
    text = text.replace(
        fill,
        "\t\t\t(thermal_bridge_width 0.5)\n\t\t\t(smoothing fillet)\n\t\t\t(radius 0.5)\n"
        "\t\t\t(island_removal_mode 0)\n",
    )
    body = text.rstrip()
    assert body.endswith(")")
    return _variant(tmp, "itemized", body[:-1] + ITEMS + ")\n")


def tuned(tmp: Path) -> Path:
    """The board with a ``generated`` tuning pattern over its first track, in a group, and a placement rule
    area of the multichannel tool (change c0277)."""
    text = BOARD.read_text(encoding="utf-8")
    track = re.search(r'\(segment\b[^()]*(?:\([^()]*\)\s*)*?\(uuid "([0-9a-f-]+)"\)', text)
    assert track is not None
    items = (
        '\t(generated (uuid "0e0e0e0e-0000-4000-8000-000000000061") (type tuning_pattern)'
        ' (name "Tuning Pattern") (layer "B.Cu") (base_line (pts (xy 110 133) (xy 112 134)))'
        f' (target_length 1000000) (members "{track.group(1)}"))\n'
        '\t(group "tuned" (uuid "0e0e0e0e-0000-4000-8000-000000000062")'
        ' (members "0e0e0e0e-0000-4000-8000-000000000061"))\n'
        '\t(zone (net 0) (net_name "") (layers "F.Cu") (uuid "0e0e0e0e-0000-4000-8000-000000000063")'
        ' (name "auto-placement-area-/CH1/") (hatch edge 0.5) (connect_pads (clearance 0))'
        " (min_thickness 0.25)"
        " (keepout (tracks allowed) (vias allowed) (pads allowed) (copperpour allowed) (footprints allowed))"
        ' (placement (enabled yes) (sheetname "/CH1/")) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))'
        " (polygon (pts (xy 100 140) (xy 110 140) (xy 110 150) (xy 100 150))))\n"
    )
    body = text.rstrip()
    assert body.endswith(")")
    return _variant(tmp, "tuned", body[:-1] + items + ")\n")


def rounded(tmp: Path) -> Path:
    """The board whose GND zone has an arc edge, which the reader keeps in the zone's slots (change c0277)."""
    text = BOARD.read_text(encoding="utf-8")
    old = "(xy 135 112) (xy 155 112) (xy 155 128) (xy 135 128)"
    assert text.count(old) == 1
    text = text.replace(old, "(xy 135 112) (arc (start 155 112) (mid 157 120) (end 155 128)) (xy 135 128)")
    return _variant(tmp, "rounded", text)


def notched(tmp: Path) -> Path:
    """The board whose left edge is drawn by D101's own ``Edge.Cuts`` instead of a root line, as a USB
    connector closes a board outline (change c0277)."""
    text = BOARD.read_text(encoding="utf-8")
    edge = re.search(r"\t\(gr_line\s*\(start 100 140\)\s*\(end 100 100\)[\s\S]*?\n\t\)\n", text)
    assert edge is not None
    text = text.replace(edge.group(0), "")
    at = text.index('"Reference" "D101"')
    start = text.rindex("(footprint ", 0, at)
    end = text.index("\n\t\t(pad ", at)
    line = (
        '\n\t\t(fp_line (start -28 25) (end -28 -15) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts")'
    )
    line += ' (uuid "0e0e0e0e-0000-4000-8000-000000000071"))'
    text = text[:end] + line + text[end:]
    assert start < end
    return _variant(tmp, "notched", text)


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
    "unfitted",
]
