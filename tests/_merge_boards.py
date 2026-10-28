# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Three versions of one authored board for the three-way merge (change c0207): ``base``, ``ours`` and
``theirs`` are text edits of the KiCad 10 board of ``_projects.authored_project``, with round invented
values. Nothing is read from a library or a third party."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from _projects import authored_project

TRACK_END = "\t\t(end 24 9.46)\n"
"""The end of the authored board's one segment."""
TRACK_UUID = "07af368b-89d1-537e-bd8c-1eba13e6bf03"
R1_AT = "\t\t(at 10 10)\n"
"""The position of the first footprint (R1)."""
EDGE_UUID = "ccf9594f-b824-5f40-82ca-d612c2b5f110"
"""The first ``gr_line`` of the outline."""
NEW_TRACK = (
    "\t(segment\n"
    "\t\t(start 30 20)\n"
    "\t\t(end 35 20)\n"
    "\t\t(width 0.25)\n"
    '\t\t(layer "F.Cu")\n'
    '\t\t(net "GND")\n'
    '\t\t(uuid "00000000-0000-4000-8000-000000000207")\n'
    "\t)\n"
)


@dataclass(frozen=True, slots=True)
class Boards:
    """The folder of the three boards and the text of the base."""

    folder: Path
    base_text: str

    @property
    def base(self) -> Path:
        return self.folder / "base.kicad_pcb"

    @property
    def ours(self) -> Path:
        return self.folder / "ours.kicad_pcb"

    @property
    def theirs(self) -> Path:
        return self.folder / "theirs.kicad_pcb"

    def write(self, name: str, text: str) -> Path:
        path = self.folder / name
        path.write_text(text, encoding="utf-8", newline="")
        return path


def replaced(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


def segment_block(text: str) -> str:
    """The text of the authored segment, from its line to its closing line."""
    end = text.index(f'(uuid "{TRACK_UUID}")')
    start = text.rindex("\t(segment\n", 0, end)
    return text[start : text.index("\t)\n", end) + 3]


def edge_block(text: str) -> str:
    end = text.index(f'(uuid "{EDGE_UUID}")')
    start = text.rindex("\t(gr_line\n", 0, end)
    return text[start : text.index("\t)\n", end) + 3]


def three_boards(tmp_path: Path) -> Boards:
    """``base``; ``ours``, the segment's end moved and a new segment after it; ``theirs``, R1 moved by
    1 mm. The two sides change different items."""
    root = authored_project(tmp_path / "authored", major=10)
    text = (root / "board.kicad_pcb").read_text(encoding="utf-8")
    folder = tmp_path / "boards"
    folder.mkdir()
    boards = Boards(folder, text)
    boards.write("base.kicad_pcb", text)
    segment = segment_block(text)
    moved = replaced(segment, TRACK_END, "\t\t(end 24 9)\n")
    boards.write("ours.kicad_pcb", replaced(text, segment, moved + NEW_TRACK))
    boards.write("theirs.kicad_pcb", replaced(text, R1_AT, "\t\t(at 11 10)\n"))
    return boards


__all__ = [
    "NEW_TRACK",
    "R1_AT",
    "TRACK_END",
    "Boards",
    "edge_block",
    "replaced",
    "segment_block",
    "three_boards",
]
