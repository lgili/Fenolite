# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the command-level tests of the edit merge (change c0250): the base record of a built
blink, token edits of its board and schematic, the issues of a reply, and the edits of the acceptance
fixture ``tests/data/lens/edit_merge``."""

from __future__ import annotations

import json

from _layout_edit import edit_properties
from _project import Project, footprint

from fenolite.backends.kicad.sch import read_schematic


def base_of(p: Project) -> dict[str, dict[str, dict[str, object]]]:
    return json.loads((p.out / "fenolite-base.json").read_text(encoding="utf-8"))["parts"]


def edit(
    p: Project, changes: dict[str, dict[str, object]], *, board: bool = True, schematic: bool = False
) -> None:
    sheet = p.out / "blink.kicad_sch"
    board_text, sheet_text = edit_properties(
        p.board.read_text(encoding="utf-8") if board else None,
        sheet.read_text(encoding="utf-8") if schematic else None,
        changes,
    )
    if board_text is not None:
        p.board.write_text(board_text, encoding="utf-8")
    if sheet_text is not None:
        sheet.write_text(sheet_text, encoding="utf-8")


def value(p: Project, ref: str) -> tuple[str, str]:
    """The value of ``ref`` on the board and in the schematic."""
    _, component = footprint(p.read(), ref)
    sheet = read_schematic(p.out / "blink.kicad_sch")
    (symbol,) = [s for s in sheet.symbols if s.ref == ref]
    return component.value, symbol.value  # type: ignore[attr-defined]


FIXTURE = "tests/data/lens/edit_merge"
FIXTURE_NAME = "edit_merge"
MM = 1_000_000
FIXTURE_EDITS = [
    "J1#reference",
    "R1#value",
    "R1#property:Part number",
    "led/D1#position",
    "led/R2#position",
    "led/R2#footprint",
]
"""The keys that ``edit_fixture`` edits, sorted as ``result.preserved.edits`` lists them."""


def edit_fixture(p: Project) -> None:
    """The edits of the acceptance loop, by token edit, as KiCad would save them: ``J1`` re-annotated
    ``J9``, ``R1``'s value and user property on the board and the root sheet, ``R2``'s footprint swapped on
    the board and the sheet of ``led`` and moved 2 mm, and ``D1`` moved 1 mm on the board."""
    root, child = p.out / f"{FIXTURE_NAME}.kicad_sch", p.out / "sheets" / "led.kicad_sch"
    board, root_text = edit_properties(
        p.board.read_text(encoding="utf-8"),
        root.read_text(encoding="utf-8"),
        {"J1": {"reference": "J9"}, "R1": {"value": "470", "properties": {"Part number": "FEN-R470"}}},
    )
    board, child_text = edit_properties(
        board,
        child.read_text(encoding="utf-8"),
        {"R2": {"footprint": "Fenolite:Chip_0805", "move": (0, 2 * MM)}},
    )
    board, _ = edit_properties(board, None, {"D1": {"move": (MM, 0)}})
    p.board.write_text(board or "", encoding="utf-8")
    root.write_text(root_text or "", encoding="utf-8")
    child.write_text(child_text or "", encoding="utf-8")


def issues(env: dict[str, object], code: str) -> list[dict[str, str]]:
    return [i for i in env["issues"] if i["code"] == code]  # type: ignore[union-attr, index, misc]


__all__ = ["FIXTURE", "FIXTURE_EDITS", "FIXTURE_NAME", "base_of", "edit", "edit_fixture", "issues", "value"]
